"""Интерфейс 3D-версии (Ursina camera.ui): HUD, приборка, меню, карта, уведомления."""
import math

from places import INTERIOR_X
import random

from ursina import Entity, Text, camera, color, window, Vec3, destroy

import graphics
from car import GEAR_NAMES, TANK
from world import BUILDINGS, ROADS, MAP_W, MAP_H
from i18n import T

UI = camera.ui
AR = window.aspect_ratio
LEFT, RIGHT = -AR / 2, AR / 2


def safe(s):
    return str(s).replace("<", "‹").replace(">", "›")


def text_w(s, size=1.0):
    """Ширина надписи на экране (кириллица шире латиницы — считаем по-настоящему, а не по числу букв)."""
    return Text.get_width(safe(s)) * size


def wrap(s, maxw, size):
    """Разбить строку по словам, чтобы каждая часть влезала в maxw."""
    out = []
    s = safe(s)
    while s and text_w(s, size) > maxw:
        words = s.split(" ")
        cut = 1
        for i in range(1, len(words) + 1):
            if text_w(" ".join(words[:i]), size) > maxw:
                break
            cut = i
        out.append(" ".join(words[:cut]))
        s = " ".join(words[cut:]).lstrip()
    out.append(s)
    return out


def rgb(c, a=255):
    return color.rgba(c[0], c[1], c[2], a)


def panel(x, y, w, h, a=215, parent=UI, z=0):
    """Прямоугольник по левому верхнему углу."""
    return Entity(parent=parent, model="quad", color=color.rgba(18, 20, 26, a), origin=(-0.5, 0.5),
                  position=(x, y, z), scale=(w, h))


def label(s, x, y, size=1.0, col=(240, 240, 235), parent=UI, origin=(-0.5, 0.5), z=-0.01, **kw):
    return Text(safe(s), parent=parent, position=(x, y, z), scale=size, origin=origin, color=rgb(col), **kw)


class Bar:
    def __init__(self, x, y, w, h, name, parent=UI):
        self.bg = Entity(parent=parent, model="quad", origin=(-0.5, 0.5), position=(x, y, -0.01), scale=(w, h),
                         color=color.rgba(45, 45, 50, 255))
        self.fill = Entity(parent=parent, model="quad", origin=(-0.5, 0.5), position=(x, y, -0.02), scale=(w, h),
                           color=color.green)
        self.w = w
        self.txt = label(name, x + 0.006, y - 0.003, 0.7, z=-0.03, parent=parent) if name else None

    def set(self, v, maxv=100.0, col=None):
        k = max(0.0, min(1.0, v / maxv))
        self.fill.scale_x = max(0.0001, self.w * k)
        if col is None:
            col = (90, 190, 90) if k > 0.5 else ((230, 140, 40) if k > 0.25 else (210, 60, 50))
        self.fill.color = rgb(col)

    def show(self, v):
        self.bg.enabled = self.fill.enabled = v
        if self.txt:
            self.txt.enabled = v


class HUD:
    def __init__(self, game):
        self.g = game
        self.root = Entity(parent=UI)
        r = self.root
        # время / место
        panel(LEFT + 0.01, 0.49, 0.62, 0.105, parent=r)
        self.time_t = label("", LEFT + 0.022, 0.482, 1.05, parent=r)
        self.place_t = label("", LEFT + 0.022, 0.447, 0.75, (170, 170, 170), parent=r)
        self.goal_t = label("", LEFT + 0.022, 0.418, 0.72, (240, 200, 60), parent=r)
        # деньги + потребности
        panel(RIGHT - 0.53, 0.49, 0.52, 0.075, parent=r)
        self.money_t = label("", RIGHT - 0.52, 0.48, 1.05, (110, 220, 110), parent=r)
        self.bars = []
        names = [T("Сытость"), T("Жажда"), T("Бодрость"), T("Гигиена")]
        for i, n in enumerate(names):
            x = RIGHT - 0.35 + (i % 2) * 0.17
            y = 0.483 - (i // 2) * 0.034
            self.bars.append(Bar(x, y, 0.16, 0.028, n, parent=r))
        self.extra_t = label("", RIGHT - 0.52, 0.448, 0.65, (230, 140, 40), parent=r)
        # прицел
        self.cross = Entity(parent=r, model="circle", scale=0.006, color=color.rgba(255, 255, 255, 180))
        # подсказка
        self.prompt_bg = panel(-0.3, -0.33, 0.6, 0.05, parent=r)
        self.prompt_t = label("", 0, -0.355, 0.95, (240, 200, 60), parent=r, origin=(0, 0))
        self.prompt2_t = label("", 0, -0.395, 0.8, (240, 240, 235), parent=r, origin=(0, 0))
        # доставка
        self.deliv_bg = panel(-0.26, 0.49, 0.52, 0.045, parent=r)
        self.deliv_t = label("", 0, 0.468, 0.85, parent=r, origin=(0, 0))
        self.arrow = Text("▲", parent=r, position=(0, 0.42, -0.01), origin=(0, 0), scale=2, color=rgb((240, 200, 60)))
        # уведомления
        self.notes = []
        self.note_ts = [label("", LEFT + 0.02, -0.25 - i * 0.032, 0.85, parent=r) for i in range(7)]
        # приборка
        self.dash = Dashboard(r)
        # вспышка / затемнение
        self.flash = Entity(parent=UI, model="quad", scale=(3, 2), color=color.rgba(255, 255, 255, 0), z=-0.5)
        self.fade = Entity(parent=UI, model="quad", scale=(3, 2), color=color.rgba(0, 0, 0, 0), z=-0.4)
        self.flash_a = 0.0
        self.fade_a = 0.0
        # дождь на экране
        self.rain = [Entity(parent=UI, model="quad", scale=(0.0015, 0.045), color=color.rgba(190, 200, 225, 110),
                            position=(random.uniform(LEFT, RIGHT), random.uniform(-0.5, 0.5), -0.1))
                     for _ in range(graphics.get("precip"))]            # число капель — по уровню графики
        self._cache = {}
        # что в руках (левая / правая) — внизу по краям экрана
        self.hand_t = [label("", LEFT + 0.02, -0.455, 0.8, (235, 225, 190), parent=r, z=-0.02),
                       label("", RIGHT - 0.02, -0.455, 0.8, (235, 225, 190), parent=r, origin=(0.5, 0.5), z=-0.02)]
        # тёмная подложка — подписи читаются и на фоне рук/снега
        self.hand_bg = [panel(LEFT + 0.012, -0.447, 0.1, 0.03, a=200, parent=r, z=-0.01),
                        panel(RIGHT - 0.112, -0.447, 0.1, 0.03, a=200, parent=r, z=-0.01)]

    def destroy(self):
        for e in [self.root, self.flash, self.fade] + self.rain:
            destroy(e)

    def notify(self, s, col=(240, 240, 235), t=5.0):
        self.notes.append([safe(s), t, col])
        self.notes = self.notes[-7:]

    def _set(self, key, ent, text):
        if self._cache.get(key) != text:
            self._cache[key] = text
            ent.text = text

    def update(self, dt, state):
        g = self.g
        p = g.p
        visible = state["hud"]
        self.root.enabled = visible
        # уведомления
        for n in self.notes:
            n[1] -= dt
        self.notes = [n for n in self.notes if n[1] > 0]
        for i, t in enumerate(self.note_ts):
            if i < len(self.notes):
                s, tl, col = self.notes[-1 - i]
                self._set(("n", i), t, s)
                a = min(1.0, tl)
                t.color = rgb(col, int(255 * a))
            else:
                self._set(("n", i), t, "")
        # вспышка / затемнение
        self.flash_a = max(0.0, self.flash_a - dt * 2.5)
        self.flash.color = color.rgba(255, 255, 255, int(220 * self.flash_a))
        self.fade.color = color.rgba(0, 0, 0, int(255 * self.fade_a))
        hs = state.get("hands")
        for i, t in enumerate(self.hand_t):
            t.enabled = hs is not None
            self.hand_bg[i].enabled = bool(hs) and bool(hs[i])
            if hs:
                self._set(("h", i), t, safe(hs[i]))
                bw = text_w(hs[i], 0.8) + 0.016
                bg = self.hand_bg[i]
                if abs(bg.scale_x - bw) > 1e-4:
                    bg.scale_x = bw
                    bg.x = LEFT + 0.012 if i == 0 else RIGHT - 0.012 - bw
        # осадки: снег — медленные хлопья, мокрый снег — косые капли
        precip = state.get("precip") if visible else None
        if precip != getattr(self, "_precip", None):
            self._precip = precip
            for i, d in enumerate(self.rain):
                d.enabled = precip is not None          # включать/выключать — только при смене погоды
                if precip == "snow":
                    sz = random.uniform(0.003, 0.0075)
                    d.scale = (sz, sz)
                    d.color = color.rgba(245, 248, 255, random.randint(130, 220))
                else:
                    d.scale = (0.0018, 0.032)
                    d.color = color.rgba(200, 208, 225, 120)
        if precip is not None:
            spd = state.get("speed", 0.0)
            # капли двигаются напрямую через Panda3D (setX/setY) — без медленного __setattr__ Ursina на каждую
            snow = precip == "snow"
            for i, d in enumerate(self.rain):
                y, x = d.getY(), d.getX()
                if snow:
                    y -= dt * (0.16 + (i % 7) * 0.025 + spd * 0.01)
                    x += dt * (math.sin(i * 1.7 + y * 9) * 0.03 - 0.015)
                else:
                    y -= dt * (1.1 + spd * 0.02)
                    x -= dt * 0.12
                if y < -0.55:
                    y = 0.55
                    x = random.uniform(LEFT, RIGHT)
                d.setX(x)
                d.setY(y)
        if not visible:
            return
        self._set("time", self.time_t, g.time_str())
        if g.p.x >= INTERIOR_X:
            wth = T("под землёй, {ambient_temp:+.0f}°C", ambient_temp=g.ambient_temp(g.p.x))
        else:
            wth = f"{g.weather_text()}, {g.ambient_temp():+.0f}°C"
        self._set("place", self.place_t, f"{state['place']}  ·  {wth}")
        self._set("money", self.money_t, f"{p.money:.2f} ₽")
        self._set("goal", self.goal_t, g.goal_text())
        self.money_t.color = rgb((110, 220, 110) if p.money >= 0 else (220, 70, 60))
        for b, v in zip(self.bars, (p.hunger, p.thirst, p.energy, p.hygiene)):
            b.set(v)
        extra = ""
        if p.drunk > 10:
            extra = T("Опьянение {drunk:.0f}%", drunk=p.drunk)
        elif p.health < 100:
            extra = T("Здоровье {health:.0f}%", health=p.health)
        self._set("extra", self.extra_t, extra)
        self.cross.enabled = state.get("cross", False)
        if self.cross.enabled:
            self.cross.color = color.rgb(255, 210, 60) if state.get("aim") else color.rgb(240, 240, 235)
        pr = state.get("prompt", [])
        self.prompt_bg.enabled = bool(pr)
        self._set("pr1", self.prompt_t, pr[0] if pr else "")
        self._set("pr2", self.prompt2_t, pr[1] if len(pr) > 1 else "")
        key = (self._cache.get("pr1"), self._cache.get("pr2"))
        if pr and key != getattr(self, "_pr_key", None):
            # плашка — по ширине текста; не помещается в экран — шрифт мельче
            self._pr_key = key
            maxw = RIGHT - LEFT - 0.06
            s1 = min(0.95, 0.95 * maxw / max(0.01, text_w(key[0] or "", 0.95)))
            s2 = min(0.8, 0.8 * maxw / max(0.01, text_w(key[1] or "", 0.8)))
            self.prompt_t.scale = s1
            self.prompt2_t.scale = s2
            w = max(0.3, text_w(key[0] or "", s1), text_w(key[1] or "", s2)) + 0.04
            two = bool(key[1])
            self.prompt_bg.scale = (w, 0.09 if two else 0.05)
            self.prompt_bg.x = -w / 2
        # доставка
        d = g.delivery
        self.deliv_bg.enabled = self.arrow.enabled = self.deliv_t.enabled = bool(d)
        if d:
            left = d["deadline"] - g.minutes
            dist = math.hypot(d["x"] - p.x, d["y"] - p.y)
            self._set("dl", self.deliv_t, T("Доставка пиццы: {0:.0f} мин  ·  {dist:.0f} м", max(0, left), dist=dist))
            self.deliv_t.color = rgb((110, 220, 110) if left > 15 else ((230, 140, 40) if left > 0 else (220, 70, 60)))
            ang = math.degrees(math.atan2(d["x"] - p.x, -(d["y"] - p.y)))
            self.arrow.rotation_z = ang - state.get("yaw", 0)
        self.dash.update(g, state.get("driving", False), state.get("clutch", False))


class Dashboard:
    def __init__(self, parent):
        self.root = Entity(parent=parent)
        r = self.root
        panel(-0.46, -0.39, 0.92, 0.105, parent=r, a=225)
        self.speed = label("0", -0.44, -0.395, 2.6, parent=r)
        label(T("км/ч"), -0.33, -0.42, 0.75, (150, 150, 150), parent=r)
        self.odo = label("", -0.44, -0.462, 0.65, (150, 150, 150), parent=r)
        self.rpm_t = label("", -0.25, -0.397, 0.75, parent=r)
        self.rpm = Bar(-0.25, -0.425, 0.27, 0.02, None, parent=r)
        self.redline = Entity(parent=r, model="quad", color=color.rgb(220, 50, 40), origin=(-0.5, 0.5),
                              position=(-0.25 + 0.27 * 5600 / 7000, -0.42, -0.03), scale=(0.003, 0.03))
        self.gear = label("N", 0.05, -0.39, 2.8, (240, 200, 60), parent=r)
        label(T("Бензин"), -0.25, -0.452, 0.6, (150, 150, 150), parent=r)
        self.fuel = Bar(-0.19, -0.455, 0.09, 0.014, None, parent=r)
        self.temp = label("", -0.09, -0.448, 0.7, parent=r)
        self.boost = label("", -0.09, -0.472, 0.65, (120, 200, 240), parent=r)
        self.drift = label("", -0.46, -0.335, 1.1, (255, 170, 60), parent=r)
        label(T("АКБ"), -0.25, -0.473, 0.6, (150, 150, 150), parent=r)
        self.batt = Bar(-0.19, -0.476, 0.09, 0.014, None, parent=r)
        self.lamps = []
        names = [T("МАСЛО"), T("ЗАРЯД"), T("ПОДСОС"), T("ФАРЫ"), T("СЦЕПЛ.")]
        for i, n in enumerate(names):
            x = 0.16 + (i % 3) * 0.1
            y = -0.405 - (i // 3) * 0.035
            dot = Entity(parent=r, model="circle", scale=0.014, position=(x, y - 0.009, -0.02), color=color.dark_gray)
            t = label(n, x + 0.012, y, 0.6, (160, 160, 160), parent=r)
            self.lamps.append((dot, t))
        self.sign = Entity(parent=r, model="circle", scale=0.075, position=(0.52, -0.335, -0.02), color=color.rgb(210, 40, 40))
        Entity(parent=self.sign, model="circle", scale=0.78, z=-0.01, color=color.white)
        self.sign_t = label("50", 0.52, -0.335, 1.1, (10, 10, 10), parent=r, origin=(0, 0), z=-0.05)
        self.hint = label("", -0.46, -0.365, 0.75, (240, 200, 60), parent=r)
        self._last = {}

    def _s(self, k, ent, v):
        if self._last.get(k) != v:
            self._last[k] = v
            ent.text = v

    def update(self, g, driving, clutch):
        self.root.enabled = driving
        if not driving:
            return
        car = g.car
        self._s("sp", self.speed, f"{car.kmh():3.0f}")
        self._s("odo", self.odo, T("{odometer:09.1f} км", odometer=car.odometer))
        self._s("rpm", self.rpm_t, T("об/мин {rpm:4.0f}", rpm=car.rpm))
        top = car.spec["cut"] + 1400
        self.redline.x = -0.25 + 0.27 * car.spec["cut"] / top
        self.rpm.set(car.rpm, top, (220, 60, 50) if car.rpm > car.spec["cut"] - 400 else (90, 190, 90))
        self._s("g", self.gear, GEAR_NAMES[car.gear])
        self.fuel.set(car.fuel, car.tank)
        self.batt.set(car.battery_charge)
        self._s("t", self.temp, f"{car.temp:.0f}°C")
        self.temp.color = rgb((220, 60, 50) if car.temp > 105 else (240, 240, 235))
        da = abs(math.degrees(car.drift_angle))
        self._s("drift", self.drift, T("ЗАНОС {da:.0f}°", da=da) if da > 10 and car.kmh() > 12 else "")
        self._s("boost", self.boost, T("Турбо {boost_now:+.2f} бар", boost_now=car.boost_now) if car.has_tune("turbo") else "")
        states = [(car.oil < 1.3 and (car.running or car.cranking), (210, 60, 50)),
                  ((not car.running and car.battery_charge > 5) or car.c("belt") < 0.05, (210, 60, 50)),
                  (car.choke, (230, 140, 40)), (car.lights, (80, 140, 220)), (clutch, (200, 200, 200))]
        for (dot, t), (on, col) in zip(self.lamps, states):
            dot.color = rgb(col) if on else color.rgb(50, 50, 55)
        lim = g.world.speed_limit(car.x, car.y)
        self._s("lim", self.sign_t, str(lim) if lim else "∞")
        hint = ""
        if not car.running:
            hint = T("I (держать) — стартер") + (T("   C — подсос") if car.temp < 45 and not car.choke else "")
        self._s("hint", self.hint, hint)


class MenuView:
    """Рисует модель меню из actions.py."""

    def __init__(self):
        self.root = None
        self.index = 0
        self.scroll = 0
        self.model = None

    def close(self):
        if self.root:
            destroy(self.root)
            self.root = None
        self.model = None

    def show(self, model, reset=False):
        if model is not self.model or reset:
            self.index = model.start_index() if hasattr(model, "start_index") else 0   # курсор — на текущем пункте
            self.scroll = 0
        self.model = model
        self.render()

    def items(self):
        return self.model.items() if self.model else []

    def render(self):
        if self.root:
            destroy(self.root)
        m = self.model
        items = m.items()
        if self.index >= len(items):
            self.index = max(0, len(items) - 1)
        title_screen = getattr(m, "title_screen", False)
        self.root = Entity(parent=UI, z=-0.2)
        r = self.root
        if title_screen:
            label("MY RUSSIAN GARAGE", LEFT + 0.06, 0.4, 3.2, (235, 205, 95), parent=r)
            label(T("ВАЗ 2102 · Германия · 1998 · 3D"), LEFT + 0.065, 0.3, 1.4, parent=r)
            label(T("ржавая «двойка», квартира, работа и техосмотр — гаражная жизнь в 1998 году"), LEFT + 0.065, 0.25, 0.9,
                  (170, 170, 170), parent=r)
            x, y, w = LEFT + 0.07, 0.12, 0.5
            rows = 8
            size = 1.4
            lines = []
        else:
            wide = getattr(m, "wide", False)
            w = 1.2 if wide else 0.95
            rows = 14 if wide else 11
            size = 0.95
            nrows = min(rows, len(items))
            src = m.lines()
            k = 1.0
            while True:                               # длинный текст — шрифт мельче, пока не влезет в экран
                lines = []
                for l in src:
                    lines += wrap(l, w - 0.05, 0.9 * k) if l else [""]
                if 0.09 + len(lines) * 0.032 * k + nrows * 0.038 + 0.06 <= 0.96 or k <= 0.6:
                    break
                k -= 0.04
            lh = 0.032 * k
            h = 0.09 + len(lines) * lh + nrows * 0.038 + 0.06
            h = min(h, 0.96)
            x = -w / 2
            y = h / 2
            if getattr(m, "side", False):
                x = RIGHT - w - 0.02
                y = 0.40
            if not getattr(m, "time_flows", False):
                Entity(parent=r, model="quad", scale=(3, 2), color=color.rgba(0, 0, 0, 110), z=0.02)
            panel(x, y, w, h, a=240, parent=r, z=0.01)
            label(m.title, x + 0.025, y - 0.02, 1.35, (240, 200, 60), parent=r)
            yy = y - 0.075
            for l in lines:
                label(l, x + 0.025, yy, 0.9 * k, parent=r)
                yy -= lh
            y = yy - 0.01
            x += 0.03
            w -= 0.06
        if self.index < self.scroll:
            self.scroll = self.index
        if self.index >= self.scroll + rows:
            self.scroll = self.index - rows + 1
        step = 0.038 * size / 0.95
        for i, it in enumerate(items[self.scroll:self.scroll + rows]):
            idx = i + self.scroll
            enabled = len(it) < 3 or it[2]
            sel = idx == self.index
            if sel:
                Entity(parent=r, model="quad", origin=(-0.5, 0.5), position=(x - 0.01, y + 0.004, 0.005),
                       scale=(w + 0.02, step * 0.95), color=color.rgba(80, 75, 30, 255))
            col = ((240, 200, 60) if sel else (240, 240, 235)) if enabled else (120, 120, 120)
            lab = it[0]
            if isinstance(lab, (list, tuple)):
                # слева — название, справа — время/цена: не даём им наехать друг на друга
                wl, wr = text_w(lab[0], size), text_w(lab[1], size)
                k = min(1.0, (w - 0.02) / max(0.01, wl + wr)) if wl + wr > w - 0.02 else 1.0
                label(lab[0], x, y, size * max(0.72, k), col, parent=r)
                label(lab[1], x + w, y, size * max(0.72, k), col, parent=r, origin=(0.5, 0.5))
            else:
                lw = text_w(lab, size)
                label(lab, x, y, size * max(0.72, min(1.0, w / max(0.01, lw))), col, parent=r)
            y -= step
        if len(items) > rows:
            label(f"{self.index + 1}/{len(items)}", x + w, y, 0.7, (150, 150, 150), parent=r, origin=(0.5, 0.5))
        if not title_screen:
            label(m.hint(), x - 0.005, y - 0.018, 0.7, (150, 150, 150), parent=r)

    def key(self, k):
        """Возвращает ('select', payload) / ('back',) / None."""
        items = self.items()
        if k in ("w", "up arrow"):
            if items:
                self.index = (self.index - 1) % len(items)
                self.render()
        elif k in ("s", "down arrow"):
            if items:
                self.index = (self.index + 1) % len(items)
                self.render()
        elif k in ("enter", "e", "space"):
            if items:
                it = items[self.index]
                if len(it) < 3 or it[2]:
                    return ("select", it[1])
        elif k in ("escape", "tab", "backspace"):
            return ("back",)
        return None


MAP_SHORT = {"apartment": T("Дом"), "imbiss": T("Закусочная"), "pizzeria": T("Пиццерия"), "supermarkt": T("Супермаркет"),
             "rathaus": T("Ратуша"), "autoteile": T("Запчасти"), "tanke": T("Заправка"), "tuv": T("Техосмотр"), "polizei": T("Полиция"),
             "lager": T("Склад"), "kirche": T("Церковь"), "bahnhof": T("Вокзал"), "schrott": T("Разборка"),
             "autohaus": T("Автосалон"), "dealer": T("Автоплощадка")}


class MapView:
    def __init__(self, tex, size):
        self._args = (tex, size)
        h = 0.9
        w = h * MAP_W / MAP_H
        self.w, self.h = w, h
        self.root = Entity(parent=UI, z=-0.3, enabled=False)
        Entity(parent=self.root, model="quad", scale=(3, 2), color=color.rgba(0, 0, 0, 200), z=0.02)
        self.map = Entity(parent=self.root, model="quad", texture=tex, scale=(w, h), position=(0, 0.02, 0.01))
        self._placed = []
        self.me = Entity(parent=self.root, model="circle", scale=0.016, color=color.red, z=-0.02)
        self.car = Entity(parent=self.root, model="circle", scale=0.014, color=color.rgb(230, 200, 60), z=-0.02)
        self.ae = Entity(parent=self.root, model="circle", scale=0.014, color=color.rgb(250, 250, 250), z=-0.02)
        self.wreck_dots = [Entity(parent=self.root, model="circle", scale=0.012, color=color.rgb(150, 150, 150),
                                  z=-0.02, enabled=False) for _ in range(12)]
        self.mine_dots = [Entity(parent=self.root, model="circle", scale=0.014, color=color.rgb(90, 200, 230),
                                 z=-0.02, enabled=False) for _ in range(16)]
        self.target = Entity(parent=self.root, model="circle", scale=0.02, color=color.rgb(255, 230, 60), z=-0.02)
        label(T("Кляйнбрук (Нижняя Саксония) · вы — красная · ВАЗ — жёлтая · AE86 — белая · ваши находки — голубые · брошенные — серые · заброшенные гаражи — коричневые · M/Esc — закрыть"),
              0, -0.465, 0.75, parent=self.root, origin=(0, 0))

    def rebuild(self):
        """Пересоздать все подписи карты (после смены языка)."""
        was, args = self.root.enabled, self._args
        destroy(self.root)
        self.__dict__.clear()                      # ag_marks и т. п. построятся заново при первом update()
        self.__init__(*args)
        self.root.enabled = was

    def _label_buildings(self, squares):
        """Подписи зданий — короткие и без наложений (в том числе на значки гаражей): не влезает над зданием —
        ставим ниже, ещё ниже..."""
        w, h = self.w, self.h
        placed = list(squares)
        for bid, b in BUILDINGS.items():
            s = MAP_SHORT.get(bid, b[4])
            cx = ((b[0] + b[2] / 2) / MAP_W - 0.5) * w
            top = 0.02 + (0.5 - b[1] / MAP_H) * h
            bot = 0.02 + (0.5 - (b[1] + b[3]) / MAP_H) * h
            tw, th = text_w(s, 0.55), 0.02
            for y in (top + 0.012, bot - 0.012, top + 0.034, bot - 0.034, top + 0.056, bot - 0.056):
                box = (cx - tw / 2 - 0.004, cx + tw / 2 + 0.004, y - th / 2, y + th / 2)
                if not any(box[0] < o[1] and o[0] < box[1] and box[2] < o[3] and o[2] < box[3] for o in placed):
                    break
            placed.append(box)
            label(s, cx, y, 0.55, parent=self.root, origin=(0, 0), z=-0.01)
        self._placed = placed

    def _pos(self, x, y):
        return ((x / MAP_W - 0.5) * self.w, 0.02 + (0.5 - y / MAP_H) * self.h)

    def update(self, g):
        self.me.position = (*self._pos(g.p.x, g.p.y), -0.02)
        if not hasattr(self, "ag_marks"):
            # заброшенные гаражи: коричневые квадраты с подписью
            self.ag_marks = {}
            sqs = []
            for ag in g.world.abandoned:
                gx, gy, gw, gh = ag["rect"]
                px, py = self._pos(gx + gw / 2, gy + gh / 2)
                sqs.append((px - 0.011, px + 0.011, py - 0.011, py + 0.011))
            self._label_buildings(sqs)
            for ag in g.world.abandoned:
                gx, gy, gw, gh = ag["rect"]
                pos = self._pos(gx + gw / 2, gy + gh / 2)
                sq = Entity(parent=self.root, model="quad", scale=0.018, color=color.rgb(150, 95, 55),
                            position=(*pos, -0.02))
                # подпись справа от квадрата; у края карты или поверх другой подписи — слева / ниже
                name_w = max(text_w(T("? Заброшенный гараж"), 0.55), text_w(ag["name"], 0.55))
                left = pos[0] + 0.012 + name_w > self.w / 2
                tx = pos[0] - 0.012 if left else pos[0] + 0.012
                ty = pos[1] + 0.01
                for dy in (0.0, -0.022, 0.022, -0.044):
                    x0, x1 = (tx - name_w, tx) if left else (tx, tx + name_w)
                    if not any(x0 < o[1] and o[0] < x1 and ty + dy - 0.02 < o[3] and o[2] < ty + dy for o in self._placed):
                        break
                ty += dy
                self._placed.append((x0, x1, ty - 0.02, ty))
                t = label("?", tx, ty, 0.55, (240, 200, 120), parent=self.root, origin=(0.5, 0.5) if left else (-0.5, 0.5))
                self.ag_marks[ag["id"]] = (sq, t)
        for gid, (sq, t) in self.ag_marks.items():
            gs = g.garages.get(gid, {})
            name = g.world.abandoned_by_id(gid)["name"]
            txt = ("? " if not gs.get("open") else "") + (T("Заброшенный гараж") if not gs.get("open") else name)
            if t.text != txt:
                t.text = txt
            sq.color = color.rgb(150, 95, 55) if not gs.get("open") else color.rgb(110, 110, 110)
        vaz, ae = g.cars["vaz"], g.cars["ae86"]
        st = getattr(vaz, "stolen", None)
        lost = st and not st["found"]                 # угнанная и не найденная — на карте её нет (метка: где видели)
        self.car.position = (*self._pos(*(st["from"] if lost else (vaz.x, vaz.y))), -0.02)
        self.car.color = color.rgb(120, 120, 120) if lost else color.rgb(240, 200, 60)
        self.ae.position = (*self._pos(ae.x, ae.y), -0.02)
        finds = g.visible_finds()
        mine = [c for k, c in g.owned_cars() if k not in ("vaz", "ae86")
                and not (getattr(c, "stolen", None) and not c.stolen["found"])]
        for i, dot in enumerate(self.wreck_dots):
            dot.enabled = i < len(finds)
            if dot.enabled:
                dot.position = (*self._pos(finds[i].x, finds[i].y), -0.02)
        for i, dot in enumerate(self.mine_dots):
            dot.enabled = i < len(mine)
            if dot.enabled:
                dot.position = (*self._pos(mine[i].x, mine[i].y), -0.02)
        self.target.enabled = bool(g.delivery)
        if g.delivery:
            self.target.position = (*self._pos(g.delivery["x"], g.delivery["y"]), -0.02)
