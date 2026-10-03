"""Руки игрока в 3D (вид от первого лица): левая и правая, в каждой — модель того, что в ней лежит.

Руки прикреплены к камере. Анимации:
  * еда — рука подносит предмет ко рту, три «укуса», предмет становится короче, рука опускается;
  * питьё — рука поднимает бутылку/стакан ко рту и наклоняет его, несколько глотков;
В конце анимации вызывается game.eat_hand(рука) — там убывает предмет и растёт сытость/жажда.
"""
import math

from ursina import Entity, camera, color, Vec3, destroy

from mesh3d import MeshBuilder
from items import ITEMS

SKIN = (214, 170, 138)
SLEEVE = (58, 62, 72)
# камера: горизонтальный угол обзора 78° — при 16:9 по вертикали видно ±24°, поэтому руки чуть ниже центра
REST = {0: Vec3(-0.21, -0.175, 0.44), 1: Vec3(0.21, -0.175, 0.44)}
REST_ROT = {0: Vec3(0, 10, 0), 1: Vec3(0, -10, 0)}
MOUTH = {0: Vec3(-0.035, -0.115, 0.31), 1: Vec3(0.035, -0.115, 0.31)}          # еда — у рта, чуть ниже глаз
MOUTH_DRINK = {0: Vec3(-0.02, -0.06, 0.29), 1: Vec3(0.02, -0.06, 0.29)}       # бутылка — горлышком ко рту
LONG_FOOD = ("brot", "wurst", "doener")
BOTTLES = {"wasser": ((175, 205, 235), (40, 90, 170), (235, 235, 240)),
           "cola": ((70, 28, 22), (200, 30, 30), (200, 30, 30)),
           "bier": ((95, 60, 22), (230, 220, 190), (200, 180, 60))}


def _smooth(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def item_mesh(e, shown_cond=None):
    """Модель предмета в руке (локально: ладонь в начале координат, «вверх» — +y)."""
    pid = e["id"]
    it = ITEMS.get(pid, {})
    kind = it.get("kind")
    cond = e.get("cond", 100.0) if shown_cond is None else shown_cond
    left = max(0.25, min(1.0, cond / 100.0))
    mb = MeshBuilder()
    if pid in BOTTLES:
        glass, label, cap = BOTTLES[pid]
        mb.cylinder(0, -0.09, 0, 0.032, 0.17, glass, seg=10)
        mb.cylinder(0, -0.04, 0, 0.0335, 0.06, label, seg=10, cap=False)
        mb.cone(0, 0.08, 0, 0.032, 0.05, glass, seg=10)
        mb.cylinder(0, 0.12, 0, 0.012, 0.035, glass, seg=8)
        mb.cylinder(0, 0.15, 0, 0.014, 0.012, cap, seg=8)
    elif pid == "kaffee":
        mb.cylinder(0, -0.04, 0, 0.038, 0.1, (235, 232, 225), seg=10)
        mb.cylinder(0, 0.059, 0, 0.034, 0.002, (70, 40, 25), seg=10)
    elif pid == "brot":
        L = 0.2 * left
        mb.box(-0.045, -0.02, -L / 2, 0.045, 0.05, L / 2, (196, 146, 84), top=(160, 105, 55))
        mb.box(-0.04, -0.019, L / 2 - 0.002, 0.04, 0.045, L / 2 + 0.001, (235, 215, 170))     # срез мякиша
    elif pid == "wurst":
        L = 0.18 * left
        mb.box(-0.02, -0.01, -L / 2, 0.02, 0.03, L / 2, (150, 70, 45), top=(125, 55, 35))
    elif pid == "pizza_tk":
        mb.box(-0.13, -0.01, -0.13, 0.13, 0.02, 0.13, (200, 60, 40), top=(230, 230, 225))
    elif pid == "pizza_hot":
        r = 0.14 * (0.4 + 0.6 * left)
        mb.cylinder(0, 0.0, 0, r, 0.018, (225, 180, 110), seg=14)
        mb.cylinder(0, 0.018, 0, r * 0.85, 0.004, (200, 60, 35), seg=14)
    elif pid == "apfel":
        mb.blob(0, 0.03, 0, 0.04 * (0.6 + 0.4 * left), (190, 35, 30), shade=0.9)
        mb.box(-0.003, 0.065, -0.003, 0.003, 0.085, 0.003, (80, 60, 30))
    elif pid == "doener":
        L = 0.17 * left
        mb.box(-0.04, -0.03, -L / 2, 0.04, 0.04, L / 2, (215, 205, 170), top=(200, 150, 90))
        mb.box(-0.042, -0.035, -L / 2 - 0.01, 0.042, 0.045, 0.0, (205, 205, 210))              # фольга
    elif kind == "food":
        mb.box(-0.05, -0.02, -0.07 * left, 0.05, 0.04, 0.07 * left, (200, 150, 90))
    elif kind == "drink":
        mb.cylinder(0, -0.06, 0, 0.03, 0.15, (120, 160, 200), seg=10)
    elif pid == "key":                                   # ключ: пластиковая головка и лезвие
        mb.box(-0.016, -0.02, -0.006, 0.016, 0.014, 0.006, (35, 35, 38))
        mb.box(-0.004, 0.014, -0.002, 0.004, 0.06, 0.002, (200, 200, 205))
        mb.box(-0.002, 0.03, -0.0025, 0.005, 0.034, 0.0025, (170, 170, 175))       # бородка
    elif pid == "flyer":
        mb.box(-0.1, -0.005, -0.075, 0.1, 0.012, 0.075, (240, 240, 235), top=(245, 245, 240))
        mb.box(-0.09, 0.0125, 0.045, 0.09, 0.013, 0.07, (200, 30, 30))            # «GESTOHLEN!»
    elif pid == "toolbox":
        mb.box(-0.13, -0.24, -0.06, 0.13, -0.13, 0.06, (190, 35, 30), top=(150, 30, 25))      # несут за ручку
        mb.box(-0.05, -0.13, -0.01, 0.05, 0.0, 0.01, (30, 30, 30))                           # ручка
    elif pid == "multimeter":
        mb.box(-0.04, -0.01, -0.07, 0.04, 0.025, 0.07, (230, 190, 30), top=(40, 40, 40))
    elif pid == "rope":
        mb.cylinder(0, -0.03, 0, 0.09, 0.05, (200, 120, 40), seg=12)
    elif pid == "fuse_set":
        mb.box(-0.05, -0.01, -0.035, 0.05, 0.012, 0.035, (210, 210, 215), top=(200, 40, 40))
    elif kind == "fluid":
        col = {"oil": (220, 180, 40), "coolant": (60, 160, 70), "brake_fl": (230, 230, 230)}.get(pid, (200, 40, 30))
        mb.box(-0.08, -0.2, -0.04, 0.08, 0.04, 0.04, col)
        mb.box(-0.02, 0.04, -0.015, 0.02, 0.07, 0.015, (30, 30, 30))
    elif kind == "material":
        if pid == "metal":
            mb.box(-0.15, -0.2, -0.003, 0.15, 0.1, 0.003, (150, 152, 155))
        else:
            mb.cylinder(0, -0.08, 0, 0.033, 0.16, (200, 200, 60) if pid == "paint" else (90, 120, 160), seg=10)
    elif pid.startswith("tire") or pid.endswith("_tire"):
        mb.cylinder(0, -0.09, 0, 0.3, 0.17, (26, 26, 26), seg=14)
        mb.cylinder(0, -0.092, 0, 0.17, 0.175, (140, 140, 138), seg=12)
    else:
        big = it.get("price", 50) > 300
        s = 0.2 if big else 0.1
        mb.box(-s, -s * 1.2, -s * 0.8, s, s * 0.3, s * 0.8, (110, 112, 116), top=(80, 82, 86))
    return mb.build()


class Hand:
    def __init__(self, i):
        self.i = i
        self.piv = Entity(parent=camera, position=REST[i], rotation=REST_ROT[i])
        sg = -1 if i == 0 else 1
        Entity(parent=self.piv, model="cube", color=color.rgb(*SLEEVE), position=(sg * 0.02, -0.045, -0.22),
               scale=(0.1, 0.1, 0.34))
        Entity(parent=self.piv, model="cube", color=color.rgb(*SKIN), position=(0, -0.02, 0.0), scale=(0.075, 0.055, 0.1))
        Entity(parent=self.piv, model="cube", color=color.rgb(*SKIN), position=(-sg * 0.045, 0.005, 0.02),
               scale=(0.022, 0.03, 0.06))                                   # большой палец
        self.fist = Entity(parent=self.piv, model="cube", color=color.rgb(*SKIN), position=(0, 0.005, 0.045),
                           scale=(0.07, 0.035, 0.03))                       # сжатые пальцы (пустая рука)
        self.holder = Entity(parent=self.piv, position=(0, 0.03, 0.03))
        self.item = None
        self.sig = None

    def show(self, e, shown_cond=None):
        sig = (e["id"], round(e.get("cond", 0) if shown_cond is None else shown_cond)) if e else None
        if sig == self.sig:
            return
        self.sig = sig
        if self.item is not None:
            destroy(self.item)
            self.item = None
        self.fist.enabled = e is None
        if e:
            self.item = Entity(parent=self.holder, model=item_mesh(e, shown_cond), double_sided=True)
            if e["id"] in LONG_FOOD:                       # батон/колбасу держат поперёк, концом к центру
                self.item.rotation_y = (-1 if self.i == 0 else 1) * 70


class Hands3D:
    def __init__(self, game):
        self.g = game
        self.hands = [Hand(0), Hand(1)]
        self.anim = None
        self.visible = True
        self._bob = 0.0

    @property
    def busy(self):
        return self.anim is not None

    def play_key(self, i, kind, entry):
        """Движение рукой с ключом: "door" — повернуть ключ в двери, "ign_in"/"ign_out" — вставить/вынуть
        ключ из замка зажигания (в салоне руки видны на время движения)."""
        if self.anim:
            return False
        self.anim = {"i": i, "kind": kind, "t": 0.0, "dur": 0.9 if kind == "door" else 0.75, "entry": entry}
        return True

    def play(self, i, kind):
        """Запустить анимацию: kind — "eat" или "drink"."""
        e = self.g.p.hands[i]
        if self.anim or not e:
            return False
        dur = 1.9 if kind == "eat" else 2.2
        part = min(self.g.PORTION["food" if kind == "eat" else "drink"], e["cond"])
        self.anim = {"i": i, "kind": kind, "t": 0.0, "dur": dur, "entry": e, "c0": e["cond"], "c1": e["cond"] - part}
        return True

    def set_visible(self, v):
        if self.anim and self.anim["kind"].startswith(("door", "ign")):
            v = True                                     # ключом работаем и из машины
        if v != self.visible:
            self.visible = v
            for h in self.hands:
                h.piv.enabled = v
            if not v and self.anim:
                self._finish()

    def _finish(self):
        a = self.anim
        self.anim = None
        if a and a["kind"] in ("eat", "drink") and self.g.p.hands[a["i"]] is a["entry"]:
            self.g.eat_hand(a["i"])

    def update(self, dt, visible, walking=0.0):
        self.set_visible(visible)
        if not self.visible:                         # (движение с ключом видно и из машины)
            return
        self._bob += dt * (7.0 if walking else 1.2)
        a = self.anim
        for h in self.hands:
            i = h.i
            e = self.g.p.hands[i]
            pos = Vec3(REST[i])
            rot = Vec3(REST_ROT[i])
            pos.y += math.sin(self._bob + i * 1.3) * (0.012 if walking else 0.004)
            pos.x += math.cos(self._bob * 0.5 + i) * (0.006 if walking else 0.002)
            shown = None
            if a and a["i"] == i and a["kind"] in ("door", "ign_in", "ign_out"):
                t, dur = a["t"], a["dur"]
                u = _smooth(t / (dur * 0.4)) if t < dur * 0.6 else _smooth((dur - t) / (dur * 0.4))
                sg = -1 if i == 0 else 1
                tgt = Vec3(sg * 0.05, -0.2, 0.5) if a["kind"] == "door" else Vec3(0.13, -0.19, 0.4)
                pos = pos + (tgt - pos) * u
                turn = _smooth((t - dur * 0.35) / (dur * 0.25)) if a["kind"] != "ign_out" else 0.0
                if t > dur * 0.6:
                    turn = _smooth((dur - t) / (dur * 0.3)) if a["kind"] == "door" else turn
                rot = rot + (Vec3(-20, -sg * 15, sg * 70 * turn) - rot) * u
                # ключ в руке: при вставке — до середины движения, при извлечении — со второй половины
                show = a["entry"]
                if a["kind"] == "ign_in" and t > dur * 0.5:
                    show = None
                if a["kind"] == "ign_out" and t < dur * 0.45:
                    show = None
                h.show(show if a["kind"] != "door" else (e or a["entry"]))
                h.piv.position = pos
                h.piv.rotation = rot
                continue
            if a and a["i"] == i:
                t, dur = a["t"], a["dur"]
                up = _smooth(t / 0.45) if t < dur - 0.45 else _smooth((dur - t) / 0.45)
                sg = -1 if i == 0 else 1
                if a["kind"] == "eat":
                    tgt = MOUTH[i]
                    pos = pos + (tgt - pos) * up
                    rot = rot + (Vec3(-10, -sg * 20, sg * 6) - rot) * up
                    chew = t > 0.45 and t < dur - 0.45
                    if chew:
                        ph = (t - 0.45) / (dur - 0.9) * 3          # три укуса: рука чуть подаётся ко рту
                        pos.z += 0.03 * abs(math.sin(ph * math.pi))
                        shown = a["c0"] + (a["c1"] - a["c0"]) * min(1.0, ph / 3)
                    elif t >= dur - 0.45:
                        shown = a["c1"]
                else:
                    tgt = MOUTH_DRINK[i]
                    pos = pos + (tgt - pos) * up
                    tilt = _smooth((t - 0.3) / 0.6) if t < dur - 0.5 else _smooth((dur - t) / 0.5)
                    # донышко вверх, горлышко ко рту: ось бутылки смотрит на камеру и вниз
                    rot = rot + (Vec3(-40 * up - 78 * tilt, 0, sg * 4) - rot) * up
                    if 0.9 < t < dur - 0.6:
                        pos.y += 0.006 * math.sin((t - 0.9) * 14)   # глотки
                h.show(e, max(0.0, shown) if shown is not None and e else None)
            else:
                h.show(e)
            h.piv.position = pos
            h.piv.rotation = rot
        if a:
            a["t"] += dt
            if a["t"] >= a["dur"]:
                self._finish()
