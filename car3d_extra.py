"""3D-детали машины, с которыми можно взаимодействовать: двери на петлях, багажник, поворотники,
рабочие приборы, болты и гайки, мелкие детали салона/кузова/моторного отсека/багажника.

Подмешивается в Car3D (car3d.py). Геометрию берёт из self._geo (задают сборщики кузова)
и из self._interior. Точки для взаимодействия прицелом — targets().
"""
import math

from panda3d.core import TransparencyAttrib
from ursina import Entity, color, Vec3, destroy, scene

from mesh3d import MeshBuilder, textured_copy
import textures3d
import fasteners as fast
import electrics as elec
import underside as _under
import under3d as _under3d

def _gauge_mesh():
    """Круглый корпус прибора (цилиндр; встроенной модели «cylinder» в Ursina нет). Свой на каждый прибор."""
    from ursina import Cylinder
    return Cylinder(resolution=12, radius=0.5, height=1.0, start=-0.5)

AMBER_ON, AMBER_OFF = (255, 150, 20), (120, 70, 25)


def _clip(poly, y, keep_below):
    """Отрезать многоугольник горизонтальной линией (Сазерленд — Ходжман)."""
    out = []
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        ina = a[1] <= y if keep_below else a[1] >= y
        inb = b[1] <= y if keep_below else b[1] >= y
        if ina:
            out.append(a)
        if ina != inb:
            t = (y - a[1]) / (b[1] - a[1])
            out.append((a[0] + (b[0] - a[0]) * t, y))
    return out


class Extras:
    bolt_ents = None
    door_piv = {}
    tail_piv = None
    signals = {}
    stalks = {}
    gauges = None
    dash_arrows = {}
    _door_ang = {"l": 0.0, "r": 0.0}
    _tail_ang = 0.0
    _blink_on = None
    live = False
    _gauge_ents = []
    fusebox = None
    fault_ents = {}

    # ================================================================== сборка
    def _build_extras(self):
        g = getattr(self, "_geo", None)
        if not g:
            return
        self.door_piv = {}
        self._door_ang = {"l": 0.0, "r": 0.0}
        self._tail_ang = 0.0
        self._build_doors()
        self._build_tail()
        self._build_details()          # в т.ч. стёкла поворотников (статично)
        self._build_mirror_glass()     # по одному стеклу на каждое зеркало (левое, правое, салонное)
        self.live = False              # приборы/переключатели/мигающие лампы — только у машины игрока
        self.kit = {}
        if self.car.model == "mustang":
            self._build_mustang_kit()
        self.bolt_ents = None            # создаются, когда игрок рядом (ensure_bolts)
        self._build_knobs()
        for e in [getattr(self, "tail_piv", None)] + [d for d in getattr(self, "details", [])] + \
                [x for v in self.door_piv.values() for x in v[:3]]:
            if e is not None:
                stack = [e]
                while stack:
                    q = stack.pop()
                    q.ignore = True                 # статичные — движок не опрашивает их каждый кадр
                    stack.extend(q.children)

    def ensure_live(self, on):
        """Приборы, подрулевые переключатели и мигающие поворотники — только у машины, которой пользуется игрок."""
        if on and not self.live and getattr(self, "_geo", None):
            self.live = True
            self._build_signals()
            self._build_gauges()
            self._build_ignition()
            self._blink_on = None
        elif not on and self.live:
            self.live = False
            for e in [x for v in self.signals.values() for x in v] + list(self.stalks.values()) + \
                    list(self.dash_arrows.values()) + getattr(self, "_gauge_ents", []) + \
                    [x for x in (getattr(self, "ign", None), getattr(self, "ign_key", None)) if x is not None]:
                destroy(e)
            self.ign = self.ign_key = None
            self.signals, self.stalks, self.dash_arrows, self.gauges, self._gauge_ents = {}, {}, {}, None, []

    # ---------------------------------------------------------------- двери
    def _build_doors(self):
        """Все двери (передние и задние) по контурам из текстуры борта. У каждой: наружная панель со стеклом
        (видна, когда дверь открыта) и дверная карта (видна всегда — одна и та же, без «упрощённой» замены)."""
        car, g, Z = self.car, self._geo, self.Z
        W2, belt = g["W2"], g["belt"]
        paint = car.paint if car.color else (196, 186, 150)
        trim = tuple(int(c * 0.8) for c in g.get("seat_c", (90, 70, 60)))
        dark_t = tuple(int(c * 0.62) for c in trim)
        self.door_piv = {}
        self._door_ang = {}
        for side, sg in (("l", -1), ("r", 1)):
            polys = sorted(getattr(car, "_door_polys", {}).get(side) or [],
                           key=lambda p_: -sum(x for x, _ in p_) / len(p_))
            for idx, poly in enumerate(polys):
                key = side if idx == 0 else side + "b"
                fx = max(p[0] for p in poly)
                rx = min(p[0] for p in poly)
                col = paint
                if car.model == "vaz2102" and side == "l" and car.odd_door and idx == 0:
                    col = (150, 72, 52)             # дверь с разборки другого цвета
                piv = Entity(parent=self.body, position=(sg * (W2 + 0.004), 0, Z(fx)))
                door = Entity(parent=piv)
                card = Entity(parent=piv)
                ob, cb = MeshBuilder(), MeshBuilder()
                inner = -sg * 0.055
                loc = lambda p, x: (x, p[1], p[0] - fx)
                lower = _clip(poly, belt, True)
                upper = _clip(poly, belt, False)
                if len(lower) >= 3:
                    ob.poly([loc(p, 0.0) for p in lower], col, (sg, 0, 0))
                    for k in range(len(lower)):          # торцы двери
                        a, b_ = lower[k], lower[(k + 1) % len(lower)]
                        ob.poly([loc(a, 0.0), loc(b_, 0.0), loc(b_, inner * 0.9), loc(a, inner * 0.9)], (60, 58, 55))
                    ob.box(min(0.0, sg * 0.018), belt - 0.08, rx - fx + 0.08, max(0.0, sg * 0.018), belt - 0.055,
                           rx - fx + 0.24, (190, 190, 185))                                     # наружная ручка
                    # --- дверная карта (изнутри): обивка, подлокотник, ручка, стеклоподъёмник, карман, швы, кнопка
                    ci = inner - sg * 0.004
                    cb.poly([loc(p, inner) for p in lower], trim, (-sg, 0, 0))
                    zc = (rx + fx) / 2 - fx
                    y0 = g["sill"] + 0.06
                    for zz in (rx - fx + 0.05, -0.05):                                         # кант по краям
                        cb.box(min(ci, ci - sg * 0.01), y0, zz - 0.012, max(ci, ci - sg * 0.01), belt - 0.02, zz + 0.012, dark_t)
                    cb.box(min(ci, ci - sg * 0.035), belt - 0.26, zc - 0.25, max(ci, ci - sg * 0.035), belt - 0.21,
                           zc + 0.12, dark_t)                                                    # подлокотник
                    cb.box(min(ci, ci - sg * 0.02), belt - 0.12, rx - fx + 0.10, max(ci, ci - sg * 0.02), belt - 0.09,
                           rx - fx + 0.18, (185, 185, 180))                                     # ручка открывания
                    cb.box(min(ci, ci - sg * 0.03), belt - 0.18, zc + 0.14, max(ci, ci - sg * 0.03), belt - 0.16,
                           zc + 0.26, (40, 40, 40))                                             # стеклоподъёмник
                    cb.box(min(ci, ci - sg * 0.012), y0 + 0.06, zc - 0.3, max(ci, ci - sg * 0.012), y0 + 0.24,
                           zc + 0.2, tuple(int(c * 0.55) for c in trim))                        # карман
                    for yy in (belt - 0.05, y0 + 0.3):                                         # швы обивки
                        cb.box(min(ci, ci - sg * 0.003), yy, rx - fx + 0.05, max(ci, ci - sg * 0.003), yy + 0.006,
                               -0.05, dark_t)
                    cb.box(min(ci, ci - sg * 0.02), belt - 0.02, rx - fx + 0.06, max(ci, ci - sg * 0.02), belt + 0.02,
                           rx - fx + 0.09, (30, 30, 30))                                        # кнопка замка
                    if idx == 0:                                                               # динамик
                        cb.box(min(ci, ci - sg * 0.006), y0 + 0.08, zc + 0.12, max(ci, ci - sg * 0.006), y0 + 0.22,
                               zc + 0.26, (35, 35, 35))
                if len(upper) >= 3:
                    for k in range(len(upper)):          # рамка стекла
                        a, b_ = upper[k], upper[(k + 1) % len(upper)]
                        if abs(a[1] - belt) < 1e-3 and abs(b_[1] - belt) < 1e-3:
                            continue
                        ln = math.hypot(b_[0] - a[0], b_[1] - a[1]) or 1
                        nx, ny = -(b_[1] - a[1]) / ln * 0.025, (b_[0] - a[0]) / ln * 0.025
                        ob.poly([loc(a, 0.0), loc(b_, 0.0), (0.0, b_[1] - ny, b_[0] - nx - fx), (0.0, a[1] - ny, a[0] - nx - fx)],
                                (30, 30, 32), (sg, 0, 0))
                door.model = ob.build(keep=True)
                door.double_sided = True
                if len(cb):
                    card.model = textured_copy(cb.build(keep=True), 0.06)
                    card.texture = textures3d.fabric()
                    card.double_sided = True
                if len(upper) >= 3:
                    gb = MeshBuilder()
                    gb.poly([loc(p, -sg * 0.02) for p in upper], (70, 92, 108, 90), None)
                    ge = Entity(parent=door, model=gb.build(), double_sided=True)
                    ge.setTransparency(TransparencyAttrib.MAlpha)
                    ge.setDepthWrite(False)
                door.enabled = False
                door._out_handle = Entity(parent=door, position=(sg * 0.02, belt - 0.07, rx - fx + 0.16))
                card._in_handle = Entity(parent=card, position=(inner - sg * 0.03, belt - 0.1, rx - fx + 0.14))
                self.door_piv[key] = (piv, door, card, fx, rx)
                self._door_ang[key] = 0.0
        self._rebuild_trims()

    def _rebuild_trims(self):
        """Старая сплошная обивка борта остаётся только там, где нет дверей (за задней дверью у купе)."""
        self._trim_off = {}
        boxes = getattr(self, "_trim_boxes", {})
        for side, (bx, col) in boxes.items():
            keys = [k for k in self.door_piv if k[0] == side]
            if not keys or side not in getattr(self, "trims", {}):
                continue
            rear = min(self.door_piv[k][4] for k in keys)
            x0, y0, z0, x1, y1, z1 = bx
            zmax = self.Z(rear) - 0.01
            t = self.trims[side]
            if zmax - min(z0, z1) < 0.08:
                t.enabled = False
                self._trim_off[side] = True
                continue
            mb = MeshBuilder()
            mb.box(x0, y0, min(z0, z1), x1, y1, zmax, col)
            mb.box(x0, y1 - 0.06, min(z0, z1), x1, y1 - 0.055, zmax, tuple(int(c * 0.6) for c in col))   # шов
            t.model = textured_copy(mb.build(keep=True), 0.06)
            t.texture = textures3d.fabric()

    # ---------------------------------------------------------------- багажник / задняя дверь
    def _build_tail(self):
        hinge = getattr(self, "_tail_hinge", None)
        parts = [e for e in (getattr(self, "trunk_lid", None), getattr(self, "rear_glass", None)) if e is not None]
        if self._geo.get("style") not in ("hatch", "wagon"):
            parts = [e for e in parts if e is getattr(self, "trunk_lid", None)]
        self.tail_piv = None
        if not hinge or not parts:
            return
        self.tail_piv = Entity(parent=self.body, position=hinge)
        for e in parts:
            e.world_parent = self.tail_piv
        for e, y in getattr(self, "snow_parts", []):         # снег на крышке — поднимается вместе с ней
            if getattr(e, "_on_trunk", False):
                e.world_parent = self.tail_piv
                e._lid_y = y - self.tail_piv.y
        self.tail_piv._grip = Entity(parent=self.body, position=(0, self._geo["rb_y"] - 0.05, self.Z(0) - 0.04))

    # ---------------------------------------------------------------- кнопки блокировки дверей
    def _build_knobs(self):
        """Кнопка блокировки у каждой двери (у стекла): заперто — утоплена."""
        belt = self._geo["belt"]
        self.knobs = []
        for key, (piv, door, card, fx, rx) in self.door_piv.items():
            h = card._in_handle
            kb = Entity(parent=card, model="cube", color=color.rgb(30, 30, 30), scale=(0.012, 0.035, 0.012),
                        position=(h.x, belt + 0.012, h.z - 0.05))
            kb._y0 = belt + 0.012
            self.knobs.append(kb)
        self._knob_state = None

    def _update_knobs(self):
        st = bool(getattr(self.car, "locked", False))
        if st == self._knob_state:
            return
        self._knob_state = st
        for kb in getattr(self, "knobs", []):
            kb.y = kb._y0 - (0.022 if st else 0.0)

    # ---------------------------------------------------------------- рабочие зеркала (стекло; камеры — mirrors.py)
    def _build_mirror_glass(self):
        """Стекло каждого зеркала — одна плоскость на грани корпуса, обращённой к водителю. У машины игрока на неё
        выводится живое отражение (mirrors.py), у остальных — просто серое стекло."""
        g, Z = self._geo, self.Z
        W2, belt, roof, ws = g["W2"], g["belt"], g["roof"], g["ws"]
        glass = (150, 162, 172)
        inner = Entity(parent=self.body, model="quad", position=(0, roof - 0.09, Z(ws - 0.35) - 0.003),
                       scale=(0.18, 0.05), color=color.rgb(*glass), double_sided=True)
        left = Entity(parent=self.body, model="quad", position=(-(W2 + 0.1) + 0.04, belt + 0.11, Z(ws - 0.14) - 0.003),
                      scale=(0.11, 0.07), color=color.rgb(*glass), double_sided=True)
        right = Entity(parent=self.body, model="quad", position=((W2 + 0.1) - 0.04, belt + 0.11, Z(ws - 0.14) - 0.003),
                       scale=(0.11, 0.07), color=color.rgb(*glass), double_sided=True)
        self.mirror_glass = {"inner": inner, "side": left, "side_r": right}

    # ---------------------------------------------------------------- замок зажигания и ключ
    def _build_ignition(self):
        """Замок зажигания — на панели правее колонки, под ободом руля; ключ торчит к водителю."""
        info = getattr(self, "_interior", None) or {}
        g = self._geo
        ex = self.car.spec["eye"][0]
        dy = info.get("dash_y", g["belt"] + 0.06)
        dz = info.get("dash_z", self.Z(g["ws"] - 0.3))
        base = (ex + 0.2, dy - 0.14, dz - 0.07)
        self.ign = Entity(parent=self.body, model="cube", color=color.rgb(60, 60, 64), position=base,
                          scale=(0.045, 0.045, 0.03))
        Entity(parent=self.ign, model="cube", color=color.rgb(170, 170, 175), position=(0, 0, -0.55), scale=(0.6, 0.6, 0.2))
        self.ign_key = Entity(parent=self.body, position=(base[0], base[1], base[2] - 0.03))
        Entity(parent=self.ign_key, model="cube", color=color.rgb(195, 195, 200), position=(0, 0, 0.0),
               scale=(0.008, 0.016, 0.03))                                   # лезвие (видно у замка)
        Entity(parent=self.ign_key, model="cube", color=color.rgb(35, 35, 38), position=(0, 0, -0.03),
               scale=(0.03, 0.036, 0.014))                                   # головка ключа
        Entity(parent=self.ign_key, model="cube", color=color.rgb(200, 180, 60), position=(0, -0.05, -0.034),
               scale=(0.012, 0.06, 0.004))                                   # брелок
        self.ign_key.enabled = False
        self._ign_ang = 0.0

    def _update_ignition(self, dt):
        car = self.car
        ik = getattr(self, "ign_key", None)
        if ik is None:
            return
        has = bool(getattr(car, "ign_key", None))
        ik.enabled = has
        want = 90.0 if car.cranking else (60.0 if car.running else 0.0)
        self._ign_ang += (want - self._ign_ang) * min(1.0, dt * 14)
        ik.rotation_z = -self._ign_ang
        # вставка/извлечение: ключ въезжает в замок
        slide = getattr(car, "_key_slide", 0.0)
        if slide > 0:
            car._key_slide = max(0.0, slide - dt * 2.2)
        ik.z = self.ign.z - 0.03 - 0.05 * min(1.0, getattr(car, "_key_slide", 0.0))

    # ---------------------------------------------------------------- поворотники
    def _build_signals(self):
        g, Z = self._geo, self.Z
        W2, L = g["W2"], g["L"]
        self.signals = {"l": [], "r": []}
        for side, sg in (("l", -1), ("r", 1)):
            for pos, sc in (((sg * (W2 - 0.09), g["nose"] - 0.05, Z(L) + 0.012), (0.12, 0.05, 0.02)),       # перед
                            ((sg * (W2 - 0.07), g["rb_y"] - 0.12, Z(0) - 0.012), (0.10, 0.06, 0.02)),       # зад
                            ((sg * (W2 + 0.006), g["belt"] - 0.18, Z(L - 0.75)), (0.01, 0.025, 0.05))):     # на крыле
                e = Entity(parent=self.body, model="cube", position=pos, scale=Vec3(*sc) * 1.05, color=color.rgb(*AMBER_ON))
                e.setLightOff()
                e.enabled = False
                self.signals[side].append(e)
        # подрулевые переключатели (не вращаются вместе с рулём)
        self.stalks = {}
        for side, sg in (("l", -1), ("r", 1)):
            st = Entity(parent=self.wheel_pivot, position=(sg * 0.16, -0.05, 0.09))
            Entity(parent=st, model="cube", color=color.rgb(35, 35, 35), position=(sg * 0.06, 0, 0), scale=(0.12, 0.016, 0.016))
            Entity(parent=st, model="cube", color=color.rgb(200, 120, 30) if side == "l" else color.rgb(60, 160, 60),
                   position=(sg * 0.125, 0, 0), scale=(0.018, 0.022, 0.022))
            self.stalks[side] = st
        self._blink_on = None

    # ---------------------------------------------------------------- приборы (работают)
    def _build_gauges(self):
        info = getattr(self, "_interior", None)
        if not info:
            return
        g = self._geo
        ex = self.car.spec["eye"][0]
        y, z = info["dash_y"] + 0.06, info["dash_z"] + 0.0
        self.gauges = {}
        self._gauge_ents = []
        hood_ = Entity(parent=self.body, model="cube", color=color.rgb(25, 24, 23), position=(ex, y + 0.02, z + 0.05),
                       scale=(0.4, 0.14, 0.06))                         # щиток приборов
        visor = Entity(parent=self.body, model="cube", color=color.rgb(20, 20, 20), position=(ex, y + 0.095, z + 0.0),
                       scale=(0.42, 0.012, 0.1))                        # козырёк
        self._gauge_ents += [hood_, visor]
        for key, dx, r, kind in (("speed", -0.075, 0.055, "speed"), ("rpm", 0.075, 0.055, "rpm"),
                                 ("fuel", -0.16, 0.028, "small"), ("temp", 0.16, 0.028, "small")):
            face = Entity(parent=self.body, model="quad", texture=textures3d.gauge(kind), position=(ex + dx, y + 0.02, z - 0.012),
                          scale=r * 2, rotation_x=-12)
            face.setTransparency(TransparencyAttrib.MAlpha)
            face.setLightOff()
            self._gauge_ents.append(face)
            needle_p = Entity(parent=face, z=-0.01)
            Entity(parent=needle_p, model="quad", color=color.rgb(240, 120, 40), scale=(0.035, 0.42), y=0.21)
            needle_p.setLightOff()
            self.gauges[key] = needle_p
        # сигнальные лампы на щитке: стрелки поворотников
        self.dash_arrows = {}
        for side, dx in (("l", -0.13), ("r", 0.13)):
            a = Entity(parent=self.body, model="quad", color=color.rgb(20, 60, 20), position=(ex + dx, y + 0.068, z - 0.013),
                       scale=(0.02, 0.012))
            a.setLightOff()
            self.dash_arrows[side] = a

    def _update_gauges(self):
        gs = getattr(self, "gauges", None)
        if not gs:
            return
        car = self.car

        def ang(v):          # 0..1 -> угол стрелки (225° .. -45°)
            return -135 + 270 * max(0.0, min(1.0, v))
        ok = car.battery_charge > 1 and car.elec_ok("dash")        # предохранитель щитка
        gs["speed"].rotation_z = ang(car.kmh() / 200 if ok else 0)
        gs["rpm"].rotation_z = ang(car.rpm / 8000 if ok else 0)
        gs["fuel"].rotation_z = ang(car.fuel / car.tank if ok else 0) * 0.5
        gs["temp"].rotation_z = ang((car.temp - 40) / 90 if ok else 0) * 0.5

    # ---------------------------------------------------------------- мелкие детали
    def _build_details(self):
        g, Z = self._geo, self.Z
        car = self.car
        W2, L, sill, belt, roof = g["W2"], g["L"], g["sill"], g["belt"], g["roof"]
        info = getattr(self, "_interior", None) or {}
        ex = car.spec["eye"][0]
        mb = MeshBuilder()           # без текстуры
        tex = MeshBuilder(uv_tile=0.06)   # ткань/ковёр
        dark, black, chrome, rub = (38, 36, 34), (22, 22, 22), (185, 185, 180), (26, 26, 26)
        fl = info.get("floor_y", sill + 0.07)
        dz, dy = info.get("dash_z", Z(g["ws"] - 0.3)), info.get("dash_y", belt + 0.06)
        # --- салон: ковёр пола, педали, ручник, центральная консоль с магнитолой и печкой, дефлекторы, бардачок
        tex.box(-(W2 - 0.12), fl, Z(g["rear_z"] + 0.2), W2 - 0.12, fl + 0.01, dz - 0.05, (58, 52, 48))
        for i, px in enumerate((-0.08, 0.0, 0.08)):
            mb.box(ex + px - 0.025, fl + 0.06, dz - 0.18, ex + px + 0.025, fl + 0.12, dz - 0.16, (45, 45, 45))
            mb.box(ex + px - 0.005, fl + 0.12, dz - 0.17, ex + px + 0.005, fl + 0.26, dz - 0.15, (30, 30, 30))
        mb.box(-0.03, fl + 0.02, Z(g["seat_z"] - 0.1), 0.03, fl + 0.12, Z(g["seat_z"] + 0.25), (40, 40, 40))   # ручник
        mb.box(-0.02, fl + 0.12, Z(g["seat_z"] + 0.18), 0.02, fl + 0.16, Z(g["seat_z"] + 0.3), (25, 25, 25))
        mb.box(-0.12, fl, dz - 0.35, 0.12, dy - 0.08, dz - 0.02, dark, top=(34, 32, 30))             # консоль
        mb.box(-0.09, dy - 0.22, dz - 0.055, 0.09, dy - 0.16, dz - 0.03, black)                       # магнитола
        mb.box(-0.08, dy - 0.205, dz - 0.058, 0.02, dy - 0.19, dz - 0.054, (80, 140, 90))             # шкала
        for kx in (-0.075, 0.075):
            mb.box(kx - 0.01, dy - 0.2, dz - 0.07, kx + 0.01, dy - 0.18, dz - 0.055, chrome)          # ручки
        for kx in (-0.05, 0.0, 0.05):
            mb.box(kx - 0.004, dy - 0.28, dz - 0.058, kx + 0.004, dy - 0.25, dz - 0.05, (200, 200, 190))   # печка
        for vx in (-0.55 * W2 * 1.2, -0.12, 0.12, 0.55 * W2 * 1.2):
            mb.box(vx - 0.05, dy - 0.07, dz - 0.03, vx + 0.05, dy - 0.03, dz - 0.015, black)          # дефлекторы
            for k in range(3):
                mb.box(vx - 0.045, dy - 0.066 + k * 0.012, dz - 0.034, vx + 0.045, dy - 0.062 + k * 0.012, dz - 0.03,
                       (60, 60, 60))
        mb.box(0.2, dy - 0.16, dz - 0.028, W2 - 0.2, dy - 0.155, dz - 0.024, (30, 28, 26))           # бардачок: шов
        mb.box(0.45, dy - 0.12, dz - 0.03, 0.5, dy - 0.11, dz - 0.02, chrome)                        # замок
        # зеркало, козырьки, плафон, ремни
        # салонное зеркало: только корпус и крепление к потолку (стекло — одно, рабочее: _build_mirror_glass)
        mb.box(-0.1, roof - 0.12, Z(g["ws"] - 0.35), 0.1, roof - 0.06, Z(g["ws"] - 0.33), (30, 30, 30))
        mb.box(-0.012, roof - 0.06, Z(g["ws"] - 0.345), 0.012, roof - 0.005, Z(g["ws"] - 0.335), (30, 30, 30))
        for sx_ in (-1, 1):
            mb.box(sx_ * 0.08, roof - 0.07, Z(g["ws"] - 0.55), sx_ * (W2 - 0.12), roof - 0.055, Z(g["ws"] - 0.32),
                   (150, 140, 120))
            mb.box(sx_ * (W2 - 0.1) - 0.02, fl + 0.3, Z(g["seat_z"] - 0.35), sx_ * (W2 - 0.1) + 0.02, roof - 0.1,
                   Z(g["seat_z"] - 0.32), (35, 35, 35))                                               # ремень
        mb.box(-0.06, roof - 0.07, Z((g["rs"] + g["re"]) / 2), 0.06, roof - 0.055, Z((g["rs"] + g["re"]) / 2 + 0.1),
               (230, 225, 200))
        # --- кузов: зеркало водителя, дворники, антенна, эмблемы, уплотнители стёкол, лючок бака, буксирный крюк
        mx = -(W2 + 0.1)
        # наружные зеркала (левое и правое): корпус над подоконником, позади стойки + тонкое крепление в цвет кузова.
        # Стекло — одна плоскость на каждом (рабочее у машины игрока): _build_mirror_glass
        pcol = car.paint if car.color else (150, 140, 120)
        for sg_ in (-1, 1):
            mx_ = sg_ * (W2 + 0.1) - (0.04 if sg_ > 0 else 0.0)
            x0, x1 = (mx_ - 0.02, mx_ + 0.1) if sg_ < 0 else (mx_ - 0.06, mx_ + 0.06)
            mb.box(x0, belt + 0.07, Z(g["ws"] - 0.14), x1, belt + 0.15, Z(g["ws"] - 0.08), black)
            sx0, sx1 = (mx_ + 0.1, sg_ * W2) if sg_ < 0 else (sg_ * W2, x0)
            mb.box(min(sx0, sx1), belt + 0.085, Z(g["ws"] - 0.115), max(sx0, sx1), belt + 0.105, Z(g["ws"] - 0.105), pcol)
        for wx in (-0.35, 0.15):
            mb.box(wx - 0.22, belt + 0.02, Z(g["ws"] + 0.02), wx + 0.22, belt + 0.035, Z(g["ws"] + 0.05), black)
        mb.box(W2 - 0.2, belt, Z(g["ws"] + 0.1), W2 - 0.19, belt + 0.8, Z(g["ws"] + 0.11), (160, 160, 160))   # антенна
        mb.box(-0.05, g["nose"] + 0.02, Z(L) + 0.004, 0.05, g["nose"] + 0.05, Z(L) + 0.012, chrome)         # эмблема
        mb.box(-0.08, g["rb_y"] - 0.06, Z(0) - 0.012, 0.08, g["rb_y"] - 0.035, Z(0) - 0.004, chrome)
        mb.box(-(W2 - 0.1), belt - 0.004, Z(g["ws"] - 0.02), W2 - 0.1, belt + 0.006, Z(g["ws"] + 0.01), rub)   # резинка
        mb.box(-0.06, sill - 0.02, Z(L) + 0.02, 0.06, sill + 0.02, Z(L) + 0.08, (60, 60, 60))              # крюк
        # стёкла поворотников (тусклые; яркие мигающие — у машины игрока)
        for sg in (-1, 1):
            mb.box(sg * (W2 - 0.09) - 0.06, g["nose"] - 0.075, Z(L) + 0.002, sg * (W2 - 0.09) + 0.06, g["nose"] - 0.025,
                   Z(L) + 0.022, AMBER_OFF)
            mb.box(sg * (W2 - 0.07) - 0.05, g["rb_y"] - 0.15, Z(0) - 0.022, sg * (W2 - 0.07) + 0.05, g["rb_y"] - 0.09,
                   Z(0) - 0.002, AMBER_OFF)
            mb.box(sg * (W2 + 0.006) - 0.005, g["belt"] - 0.19, Z(L - 0.75) - 0.025, sg * (W2 + 0.006) + 0.005,
                   g["belt"] - 0.17, Z(L - 0.75) + 0.025, AMBER_OFF)
        # швы капота и крыльев (тёмные линии зазоров)
        hz = Z(g["ws"])
        for sx_ in (-1, 1):
            mb.box(sx_ * (W2 - 0.13) - 0.004, g["nose"] + 0.08, hz + 0.02, sx_ * (W2 - 0.13) + 0.004,
                   max(belt, g["nose"] + 0.09) + 0.005, Z(L) - 0.02, (30, 30, 30))
        # --- моторный отсек: стаканы стоек, вакуумник с ГТЦ, бачки, патрубки, жгут, катушка, блок предохранителей
        eb = getattr(self, "_engine_box", None)
        bay = MeshBuilder()
        if eb:
            cx, cy, cz, w, h, l = eb
            front = cz + l / 2
            for sx_ in (-1, 1):
                bay.box(sx_ * (W2 - 0.2) - 0.1, cy - 0.05, cz - 0.1, sx_ * (W2 - 0.2) + 0.1, cy + 0.3, cz + 0.15, (70, 70, 72))
            bay.box(-(W2 - 0.1), cy - 0.2, cz - l / 2 - 0.22, W2 - 0.1, cy + 0.35, cz - l / 2 - 0.2, (55, 55, 58))   # щит
            bay.cylinder(ex, cy + 0.15, cz - l / 2 - 0.12, 0.1, 0.02, (40, 40, 42), seg=12)
            bay.box(ex - 0.03, cy + 0.12, cz - l / 2 - 0.1, ex + 0.03, cy + 0.2, cz - l / 2 + 0.02, (150, 150, 150))  # ГТЦ
            bay.box(ex - 0.025, cy + 0.2, cz - l / 2 - 0.05, ex + 0.025, cy + 0.26, cz - l / 2 - 0.0, (220, 220, 200))
            bay.box(W2 - 0.3, cy, front - 0.1, W2 - 0.15, cy + 0.2, front + 0.02, (225, 225, 215))            # омыватель
            bay.box(-(W2 - 0.18), cy + 0.05, cz, -(W2 - 0.3), cy + 0.2, cz + 0.12, (215, 210, 190))           # расширит.
            bay.box(-0.03, cy + 0.08, front + 0.02, 0.03, cy + 0.12, front + 0.25, (25, 25, 25))              # патрубок
            bay.box(-0.03, cy - 0.12, front + 0.02, 0.03, cy - 0.08, front + 0.25, (25, 25, 25))
            bay.box(-w * 0.6, cy + h * 0.25, cz - l / 2, -w * 0.6 + 0.02, cy + h * 0.25 + 0.02, cz + l / 2, (20, 20, 20))  # жгут
            bay.box(w * 0.5, cy + 0.2, cz - l / 2 - 0.08, w * 0.5 + 0.06, cy + 0.3, cz - l / 2 - 0.02, (40, 40, 40))  # катушка
            bay.box(-(W2 - 0.3), cy + 0.25, cz - l / 2 - 0.19, -(W2 - 0.12), cy + 0.33, cz - l / 2 - 0.12, (40, 40, 40))
        # --- багажник: коврик, запаска, домкрат, свёрток с ключами
        tz0, tz1 = g.get("trunk_z0", 0.12), g.get("trunk_z1", 0.6)
        ty = g.get("trunk_y", sill + 0.15)               # высота пола багажника (у универсала ВАЗ — выше)
        tex.box(-(W2 - 0.12), ty, Z(tz0), W2 - 0.12, ty + 0.01, Z(tz1), (48, 46, 44))
        mb.cylinder(-(W2 - 0.4), ty + 0.01, Z((tz0 + tz1) / 2), 0.27, 0.16, (28, 28, 28), seg=14)
        mb.cylinder(-(W2 - 0.4), ty + 0.012, Z((tz0 + tz1) / 2), 0.16, 0.162, (120, 120, 115), seg=10)
        mb.box(0.1, ty + 0.01, Z(tz0 + 0.1), 0.35, ty + 0.09, Z(tz0 + 0.2), (150, 40, 30))                   # домкрат
        mb.box(0.4, ty + 0.01, Z(tz0 + 0.1), 0.6, ty + 0.05, Z(tz0 + 0.18), (70, 60, 45))                    # ключи
        det = Entity(parent=self.body, model=mb.build(keep=True), double_sided=True)
        te = Entity(parent=self.body, model=tex.build(keep=True), texture=textures3d.carpet(), double_sided=True)
        self.details = [det, te]
        if len(bay):
            be = Entity(parent=self.bay, model=bay.build(keep=True), double_sided=True)
            self.details.append(be)
        # ткань сидений — с нормальными UV (раньше вся деталь брала один пиксель текстуры)
        se = getattr(self, "seats_e", None)
        if se is not None and getattr(se.model, "_src", None):
            se.model = textured_copy(se.model, 0.06)
            se.texture = textures3d.fabric()

    # ---------------------------------------------------------------- Mustang → Shelby GT500 «Eleanor»
    def _build_mustang_kit(self):
        from ursina import Text
        g, Z = self._geo, self.Z
        W2, L, sill, belt, roof = g["W2"], g["L"], g["sill"], g["belt"], g["roof"]
        blk, chrome, red = color.rgb(18, 18, 20), color.rgb(205, 205, 200), color.rgb(190, 25, 25)
        kit = {}

        def add(node, ent):
            kit.setdefault(node, []).append(ent)
            return ent
        hl = getattr(self, "_hood_len", 1.2)
        # капот GT500: два воздухозаборника и замки-шпильки
        for sx in (-0.22, 0.22):
            add("hood", Entity(parent=self.hood, model="cube", color=blk, position=(sx, 0.035, hl * 0.45), scale=(0.18, 0.05, 0.32)))
            add("hood", Entity(parent=self.hood, model="cube", color=chrome, position=(sx * 2.6, 0.02, hl * 0.95),
                               scale=(0.03, 0.02, 0.03)))
        # покраска: чёрные гоночные полосы — капот, крыша, багажник
        for sx in (-0.12, 0.12):
            add("paint", Entity(parent=self.hood, model="cube", color=blk, position=(sx, 0.012, hl / 2), scale=(0.17, 0.004, hl)))
            add("paint", Entity(parent=self.body, model="cube", color=blk, position=(sx, roof + 0.004, Z((g["rs"] + g["re"]) / 2)),
                                scale=(0.17, 0.004, g["re"] - g["rs"] - 0.1)))
            tr = add("paint", Entity(parent=self.body, model="cube", color=blk, position=(sx, g["rb_y"] + 0.004,
                                                                                      Z((0.05 + g["rgb"]) / 2)),
                                     scale=(0.17, 0.004, g["rgb"] - 0.1)))
            if getattr(self, "tail_piv", None) is not None:
                tr.world_parent = self.tail_piv
        for sg in (-1, 1):
            add("paint", Entity(parent=self.body, model="cube", color=blk, position=(sg * (W2 + 0.006), sill + 0.13, Z(L / 2)),
                                scale=(0.004, 0.05, L * 0.75)))
        # обвес: «пасть», противотуманки, центральные фары, воздухозаборники, пороги, спойлер
        add("bodykit", Entity(parent=self.body, model="cube", color=blk, position=(0, sill + 0.05, Z(L) + 0.05),
                              scale=(W2 * 1.6, 0.16, 0.12)))
        for sx in (-0.5, 0.5):
            f = add("bodykit", Entity(parent=self.body, model="cube", color=color.rgb(240, 235, 200),
                                      position=(sx, sill + 0.08, Z(L) + 0.115), scale=(0.1, 0.07, 0.02)))
        for sx in (-0.18, 0.18):
            add("bodykit", Entity(parent=self.body, model="mrg_sphere", color=color.rgb(235, 235, 220),
                                  position=(sx, g["nose"] - 0.04, Z(L) + 0.02), scale=0.09))
        for sg in (-1, 1):
            add("bodykit", Entity(parent=self.body, model="cube", color=blk, position=(sg * (W2 + 0.02), belt - 0.18, Z(1.35)),
                                  scale=(0.05, 0.12, 0.35)))
            add("bodykit", Entity(parent=self.body, model="cube", color=blk, position=(sg * (W2 + 0.02), sill + 0.03, Z(L / 2)),
                                  scale=(0.05, 0.07, L * 0.55)))
        sp_ = add("bodykit", Entity(parent=self.body, model="cube", color=color.rgb(100, 102, 106),
                                    position=(0, g["rb_y"] + 0.04, Z(0.1)), scale=(W2 * 1.8, 0.06, 0.12)))
        if getattr(self, "tail_piv", None) is not None:
            sp_.world_parent = self.tail_piv
        # боковой выхлоп
        for sg in (-1, 1):
            add("sidepipes", Entity(parent=self.body, model="cube", color=chrome, position=(sg * (W2 + 0.07), sill - 0.02, Z(L * 0.45)),
                                    scale=(0.07, 0.07, 1.4)))
            add("sidepipes", Entity(parent=self.body, model="cube", color=color.rgb(30, 30, 30),
                                    position=(sg * (W2 + 0.07), sill - 0.02, Z(L * 0.45 - 0.72)), scale=(0.05, 0.05, 0.02)))
        # колёса: тёмные 5-спицевые диски; красные суппорты
        for slot, (pivot, spin, bricks) in self.wheels.items():
            sg = -1 if pivot.x < 0 else 1
            for k in range(5):
                a = k * 72
                add("wheels", Entity(parent=spin, model="cube", color=color.rgb(45, 45, 48),
                                     position=(sg * 0.1, math.sin(math.radians(a)) * 0.1, math.cos(math.radians(a)) * 0.1),
                                     rotation_x=-a, scale=(0.02, 0.2, 0.045)))
            add("wheels", Entity(parent=spin, model="cube", color=chrome, position=(sg * 0.11, 0, 0), scale=(0.02, 0.07, 0.07)))
            add("brakes", Entity(parent=pivot, model="cube", color=red, position=(sg * 0.02, 0.1, -0.12), scale=(0.07, 0.1, 0.1)))
        # мотор 428: хромированный фильтр «Cobra» и крышки клапанов
        eb = getattr(self, "_engine_box", None)
        if eb:
            cx, cy, cz, w, h, l = eb
            add("engine428", Entity(parent=self.bay, model="cube", color=chrome, position=(cx, cy + h * 0.25 + 0.3, cz),
                                    scale=(0.36, 0.06, 0.26)))
            for sx in (-0.13, 0.13):
                add("engine428", Entity(parent=self.bay, model="cube", color=chrome, position=(cx + sx, cy + h * 0.25 + 0.2, cz),
                                        scale=(0.09, 0.05, l * 0.85)))
        # салон: Hurst и приборы Stewart-Warner
        info = getattr(self, "_interior", {})
        if info:
            add("toploader", Entity(parent=self.body, model="mrg_sphere", color=color.rgb(245, 245, 240),
                                    position=(0, info["floor_y"] + 0.5, info["dash_z"] - 0.5), scale=0.05))
            for k in range(3):
                add("interior", Entity(parent=self.body, model=_gauge_mesh(), color=color.rgb(20, 20, 20),
                                       position=(-0.08 + k * 0.08, info["dash_y"] - 0.1, info["dash_z"] - 0.06),
                                       rotation_x=90, scale=(0.05, 0.03, 0.05)))
        # надписи GT500 — только у полностью собранной «Eleanor»
        for sg in (-1, 1):
            t = Text("GT500", parent=self.body, scale=8, color=color.rgb(20, 20, 20), origin=(0, 0),
                     position=(sg * (W2 + 0.012), sill + 0.2, Z(2.3)), rotation_y=-90 * sg)
            add("_legend", t)
        self.kit = kit
        self._kit_key = None

    def _update_kit(self):
        if not getattr(self, "kit", None):
            return
        from tuning import is_legend
        car = self.car
        key = tuple(sorted(n for n in self.kit if n != "_legend" and car.has_tune(n))) + (is_legend(car),)
        if key == self._kit_key:
            return
        self._kit_key = key
        for node, ents in self.kit.items():
            on = is_legend(car) if node == "_legend" else car.has_tune(node)
            for e in ents:
                e.enabled = on

    # ================================================================== обновление
    def _update_extras(self, dt):
        car = self.car
        # двери (передние и задние): карта видна всегда, наружная панель — только открытая
        for key, (piv, door, card, fx, rx) in getattr(self, "door_piv", {}).items():
            has = car.has("door_" + key[0])
            want = 65.0 if car.door_open.get(key) and has else 0.0
            a = self._door_ang.get(key, 0.0)
            a += (want - a) * min(1.0, dt * 6)
            if abs(a - want) < 0.5:
                a = want
            self._door_ang[key] = a
            sg = -1 if key[0] == "l" else 1
            piv.rotation_y = -sg * a
            door.enabled = has and a > 0.3
            card.enabled = has
        self._update_trunk_items()
        self._update_knobs()
        if self.fusebox is not None:
            self._update_elec()
        # багажник
        tp = getattr(self, "tail_piv", None)
        if tp is not None:
            # крышка багажника седана встаёт почти вертикально; дверь универсала/хэтчбека (петли на крыше)
            # поднимается выше головы — в багажник видно и можно дотянуться
            hy = (getattr(self, "_tail_hinge", None) or (0, 0, 0))[1]
            full = 108.0 if hy > self._geo.get("belt", 0.9) + 0.3 else 82.0
            want = full if car.trunk_open and car.has("trunk") else 0.0
            self._tail_ang += (want - self._tail_ang) * min(1.0, dt * 5)
            tp.rotation_x = self._tail_ang
        # поворотники: 1.5 Гц, щелчок (только у «живой» машины игрока)
        if not self.live:
            if self.bolt_ents:
                self._update_bolts()
            self._update_kit()
            return
        self._update_ignition(dt)
        on = car.turn != 0 and (car.blink_t % 0.66) < 0.33 and car.battery_charge > 2 and car.elec_ok("turn")
        fl = getattr(car, "_flash_t", 0.0)
        flash = fl > 0 and car.battery_charge > 2                   # центральный замок мигает аварийкой
        if fl > 0:
            car._flash_t = max(0.0, fl - dt)
            flash = flash and (fl % 0.4) > 0.2
        state_ = (on, flash)
        if state_ != self._blink_on:
            self._blink_on = state_
            for side, ents in self.signals.items():
                lit = (on and ((side == "l" and car.turn < 0) or (side == "r" and car.turn > 0))) or flash
                for e in ents:
                    e.enabled = lit
                arr = getattr(self, "dash_arrows", {}).get(side)
                if arr:
                    arr.color = color.rgb(60, 230, 60) if lit else color.rgb(20, 60, 20)
            if car.turn:
                car.sounds.append("click")
        for side, st in getattr(self, "stalks", {}).items():
            active = (side == "l" and car.turn < 0) or (side == "r" and car.turn > 0)
            st.rotation_z = (18 if side == "l" else -18) if active else 0
        self._update_gauges()
        self._update_kit()
        if self.bolt_ents:
            self._update_bolts()

    # ================================================================== болты и гайки
    def _bolt_anchors(self):
        """[(ключ крепежа, родитель, [локальные позиции])] для деталей, у которых есть 3D-модель."""
        car = self.car
        out = []

        def ring(n, rr=0.38, y=0.5):
            return [(math.cos(2 * math.pi * i / n) * rr, y, math.sin(2 * math.pi * i / n) * rr) for i in range(n)]

        def perim(n, y=0.5):
            pts = []
            for i in range(n):
                t = i / n * 4
                side, f = int(t), t - int(t)
                x, z = [(-0.42 + 0.84 * f, -0.42), (0.42, -0.42 + 0.84 * f), (0.42 - 0.84 * f, 0.42), (-0.42, 0.42 - 0.84 * f)][side]
                pts.append((x, y, z))
            return pts
        # колёса: гайки на ступице (снаружи)
        for slot, (pivot, spin, bricks) in self.wheels.items():
            n = fast.total(car, slot) or fast.spec(car, slot)[0]
            sg = -1 if pivot.x < 0 else 1
            tw = 0.09
            pts = [(sg * tw, math.sin(2 * math.pi * i / n) * 0.08, math.cos(2 * math.pi * i / n) * 0.08) for i in range(n)]
            out.append((slot, spin, pts))
        # моторный отсек (детали из bay_parts)
        for slot, ent in getattr(self, "bay_parts", {}).items():
            spec = fast.spec(car, slot)
            if spec and ent is not None:
                out.append((slot, ent, perim(spec[0])))
        # двигатель по деталям (нижние — поддон, коленвал, вкладыши — крепёж снизу, видно из-под машины)
        for k, ents in getattr(self, "eng_vis", {}).items():
            spec = fast.spec(car, "eng:" + k)
            if spec and ents:
                if k in _under.UNDER_ENG:
                    pts = [(x * 1.1, -0.5, z * 1.1) for x, _, z in perim(spec[0])]
                else:
                    pts = perim(spec[0]) if k != "crank_pulley" else [(0, 0, 0.6)]
                out.append(("eng:" + k, ents[0], pts))
        # низ машины: КПП, сцепление, выхлоп, амортизаторы, рулевое, стартер (under3d.py)
        for key, parent, pts in _under3d.build(self):
            out.append((key, parent, pts))
        # капот и дверь багажника: болты петель
        if getattr(self, "hood", None) is not None:      # всегда: снятый капот ставится на эти же петли
            W2 = self._geo["W2"]
            out.append(("hood", self.hood, [(sx * (W2 - 0.25), -0.005, dz) for sx in (-1, 1) for dz in (0.05, 0.12)]))
        if getattr(self, "tail_piv", None) is not None:
            out.append(("trunk", self.tail_piv, [(sx * 0.45, -0.01, dz) for sx in (-1, 1) for dz in (-0.03, -0.08)]))
        # петли дверей (видно при открытой двери)
        seen = set()
        for key, (piv, door, card, fx, rx) in getattr(self, "door_piv", {}).items():
            if key[0] in seen:                  # крепёж — у слота «двери левые/правые», петли передней двери
                continue
            seen.add(key[0])
            g = self._geo
            sg = -1 if key[0] == "l" else 1
            pts = [(-sg * 0.06, y, -0.015) for y in (g["sill"] + 0.2, g["sill"] + 0.25, g["belt"] - 0.22, g["belt"] - 0.17)]
            out.append(("door_" + key[0], door, pts))
        return out

    def ensure_bolts(self, on):
        """Болты создаются только у машины, возле которой стоит игрок (их много)."""
        self.ensure_elec(on or self.live)          # блок предохранителей: рядом с машиной или изнутри
        if on and not self.bolt_ents:
            self.bolt_ents = []
            for key, parent, pts in self._bolt_anchors():
                for i, p in enumerate(pts):
                    e = Entity(parent=parent, model="cube", position=p, color=color.rgb(150, 150, 145))
                    e.world_scale = Vec3(0.024, 0.016, 0.024)
                    self.bolt_ents.append((key, i, e, Vec3(*p)))
            self._bolt_key = None
            self._update_bolts()
        elif not on and self.bolt_ents:
            for _, _, e, _ in self.bolt_ents:
                destroy(e)
            self.bolt_ents = None
            _under3d.destroy_parts(self)

    def _update_bolts(self):
        car = self.car
        key = (tuple(sorted((k, tuple(v) if isinstance(v, list) else v) for k, v in car.bolts.items())),
               tuple(k for k in car.parts if car.parts[k] is None), tuple(k for k, v in (car.eng or {}).items() if v is None))
        _under3d.update(self)
        if key == self._bolt_key:
            return
        self._bolt_key = key
        for k, i, e, p0 in self.bolt_ents:
            st = fast.states(car, k)
            if not st:
                e.enabled = False
                continue
            e.enabled = True
            tight_ = st[i] if i < len(st) else 1
            e.color = color.rgb(150, 150, 145) if tight_ else color.rgb(210, 170, 60)
            if tight_:
                e.position = p0
            elif _under.is_under(k):                     # снизу отпущенный болт свисает вниз
                e.position = p0 + (Vec3(0, -0.25, 0) if k.startswith("eng:") else Vec3(0, -0.03, 0))
            else:
                e.position = p0 + Vec3(0, 0.25, 0)

    # ================================================================== точки взаимодействия
    def targets(self, inside, owned, seat="driver"):
        """Список (ключ-цель, позиция в мире, радиус «попадания»). Что делать по E — решает main."""
        car = self.car
        out = []
        if not getattr(self, "_geo", None):
            return out
        g = self._geo
        if inside:
            if not self.live:
                self.ensure_live(True)
            side = "l" if seat == "driver" else "r"
            sg = -1 if side == "l" else 1
            if seat == "driver":
                self._elec_targets(out, True)
                if getattr(self, "ign", None) is not None:
                    out.append((("ign", None), self.ign.world_position, 0.06))
                for st_side, st in getattr(self, "stalks", {}).items():
                    out.append((("stalk", st_side), st.world_position + st.right * (0.12 if st_side == "r" else -0.12), 0.05))
            else:
                out.append((("seat_move", "driver"), self._w((-0.36, g["seat_y"] + 0.12, self.Z(g["seat_z"]))), 0.2))
            if side in self.door_piv and car.has("door_" + side):
                piv, door, card, fx, rx = self.door_piv[side]
                if car.door_open.get(side):
                    out.append((("door_close", side), card._in_handle.world_position, 0.09))
                    out.append((("exit", side), self._w((sg * (g["W2"] + 0.45), g["belt"] - 0.05, self.Z(g["seat_z"]))), 0.25))
                else:
                    out.append((("door_open_in", side), card._in_handle.world_position, 0.08))
            elif car.door_open.get(side) or not car.has("door_" + side):
                out.append((("exit", side), self._w((sg * (g["W2"] + 0.45), g["belt"] - 0.05, self.Z(g["seat_z"]))), 0.25))
            return out
        # снаружи: ручки всех дверей, сиденья, капот, багажник
        for key, (piv, door, card, fx, rx) in self.door_piv.items():
            if not car.has("door_" + key[0]):
                continue
            sg = -1 if key[0] == "l" else 1
            if car.door_open.get(key):
                out.append((("door_close", key), door._out_handle.world_position, 0.1))
                if owned and key in ("l", "r"):
                    out.append((("seat", key), self._w((sg * 0.36, g["seat_y"] + 0.12, self.Z(g["seat_z"]))), 0.2))
            else:
                out.append((("door_open", key), self._w((sg * (g["W2"] + 0.03), g["belt"] - 0.07, self.Z(rx + 0.16))), 0.1))
        if car.has("hood"):
            out.append((("hood", None), self._w((0, g["nose"] + 0.12, self.Z(g["L"]) - 0.08)), 0.22))
        if getattr(self, "tail_piv", None) is not None and car.has("trunk"):
            out.append((("trunk", None), self.tail_piv._grip.world_position, 0.22))
            if car.trunk_open:
                for idx, e in getattr(self, "trunk_ents", []):
                    out.append((("titem", idx), e.world_position, 0.08))
                out.append((("tput", None), self._w((0, g["sill"] + 0.2, self.Z((g["trunk_z0"] + g["trunk_z1"]) / 2))), 0.3))
        self._elec_targets(out, False)
        # болты и детали
        for k, i, e, p0 in (self.bolt_ents or []):
            if e.enabled and e.parent.enabled and self._visible(e):
                out.append((("bolt", k, i), e.world_position, 0.035))
        return out

    # ---------------------------------------------------------------- электрика: блок предохранителей и места неисправностей
    def _elec_pos(self, seg):
        """Где на кузове участок цепи (локально в осях кузова)."""
        g, Z = self._geo, self.Z
        W2, L, belt, ws = g["W2"], g["L"], g["belt"], g["ws"]
        info = getattr(self, "_interior", None) or {}
        dy, dz = info.get("dash_y", belt + 0.06), info.get("dash_z", Z(ws - 0.3))
        fl = info.get("floor_y", g["floor"])
        ex = self.car.spec["eye"][0]
        if seg == "box":
            if elec.box_place(self.car) == "bay":
                return (-(W2 - 0.24), belt - 0.1, Z(ws + 0.25))
            return (max(-(W2 - 0.12), ex - 0.24), dy - 0.2, dz - 0.07)
        return {"column": (ex, dy - 0.12, dz - 0.2),
                "dash": (ex + 0.2, dy - 0.26, dz - 0.1),
                "bay_l": (-(W2 - 0.26), belt - 0.12, Z(L - 0.38)),
                "bay_r": (W2 - 0.26, belt - 0.12, Z(L - 0.38)),
                "bay_c": (0.25, belt - 0.12, Z(ws + 0.3)),
                "sill_l": (-(W2 - 0.13), fl + 0.03, Z(g["seat_z"] - 0.15)),
                "trunk": (-(W2 - 0.22), g["sill"] + 0.25, Z(g["trunk_z0"] + 0.12)),
                "tank": (-0.3, fl + 0.12, Z(g["rear_z"]))}[seg]

    def ensure_elec(self, on):
        if on and self.fusebox is None and getattr(self, "_geo", None):
            box = Entity(parent=self.body, position=self._elec_pos("box"))
            Entity(parent=box, model="cube", color=color.rgb(30, 30, 32), scale=(0.2, 0.03, 0.1))       # корпус
            box._fuses = []
            for i in range(len(elec.KEYS)):
                f = Entity(parent=box, model="cube", position=(-0.085 + (i % 5) * 0.042, 0.02, -0.022 + (i // 5) * 0.045),
                           scale=(0.02, 0.012, 0.03))
                box._fuses.append(f)
            self.fusebox = box
            self.fault_ents = {}
            self._elec_sig = None
            self._update_elec()
        elif not on and self.fusebox is not None:
            destroy(self.fusebox)
            for e in self.fault_ents.values():
                destroy(e)
            self.fusebox, self.fault_ents = None, {}

    FUSE_COL = {8: (150, 90, 60), 10: (200, 40, 40), 15: (60, 110, 210), 16: (230, 230, 225), 25: (230, 230, 225)}

    def _update_elec(self):
        car = self.car
        d = elec.data(car)
        sig = (tuple(sorted(d["fuses"].items())), tuple(sorted((k, f["kind"], f["seg"], f["found"])
                                                               for k, f in d["faults"].items())))
        if sig == self._elec_sig:
            return
        self._elec_sig = sig
        for i, k in enumerate(elec.KEYS):
            st = d["fuses"][k]
            e = self.fusebox._fuses[i]
            e.enabled = True
            e.color = color.rgb(60, 45, 35) if st == "blown" else (color.rgb(180, 170, 90) if st == "bug" else
                                                                   color.rgb(*self.FUSE_COL.get(elec.BY_KEY[k]["amp"], (200, 200, 200))))
        for e in self.fault_ents.values():
            destroy(e)
        self.fault_ents = {}
        for k, f in d["faults"].items():
            if not f["found"] or f["seg"] == "box":
                continue
            m = Entity(parent=self.body, position=self._elec_pos(f["seg"]))
            Entity(parent=m, model="cube", color=color.rgb(230, 40, 30), scale=(0.07, 0.025, 0.025))
            Entity(parent=m, model="cube", color=color.rgb(255, 200, 40), scale=(0.02, 0.05, 0.02), y=0.02)
            m.setLightOff()
            self.fault_ents[k] = m

    def elec_access(self, seg, inside):
        """Можно ли дотянуться до участка: капот/двери/багажник открыты?"""
        car = self.car
        if seg == "box":
            seg = "bay_c" if elec.box_place(car) == "bay" else "dash"
        if seg.startswith("bay"):
            return not inside and getattr(car, "hood_open", False)
        if seg in ("dash", "column"):
            return inside or car.door_open.get("l")
        if seg in ("sill_l", "tank"):
            return not inside and (car.door_open.get("l") or car.door_open.get("lb"))
        if seg == "trunk":
            return not inside and car.trunk_open
        return False

    # ---------------------------------------------------------------- багажник: предметы лежат физически
    KIND_COL = {"food": (200, 70, 50), "drink": (60, 110, 190), "part": (120, 120, 125), "tool": (200, 120, 30),
                "fluid": (60, 150, 70), "material": (140, 100, 60)}

    def _update_trunk_items(self):
        car = self.car
        items = getattr(car, "trunk_items", None) or []
        sig = tuple((e["id"], round(e.get("cond", 0))) for e in items)
        if sig == getattr(self, "_trunk_sig", None):
            return
        self._trunk_sig = sig
        for _, e in getattr(self, "trunk_ents", []):
            destroy(e)
        self.trunk_ents = []
        if not items or not getattr(self, "_geo", None):
            return
        from items import ITEMS
        g = self._geo
        z0, z1 = g["trunk_z0"] + 0.08, g["trunk_z1"] - 0.05
        W = g["W2"] - 0.2
        xl = -W + 0.62                                    # слева лежит запаска — вещи правее
        floor_y = g.get("trunk_y", g["sill"] + 0.15) + 0.02
        cols, rows = 3, 3
        for idx, it in enumerate(items):
            layer, cell = divmod(idx, cols * rows)
            r, c = divmod(cell, cols)
            x = xl + (c + 0.5) * (W - xl) / cols
            z = z0 + (r + 0.5) * (z1 - z0) / rows
            kind = ITEMS.get(it["id"], {}).get("kind", "part")
            size = (0.16, 0.1, 0.12) if kind in ("food", "drink") else (0.22, 0.12, 0.16)
            e = Entity(parent=self.body, model="cube", color=color.rgb(*self.KIND_COL.get(kind, (150, 150, 150))),
                       position=(x, floor_y + size[1] / 2 + layer * 0.13, self.Z(z)), scale=size)
            self.trunk_ents.append((idx, e))

    def _elec_targets(self, out, inside):
        if inside and self.fusebox is None:
            self.ensure_elec(True)
        if self.fusebox is None:
            return
        if self.elec_access("box", inside):
            out.append((("fusebox", None), self.fusebox.world_position, 0.12))
        for k, m in self.fault_ents.items():
            f = elec.fault(self.car, k)
            if f and self.elec_access(f["seg"], inside):
                out.append((("efault", k), m.world_position, 0.09))

    def _w(self, local):
        """Точка в осях кузова -> мир."""
        return Vec3(*scene.getRelativePoint(self.body, Vec3(*local)))

    def _visible(self, e):
        p = e.parent
        while p is not None and p is not self.root:
            if not p.enabled:
                return False
            p = p.parent
        return True
