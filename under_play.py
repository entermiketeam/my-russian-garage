"""Игрок под машиной (3D): лечь, ползать, смотреть вверх на днище, откручивать болты снизу, вылезти.

Логика доступа, просвет, домкрат и подставки — underside.py; 3D деталей низа — under3d.py.
Положение под машиной — в координатах кузова: p.uc_pos = [поперёк (x, + вправо), вдоль (z, + к носу)].
"""
import math

from ursina import camera, held_keys, scene, Vec3

import underside as U
from state import RED, GREEN, YELLOW
from i18n import T

EYE_LYING = 0.17           # глаза лежащего на подкатном лежаке
CRAWL = 0.6                # м/с
REACH = 1.25               # дотянуться рукой (с подкатного лежака можно приподняться)
TIRES = ("tire_fl", "tire_fr", "tire_rl", "tire_rr")


class UnderMixin:
    underside_rules = True

    # ------------------------------------------------------------ геометрия
    def _uc_world(self, c3, lx, lz, y=0.0):
        """Точка кузова (поперёк, вдоль) → мир (x, y 2D)."""
        p = scene.getRelativePoint(c3.root, Vec3(lx, y, lz))
        return p[0], -p[2]

    def _uc_free(self, car, lx, lz):
        """Можно ли лежать в этой точке под машиной: колёса, просвет."""
        sp = car.spec
        W2 = sp["width"] / 2
        tr, wr = sp["track"], sp["wheel_r"]
        for ax in sp["axles"]:
            az = ax - car.length / 2
            if abs(lx) > tr - 0.3 and abs(lz - az) < wr + 0.15:
                return False, T("колесо")
        c = U.clearance(car, U.t_of(car, lz))
        inside = abs(lx) < W2 - 0.35 and abs(lz) < car.length / 2 - 0.3
        if inside and c < U.FREE:
            return False, T("тесно ({0:.0f} см) — дальше не пролезть, поднимите машину", c * 100)
        if abs(lx) < W2 + 0.1 and c < U.MIN_CRAWL:
            return False, T("не пролезть ({0:.0f} см)", c * 100)
        return True, ""

    # ------------------------------------------------------------ лечь / вылезти
    def crawl_under(self, key, side):
        car = self.cars[key]
        c3 = self.car3ds.get(key)
        if c3 is None:
            return
        if car.running:
            self.notify(T("Под работающую машину не лезут — заглушите двигатель."), RED)
            return
        if abs(car.speed) > 0.1:
            return
        fx, fy = math.cos(car.angle), math.sin(car.angle)
        lz = (self.p.x - car.x) * fx + (self.p.y - car.y) * fy
        lz = max(-car.length / 2 + 0.7, min(car.length / 2 - 0.7, lz))
        W2 = car.spec["width"] / 2
        lx = side * (W2 - 0.2)
        ok, why = self._uc_free(car, lx, lz)
        if not ok:
            for dz in (0.5, -0.5, 1.0, -1.0):          # рядом с колесом — сдвинуться вдоль порога
                ok, why2 = self._uc_free(car, lx, lz + dz)
                if ok:
                    lz += dz
                    break
        if not ok:
            c = U.clearance(car, U.t_of(car, lz))
            self.notify(T("Под машину не пролезть: просвет {0:.0f} см. Поднимите её домкратом "
                        "(E на переднем или заднем бампере внизу) и поставьте на подставки.", c * 100), RED, 8)
            return
        self.cur = key
        self.p.under_car = key
        self.p.uc_pos = [lx, lz]
        self._uc_look = [-72.0, 0.0]
        c3.bay.enabled = True                          # снизу двигатель видно и при закрытом капоте
        self._uc_lamp(True)
        c = U.clearance(car, U.t_of(car, lz))
        self.play_sound("step", 0.5)
        msg = (T("Вы под машиной (просвет {0:.0f} см). WASD — ползти, мышь — смотреть, E/G — болты и детали, "
               "Tab — руки, F — вылезти.", c * 100))
        if c < U.FREE:
            msg += T(" Тесно: пролезли только голова и плечи — крупное не снять.")
        if "jack" in (U.held_by(car, "f"), U.held_by(car, "r")):
            msg += T(" ⚠ Машина на одном домкрате — может соскочить!")
        self.notify(msg, YELLOW if c >= U.FREE else RED, 9)

    def crawl_out(self, side=None):
        key = self.p.under_car
        if not key:
            return
        car = self.cars[key]
        c3 = self.car3ds.get(key)
        lx, lz = self.p.uc_pos
        W2 = car.spec["width"] / 2
        L2 = car.length / 2
        cands = []
        if side is None:
            side = 1 if lx >= 0 else -1
        if abs(lz) > L2 - 0.2:
            cands.append((lx, math.copysign(L2 + 0.6, lz)))
        cands += [(side * (W2 + 0.6), lz), (-side * (W2 + 0.6), lz), (0, L2 + 0.7), (0, -L2 - 0.7)]
        x, y = car.x, car.y
        for cx, cz in cands:
            x, y = self._uc_world(c3, cx, cz) if c3 is not None else (car.x, car.y)
            if not self.world.collide_circle(x, y, 0.35):
                break
        self.on_crawl_out(key, (x, y))

    def on_crawl_out(self, key, pos):
        """Игрок больше не под машиной (вылез сам или выкатился, когда соскочил домкрат)."""
        car = self.cars.get(key)
        c3 = self.car3ds.get(key)
        if pos is None and car is not None and c3 is not None:
            W2 = car.spec["width"] / 2
            lx, lz = getattr(self.p, "uc_pos", [W2, 0.0])
            pos = self._uc_world(c3, math.copysign(W2 + 0.7, lx or 1), lz)
        self.p.under_car = None
        if pos:
            self.p.x, self.p.y = pos
        if car is not None:
            dx, dy = car.x - self.p.x, car.y - self.p.y
            self.yaw = math.degrees(math.atan2(dx, -dy))
            self.pitch = 15
        if c3 is not None:
            c3.bay.enabled = getattr(car, "hood_open", False) or not car.has("hood")
        self._uc_lamp(False)
        camera.parent = scene

    def _uc_lamp(self, on):
        """Переноска (Handlampe): под машиной солнце не светит — лампа у лица, светит на днище."""
        from panda3d.core import PointLight
        np_ = getattr(self, "_uc_lamp_np", None)
        if on and np_ is None:
            pl = PointLight("uc_lamp")
            pl.setColor((1.5, 1.42, 1.25, 1))
            pl.setAttenuation((1.0, 0.0, 0.9))
            np_ = scene.attachNewNode(pl)
            scene.setLight(np_)
            self._uc_lamp_np = np_
        elif not on and np_ is not None:
            scene.clearLight(np_)
            np_.removeNode()
            self._uc_lamp_np = None

    # ------------------------------------------------------------ кадр под машиной
    def update_under(self, dt, free):
        p = self.p
        key = p.under_car
        car = self.cars.get(key)
        c3 = self.car3ds.get(key)
        if car is None or c3 is None or self.location != "street":
            p.under_car = None
            return []
        lx, lz = p.uc_pos
        if free:
            dx, dy = self.mouselook.dx * self.sens, self.mouselook.dy * self.sens
            self._uc_look[0] = max(-89.0, min(25.0, self._uc_look[0] + dy))
            self._uc_look[1] = max(-120.0, min(120.0, self._uc_look[1] + dx))
            fwd = (held_keys["w"] or held_keys["up arrow"]) - (held_keys["s"] or held_keys["down arrow"])
            side = (held_keys["d"] or held_keys["right arrow"]) - (held_keys["a"] or held_keys["left arrow"])
            if fwd or side:
                st = CRAWL * dt
                W2 = car.spec["width"] / 2
                L2 = car.length / 2
                for nx, nz in ((lx + side * st, lz), (lx, lz + fwd * st)):
                    if abs(nx) > W2 + 0.35:                  # выползли из-под борта
                        self.crawl_out(1 if nx > 0 else -1)
                        return []
                    if abs(nz) > L2 + 0.3:                   # выползли спереди / сзади
                        p.uc_pos = [nx, nz]
                        self.crawl_out()
                        return []
                    ok, why = self._uc_free(car, nx, nz)
                    if ok:
                        lx, lz = nx, nz
                    elif getattr(self, "_uc_why_t", 0) <= 0:
                        self.notify(T("Дальше нельзя: ") + why + ".", YELLOW, 2.5)
                        self._uc_why_t = 2.5
                p.uc_pos = [lx, lz]
                self.bob += dt * 5
        self._uc_why_t = max(0.0, getattr(self, "_uc_why_t", 0.0) - dt)
        x, y = self._uc_world(c3, lx, lz)
        p.x, p.y = x, y
        camera.parent = scene
        camera.position = Vec3(x, EYE_LYING + math.sin(self.bob) * 0.006, -y)
        camera.rotation = Vec3(self._uc_look[0], c3.root.rotation_y + self._uc_look[1], 0)
        lamp = getattr(self, "_uc_lamp_np", None)
        if lamp is None:
            self._uc_lamp(True)
            lamp = self._uc_lamp_np
        lamp.setPos(x, EYE_LYING + 0.12, -y)
        c3.bay.enabled = True
        return self._under_prompt(car, lx, lz)

    def _under_prompt(self, car, lx, lz):
        c = U.clearance(car, U.t_of(car, lz))
        st = U.status(car)
        return [T("Под машиной: просвет {0:.0f} см", c * 100) + (T(" · поднято: {st}", st=st) if st else T(" · на колёсах"))
                + (T("  ⚠ ОДИН ДОМКРАТ") if "jack" in (U.held_by(car, "f"), U.held_by(car, "r")) else "")]

    # ------------------------------------------------------------ прицел
    def _uc_filter(self, key, tl):
        """Что достаётся из текущего положения: лёжа — только низ (и колёса), стоя — только верх."""
        lying = self.p.under_car == key
        out = []
        for tid, pos, r in tl:
            kind = tid[0]
            if kind in ("bolt", "part", "place"):
                k = tid[1]
                under = U.is_under(k)
                if lying and not (under or k in TIRES):
                    continue
                if not lying and under:
                    continue
            elif lying:
                continue                                      # двери, капот, сиденья — не из-под машины
            out.append((tid, pos, r))
        return out

    def _uc_targets(self, key, c3):
        """Стоя у своей машины: «лечь под машину» у порогов, домкрат у бамперов."""
        car = self.cars[key]
        if not self.owned.get(key) or self.p.under_car:
            return []
        W2 = car.spec["width"] / 2
        L2 = car.length / 2
        out = []
        for sg in (-1, 1):
            out.append((("under", sg), Vec3(*_w(c3, sg * (W2 + 0.05), 0.12, 0.0)), 0.45))
        out.append((("jackpt", "f"), Vec3(*_w(c3, 0, 0.18, L2 + 0.05)), 0.3))
        out.append((("jackpt", "r"), Vec3(*_w(c3, 0, 0.18, -L2 - 0.05)), 0.3))
        return out

    def _uc_action(self, key, tid):
        car = self.cars[key]
        kind = tid[0]
        if kind == "under":
            sg = tid[1]
            fx, fy = math.cos(car.angle), math.sin(car.angle)
            lz = (self.p.x - car.x) * fx + (self.p.y - car.y) * fy
            c = U.clearance(car, U.t_of(car, max(-car.length / 2, min(car.length / 2, lz))))
            tag = "" if c >= U.FREE else (T(" — тесно, только голова и плечи") if c >= U.MIN_CRAWL else T(" — не пролезть"))
            return (T("Лечь под машину ({0}, просвет {1:.0f} см{tag})", T('справа') if sg > 0 else T('слева'), c * 100, tag=tag),
                    lambda: self.crawl_under(key, sg), None)
        if kind == "jackpt":
            end = tid[1]
            nm = U.END_RU[end]
            by = U.held_by(car, end)
            if by is None:
                return (T("Поднять {nm} домкратом", nm=nm) + ("" if self.has("jack") else T(" (нужен домкрат)")),
                        lambda: U.jack_up(self, key, end), None)
            if by == "jack":
                return (T("Поставить {nm} на подставки", nm=nm) + ("" if self.has("stands") else T(" (нужны подставки)")),
                        lambda: U.put_stands(self, key, end),
                        (T("Опустить {nm} (убрать домкрат)", nm=nm), lambda: U.lower(self, key, end)))
            return (T("Снять {nm} с подставок и опустить", nm=nm) + ("" if self.has("jack") else T(" (нужен домкрат)")),
                    lambda: U.lower(self, key, end), None)
        return None

    def open_underwork(self):
        from actions import CarWork
        if self.p.under_car:
            self.cur = self.p.under_car
            self.open_menu(CarWork(self))


def _w(c3, x, y, z):
    p = scene.getRelativePoint(c3.root, Vec3(x, y, z))
    return p[0], p[1], p[2]
