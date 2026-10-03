"""Аварии: деформация кузова в месте удара и её последствия.

Каждый удар запоминается в car.deforms как вмятина в координатах кузова:
  s, l   — точка контакта (м): s — вдоль машины (+ вперёд от центра), l — поперёк (+ вправо),
  ds, dl — куда вдавило (единичный вектор внутрь кузова),
  d      — глубина смятия (м), зависит от скорости удара и жёсткости зоны,
  rad    — полуширина пятна контакта (столб узкий, стена широкая, машина средняя),
  h, hr  — высота центра удара и её разброс (бампер другой машины бьёт низко, стена — во всю высоту),
  st     — растяжение вдоль кузова (скользящий удар по борту), seed — «почерк» конкретной аварии.
Форму вмятины строит deform_field(): смятие «гармошкой», складки капота/крыльев, провал двери,
оторванный на одном креплении бампер. car3d.py мнёт по этому полю настоящую геометрию кузова.
"""
import math
import random

import numpy as np
from i18n import T

# на сколько сминается зона при ударе (м) — примерно как у машин 70–80-х без зон деформации
MAX_DEPTH = {"front": 1.05, "rear": 0.95, "left": 0.45, "right": 0.45}
# «тотал»: геометрия кузова (лонжероны, стойки) уведена — чинить дороже, чем стоит машина
TOTAL_LIMITS = {"front": 0.62, "rear": 0.62, "left": 0.30, "right": 0.30}
FRAME_SHOP_PRICE = 2800.0        # стапель у Krüger — восстановление геометрии


def crush_depth(v_ms, kind):
    """Глубина смятия от скорости по нормали (м/с): 15 км/ч — царапины и вмятина, 50 — капот гармошкой."""
    kmh = abs(v_ms) * 3.6
    d = 0.0009 * kmh ** 1.6
    if kind == "pole":
        d *= 1.35                   # узкий столб входит глубже
    elif kind == "car":
        d *= 0.7                    # энергию делят две машины
    return d


def zone_of(ds, dl):
    """Куда пришёлся удар — по направлению вдавливания."""
    if abs(ds) >= abs(dl):
        return "front" if ds < 0 else "rear"
    return "right" if dl < 0 else "left"


def zones(car):
    """Суммарное смятие по зонам (м), с убыванием: вторая вмятина в том же месте добавляет меньше."""
    out = {"front": 0.0, "rear": 0.0, "left": 0.0, "right": 0.0}
    for d in getattr(car, "deforms", []) or []:
        z = zone_of(d["ds"], d["dl"])
        out[z] = math.sqrt(out[z] ** 2 + d["d"] ** 2)
    return out


def is_totaled(car):
    z = zones(car)
    over = sum(z[k] / TOTAL_LIMITS[k] for k in z)
    return any(z[k] >= TOTAL_LIMITS[k] for k in z) or over >= 1.6


def damage_text(car):
    z = zones(car)
    names = {"front": T("перед"), "rear": T("зад"), "left": T("левый борт"), "right": T("правый борт")}
    parts = [T("{0} {1:.0f} см", names[k], v * 100) for k, v in z.items() if v > 0.02]
    return ", ".join(parts)


# ============================================================= запись удара
def record_impact(car, cx, cy, nx, ny, v_normal, v_tangent=0.0, kind="wall", contact_w=1.4, now=None):
    """Удар по машине. (cx, cy) — точка контакта в мире, (nx, ny) — куда толкнуло машину (внутрь кузова),
    v_normal — скорость сближения по нормали (м/с). Возвращает глубину смятия (м)."""
    if v_normal < 2.2:
        return 0.0
    fx, fy = math.cos(car.angle), math.sin(car.angle)
    rx, ry = -fy, fx                                   # вправо от машины
    L, W = car.length, car.spec["width"]
    px, py = cx - car.x, cy - car.y
    s, l = px * fx + py * fy, px * rx + py * ry
    ds, dl = nx * fx + ny * fy, nx * rx + ny * ry
    n = math.hypot(ds, dl) or 1.0
    ds, dl = ds / n, dl / n
    # точку контакта — на поверхность кузова (из точки наружу против направления удара)
    s = max(-L / 2, min(L / 2, s))
    l = max(-W / 2, min(W / 2, l))
    for _ in range(40):
        if abs(s) >= L / 2 - 0.01 or abs(l) >= W / 2 - 0.01:
            break
        s -= ds * 0.05
        l -= dl * 0.05
    zone = zone_of(ds, dl)
    d = min(MAX_DEPTH[zone], crush_depth(v_normal, kind))
    if zone in ("left", "right"):
        d *= 0.8                                       # борт тоньше, но уже — смятие меньше по глубине
    try:
        import electrics
        electrics.on_crash(car, zone, d)               # смятые жгуты: замыкания и обрывы в зоне удара
    except Exception:
        pass
    # физика столкновения касается препятствия несколько кадров подряд и обоими кругами кузова:
    # это ОДНА авария — усиливаем уже записанную вмятину, а не добавляем новую со своим «почерком»
    now = getattr(car, "_clock", 0.0) if now is None else now
    last = car.deforms[-1] if car.deforms else None
    if last is not None and zone_of(last["ds"], last["dl"]) == zone and now - last.get("t", -9.0) < 0.6:
        if d > last["d"]:
            add = d - last["d"]
            last["d"] = round(d, 3)
            last["t"] = now
            _mechanical(car, zone, add, last["s"], last["l"], last["ds"], last["dl"])
        return d
    rad = {"pole": 0.28, "car": 0.95}.get(kind, max(0.35, min(1.5, contact_w / 2)))   # другая машина — широкий кузов
    h, hr = (0.5, 0.42) if kind == "car" else (0.62, 1.6)
    st = min(2.5, abs(v_tangent) / max(1.0, v_normal) * 0.6)    # скользящий удар тянет вмятину вдоль борта
    seed = random.randint(1, 10 ** 6)
    car.deforms.append(dict(s=round(s, 3), l=round(l, 3), ds=round(ds, 3), dl=round(dl, 3), d=round(d, 3),
                            rad=round(rad, 2), h=h, hr=hr, st=round(st, 2), seed=seed, k=kind, t=now))
    if len(car.deforms) > 24:                          # старые мелкие вмятины сливаются
        car.deforms.sort(key=lambda x: -x["d"])
        del car.deforms[24:]
    _mechanical(car, zone, d, s, l, ds, dl)
    return d


def _mechanical(car, zone, d, s, l, ds, dl):
    """Что ломается от удара: зависит от зоны и глубины."""
    k = d * 100                                        # см смятия
    if zone == "front":
        car.wear("lights", k * 1.6)
        car.wear("radiator", k * 1.3)
        car.wear("hood", k * 1.2)
        if d > 0.15:
            car.wear("alternator", k * 0.4)
            car.wear("battery", k * 0.3)
        if d > 0.3:
            car.wear("engine", (k - 30) * 0.9)
            car.wear("steering", (k - 30) * 0.8)
            car.wear("glass", (k - 30) * 1.2)
            if car.coolant > 0:
                car.coolant = max(0.0, car.coolant - (d - 0.3) * 8)
        car.tune_wear("intercooler", k * 1.5)
    elif zone == "rear":
        car.wear("lights", k * 0.8)
        car.wear("trunk", k * 1.3)
        car.wear("exhaust", k * 1.2)
        if d > 0.35:
            car.fuel = max(0.0, car.fuel - (d - 0.35) * 20)          # пробило бак
    else:
        door = "door_l" if zone == "left" else "door_r"
        car.wear(door, k * 2.0)
        if d > 0.2:
            car.wear("glass", k * 0.5)
            car.wear("seats", k * 0.5)
    # удар рядом с колесом: гнёт подвеску — машину уводит, колесо может спустить
    fa = car.spec["axles"][1] - car.length / 2
    ra = car.spec["axles"][0] - car.length / 2
    for axle, pre in ((fa, "f"), (ra, "r")):
        if abs(s - axle) < 0.75 and d > 0.12:
            side = "l" if l < 0 else "r"
            car.wear("shocks", k * 0.6)
            if pre == "f":
                car.wear("steering", k * 0.8)
            car.align = max(-0.06, min(0.06, getattr(car, "align", 0.0) + (-1 if side == "l" else 1) * d * 0.035))
            if d > 0.3:
                car.wear(f"tire_{pre}{side}", 60 + k)
    if zone == "front" and d > 0.2 and abs(l) > 0.25:       # удар углом — уводит лонжерон
        car.align = max(-0.06, min(0.06, getattr(car, "align", 0.0) + (1 if l > 0 else -1) * d * 0.02))


def bounce(car, nx, ny, cx, cy, restitution=0.15):
    """Отскок: гасим скорость по нормали, трение по касательной, от удара углом машину разворачивает."""
    fx, fy = math.cos(car.angle), math.sin(car.angle)
    rx, ry = -fy, fx
    vx = fx * car.speed + rx * car.vlat
    vy = fy * car.speed + ry * car.vlat
    vn = vx * nx + vy * ny
    if vn >= 0:
        return 0.0
    j = -(1 + restitution) * vn
    vx += j * nx
    vy += j * ny
    tx, ty = -ny, nx
    vt = vx * tx + vy * ty
    vt *= max(0.4, 1.0 - 0.06 * j)                     # трение металла о препятствие
    vn2 = vx * nx + vy * ny
    vx, vy = nx * vn2 + tx * vt, ny * vn2 + ty * vt
    car.speed = vx * fx + vy * fy
    car.vlat = vx * rx + vy * ry
    # момент от удара вне центра масс
    ax, ay = cx - car.x, cy - car.y
    torque = ax * ny - ay * nx
    car.ang_vel += torque * j * 0.35 / max(1.0, car.length / 2)
    car.ang_vel = max(-4.0, min(4.0, car.ang_vel))
    return -vn


# ============================================================= поле деформации (numpy)
def _smooth(x, a, b):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def _quiet(fn):
    """numpy 2.0 + Accelerate (macOS) пишет ложные предупреждения в matmul — результаты при этом верные."""
    def w(*a, **k):
        with np.errstate(all="ignore"):
            return fn(*a, **k)
    return w


@_quiet
def deform_field(deforms, P, dims, hang=True):
    """Смещения вершин P (N×3, оси кузова car3d: x — вправо, y — вверх, z — вперёд) от всех вмятин."""
    W2, L2, sill, belt, roof = dims
    D = np.zeros_like(P)
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    for dd in deforms:
        rng = np.random.default_rng(dd.get("seed", 1))
        ph = rng.uniform(0, 6.3, 6)
        fr = rng.uniform(0.8, 1.3, 3)
        depth = dd["d"]
        # тяжесть: до ~55 км/ч в стену почти 0 (аккуратная гармошка), к ~90 км/ч — 1 (рваный металл)
        # (по энергии удара: столб даёт глубже при той же скорости, машина-машина — мельче)
        eq = depth / {"pole": 1.35, "car": 0.7}.get(dd.get("k", "wall"), 1.0)
        sev = float(np.clip((eq - 0.5) / 0.5, 0.0, 1.0))
        dirv = np.array([dd["dl"], 0.0, dd["ds"]])
        dirv /= np.linalg.norm(dirv) or 1.0
        tang = np.array([dirv[2], 0.0, -dirv[0]])
        C = np.array([dd["l"], dd["h"], dd["s"]])
        R = P - C
        q = R @ dirv                                    # насколько вершина «за» точкой удара (внутрь кузова)
        t = R @ tang
        rad = dd["rad"] * (1 + dd.get("st", 0.0))
        wt = np.exp(-(t / rad) ** 2 * 1.2)
        if dd["rad"] >= 1.2:                            # стена: давит всю ширину; лонжероны по краям чуть жёстче
            wt = (0.7 + 0.3 * wt) * (1 + (0.06 + 0.2 * sev) * np.sin(t * 3.3 + ph[3])
                                     + (0.03 + 0.09 * sev) * np.sin(t * 7.9 + ph[4]))
        wv = np.exp(-((y - dd["h"]) / dd["hr"]) ** 2)
        lz = depth * 1.4 + 0.3                          # длина зоны смятия
        f = np.where(q < 0, 1.0, np.clip(1.0 - q / lz, 0.0, 1.0) ** 1.5)
        if abs(dd["ds"]) >= abs(dd["dl"]):
            # моторный щит и салон жёсткие: гармошка живёт в моторном отсеке (~1.1 м), салон мнётся только
            # в экстремальных ударах
            fw = 1.1 + 0.35 * sev
            f = f * (1.0 - (1.0 - 0.5 * sev) * _smooth(q, fw - 0.25, fw + 0.2))
        if abs(dd["ds"]) >= abs(dd["dl"]) and dd.get("k", "wall") != "car":
            # бампер выступает и принимает удар первым; верх морды (кромка капота) уходит чуть меньше
            wv = wv * (1.18 - 0.28 * _smooth(y, sill + 0.05, belt + 0.05))
        amp = depth * f * wt * wv
        # «почерк» аварии: плавные волны складок, у каждой аварии свои
        noise = (np.sin(x * 6.5 * fr[0] + ph[0]) * np.sin(z * 5.1 * fr[1] + ph[1]) +
                 0.6 * np.sin(y * 8.3 * fr[2] + z * 3.7 + ph[2]))
        disp = np.outer(amp * (1 + (0.04 + 0.14 * sev) * noise), dirv)
        bk = depth * 4 * f * (1 - f) * wt                 # выпучивание: сильнее всего в середине зоны смятия
        frontal = abs(dd["ds"]) >= abs(dd["dl"])
        if frontal:
            top = _smooth(y, belt - 0.12, belt + 0.1) * (1 - _smooth(y, roof - 0.25, roof))
            # капот/крышка багажника встают «домиком» и мнутся волнами
            # одна чёткая складка поперёк капота — ближе к его середине даже при слабом ударе;
            # с тяжестью удара — перекос и волны
            lz2 = max(lz, 1.0)
            f2 = np.where(q < 0, 1.0, np.clip(1.0 - q / lz2, 0.0, 1.0) ** 1.3)
            bk2 = min(depth, 0.45) * 4 * f2 * (1 - f2) * wt + bk * 0.5
            disp[:, 1] += bk2 * top * (0.42 + (0.03 + 0.12 * sev) * np.sin(x * 4.0 + ph[3]))
            # крылья выгибаются наружу складками
            side = _smooth(np.abs(x), W2 * 0.55, W2 * 0.95)
            disp[:, 0] += np.sign(x) * bk * side * (0.1 + (0.02 + 0.07 * sev) * np.sin(z * 9 + ph[4]))
            disp[:, 1] += bk * side * (0.03 + 0.1 * sev) * np.sin(z * 11 + ph[5])
            # бампер: при сильном ударе висит на одном креплении
            if depth > 0.35 and hang:
                end = L2 if dd["ds"] < 0 else -L2
                bump = (y < sill + 0.28) & (np.abs(z) > abs(end) - 0.12) & (np.sign(z) == np.sign(end))
                hang_side = 1 if dd["seed"] % 2 else -1
                drop = min(0.28, (depth - 0.35) * 0.5) * np.clip((x * hang_side + W2) / (2 * W2), 0, 1)
                disp[:, 1] -= drop * bump * wt.clip(0.5, 1)
                disp[:, 2] += np.sign(end) * drop * 0.35 * bump
        else:
            # борт: дверь проваливается по линии удара, порог и крыша жёстче
            mid = np.exp(-((y - (sill + belt) / 2 - 0.1) / 0.32) ** 2)
            stiff = 0.55 + 0.45 * mid
            disp *= stiff[:, None]
            disp[:, 2] += bk * (0.04 + 0.1 * sev) * np.sin(z * 7 + ph[3]) * mid
            roofm = _smooth(y, roof - 0.3, roof)
            disp[:, 1] -= bk * 0.25 * roofm
        D += disp
    mag = np.linalg.norm(D, axis=1)
    k = np.where(mag > 1.2, 1.2 / np.maximum(mag, 1e-6), 1.0)
    return D * k[:, None]


# ============================================================= меши (разбиение и смятие)
THR = 0.11          # длина ребра после разбиения (м)


def _normals(tri):
    e1 = tri[:, 1] - tri[:, 0]
    e2 = tri[:, 2] - tri[:, 0]
    n = np.cross(e2, e1)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    return n / np.maximum(ln, 1e-9)


def _grid_quad(p, c, uv, nu, nv):
    """Бiлинейная сетка на четырёхугольнике: вершины, цвета, uv и треугольники (в порядке исходного обхода)."""
    u = np.linspace(0, 1, nu + 1)
    v = np.linspace(0, 1, nv + 1)
    U, V = np.meshgrid(u, v, indexing="ij")
    U, V = U.ravel()[:, None], V.ravel()[:, None]

    def bl(a):
        return (a[0] * (1 - U) * (1 - V) + a[1] * U * (1 - V) + a[2] * U * V + a[3] * (1 - U) * V)
    pts = bl(p)
    cols = bl(c)
    uvs = bl(uv) if uv is not None else None
    idx = np.arange((nu + 1) * (nv + 1)).reshape(nu + 1, nv + 1)
    a = idx[:-1, :-1].ravel()
    b = idx[1:, :-1].ravel()
    cc = idx[1:, 1:].ravel()
    d = idx[:-1, 1:].ravel()
    tris = np.concatenate([np.stack([a, b, cc], 1), np.stack([a, cc, d], 1)])
    return pts, cols, uvs, tris


def _grid_tri(p, c, uv, n):
    pts, cols, uvs = [], [], []
    index = {}
    for i in range(n + 1):
        for j in range(n + 1 - i):
            w1, w2 = i / n, j / n
            w0 = 1 - w1 - w2
            index[(i, j)] = len(pts)
            pts.append(w0 * p[0] + w1 * p[1] + w2 * p[2])
            cols.append(w0 * c[0] + w1 * c[1] + w2 * c[2])
            if uv is not None:
                uvs.append(w0 * uv[0] + w1 * uv[1] + w2 * uv[2])
    tris = []
    for i in range(n):
        for j in range(n - i):
            tris.append((index[(i, j)], index[(i + 1, j)], index[(i, j + 1)]))
            if j < n - i - 1:
                tris.append((index[(i + 1, j)], index[(i + 1, j + 1)], index[(i, j + 1)]))
    return np.array(pts), np.array(cols), (np.array(uvs) if uv is not None else None), np.array(tris)


@_quiet
def deform_mesh(src, M, Minv, deforms, dims, hang=True):
    """Смять меш: src = (вершины, цвета, нормали, uv, многоугольники) в своих осях; M — в оси кузова.
    Возвращает (vertices, triangles, colors, normals, uvs) или None, если вмятины его не касаются."""
    V = np.asarray(src[0], dtype=float)
    Cc = np.asarray(src[1], dtype=float)
    N0 = np.asarray(src[2], dtype=float)
    UV = np.asarray(src[3], dtype=float) if src[3] is not None else None
    polys = src[4]
    if len(V) == 0:
        return None

    def to_body(p):
        return p @ M[:3, :3] + M[3, :3]

    Vb = to_body(V)
    Dv = deform_field(deforms, Vb, dims)
    if np.abs(Dv).max() < 0.002:
        # вершины не задело — но большая грань может быть задета серединой
        lo, hi = Vb.min(0), Vb.max(0)
        probe = lo + (hi - lo) * np.random.default_rng(0).random((64, 3))
        if np.abs(deform_field(deforms, probe, dims)).max() < 0.004:
            return None
    out_v, out_c, out_n, out_uv = [], [], [], []
    keep_tris = []                                      # незадетые грани — как были
    for base, cnt in polys:
        p = V[base:base + cnt]
        pb = Vb[base:base + cnt]
        d = Dv[base:base + cnt]
        span = np.linalg.norm(pb.max(0) - pb.min(0))
        hit = np.abs(d).max() > 0.002
        if not hit and span > 0.3:
            probe = pb.mean(0)[None, :] + (pb - pb.mean(0)) * 0.5
            hit = np.abs(deform_field(deforms, np.vstack([probe, pb.mean(0)[None, :]]), dims)).max() > 0.002
        c = Cc[base:base + cnt]
        uv = UV[base:base + cnt] if UV is not None else None
        if not hit:
            keep_tris.extend((base, base + i, base + i + 1) for i in range(1, cnt - 1))
            continue
        if cnt == 4:
            e = [np.linalg.norm(pb[1] - pb[0]), np.linalg.norm(pb[2] - pb[1]),
                 np.linalg.norm(pb[3] - pb[2]), np.linalg.norm(pb[0] - pb[3])]
            nu = int(min(30, max(1, math.ceil(max(e[0], e[2]) / THR))))
            nv = int(min(30, max(1, math.ceil(max(e[1], e[3]) / THR))))
            gp, gc, guv, gt = _grid_quad(p, c, uv, nu, nv)
            pieces = [(gp, gc, guv, gt)]
        else:
            pieces = []
            for i in range(1, cnt - 1):
                tri_ix = [0, i, i + 1]
                tb = pb[tri_ix]
                n_ = int(min(20, max(1, math.ceil(max(np.linalg.norm(tb[1] - tb[0]), np.linalg.norm(tb[2] - tb[1]),
                                                     np.linalg.norm(tb[0] - tb[2])) / THR))))
                pieces.append(_grid_tri(p[tri_ix], c[tri_ix], uv[tri_ix] if uv is not None else None, n_))
        for gp, gc, guv, gt in pieces:
            gb = to_body(gp)
            gd = deform_field(deforms, gb, dims, hang)
            nb = gb + gd
            gl = (np.hstack([nb, np.ones((len(nb), 1))]) @ Minv)[:, :3]
            # краска трескается в местах сильного смятия — видно металл/грунт
            dm = np.linalg.norm(gd, axis=1)
            kk = np.clip((dm - 0.03) * 1.4, 0, 0.4)[:, None]
            col = gc.copy()
            col[:, :3] = col[:, :3] * (1 - kk) + np.array([0.36, 0.35, 0.33]) * kk
            tri = gl[gt]
            n = _normals(tri)
            ref = N0[base]
            cosn = n @ ref
            flip = cosn < -0.6                         # сложившаяся складка: нормаль не переворачиваем резко
            n[flip] *= -1
            # вмятина в тени: чем сильнее наклонилась поверхность, тем темнее (виден рельеф при любом свете)
            shade = 0.62 + 0.38 * np.clip(np.abs(cosn), 0, 1) ** 2
            col = col[gt]
            col[..., :3] *= shade[:, None, None]
            out_v.append(tri)
            out_c.append(col)
            out_n.append(np.repeat(n[:, None, :], 3, 1))
            if guv is not None:
                out_uv.append(guv[gt])
    if keep_tris:
        kt = np.array(keep_tris)
        out_v.append(V[kt])
        out_c.append(Cc[kt])
        out_n.append(N0[kt])
        if UV is not None:
            out_uv.append(UV[kt])
    Vt = np.concatenate([a.reshape(-1, 3) for a in out_v])
    Ct = np.concatenate([a.reshape(-1, Cc.shape[1]) for a in out_c])
    Nt = np.concatenate([a.reshape(-1, 3) for a in out_n])
    UVt = np.concatenate([a.reshape(-1, 2) for a in out_uv]) if UV is not None and out_uv else None
    tris = np.arange(len(Vt)).reshape(-1, 3)
    return Vt, tris, Ct, Nt, UVt


def rigid_offset(deforms, center_body, dims):
    """Смещение маленькой детали целиком (фары, детали в моторном отсеке)."""
    return deform_field(deforms, np.asarray([center_body], dtype=float), dims)[0]


def random_crash(car, rng, severity=1.0):
    """Старая авария у брошенной/битой машины (для свалки): 1–2 удара случайной силы и направления."""
    for _ in range(rng.choice((1, 1, 2))):
        side = rng.choice(("front", "front", "rear", "left", "right"))
        L, W = car.length, car.spec["width"]
        fx, fy = math.cos(car.angle), math.sin(car.angle)
        rx, ry = -fy, fx
        if side == "front":
            s, l, ns, nl = L / 2, rng.uniform(-W / 2, W / 2), -1.0, rng.uniform(-0.3, 0.3)
        elif side == "rear":
            s, l, ns, nl = -L / 2, rng.uniform(-W / 2, W / 2), 1.0, rng.uniform(-0.3, 0.3)
        else:
            sg = 1 if side == "right" else -1
            s, l, ns, nl = rng.uniform(-L / 3, L / 3), sg * W / 2, rng.uniform(-0.3, 0.3), -sg
        n = math.hypot(ns, nl)
        nx, ny = (fx * ns + rx * nl) / n, (fy * ns + ry * nl) / n
        cx, cy = car.x + fx * s + rx * l, car.y + fy * s + ry * l
        v = rng.uniform(5, 15) * severity
        state = random.getstate()
        random.seed(rng.randint(0, 10 ** 9))
        record_impact(car, cx, cy, nx, ny, v, rng.uniform(0, 4), rng.choice(("wall", "pole", "car")),
                      rng.uniform(0.6, 3.0))
        random.setstate(state)
