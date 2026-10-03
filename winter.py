"""Зима: снежный покров и слякоть. Только логика (numpy), без графики — её рисует winter3d.py.

SnowCover — карта покрытия снегом 1 пиксель = 1 м (0..1): на траве много, на тротуарах местами,
            на дорогах мало и в основном у обочин, у стен домов — надувы. Влияет на сцепление.
SlushField — пятна слякоти ТОЛЬКО на дорогах и тротуарах. Каждое пятно — сетка высот 0.25 м:
            колёса продавливают колеи (слякоть выдавливается в валики по бокам), снегопад их заносит.
"""
import math
import random

import numpy as np

from world import ROADS, MAP_W, MAP_H, BUILDINGS, GARAGE, SERVICE_LOT, SERVICE_HALL, rect_overlap

CELL = 0.25      # шаг сетки слякоти, м


def _noise(w, h, seed, octaves=5, base=6):
    """Плавный шум 0..1 размером (h, w) — сумма октав билинейно растянутых случайных решёток."""
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w), dtype=np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        n = base * (2 ** o)
        g = rng.random((n + 1, n + 1)).astype(np.float32)
        ys = np.linspace(0, n, h, dtype=np.float32)
        xs = np.linspace(0, n, w, dtype=np.float32)
        y0 = np.floor(ys).astype(int).clip(0, n - 1)
        x0 = np.floor(xs).astype(int).clip(0, n - 1)
        fy = (ys - y0)[:, None]
        fx = (xs - x0)[None, :]
        fy = fy * fy * (3 - 2 * fy)
        fx = fx * fx * (3 - 2 * fx)
        a = g[y0][:, x0]
        b = g[y0][:, x0 + 1]
        c = g[y0 + 1][:, x0]
        d = g[y0 + 1][:, x0 + 1]
        out += amp * ((a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy)
        tot += amp
        amp *= 0.5
    return out / tot


def _fill(mask, r, val=True):
    x, y, w, h = r
    x0, y0 = max(0, int(x)), max(0, int(y))
    x1, y1 = min(mask.shape[1], int(math.ceil(x + w))), min(mask.shape[0], int(math.ceil(y + h)))
    if x1 > x0 and y1 > y0:
        mask[y0:y1, x0:x1] = val


def _dilate(m, n):
    out = m.copy()
    for _ in range(n):
        o = out.copy()
        o[1:, :] |= out[:-1, :]
        o[:-1, :] |= out[1:, :]
        o[:, 1:] |= out[:, :-1]
        o[:, :-1] |= out[:, 1:]
        out = o
    return out


class SnowCover:
    def __init__(self, world):
        W, H = int(MAP_W), int(MAP_H)
        road = np.zeros((H, W), bool)
        walk = np.zeros((H, W), bool)
        build = np.zeros((H, W), bool)
        for r in ROADS:
            _fill(road, r[:4])
            if r[4] == "town":
                _fill(walk, (r[0] - 2.5, r[1] - 2.5, r[2] + 5, r[3] + 5))
        walk &= ~road
        for b in BUILDINGS.values():
            _fill(build, b[:4])
        for h in world.houses:
            _fill(build, h[:4])
        for ag in world.abandoned:
            _fill(build, ag["rect"])
        _fill(build, GARAGE)
        _fill(build, SERVICE_HALL)                      # цех автосервиса — под крышей
        yards = [GARAGE, SERVICE_LOT] + [ag["apron"] for ag in world.abandoned]
        from places import DEALER_LOT
        yards.append(DEALER_LOT)
        dead = np.zeros((H, W), bool)          # заброшенные парковки: никто не чистит — снег по щиколотку
        for pp in world.places.parkings:
            _fill(dead, pp["rect"])
        yard = np.zeros((H, W), bool)
        for y_ in yards:
            _fill(yard, y_)
        n1 = _noise(W, H, 11, octaves=6, base=8)
        n2 = _noise(W, H, 29, octaves=4, base=40)
        cov = 0.72 + 0.28 * n1 + 0.1 * (n2 - 0.5)                       # трава / поля
        # надувы у стен и заборов
        near = _dilate(build, 3) & ~build
        cov = np.where(near, np.minimum(1.0, cov + 0.25), cov)
        # тротуары: протоптано посередине, сугробы у краёв
        cov = np.where(walk, 0.28 + 0.45 * n1, cov)
        # площадки: машинами укатано, пятнами
        cov = np.where(yard & ~road, 0.2 + 0.55 * n2 * n1, cov)
        cov = np.where(dead, 0.55 + 0.45 * n1, cov)
        # дороги: почти чисто, снег у кромки, иногда на осевой
        edge = road & ~(_erode(road, 2))
        cov = np.where(road, 0.03 + 0.18 * (n1 > 0.62) * n1, cov)
        cov = np.where(edge, 0.35 + 0.4 * n1, cov)
        # под деревьями меньше
        for tx, ty, tr, _ in world.trees:
            x0, x1 = int(max(0, tx - tr)), int(min(W, tx + tr))
            y0, y1 = int(max(0, ty - tr)), int(min(H, ty + tr))
            cov[y0:y1, x0:x1] *= 0.7
        cov[build] = 0.0
        self.cov = np.clip(cov, 0, 1).astype(np.float32)
        self.road = road
        self.walk = walk

    def at(self, x, y):
        if x < 0 or y < 0 or x >= self.cov.shape[1] or y >= self.cov.shape[0]:
            return 0.0
        return float(self.cov[int(y), int(x)])

    def grip(self, x, y):
        """Сцепление на снегу: на дороге снега мало — почти асфальт, в поле — как по целине."""
        c = self.at(x, y)
        return 1.0 - 0.42 * c

    def offroad_depth(self, x, y):
        """На целине снег сопротивляется как неглубокая слякоть."""
        if self.on_paved(x, y):
            return 0.0
        return 0.035 * self.at(x, y)

    def on_paved(self, x, y):
        ix, iy = int(x), int(y)
        if ix < 0 or iy < 0 or ix >= self.cov.shape[1] or iy >= self.cov.shape[0]:
            return False
        return bool(self.road[iy, ix] or self.walk[iy, ix])

    def rgba(self):
        """Картинка покрытия для 3D (белый снег, альфа = покрытие)."""
        a = (np.clip(self.cov * 1.15, 0, 1) * 255).astype(np.uint8)
        img = np.zeros(self.cov.shape + (4,), np.uint8)
        img[..., 0] = 236
        img[..., 1] = 240
        img[..., 2] = 246
        img[..., 3] = a
        return img


def _erode(m, n):
    return ~_dilate(~m, n)


class SlushPatch:
    def __init__(self, rect, thick, rng, kind="road"):
        self.rect = rect
        x, y, w, h = rect
        self.nx = max(2, int(w / CELL))
        self.ny = max(2, int(h / CELL))
        self.thick = thick
        self.kind = kind
        noise = rng.random((self.ny + 1, self.nx + 1)).astype(np.float32)
        # сгладить шум
        for _ in range(2):
            noise = (noise + np.roll(noise, 1, 0) + np.roll(noise, -1, 0) + np.roll(noise, 1, 1) + np.roll(noise, -1, 1)) / 5
        # плавно сходит на нет к краям пятна
        yy = np.linspace(0, 1, self.ny + 1)[:, None]
        xx = np.linspace(0, 1, self.nx + 1)[None, :]
        edge = np.minimum(np.minimum(xx, 1 - xx) * w, np.minimum(yy, 1 - yy) * h)
        taper = np.clip(edge / 0.6, 0, 1) ** 0.7
        self.base = (thick * (0.6 + 0.8 * noise) * taper).astype(np.float32)
        self.h = self.base.copy()
        self.dirt = rng.random((self.ny + 1, self.nx + 1)).astype(np.float32) * 0.6 + 0.2 * (kind == "road")
        self.comp = np.zeros_like(self.h)          # насколько продавлено (для цвета колеи)
        self.dirty = True
        self.version = 0

    def contains(self, x, y):
        x0, y0, w, h = self.rect
        return x0 <= x <= x0 + w and y0 <= y <= y0 + h

    def depth(self, x, y):
        x0, y0, w, h = self.rect
        i = int((y - y0) / CELL)
        j = int((x - x0) / CELL)
        if 0 <= i <= self.ny and 0 <= j <= self.nx:
            return float(self.h[i, j])
        return 0.0

    def press(self, x, y, radius, weight=1.0):
        """Колесо продавливает слякоть: в следе тонко и мокро, по краям — валик."""
        x0, y0, w, h = self.rect
        ci = (y - y0) / CELL
        cj = (x - x0) / CELL
        r = max(radius / CELL, 0.85)      # след не уже ячейки сетки
        rb = r + 1.1
        i0, i1 = max(0, int(ci - rb)), min(self.ny, int(ci + rb) + 1)
        j0, j1 = max(0, int(cj - rb)), min(self.nx, int(cj + rb) + 1)
        if i0 > i1 or j0 > j1:
            return
        ii = np.arange(i0, i1 + 1)[:, None]
        jj = np.arange(j0, j1 + 1)[None, :]
        d = np.sqrt((ii - ci) ** 2 + (jj - cj) ** 2)
        sub = self.h[i0:i1 + 1, j0:j1 + 1]
        inner = d <= r
        ring = (d > r) & (d <= rb)
        target = np.maximum(0.003, self.base[i0:i1 + 1, j0:j1 + 1] * (0.25 - 0.1 * weight))
        displaced = np.clip(sub - target, 0, None) * inner
        moved = float(displaced.sum())
        if moved <= 1e-5:
            return
        sub[inner] = np.minimum(sub[inner], target[inner])
        if ring.any():
            sub[ring] += moved / ring.sum() * 0.6
            np.minimum(sub, self.base[i0:i1 + 1, j0:j1 + 1] * 1.45 + 0.01, out=sub)
        self.comp[i0:i1 + 1, j0:j1 + 1][inner] = 1.0
        self.dirty = True
        self.version += 1

    def regrow(self, amount):
        """Снегопад заметает колеи, со временем «свежая» слякоть темнеет и оседает."""
        if amount <= 0:
            return
        self.h += (self.base - self.h) * min(1.0, amount)
        self.comp *= max(0.0, 1.0 - amount * 0.7)
        self.dirty = True
        self.version += 1


class SlushField:
    """Пятна слякоти на проезжей части и тротуарах (на земле её нет)."""

    def __init__(self, world, seed=1998):
        rng = random.Random(seed)
        nrng = np.random.default_rng(seed)
        self.patches = []
        crossings = world.crossings
        for r in ROADS:
            x, y, w, h, kind = r[:5]
            horiz = w > h
            length = w if horiz else h
            width = h if horiz else w
            step = 22 if kind == "town" else 45
            if kind == "autobahn":
                step = 90
            pos = rng.uniform(5, step)
            while pos < length - 8:
                plen = rng.uniform(5, 14)
                # пятно — в колее у обочины или у осевой, иногда во всю полосу
                lane_w = rng.choice([2.2, 3.0, 4.2])
                side = rng.choice([0.0, width - lane_w, width / 2 - lane_w / 2, rng.uniform(0, width - lane_w)])
                thick = rng.uniform(0.05, 0.11) if rng.random() < 0.32 else rng.uniform(0.012, 0.035)
                if horiz:
                    rect = (x + pos, y + side, plen, lane_w)
                else:
                    rect = (x + side, y + pos, lane_w, plen)
                self.patches.append(SlushPatch(rect, thick, nrng, "road"))
                pos += plen + rng.uniform(step * 0.5, step * 1.4)
            # тротуары: тонкая жижа
            if kind == "town":
                for s_ in (-1, 1):
                    pos = rng.uniform(5, 40)
                    while pos < length - 6:
                        plen = rng.uniform(3, 9)
                        if horiz:
                            yy = y - 2.4 if s_ < 0 else y + h + 0.1
                            rect = (x + pos, yy, plen, 2.3)
                        else:
                            xx = x - 2.4 if s_ < 0 else x + w + 0.1
                            rect = (xx, y + pos, 2.3, plen)
                        self.patches.append(SlushPatch(rect, rng.uniform(0.01, 0.03), nrng, "walk"))
                        pos += plen + rng.uniform(20, 55)
        # на перекрёстках — большие лужи-каши
        for c in crossings:
            if rng.random() < 0.6:
                cx, cy, cw, ch = c
                rect = (cx + rng.uniform(0, cw * 0.3), cy + rng.uniform(0, ch * 0.3), cw * rng.uniform(0.5, 0.8),
                        ch * rng.uniform(0.5, 0.8))
                self.patches.append(SlushPatch(rect, rng.uniform(0.04, 0.09), nrng, "road"))
        # начальные колеи — по машинам, которые тут уже проехали
        for p in self.patches:
            if p.kind != "road":
                continue
            x0, y0, w, h = p.rect
            horiz_p = w > h
            for lane in (0.3, 0.7):
                if rng.random() < 0.6:
                    for k in range(int((w if horiz_p else h) / 0.3)):
                        t = k * 0.3
                        if horiz_p:
                            p.press(x0 + t, y0 + h * lane, 0.1, 0.5)
                            p.press(x0 + t, y0 + h * lane + 1.35 * (1 if lane < 0.5 else -1) * 0.5, 0.1, 0.5)
                        else:
                            p.press(x0 + w * lane, y0 + t, 0.1, 0.5)
        # пространственный индекс 20 м
        self.grid = {}
        for idx, p in enumerate(self.patches):
            x0, y0, w, h = p.rect
            for gx in range(int(x0 // 20), int((x0 + w) // 20) + 1):
                for gy in range(int(y0 // 20), int((y0 + h) // 20) + 1):
                    self.grid.setdefault((gx, gy), []).append(idx)

    def patch_at(self, x, y):
        for idx in self.grid.get((int(x // 20), int(y // 20)), ()):
            p = self.patches[idx]
            if p.contains(x, y):
                return p
        return None

    def depth(self, x, y):
        p = self.patch_at(x, y)
        return p.depth(x, y) if p else 0.0

    def press(self, x, y, radius=0.1, weight=1.0):
        p = self.patch_at(x, y)
        if p:
            p.press(x, y, radius, weight)

    def regrow(self, amount):
        for p in self.patches:
            p.regrow(amount)


def wheel_points(car):
    """Координаты пятен контакта колёс (2D)."""
    fx, fy = car.forward()
    rx, ry = -fy, fx
    ra, fa = car.spec["axles"]
    half = car.length / 2
    tr = car.spec["track"]
    out = []
    for ax in (fa - half, ra - half):
        for side in (-1, 1):
            out.append((car.x + fx * ax + rx * tr * side, car.y + fy * ax + ry * tr * side))
    return out


class Winter:
    def __init__(self, world):
        self.snow = SnowCover(world)
        self.slush = SlushField(world)
        self._last = {}      # последняя точка продавливания для каждой машины
        self.level = 1.0     # сколько снега лежит по сезону (state.snow_level): 0 — лето, 1 — зима

    def surface(self, car):
        """(сцепление, глубина слякоти под колёсами) для машины."""
        if car.x >= 2350 or self.level <= 0.02:      # подземные гаражи / бесснежный сезон: сухо
            return 1.0, 0.0
        pts = wheel_points(car)
        depth = sum(self.slush.depth(x, y) for x, y in pts) / 4
        off = sum(self.snow.offroad_depth(x, y) for x, y in pts) / 4
        grip = sum(self.snow.grip(x, y) for x, y in pts) / 4
        lv = self.level
        return 1.0 - (1.0 - grip) * lv, (depth + off) * lv

    def drive(self, key, car):
        """Колёса движущейся машины оставляют колеи в слякоти."""
        if abs(car.speed) < 0.3 or car.x >= 2350 or self.level <= 0.1:
            return
        last = self._last.get(key)
        if last and math.hypot(car.x - last[0], car.y - last[1]) < 0.18:
            return
        self._last[key] = (car.x, car.y)
        w = min(1.0, car.spec["mass"] / 1200)
        for x, y in wheel_points(car):
            self.slush.press(x, y, 0.09 + car.spec.get("wheel_r", 0.29) * 0.05, w)
