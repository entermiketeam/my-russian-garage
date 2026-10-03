"""3D-вид особых мест: подземные гаражи, заброшенные парковки, площадка Weber, детали на земле.

Всё статическое собирается в несколько больших мешей (MeshBuilder). Под землёй освещение
«запечено» в цвета вершин: светлые пятна под рабочими лампами, темнота под разбитыми.
"""
import math
import random

from ursina import Entity, Text, color

from streaming import mesh_group, point_group
from mesh3d import MeshBuilder
from places import INTERIOR_X, TG_ENTRANCES, DEALER_LOT, DEALER_SELL, driveway
from world import JUNKYARD
import textures3d
import i18n
from i18n import T

HEIGHTS = {"modern": 2.7, "modern_low": 2.3, "old": 2.6, "bunker": 2.4}
PALETTE = {
    #            пол              стены             полоса на стенах  потолок
    "modern": ((138, 140, 138), (205, 205, 198), (40, 90, 160), (170, 170, 166)),
    "modern_low": ((118, 120, 118), (180, 178, 170), (160, 120, 30), (140, 140, 136)),
    "old": ((96, 94, 88), (168, 156, 120), (150, 60, 40), (120, 116, 106)),
    "bunker": ((88, 90, 86), (120, 126, 112), (60, 80, 60), (100, 102, 96)),
}
YELLOW = (225, 185, 30)
BLACK = (28, 28, 28)
WHITE = (215, 215, 208)


def _mul(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c[:3])


def obox(mb, cx, cy, ang, w, d, h0, h1, col, top=None):
    """Повёрнутая коробка: центр (cx, cy) в 2D-мире, w — вдоль угла ang, d — поперёк."""
    ca, sa = math.cos(ang), math.sin(ang)
    hw, hd = w / 2, d / 2
    pts = [(cx + ca * u - sa * v, cy + sa * u + ca * v) for u, v in ((-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd))]
    bot = [(x, h0, -y) for x, y in pts]
    tp = [(x, h1, -y) for x, y in pts]
    mb.poly(tp, top or col, (0, 1, 0))
    for i in range(4):
        a, b = i, (i + 1) % 4
        mx = (pts[a][0] + pts[b][0]) / 2 - cx
        my = (pts[a][1] + pts[b][1]) / 2 - cy
        mb.poly([bot[a], bot[b], tp[b], tp[a]], col, (mx, 0, -my))


def beam(mb, p0, p1, r, col):
    """Квадратный брус между двумя 3D-точками (наклонный столб, стрела шлагбаума)."""
    dx, dy, dz = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
    L = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
    d = (dx / L, dy / L, dz / L)
    up = (0, 1, 0) if abs(d[1]) < 0.9 else (1, 0, 0)
    a = (d[1] * up[2] - d[2] * up[1], d[2] * up[0] - d[0] * up[2], d[0] * up[1] - d[1] * up[0])
    la = math.sqrt(sum(v * v for v in a)) or 1.0
    a = tuple(v / la * r for v in a)
    b = (d[1] * a[2] - d[2] * a[1], d[2] * a[0] - d[0] * a[2], d[0] * a[1] - d[1] * a[0])
    offs = [(a[i] + b[i] for i in range(3)), (a[i] - b[i] for i in range(3)),
            (-a[i] - b[i] for i in range(3)), (-a[i] + b[i] for i in range(3))]
    offs = [tuple(o) for o in offs]
    for i in range(4):
        o1, o2 = offs[i], offs[(i + 1) % 4]
        q = [tuple(p0[k] + o1[k] for k in range(3)), tuple(p0[k] + o2[k] for k in range(3)),
             tuple(p1[k] + o2[k] for k in range(3)), tuple(p1[k] + o1[k] for k in range(3))]
        n = tuple((o1[k] + o2[k]) for k in range(3))
        mb.poly(q, col, n)


def board(text, pos, rot, size, fg, bg, parent=None, h=None):
    """Табличка с надписью (не зависит от освещения)."""
    e = Entity(parent=parent, position=pos, rotation_y=rot)
    ch = size * 0.025
    bw = len(text) * ch * 0.52 + ch * 1.2
    plate = Entity(parent=e, model="quad", scale=(bw, h or ch * 1.7), color=color.rgb(*bg), z=0.01)
    t = Text(text, parent=e, scale=size, origin=(0, 0), color=color.rgb(*fg), z=-0.02)
    i18n.live(t, text, after=lambda t: setattr(plate, "scale_x", len(t.text) * ch * 0.52 + ch * 1.2))
    e.setLightOff()
    return e


# ====================================================================== детали на земле
def part_mesh(mb, it):
    """Небольшая модель детали по её слоту."""
    x, y, rot = it["x"], it["y"], it.get("rot", 0.0)
    sl = it.get("slot") or ""
    pid = it["id"]
    rng = random.Random(int(x * 13 + y * 7))
    rust = (120, 70, 40)
    if sl.startswith("tire") or pid.startswith("tire"):
        if rng.random() < 0.5:   # лежит плашмя
            mb.cylinder(x, 0.08, -y, 0.31, 0.19, (26, 26, 26), seg=12)
            mb.cylinder(x, 0.08, -y, 0.17, 0.195, (120, 120, 118), seg=10)
        else:                    # прислонена
            beam(mb, (x - 0.1, 0.32, -y), (x + 0.1, 0.32, -y), 0.3, (26, 26, 26))
        return
    if sl in ("door_l", "door_r"):
        col = rng.choice([(150, 40, 35), (196, 186, 150), (70, 110, 150), (110, 120, 90)])
        obox(mb, x, y, rot, 1.05, 0.9, 0.08, 0.13, col, top=_mul(col, 0.9))
        obox(mb, x + 0.1, y, rot, 0.5, 0.45, 0.13, 0.135, rust)
        obox(mb, x - 0.15, y + 0.2, rot, 0.6, 0.35, 0.13, 0.14, (50, 60, 70))   # стекло
        return
    if sl in ("hood", "trunk"):
        col = rng.choice([(150, 40, 35), (196, 186, 150), (70, 110, 150), (200, 200, 195)])
        obox(mb, x, y, rot, 1.3, 1.1 if sl == "hood" else 0.9, 0.08, 0.12, col)
        obox(mb, x + 0.2, y - 0.1, rot, 0.4, 0.5, 0.12, 0.125, rust)
        return
    if sl in ("engine", "gearbox"):
        big = sl == "engine"
        obox(mb, x, y, rot, 0.7 if big else 0.6, 0.5 if big else 0.35, 0.08, 0.62 if big else 0.4, (78, 80, 82))
        if big:
            obox(mb, x, y, rot, 0.62, 0.3, 0.62, 0.72, (130, 60, 40))      # клапанная крышка
            obox(mb, x + 0.2, y + 0.25, rot, 0.25, 0.1, 0.3, 0.5, (60, 55, 50))
        obox(mb, x, y, rot, 1.0, 0.8, 0.02, 0.08, (140, 115, 75))           # поддон-паллета
        return
    if sl == "seats":
        col = rng.choice([(90, 60, 45), (60, 60, 70), (120, 40, 35)])
        obox(mb, x, y, rot, 0.55, 0.55, 0.08, 0.42, col)
        ca, sa = math.cos(rot), math.sin(rot)
        obox(mb, x - ca * 0.25, y - sa * 0.25, rot, 0.12, 0.55, 0.3, 1.0, col)
        return
    if sl == "battery":
        obox(mb, x, y, rot, 0.28, 0.18, 0.08, 0.3, (30, 30, 32), top=(60, 60, 64))
        return
    if sl == "lights":
        mb.cylinder(x, 0.08, -y, 0.1, 0.12, (170, 175, 180), seg=8)
        return
    if sl == "radiator":
        obox(mb, x, y, rot, 0.7, 0.08, 0.08, 0.55, (120, 100, 70))
        return
    if sl == "exhaust":
        obox(mb, x, y, rot, 1.6, 0.12, 0.08, 0.18, rust)
        obox(mb, x + 0.3, y, rot, 0.55, 0.26, 0.08, 0.28, (100, 60, 35))
        return
    if sl == "glass":
        obox(mb, x, y, rot, 1.2, 0.6, 0.08, 0.1, (90, 120, 130))
        return
    # мелочь: генератор, стартер, карбюратор, амортизаторы, тормоза...
    obox(mb, x, y, rot, 0.3, 0.22, 0.08, 0.3, rng.choice([(90, 90, 92), (120, 110, 90), (70, 70, 72)]))


# ====================================================================== главный класс
class Places3D:
    def __init__(self, world, rng=None):
        self.world = world
        self.pl = world.places
        rng = rng or random.Random(11)
        self.surface = []
        self.interior = []
        self.flicker = []
        self.price_tags = {}
        self._loose_sig = None
        self.loose_e = None
        self.build_entrances(rng)
        self.build_parkings(rng)
        self.build_dealer(rng)
        self.build_junk_extra(rng)
        self.level_ents = {}
        # вывески на поверхности — тоже по расстоянию
        self.surface = [point_group(e, e.x, -e.z, 6.0, "board") if isinstance(e, Entity) and e.model is None else e
                        for e in self.surface]
        for L in self.pl.levels:
            i0 = len(self.interior)
            self.build_level(L)
            self.level_ents[L["id"]] = self.interior[i0:]
        self._level = None
        self._under = None
        self.set_under(False)

    # -------------------------------------------------------------- въезды
    def build_entrances(self, rng):
        mb = MeshBuilder()
        glow = MeshBuilder(uv_tile=None)
        for e in self.pl.entrances:
            x, y, w, h = e["rect"]
            # пандус «уходит вниз»: пол темнеет к южной стене, над дальней частью — бетонный короб
            n = 10
            for i in range(n):
                t = i / n
                col = _mul((120, 120, 118), 1.0 - 0.9 * t)
                mb.flat2d(x + 0.4, y + t * h, w - 0.8, h / n + 0.02, 0.09, col)
            for i in range(0, int(h), 1):          # рифлёные полосы против скольжения
                mb.flat2d(x + 0.6, y + i + 0.3, w - 1.2, 0.08, 0.095, _mul((90, 90, 88), 1 - 0.8 * i / h))
            for wx, wy, ww, wh in e["walls"]:
                mb.box2d(wx, wy, ww, wh, 0, 1.1 if wy + wh < y + 5 else 3.0, (175, 172, 164))
            # короб над спуском, чёрный проём
            mb.box2d(x - 0.3, y + 4.6, w + 0.6, h - 4.6, 3.0, 3.35, (160, 158, 150))
            mb.box2d(x, y + 4.6, w, 0.4, 2.35, 3.0, (185, 182, 175))
            mb.box2d(x + 0.4, y + h - 0.8, w - 0.8, 0.3, 0, 3.0, (4, 4, 5))
            # жёлто-чёрная окантовка въезда
            for k in range(int(w / 0.6)):
                mb.box2d(x + k * 0.6, y + 4.55, 0.6, 0.06, 2.1, 2.35, YELLOW if k % 2 else BLACK)
            # шлагбаум (поднят) и будка с кнопкой
            bx, by = x + w - 1.0, y + 2.0
            mb.box2d(bx - 0.25, by - 0.25, 0.5, 0.5, 0, 1.1, (230, 230, 225), top=(200, 40, 30))
            for k in range(6):
                t0, t1 = k / 6, (k + 1) / 6
                p0 = (bx - 0.2 - t0 * 3.5 * 0.5, 1.0 + t0 * 3.5 * 0.85, -by)
                p1 = (bx - 0.2 - t1 * 3.5 * 0.5, 1.0 + t1 * 3.5 * 0.85, -by)
                beam(mb, p0, p1, 0.05, (220, 30, 30) if k % 2 == 0 else (240, 240, 235))
            mb.box2d(x - 1.4, y + 1.0, 0.8, 0.6, 0, 1.3, (60, 64, 70), top=(90, 90, 95))
            # знак «P» на столбе
            px, py = x - 1.6, y - 1.2
            mb.cylinder(px, 0, -py, 0.06, 3.0, (150, 150, 150), seg=6)
            mb.box(px - 0.45, 2.3, -py - 0.03, px + 0.45, 3.2, -py + 0.03, (30, 80, 170))
            # лампы в коробе
            for ly in (y + 7, y + 10.5):
                mb.box2d(x + w / 2 - 0.6, ly, 1.2, 0.2, 2.9, 2.98, (255, 235, 190))
                r = 2.4
                cx = x + w / 2
                glow.poly([(cx - r, 0.12, -ly - r), (cx + r, 0.12, -ly - r), (cx + r, 0.12, -ly + r), (cx - r, 0.12, -ly + r)],
                          (255, 220, 170, 110), (0, 1, 0), uvs=[(0, 0), (1, 0), (1, 1), (0, 1)])
            self.surface.append(board("P", (px, 2.75, -py + 0.05), 180, 40, (250, 250, 250), (30, 80, 170)))
            self.surface.append(board("P", (px, 2.75, -py - 0.05), 0, 40, (250, 250, 250), (30, 80, 170)))
            self.surface.append(board(e["name"], (x + w / 2, 3.18, -(y + 4.6) + 0.33), 180, 12, (245, 245, 240),
                                      (35, 40, 50)))
            self.surface.append(board(T("Въезд  ·  высота до 2,00 м"), (x + w / 2, 2.62, -(y + 4.6) + 0.34), 180, 8,
                                      (20, 20, 20), YELLOW))
        from city3d import additive
        self.surface.append(mesh_group(mb, "tg", double_sided=True))
        self.surface.append(mesh_group(glow, "tg_glow", with_uvs=True, setup=additive, texture=textures3d.glow(),
                                       double_sided=True))

    # -------------------------------------------------------------- парковки
    def build_parkings(self, rng):
        mb = MeshBuilder()
        gnd = MeshBuilder(uv_tile=5.0)
        for P in self.pl.parkings:
            r = random.Random(P["id"] + "3d")
            x, y, w, h = P["rect"]
            style = P["style"]
            base = {"market": (84, 84, 86), "gravel": (118, 110, 98), "yard": (96, 94, 92)}[style]
            gnd.flat2d(x, y, w, h, 0.06, base)
            gnd.flat2d(*driveway(P), 0.06, _mul(base, 0.95))
            # заплатки и выбоины разного цвета
            for _ in range(30 if style != "gravel" else 45):
                pw, ph = r.uniform(1, 5), r.uniform(1, 4)
                gnd.flat2d(x + r.uniform(0, w - pw), y + r.uniform(0, h - ph), pw, ph, 0.062,
                           _mul(base, r.uniform(0.82, 1.12)))
            # выцветшая разметка мест (часть стёрлась)
            for bx, by, ba in P["bays"]:
                if style == "gravel":
                    continue
                ca, sa = math.cos(ba), math.sin(ba)
                for side in (-1.3, 1.3):
                    if r.random() < 0.35:
                        continue
                    px, py = bx - sa * side, by + ca * side
                    obox(mb, px, py, ba, 4.8, 0.1, 0.063, 0.066, _mul(WHITE, r.uniform(0.55, 0.85)))
            for kind, px, py, ang, pw, pd, ph, col in P["props"]:
                self._prop(mb, r, kind, px, py, ang, pw, pd, ph, col, P)
            # табличка с названием у въезда
            dx, dy, dw, dh = driveway(P)
            sx, sy = dx - 1.0, dy + (dh if P["door"] == "w" else 0)
            mb.cylinder(sx, 0, -sy, 0.05, 2.4, (120, 120, 118), seg=5)
            rot = {"n": 180, "s": 0, "w": 90, "e": -90}[P["door"]]
            self.surface.append(board(P["name"], (sx, 2.2, -sy + (0.05 if rot == 180 else 0)), rot, 9,
                                      (30, 30, 30), (225, 222, 205)))
            self.surface.append(board(T("Частная территория — вход запрещён"), (sx, 1.75, -sy + (0.05 if rot == 180 else 0)),
                                      rot, 6, (240, 240, 240), (170, 35, 30)))
        self.surface.append(mesh_group(gnd, "places_gnd", texture=textures3d.detail(), double_sided=True))
        self.surface.append(mesh_group(mb, "places", double_sided=True))

    def _prop(self, mb, r, kind, px, py, ang, pw, pd, ph, col, P):
        if kind == "wall":
            # полуразрушенная стена: сегменты разной высоты, граффити, потёки
            n = max(1, int(max(pw, pd)))
            along = pw >= pd
            for k in range(n):
                hh = ph * r.uniform(0.55, 1.0) if r.random() < 0.6 else ph
                if along:
                    mb.box2d(px + k * pw / n, py, pw / n, pd, 0, hh, _mul(col, r.uniform(0.85, 1.05)))
                else:
                    mb.box2d(px, py + k * pd / n, pw, pd / n, 0, hh, _mul(col, r.uniform(0.85, 1.05)))
            for k in range(3):
                gc = r.choice([(60, 120, 180), (190, 50, 120), (40, 40, 40), (220, 160, 40)])
                if along:
                    gx = px + r.uniform(0, pw - 1.5)
                    mb.box2d(gx, py - 0.02, r.uniform(0.8, 1.8), pd + 0.04, 0.3, r.uniform(0.8, 1.2), gc)
                else:
                    gy = py + r.uniform(0, pd - 1.5)
                    mb.box2d(px - 0.02, gy, pw + 0.04, r.uniform(0.8, 1.8), 0.3, r.uniform(0.8, 1.2), gc)
        elif kind == "sign":
            mb.box2d(px, py, 0.15, 0.15, 0, ph, (110, 110, 112))
            mb.box2d(px + pw - 0.15, py, 0.15, 0.15, 0, ph, (110, 110, 112))
            mb.box2d(px - 0.2, py, pw + 0.4, 0.12, ph - 1.3, ph, _mul(col, 0.8))
            mb.box2d(px + 0.4, py - 0.01, 0.9, 0.14, ph - 1.1, ph - 0.4, (150, 90, 60))   # ржавое пятно
            self.surface.append(board(T("КОНСУМ"), (px + pw / 2, ph - 0.65, -py + 0.08), 180, 22, (250, 245, 230),
                                      _mul(col, 0.8)))
        elif kind == "cart":
            tipped = r.random() < 0.35
            if tipped:
                obox(mb, px, py, ang, 0.9, 0.6, 0.05, 0.6, _mul(col, 0.9))
            else:
                obox(mb, px, py, ang, 0.9, 0.6, 0.4, 1.0, col)
                obox(mb, px, py, ang, 0.8, 0.5, 0.1, 0.4, (60, 60, 60))
        elif kind == "lamp":
            tilt = math.radians(ang)
            top = (px + math.sin(tilt) * ph, math.cos(tilt) * ph, -py)
            beam(mb, (px, 0, -py), top, 0.08, col)
            mb.box(top[0] - 0.3, top[1] - 0.15, top[2] - 0.2, top[0] + 0.3, top[1], top[2] + 0.2, (60, 60, 64))
            mb.cylinder(px, 0, -py, 0.25, 0.4, (130, 130, 128), seg=6)
        elif kind == "container":
            mb.box2d(px, py, pw, pd, 0.1, ph, col, top=_mul(col, 0.85))
            for k in range(int(max(pw, pd) / 0.4)):
                if pw >= pd:
                    mb.box2d(px + k * 0.4, py - 0.03, 0.06, pd + 0.06, 0.15, ph - 0.1, _mul(col, 0.8))
                else:
                    mb.box2d(px - 0.03, py + k * 0.4, pw + 0.06, 0.06, 0.15, ph - 0.1, _mul(col, 0.8))
            mb.box2d(px + 0.2, py + 0.2, pw * 0.3, pd * 0.3, ph - 0.02, ph + 0.02, (130, 75, 40))
        elif kind == "barrier":
            for bx in (px, px + pw):
                mb.box2d(bx - 0.1, py - 0.1, 0.2, 0.2, 0, ph, (200, 200, 200))
            n = 8
            for k in range(n):
                t0, t1 = k / n, (k + 1) / n
                sag = 0.15 * math.sin(math.pi * (t0 + t1) / 2)
                beam(mb, (px + t0 * pw, ph - 0.1 - sag, -py), (px + t1 * pw, ph - 0.1 - sag, -py), 0.05,
                     col if k % 2 == 0 else (240, 240, 235))
        elif kind == "caravan":
            cx, cy = px + pw / 2, py + pd / 2
            obox(mb, cx, cy, ang, pw, pd, 0.45, ph, col, top=(200, 196, 180))
            obox(mb, cx, cy, ang, pw + 0.02, pd + 0.02, 0.9, 1.2, (150, 110, 60))          # полоса
            ca, sa = math.cos(ang), math.sin(ang)
            for k in (-1.8, 0.3, 1.9):
                obox(mb, cx + ca * k - sa * (pd / 2), cy + sa * k + ca * (pd / 2), ang, 0.9, 0.06, 1.3, 1.9,
                     (40, 50, 60))
            for k in (-0.5, 0.5):
                obox(mb, cx + ca * k, cy + sa * k, ang, 0.2, pd + 0.1, 0.0, 0.5, (25, 25, 25))   # колёса (спущены)
            obox(mb, cx + ca * (pw / 2 + 0.8), cy + sa * (pw / 2 + 0.8), ang, 1.6, 0.1, 0.35, 0.45, (90, 90, 90))
        elif kind == "shelter":
            for bx in (px, px + pw):
                mb.box2d(bx - 0.05, py, 0.1, 0.1, 0, ph, (90, 100, 110))
                mb.box2d(bx - 0.05, py + pd, 0.1, 0.1, 0, ph, (90, 100, 110))
            mb.box2d(px - 0.2, py - 0.2, pw + 0.4, pd + 0.4, ph, ph + 0.12, _mul(col, 0.8))
            mb.box2d(px, py + pd, pw * 0.45, 0.05, 0.3, ph - 0.2, (120, 150, 160))          # уцелевшее стекло
            mb.box2d(px + 0.3, py + pd - 0.5, pw - 0.6, 0.4, 0.45, 0.5, (100, 80, 60))       # лавка
        elif kind == "tires":
            n = max(1, int(ph / 0.2))
            for k in range(n):
                mb.cylinder(px + r.uniform(-0.05, 0.05), 0.02 + k * 0.2, -py + r.uniform(-0.05, 0.05), 0.33, 0.18,
                            (24, 24, 24), seg=10)
        elif kind == "drum":
            if r.random() < 0.3:   # опрокинута
                beam(mb, (px - 0.45, 0.3, -py), (px + 0.45, 0.3, -py), 0.28, col)
            else:
                mb.cylinder(px, 0, -py, 0.29, ph, col, seg=10)
                for hh in (0.3, 0.6):
                    mb.cylinder(px, hh, -py, 0.3, 0.03, _mul(col, 0.7), seg=10, cap=False)
                mb.cylinder(px, ph - 0.01, -py, 0.2, 0.02, (120, 70, 40), seg=8)
        elif kind == "fence":
            lean = math.radians(ang)
            mb.box2d(px, py - 0.05, 0.08, 0.1, 0, ph, (90, 90, 88))
            top = ph * math.cos(lean)
            dz = ph * math.sin(lean)
            mb.poly([(px, 0.1, -py), (px + pw, 0.1, -py), (px + pw, top, -py - dz), (px, top, -py - dz)],
                    (120, 122, 118, 150), (0, 0, 1))
        elif kind == "trailer":
            cx, cy = px + pw / 2, py + pd / 2
            obox(mb, cx, cy, ang, pw, pd, 1.2, ph, col, top=_mul(col, 0.9))
            obox(mb, cx, cy, ang, pw + 0.02, pd + 0.02, 2.2, 2.7, r.choice([(170, 40, 30), (40, 70, 140)]))
            ca, sa = math.cos(ang), math.sin(ang)
            for k in (pw / 2 - 1.5, pw / 2 - 2.8):
                obox(mb, cx + ca * k, cy + sa * k, ang, 0.9, pd - 0.1, 0.1, 1.05, (24, 24, 24))
            obox(mb, cx - ca * (pw / 2 - 2.5), cy - sa * (pw / 2 - 2.5), ang, 0.2, pd - 0.3, 0.0, 1.2, (80, 80, 80))
            obox(mb, cx + ca * 0.5, cy + sa * 0.5, ang, pw * 0.5, 0.05 + pd, 1.5, 2.0, (150, 80, 45))   # ржавчина
        elif kind == "ramp":
            mb.box2d(px, py, pw, pd, 0, ph, (130, 128, 122), top=(115, 113, 108))
            mb.box2d(px - 0.05, py, 0.1, pd, ph - 0.2, ph, YELLOW)
        elif kind == "pallets":
            n = max(1, int(ph / 0.15))
            for k in range(n):
                obox(mb, px, py, ang + r.uniform(-0.1, 0.1), pw, pd, k * 0.15, k * 0.15 + 0.13, _mul(col, r.uniform(0.8, 1.05)))
        elif kind == "forklift":
            cx, cy = px, py
            obox(mb, cx, cy, ang, pw, pd, 0.3, 1.2, col)
            ca, sa = math.cos(ang), math.sin(ang)
            obox(mb, cx + ca * 1.25, cy + sa * 1.25, ang, 0.15, pd, 0.0, 2.4, (50, 50, 50))           # мачта
            obox(mb, cx + ca * 1.7, cy + sa * 1.7, ang, 0.9, 0.5, 0.05, 0.12, (60, 60, 60))           # вилы
            obox(mb, cx - ca * 0.2, cy - sa * 0.2, ang, 1.1, pd, 2.0, 2.1, (40, 40, 40))              # крыша
            for k in (-0.6, 0.3):
                obox(mb, cx + ca * k, cy + sa * k, ang, 0.08, pd - 0.1, 1.2, 2.0, (40, 40, 40))
            for k in (-0.6, 0.6):
                obox(mb, cx + ca * k, cy + sa * k, ang, 0.5, pd + 0.1, 0.0, 0.5, (22, 22, 22))
        elif kind == "weed":
            # сухой бурьян торчит из-под снега: пучок тонких стеблей
            for k in range(6):
                bx, by = px + r.uniform(-pw / 3, pw / 3), py + r.uniform(-pw / 3, pw / 3)
                hh = ph * r.uniform(0.8, 1.9) + 0.15
                tx, ty = bx + r.uniform(-0.15, 0.15), by + r.uniform(-0.15, 0.15)
                beam(mb, (bx, 0.05, -by), (tx, hh, -ty), 0.012, r.choice([(128, 108, 66), (104, 90, 56), (84, 74, 48)]))
        elif kind == "crack":
            obox(mb, px, py, ang, pw, pd, 0.063, 0.068, col)

    # -------------------------------------------------------------- Weber
    def build_dealer(self, rng):
        mb = MeshBuilder()
        gnd = MeshBuilder(uv_tile=5.0)
        x, y, w, h = DEALER_LOT
        gnd.flat2d(x, y, w, h, 0.06, (104, 104, 108))
        sx, sy, sw, sh = DEALER_SELL
        gnd.flat2d(sx, sy, sw, sh, 0.061, (96, 98, 104))
        for fx, fy, fw, fh in ((sx, sy, sw, 0.25), (sx, sy + sh - 0.25, sw, 0.25), (sx, sy, 0.25, sh),
                               (sx + sw - 0.25, sy, 0.25, sh)):
            mb.flat2d(fx, fy, fw, fh, 0.066, YELLOW)
        # флажки-гирлянды между столбами по периметру
        posts = [(x + k * 9, y + 0.3) for k in range(7)] + [(x + 0.3, y + h - 0.3), (x + 27, y + h - 0.3)]
        for px, py in posts:
            mb.cylinder(px, 0, -py, 0.06, 4.2, (210, 210, 210), seg=6)
        cols = [(200, 30, 30), (240, 240, 240), (30, 80, 170), (240, 200, 30)]
        for k in range(6):
            x0, x1 = x + k * 9, x + (k + 1) * 9
            n = 12
            for i in range(n):
                t0, t1 = i / n, (i + 1) / n
                s0 = 4.0 - 0.7 * math.sin(math.pi * t0)
                s1 = 4.0 - 0.7 * math.sin(math.pi * t1)
                ax, bx = x0 + (x1 - x0) * t0, x0 + (x1 - x0) * t1
                mb.poly([(ax, s0, -y - 0.3), (bx, s1, -y - 0.3), ((ax + bx) / 2, (s0 + s1) / 2 - 0.45, -y - 0.3)],
                        cols[(i + k) % 4], (0, 0, 1))
        # большой щит у дороги
        mb.box2d(x + 2, y - 0.8, 0.2, 0.2, 0, 5.2, (120, 120, 125))
        mb.box2d(x + 9.8, y - 0.8, 0.2, 0.2, 0, 5.2, (120, 120, 125))
        mb.box2d(x + 1.5, y - 0.85, 9.0, 0.1, 3.2, 5.2, (40, 90, 150))
        self.surface.append(board(T("АВТОПЛОЩАДКА ВЕБЕРА"), (x + 6, 4.55, -(y - 0.85) + 0.07), 180, 16,
                                  (250, 250, 240), (40, 90, 150)))
        self.surface.append(board(T("Покупка и продажа · наличные · экспорт"), (x + 6, 3.7, -(y - 0.85) + 0.07), 180, 9,
                                  (40, 40, 40), (240, 200, 40)))
        # табличка «Ankauf» у площадки приёма
        mb.cylinder(sx + sw / 2, 0, -(sy - 0.6), 0.05, 2.6, (150, 150, 150), seg=6)
        self.surface.append(board(T("СКУПКА — ставьте машину сюда"), (sx + sw / 2, 2.3, -(sy - 0.6) + 0.06), 180, 8,
                                  (20, 20, 20), YELLOW))
        # разметка мест продажи
        for bx, by, ba in self._dealer_spots():
            for side in (-1.55, 1.55):
                mb.flat2d(bx + side - 0.05, by - 2.4, 0.1, 4.8, 0.065, WHITE)
        self.surface.append(mesh_group(gnd, "places_gnd", texture=textures3d.detail(), double_sided=True))
        self.surface.append(mesh_group(mb, "places", double_sided=True))

    @staticmethod
    def _dealer_spots():
        from places import DEALER_SPOTS
        return DEALER_SPOTS

    def update_price_tags(self, g):
        """Ценники над машинами на площадке Weber (только рядом с игроком)."""
        near = abs(g.p.x - (DEALER_LOT[0] + 27)) < 90 and abs(g.p.y - (DEALER_LOT[1] + 18)) < 90
        stock = g.dealer["stock"] if near else {}
        for k in list(self.price_tags):
            if k not in stock or self.price_tags[k][1] != stock[k]:
                from ursina import destroy
                destroy(self.price_tags[k][0])
                del self.price_tags[k]
        for k, price in stock.items():
            car = g.cars.get(k)
            if car is None:
                continue
            if k not in self.price_tags:
                e = Entity(position=(car.x, 2.05, -car.y))
                e.setLightOff()
                Entity(parent=e, model="quad", scale=(1.3, 0.42), color=color.rgb(250, 240, 90))
                Text(f"{price:.0f} ₽", parent=e, scale=11, origin=(0, 0), color=color.rgb(20, 20, 20), z=-0.01)
                e2 = Entity(parent=e, rotation_y=180)
                Entity(parent=e2, model="quad", scale=(1.3, 0.42), color=color.rgb(250, 240, 90))
                Text(f"{price:.0f} ₽", parent=e2, scale=11, origin=(0, 0), color=color.rgb(20, 20, 20), z=-0.01)
                self.price_tags[k] = (e, price)
            e = self.price_tags[k][0]
            e.position = (car.x, 2.05, -car.y)
            e.rotation_y = 90 + math.degrees(car.angle)

    # -------------------------------------------------------------- свалка (новые ряды)
    def build_junk_extra(self, rng):
        mb = MeshBuilder()
        jx, jy, jw, jh = JUNKYARD
        # грязная колея между рядами доноров
        for ly in (397.0, 411.5, 425.0):
            mb.flat2d(jx + 2, ly - 2.2, jw - 10, 4.4, 0.058, (96, 88, 76))
        # моторы на поддонах, стопки дверей и капотов, коробки с мелочью
        for k in range(5):
            fake = dict(x=443 + k * 1.3, y=371.5, slot="engine" if k % 2 == 0 else "gearbox", id="x", rot=0.0)
            part_mesh(mb, fake)
        for k in range(4):
            col = rng.choice([(150, 40, 35), (196, 186, 150), (70, 110, 150), (110, 120, 90), (200, 200, 195)])
            obox(mb, 386.5, 432.0 - 3.5 + k * 0.02, 0.0, 1.1, 0.12, 0.0, 1.05 - k * 0.05, col)
        for k in range(6):
            col = rng.choice([(150, 40, 35), (196, 186, 150), (70, 110, 150), (230, 230, 220)])
            mb.box2d(430 + k * 1.6, 429.0, 1.3, 1.1, 0.0 + 0.0, 0.05 + 0.06 * (k % 3 + 1), col)
        self.surface.append(mesh_group(mb, "junk_extra", double_sided=True))
        self.surface.append(board(T("Запчасти — снимайте сами"), (jx + 40, 2.6, -(jy + 44)), 180, 9,
                                  (20, 20, 20), (240, 200, 40)))

    # -------------------------------------------------------------- подземный уровень
    def build_level(self, L):
        rng = random.Random(L["id"] + "3d")
        x0, y0, w, h = L["rect"]
        style = L["style"]
        H = HEIGHTS[style]
        floor_c, wall_c, stripe_c, ceil_c = PALETTE[style]
        lamps_ok = [(lx, ly, 1.0 if st == "ok" else 0.45) for lx, ly, st in L["lamps"] if st != "broken"]

        dim = {"modern": 1.0, "modern_low": 0.85, "old": 0.85, "bunker": 0.8}[style]

        def light(x, y):
            v = 0.15
            for lx, ly, k in lamps_ok:
                d2 = (x - lx) ** 2 + (y - ly) ** 2
                if d2 < 120:
                    v += 0.75 * k * dim * math.exp(-d2 / 16.0)
            return min(1.0, v)

        def lit(c, x, y, k=1.0):
            return _mul(c, light(x, y) * k)

        mb = MeshBuilder(uv_tile=3.0)
        # пол плитками по 2 м — у каждой своё освещение и немного разный оттенок
        step = 2.0
        yy = y0
        while yy < y0 + h - 0.01:
            xx = x0
            hh = min(step, y0 + h - yy)
            while xx < x0 + w - 0.01:
                ww = min(step, x0 + w - xx)
                c = _mul(floor_c, rng.uniform(0.97, 1.02))
                mb.flat2d(xx, yy, ww, hh, 0.0, lit(c, xx + ww / 2, yy + hh / 2))
                xx += step
            yy += step
        # потолок
        yy = y0
        while yy < y0 + h - 0.01:
            xx = x0
            hh = min(4.0, y0 + h - yy)
            while xx < x0 + w - 0.01:
                ww = min(4.0, x0 + w - xx)
                c = lit(ceil_c, xx + ww / 2, yy + hh / 2, 0.85)
                mb.poly([(xx, H, -yy), (xx + ww, H, -yy), (xx + ww, H, -(yy + hh)), (xx, H, -(yy + hh))], c, (0, -1, 0))
                xx += 4.0
            yy += 4.0
        # разметка: полосы мест, стрелки в проездах, пятна масла
        for bx, by, ba, tag in L["bays"]:
            ca, sa = math.cos(ba), math.sin(ba)
            for side in (-1.25, 1.25):
                px, py = bx - sa * side, by + ca * side
                obox(mb, px, py, ba, 4.6, 0.1, 0.004, 0.008, lit(WHITE if style != "old" else YELLOW, px, py, 0.9))
            if rng.random() < 0.35:
                obox(mb, bx + rng.uniform(-0.4, 0.4), by + rng.uniform(-0.8, 0.8), rng.uniform(0, 3), rng.uniform(0.5, 1.2),
                     rng.uniform(0.4, 0.9), 0.006, 0.009, lit((40, 38, 36), bx, by))
        for band in ("aisleA", "aisleB", "aisleC"):
            b0, b1 = L["bands"][band]
            cy = (b0 + b1) / 2
            for ax in range(int(x0 + 10), int(x0 + w - 8), 14):
                d = 1 if band != "aisleB" else -1
                obox(mb, ax, cy, 0.0, 1.6, 0.25, 0.004, 0.009, lit(WHITE, ax, cy, 0.8))
                obox(mb, ax + d * 0.9, cy - 0.25, d * 0.7, 0.7, 0.18, 0.004, 0.009, lit(WHITE, ax, cy, 0.8))
                obox(mb, ax + d * 0.9, cy + 0.25, -d * 0.7, 0.7, 0.18, 0.004, 0.009, lit(WHITE, ax, cy, 0.8))
        # стены периметра с цветной полосой и потёками
        walls = [(x0 - 0.5, y0 - 0.5, w + 1, 0.5), (x0 - 0.5, y0 + h, w + 1, 0.5), (x0 - 0.5, y0, 0.5, h), (x0 + w, y0, 0.5, h)]
        seg = 3.0
        for wx, wy, ww, wh in walls:
            along = ww > wh
            n = max(1, int((ww if along else wh) / seg))
            for k in range(n):
                if along:
                    sx, sy, sw, sh = wx + k * ww / n, wy, ww / n, wh
                else:
                    sx, sy, sw, sh = wx, wy + k * wh / n, ww, wh / n
                cx, cy = sx + sw / 2, sy + sh / 2
                cxi = min(max(cx, x0 + 0.5), x0 + w - 0.5)
                cyi = min(max(cy, y0 + 0.5), y0 + h - 0.5)
                mb.box2d(sx, sy, sw, sh, 0, H, lit(wall_c, cxi, cyi, rng.uniform(0.9, 1.0)))
                mb.box2d(sx - 0.01, sy - 0.01, sw + 0.02, sh + 0.02, 0.9, 1.25, lit(stripe_c, cxi, cyi))
                mb.box2d(sx - 0.012, sy - 0.012, sw + 0.024, sh + 0.024, 0.0, 0.25, lit((60, 60, 60), cxi, cyi))
                if rng.random() < 0.35:     # потёк воды/ржавчины
                    if along:
                        px = sx + rng.uniform(0, sw - 0.3)
                        mb.box2d(px, sy - 0.015, rng.uniform(0.1, 0.35), sh + 0.03, rng.uniform(0.3, 1.4), H,
                                 lit((105, 85, 60), cxi, cyi))
                    else:
                        py = sy + rng.uniform(0, sh - 0.3)
                        mb.box2d(sx - 0.015, py, sw + 0.03, rng.uniform(0.1, 0.35), rng.uniform(0.3, 1.4), H,
                                 lit((105, 85, 60), cxi, cyi))
        # колонны с жёлто-чёрной разметкой и буквой ряда
        for i, (px, py, pw, ph) in enumerate(L["pillars"]):
            cx, cy = px + pw / 2, py + ph / 2
            mb.box2d(px, py, pw, ph, 0, H, lit(_mul(wall_c, 0.95), cx, cy))
            for k in range(4):
                mb.box2d(px - 0.01, py - 0.01, pw + 0.02, ph + 0.02, k * 0.2, k * 0.2 + 0.2,
                         lit(YELLOW if k % 2 == 0 else BLACK, cx, cy))
            if style in ("old", "bunker") and rng.random() < 0.3:     # отбитый угол, торчит арматура
                mb.box2d(px - 0.05, py - 0.05, 0.2, 0.2, 0.6, 1.3, lit((70, 60, 50), cx, cy))
        # балки и трубы под потолком
        for bx in range(int(x0 + 6), int(x0 + w), 8):
            mb.box2d(bx - 0.2, y0, 0.4, h, H - 0.45, H, lit(_mul(ceil_c, 0.9), bx, y0 + h / 2, 0.8))
        for k, (py, col, r_) in enumerate(((y0 + 5.3, (190, 40, 30), 0.09), (y0 + 5.8, (70, 110, 70), 0.06),
                                           (y0 + 42.6, (200, 200, 200), 0.13))):
            mb.box(x0, H - 0.6 - k * 0.1, -py - r_, x0 + w, H - 0.6 - k * 0.1 + 2 * r_, -py + r_, lit(col, x0 + w / 2, py, 0.7))
        # лампы: корпуса (рабочие светятся — отдельный меш без освещения)
        glow_on = MeshBuilder()
        glow_fl = MeshBuilder()
        pools = MeshBuilder()
        for lx, ly, st in L["lamps"]:
            mb.box(lx - 0.7, H - 0.12, -ly - 0.12, lx + 0.7, H - 0.02, -ly + 0.12, lit((80, 80, 82), lx, ly))
            if st == "broken":
                mb.box(lx - 0.2, 0.0, -ly - 0.15, lx + 0.1, 0.03, -ly + 0.1, lit((150, 160, 165), lx, ly))   # осколки
                continue
            tgt = glow_on if st == "ok" else glow_fl
            tgt.box(lx - 0.65, H - 0.15, -ly - 0.08, lx + 0.65, H - 0.1, -ly + 0.08,
                    (240, 245, 235) if style.startswith("modern") else (255, 225, 160))
            r = 4.5
            pools.poly([(lx - r, 0.02, -ly - r), (lx + r, 0.02, -ly - r), (lx + r, 0.02, -ly + r), (lx - r, 0.02, -ly + r)],
                       (255, 240, 210, 50 if st == "ok" else 25), (0, 1, 0), uvs=[(0, 0), (1, 0), (1, 1), (0, 1)])
        # помещения: стены с проёмами (из solids), содержимое
        for room in L["rooms"]:
            rx, ry, rw, rh = room["rect"]
            dx, dy = room["door"]
            k = room["kind"]
            rc = {"Treppenhaus": (170, 170, 160), "Technikraum": (140, 140, 150), "Kellerabteile": (150, 145, 135),
                  "Waschbox": (120, 160, 190), "Lager": (150, 140, 120), "Eingestürzt": (110, 105, 95),
                  "Schutzraum": (110, 125, 105)}[k]
            if k == "Waschbox":        # кафель и шланг
                for tx in range(int(rx + 0.5), int(rx + rw - 0.5)):
                    mb.box2d(tx, ry + rh - 0.2, 0.95, 0.05, 0.1, 2.0, lit((150, 190, 215), tx, ry + rh - 1))
                mb.flat2d(rx + 1, ry + 1, rw - 2, rh - 2, 0.01, lit((70, 90, 100), rx + rw / 2, ry + rh / 2))
                mb.cylinder(rx + rw / 2, 1.2, -(ry + rh - 0.5), 0.2, 0.08, lit((30, 30, 30), rx + rw / 2, ry + rh - 1), seg=8)
            if k == "Treppenhaus":     # лестница наверх
                for s_ in range(8):
                    mb.box2d(rx + 1, ry + rh - 1.5 - s_ * 0.3, 2.2, 0.3, 0, 0.18 * (s_ + 1),
                             lit((150, 150, 145), rx + 2, ry + rh - 2))
                mb.box2d(rx + 3.4, ry + 1.2, 0.05, rh - 2, 0.0, 1.0, lit((120, 120, 120), rx + 3.4, ry + rh / 2))
            if "cages" in room:        # клетки из сетки
                cx_, cy_, cw_, ch_, cn = room["cages"]
                mb.box2d(cx_, cy_ - 0.02, cw_, 0.04, 0.0, 2.1, (120, 122, 118, 110))
                for c in range(cn):
                    for obj in range(rng.randint(0, 3)):
                        ox = cx_ + c * 2.6 + rng.uniform(0.3, 2.0)
                        oy = cy_ + rng.uniform(0.3, 2.4)
                        mb.box2d(ox, oy, rng.uniform(0.3, 0.6), rng.uniform(0.3, 0.6), 0, rng.uniform(0.3, 1.0),
                                 lit(rng.choice([(150, 120, 80), (90, 90, 95), (160, 60, 50), (60, 90, 120)]), ox, oy))
            if "racks" in room:
                x_, y_, w_, h_ = room["racks"]
                for lvl in (0.05, 0.75, 1.45):
                    mb.box2d(x_, y_, w_, h_, lvl, lvl + 0.05, lit((100, 90, 70), x_ + w_ / 2, y_))
                    for bx in range(int(x_), int(x_ + w_ - 0.6), 1):
                        if rng.random() < 0.6:
                            mb.box2d(bx + 0.1, y_ + 0.05, 0.7, h_ - 0.1, lvl + 0.05, lvl + rng.uniform(0.3, 0.6),
                                     lit(rng.choice([(170, 140, 90), (90, 90, 90), (140, 40, 30)]), bx, y_))
                for bx in (x_, x_ + w_ - 0.08):
                    mb.box2d(bx, y_, 0.08, h_, 0, 2.1, lit((60, 80, 140), bx, y_))
            if "cabinets" in room:
                x_, y_, w_, h_ = room["cabinets"]
                n = max(1, int(w_ / 0.9))
                for c in range(n):
                    cx_ = x_ + c * w_ / n
                    mb.box2d(cx_ + 0.03, y_, w_ / n - 0.06, h_, 0, 2.0, lit((150, 155, 150), cx_, y_ + 1))
                    mb.box2d(cx_ + 0.3, y_ + h_ - 0.01, 0.15, 0.02, 1.4, 1.55, (230, 190, 30))
            if "rubble" in room:       # обрушившаяся плита перекрытия и обломки
                x_, y_, w_, h_ = room["rubble"]
                for _ in range(22):
                    bx, by = rng.uniform(x_, x_ + w_ - 1), rng.uniform(y_, y_ + h_ - 1)
                    obox(mb, bx + 0.5, by + 0.5, rng.uniform(0, 3), rng.uniform(0.6, 2.0), rng.uniform(0.5, 1.5), 0,
                         rng.uniform(0.3, 1.6), lit((125, 120, 110), bx, by, rng.uniform(0.8, 1.1)))
                p0 = (x_ + 0.5, 0.2, -(y_ + h_ / 2))
                beam(mb, p0, (x_ + w_ - 0.5, H - 0.1, -(y_ + h_ / 2)), 0.25, lit((140, 135, 125), x_ + w_ / 2, y_ + h_ / 2))
                for _ in range(5):   # арматура
                    ax, ay = rng.uniform(x_, x_ + w_), rng.uniform(y_, y_ + h_)
                    beam(mb, (ax, 0.8, -ay), (ax + rng.uniform(-0.6, 0.6), 2.0, -ay + rng.uniform(-0.6, 0.6)), 0.02,
                         (110, 60, 35))
            if "bunker_door" in room:  # гермодверь, приоткрыта
                bx, by = room["bunker_door"]
                mb.box(bx - 0.9, 0.0, -by - 0.02, bx + 0.9, 2.1, -by + 0.25, lit((95, 110, 90), bx, by - 1))
                mb.cylinder(bx - 0.4, 1.1, -by + 0.3, 0.25, 0.05, lit((150, 40, 30), bx, by - 1), seg=10)
            # «пол» комнаты чуть другого цвета
            mb.flat2d(rx + 0.2, ry + 0.3, rw - 0.4, rh - 0.5, 0.003, lit(_mul(rc, 0.7), rx + rw / 2, ry + rh / 2, 0.8))
        # все стенки комнат и перегородки из solids (кроме колонн и периметра)
        pill = set(L["pillars"])
        for s_ in self.pl.interior_solids:
            sx, sy, sw, sh = s_
            if s_ in pill or not (x0 <= sx + sw / 2 <= x0 + w and y0 <= sy + sh / 2 <= y0 + h):
                continue
            if sy >= L["bands"]["rooms"][0] - 0.01 and (sw < 0.1 or sh < 0.1):
                continue                                    # сетки клеток — выше
            special = any(s_ == room.get(kk) for room in L["rooms"] for kk in ("racks", "cabinets", "rubble"))
            if special:
                continue
            cx, cy = sx + sw / 2, sy + sh / 2
            mb.box2d(sx, sy, sw, sh, 0, H, lit(_mul(wall_c, 0.92), cx, max(cy - 1, y0)))
            mb.box2d(sx - 0.01, sy - 0.01, sw + 0.02, sh + 0.02, 0.9, 1.25, lit(stripe_c, cx, max(cy - 1, y0)))
        # лужи (блестят), мусор
        pud = MeshBuilder()
        for px, py, pw, ph in L["puddles"]:
            n = 7
            pts = [(px + math.cos(a) * pw / 2 * (0.8 + 0.2 * math.sin(a * 3 + px)),
                    py + math.sin(a) * ph / 2 * (0.8 + 0.2 * math.cos(a * 2 + py)))
                   for a in [i * 2 * math.pi / n for i in range(n)]]
            pud.poly([(x_, 0.012, -y_) for x_, y_ in pts], (30, 34, 38, 170), (0, 1, 0))
        for jx, jy, kind in L["junk"]:
            c = lit({"paper": (200, 195, 180), "box": (150, 120, 80), "can": (160, 40, 40), "tire": (25, 25, 25),
                     "bottle": (60, 110, 60)}[kind], jx, jy)
            if kind == "tire":
                mb.cylinder(jx, 0.0, -jy, 0.32, 0.2, c, seg=10)
            elif kind == "box":
                obox(mb, jx, jy, jx % 3, 0.5, 0.4, 0, 0.35, c)
            else:
                obox(mb, jx, jy, jy % 3, 0.25, 0.12, 0, 0.05, c)
        # пандусы: наклонная плоскость с разметкой, чёрный проход
        for kind, (rx, ry, rw, rh) in L.get("ramps", []):
            east = rx > x0 + w / 2
            lo, hi = (rx, rx + rw) if east else (rx + rw, rx)
            rise = 1.1 if kind == "up" else -0.8
            mb.poly([(lo, 0.02, -ry), (hi, 0.02 + rise, -ry), (hi, 0.02 + rise, -(ry + rh)), (lo, 0.02, -(ry + rh))],
                    lit(_mul(floor_c, 0.9), rx + rw / 2, ry + rh / 2), (0, 1, 0))
            for k in range(int(rh / 0.6)):
                mb.box2d(lo - 0.1 if east else lo, ry + k * 0.6, 0.1, 0.6, 0.0, 0.08,
                         lit(YELLOW if k % 2 else BLACK, rx, ry))
            endx = rx + rw - 0.1 if east else rx
            mb.box2d(endx, ry, 0.1, rh, 0, H, (3, 3, 4))
        interior = Entity(model=mb.build(), texture=textures3d.detail(), double_sided=True)
        interior.setLightOff()
        pe = Entity(model=pud.build(), double_sided=True)
        pe.setLightOff()
        from city3d import additive
        on = Entity(model=glow_on.build(), double_sided=True)
        on.setLightOff()
        fl = Entity(model=glow_fl.build(), double_sided=True) if len(glow_fl) else None
        if fl:
            fl.setLightOff()
            self.flicker.append([fl, rng.random() * 3, L["id"]])
        pl_ = Entity(model=_mesh_uv(pools), texture=textures3d.glow(), double_sided=True)
        additive(pl_)
        self.interior += [interior, pe, on, pl_] + ([fl] if fl else [])
        # таблички
        name = T("{name}  ·  уровень {0}", '−1' if L['no'] == -1 else '−2', name=L['name'])
        self.interior.append(board(name, (x0 + 12, 1.9, -(y0 + 0.01) - 0.02), 180, 12, (245, 245, 240), (40, 60, 90)))
        for kind, (rx, ry, rw, rh) in L.get("ramps", []):
            east = rx > x0 + w / 2
            lab = (T("Выезд ↑") if L["no"] == -1 else T("Уровень −1 ↑")) if kind == "up" else T("Уровень −2 ↓")
            bxp = rx + rw + 1.2 if not east else rx - 1.2
            self.interior.append(board(lab, (bxp, H - 0.7, -(ry + rh / 2)), 90 if not east else -90, 12,
                                       (20, 20, 20), YELLOW))
            self.interior.append(board(lab, (bxp, H - 0.7, -(ry + rh / 2)), -90 if not east else 90, 12,
                                       (20, 20, 20), YELLOW))
        for room in L["rooms"]:
            dx, dy = room["door"]
            lab = {"Treppenhaus": T("Лестница · запасный выход"), "Technikraum": T("Техпомещение — вход запрещён"),
                   "Kellerabteile": T("Кладовки"), "Waschbox": T("Мойка"), "Lager": T("Склад"),
                   "Eingestürzt": T("ОПАСНО: ОБРУШЕНИЕ!"), "Schutzraum": T("Бомбоубежище")}[room["kind"]]
            bg = (30, 130, 70) if room["kind"] == "Treppenhaus" else (
                (200, 40, 30) if room["kind"] == "Eingestürzt" else (220, 220, 215))
            fg = (250, 250, 250) if bg != (220, 220, 215) else (30, 30, 30)
            self.interior.append(board(lab, (dx, 2.1, -dy + 0.02), 180, 8, fg, bg))
        for i, (px, py, pw, ph) in enumerate(L["pillars"]):
            if i % 2 == 0:
                lab = f"{'ABCDEFGH'[int(py - y0) // 17]}{i // 2 + 1}"
                self.interior.append(board(lab, (px + pw / 2, 1.6, -py + 0.02), 180, 10, (250, 250, 250), stripe_c))
                self.interior.append(board(lab, (px + pw / 2, 1.6, -(py + ph) - 0.02), 0, 10, (250, 250, 250), stripe_c))

    # -------------------------------------------------------------- обновление
    def set_under(self, under):
        if under == self._under:
            return
        self._under = under
        for e in self.interior:
            e.enabled = under
        for e in self.surface:
            e.enabled = not under
        if self.loose_e is not None:
            self.loose_e.enabled = True

    def set_visible(self, v):
        """Квартира: скрыть всё."""
        for e in self.interior + self.surface:
            e.enabled = v and (e in self.interior) == bool(self._under)
        if self.loose_e is not None:
            self.loose_e.enabled = v
        for e, _ in self.price_tags.values():
            e.enabled = v

    def update(self, dt, g):
        under = g.p.x >= INTERIOR_X
        self.set_under(under)
        L = g.world.level_at(g.p.x, g.p.y) if under else None
        lid = L["id"] if L else None
        if under and lid != self._level:
            # рисуем только тот уровень, где стоит игрок
            self._level = lid
            for k, ents in self.level_ents.items():
                for e in ents:
                    e.enabled = (k == lid) or lid is None
        if not under:
            self._level = None
        if under:
            for f in self.flicker:
                if f[2] != self._level:
                    continue
                f[1] -= dt
                if f[1] <= 0:
                    on = not f[0].enabled
                    f[0].enabled = on
                    f[1] = random.uniform(0.03, 0.25) if not on else random.uniform(0.1, 2.5)
        else:
            self.update_price_tags(g)
        sig = (len(g.loose), tuple(id(it) for it in g.loose[:3]), g.loose[-1]["x"] if g.loose else 0)
        if sig != self._loose_sig:
            self._loose_sig = sig
            from ursina import destroy
            if self.loose_e is not None:
                destroy(self.loose_e)
            mb = MeshBuilder()
            for it in g.loose:
                part_mesh(mb, it)
            self.loose_e = Entity(model=mb.build(), double_sided=True) if len(mb) else None


def _mesh_uv(mb):
    from ursina import Mesh
    return Mesh(vertices=mb.v, triangles=mb.t, colors=mb.c, normals=mb.n, uvs=mb.uv)
