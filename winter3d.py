"""3D-вид зимы: снежный покров, валы вдоль дорог, сугробы у стен, снег на крышах и ёлках, слякоть с колеями.

Слякоть — настоящая сетка высот (winter.SlushPatch): колёса продавливают её, по краям колеи
остаются валики, и меш пятна пересобирается прямо во время игры.
"""
import math
import random

import numpy as np
from PIL import Image
from ursina import Entity, Mesh, Texture
from panda3d.core import TransparencyAttrib

from streaming import mesh_group
from mesh3d import MeshBuilder
from world import ROADS, MAP_W, MAP_H, BUILDINGS, GARAGE, PUMP_ZONE, TUV_YARD, AUTOHAUS_LOT, JUNKYARD, SCRAP_DROP, \
    PARKING2, SERVICE_LOT
from places import DEALER_LOT, TG_ENTRANCES
from winter import CELL, _noise

SNOW_Y = 0.092          # слой снега поверх земли/асфальта
SLUSH_Y = 0.096         # основание слякоти
SNOW = (236, 240, 246)
SNOW_DIRTY = (160, 154, 146)


def _tup(a):
    return list(map(tuple, a.tolist()))


def _snow_col(rng, k=1.0):
    v = rng.uniform(0.93, 1.02) * k
    return tuple(min(255, int(c * v)) for c in SNOW)


class Winter3D:
    def __init__(self, world, winter, city):
        self.world = world
        self.winter = winter
        self.city = city
        self.entities = []
        self.slush_e = {}          # индекс пятна -> (Entity, версия)
        rng = random.Random(1998)
        self._blocked = self._make_blocked()
        self.build_cover()
        self.build_banks(rng)
        self.build_drifts(rng)
        self.build_roofs(rng)
        self.build_trees(rng)
        self.visible = True

    # -------------------------------------------------------------- маска «здесь валов нет»
    def _make_blocked(self):
        W, H = int(MAP_W), int(MAP_H)
        m = np.zeros((H, W), bool)

        def fill(r, pad=0.0):
            x, y, w, h = r
            x0, y0 = max(0, int(x - pad)), max(0, int(y - pad))
            x1, y1 = min(W, int(math.ceil(x + w + pad))), min(H, int(math.ceil(y + h + pad)))
            if x1 > x0 and y1 > y0:
                m[y0:y1, x0:x1] = True

        for r in ROADS:
            fill(r[:4])
        for c in self.world.crossings:
            fill(c, 3)
        for g in self.world.places.gaps:
            fill(g, 1)
        for r in (GARAGE, PUMP_ZONE, TUV_YARD, AUTOHAUS_LOT, JUNKYARD, SCRAP_DROP, PARKING2, DEALER_LOT, SERVICE_LOT):
            fill(r, 2)
        for e in TG_ENTRANCES:
            fill(e["rect"], 2)
        for ag in self.world.abandoned:
            fill(ag["apron"], 1)
        for b in BUILDINGS.values():
            fill(b[:4])
            if b[7]:
                fill((b[7][0] - 2.5, b[7][1] - 2.5, 5, 5))
        for hh in self.world.houses:
            fill(hh[:4])
            d = hh[6]
            fill((d[0] - 1.5, d[1] - 1.5, 3, 3))
        # подъезд к своему гаражу с дороги
        gx, gy, gw, gh = GARAGE
        fill((gx - 2, gy - 12, gw + 4, 14))
        return m

    def _free(self, x, y):
        ix, iy = int(x), int(y)
        if ix < 0 or iy < 0 or iy >= self._blocked.shape[0] or ix >= self._blocked.shape[1]:
            return False
        return not self._blocked[iy, ix]

    # -------------------------------------------------------------- покров
    def build_cover(self):
        cov = self.winter.snow.cov
        H, W = cov.shape
        fine = _noise(W, H, 77, octaves=3, base=180)
        a = np.clip(cov * 1.18, 0, 1)
        img = np.zeros((H, W, 4), np.uint8)
        v = 0.9 + 0.1 * fine
        img[..., 0] = np.clip(236 * v, 0, 255)
        img[..., 1] = np.clip(240 * v, 0, 255)
        img[..., 2] = np.clip(247 * v, 0, 255)
        img[..., 3] = (a * 255).astype(np.uint8)
        tex = Texture(Image.fromarray(img, "RGBA"))
        tex.filtering = "mipmap"
        mb = MeshBuilder()
        mb.poly([(0, SNOW_Y, 0), (MAP_W, SNOW_Y, 0), (MAP_W, SNOW_Y, -MAP_H), (0, SNOW_Y, -MAP_H)], (255, 255, 255),
                (0, 1, 0), uvs=[(0, 1), (1, 1), (1, 0), (0, 0)])
        e = Entity(model=Mesh(vertices=mb.v, triangles=mb.t, colors=mb.c, normals=mb.n, uvs=mb.uv), texture=tex,
                   double_sided=True)
        e.setTransparency(TransparencyAttrib.MAlpha)
        e.setDepthOffset(1)
        self.entities.append(e)
        # за краем карты — сплошной снег
        m = MeshBuilder()
        M = 400
        for r in ((-M, -M, MAP_W + 2 * M, M), (-M, MAP_H, MAP_W + 2 * M, M), (-M, 0, M, MAP_H), (MAP_W, 0, M, MAP_H)):
            m.flat2d(*r, SNOW_Y - 0.08, (228, 232, 238))
        self.entities.append(Entity(model=m.build(), double_sided=True))

    # -------------------------------------------------------------- валы вдоль дорог
    def _ridge(self, mb, pts, rng, dirty_side=0):
        """Вал по списку сечений: (x, y, nx, ny, высота, ширина) — n смотрит «от дороги»."""
        prev = None
        for (x, y, nx, ny, h, w) in pts:
            prof = []
            for t, k in ((-0.5, 0.0), (-0.22, 0.75), (0.0, 1.0), (0.25, 0.7), (0.5, 0.0)):
                px, py = x + nx * w * t, y + ny * w * t
                prof.append((px, SNOW_Y + h * k, -py))
            if prev is not None:
                for i in range(4):
                    a0, a1, b0, b1 = prev[i], prev[i + 1], prof[i], prof[i + 1]
                    col = SNOW_DIRTY if (i == 0 and dirty_side) else _snow_col(rng, 0.96 if i == 0 else 1.0)
                    if i == 1 and dirty_side and rng.random() < 0.5:
                        col = tuple(int((a + b) / 2) for a, b in zip(SNOW_DIRTY, SNOW))
                    mb.poly([a0, a1, b1, b0], col, (0, 1, 0))
            prev = prof

    def build_banks(self, rng):
        mb = MeshBuilder()
        step = 1.8
        for r in ROADS:
            x, y, w, h, kind = r[:5]
            horiz = w > h
            length = w if horiz else h
            for side in (-1, 1):
                if horiz:
                    ex = None
                    ey = y if side < 0 else y + h
                else:
                    ex = x if side < 0 else x + w
                    ey = None
                off = {"town": 0.55, "land": 1.0, "autobahn": 1.6}[kind]
                size = {"town": 0.8, "land": 0.95, "autobahn": 1.15}[kind]
                run = []
                s = 0.0
                seed = rng.random() * 100
                while s <= length:
                    if horiz:
                        cx, cy = x + s, ey + side * off
                        nx, ny = 0.0, float(side)
                    else:
                        cx, cy = ex + side * off, y + s
                        nx, ny = float(side), 0.0
                    ok = self._free(cx, cy) and self._free(cx + nx * 0.8, cy + ny * 0.8)
                    if ok:
                        n = 0.5 + 0.5 * math.sin(s * 0.21 + seed) * math.sin(s * 0.057 + seed * 2) + rng.uniform(-0.12, 0.12)
                        hh = size * (0.12 + 0.45 * max(0.0, n))
                        ww = size * (0.9 + 0.7 * max(0.0, n))
                        if rng.random() < 0.06:          # местами расчищено до земли
                            hh *= 0.25
                        jx = rng.uniform(-0.15, 0.15)
                        run.append((cx + nx * jx, cy + ny * jx, nx, ny, hh, ww))
                    if not ok or s + step > length:
                        if len(run) >= 2:
                            run[0] = run[0][:4] + (0.02, run[0][5] * 0.5)
                            run[-1] = run[-1][:4] + (0.02, run[-1][5] * 0.5)
                            # край, обращённый к дороге (-n), — грязный от брызг
                            self._ridge(mb, [(px, py, -nx_, -ny_, hh_, ww_) for px, py, nx_, ny_, hh_, ww_ in run], rng,
                                        dirty_side=1)
                        run = []
                    s += step
        self.entities.append(mesh_group(mb, "snow", double_sided=True))

    # -------------------------------------------------------------- сугробы у стен
    def build_drifts(self, rng):
        mb = MeshBuilder()
        rects = [(hh[:4], hh[6]) for hh in self.world.houses] + [(b[:4], b[7]) for b in BUILDINGS.values()]
        rects += [(ag["rect"], ag["door_pt"]) for ag in self.world.abandoned]
        for (x, y, w, h), door in rects:
            for face in ("n", "s", "w", "e"):
                if rng.random() < 0.25:      # с тёплой стороны почти растаяло
                    continue
                if face in ("n", "s"):
                    fy = y - 0.05 if face == "n" else y + h + 0.05
                    ny = -1.0 if face == "n" else 1.0
                    pts_ = [(x + t, fy, 0.0, ny) for t in np.arange(0.0, w + 0.01, 1.0)]
                else:
                    fx = x - 0.05 if face == "w" else x + w + 0.05
                    nx = -1.0 if face == "w" else 1.0
                    pts_ = [(fx, y + t, nx, 0.0) for t in np.arange(0.0, h + 0.01, 1.0)]
                run = []
                seed = rng.random() * 10
                for i, (px, py, nx_, ny_) in enumerate(pts_):
                    near_door = door and math.hypot(px - door[0], py - door[1]) < 2.2
                    ok = not near_door and self._free_side(px + nx_ * 0.6, py + ny_ * 0.6)
                    if ok:
                        n = 0.5 + 0.5 * math.sin(i * 0.7 + seed) * math.cos(i * 0.23 + seed)
                        hh = 0.12 + 0.45 * n
                        ww = 1.0 + 1.1 * n
                        run.append((px + nx_ * ww * 0.5, py + ny_ * ww * 0.5, nx_, ny_, hh, ww))
                    if not ok or i == len(pts_) - 1:
                        if len(run) >= 2:
                            run[0] = run[0][:4] + (0.02, run[0][5])
                            run[-1] = run[-1][:4] + (0.02, run[-1][5])
                            # сугроб: высокий у стены, пологий наружу
                            self._drift(mb, run, rng)
                        run = []
        self.entities.append(mesh_group(mb, "snow", double_sided=True))

    def _free_side(self, x, y):
        """Снаружи дома: не на дороге и не на проезде (там снег счищен)."""
        ix, iy = int(x), int(y)
        if ix < 0 or iy < 0 or iy >= self._blocked.shape[0] or ix >= self._blocked.shape[1]:
            return False
        for r in ROADS:
            if r[0] - 0.5 <= x <= r[0] + r[2] + 0.5 and r[1] - 0.5 <= y <= r[1] + r[3] + 0.5:
                return False
        return True

    def _drift(self, mb, run, rng):
        prev = None
        for (x, y, nx, ny, h, w) in run:
            # точка у стены (-n * w/2) — самая высокая
            prof = []
            for t, k in ((-0.5, 0.0), (-0.48, 1.0), (-0.1, 0.8), (0.25, 0.35), (0.5, 0.0)):
                prof.append((x + nx * w * t, SNOW_Y + h * k, -(y + ny * w * t)))
            if prev is not None:
                for i in range(4):
                    mb.poly([prev[i], prev[i + 1], prof[i + 1], prof[i]], _snow_col(rng), (0, 1, 0))
            prev = prof

    # -------------------------------------------------------------- крыши
    def build_roofs(self, rng):
        mb = MeshBuilder()
        ice = MeshBuilder()
        for kind, (x, y, w, h), wh, rh in getattr(self.city, "roofs", []):
            if kind == "gable":
                self._gable_snow(mb, ice, rng, x, y, w, h, wh, rh)
            else:
                # плоская крыша: снег на парапете и на вентблоке, пятнами разной толщины
                top = wh + 0.5
                n = 4
                for i in range(n):
                    for j in range(n):
                        if rng.random() < 0.2:
                            continue
                        sx, sy = x + i * w / n, y + j * h / n
                        mb.box2d(sx, sy, w / n, h / n, top, top + rng.uniform(0.06, 0.22), _snow_col(rng))
                mb.box2d(x + 1.05, y + 1.05, w - 2.1, h - 2.1, wh + 1.2, wh + 1.2 + rng.uniform(0.08, 0.2), _snow_col(rng))
        # свой гараж, заброшенные гаражи, будки въездов в Tiefgarage
        gx, gy, gw, gh = GARAGE
        mb.box2d(gx - 1.1, gy - 0.3, gw + 2.2, gh + 1.2, 2.95, 3.12, _snow_col(rng))
        for ag in self.world.abandoned:
            ax, ay, aw, ah = ag["rect"]
            for k in range(3):
                mb.box2d(ax - 0.2 + k * aw / 3, ay - 0.2, aw / 3 + 0.1, ah + 0.4, 3.02, 3.02 + rng.uniform(0.1, 0.25),
                         _snow_col(rng))
        for e in TG_ENTRANCES:
            ex, ey, ew, eh = e["rect"]
            mb.box2d(ex - 0.2, ey + 4.7, ew + 0.4, eh - 4.8, 3.35, 3.35 + rng.uniform(0.12, 0.25), _snow_col(rng))
        # колючая «шапка» на кучах металлолома у Ковальского
        from world import JUNK_PILES
        for (px, py, pw, ph) in JUNK_PILES[:-1]:
            for k in range(int(ph // 3)):
                mb.box2d(px + 0.3, py + k * 3 + 0.3, pw - 0.6, 2.4, 2.2 + rng.uniform(0, 0.6), 2.5 + rng.uniform(0, 0.8),
                         _snow_col(rng, 0.97))
        self.entities.append(mesh_group(mb, "snow", double_sided=True))
        if len(ice):
            ie = mesh_group(ice, "ice", setup=lambda e: e.setTransparency(TransparencyAttrib.MAlpha), double_sided=True)
            self.entities.append(ie)

    def _gable_snow(self, mb, ice, rng, x, y, w, h, wh, rh):
        o = 0.4
        lift = 0.07
        melted = rng.random() < 0.15           # тёплый чердак: снег съехал/растаял
        strips = rng.randint(3, 6)
        if w >= h:
            z0, z1 = -(y + h), -y
            zm = (z0 + z1) / 2
            for side, (za, zb) in ((0, (z0 - o, zm)), (1, (z1 + o, zm))):
                for k in range(strips):
                    if melted and rng.random() < 0.6:
                        continue
                    xa = x - o + (w + 2 * o) * k / strips
                    xb = x - o + (w + 2 * o) * (k + 1) / strips
                    t = rng.uniform(0.08, 0.2)
                    low = rng.uniform(0.0, 0.35) if rng.random() < 0.4 else 0.0   # снег сполз, открыв низ
                    y0_ = wh + lift + (rh * low)
                    zlow = za + (zb - za) * low
                    p = [(xa, y0_, zlow), (xb, y0_, zlow), (xb, wh + rh + lift, zb), (xa, wh + rh + lift, zb)]
                    n = (0, 1, -1) if side == 0 else (0, 1, 1)
                    mb.poly(p, _snow_col(rng), n)
                    # толщина по нижнему краю
                    mb.poly([(xa, y0_, zlow), (xb, y0_, zlow), (xb, y0_ - t, zlow), (xa, y0_ - t, zlow)], _snow_col(rng, 0.9),
                            (0, 0, -1) if side == 0 else (0, 0, 1))
                    if low == 0.0 and rng.random() < 0.5:        # сосульки
                        for _ in range(rng.randint(1, 4)):
                            ix = rng.uniform(xa, xb)
                            L = rng.uniform(0.15, 0.6)
                            ice.poly([(ix - 0.04, wh - 0.02, zlow), (ix + 0.04, wh - 0.02, zlow), (ix, wh - L, zlow)],
                                     (215, 230, 245, 190), (0, 0, 1))
        else:
            xm = x + w / 2
            for side, (xa0, xb0) in ((0, (x - o, xm)), (1, (x + w + o, xm))):
                for k in range(strips):
                    if melted and rng.random() < 0.6:
                        continue
                    ya = y - o + (h + 2 * o) * k / strips
                    yb = y - o + (h + 2 * o) * (k + 1) / strips
                    t = rng.uniform(0.08, 0.2)
                    low = rng.uniform(0.0, 0.35) if rng.random() < 0.4 else 0.0
                    y0_ = wh + lift + rh * low
                    xlow = xa0 + (xb0 - xa0) * low
                    p = [(xlow, y0_, -ya), (xlow, y0_, -yb), (xb0, wh + rh + lift, -yb), (xb0, wh + rh + lift, -ya)]
                    n = (-1, 1, 0) if side == 0 else (1, 1, 0)
                    mb.poly(p, _snow_col(rng), n)
                    mb.poly([(xlow, y0_, -ya), (xlow, y0_, -yb), (xlow, y0_ - t, -yb), (xlow, y0_ - t, -ya)],
                            _snow_col(rng, 0.9), (-1, 0, 0) if side == 0 else (1, 0, 0))

    # -------------------------------------------------------------- деревья
    def build_trees(self, rng):
        mb = MeshBuilder()
        for tx, ty, r, k in self.world.trees:
            if k == 2:      # ель: белые «юбки» на ярусах
                for lvl in (0.45, 0.7):
                    rr = r * 0.75 * (1 - lvl) * 1.15
                    mb.cone(tx, 1.0 + r * 3.6 * lvl - 0.05, -ty, rr, r * 3.6 * 0.12, _snow_col(rng), seg=7)
                mb.cone(tx, 1.0 + r * 3.6 * 0.86, -ty, r * 0.12, r * 3.6 * 0.15, _snow_col(rng), seg=5)
            else:           # лиственные: зимой без листьев — снег лежит на развилке голых веток
                mb.blob(tx, r * 2.3, -ty, r * 0.38, _snow_col(rng), shade=0.97)
        self.entities.append(mesh_group(mb, "snow", double_sided=True))

    # -------------------------------------------------------------- слякоть
    @staticmethod
    def _patch_arrays(p):
        x0, y0, w, h = p.rect
        ny, nx = p.h.shape
        jj, ii = np.meshgrid(np.arange(nx), np.arange(ny))
        hh = p.h
        xs = x0 + jj * CELL
        ys = y0 + ii * CELL
        base_y = SLUSH_Y + (-0.045 if p.kind == "walk" else 0.0)
        verts = np.stack([xs, base_y + hh * 1.6, -ys], axis=-1).reshape(-1, 3)
        # нормали по градиенту (рельеф чуть преувеличен — колеи читаются под любым светом)
        gx = np.gradient(hh, CELL, axis=1) * 4.0
        gy = np.gradient(hh, CELL, axis=0) * 4.0
        n = np.stack([-gx, np.ones_like(hh), gy], axis=-1)
        n /= np.linalg.norm(n, axis=-1, keepdims=True)
        # цвет: свежая серо-белая каша, грязная коричневатая, в колее — мокрая тёмная
        rel = np.clip(hh / max(1e-4, p.thick), 0, 1.6)
        fresh = np.array([222, 221, 214], np.float32) / 255
        dirty = np.array([140, 128, 110], np.float32) / 255
        wet = np.array([52, 50, 47], np.float32) / 255
        d = np.clip(p.dirt * 0.8 + 0.3 * (rel < 0.5), 0, 1)[..., None]
        col = fresh * (1 - d) + dirty * d
        comp = np.clip(p.comp, 0, 1)[..., None]
        col = col * (1 - comp * 0.9) + wet * comp * 0.9
        berm = np.clip(rel - 1.0, 0, 0.6)[..., None] / 0.6
        col = col * (1 - berm * 0.5) + (dirty * 0.85) * berm * 0.5
        # по краям пятна слякоть сходит на нет — прозрачность
        a = np.clip(p.base / 0.006, 0, 1) * 0.96
        a = np.maximum(a, comp[..., 0] * np.clip(p.base / 0.003, 0, 1) * 0.9)
        cols = np.concatenate([col, a[..., None]], axis=-1).reshape(-1, 4)
        # треугольники
        idx = np.arange(ny * nx).reshape(ny, nx)
        a0 = idx[:-1, :-1].ravel()
        a1 = idx[:-1, 1:].ravel()
        b0 = idx[1:, :-1].ravel()
        b1 = idx[1:, 1:].ravel()
        tris = np.stack([a0, b0, b1, a0, b1, a1], axis=-1).ravel()
        return verts, n.reshape(-1, 3), cols, tris

    def _build_patch(self, i):
        p = self.winter.slush.patches[i]
        v, n, c, t = self._patch_arrays(p)
        m = Mesh(vertices=_tup(v), triangles=t.tolist(), normals=_tup(n), colors=_tup(c), static=False)
        e = Entity(model=m, double_sided=True)
        e.setTransparency(TransparencyAttrib.MAlpha)
        e.setDepthOffset(2)
        e.enabled = self.visible
        self.slush_e[i] = [e, p.version]
        p.dirty = False

    def _refresh_patch(self, i):
        e, ver = self.slush_e[i]
        p = self.winter.slush.patches[i]
        v, n, c, t = self._patch_arrays(p)
        m = e.model
        m.vertices = _tup(v)
        m.normals = _tup(n)
        m.colors = _tup(c)
        m.generate()
        self.slush_e[i][1] = p.version
        p.dirty = False

    def reset_slush(self):
        from ursina import destroy
        for e, _ in self.slush_e.values():
            destroy(e)
        self.slush_e = {}

    def update(self, px, py, budget=3):
        """Показывать пятна слякоти рядом с игроком; пересобирать продавленные."""
        slush = self.winter.slush
        if getattr(self, "_field", None) is not slush:      # новая игра / загрузка
            self.reset_slush()
            self._field = slush
        if not self.visible:
            return
        near = set()
        gx0, gx1 = int((px - 90) // 20), int((px + 90) // 20)
        gy0, gy1 = int((py - 90) // 20), int((py + 90) // 20)
        for gx in range(gx0, gx1 + 1):
            for gy in range(gy0, gy1 + 1):
                near.update(slush.grid.get((gx, gy), ()))
        from ursina import destroy
        for i in list(self.slush_e):
            p = slush.patches[i]
            x0, y0, w, h = p.rect
            if i not in near and (abs(px - (x0 + w / 2)) > 130 or abs(py - (y0 + h / 2)) > 130):
                destroy(self.slush_e[i][0])
                del self.slush_e[i]
        # сначала ближайшие
        order = sorted(near, key=lambda i: abs(px - slush.patches[i].rect[0] - slush.patches[i].rect[2] / 2) +
                       abs(py - slush.patches[i].rect[1] - slush.patches[i].rect[3] / 2))
        work = 0
        for i in order:
            if i not in self.slush_e:
                self._build_patch(i)
                work += 1
            elif self.slush_e[i][1] != slush.patches[i].version:
                self._refresh_patch(i)
                work += 1
            if work >= budget:
                break

    def set_visible(self, v):
        self.visible = v
        for e in self.entities:
            e.enabled = v
        for e, _ in self.slush_e.values():
            e.enabled = v
