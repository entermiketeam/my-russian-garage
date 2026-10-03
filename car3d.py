"""3D-модель ВАЗ 2102 (универсал), машины трафика и эффекты (дым, свет фар).

Локальные оси модели: x — вправо, y — вверх, z — вперёд. Центр кузова — (0, 0, 0) на земле.
Профиль из 2D-рисунка: sx от 0 (задний край) до 4.02 (передний) -> z = sx - 2.015.
"""
import under3d as _under3d
import math
import random

from panda3d.core import TransparencyAttrib
from ursina import Entity, Text, color, Vec3, destroy

from mesh3d import MeshBuilder
from city3d import additive
import textures3d
from car import WHEELBASE
from models import MODELS
from car3d_extra import Extras

PAINT = (196, 186, 150)
PAINT_DARK = (178, 168, 134)
CHROME = (185, 185, 180)
GLASS = (70, 92, 108)
VINYL = (108, 62, 42)
DASH = (38, 34, 32)


def Z(sx):
    return sx - 2.015


def wheel_mesh(r=0.29, w=0.165, seg=14, rim=(112, 106, 96)):
    """Колесо вдоль оси x: шина, диск, колпак."""
    mb = MeshBuilder()
    pts = [(math.cos(2 * math.pi * i / seg), math.sin(2 * math.pi * i / seg)) for i in range(seg)]
    x0, x1 = -w / 2, w / 2
    for i in range(seg):
        a, b = pts[i], pts[(i + 1) % seg]
        mb.poly([(x0, a[1] * r, a[0] * r), (x1, a[1] * r, a[0] * r), (x1, b[1] * r, b[0] * r), (x0, b[1] * r, b[0] * r)],
                (28, 28, 28), (0, (a[1] + b[1]), (a[0] + b[0])))
    for side, xs in ((1, x1), (-1, x0)):
        mb.poly([(xs, p[1] * r, p[0] * r) for p in pts], (32, 32, 32), (side, 0, 0))
        rr = r * 0.62
        mb.poly([(xs + side * 0.005, p[1] * rr, p[0] * rr) for p in pts], rim, (side, 0, 0))
        hr = r * 0.25
        mb.poly([(xs + side * 0.012, p[1] * hr, p[0] * hr) for p in pts], (200, 198, 190), (side, 0, 0))
        # болты (чтобы было видно вращение)
        for k in range(4):
            a = k * math.pi / 2 + 0.3
            cy, cz = math.sin(a) * r * 0.42, math.cos(a) * r * 0.42
            s = 0.022
            mb.poly([(xs + side * 0.01, cy - s, cz - s), (xs + side * 0.01, cy + s, cz - s),
                     (xs + side * 0.01, cy + s, cz + s), (xs + side * 0.01, cy - s, cz + s)], (60, 58, 55), (side, 0, 0))
    return mb.build()


def ring_entity(parent, radius, thick, col, **kw):
    """Руль: кольцо одним мешем (много машин — мало объектов)."""
    c = tuple(int(v * 255) for v in (col[0], col[1], col[2])) if max(col[0], col[1], col[2]) <= 1.0 else tuple(col[:3])
    mb = MeshBuilder()
    n = 20
    t = thick / 2
    for i in range(n):
        a0 = 2 * math.pi * i / n
        a1 = 2 * math.pi * (i + 1) / n
        ro, ri = radius + t, radius - t
        p = lambda a_, r_, z_: (math.cos(a_) * r_, math.sin(a_) * r_, z_)
        mb.poly([p(a0, ri, -t), p(a1, ri, -t), p(a1, ro, -t), p(a0, ro, -t)], c, (0, 0, -1))
        mb.poly([p(a0, ri, t), p(a1, ri, t), p(a1, ro, t), p(a0, ro, t)], c, (0, 0, 1))
        mb.poly([p(a0, ro, -t), p(a1, ro, -t), p(a1, ro, t), p(a0, ro, t)], c,
                (math.cos((a0 + a1) / 2), math.sin((a0 + a1) / 2), 0))
    return Entity(parent=parent, model=mb.build(), double_sided=True, **kw)


def glass_entity(parent, pts, col=GLASS, alpha=0.35):
    mb = MeshBuilder()
    mb.poly(pts, (*col, int(alpha * 255)), None)
    e = Entity(parent=parent, model=mb.build(keep=True), double_sided=True)
    e.setTransparency(TransparencyAttrib.MAlpha)
    e.setDepthWrite(False)
    e.setBin("transparent", 20)
    return e


class Car3D(Extras):
    def __init__(self, car):
        self.car = car
        self.root = Entity()
        self.body = Entity(parent=self.root)
        self.t = 0.0
        self.spin = 0.0
        self._rust_key = None
        self._built_color = car.color
        self._build()
        self.smoke = Smoke()
        self._capture_deform()
        self.apply_deforms()

    # ------------------------------------------------------------------ вмятины (damage.py)
    def _dims(self):
        car = self.car
        W2, L2 = car.spec["width"] / 2, car.length / 2
        if car.model in MODELS:
            B = MODELS[car.model]["body"]
            return (W2, L2, B["sill"], B["belt"], B["roof_y"])
        if car.model == "ae86":
            return (W2, L2, 0.30, 0.80, 1.30)
        return (W2, L2, 0.30, 0.86, 1.42)

    def _capture_deform(self):
        """Запомнить исходную геометрию кузова, пока капот закрыт: по ней потом мнутся вмятины."""
        import numpy as np
        from ursina import Text as _Text

        def mat(e):
            m = e.getMat(self.body)
            return np.array([[m.getCell(i, j) for j in range(4)] for i in range(4)], dtype=float)

        skip = {id(e) for e, _ in getattr(self, "snow_parts", [])}
        # ржавчина салона пересоздаётся при каждом изменении ржавчины (в т.ч. от удара) — её не мнём,
        # иначе в списке останется ссылка на удалённый объект (это и был вылет при сильной аварии)
        if getattr(self, "int_rust", None) is not None:
            skip.add(id(self.int_rust))
        self._def_meshes, self._def_rigid = [], []
        stack = list(self.body.children)
        while stack:
            e = stack.pop()
            stack.extend(getattr(e, "children", []))
            if id(e) in skip or e.model is None:
                continue
            M = mat(e)
            if abs(np.linalg.det(M[:3, :3])) < 1e-9:           # сплющенная (скрытая) деталь
                continue
            if e is self.side_l or e is self.side_r:
                quad = ([(-0.5, -0.5, 0.0), (0.5, -0.5, 0.0), (0.5, 0.5, 0.0), (-0.5, 0.5, 0.0)], [(1, 1, 1, 1)] * 4,
                        [(0, 0, -1)] * 4, [(0, 0), (1, 0), (1, 1), (0, 1)], [(0, 4)])
                self._def_meshes.append([e, quad, M, False, False])
            elif getattr(e.model, "_src", None) is not None and not isinstance(e, _Text):
                self._def_meshes.append([e, e.model._src, M, False, True])
            else:
                par = e.parent if e.parent is not None else self.body
                Mp = mat(par) if par is not self.body else np.eye(4)
                self._def_rigid.append([e, Vec3(e.position), M[3, :3].copy(), np.linalg.inv(Mp)[:3, :3]])
        for i, rec in enumerate(self._def_meshes):
            rec.append(i)                                   # постоянный номер детали (ключ кэша)
        self._wheel_base = {k: (Vec3(pv.position), pv.rotation_z) for k, (pv, _, _) in self.wheels.items()}
        self._deform_key = ()

    def _deform_sig(self):
        d = self.car.deforms
        return (len(d), round(sum(x["d"] for x in d), 3)) if d else ()

    @staticmethod
    def _make_mesh(V, T, C, N, UV):
        from ursina import Mesh

        def tup(a):
            return list(map(tuple, a.tolist()))
        return Mesh(vertices=tup(V), triangles=T.reshape(-1).tolist(), colors=tup(C), normals=tup(N),
                    uvs=tup(UV) if UV is not None else None)

    @staticmethod
    def _alive(e):
        try:
            return e is not None and not e.isEmpty()
        except Exception:
            return False

    def apply_deforms(self):
        """Смять геометрию по вмятинам машины (или вернуть исходную после рихтовки).
        Графика вмятин никогда не должна ронять игру: сбойная деталь просто остаётся несмятой."""
        try:
            self._apply_deforms()
        except Exception as ex:                      # pragma: no cover — страховка
            print("Вмятины: не удалось смять кузов:", ex)
            self._deform_key = self._deform_sig()

    def _apply_deforms(self):
        sig = self._deform_sig()
        if sig == self._deform_key:
            return
        self._deform_key = sig
        import numpy as np
        import damage
        defs = self.car.deforms
        dims = self._dims()
        cache = getattr(self.car, "_def_cache", None)
        if cache is None or cache.get("sig") != sig:
            cache = self.car._def_cache = {"sig": sig}          # смятая геометрия переживает пересоздание модели
        # объекты, удалённые с момента запоминания, — выбрасываем
        self._def_meshes = [r for r in self._def_meshes if self._alive(r[0])]
        self._def_rigid = [r for r in self._def_rigid if self._alive(r[0])]
        for rec in self._def_meshes:
            e, src, M, changed, hang, idx = rec
            ck = (idx, len(src[0]))
            if ck in cache:
                res = cache[ck]
            else:
                res = damage.deform_mesh(src, M, np.linalg.inv(M), defs, dims, hang) if defs else None
                if defs:
                    cache[ck] = res
            if res is None:
                if not changed:
                    continue
                V = np.asarray(src[0], float)
                T = np.array([(b, b + i, b + i + 1) for b, n in src[4] for i in range(1, n - 1)])
                res = (V, T, np.asarray(src[1], float), np.asarray(src[2], float),
                       np.asarray(src[3], float) if src[3] is not None else None)
                rec[3] = False
            else:
                rec[3] = True
            if not all(np.isfinite(a).all() for a in (res[0], res[3]) if a is not None):
                continue                                  # испорченная геометрия — не показываем
            try:
                tex = e.texture
                e.model = self._make_mesh(*res)
                if tex is not None:
                    e.texture = tex
                e.double_sided = True
            except Exception as ex:
                print("Вмятины: деталь пропущена:", ex)
        for e, pos0, cb, inv_p in self._def_rigid:
            dv = damage.rigid_offset(defs, cb, dims) if defs else np.zeros(3)
            dl = dv @ inv_p
            if np.isfinite(dl).all():
                e.position = pos0 + Vec3(*dl)
        # погнутая подвеска: колесо смещается и заваливается
        sp = self.car.spec
        for slot, (pivot, _, _) in self.wheels.items():
            pos0, rz0 = self._wheel_base[slot]
            if not defs:
                pivot.position, pivot.rotation_z = pos0, rz0
                continue
            dv = damage.rigid_offset(defs, np.array([pos0.x, sp["wheel_r"], pos0.z]), dims)
            mag = float(np.linalg.norm(dv))
            k = min(1.0, 0.22 / mag) if mag > 0.22 else 1.0
            pivot.x, pivot.z = pos0.x + dv[0] * k * 0.6, pos0.z + dv[2] * k * 0.6
            pivot.rotation_z = rz0 + max(-14.0, min(14.0, dv[0] * 55))

    # ------------------------------------------------------------------ сборка
    def _build(self):
        b = self.body
        L = self.car.length
        self.Z = lambda sx: sx - L / 2
        self.popups = []
        self.hood_rest = 0.0
        self.plate_texts = []
        if self.car.model == "ae86":
            self._build_ae86(b)
        elif self.car.model in MODELS:
            self._build_generic(b)
        else:
            self._build_vaz(b)
        Z = self.Z
        # борта (текстура с ржавчиной)
        from textures3d import SIDE_W, SIDE_H, SIDE_PPM, SIDE_X0
        qw, qh = SIDE_W / SIDE_PPM, SIDE_H / SIDE_PPM
        cz = Z(-SIDE_X0 + qw / 2)
        cy = qh / 2 - 2 / SIDE_PPM
        sx_ = self.car.spec["width"] / 2 + 0.005
        self.side_r = Entity(parent=b, model="quad", position=(sx_, cy, cz), rotation_y=-90, scale=(qw, qh))
        # левый борт: картинка в текстуре отражена (перед слева)
        self.side_l = Entity(parent=b, model="quad", position=(-sx_, cy, cz), rotation_y=90, scale=(qw, qh))
        for e in (self.side_r, self.side_l):
            e.setTransparency(TransparencyAttrib.MBinary)
        self.refresh_rust(force=True)

        # колёса
        self.wheels = {}
        sp = self.car.spec
        rz, fz = Z(sp["axles"][0]), Z(sp["axles"][1])
        tr = sp["track"]
        self.wr = sp["wheel_r"]
        rim = {"ae86": (170, 170, 172), "w123": (185, 185, 188), "golf": (150, 150, 150),
               "trabant": (200, 200, 195)}.get(self.car.model, (112, 106, 96))
        for slot, (x, z) in {"tire_fl": (-tr, fz), "tire_fr": (tr, fz),
                             "tire_rl": (-tr, rz), "tire_rr": (tr, rz)}.items():
            pivot = Entity(parent=self.root, position=(x, self.wr, z))
            tw = {"ae86": 0.18, "trabant": 0.145, "golf": 0.145, "kadett": 0.155, "taunus": 0.175, "w123": 0.175}
            spin = Entity(parent=pivot, model=wheel_mesh(self.wr, tw.get(self.car.model, 0.165), rim=rim),
                          double_sided=True)
            bricks = Entity(parent=self.root, position=(x, 0, z), enabled=False)
            for k in range(3):
                Entity(parent=bricks, model="cube", color=color.rgb(150, 70, 50), position=(0, 0.05 + k * 0.08, 0),
                       scale=(0.12, 0.075, 0.25))
            self.wheels[slot] = (pivot, spin, bricks)

        # свет фар на асфальте
        self.beams = []
        for x in (-0.55, 0.55):
            bm = Entity(parent=self.root, model="quad", texture=textures3d.beam(), rotation_x=90,
                        position=(x * 3, 0.13, self.car.length / 2 + 14), scale=(9, 28), color=color.rgba(255, 240, 200, 120))
            additive(bm)
            bm.enabled = False
            self.beams.append(bm)
        self._build_snow()
        self._build_extras()          # двери, багажник, поворотники, приборы, детали (car3d_extra.py)
        self.set_hood(getattr(self.car, "hood_open", False))

    def _build_generic(self, b):
        """3D-кузов найденной машины по параметрам модели (models.py)."""
        import random as _r
        Z = self.Z
        car = self.car
        info = MODELS[car.model]
        B = info["body"]
        sp = car.spec
        rng = _r.Random(car.seed)
        L = car.length
        W2 = sp["width"] / 2
        paint = car.paint
        top_c = tuple(max(0, int(c * 0.93)) for c in paint)
        dark = (26, 24, 22)
        chrome = (185, 185, 180)
        black = (28, 28, 30)
        sill, belt, roof_y = B["sill"], B["belt"], B["roof_y"]
        style = B["style"]
        rb_y = belt if style == "hatch" else B["trunk_y"]
        rgb, rs, re, wb = B["rgb"], B["roof_start"], B["roof_end"], B["ws_base"]
        nose_y, hood_y = B["nose_y"], B["hood_y"]
        seat_c = rng.choice([(108, 62, 42), (40, 40, 44), (60, 70, 110), (170, 150, 110), (120, 40, 35)])
        mb = MeshBuilder()
        for sx in sp["axles"]:
            for side in (-1, 1):
                mb.box(side * 0.28, sill + 0.02, Z(sx - 0.42), side * (W2 - 0.23), sill + 0.44, Z(sx + 0.42), dark)
        mb.box(-(W2 - 0.1), sill + 0.02, Z(wb), W2 - 0.1, sill + 0.1, Z(L - 0.1), (30, 28, 26))
        mb.box(-(W2 - 0.08), sill, Z(0.3), W2 - 0.08, sill + 0.06, Z(wb), (38, 36, 34))
        # нос
        mb.box(-(W2 - 0.01), sill + 0.03, Z(L - 0.08), W2 - 0.01, nose_y, Z(L), paint, top=top_c)
        g = B["grille"]
        fz = Z(L) + 0.005
        if g == "slots":
            for k in range(3):
                mb.box(-0.30, nose_y - 0.24 + k * 0.05, fz, 0.30, nose_y - 0.215 + k * 0.05, fz + 0.01, black)
        elif g == "wide_chrome":
            mb.box(-(W2 - 0.45), nose_y - 0.22, fz, W2 - 0.45, nose_y - 0.05, fz + 0.01, chrome)
            mb.box(-(W2 - 0.48), nose_y - 0.20, fz + 0.01, W2 - 0.48, nose_y - 0.07, fz + 0.015, black)
        elif g == "black_bars":
            mb.box(-(W2 - 0.38), nose_y - 0.20, fz, W2 - 0.38, nose_y - 0.04, fz + 0.01, black)
            for k in range(3):
                mb.box(-(W2 - 0.39), nose_y - 0.17 + k * 0.045, fz + 0.01, W2 - 0.39, nose_y - 0.16 + k * 0.045,
                       fz + 0.015, (60, 60, 62))
        elif g == "egg_crate":
            mb.box(-(W2 - 0.42), nose_y - 0.22, fz, W2 - 0.42, nose_y - 0.04, fz + 0.01, (40, 40, 42))
            for k in range(-4, 5):
                mb.box(k * 0.1 - 0.008, nose_y - 0.22, fz + 0.01, k * 0.1 + 0.008, nose_y - 0.04, fz + 0.016, chrome)
        elif g == "kidney":        # BMW: две «ноздри»
            for kx in (-0.11, 0.11):
                mb.box(kx - 0.085, nose_y - 0.24, fz, kx + 0.085, nose_y - 0.02, fz + 0.02, chrome)
                mb.box(kx - 0.065, nose_y - 0.22, fz + 0.02, kx + 0.065, nose_y - 0.04, fz + 0.025, black)
            mb.box(-(W2 - 0.2), nose_y - 0.2, fz, -0.22, nose_y - 0.06, fz + 0.008, black)
            mb.box(0.22, nose_y - 0.2, fz, W2 - 0.2, nose_y - 0.06, fz + 0.008, black)
        elif g == "tall_chrome":
            mb.box(-0.24, nose_y - 0.28, fz, 0.24, nose_y + 0.08, fz + 0.03, chrome)
            for k in range(-4, 5):
                mb.box(k * 0.045 - 0.006, nose_y - 0.25, fz + 0.03, k * 0.045 + 0.006, nose_y + 0.05, fz + 0.035, black)
        for x in (-(W2 - 0.12), W2 - 0.12):
            mb.box(x - 0.07, sill + 0.21, Z(L) - 0.01, x + 0.07, sill + 0.26, fz + 0.01, (230, 140, 30))
        # бамперы
        bh = 0.07 if B["bumper"] == "chrome_thin" else 0.12
        bcol = black if B["bumper"] == "black" else chrome
        for z0, z1 in ((Z(L), Z(L) + 0.1), (Z(0) - 0.1, Z(0))):
            mb.box(-(W2 + 0.02), sill + 0.07, z0, W2 + 0.02, sill + 0.07 + bh, z1, bcol)
            if B["bumper"] == "chrome_rubber":
                mb.box(-(W2 + 0.03), sill + 0.10, z0 - 0.005, W2 + 0.03, sill + 0.14, z1 + 0.005, black)
        # корма, крышка багажника / дверь хэтчбека (на петлях — car3d_extra)
        tb = MeshBuilder()
        if style != "hatch":
            mb.box(-(W2 - 0.01), sill + 0.03, Z(0), W2 - 0.01, rb_y, Z(0.08), paint, top=top_c)
            tb.box(-(W2 - 0.02), rb_y - 0.04, Z(0.05), W2 - 0.02, rb_y, Z(rgb), paint, top=top_c)
            self._tail_hinge = (0, rb_y, Z(rgb))
        else:
            mb.box(-(W2 - 0.01), sill + 0.03, Z(0), W2 - 0.01, sill + 0.22, Z(0.08), paint, top=top_c)
            tb.box(-(W2 - 0.01), sill + 0.22, Z(0), W2 - 0.01, rb_y, Z(0.08), paint, top=top_c)
            self._tail_hinge = (0, roof_y, Z(rs))
        self.trunk_lid = Entity(parent=b, model=tb.build(keep=True), double_sided=True)
        mb.box(-0.26, sill + 0.24, Z(0) - 0.012, 0.26, sill + 0.37, Z(0), (20, 20, 20))      # место под номер
        # крыша и стойки
        mb.box(-(W2 - 0.08), roof_y - 0.05, Z(rs), W2 - 0.08, roof_y, Z(re), paint, top=top_c)
        for x in (-(W2 - 0.05), W2 - 0.05):
            d = 0.035
            for (y0, z0), (y1, z1) in (((belt, Z(wb)), (roof_y, Z(re))), ((rb_y, Z(rgb)), (roof_y, Z(rs)))):
                mb.poly([(x - d, y0, z0), (x + d, y0, z0), (x + d, y1, z1), (x - d, y1, z1)], paint, (0, 0.5, 0.5))
                mb.poly([(x - d, y0, z0 - 0.05), (x + d, y0, z0 - 0.05), (x + d, y1, z1 - 0.05), (x - d, y1, z1 - 0.05)],
                        paint, (0, -0.5, -0.5))
            mb.box(x - 0.03, belt, Z(B["b_pillar"] - 0.03), x + 0.03, roof_y - 0.03, Z(B["b_pillar"] + 0.03), (40, 40, 40))
        mb.box(0.30, sill - 0.10, Z(0) - 0.12, 0.36, sill - 0.05, Z(0.5), (90, 80, 70))                  # выхлоп
        # салон
        mb.box(-(W2 - 0.1), belt - 0.16, Z(wb - 0.35), W2 - 0.1, belt + 0.06, Z(wb), (32, 30, 30), top=(26, 24, 24))
        mb.box(-(W2 - 0.3), belt + 0.02, Z(wb - 0.35), -0.14, belt + 0.14, Z(wb - 0.26), (22, 22, 22))   # щиток
        seat_z0, seat_z1 = B["b_pillar"] - 0.45, B["b_pillar"] + 0.1
        sb = MeshBuilder()
        if B["seats"] == "bench_front":
            sb.box(-(W2 - 0.12), sill + 0.10, Z(seat_z0), W2 - 0.12, sill + 0.24, Z(seat_z1), seat_c)
            sb.box(-(W2 - 0.12), sill + 0.24, Z(seat_z0 - 0.08), W2 - 0.12, sill + 0.80, Z(seat_z0 + 0.02), seat_c)
        else:
            for x0 in (-(W2 - 0.12), 0.1):
                sb.box(x0, sill + 0.10, Z(seat_z0), x0 + W2 - 0.24, sill + 0.24, Z(seat_z1), seat_c)
                sb.box(x0, sill + 0.24, Z(seat_z0 - 0.08), x0 + W2 - 0.24, sill + 0.82, Z(seat_z0 + 0.02), seat_c)
                sb.box(x0 + 0.1, sill + 0.82, Z(seat_z0 - 0.07), x0 + W2 - 0.34, sill + 0.96, Z(seat_z0), seat_c)
        rz = max(rgb + 0.35, 0.6)
        self._geo = dict(W2=W2, L=L, sill=sill, belt=belt, roof=roof_y, ws=wb, rs=rs, re=re, rgb=rgb, rb_y=rb_y,
                         nose=nose_y, seat_z=(seat_z0 + seat_z1) / 2, rear_z=rz, seat_y=sill + 0.24, style=style,
                         floor=sill + 0.07, trunk_z0=0.12, trunk_z1=max(0.5, rz - 0.1), seat_c=seat_c)
        sb.box(-(W2 - 0.12), sill + 0.10, Z(rz), W2 - 0.12, sill + 0.24, Z(seat_z0 - 0.35), seat_c)
        sb.box(-(W2 - 0.12), sill + 0.24, Z(rz - 0.08), W2 - 0.12, sill + 0.72, Z(rz + 0.02), seat_c)
        self.seats_e = Entity(parent=b, model=sb.build(keep=True), double_sided=True)
        tc = tuple(int(c * 0.8) for c in seat_c)
        self._make_trims(b, [(-(W2 - 0.09), sill + 0.06, Z(0.4), -(W2 - 0.13), belt, Z(wb - 0.05)),
                             (W2 - 0.13, sill + 0.06, Z(0.4), W2 - 0.09, belt, Z(wb - 0.05))], tc)
        self._interior = dict(floor_y=sill + 0.07, hw=W2 - 0.14, z0=Z(0.45), z1=Z(wb - 0.1), dash_y=belt + 0.06,
                              dash_z=Z(wb - 0.35))
        self._snow = dict(roof=(W2 - 0.08, roof_y, Z(rs), Z(re)),
                          trunk=(W2 - 0.04, rb_y, Z(0.06), Z(rgb)) if style != "hatch" else None)
        mb.box(-(W2 - 0.1), roof_y - 0.06, Z(rs + 0.05), W2 - 0.1, roof_y - 0.055, Z(re - 0.05), (165, 160, 150))
        if B.get("dash_shift"):     # Trabant: рычаг КПП торчит из торпедо
            mb.box(0.05, belt - 0.04, Z(wb - 0.55), 0.08, belt - 0.01, Z(wb - 0.3), (30, 30, 30))
            mb.box(0.04, belt - 0.05, Z(wb - 0.58), 0.09, belt, Z(wb - 0.53), (20, 20, 20))
        else:
            mb.box(-0.02, sill + 0.06, Z(wb - 0.75), 0.02, sill + 0.42, Z(wb - 0.71), (30, 30, 30))
            mb.box(-0.035, sill + 0.40, Z(wb - 0.77), 0.035, sill + 0.47, Z(wb - 0.69), (20, 20, 20))
        self.shell = Entity(parent=b, model=mb.build(keep=True), double_sided=True)

        # руль
        self.wheel_pivot = Entity(parent=b, position=(sp["eye"][0], belt + 0.06, Z(wb - 0.42)), rotation_x=28)
        big = car.model in ("w123", "trabant", "wartburg")
        ring_entity(self.wheel_pivot, 0.2 if big else 0.18, 0.025, color.rgb(20, 20, 20))
        self.steer_spokes = Entity(parent=self.wheel_pivot)
        spokes = (0, 180) if B["wheel"] == "two_spoke" else (30, 150, 210, 330)
        for a in spokes:
            Entity(parent=self.steer_spokes, model="cube", color=color.rgb(25, 25, 25), rotation_z=a,
                   position=(math.cos(math.radians(a)) * 0.09, math.sin(math.radians(a)) * 0.09, 0),
                   scale=(0.18, 0.025, 0.02))
        Entity(parent=self.steer_spokes, model="cube", color=color.rgb(40, 40, 40), scale=(0.08, 0.08, 0.03))

        # капот: от лобового к носу, с естественным наклоном
        run = (L - 0.08) - wb
        self.hood_rest = math.degrees(math.atan2(belt - (nose_y + 0.02), run))
        self.hood = Entity(parent=b, position=(0, belt, Z(wb)))
        hm = MeshBuilder()
        hm.box(-(W2 - 0.02), -0.045, 0.0, W2 - 0.02, 0.0, math.hypot(run, belt - nose_y), paint, top=top_c)
        self._hood_len = math.hypot(run, belt - nose_y)
        self.hood_mesh = Entity(parent=self.hood, model=hm.build(keep=True), double_sided=True)

        # фары
        self.headlamps = []
        lt = B["lights"]
        for sgn in (-1, 1):
            if lt == "round4":
                for x in (sgn * (W2 - 0.2), sgn * (W2 - 0.42)):
                    Entity(parent=b, model="cube", color=color.rgb(*chrome), position=(x, nose_y - 0.12, Z(L) + 0.02),
                           scale=(0.18, 0.18, 0.01))
                    self.headlamps.append(Entity(parent=b, model="sphere", color=color.rgb(200, 200, 185),
                                                 position=(x, nose_y - 0.12, Z(L) + 0.028), scale=(0.14, 0.14, 0.04)))
            elif lt == "round2":
                x = sgn * (W2 - 0.25)
                Entity(parent=b, model="cube", color=color.rgb(*chrome), position=(x, nose_y - 0.12, Z(L) + 0.006),
                       scale=(0.22, 0.22, 0.01))
                self.headlamps.append(Entity(parent=b, model="sphere", color=color.rgb(200, 200, 185),
                                             position=(x, nose_y - 0.12, Z(L) + 0.012), scale=(0.18, 0.18, 0.04)))
            elif lt == "rect2":
                x = sgn * (W2 - 0.26)
                self.headlamps.append(Entity(parent=b, model="cube", color=color.rgb(200, 200, 185),
                                             position=(x, nose_y - 0.12, Z(L) + 0.008), scale=(0.30, 0.13, 0.02)))
            else:   # rect_tall — W123: высокие фары с поворотниками сбоку
                x = sgn * (W2 - 0.3)
                self.headlamps.append(Entity(parent=b, model="cube", color=color.rgb(200, 200, 185),
                                             position=(x, nose_y - 0.12, Z(L) + 0.008), scale=(0.26, 0.2, 0.02)))
                Entity(parent=b, model="cube", color=color.rgb(230, 140, 30),
                       position=(sgn * (W2 - 0.1), nose_y - 0.12, Z(L) + 0.008), scale=(0.1, 0.2, 0.02))
        # фонари
        self.taillights = []
        tail = B["tail"]
        for sgn in (-1, 1):
            if tail == "small_vertical":
                pos, sc = (sgn * (W2 - 0.12), rb_y - 0.16, Z(0) - 0.006), (0.1, 0.18, 0.02)
            elif tail == "vertical_rect":
                pos, sc = (sgn * (W2 - 0.14), rb_y - 0.17, Z(0) - 0.006), (0.18, 0.24, 0.02)
            elif tail == "rect_small":
                pos, sc = (sgn * (W2 - 0.2), rb_y - 0.12, Z(0) - 0.006), (0.3, 0.12, 0.02)
            elif tail == "ribbed_wide":
                pos, sc = (sgn * (W2 - 0.28), rb_y - 0.14, Z(0) - 0.006), (0.46, 0.2, 0.02)
            else:
                pos, sc = (sgn * (W2 - 0.25), rb_y - 0.12, Z(0) - 0.006), (0.42, 0.14, 0.02)
            tl = Entity(parent=b, model="cube", color=color.rgb(120, 20, 20), position=pos, scale=sc)
            self.taillights.append(tl)
            if tail == "ribbed_wide":
                for k in range(4):
                    Entity(parent=tl, model="cube", color=color.rgb(30, 30, 30), position=(0, -0.4 + k * 0.27, -0.6),
                           scale=(1, 0.05, 0.5))
        # номера (появятся после регистрации)
        self.plates = []
        for z, y, rot in ((Z(L) + 0.11, sill + 0.14, 180), (Z(0) - 0.015, sill + 0.305, 0)):
            pl = Entity(parent=b, model="cube", color=color.rgb(240, 240, 240), position=(0, y, z), scale=(0.52, 0.11, 0.01))
            t = Text(car.plate, parent=pl, scale=(1 / 0.52 * 0.9, 1 / 0.11 * 0.9), origin=(0, 0), color=color.black,
                     position=(0, 0, -0.6 if rot == 0 else 0.6), rotation_y=rot)
            self.plate_texts.append(t)
            self.plates.append(pl)
        # стёкла
        glass_entity(b, [(-(W2 - 0.06), belt + 0.01, Z(wb)), (W2 - 0.06, belt + 0.01, Z(wb)),
                         (W2 - 0.1, roof_y - 0.01, Z(re)), (-(W2 - 0.1), roof_y - 0.01, Z(re))],
                     (95, 105, 105) if car.c("glass") < 0.3 else GLASS, 0.55 if car.c("glass") < 0.3 else 0.35)
        self.rear_glass = glass_entity(b, [(-(W2 - 0.08), rb_y + 0.01, Z(rgb)), (W2 - 0.08, rb_y + 0.01, Z(rgb)),
                         (W2 - 0.1, roof_y - 0.01, Z(rs)), (-(W2 - 0.1), roof_y - 0.01, Z(rs))])

        # моторный отсек
        self.bay = Entity(parent=b)
        ez = Z((wb + L) / 2)
        diesel, two = sp.get("diesel"), sp.get("two_stroke")
        eng_len = 0.62 if diesel else (0.32 if two else 0.46)
        self._build_engine(0, sill + 0.30, ez, 0.40 if not two else 0.46, 0.40, eng_len,
                           (20, 20, 20) if not diesel else (150, 150, 155))
        cool_part = "belt"
        self.bay_parts = {
            "air_filter": Entity(parent=self.bay, model="cube", color=color.rgb(40, 40, 42),
                                 position=(0.18, sill + 0.62, ez), scale=(0.26, 0.08, 0.26)),
            "carb": Entity(parent=self.bay, model="cube", color=color.rgb(160, 150, 120),
                           position=(0.2, sill + 0.48, ez), scale=(0.1, 0.1, 0.1)),
            "battery": Entity(parent=self.bay, model="cube", color=color.rgb(25, 25, 25),
                              position=(W2 - 0.3, sill + 0.35, Z(wb + 0.2)), scale=(0.22, 0.2, 0.28)),
            "alternator": Entity(parent=self.bay, model="cube", color=color.rgb(170, 170, 170),
                                 position=(-0.3, sill + 0.25, ez + 0.15), scale=(0.14, 0.14, 0.16)),
            "distributor": Entity(parent=self.bay, model="cube", color=color.rgb(30, 30, 30) if not diesel else color.rgb(90, 90, 95),
                                  position=(-0.2, sill + 0.5, ez - 0.1), scale=(0.08, 0.12, 0.08) if not diesel else (0.12, 0.18, 0.25)),
            cool_part: Entity(parent=self.bay, model="cube", color=color.rgb(15, 15, 15),
                              position=(-0.2, sill + 0.22, Z(L - 0.25)), scale=(0.25, 0.03, 0.02)),
        }
        if sp.get("air_cooled"):   # Trabant: кожух вентилятора вместо радиатора
            Entity(parent=self.bay, model="cube", color=color.rgb(70, 70, 72), position=(-0.1, sill + 0.4, Z(L - 0.3)),
                   scale=(0.35, 0.3, 0.12))
        else:
            self.bay_parts["radiator"] = Entity(parent=self.bay, model="cube", color=color.rgb(150, 90, 50),
                                                position=(0, sill + 0.3, Z(L - 0.14)), scale=(W2 * 1.1, 0.34, 0.04))
        Entity(parent=self.bay_parts["battery"], model="cube", color=color.red, position=(0.3, 0.55, 0.3), scale=(0.15, 0.1, 0.1))
        Entity(parent=self.bay_parts["battery"], model="cube", color=color.blue, position=(-0.3, 0.55, 0.3), scale=(0.15, 0.1, 0.1))
        # тюнинг (tuning.py): видно, только если установлено
        self.tune_parts = {}
        if car.tune:
            tb = Entity(parent=self.bay, position=(-0.12, sill + 0.42, ez + 0.05))
            Entity(parent=tb, model="sphere", color=color.rgb(150, 150, 155), scale=(0.2, 0.2, 0.14))      # «улитка»
            Entity(parent=tb, model="sphere", color=color.rgb(120, 70, 40), position=(0.06, -0.06, 0), scale=(0.14, 0.14, 0.12))
            Entity(parent=tb, model="cube", color=color.rgb(170, 170, 175), position=(0.0, 0.08, 0.2), scale=(0.07, 0.07, 0.36))
            Entity(parent=tb, model="cube", color=color.rgb(30, 30, 32), position=(-0.12, 0.02, -0.12), scale=(0.08, 0.08, 0.2))
            self.tune_parts["turbo"] = tb
            ic = Entity(parent=b, position=(0, sill - 0.02, Z(L) + 0.07))      # под бампером, как настоящий FMIC
            Entity(parent=ic, model="cube", color=color.rgb(175, 178, 182), scale=(W2 * 1.3, 0.13, 0.05))
            for k in range(4):
                Entity(parent=ic, model="cube", color=color.rgb(60, 62, 66), position=(0, -0.045 + k * 0.03, 0.028),
                       scale=(W2 * 1.25, 0.008, 0.01))
            self.tune_parts["intercooler"] = ic
            self.tune_parts["boost_ctrl"] = Entity(parent=self.bay, model="cube", color=color.rgb(200, 30, 30),
                                                   position=(0.25, sill + 0.56, ez - 0.2), scale=(0.05, 0.05, 0.05))

    def _build_engine(self, cx, cy, cz, w, h, l, cover, stripe=None):
        """Двигатель по деталям (engine.py): каждая видна на своём месте и пропадает, когда её сняли;
        под снятой крышкой/ГБЦ/поддоном видно то, что она закрывала."""
        import engine as _e
        L = _e.layout(self.car.model)
        cyl = L["cyl"]
        yb = cy + h * 0.25                       # верх блока
        front = cz + l / 2
        ev = {}

        def box(key, pos, sc, col):
            ent = Entity(parent=self.bay, model="cube", color=color.rgb(*col), position=pos, scale=sc)
            if key:
                ev.setdefault(key, []).append(ent)
            return ent
        box("block", (cx, cy - h * 0.125, cz), (w, h * 0.75, l), (95, 97, 100))
        box("head_gasket", (cx, yb + 0.006, cz), (w * 0.95, 0.012, l * 0.97), (70, 70, 72))
        box("head", (cx, yb + 0.065, cz), (w * 0.9, 0.11, l * 0.95), (165, 165, 160) if L["stroke"] == 4 else (120, 120, 118))
        if L["stroke"] == 2:                      # рёбра охлаждения двухтакта
            for k in range(4):
                box("head", (cx, yb + 0.03 + k * 0.025, cz), (w * 1.05, 0.008, l * 0.98), (110, 110, 108))
        box("valve_cover", (cx, yb + 0.155, cz), (w * 0.78, 0.07, l * 0.9), cover)
        if stripe:
            box("valve_cover", (cx, yb + 0.192, cz), (w * 0.35, 0.006, l * 0.55), stripe)
        cams = (-w * 0.15, w * 0.15) if L["vt"] == "dohc" else (0.0,)
        for x_ in cams:
            box("camshaft", (cx + x_, yb + 0.13, cz), (0.035, 0.035, l * 0.9), (190, 190, 185))
        for i in range(cyl):
            z_ = cz - l * 0.4 + (i + 0.5) * l * 0.8 / cyl
            box("pistons", (cx, yb - 0.004, z_), (w * 0.5, 0.012, l * 0.8 / cyl * 0.75), (200, 200, 205))
            for x_ in (-0.06, 0.06):
                box("valves", (cx + x_, yb + 0.12, z_), (0.025, 0.02, 0.025), (150, 150, 150))
                box("springs", (cx + x_, yb + 0.135, z_), (0.03, 0.03, 0.03), (70, 140, 80))
            box("conrods", (cx, cy - h * 0.33, z_), (0.035, 0.13, 0.035), (140, 140, 145))
            box("rod_bearings", (cx, cy - h * 0.43, z_), (0.07, 0.02, 0.05), (190, 120, 60))
        box("crankshaft", (cx, cy - h * 0.45, cz), (0.06, 0.06, l * 0.95), (120, 120, 125))
        for i in range(cyl + 1):
            box("main_bearings", (cx, cy - h * 0.49, cz - l * 0.45 + i * l * 0.9 / cyl), (0.08, 0.015, 0.03), (190, 120, 60))
        box("oil_pump", (cx + w * 0.15, cy - h * 0.47, front - 0.1), (0.1, 0.07, 0.1), (100, 100, 105))
        box("oil_pan", (cx, cy - h * 0.5 - 0.045, cz), (w * 0.82, 0.09, l * 0.88), (60, 62, 66))
        box("intake", (cx + w * 0.58, yb + 0.03, cz), (w * 0.3, 0.1, l * 0.85), (175, 175, 170))
        box("fuel_rail", (cx + w * 0.62, yb + 0.1, cz), (0.04, 0.04, l * 0.8), (200, 180, 60))
        box("exhaust_mf", (cx - w * 0.58, yb - 0.02, cz), (w * 0.22, 0.1, l * 0.85), (125, 72, 45))
        box("timing_cover", (cx, cy + 0.02, front + 0.02), (w * 0.72, h * 0.85, 0.03), (150, 150, 148))
        box("timing", (cx, cy + 0.03, front + 0.006), (w * 0.3, h * 0.8, 0.012), (25, 25, 25))
        box("tensioner", (cx + w * 0.16, cy + 0.06, front + 0.014), (0.05, 0.05, 0.02), (180, 180, 180))
        box("crank_pulley", (cx, cy - h * 0.3, front + 0.05), (0.16, 0.16, 0.03), (40, 40, 42))
        box("water_pump", (cx - w * 0.22, cy + 0.02, front + 0.055), (0.1, 0.1, 0.06), (120, 120, 118))
        box("thermostat", (cx + w * 0.2, yb + 0.08, front - 0.02), (0.06, 0.06, 0.06), (90, 90, 90))
        box("oil_filter", (cx + w * 0.56, cy - h * 0.2, cz - l * 0.15), (0.08, 0.12, 0.08), (210, 100, 30))
        self.eng_vis = ev
        self._engine_box = (cx, cy, cz, w, h, l)

    def _update_engine_vis(self):
        import engine as _e
        car = self.car
        ev = getattr(self, "eng_vis", None)
        if not ev:
            return
        whole = car.has("engine")
        key = (whole, tuple(sorted(k for k, v in (car.eng or {}).items() if v)))
        if key == getattr(self, "_eng_vis_key", None):
            return
        self._eng_vis_key = key
        for k, ents in ev.items():
            if k == "block":
                on = whole
            elif not car.eng or k not in car.eng:
                on = False                        # у этого двигателя такой детали нет (двухтакт, без впрыска...)
            else:
                on = whole and _e.has(car, k) and not any(_e.has(car, c) for c in _e.COVERED.get(k, ()))
            for ent in ents:
                ent.enabled = on

    def _build_vaz(self, b):
        Z = self.Z
        P_ = self.car.paint if self.car.color else PAINT
        PD_ = tuple(int(c * 0.91) for c in P_)
        mb = MeshBuilder()
        # колёсные ниши (видны сквозь вырезы арок) и дно моторного отсека
        for sx in (0.83, 3.25):
            for side in (-1, 1):
                mb.box(side * 0.30, 0.26, Z(sx - 0.42), side * 0.58, 0.74, Z(sx + 0.42), (24, 22, 20))
        mb.box(-0.70, 0.26, Z(2.98), 0.70, 0.40, Z(3.95), (30, 28, 26))
        mb.box(-0.70, 0.30, Z(0.08), 0.70, 0.60, Z(0.45), (40, 36, 34))   # пол багажника
        # днище/пол салона
        mb.box(-0.72, 0.30, Z(0.3), 0.72, 0.36, Z(2.95), (40, 36, 34))
        # передняя панель
        mb.box(-0.80, 0.33, Z(3.94), 0.80, 0.82, Z(4.01), P_)
        mb.box(-0.52, 0.52, Z(4.01), 0.52, 0.76, Z(4.03), (22, 22, 22))              # решётка
        for x in (-0.53, 0.53):
            mb.box(x - 0.012, 0.51, Z(4.0), x + 0.012, 0.77, Z(4.04), CHROME)
        mb.box(-0.53, 0.755, Z(4.0), 0.53, 0.775, Z(4.04), CHROME)
        # задняя панель (универсал) и дверь багажника
        mb.box(-0.80, 0.33, Z(0.0), 0.80, 0.50, Z(0.07), P_)
        tb = MeshBuilder()
        tb.box(-0.80, 0.50, Z(0.0), 0.80, 0.86, Z(0.07), P_)
        tb.box(-0.78, 0.86, Z(0.06), 0.78, 0.94, Z(0.12), P_)
        self.trunk_lid = Entity(parent=b, model=tb.build(keep=True), double_sided=True)
        self._tail_hinge = (0, 1.40, Z(0.11))
        self._geo = dict(W2=0.805, L=4.03, sill=0.30, belt=0.86, roof=1.40, ws=2.98, rs=0.1, re=2.36, rgb=0.1, rb_y=0.86,
                         nose=0.78, seat_z=1.72, rear_z=0.85, seat_y=0.52, style="wagon", floor=0.37,
                         trunk_z0=0.12, trunk_z1=0.62, trunk_y=0.60, seat_c=(108, 62, 42))
        # багажник на крыше и крыша
        mb.box(-0.80, 1.38, Z(0.10), 0.80, 1.45, Z(2.36), PD_, top=(205, 197, 162))
        for x in (-0.62, 0.62):
            mb.box(x - 0.025, 1.52, Z(0.3), x + 0.025, 1.56, Z(2.2), (60, 55, 50))
        for sx in (0.4, 1.2, 2.1):
            mb.box(-0.64, 1.45, Z(sx) - 0.02, -0.60, 1.53, Z(sx) + 0.02, (60, 55, 50))
            mb.box(0.60, 1.45, Z(sx) - 0.02, 0.64, 1.53, Z(sx) + 0.02, (60, 55, 50))
            mb.box(-0.64, 1.52, Z(sx) - 0.02, 0.64, 1.555, Z(sx) + 0.02, (60, 55, 50))
        # стойки (видны и изнутри)
        mb.box(-0.80, 0.86, Z(1.84), -0.74, 1.40, Z(1.90), P_)      # B-стойка
        mb.box(0.74, 0.86, Z(1.84), 0.80, 1.40, Z(1.90), P_)
        mb.box(-0.80, 0.86, Z(0.96), -0.74, 1.40, Z(1.02), P_)      # C-стойка
        mb.box(0.74, 0.86, Z(0.96), 0.80, 1.40, Z(1.02), P_)
        mb.box(-0.80, 0.86, Z(0.06), -0.70, 1.40, Z(0.2), P_)       # D-стойка
        mb.box(0.70, 0.86, Z(0.06), 0.80, 1.40, Z(0.2), P_)
        for x in (-0.77, 0.77):   # A-стойки
            p0 = (x, 0.87, Z(2.98))
            p1 = (x, 1.40, Z(2.52))
            d = 0.035
            mb.poly([(x - d, p0[1], p0[2]), (x + d, p0[1], p0[2]), (x + d, p1[1], p1[2]), (x - d, p1[1], p1[2])], P_, (0, 0.5, 0.5))
            mb.poly([(x - d, p0[1], p0[2] - 0.06), (x + d, p0[1], p0[2] - 0.06), (x + d, p1[1], p1[2] - 0.06),
                     (x - d, p1[1], p1[2] - 0.06)], P_, (0, -0.5, -0.5))
        # бамперы
        mb.box(-0.84, 0.36, Z(4.0), 0.84, 0.47, Z(4.11), CHROME)
        mb.box(-0.84, 0.38, Z(-0.09), 0.84, 0.49, Z(0.0), CHROME)
        for x in (-0.55, 0.55):
            mb.box(x - 0.08, 0.30, Z(4.02), x + 0.08, 0.35, Z(4.06), (230, 140, 30))   # поворотники
        # выхлопная труба
        mb.box(0.35, 0.18, Z(-0.12), 0.41, 0.24, Z(0.5), (90, 80, 70))
        # салон: приборная панель, сиденья, обивка дверей
        mb.box(-0.72, 0.70, Z(2.62), 0.72, 0.93, Z(2.98), DASH, top=(30, 28, 27))
        mb.box(-0.56, 0.88, Z(2.62), -0.16, 1.02, Z(2.72), (26, 24, 23))                # щиток приборов
        sb = MeshBuilder()
        for x0 in (-0.62, 0.12):
            sb.box(x0, 0.40, Z(1.55), x0 + 0.50, 0.54, Z(2.1), VINYL)
            sb.box(x0, 0.54, Z(1.47), x0 + 0.50, 1.12, Z(1.57), VINYL)
            sb.box(x0 + 0.1, 1.12, Z(1.49), x0 + 0.40, 1.28, Z(1.56), VINYL)             # подголовник
        sb.box(-0.64, 0.40, Z(0.62), 0.64, 0.54, Z(1.15), VINYL)
        sb.box(-0.64, 0.54, Z(0.55), 0.64, 1.05, Z(0.66), VINYL)
        self.seats_e = Entity(parent=b, model=sb.build(keep=True), double_sided=True)
        self._make_trims(b, [(-0.73, 0.36, Z(0.4), -0.69, 0.86, Z(2.9)), (0.69, 0.36, Z(0.4), 0.73, 0.86, Z(2.9))],
                         (95, 66, 52))
        self._interior = dict(floor_y=0.37, hw=0.68, z0=Z(0.45), z1=Z(2.85), dash_y=0.93, dash_z=Z(2.66))
        self._snow = dict(roof=(0.78, 1.45, Z(0.12), Z(2.34)), trunk=None)
        mb.box(-0.72, 1.37, Z(0.2), 0.72, 1.38, Z(2.45), (170, 160, 140))               # потолок
        mb.box(-0.02, 0.36, Z(2.2), 0.02, 0.72, Z(2.24), (30, 30, 30))                  # рычаг КПП
        mb.box(-0.035, 0.70, Z(2.18), 0.035, 0.77, Z(2.25), (20, 20, 20))
        self.shell = Entity(parent=b, model=mb.build(keep=True), double_sided=True)

        # руль
        self.wheel_pivot = Entity(parent=b, position=(-0.36, 0.98, Z(2.55)), rotation_x=28)
        ring_entity(self.wheel_pivot, 0.19, 0.03, color.rgb(20, 20, 20))
        self.steer_spokes = Entity(parent=self.wheel_pivot)
        for a in (0, 180, 270):
            Entity(parent=self.steer_spokes, model="cube", color=color.rgb(25, 25, 25),
                   rotation_z=a, position=(math.cos(math.radians(a)) * 0.09, math.sin(math.radians(a)) * 0.09, 0),
                   scale=(0.18, 0.025, 0.02))
        Entity(parent=self.steer_spokes, model="cube", color=color.rgb(40, 40, 40), scale=(0.07, 0.07, 0.03))

        # капот (открывается в гараже)
        self.hood = Entity(parent=b, position=(0, 0.86, Z(2.99)))
        hm = MeshBuilder()
        hm.box(-0.80, -0.05, 0.0, 0.80, 0.0, Z(3.95) - Z(2.99), P_, top=(190, 180, 146))
        self._hood_len = Z(3.95) - Z(2.99)
        hm.box(-0.30, 0.0, 0.25, 0.05, 0.004, 0.55, (128, 128, 122))     # пятно грунта
        self.hood_mesh = Entity(parent=self.hood, model=hm.build(keep=True), double_sided=True)

        # моторный отсек
        self.bay = Entity(parent=b)
        self._build_engine(-0.05, 0.55, Z(3.35), 0.42, 0.42, 0.55, (20, 20, 20))
        self.bay_parts = {
            "air_filter": Entity(parent=self.bay, model="cube", color=color.rgb(40, 40, 42), position=(0.05, 0.86, Z(3.3)), scale=(0.34, 0.07, 0.34)),
            "carb": Entity(parent=self.bay, model="cube", color=color.rgb(160, 150, 120), position=(0.12, 0.72, Z(3.3)), scale=(0.12, 0.1, 0.12)),
            "battery": Entity(parent=self.bay, model="cube", color=color.rgb(25, 25, 25), position=(0.52, 0.62, Z(3.62)), scale=(0.22, 0.2, 0.28)),
            "radiator": Entity(parent=self.bay, model="cube", color=color.rgb(150, 90, 50), position=(0, 0.58, Z(3.88)), scale=(0.9, 0.38, 0.04)),
            "alternator": Entity(parent=self.bay, model="cube", color=color.rgb(170, 170, 170), position=(-0.36, 0.5, Z(3.6)), scale=(0.14, 0.14, 0.16)),
            "distributor": Entity(parent=self.bay, model="cube", color=color.rgb(30, 30, 30), position=(-0.2, 0.8, Z(3.1)), scale=(0.07, 0.12, 0.07)),
            "belt": Entity(parent=self.bay, model="cube", color=color.rgb(15, 15, 15), position=(-0.2, 0.46, Z(3.66)), scale=(0.25, 0.03, 0.02)),
        }
        Entity(parent=self.bay_parts["battery"], model="cube", color=color.red, position=(0.3, 0.55, 0.3), scale=(0.15, 0.1, 0.1))
        Entity(parent=self.bay_parts["battery"], model="cube", color=color.blue, position=(-0.3, 0.55, 0.3), scale=(0.15, 0.1, 0.1))

        # стёкла
        glass_entity(b, [(-0.74, 0.88, Z(2.98)), (0.74, 0.88, Z(2.98)), (0.72, 1.39, Z(2.52)), (-0.72, 1.39, Z(2.52))])
        self.rear_glass = glass_entity(b, [(-0.70, 0.94, Z(0.07)), (0.70, 0.94, Z(0.07)), (0.70, 1.37, Z(0.1)), (-0.70, 1.37, Z(0.1))])

        # фары, фонари (отдельно — меняют яркость)
        self.headlamps = []
        for x in (-0.62, 0.62):
            Entity(parent=b, model="cube", color=color.rgb(*CHROME), position=(x, 0.64, Z(4.015)), scale=(0.24, 0.24, 0.02))
            lamp = Entity(parent=b, model="sphere", color=color.rgb(200, 200, 185), position=(x, 0.64, Z(4.02)),
                          scale=(0.19, 0.19, 0.05))
            self.headlamps.append(lamp)
        self.taillights = []
        for x in (-0.66, 0.66):
            tl = Entity(parent=b, model="cube", color=color.rgb(120, 20, 20), position=(x, 0.66, Z(-0.005)), scale=(0.18, 0.22, 0.02))
            self.taillights.append(tl)
        # номера
        self.plates = []
        for z, rot in ((Z(4.12), 180), (Z(-0.1), 0)):
            pl = Entity(parent=b, model="cube", color=color.rgb(240, 240, 240), position=(0, 0.52 if z > 0 else 0.62, z), scale=(0.52, 0.11, 0.01))
            Text(self.car.plate, parent=pl, scale=(1 / 0.52 * 0.9, 1 / 0.11 * 0.9), origin=(0, 0), color=color.black,
                 position=(0, 0, -0.6 if rot == 0 else 0.6), rotation_y=rot)
            self.plates.append(pl)


    def _build_ae86(self, b):
        """Toyota Sprinter Trueno AE86 (1985), «панда»: белый верх, чёрный низ."""
        Z = self.Z
        W_, K_ = (238, 238, 232), (32, 32, 34)
        GLS = (40, 50, 60)
        mb = MeshBuilder()
        for sx in self.car.spec["axles"]:
            for side in (-1, 1):
                mb.box(side * 0.30, 0.26, Z(sx - 0.42), side * 0.58, 0.74, Z(sx + 0.42), (24, 22, 20))
        mb.box(-0.70, 0.26, Z(3.10), 0.70, 0.40, Z(4.10), (30, 28, 26))
        mb.box(-0.72, 0.30, Z(0.3), 0.72, 0.36, Z(3.05), (38, 38, 40))
        mb.box(-0.70, 0.30, Z(0.10), 0.70, 0.62, Z(0.45), (40, 40, 42))          # пол багажника
        # нос: чёрный бампер + белая панель со щелью решётки
        mb.box(-0.82, 0.33, Z(4.00), 0.82, 0.52, Z(4.25), K_)
        mb.box(-0.80, 0.52, Z(4.05), 0.80, 0.71, Z(4.19), W_)
        mb.box(-0.55, 0.56, Z(4.19), 0.55, 0.62, Z(4.20), (15, 15, 15))
        for x in (-0.62, 0.62):
            mb.box(x - 0.1, 0.44, Z(4.24), x + 0.1, 0.49, Z(4.26), (230, 140, 30))   # поворотники в бампере
        # корма: чёрный бампер, белая панель, сплошная полоса фонарей
        mb.box(-0.82, 0.33, Z(-0.06), 0.82, 0.50, Z(0.12), K_)
        mb.box(-0.80, 0.50, Z(0.0), 0.80, 0.87, Z(0.08), W_)
        mb.box(-0.30, 0.62, Z(-0.01), 0.30, 0.80, Z(0.0), (20, 20, 20))            # место под номер
        # крыша, стойки
        mb.box(-0.74, 1.29, Z(1.45), 0.74, 1.35, Z(2.50), W_, top=(245, 245, 240))
        mb.box(-0.80, 0.87, Z(1.94), -0.74, 1.30, Z(2.0), K_)
        mb.box(0.74, 0.87, Z(1.94), 0.80, 1.30, Z(2.0), K_)
        for x in (-0.77, 0.77):
            d = 0.035
            p0, p1 = (0.87, Z(3.08)), (1.30, Z(2.55))
            mb.poly([(x - d, p0[0], p0[1]), (x + d, p0[0], p0[1]), (x + d, p1[0], p1[1]), (x - d, p1[0], p1[1])], K_, (0, 0.5, 0.5))
            mb.poly([(x - d, p0[0], p0[1] - 0.06), (x + d, p0[0], p0[1] - 0.06), (x + d, p1[0], p1[1] - 0.06),
                     (x - d, p1[0], p1[1] - 0.06)], K_, (0, -0.5, -0.5))
            # задние стойки вдоль стекла люка
            q0, q1 = (0.88, Z(0.45)), (1.30, Z(1.45))
            mb.poly([(x - d, q0[0], q0[1]), (x + d, q0[0], q0[1]), (x + d, q1[0], q1[1]), (x - d, q1[0], q1[1])], W_, (0, 0.5, -0.5))
        # выхлоп (зеркала — рабочие, в car3d_extra.py)
        mb.box(0.35, 0.18, Z(-0.12), 0.41, 0.24, Z(0.5), (90, 80, 70))
        # салон: торпедо, ковши, заднее сиденье
        mb.box(-0.72, 0.66, Z(2.75), 0.72, 0.88, Z(3.08), (28, 28, 30), top=(24, 24, 26))
        mb.box(-0.56, 0.84, Z(2.75), -0.16, 0.98, Z(2.85), (20, 20, 22))            # щиток приборов
        mb.box(-0.12, 0.70, Z(2.72), 0.12, 0.84, Z(2.78), (35, 35, 38))             # магнитола
        seat, trim = (60, 60, 66), (140, 30, 30)
        sb = MeshBuilder()
        for x0 in (-0.62, 0.12):
            sb.box(x0, 0.36, Z(1.72), x0 + 0.50, 0.50, Z(2.25), seat)
            sb.box(x0, 0.50, Z(1.64), x0 + 0.50, 1.10, Z(1.74), seat)
            sb.box(x0 - 0.02, 0.50, Z(1.66), x0 + 0.04, 0.95, Z(1.90), seat)         # боковая поддержка
            sb.box(x0 + 0.46, 0.50, Z(1.66), x0 + 0.52, 0.95, Z(1.90), seat)
            sb.box(x0 + 0.1, 1.10, Z(1.66), x0 + 0.40, 1.24, Z(1.72), seat)
            sb.box(x0 + 0.05, 0.505, Z(1.742), x0 + 0.45, 0.515, Z(2.2), trim)       # красная вставка
        sb.box(-0.64, 0.36, Z(0.80), 0.64, 0.50, Z(1.30), seat)
        sb.box(-0.64, 0.50, Z(0.72), 0.64, 0.95, Z(0.82), seat)
        self.seats_e = Entity(parent=b, model=sb.build(keep=True), double_sided=True)
        self._make_trims(b, [(-0.73, 0.36, Z(0.5), -0.69, 0.86, Z(3.0)), (0.69, 0.36, Z(0.5), 0.73, 0.86, Z(3.0))],
                         (45, 45, 48))
        self._interior = dict(floor_y=0.37, hw=0.68, z0=Z(0.55), z1=Z(2.95), dash_y=0.88, dash_z=Z(2.78))
        self._snow = dict(roof=(0.74, 1.35, Z(1.45), Z(2.5)), trunk=None)
        mb.box(-0.72, 1.28, Z(1.5), 0.72, 1.29, Z(2.52), (150, 150, 150))           # потолок
        mb.box(-0.02, 0.36, Z(2.35), 0.02, 0.70, Z(2.39), (25, 25, 25))             # рычаг КПП (5 ступ.)
        mb.box(-0.035, 0.68, Z(2.33), 0.035, 0.75, Z(2.40), (20, 20, 20))
        self.shell = Entity(parent=b, model=mb.build(keep=True), double_sided=True)

        # руль (трёхспицевый)
        self.wheel_pivot = Entity(parent=b, position=(-0.36, 0.88, Z(2.72)), rotation_x=24)
        ring_entity(self.wheel_pivot, 0.18, 0.03, color.rgb(18, 18, 18))
        self.steer_spokes = Entity(parent=self.wheel_pivot)
        for a in (0, 180, 270):
            Entity(parent=self.steer_spokes, model="cube", color=color.rgb(30, 30, 30), rotation_z=a,
                   position=(math.cos(math.radians(a)) * 0.085, math.sin(math.radians(a)) * 0.085, 0),
                   scale=(0.17, 0.03, 0.02))
        Entity(parent=self.steer_spokes, model="cube", color=color.rgb(170, 20, 20), scale=(0.06, 0.06, 0.03))

        # капот (с наклоном к носу)
        self.hood_rest = 9.0
        self.hood = Entity(parent=b, position=(0, 0.87, Z(3.08)))
        hm = MeshBuilder()
        hm.box(-0.80, -0.05, 0.0, 0.80, 0.0, Z(4.05) - Z(3.08) - 0.32, W_, top=(242, 242, 236))
        self._hood_len = Z(4.05) - Z(3.08) - 0.32
        self.hood_mesh = Entity(parent=self.hood, model=hm.build(keep=True), double_sided=True)

        # поднимающиеся фары: крышка на шарнире + фара под ней
        self.headlamps = []
        for x in (-0.60, 0.60):
            pivot = Entity(parent=self.hood, position=(x, 0.0, 0.66))
            Entity(parent=pivot, model="cube", color=color.rgb(*W_), position=(0, -0.02, 0.15), scale=(0.34, 0.035, 0.30))
            self.popups.append(pivot)
            lamp = Entity(parent=pivot, model="cube", color=color.rgb(200, 200, 190), position=(0, -0.13, 0.30),
                          scale=(0.28, 0.20, 0.03))
            self.headlamps.append(lamp)

        # моторный отсек: 4A-GE
        self.bay = Entity(parent=b)
        self._build_engine(0, 0.55, Z(3.55), 0.46, 0.40, 0.52, (200, 200, 205), stripe=(190, 30, 30))
        self.bay_parts = {
            "air_filter": Entity(parent=self.bay, model="cube", color=color.rgb(30, 30, 32), position=(-0.45, 0.70, Z(3.45)), scale=(0.25, 0.14, 0.35)),
            "carb": Entity(parent=self.bay, model="cube", color=color.rgb(150, 150, 150), position=(0.22, 0.70, Z(3.5)), scale=(0.1, 0.1, 0.4)),
            "battery": Entity(parent=self.bay, model="cube", color=color.rgb(25, 25, 25), position=(0.52, 0.60, Z(3.9)), scale=(0.22, 0.2, 0.26)),
            "radiator": Entity(parent=self.bay, model="cube", color=color.rgb(60, 60, 62), position=(0, 0.55, Z(4.02)), scale=(0.9, 0.32, 0.04)),
            "alternator": Entity(parent=self.bay, model="cube", color=color.rgb(170, 170, 170), position=(0.3, 0.45, Z(3.8)), scale=(0.14, 0.14, 0.16)),
            "distributor": Entity(parent=self.bay, model="cube", color=color.rgb(30, 30, 30), position=(-0.1, 0.72, Z(3.25)), scale=(0.08, 0.1, 0.08)),
            "belt": Entity(parent=self.bay, model="cube", color=color.rgb(20, 20, 20), position=(-0.26, 0.58, Z(3.84)), scale=(0.06, 0.36, 0.1)),
        }
        Entity(parent=self.bay_parts["battery"], model="cube", color=color.red, position=(0.3, 0.55, 0.3), scale=(0.15, 0.1, 0.1))
        Entity(parent=self.bay_parts["battery"], model="cube", color=color.blue, position=(-0.3, 0.55, 0.3), scale=(0.15, 0.1, 0.1))

        # стёкла: лобовое и покатое стекло люка
        glass_entity(b, [(-0.74, 0.87, Z(3.08)), (0.74, 0.87, Z(3.08)), (0.72, 1.30, Z(2.55)), (-0.72, 1.30, Z(2.55))], GLS)
        self.rear_glass = glass_entity(b, [(-0.72, 0.88, Z(0.45)), (0.72, 0.88, Z(0.45)), (0.70, 1.30, Z(1.45)), (-0.70, 1.30, Z(1.45))], GLS)
        self._tail_hinge = (0, 1.31, Z(1.45))
        self._geo = dict(W2=0.8125, L=4.20, sill=0.30, belt=0.80, roof=1.33, ws=2.9, rs=1.45, re=2.5, rgb=0.45, rb_y=0.88,
                         nose=0.62, seat_z=1.95, rear_z=1.05, seat_y=0.50, style="hatch", floor=0.37,
                         trunk_z0=0.12, trunk_z1=0.7, trunk_y=0.62, seat_c=(60, 60, 66))

        # фонари: широкая полоса по всей корме
        self.taillights = []
        for x0, x1 in ((-0.79, -0.31), (0.31, 0.79)):
            tl = Entity(parent=b, model="cube", color=color.rgb(120, 20, 20), position=((x0 + x1) / 2, 0.71, Z(-0.005)),
                        scale=(x1 - x0, 0.17, 0.02))
            self.taillights.append(tl)
        # номера
        self.plates = []
        for z, y, rot in ((Z(4.26), 0.41, 180), (Z(-0.02), 0.71, 0)):
            pl = Entity(parent=b, model="cube", color=color.rgb(240, 240, 240), position=(0, y, z), scale=(0.52, 0.11, 0.01))
            Text(self.car.plate, parent=pl, scale=(1 / 0.52 * 0.9, 1 / 0.11 * 0.9), origin=(0, 0), color=color.black,
                 position=(0, 0, -0.6 if rot == 0 else 0.6), rotation_y=rot)
            self.plates.append(pl)

    def _make_trims(self, b, boxes, col):
        """Обшивки дверей — отдельно: снял дверь — обшивки нет, видно салон."""
        self.trims = {}
        self._trim_boxes = {side: (bx, col) for side, bx in zip(("l", "r"), boxes)}
        for side, bx in zip(("l", "r"), boxes):
            mb = MeshBuilder()
            mb.box(*bx, col)
            # ручка и карман
            x0, y0, z0, x1, y1, z1 = bx
            mb.box(x0, y0 + 0.28, z0 + (z1 - z0) * 0.55, x1, y0 + 0.31, z0 + (z1 - z0) * 0.62, (30, 30, 30))
            self.trims[side] = Entity(parent=b, model=mb.build(keep=True), double_sided=True)

    def _build_interior_rust(self):
        """Ржавчина внутри салона: пол, пороги изнутри, низ обшивки, кромка торпедо."""
        import random as _r
        if getattr(self, "int_rust", None) is not None:
            destroy(self.int_rust)
            self.int_rust = None
        info = getattr(self, "_interior", None)
        if not info:
            return
        car = self.car
        rng = _r.Random(car.seed * 3 + 11)
        fr, dr = car.rust["floor"], car.rust["doors"]
        sl = max(car.rust["sill_l"], car.rust["sill_r"])
        mb = MeshBuilder()
        cols = [(128, 64, 28), (98, 46, 20), (150, 80, 36), (70, 40, 22)]
        y, hw, z0, z1 = info["floor_y"], info["hw"], info["z0"], info["z1"]
        for _ in range(int(fr / 3)):                                  # пол
            x = rng.uniform(-hw, hw)
            z = rng.uniform(min(z0, z1), max(z0, z1))
            r = rng.uniform(0.04, 0.12) * (0.6 + fr / 80)
            mb.box(x - r, y, z - r * 1.3, x + r, y + 0.006, z + r * 1.3, rng.choice(cols))
            if fr > 75 and rng.random() < 0.25:                       # дыры в полу
                mb.box(x - r * 0.5, y + 0.001, z - r * 0.6, x + r * 0.5, y + 0.008, z + r * 0.6, (10, 8, 6))
        for side in (-1, 1):                                           # пороги изнутри и низ обшивки
            for _ in range(int(max(sl, dr) / 6)):
                z = rng.uniform(min(z0, z1), max(z0, z1))
                h = rng.uniform(0.02, 0.1)
                mb.box(side * hw - 0.01, y, z - 0.08, side * hw + 0.01 * side, y + h + 0.04, z + 0.08, rng.choice(cols))
        for _ in range(int(dr / 12)):                                  # кромка торпедо, крепления
            x = rng.uniform(-hw, hw)
            mb.box(x - 0.05, info["dash_y"] - 0.02, info["dash_z"] - 0.01, x + 0.05, info["dash_y"] + 0.004,
                   info["dash_z"] + 0.05, rng.choice(cols))
        if mb.v:
            self.int_rust = Entity(parent=self.body, model=mb.build(keep=True), double_sided=True)

    def _build_snow(self):
        """Шапки снега на крыше, капоте и багажнике (толщина — car.snow)."""
        white = color.rgb(236, 240, 246)
        self.snow_parts = []
        sn = getattr(self, "_snow", None) or {}
        if sn.get("roof"):
            hw, y, z0, z1 = sn["roof"]
            e = Entity(parent=self.body, model="cube", color=white, position=(0, y, (z0 + z1) / 2),
                       scale=(hw * 2 - 0.1, 0.01, abs(z1 - z0) - 0.1))
            self.snow_parts.append((e, y))
        if sn.get("trunk"):
            hw, y, z0, z1 = sn["trunk"]
            e = Entity(parent=self.body, model="cube", color=white, position=(0, y, (z0 + z1) / 2),
                       scale=(hw * 2 - 0.12, 0.01, abs(z1 - z0) - 0.08))
            e._on_trunk = True                  # лежит на крышке багажника: поднимается вместе с ней
            self.snow_parts.append((e, y))
        hl = getattr(self, "_hood_len", 0.9)
        e = Entity(parent=self.hood, model="cube", color=white, position=(0, 0.0, hl / 2), scale=(1.3, 0.01, hl * 0.85))
        self.snow_parts.append((e, 0.0))
        self._snow_level = -1.0

    def _update_parts(self):
        car = self.car
        if getattr(self, "hood_mesh", None) is not None:
            self.hood_mesh.enabled = car.has("hood")
        if getattr(self, "seats_e", None) is not None:
            self.seats_e.enabled = car.has("seats")
        for side, t in getattr(self, "trims", {}).items():
            t.enabled = car.has("door_" + side) and not getattr(self, "_trim_off", {}).get(side)
        has_trunk = car.has("trunk")
        if getattr(self, "trunk_lid", None) is not None:
            self.trunk_lid.enabled = has_trunk
        if getattr(self, "rear_glass", None) is not None:
            self.rear_glass.enabled = has_trunk
        if not car.has("hood"):
            self.bay.enabled = True
        lvl = round(car.snow, 2)
        if (lvl, has_trunk) != (self._snow_level, getattr(self, "_snow_trunk", None)):
            self._snow_trunk = has_trunk
            self._snow_level = lvl
            th = 0.01 + 0.09 * lvl
            for e, y in self.snow_parts:
                e.enabled = lvl > 0.05 and (e.parent is not self.hood or car.has("hood")) and \
                    (not getattr(e, "_on_trunk", False) or has_trunk)
                e.scale_y = th
                if getattr(e, "_lid_y", None) is not None:      # шапка на крышке: координаты — от петли
                    e.y = e._lid_y + th / 2
                else:
                    e.y = y + th / 2

    # ------------------------------------------------------------------ состояние
    def refresh_rust(self, force=False):
        car = self.car
        key = tuple(int(v // 4) for v in car.rust.values()) + (int(car.dirt * 6), int(car.fade * 6),
                                                                 int(car.c("glass") * 4), tuple(car.dents),
                                                                 car.has("door_l"), car.has("door_r"),
                                                                 tuple(sorted(car.door_open.items())))
        if key == self._rust_key and not force:
            return
        self._rust_key = key
        self.side_r.texture = textures3d.car_side(self.car, "r")
        self.side_l.texture = textures3d.car_side(self.car, "l")
        self._build_interior_rust()

    def set_hood(self, open_):
        self.car.hood_open = bool(open_)
        self.hood.rotation_x = -55 if open_ else self.hood_rest
        self.bay.enabled = open_ or not self.car.has("hood")

    def _side_of(self, e):
        s = getattr(e, "_eside", None)
        if s is None:
            try:
                s = "l" if e.get_position(relative_to=self.body).x < 0 else "r"
            except Exception:
                s = "l"
            e._eside = s
        return s

    def update(self, dt, inp, night, lazy=False):
        car = self.car
        self.t += dt
        if self._deform_sig() != self._deform_key:
            self.apply_deforms()
        # стоящие чужие машины обновляются раз в ~12 кадров — их на карте много
        if lazy and not car.running and not car.cranking and abs(car.speed) < 0.01 and not inp and not car.turn \
                and not self.bolt_ents:
            key = (round(car.x, 2), round(car.y, 2), round(car.angle, 3), night > 0.15, car.lights, str(getattr(car, "lift", "")),
                   tuple(sorted(car.door_open.items())), car.trunk_open, round(sum(self._door_ang.values()) + self._tail_ang))
            self._lazy = getattr(self, "_lazy", 0) + 1
            if key == getattr(self, "_lazy_key", None) and self._lazy < 12:
                return
            self._lazy = 0
            self._lazy_key = key
        self.root.position = Vec3(car.x, 0, -car.y)
        self.root.rotation_y = 90 + math.degrees(car.angle)
        _under3d.apply_lift(self)                         # на домкрате / подставках (underside.py)
        # крен и клевки
        lat = car.speed * car.ang_vel
        soft = 1.6 - 0.8 * car.c("shocks")
        self.body.rotation_z = max(-4, min(4, lat * 0.35 * soft))
        acc = inp.get("throttle", 0) * (1 if car.running and car.gear else 0) - inp.get("brake", 0) * (1 if abs(car.speed) > 0.5 else 0)
        self.body.rotation_x += ((-acc * 1.4 * soft) - self.body.rotation_x) * min(1, dt * 4)
        y = 0.0
        if car.shake > 0.05:
            y += math.sin(self.t * 23) * car.shake * 0.025
        if car.running:
            y += math.sin(self.t * max(10, car.rpm / 60)) * 0.004 * (2 - car.c("engine"))
        flats = car.flat_tires()
        self.body.y = y - 0.04 * len(flats) - car.sink - (0.035 if car.has_tune("susp") else 0.0)
        self._update_parts()
        # колёса
        self.spin += car.speed / self.wr * dt
        for slot, (pivot, spin, bricks) in self.wheels.items():
            present = car.has(slot)
            pivot.enabled = present
            bricks.enabled = not present
            if not present:
                continue
            spin.rotation_x = math.degrees(self.spin)
            flat = slot in flats
            pivot.y = self.wr - 0.07 if flat else self.wr
            spin.scale_y = 0.78 if flat else 1.0
            if slot in ("tire_fl", "tire_fr"):
                pivot.rotation_y = math.degrees(car.front_delta)       # как реально повёрнуты колёса
        self.wheel_pivot.rotation_z = 0
        # руль: по часовой — вправо; рулевое передаточное ~13:1, синхронно с колёсами
        tgt = max(-540.0, min(540.0, math.degrees(car.front_delta) * 13.0))
        self.steer_spokes.rotation_z += (tgt - self.steer_spokes.rotation_z) * min(1.0, dt * 14)
        self._lightfr = getattr(self, "_lightfr", 0) + 1
        if getattr(car, "traffic", False) and self._lightfr % 4:
            return                                        # машина трафика: свет, номера, детали — раз в 4 кадра
        # свет
        lit = car.lights_ok
        side_ok = {"l": car.head_ok("l"), "r": car.head_ok("r")}     # у каждой фары своя цепь и предохранитель
        for t in self.plate_texts:
            if t.text != car.plate:
                t.text = car.plate
        for lamp in self.headlamps:
            lamp.enabled = car.has("lights")
        k = 0.4 + 0.6 * car.c("lights") if lit else 0
        for lamp in self.headlamps:
            if side_ok[self._side_of(lamp)]:
                lamp.color = color.rgb(255, 250, 220)
                lamp.setLightOff()
            else:
                lamp.color = color.rgb(190, 190, 176)
                lamp.clearLight()
        # поднимающиеся фары AE86: открыты, когда включён свет
        for pu in self.popups:
            target = -78 if car.lights else 0
            pu.rotation_x += (target - pu.rotation_x) * min(1, dt * 6)
        for bm in self.beams:
            bm.enabled = side_ok[self._side_of(bm)] and night > 0.15
            bm.color = color.rgba(255, 240, 200, int(140 * k))
        braking = inp.get("brake", 0) > 0.1 and car.battery_charge > 2 and car.elec_ok("brake")
        tail_on = car.lights and car.battery_charge > 2 and car.elec_ok("tail")
        for tl in self.taillights:
            if braking or tail_on:
                tl.color = color.rgb(255, 40, 30) if braking else color.rgb(200, 30, 25)
                tl.setLightOff()
            else:
                tl.color = color.rgb(120, 20, 20)
                tl.clearLight()
        for pl in self.plates:
            pl.enabled = car.registered
        for name, ent in self.bay_parts.items():
            ent.enabled = car.has(name)
        for name, ent in getattr(self, "tune_parts", {}).items():
            ent.enabled = car.has_tune(name)
        # машины трафика: тяжёлое (ржавчина, моторный отсек, двери/детали) — раз в 8 кадров
        self._heavy = getattr(self, "_heavy", 0) + 1
        if not getattr(car, "traffic", False) or self._heavy % 8 == 0:
            self._update_engine_vis()
            self._update_extras(dt)
            self.refresh_rust()
        # дым
        if car.running:
            fx, fy = car.forward()
            back = car.length / 2 + 0.1
            ex = car.x - fx * back + fy * 0.38
            ey = car.y - fy * back - fx * 0.38
            rich = car.choke or car.temp < 40 or car.c("plugs") < 0.4
            blue = car.c("engine") < 0.35
            rate = 6 + car.rpm / 400 * (0.3 + inp.get("throttle", 0))
            if rich:
                col = (60, 60, 62)
            elif blue:
                col = (140, 150, 175)
            else:
                col = (200, 200, 205)
            dens = 0.55 if rich or blue else 0.25
            if car.temp < 50:
                dens += 0.2   # пар из холодной трубы
            k = 1 - 0.8 * night
            col = tuple(int(c * k) for c in col)
            self.smoke.emit(dt, rate, (ex, 0.25, -ey), col, dens * (1 - 0.5 * night), (-fx * 0.6, 0.35, fy * 0.6))
        self.smoke.update(dt)


class Smoke:
    def __init__(self, n=48):
        self.pool = []
        for _ in range(n):
            e = Entity(model="quad", texture=textures3d.glow(), billboard=True, enabled=False)
            e.setTransparency(TransparencyAttrib.MAlpha)
            e.setDepthWrite(False)
            e.setBin("transparent", 30)
            e.setLightOff()
            self.pool.append([e, 0.0, Vec3(0, 0, 0), 0.0, (0, 0, 0)])
        self.acc = 0.0
        self.i = 0

    def emit(self, dt, rate, pos, col, dens, vel):
        self.acc += rate * dt
        while self.acc >= 1:
            self.acc -= 1
            p = self.pool[self.i]
            self.i = (self.i + 1) % len(self.pool)
            e = p[0]
            e.enabled = True
            e.position = Vec3(*pos)
            e.scale = 0.25
            p[1] = 1.6
            p[2] = Vec3(vel[0] + random.uniform(-0.2, 0.2), vel[1], vel[2] + random.uniform(-0.2, 0.2))
            p[3] = dens
            p[4] = col

    def update(self, dt):
        for p in self.pool:
            e = p[0]
            if not e.enabled:
                continue
            p[1] -= dt
            if p[1] <= 0:
                e.enabled = False
                continue
            e.position += p[2] * dt
            e.scale = 0.25 + (1.6 - p[1]) * 0.9
            a = p[3] * (p[1] / 1.6)
            e.color = color.rgba(*p[4], int(a * 255))


# ====================================================================== трафик


class AICar3D:
    def __init__(self, ai):
        self.ai = ai
        self.root = Entity()
        c = ai.color
        mb = MeshBuilder()
        police = ai.police
        body = (235, 235, 235) if police else c
        lower = (40, 110, 70) if police else c
        mb.box(-0.84, 0.28, -2.05, 0.84, 0.62, 2.05, lower)
        mb.box(-0.84, 0.62, -2.05, 0.84, 0.92, 2.05, body)
        mb.box(-0.78, 0.92, -1.75, 0.78, 1.38, 0.55, body)                   # кабина
        mb.box(-0.79, 0.97, -1.6, 0.79, 1.32, 0.45, (40, 52, 62))           # стёкла вокруг
        mb.box(-0.86, 0.3, 2.05, 0.86, 0.5, 2.15, (30, 30, 30))            # пластиковые бамперы
        mb.box(-0.86, 0.3, -2.15, 0.86, 0.5, -2.05, (30, 30, 30))
        for x in (-0.6, 0.6):
            mb.box(x - 0.2, 0.62, 2.05, x + 0.2, 0.75, 2.07, (235, 235, 210))
            mb.box(x - 0.2, 0.62, -2.07, x + 0.2, 0.78, -2.05, (170, 25, 25))
        if police:
            mb.box(-0.5, 1.38, -0.4, 0.5, 1.42, 0.2, (240, 240, 240))
        Entity(parent=self.root, model=mb.build(), double_sided=True)
        self.siren = None
        if police:
            self.siren = Entity(parent=self.root, model="cube", position=(0, 1.5, -0.1), scale=(0.7, 0.12, 0.22),
                                color=color.rgb(40, 70, 160))
            t = Text("ПОЛИЦИЯ", parent=self.root, position=(0.86, 0.75, 0), rotation_y=-90, scale=6, origin=(0, 0),
                     color=color.rgb(30, 90, 60))
            t2 = Text("ПОЛИЦИЯ", parent=self.root, position=(-0.86, 0.75, 0), rotation_y=90, scale=6, origin=(0, 0),
                      color=color.rgb(30, 90, 60))
        self.wheels = []
        for x in (-0.76, 0.76):
            for z in (-1.3, 1.3):
                self.wheels.append(Entity(parent=self.root, model=wheel_mesh(0.3, 0.18, seg=10, rim=(150, 150, 150)),
                                          position=(x, 0.3, z), double_sided=True))
        self.spin = 0.0

    def update(self, dt, t):
        ai = self.ai
        self.root.position = Vec3(ai.x, 0, -ai.y)
        self.root.rotation_y = 90 + math.degrees(ai.angle)
        self.spin += ai.speed / 0.3 * dt
        for w in self.wheels:
            w.rotation_x = math.degrees(self.spin)
        if self.siren is not None:
            on = ai.siren > 0 and int(t * 6) % 2 == 0
            self.siren.color = color.rgb(90, 150, 255) if on else color.rgb(40, 70, 160)
            if on:
                self.siren.setLightOff()
            else:
                self.siren.clearLight()


# ====================================================================== брошенные машины
class Wreck3D:
    """Брошенная машина у дороги: выцветшая краска, ржавчина, мутные/битые стёкла, спущенные колёса."""

    def __init__(self, w):
        import random as _r
        from state import WRECK_MODELS
        rng = _r.Random(w["seed"])
        self.id = w["id"]
        self.root = Entity()
        L, W = w["len"], w["wid"]
        hl, hw = L / 2, W / 2
        base = WRECK_MODELS[w["model"]][5]
        fade = tuple(int(c * 0.75 + 45) for c in base)
        rust = w["rust"]
        mb = MeshBuilder()
        sink = 0.08 if rng.random() < 0.5 else 0.0          # спущенные колёса — машина «села»
        y0 = 0.26 - sink
        mb.box(-hw, y0, -hl, hw, 0.84 - sink, hl, fade)
        roof_back, roof_front = -hl * 0.55, hl * 0.18
        if w["model"] in ("golf", "trabant"):
            roof_back = -hl * 0.85                            # хэтчбеки — крыша почти до конца
        mb.box(-hw + 0.08, 0.84 - sink, roof_back, hw - 0.08, 1.34 - sink, roof_front, fade,
               top=tuple(max(0, c - 15) for c in fade))
        glass = (60, 70, 72) if rng.random() < 0.6 else (95, 105, 100)
        for side in (-1, 1):
            mb.box(side * (hw - 0.05), 0.9 - sink, roof_back + 0.15, side * (hw - 0.035), 1.28 - sink, roof_front - 0.1, glass)
        mb.box(-hw + 0.15, 0.9 - sink, roof_front + 0.01, hw - 0.15, 1.28 - sink, roof_front + 0.025, glass)
        mb.box(-hw + 0.2, 0.9 - sink, roof_back - 0.025, hw - 0.2, 1.26 - sink, roof_back - 0.01, glass)
        mb.box(-hw - 0.03, 0.30 - sink, hl, hw + 0.03, 0.42 - sink, hl + 0.08, (70, 70, 70))    # бамперы
        mb.box(-hw - 0.03, 0.30 - sink, -hl - 0.08, hw + 0.03, 0.42 - sink, -hl, (70, 70, 70))
        for x in (-hw + 0.25, hw - 0.25):
            mb.box(x - 0.13, 0.55 - sink, hl, x + 0.13, 0.7 - sink, hl + 0.02, (150, 150, 140))
            mb.box(x - 0.13, 0.55 - sink, -hl - 0.02, x + 0.13, 0.7 - sink, -hl, (110, 30, 25))
        # ржавчина: пятна по бортам, аркам и порогам
        rcols = [(135, 66, 28), (105, 48, 22), (80, 40, 20)]
        for _ in range(int(10 + 30 * rust)):
            side = rng.choice((-1, 1))
            z = rng.uniform(-hl + 0.1, hl - 0.1)
            y = (rng.uniform(0.34, 0.62) if rng.random() < 0.75 else rng.uniform(0.62, 0.78)) - sink
            s_ = rng.uniform(0.03, 0.09) * (0.7 + rust)
            x = side * (hw + 0.005)
            mb.box(x - 0.004, y - s_, z - s_ * 1.4, x + 0.004, y + s_, z + s_ * 1.4, rng.choice(rcols))
        for _ in range(int(8 + 25 * rust)):                    # на капоте и крыше
            z = rng.uniform(-hl + 0.2, hl - 0.2)
            x = rng.uniform(-hw + 0.1, hw - 0.1)
            s_ = rng.uniform(0.05, 0.14)
            top = 1.34 - sink if roof_back < z < roof_front else 0.84 - sink
            mb.box(x - s_, top, z - s_, x + s_, top + 0.006, z + s_, rng.choice(rcols))
        Entity(parent=self.root, model=mb.build(), double_sided=True)
        # колёса (некоторых нет)
        for x in (-hw + 0.1, hw - 0.1):
            for z in (-hl + 0.75, hl - 0.75):
                if rng.random() < 0.18:
                    continue
                e = Entity(parent=self.root, model=wheel_mesh(0.28, 0.16, seg=10, rim=(95, 90, 85)),
                           position=(x, 0.28 - sink * 0.7, z), double_sided=True)
                e.scale_y = 0.85 if sink else 1.0

    def update(self, w):
        self.root.position = Vec3(w["x"], 0, -w["y"])
        self.root.rotation_y = 90 + math.degrees(w["angle"])


class Rope3D:
    """Буксировочный трос — тонкая жёлтая полоса между машинами."""

    def __init__(self):
        self.e = Entity(model="cube", color=color.rgb(230, 190, 40), enabled=False)

    def set(self, a, b):
        if a is None:
            self.e.enabled = False
            return
        ax, ay = a
        bx, by = b
        mid = Vec3((ax + bx) / 2, 0.45, -(ay + by) / 2)
        d = math.hypot(bx - ax, by - ay)
        self.e.enabled = True
        self.e.position = mid
        self.e.rotation = Vec3(0, math.degrees(math.atan2(bx - ax, -(by - ay))), 0)
        self.e.scale = (0.035, 0.035, max(0.1, d))
