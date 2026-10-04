"""3D трафика: машины (вблизи — полная модель Car3D, дальше — лёгкая), светофоры, пешеходы.

Уровни детализации: машины трафика ближе NEAR — полноценные Car3D (колёса крутятся и поворачиваются, подвеска,
фары, стоп-сигналы, поворотники), дальше до FAR — лёгкая коробка, ещё дальше — не рисуются (но ездят).
Пешеходы — фигурки с анимацией ходьбы в пределах PED_DIST; в дождь/снег у многих зонт.
Новые модели создаются по нескольку за кадр — без рывков.
"""
import math

from ursina import Entity, Text, color, Vec3, destroy
from panda3d.core import TransparencyAttrib

from car3d import Car3D, AICar3D
from config import VIEW_DIST, CAR_VIEW_DIST
from i18n import T

import graphics  # noqa: E402

NEAR = graphics.get("traffic_near")        # полная модель ближе этого (на «Высоком» 95 м), дальше — лёгкая
FAR = VIEW_DIST * graphics.get("traffic_far_k")
PED_DIST = graphics.get("ped_dist")


def _glow(e):
    e.setLightOff()
    return e


class TrafficView:
    def __init__(self, traffic):
        self.tr = traffic
        self.near = {}          # id(driver) -> Car3D
        self.far = {}           # id(driver) -> AICar3D
        self.lights = LightsView(traffic)
        self.peds = PedsView(traffic)
        self.visible = True

    def set_visible(self, v):
        self.visible = v
        for c3 in self.near.values():
            c3.root.enabled = v
        for a in self.far.values():
            a.root.enabled = v
        self.lights.set_visible(v)
        self.peds.set_visible(v)

    def _build(self, d):
        c3 = Car3D(d.car)
        if d.police:
            self._police_bar(c3)
        c3._vis = True
        self.near[id(d)] = c3
        return c3

    def prebuild(self, n=1):
        """Заранее собрать модели машин трафика (на титульном экране) — чтобы в игре не было рывков."""
        if NEAR <= 0:                          # сверхнизкая графика: у трафика только лёгкие модели
            return True
        done = 0
        for d in self.tr.drivers:
            if id(d) not in self.near:
                c3 = self._build(d)
                c3.root.enabled = False
                c3._vis = False
                done += 1
                if done >= n:
                    return False
        return True

    def _police_bar(self, c3):
        g = getattr(c3, "_geo", None) or {}
        roof = g.get("roof", 1.4)
        bar = Entity(parent=c3.body, model="cube", position=(0, roof + 0.07, c3.Z(g.get("rs", 1.5)) + 0.3 if g else 0),
                     scale=(0.9, 0.1, 0.22), color=color.rgb(40, 70, 160))
        for sx in (-1, 1):
            Text(T("ПОЛИЦИЯ"), parent=c3.body, position=(sx * (g.get("W2", 0.8) + 0.02), g.get("belt", 0.8) - 0.12, c3.Z(g.get("L", 4.2) / 2)),
                 rotation_y=-90 * sx, scale=5, origin=(0, 0), color=color.rgb(30, 90, 60))
        c3._siren = bar

    def update(self, dt, px, py, night, t, show=True):
        built = 0
        for d in self.tr.drivers:
            k = id(d)
            dist = abs(d.x - px) + abs(d.y - py)
            want_near = show and dist < NEAR
            want_far = show and not want_near and dist < FAR
            c3 = self.near.get(k)
            if want_near and c3 is None and built < 1:
                c3 = self._build(d)                              # модель строится один раз и потом не удаляется
                built += 1
            a = self.far.get(k)
            if (want_far or (want_near and c3 is None)) and a is None:
                a = AICar3D(d)
                self.far[k] = a
            if a is not None:
                vis = (want_far or (want_near and c3 is None))
                if getattr(a, "_vis", None) != vis:               # включать/выключать только при смене (это дорого)
                    a.root.enabled = vis
                    a._vis = vis
                if vis:
                    a.update(dt, t)
            if c3 is not None:
                vis = want_near or dist < NEAR + 25
                if getattr(c3, "_vis", None) != vis:
                    c3.root.enabled = vis
                    c3._vis = vis
                if vis:
                    c3.update(dt, d.inp, night, lazy=False)
                    sb = getattr(c3, "_siren", None)
                    if sb is not None:
                        on = d.siren > 0 and int(t * 6) % 2 == 0
                        sb.color = color.rgb(90, 150, 255) if on else color.rgb(40, 70, 160)
                        (sb.setLightOff() if on else sb.clearLight())
        self.lights.update(t, px, py, show)
        self.peds.update(dt, px, py, show)


# ======================================================================== светофоры
class LightsView:
    """На каждом светофорном перекрёстке — 4 столба (по углам) с тремя секциями навстречу потоку и
    «человечками» для пешеходов."""
    COLS = {"red": ((230, 30, 25), (60, 12, 10)), "yellow": ((250, 190, 20), (70, 55, 10)),
            "green": ((40, 230, 90), (10, 55, 25))}

    def __init__(self, traffic):
        self.tr = traffic
        self.heads = []          # (light, axis, {"red": e, ...}, walk_red, walk_green)
        self.roots = []
        for L in traffic.graph.lights:
            n = L.node
            # столб у правого угла перед перекрёстком для каждого подхода
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                # подход с направлением движения (dx,dy): машина едет в +dx; столб справа перед узлом
                rx, ry = -dy, dx
                px = n.x - dx * 7.0 + rx * 6.2
                py = n.y - dy * 7.0 + ry * 6.2
                axis = "h" if dx else "v"
                root = Entity(position=(px, 0, -py))
                Entity(parent=root, model="cube", color=color.rgb(70, 72, 75), position=(0, 1.6, 0), scale=(0.12, 3.2, 0.12))
                head = Entity(parent=root, position=(0, 3.0, 0), rotation_y=math.degrees(math.atan2(-dx, dy)))   # стёкла — навстречу подъезжающим
                Entity(parent=head, model="cube", color=color.rgb(25, 25, 28), scale=(0.34, 0.95, 0.22))
                lamps = {}
                for i, st in enumerate(("red", "yellow", "green")):
                    lamps[st] = _glow(Entity(parent=head, model="mrg_sphere_lo", position=(0, 0.3 - i * 0.3, 0.12),
                                             scale=(0.2, 0.2, 0.06), color=color.rgb(*self.COLS[st][1])))
                # пешеходный сигнал — на том же столбе, смотрит поперёк
                ped = Entity(parent=root, position=(0, 2.1, 0), rotation_y=head.rotation_y + 90)
                Entity(parent=ped, model="cube", color=color.rgb(25, 25, 28), scale=(0.26, 0.5, 0.16))
                w_red = _glow(Entity(parent=ped, model="cube", position=(0, 0.11, 0.09), scale=(0.16, 0.16, 0.02),
                                     color=color.rgb(60, 12, 10)))
                w_green = _glow(Entity(parent=ped, model="cube", position=(0, -0.11, 0.09), scale=(0.16, 0.16, 0.02),
                                       color=color.rgb(10, 55, 25)))
                cross_axis = "v" if axis == "h" else "h"      # пешеход у этого столба переходит поперечную дорогу
                self.heads.append((L, axis, lamps, w_red, w_green, cross_axis, root))
                self.roots.append(root)
        self._sig = None

    def set_visible(self, v):
        for r in self.roots:
            r.enabled = v

    def update(self, t, px, py, show):
        sig = []
        for L, axis, lamps, wr, wg, cax, root in self.heads:
            st = L.state(axis, t)
            walk = L.walk(cax, t)
            sig.append((st, walk))
        sig = tuple(sig)
        if sig == self._sig:
            return
        self._sig = sig
        for (L, axis, lamps, wr, wg, cax, root), (st, walk) in zip(self.heads, sig):
            for k, e in lamps.items():
                on, off = self.COLS[k]
                e.color = color.rgb(*(on if k == st else off))
            wr.color = color.rgb(*((230, 30, 25) if not walk else (60, 12, 10)))
            wg.color = color.rgb(*((40, 230, 90) if walk else (10, 55, 25)))


# ======================================================================== пешеходы
class Ped3D:
    def __init__(self, p):
        self.p = p
        coat, pants, skin, hair, k = p.looks
        self.root = Entity(scale=k)
        r = self.root
        self.legs = []
        for sx in (-1, 1):
            hip = Entity(parent=r, position=(sx * 0.1, 0.9, 0))
            Entity(parent=hip, model="cube", color=color.rgb(*pants), position=(0, -0.43, 0), scale=(0.14, 0.86, 0.16))
            Entity(parent=hip, model="cube", color=color.rgb(30, 28, 26), position=(0, -0.88, 0.05), scale=(0.15, 0.08, 0.26))
            self.legs.append(hip)
        Entity(parent=r, model="cube", color=color.rgb(*coat), position=(0, 1.22, 0), scale=(0.42, 0.66, 0.24))   # куртка
        Entity(parent=r, model="cube", color=color.rgb(*skin), position=(0, 1.66, 0), scale=(0.2, 0.24, 0.22))   # голова
        Entity(parent=r, model="cube", color=color.rgb(*hair), position=(0, 1.8, -0.02), scale=(0.22, 0.07, 0.24))
        self.arms = []
        for sx in (-1, 1):
            sh = Entity(parent=r, position=(sx * 0.27, 1.5, 0))
            Entity(parent=sh, model="cube", color=color.rgb(*coat), position=(0, -0.3, 0), scale=(0.11, 0.6, 0.13))
            Entity(parent=sh, model="cube", color=color.rgb(*skin), position=(0, -0.63, 0), scale=(0.09, 0.09, 0.09))
            self.arms.append(sh)
        self.umbrella = Entity(parent=self.arms[1], position=(0, -0.62, 0))
        Entity(parent=self.umbrella, model="cube", color=color.rgb(40, 40, 40), position=(0, 0.45, 0), scale=(0.02, 0.9, 0.02))
        top = Entity(parent=self.umbrella, model="mrg_sphere", position=(0, 0.95, 0), scale=(0.95, 0.25, 0.95),
                     color=color.rgb(*((30, 30, 60) if p.i % 3 else (150, 30, 30))))
        self.umbrella.enabled = False
        self._umb = p.i % 3 != 2
        self._vis = True
        self._um_on = False

    def update(self, rain):
        p = self.p
        r = self.root
        r.position = Vec3(p.x, 0, -p.y)
        if p.down > 0:
            r.rotation = Vec3(0, 90 + math.degrees(p.angle), 88)      # лежит
            return
        r.rotation = Vec3(0, 90 + math.degrees(p.angle), 0)
        sw = math.sin(p.phase) * (32 if p.speed > 0.1 else 0) * min(1.6, p.speed / 1.3)
        self.legs[0].rotation_x = sw
        self.legs[1].rotation_x = -sw
        self.arms[0].rotation_x = -sw * 0.7
        um = rain and self._umb
        if um != self._um_on:
            self.umbrella.enabled = um
            self._um_on = um
        self.arms[1].rotation_x = -80 if um else sw * 0.7
        r.y = abs(math.sin(p.phase)) * 0.03 if p.speed > 0.1 else 0.0


class PedsView:
    def __init__(self, traffic):
        self.tr = traffic
        self.views = {}
        self.visible = True
        self.rain = False

    def set_visible(self, v):
        self.visible = v
        for pv in self.views.values():
            pv.root.enabled = v

    def update(self, dt, px, py, show):
        built = 0
        for p in self.tr.peds.peds:
            d = abs(p.x - px) + abs(p.y - py)
            pv = self.views.get(p.i)
            if show and d < PED_DIST:
                if pv is None and built < 3:
                    pv = Ped3D(p)
                    self.views[p.i] = pv
                    built += 1
                if pv is not None:
                    if not pv._vis:
                        pv.root.enabled = True
                        pv._vis = True
                    pv.update(self.rain)
            elif pv is not None and pv._vis:                      # фигурка остаётся, просто прячется
                pv.root.enabled = False
                pv._vis = False
