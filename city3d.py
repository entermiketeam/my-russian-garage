"""3D-город Kleinbruck, собранный из данных world.py в несколько больших мешей."""
import math
import random

from panda3d.core import ColorBlendAttrib, TransparencyAttrib
from ursina import Entity, Text, color, scene

from streaming import mesh_group, point_group
from mesh3d import MeshBuilder
from world import (ROADS, BUILDINGS, GARAGE, GARAGE_WALLS, PUMP_ZONE, PUMPS, TUV_YARD, BLITZER,
                   MAP_W, MAP_H, AUTOHAUS_LOT, PARKING2, JUNKYARD, JUNK_LANE, JUNK_FENCES, JUNK_PILES,
                   SCRAP_DROP)
import textures3d
import i18n
from i18n import T

GRASS = (78, 112, 58)
ASPHALT = (78, 78, 82)
ASPHALT_LAND = (88, 88, 90)
SIDEWALK = (160, 158, 150)
LINE = (225, 225, 215)
CURB = (185, 183, 175)

# высоты особых зданий: (высота стен, тип крыши, этажей с окнами)
SPECIAL = {
    "apartment": (12.0, "gable", 4), "imbiss": (3.6, "flat", 1), "pizzeria": (6.5, "gable", 2),
    "supermarkt": (6.0, "flat", 0), "rathaus": (10.0, "gable", 3), "autoteile": (5.0, "flat", 1),
    "tanke": (4.0, "flat", 1), "tuv": (6.0, "flat", 1), "polizei": (8.0, "gable", 2),
    "lager": (9.0, "flat", 0), "kirche": (11.0, "gable", 0), "bahnhof": (7.0, "gable", 2),
    "schrott": (3.2, "flat", 1),
    "autohaus": (6.0, "flat", 0),
    "dealer": (4.2, "flat", 1),
}


def additive(ent):
    """Сделать сущность «светящейся» поверх сцены (аддитивное смешивание)."""
    ent.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OIncomingAlpha, ColorBlendAttrib.OOne))
    ent.setTransparency(TransparencyAttrib.MAlpha)
    ent.setDepthWrite(False)
    ent.setLightOff()
    ent.setBin("fixed", 10)


class City:
    def __init__(self, world):
        self.world = world
        rng = random.Random(7)
        self.build_ground()
        self.build_buildings(rng)
        self.build_props(rng)
        self.build_abandoned()
        self.build_lights()
        self.build_signs()

    # ----------------------------------------------------------------- земля и дороги
    def build_ground(self):
        g = MeshBuilder(uv_tile=6.0)
        m = 400
        g.flat2d(-m, -m, MAP_W + 2 * m, MAP_H + 2 * m, 0.0, GRASS)
        for fx, fy, fw, fh, col in self.world.fields:
            g.flat2d(fx, fy, fw, fh, 0.01, col)
        # тротуары
        for r in ROADS:
            if r[4] == "town":
                g.flat2d(r[0] - 2.5, r[1] - 2.5, r[2] + 5, r[3] + 5, 0.05, SIDEWALK)
        # дворы
        for z, col in ((PUMP_ZONE, (96, 96, 100)), (TUV_YARD, (104, 104, 108)), (GARAGE, (95, 93, 90)),
                       ((356, 310, 30, 4), (92, 92, 94)), (PARKING2, (100, 100, 102)),
                       (AUTOHAUS_LOT, (110, 110, 114)), ((1108, 312.5, 94, 5.5), (110, 110, 114)),
                       (JUNKYARD, (112, 104, 92)), (JUNK_LANE, (100, 96, 88))):
            g.flat2d(*z, 0.055, col)
        # асфальт
        for r in ROADS:
            g.flat2d(r[0], r[1], r[2], r[3], 0.07, ASPHALT if r[4] != "land" else ASPHALT_LAND)
        # разметка
        for r in ROADS:
            x, y, w, h, kind = r[:5]
            if kind == "autobahn":
                mid = x + w / 2
                for yy in range(int(y), int(y + h), 18):
                    for lx in (x + 6.5, x + w - 6.5):
                        g.flat2d(lx - 0.075, yy, 0.15, 6, 0.08, LINE)
                for lx in (x + 0.8, x + w - 0.8, mid - 1.2, mid + 1.05):
                    g.flat2d(lx - 0.075, y, 0.15, h, 0.08, LINE)
                continue
            if w > h:
                mid = y + h / 2
                for xx in range(int(x), int(x + w) - 3, 6):
                    g.flat2d(xx, mid - 0.06, 3, 0.12, 0.08, LINE)
            else:
                mid = x + w / 2
                for yy in range(int(y), int(y + h) - 3, 6):
                    g.flat2d(mid - 0.06, yy, 0.12, 3, 0.08, LINE)
        for c in self.world.crossings:
            g.flat2d(*c, 0.085, ASPHALT)
        # «зебра» у супермаркета и у Rathaus
        for zx in (445, 520):
            for k in range(6):
                g.flat2d(zx + k * 0.9, 300.5, 0.5, 9, 0.09, LINE)
        self.ground = mesh_group(g, "ground", texture=textures3d.detail(), double_sided=True)

    # ----------------------------------------------------------------- здания
    def _windows(self, wb, nb, rect, floors, wall_h, door=None, rng=None, lit=0.35):
        x, y, w, h = rect
        if floors <= 0:
            return
        fh = min(3.0, wall_h / max(1, floors))
        glass = (58, 72, 84)
        frame = (230, 228, 220)
        faces = [
            ("n", x, y, w, (0, 0, 1)), ("s", x, y + h, w, (0, 0, -1)),
            ("w", x, y, h, (-1, 0, 0)), ("e", x + w, y, h, (1, 0, 0)),
        ]
        for name, fx, fy, length, nrm in faces:
            n = int(length // 3.6)
            if n <= 0:
                continue
            step = length / n
            for f in range(floors):
                base = 0.9 + f * fh
                if base + 1.3 > wall_h - 0.2:
                    break
                for i in range(n):
                    c = (i + 0.5) * step
                    if name in ("n", "s"):
                        px, py = fx + c, fy
                    else:
                        px, py = fx, fy + c
                    if door and f == 0 and math.hypot(px - door[0], py - door[1]) < 3.2:
                        continue
                    self._win_quad(wb, name, px, py, base, 1.2, 1.3, glass, frame, nrm)
                    on = rng.random() < lit
                    wl = (255, 214, 140) if on else (20, 24, 34)
                    self._win_quad(nb, name, px, py, base, 1.2, 1.3, wl, None, nrm, out=0.06)

    @staticmethod
    def _win_quad(mb, face, px, py, base, ww, wh, col, frame, nrm, out=0.05):
        hw = ww / 2
        if face == "n":
            z = -py + out
            pts = [(px - hw, base, z), (px + hw, base, z), (px + hw, base + wh, z), (px - hw, base + wh, z)]
        elif face == "s":
            z = -py - out
            pts = [(px - hw, base, z), (px + hw, base, z), (px + hw, base + wh, z), (px - hw, base + wh, z)]
        elif face == "w":
            xx = px - out
            pts = [(xx, base, -py - hw), (xx, base, -py + hw), (xx, base + wh, -py + hw), (xx, base + wh, -py - hw)]
        else:
            xx = px + out
            pts = [(xx, base, -py - hw), (xx, base, -py + hw), (xx, base + wh, -py + hw), (xx, base + wh, -py - hw)]
        if frame:
            # рама чуть больше стекла
            cx = sum(p[0] for p in pts) / 4
            cy = sum(p[1] for p in pts) / 4
            cz = sum(p[2] for p in pts) / 4
            fr = [(cx + (p[0] - cx) * 1.15 - nrm[0] * 0.01, cy + (p[1] - cy) * 1.12, cz + (p[2] - cz) * 1.15 - nrm[2] * 0.01)
                  for p in pts]
            mb.poly(fr, frame, nrm)
        mb.poly(pts, col, nrm)

    def _door(self, mb, rect, door, col=(92, 62, 40)):
        x, y, w, h = rect
        dx, dy = door
        if dy <= y + 0.1:
            face, px, py = "n", dx, y
        elif dy >= y + h - 0.1:
            face, px, py = "s", dx, y + h
        elif dx <= x:
            face, px, py = "w", x, dy
        else:
            face, px, py = "e", x + w, dy
        nrm = {"n": (0, 0, 1), "s": (0, 0, -1), "w": (-1, 0, 0), "e": (1, 0, 0)}[face]
        self._win_quad(mb, face, px, py, 0.0, 1.3, 2.2, col, None, nrm, out=0.04)
        return face

    def build_buildings(self, rng):
        mb = MeshBuilder()
        self.roofs = []      # (вид, прямоугольник, высота стен, высота конька) — для снега на крышах
        wb = MeshBuilder()   # окна днём
        nb = MeshBuilder()   # окна ночью
        for i, hh in enumerate(self.world.houses):
            x, y, w, h, wall, roof, door = hh
            floors = 1 if rng.random() < 0.35 else 2
            wh = floors * 3.0
            mb.box2d(x, y, w, h, 0, 0.5, (120, 116, 110))          # цоколь
            mb.box2d(x, y, w, h, 0.5, wh, wall)
            gable = tuple(max(0, c - 12) for c in wall)
            rh_ = rng.uniform(2.5, 4.0)
            mb.gable2d(x, y, w, h, wh, rh_, roof, gable)
            self.roofs.append(("gable", (x, y, w, h), wh, rh_))
            if rng.random() < 0.5:   # печная труба
                cx, cy = x + w * rng.uniform(0.25, 0.75), y + h * rng.uniform(0.3, 0.7)
                mb.box2d(cx, cy, 0.6, 0.6, wh, wh + 3.8, (140, 70, 55))
            self._door(mb, (x, y, w, h), door)
            self._windows(wb, nb, (x, y, w, h), floors, wh, door, rng)
            # палисадник: живая изгородь у входа
            if rng.random() < 0.4:
                dx, dy = door
                mb.box(dx - 3, 0, -dy - 0.3, dx - 1.2, 0.9, -dy + 0.3, (50, 90, 45))

        for bid, b in BUILDINGS.items():
            x, y, w, h, name, wall, roof, door = b
            wh, kind, floors = SPECIAL[bid]
            mb.box2d(x, y, w, h, 0, wh, wall)
            if kind == "gable":
                mb.gable2d(x, y, w, h, wh, 4.0 if bid != "kirche" else 7.0, roof, tuple(max(0, c - 12) for c in wall))
                self.roofs.append(("gable", (x, y, w, h), wh, 4.0 if bid != "kirche" else 7.0))
            else:
                self.roofs.append(("flat", (x, y, w, h), wh, 0.0))
                mb.box2d(x - 0.2, y - 0.2, w + 0.4, h + 0.4, wh, wh + 0.5, roof)   # парапет
                mb.box2d(x + 1, y + 1, w - 2, h - 2, wh + 0.5, wh + 1.2, (110, 110, 112))  # вентиляция
            if door:
                self._door(mb, (x, y, w, h), door, (60, 70, 80) if kind == "flat" else (92, 62, 40))
            self._windows(wb, nb, (x, y, w, h), floors, wh, door, rng, lit=0.55)
            if bid == "autohaus":     # стеклянная витрина шоурума и красная полоса
                mb.box2d(x + 3, y - 0.05, w - 6, 0.2, 0.4, 4.2, (150, 190, 210))
                mb.box2d(x - 0.1, y - 0.15, w + 0.2, 0.2, 4.6, 5.4, (190, 25, 25))
            if bid == "supermarkt":   # витрина
                mb.box2d(x + 4, y + h - 0.05, w - 8, 0.2, 0.3, 3.2, (140, 180, 200))
            if bid == "kirche":       # колокольня со шпилем
                mb.box2d(x + 8, y + h - 10, 10, 10, 0, 24, wall)
                mb.cone(x + 13, 24, -(y + h - 5), 6.5, 14, (70, 90, 80), seg=4)
            if bid == "apartment":    # балконы
                for f in range(1, 4):
                    for bx in range(int(x) + 4, int(x + w) - 4, 8):
                        mb.box(bx, f * 3.0, -(y + h) - 1.3, bx + 3.2, f * 3.0 + 0.15, -(y + h), (170, 165, 155))
                        mb.box(bx, f * 3.0 + 0.15, -(y + h) - 1.3, bx + 3.2, f * 3.0 + 1.1, -(y + h) - 1.2, (150, 60, 50))
            if bid == "lager":        # рампы и ворота
                for k in range(4):
                    zx = x + 10 + k * 24
                    mb.box2d(zx, y + h - 0.1, 6, 0.3, 0, 4.2, (200, 160, 40))
                mb.box2d(x, y + h, w, 3, 0, 1.2, (130, 130, 128))
        self.buildings = mesh_group(mb, "buildings", double_sided=True)
        self.windows_day = mesh_group(wb, "windows_day", double_sided=True)
        self.windows_night = mesh_group(nb, "windows_night", setup=lambda e: e.setLightOff(), double_sided=True)
        self.windows_night.enabled = False

    # ----------------------------------------------------------------- мелочи
    def build_props(self, rng):
        gm = MeshBuilder()
        # гараж: стены и крыша (отдельно — прячутся при осмотре машины)
        gx, gy, gw, gh = GARAGE
        for wx, wy, ww, whh in GARAGE_WALLS:
            gm.box2d(wx, wy, ww, whh, 0, 2.7, (150, 140, 128))
        gm.box2d(gx - 1.2, gy - 0.4, gw + 2.4, gh + 1.4, 2.7, 2.95, (80, 80, 82))
        gm.box2d(gx - 1.2, gy - 0.4, gw + 2.4, 0.4, 2.2, 2.7, (150, 140, 128))       # перемычка ворот
        self.garage = Entity(model=gm.build(), double_sided=True)
        mb = MeshBuilder()
        mb.box2d(gx + 0.3, gy + gh - 1.2, 3.0, 0.8, 0, 0.9, (110, 80, 50))            # верстак
        mb.box2d(gx + 5.2, gy + gh - 0.7, 3.3, 0.5, 0, 2.0, (90, 70, 50))             # стеллаж
        for k in range(5):
            mb.box2d(gx + 5.4 + k * 0.6, gy + gh - 0.6, 0.35, 0.3, 1.2, 1.55,
                     [(200, 170, 40), (40, 90, 160), (160, 40, 40), (60, 120, 60), (200, 200, 200)][k])
        for k in range(3):   # старые шины в углу
            mb.cylinder(gx + 8.2, 0.02 + k * 0.2, -(gy + 1.2), 0.3, 0.18, (25, 25, 25), seg=10)
        # заправка: навес, колонки, стела с ценой
        px, py, pw, ph = PUMP_ZONE
        for cx in (px + 12, px + pw - 12):
            for cy in (py + 3, py + ph - 3):
                mb.box2d(cx - 0.3, cy - 0.3, 0.6, 0.6, 0, 5.0, (220, 220, 220))
        mb.box2d(px + 8, py + 1, pw - 16, ph - 2, 5.0, 5.8, (235, 235, 235), sides=(200, 30, 30))
        for p in PUMPS:
            mb.box2d(p[0] - 0.5, p[1] - 0.2, p[2] + 1.0, p[3] + 0.4, 0, 0.2, (160, 160, 160))
            mb.box2d(p[0], p[1], p[2], p[3], 0.2, 1.8, (210, 40, 40), top=(240, 240, 240))
        mb.box2d(px + pw + 2, py + ph - 2, 0.5, 0.5, 0, 6, (200, 200, 200))
        mb.box2d(px + pw + 1, py + ph - 2.2, 2.5, 0.8, 6, 9, (200, 30, 30))
        # автобан: отбойники
        for r in ROADS:
            if r[4] == "autobahn":
                x, y, w, h = r[:4]
                for bx in (x - 0.6, x + w + 0.4, x + w / 2 - 0.25):
                    mb.box2d(bx, y, 0.2, h, 0.45, 0.8, (170, 170, 175))
                    for yy in range(int(y), int(y + h), 4):
                        mb.box2d(bx, yy, 0.15, 0.15, 0, 0.6, (120, 120, 125))
        # железная дорога у вокзала
        for ry in (50.0, 51.5):
            mb.box2d(0, ry, MAP_W, 0.12, 0.1, 0.25, (120, 110, 100))
        for sx in range(0, int(MAP_W), 1):
            if sx % 2 == 0:
                mb.box2d(sx, 49.4, 0.3, 2.7, 0.0, 0.1, (90, 70, 50))
        # Autoverwertung Kowalski за гаражом: забор из профлиста, штабеля сплющенных машин, пресс
        for fx, fy, fw, fh in JUNK_FENCES:
            mb.box2d(fx, fy, max(fw, 0.12), max(fh, 0.12), 0, 2.3, (104, 116, 100))
            step = 2.0
            if fw > fh:
                for xx in range(int(fx), int(fx + fw), 2):
                    mb.box2d(xx, fy - 0.05, 0.12, 0.4, 0, 2.4, (80, 90, 78))
            else:
                for yy in range(int(fy), int(fy + fh), 2):
                    mb.box2d(fx - 0.05, yy, 0.4, 0.12, 0, 2.4, (80, 90, 78))
        for gx_ in (385.6, 395.0):                                   # столбы ворот
            mb.box2d(gx_, 343.7, 0.4, 0.6, 0, 3.4, (60, 60, 62))
        rust_cols = [(120, 62, 30), (95, 90, 88), (140, 115, 80), (80, 55, 40), (110, 45, 30), (70, 90, 110)]
        for (px_, py_, pw_, ph_) in JUNK_PILES[:-1]:
            h = 0.0
            layers = rng.randint(3, 5)
            for k in range(layers):
                inset = rng.uniform(0.0, 0.3)
                th = rng.uniform(0.45, 0.7)
                mb.box2d(px_ + inset, py_ + inset, pw_ - 2 * inset, ph_ - 2 * inset, h, h + th, rng.choice(rust_cols))
                h += th
        # гидравлический пресс и кран
        px_, py_, pw_, ph_ = JUNK_PILES[-1]
        mb.box2d(px_, py_, pw_, ph_, 0, 2.6, (225, 180, 30), top=(60, 60, 60))
        mb.box2d(px_ + 1, py_ + 1, pw_ - 2, ph_ - 2, 2.6, 3.4, (40, 40, 42))
        mb.box2d(px_ + pw_ - 0.6, py_ + ph_ - 0.6, 0.6, 0.6, 0, 9.0, (225, 180, 30))
        mb.box(px_ + pw_ - 0.3, 8.6, -(py_ + ph_ - 0.3) - 0.2, px_ + pw_ - 9.0, 9.0, -(py_ + ph_ - 0.3) + 0.2, (225, 180, 30))
        mb.box(px_ + pw_ - 8.9, 5.0, -(py_ + ph_ - 0.3) - 0.03, px_ + pw_ - 8.8, 8.6, -(py_ + ph_ - 0.3) + 0.03, (40, 40, 40))
        # покрышки у конторы
        for k in range(6):
            mb.cylinder(438 + (k % 3) * 0.7, 0.02 + (k // 3) * 0.22, -357, 0.32, 0.2, (25, 25, 25), seg=10)
        # разметка площадки приёма
        dx_, dy_, dw_, dh_ = SCRAP_DROP
        for fx, fy, fw, fh in ((dx_, dy_, dw_, 0.3), (dx_, dy_ + dh_ - 0.3, dw_, 0.3), (dx_, dy_, 0.3, dh_),
                               (dx_ + dw_ - 0.3, dy_, 0.3, dh_)):
            mb.flat2d(fx, fy, fw, fh, 0.075, (230, 190, 40))
        # площадка автосалона: подержанные машины на продажу, ценники, флажки
        lx, ly, lw, lh = AUTOHAUS_LOT
        for i, (cx, col) in enumerate(((1186, (170, 25, 25)), (1192, (40, 60, 120)), (1198, (200, 200, 205)))):
            cy = ly + 8
            mb.box(cx - 0.85, 0.3, -(cy + 4.1), cx + 0.85, 0.95, -cy, col)
            mb.box(cx - 0.78, 0.95, -(cy + 3.2), cx + 0.78, 1.38, -(cy + 1.1), (50, 60, 70))
            for wz in (cy + 0.8, cy + 3.3):
                for wx in (cx - 0.85, cx + 0.72):
                    mb.box(wx, 0.0, -(wz + 0.3), wx + 0.13, 0.58, -(wz - 0.3), (25, 25, 25))
            mb.box(cx - 0.3, 1.0, -(cy + 0.9), cx + 0.3, 1.25, -(cy + 0.88), (250, 250, 240))   # ценник за стеклом
        for fx in range(int(lx), int(lx + lw) + 1, 5):
            mb.box2d(fx, ly + 0.2, 0.08, 0.08, 0, 4.0, (200, 200, 200))
            mb.box2d(fx + 0.08, ly + 0.2, 0.9, 0.04, 3.1, 3.9, (190, 25, 25) if fx % 10 == 0 else (240, 240, 240))
        # блитцеры
        for bx, by, lim in BLITZER:
            mb.box2d(bx - 0.3, by - 0.3, 0.6, 0.6, 0, 2.6, (230, 230, 230))
            mb.box2d(bx - 0.35, by - 0.5, 0.7, 1.0, 2.0, 2.6, (40, 40, 40))
        # деревья
        crowns = MeshBuilder()
        for tx, ty, r, k in self.world.trees:
            if k == 2:   # ель
                mb.cylinder(tx, 0, -ty, 0.18, 1.2, (80, 60, 40), seg=5, cap=False)
                mb.cone(tx, 1.0, -ty, r * 0.75, r * 3.6, (40, 72, 45))
            else:
                mb.cylinder(tx, 0, -ty, 0.22, r * 1.3, (95, 72, 50), seg=5, cap=False)
                mb.cone(tx, r * 1.45, -ty, r * 0.4, r * 1.2, (78, 62, 48), seg=5)      # голые ветки (летом внутри кроны)
                # крона — отдельно: её цвет и видимость меняются по месяцу (set_season)
                shade = 235 if k == 0 else 255
                crowns.blob(tx, r * 1.3 + r * 0.6, -ty, r * 0.95, (shade, shade, shade))
        # фонари
        for lx, ly in self.world.lamps:
            mb.cylinder(lx, 0, -ly, 0.08, 5.2, (60, 62, 66), seg=5)
            mb.box(lx - 0.25, 5.0, -ly - 0.25, lx + 0.25, 5.25, -ly + 0.25, (50, 50, 55))
        self.props = mesh_group(mb, "props", double_sided=True)
        self.crowns = mesh_group(crowns, "crowns", double_sided=True)
        self._season = None

    def build_abandoned(self):
        """Заброшенные гаражи: бетонные стены с потёками, ржавая крыша, мох, полки с хламом, ворота-гармошка."""
        import random as _r
        mb = MeshBuilder()
        self.garage_doors = {}
        for ag in self.world.abandoned:
            rng = _r.Random(ag["id"])
            gx, gy, gw, gh = ag["rect"]
            wall_c = rng.choice([(150, 146, 138), (135, 120, 105), (160, 150, 130)])
            H = 2.9
            mb.flat2d(gx, gy, gw, gh, 0.03, (70, 66, 60))                                  # бетонный пол
            mb.flat2d(*ag["apron"], 0.025, (88, 82, 70))                                   # заросший подъезд
            for w in ag["walls"][:-1]:
                mb.box2d(*w, 0, H, wall_c)
            # потёки ржавчины и мох по стенам снаружи
            for w in ag["walls"][:-1]:
                wx, wy, ww, wh = w
                for k in range(6):
                    if ww > wh:
                        px, py = wx + rng.uniform(0.3, ww - 0.5), wy - 0.02
                        mb.box2d(px, py - 0.01, rng.uniform(0.15, 0.4), wh + 0.02, rng.uniform(0.6, 1.8), H - 0.1,
                                 rng.choice([(120, 80, 50), (70, 90, 55), (100, 95, 85)]))
                    else:
                        px, py = wx - 0.02, wy + rng.uniform(0.3, wh - 0.5)
                        mb.box2d(px - 0.01, py, ww + 0.02, rng.uniform(0.15, 0.4), rng.uniform(0.6, 1.8), H - 0.1,
                                 rng.choice([(120, 80, 50), (70, 90, 55), (100, 95, 85)]))
            mb.box2d(gx - 0.3, gy - 0.3, gw + 0.6, gh + 0.6, H, H + 0.12, (115, 70, 45), top=(125, 80, 50))   # ржавая крыша
            for k in range(5):     # мох/листья на крыше
                mb.box2d(gx + rng.uniform(0, gw - 1.5), gy + rng.uniform(0, gh - 1.5), 1.4, 1.2, H + 0.12, H + 0.16,
                         (70, 95, 50))
            # перемычка над воротами
            dx, dy, dw, dh = ag["door_rect"]
            mb.box2d(dx, dy, dw, dh, 2.35, H, wall_c)
            # полки с хламом
            sx, sy, sw, sh = ag["shelf"]
            mb.box2d(sx, sy, sw, sh, 0, 1.9, (95, 75, 55))
            for lvl in (0.5, 1.1, 1.7):
                for k in range(5):
                    along = sw > sh
                    bx = sx + (rng.uniform(0.1, sw - 0.5) if along else 0.05)
                    by = sy + (0.05 if along else rng.uniform(0.1, sh - 0.5))
                    col = rng.choice([(180, 60, 40), (200, 170, 50), (60, 80, 140), (90, 90, 90), (150, 120, 80)])
                    mb.box2d(bx, by, 0.35 if along else 0.4, 0.4 if along else 0.35, lvl, lvl + rng.uniform(0.2, 0.4), col)
            # старые покрышки и верстак у стены
            w0 = ag["walls"][0]
            for k in range(3):
                mb.cylinder(w0[0] + (0.8 if w0[2] < 1 else 1.2), 0.03 + k * 0.2, -(w0[1] + (1.2 if w0[2] < 1 else 0.8)),
                            0.3, 0.18, (25, 25, 25), seg=10)
            ww = ag["walls"][1]
            if ww[2] < 1:
                mb.box2d(ww[0] - 0.7, ww[1] + ww[3] * 0.35, 0.7, 1.6, 0, 0.9, (110, 85, 55))
            else:
                mb.box2d(ww[0] + ww[2] * 0.35, ww[1] - 0.7, 1.6, 0.7, 0, 0.9, (110, 85, 55))
            # ворота-гармошка (отдельно — поднимаются)
            door = Entity()
            dm = MeshBuilder()
            ribs = 12
            if dw > dh:
                for k in range(ribs):
                    y0 = k * 2.35 / ribs
                    dm.box2d(dx, dy + 0.05, dw, dh - 0.1, y0, y0 + 2.35 / ribs - 0.015, (120 + (k % 2) * 12, 72, 45))
            else:
                for k in range(ribs):
                    y0 = k * 2.35 / ribs
                    dm.box2d(dx + 0.05, dy, dw - 0.1, dh, y0, y0 + 2.35 / ribs - 0.015, (120 + (k % 2) * 12, 72, 45))
            door.model = dm.build()
            door.double_sided = True
            self.garage_doors[ag["id"]] = point_group(door, dx + dw / 2, dy + dh / 2, 4.0, "door")
        self.abandoned_mesh = mesh_group(mb, "abandoned", double_sided=True)

    def set_garage_door(self, gid, open_):
        d = self.garage_doors.get(gid)
        if d is None:
            return
        d = d.items[0][0]
        # ворота «сворачиваются» под потолок
        d.y = 2.0 if open_ else 0.0
        d.scale_y = 0.15 if open_ else 1.0

    def build_lights(self):
        bulbs = MeshBuilder()
        glows = MeshBuilder(uv_tile=None)
        for lx, ly in self.world.lamps:
            bulbs.box(lx - 0.2, 4.9, -ly - 0.2, lx + 0.2, 5.0, -ly + 0.2, (255, 225, 160))
            r = 11.0
            glows.poly([(lx - r, 0.12, -ly - r), (lx + r, 0.12, -ly - r), (lx + r, 0.12, -ly + r), (lx - r, 0.12, -ly + r)],
                       (255, 200, 130, 150), (0, 1, 0), uvs=[(0, 0), (1, 0), (1, 1), (0, 1)])
        self.bulbs = mesh_group(bulbs, "bulbs", setup=lambda e: e.setLightOff(), double_sided=True)
        self.glow = mesh_group(glows, "glow", with_uvs=True, setup=additive, texture=textures3d.glow(), double_sided=True)
        self.bulbs.enabled = False
        self.glow.enabled = False

    def build_signs(self):
        self.signs = []
        for bid, b in BUILDINGS.items():
            x, y, w, h, name, wall, roof, door = b
            wh = SPECIAL[bid][0]
            if door:
                dx, dy = door
                if dy <= y + 0.1:
                    pos, rot = (dx, min(wh - 0.8, 4.2), -y + 0.25), 180
                elif dy >= y + h - 0.1:
                    pos, rot = (dx, min(wh - 0.8, 4.2), -(y + h) - 0.25), 0
                elif dx <= x:
                    pos, rot = (x - 0.25, min(wh - 0.8, 4.2), -dy), 90
                else:
                    pos, rot = (x + w + 0.25, min(wh - 0.8, 4.2), -dy), -90
            else:
                pos, rot = (x + w / 2, wh - 1.2, -(y + h) - 0.25), 0
            self.signs.append(point_group(self._board(name, pos, rot, 34, (250, 245, 225), (25, 30, 40)),
                                          pos[0], -pos[2], 6.0, "sign"))
        # вывеска над воротами свалки (видна с Hauptstraße)
        self.signs.append(point_group(self._board(T("Авторазборка Ковальского — скупка старых машин"), (390.3, 4.2, -343.6),
                                                  180, 17, (20, 20, 20), (240, 200, 40)), 390.3, 343.6, 8.0, "sign"))
        # табличка населённого пункта (жёлтая, как в Германии)
        for (sx, sy, rot) in ((1318, 297, -90), (297, 918, 0), (297, 96, 180)):
            Entity(model="cube", position=(sx, 1.1, -sy), scale=(0.08, 2.2, 0.08), color=color.gray)
            self.signs.append(point_group(self._board(T("Кляйнбрук"), (sx, 2.5, -sy), rot, 16, (10, 10, 10), (245, 205, 40),
                                                      h=0.8), sx, sy, 3.0, "sign"))

    def _board(self, name, pos, rot, size, fg, bg, h=None):
        """Вывеска: щит + надпись (светятся ночью)."""
        board = Entity(position=pos, rotation_y=rot)
        ch = size * 0.025
        bw = len(name) * ch * 0.5 + ch * 1.2
        plate = Entity(parent=board, model="quad", scale=(bw, h or ch * 1.7), color=color.rgb(*bg), z=0.01)
        t = Text(name, parent=board, scale=size, origin=(0, 0), color=color.rgb(*fg), z=-0.02)
        i18n.live(t, name, after=lambda t: setattr(plate, "scale_x", len(t.text) * ch * 0.5 + ch * 1.2))
        board.setLightOff()
        return board

    def set_visible(self, v):
        for e in (self.ground, self.buildings, self.windows_day, self.props, self.garage, self.abandoned_mesh):
            e.enabled = v
        if getattr(self, "_season", None):
            self.crowns.enabled = v and self._season[1] >= 0.15
        for d in self.garage_doors.values():
            d.enabled = v
        for t in self.signs:
            t.enabled = v
        if not v:
            self.windows_night.enabled = self.bulbs.enabled = self.glow.enabled = False
        else:
            self.set_night(self._night)

    # ----------------------------------------------------------------- день/ночь
    _night = False

    # цвет листвы по месяцам: весной светлая, летом тёмная, осенью жёлтая/рыжая, зимой крон нет
    LEAF = {3: (150, 185, 95), 4: (120, 180, 80), 5: (80, 140, 60), 6: (68, 118, 50), 7: (64, 112, 48),
            8: (72, 112, 46), 9: (120, 130, 50), 10: (200, 130, 45), 11: (150, 95, 50)}

    def set_season(self, month, leaves):
        """Листва по календарю (calendar_de: leaves 0..1). Голые деревья — когда листьев почти нет."""
        key = (month, round(leaves, 1))
        if key == self._season:
            return
        self._season = key
        show = leaves >= 0.15
        col = self.LEAF.get(month, (64, 112, 48))
        for item in self.crowns.items:
            item[0].color = color.rgb(*col)
        self.crowns.enabled = show

    def set_night(self, night):
        self._night = night
        self.windows_night.enabled = night
        self.windows_day.enabled = not night
        self.bulbs.enabled = night
        self.glow.enabled = night


def Mesh_with_uvs(mb):
    from ursina import Mesh
    return Mesh(vertices=mb.v, triangles=mb.t, colors=mb.c, normals=mb.n, uvs=mb.uv)
