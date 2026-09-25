"""Mein Garagen-Sommer 3D — аналог My Winter Car: ржавая ВАЗ 2102 в Германии, 1998.

Запуск:  python3 main.py        (нужны ursina, numpy, pygame, pillow)
Старая 2D-версия:  python3 main2d.py
"""
import math
import os
import random
import sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))

from ursina import Ursina, Entity, Text, camera, color, held_keys, mouse, time, window, scene, Vec3, application, destroy

TITLE = "Mein Garagen-Sommer 3D — ВАЗ 2102 в Германии"
app = Ursina(title=TITLE, development_mode=False, fullscreen=False, size=(1280, 720), borderless=False, vsync=True)
window.size = (1280, 720)
window.center_on_screen()
window.exit_button.visible = False
window.fps_counter.enabled = False
window.color = color.rgb(135, 170, 210)
for _f in ("/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf",
           "C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
    if os.path.exists(_f):
        Text.default_font = _f
        break
Text.default_resolution = 48

from panda3d.core import DirectionalLight, AmbientLight, Fog, TransparencyAttrib, WindowProperties  # noqa: E402

from state import GameState, RED, GREEN, YELLOW, WHITE  # noqa: E402
from actions import ActionsMixin, Menu, Inventory, CarWork, CONTROLS, INTRO, Dialog  # noqa: E402
from world import BUILDINGS, ROADS, PUMP_ZONE, TUV_YARD, GARAGE, SCRAP_DROP, point_in  # noqa: E402
from city3d import City, additive  # noqa: E402
from car3d import Car3D, AICar3D, Rope3D  # noqa: E402
from apartment3d import Apartment3D, OBJECTS as APT_OBJECTS, WALLS as APT_WALLS, AX, AZ  # noqa: E402
from ui3d import HUD, MenuView, MapView  # noqa: E402
from audio3d import Audio3D  # noqa: E402
from mesh3d import MeshBuilder  # noqa: E402
import textures3d  # noqa: E402

GAME_MIN_PER_SEC = 1.0
EYE = 1.65
SAVE_FILE = "savegame.json"


class MouseLook:
    """Свой захват мыши вместо Ursina mouse.locked.

    Почему не mouse.locked: Ursina каждый кадр переносит курсор в центр (movePointer),
    а в Panda3D на macOS перенос курсора вызывает CGAssociateMouseAndMouseCursorPosition(YES)
    и тем самым выключает относительный режим — камера перестаёт крутиться.

    Здесь (как в SDL): курсор один раз переносится в центр окна в обычном режиме,
    через ~0.25 с (macOS после переноса ненадолго глушит события) включается
    относительный режим. Дальше курсор не трогаем: поворот = разница координат
    указателя между кадрами (Panda копит deltaX/deltaY мыши).
    """
    SETTLE = 18   # кадров между переносом курсора и включением относительного режима

    def __init__(self):
        self.active = False
        self.state = "off"    # off / settle / on
        self.timer = 0
        self.last = None
        self.dx = 0.0
        self.dy = 0.0
        self.outside = 0

    def set(self, active):
        if active == self.active:
            return
        self.active = active
        props = WindowProperties()
        props.setCursorHidden(active)
        props.setMouseMode(WindowProperties.M_absolute)
        app.win.requestProperties(props)
        if active:
            self._arm()
        else:
            self.state = "off"

    def _arm(self):
        app.win.movePointer(0, app.win.getXSize() // 2, app.win.getYSize() // 2)
        self.state = "settle"
        self.timer = self.SETTLE
        self.last = None
        self.outside = 0

    def update(self):
        """Вызывать раз в кадр. Результат в пикселях — self.dx, self.dy."""
        self.dx = self.dy = 0.0
        if not self.active:
            return
        if self.state == "settle":
            self.timer -= 1
            if self.timer <= 0:
                props = WindowProperties()
                props.setMouseMode(WindowProperties.M_relative)
                app.win.requestProperties(props)
                self.state = "on"
                self.timer = 3
            return
        ptr = app.win.getPointer(0)
        if not ptr.getInWindow():
            # замороженный курсор оказался вне окна — события не приходят; перезахватываем
            self.outside += 1
            if self.outside > 30:
                props = WindowProperties()
                props.setMouseMode(WindowProperties.M_absolute)
                app.win.requestProperties(props)
                self._arm()
            return
        self.outside = 0
        x, y = ptr.getX(), ptr.getY()
        if self.last is None or self.timer > 0:
            self.timer = max(0, self.timer - 1)
            self.last = (x, y)
            return
        self.dx = x - self.last[0]
        self.dy = y - self.last[1]
        if abs(self.dx) > 400 or abs(self.dy) > 400:   # выбросы после смены режима
            self.dx = self.dy = 0.0
        self.last = (x, y)


# ====================================================================== меню верхнего уровня
class TitleMenu(Menu):
    title_screen = True

    def __init__(self, g):
        self.g = g

    def items(self):
        return [("Новая игра", "new", True), ("Продолжить", "load", os.path.exists(SAVE_FILE)),
                ("Управление", "help", True), ("Выход", "quit", True)]

    def select(self, s):
        g = self.g
        if s == "new":
            return g.start_new_game
        if s == "load":
            return g.load_game
        if s == "help":
            g.open_menu(Dialog("Управление", CONTROLS, wide=True))
            return None
        if s == "quit":
            application.quit()
        return None

    def back(self):
        return False


class PauseMenu(Menu):
    title = "Пауза"

    def __init__(self, g):
        self.g = g

    def items(self):
        return [("Продолжить", "back", True), ("Сохранить игру", "save", True),
                ("Загрузить игру", "load", os.path.exists(SAVE_FILE)), ("Управление", "help", True),
                ("Выйти в главное меню", "title", True)]

    def select(self, s):
        g = self.g
        if s == "back":
            return "close"
        if s == "save":
            g.save()
            return "close"
        if s == "load":
            return g.load_game
        if s == "help":
            g.open_menu(Dialog("Управление", CONTROLS, wide=True))
            return None
        if s == "title":
            return g.show_title
        return None


class GameOverMenu(Menu):
    title = "ИГРА ОКОНЧЕНА"

    def __init__(self, reason):
        self.reason = reason

    def lines(self):
        return self.reason.split("\n")

    def items(self):
        return [("В главное меню", "title", True)]

    def select(self, s):
        return "title"

    def back(self):
        return False


# ====================================================================== игра
class Game3D(GameState, ActionsMixin):
    def __init__(self):
        self.hud = None
        GameState.__init__(self)
        self.audio = Audio3D(app.loader)
        self._setup_env()
        self.city = City(self.world)
        self.car3ds = {k: Car3D(c) for k, c in self.cars.items()}
        self.rope3d = Rope3D()
        self.rope_action = None
        self.ai3d = [AICar3D(a) for a in self.world.ai]
        self.apt = Apartment3D()
        self.apt.set_visible(False)
        self.hud = HUD(self)
        self.menu_view = MenuView()
        self.menus = []
        tex, size = textures3d.map_texture(self.world, BUILDINGS, ROADS)
        self.mapview = MapView(tex, size)
        self.show_map = False
        # маркер доставки — столб света
        mb = MeshBuilder()
        mb.cylinder(0, 0, 0, 1.3, 70, (255, 220, 60, 90), seg=12, cap=False)
        self.marker = Entity(model=mb.build(), double_sided=True, enabled=False)
        additive(self.marker)
        self.mode = "title"
        self.location = "street"
        self.cam_mode = "cockpit"
        self.yaw = 0.0
        self.pitch = 0.0
        self.look_yaw = 0.0
        self.orbit = 35.0
        self.orbit_dist = 4.3
        self.apt_x, self.apt_y = 0.55, 5.1
        self.throttle = 0.0
        self.brake = 0.0
        self.bob = 0.0
        self.actions = []
        self.apt_near = None
        self._env_t = 0.0
        self._locked = None
        self.mouselook = MouseLook()
        self.sens = 0.15   # градусов на пиксель
        camera.fov = 78
        camera.clip_plane_near = 0.05
        camera.clip_plane_far = 900
        self.show_title()

    @property
    def car3d(self):
        self._sync_cars()
        return self.car3ds[self.cur]

    def _sync_cars(self):
        """3D-модели: создать для новых машин (находки), удалить у сданных на лом."""
        for k in list(self.car3ds):
            c3 = self.car3ds[k]
            if k not in self.cars or c3.car is not self.cars[k]:
                destroy(c3.root)
                del self.car3ds[k]
        for k, c in self.cars.items():
            if k not in self.car3ds:
                self.car3ds[k] = Car3D(c)
                self.car3ds[k].root.enabled = self.location != "apartment"

    # ------------------------------------------------------------------ окружение
    def _setup_env(self):
        self.sun = DirectionalLight("sun")
        self.sun_np = app.render.attachNewNode(self.sun)
        app.render.setLight(self.sun_np)
        self.amb = AmbientLight("amb")
        self.amb_np = app.render.attachNewNode(self.amb)
        app.render.setLight(self.amb_np)
        self.fog = Fog("fog")
        self.fog.setExpDensity(0.003)
        app.render.setFog(self.fog)

    def update_env(self):
        d = self.darkness()
        rain = self.weather == "rain"
        cloudy = self.weather == "cloudy"
        if self.location == "apartment":
            self.sun.setColor((0.25 * (1 - d), 0.25 * (1 - d), 0.22 * (1 - d), 1))
            self.amb.setColor((0.62, 0.58, 0.52, 1))
            self.fog.setExpDensity(0.0001)
            window.color = color.rgb(20, 20, 24)
            self.apt.update_env(d, rain, self.date().strftime("%d.%m.\n%Y"),
                                watching_tv=math.hypot(self.apt_x - 4.35, self.apt_y - 1.0) < 2.4, t=self.t)
            return
        k = 1 - d
        dim = 0.65 if rain else (0.85 if cloudy else 1.0)
        sky_day = (150, 170, 190) if rain else ((150, 180, 212) if cloudy else (130, 175, 225))
        sky_night = (8, 11, 22)
        sky = tuple(int(sky_night[i] + (sky_day[i] - sky_night[i]) * k) for i in range(3))
        # вечерний оттенок
        h = self.hour
        if 17.3 < h < 19.0 and not rain:
            w = 1 - abs(h - 18.2) / 0.9
            sky = (min(255, int(sky[0] + 70 * w)), int(sky[1] + 20 * w), int(sky[2] - 20 * w))
        window.color = color.rgb(*sky)
        self.fog.setColor(sky[0] / 255, sky[1] / 255, sky[2] / 255)
        self.fog.setExpDensity(0.0045 if rain else (0.0028 if d < 0.5 else 0.0038))
        s = 0.95 * k * dim
        self.sun.setColor((s * 1.0, s * 0.96, s * 0.88, 1))
        elev = max(12.0, 55 * math.sin(math.pi * max(0.0, min(1.0, (h - 6.5) / 12.5))))
        self.sun_np.setHpr((h - 12) * 15 + 30, -elev, 0)
        a = 0.12 + 0.36 * k * (0.8 if rain else 1.0)
        self.amb.setColor((a * 0.95, a * 1.0, a * 1.12, 1))
        self.city.set_night(d > 0.35)

    # ------------------------------------------------------------------ крючки GameState
    def notify(self, s, col=WHITE, t=5.0):
        if self.hud:
            self.hud.notify(s, col, t)
        else:
            print(s)

    def play_sound(self, name, vol=1.0):
        self.audio.play(name, vol)

    def engine_audio(self, inp):
        car = self.car
        if self.p.in_car:
            vol = 1.0
        elif self.location == "apartment":
            vol = 0.05
        else:
            vol = max(0.0, 0.8 - math.hypot(self.p.x - car.x, self.p.y - car.y) / 70)
        snd = car.sp("sound", "4t")
        rpm = car.rpm * (0.8 if snd == "diesel" else 1.15 if snd == "2t" else 1.0)
        exhaust = (car.c("exhaust") if car.has("exhaust") else 0.0) * (0.55 if snd in ("diesel", "2t") else 1.0)
        self.audio.engine(car.running, rpm, inp.get("throttle", 0), car.cranking, exhaust, vol,
                          skid=car.skidding and self.p.in_car)

    def open_menu(self, menu):
        self.menus.append(menu)
        self.menu_view.show(menu, reset=True)

    def flash_screen(self):
        self.hud.flash_a = 1.0

    def sleep(self, minutes):
        super().sleep(minutes)
        self.hud.fade_a = 1.0

    # ------------------------------------------------------------------ меню
    def close_menu(self):
        if not self.menus:
            return
        m = self.menus.pop()
        if isinstance(m, CarWork):
            self.car3d.set_hood(False)
            self.city.garage.enabled = True
            if self.mode == "carwork":
                self.mode = "play"
        if self.menus:
            self.menu_view.show(self.menus[-1], reset=True)
        else:
            self.menu_view.close()

    def menu_key(self, k):
        m = self.menus[-1]
        r = self.menu_view.key(k)
        if r is None:
            return
        depth = len(getattr(m, "stack", []))
        if r[0] == "back":
            if m.back():
                self.close_menu()
            else:
                self.menu_view.show(m, reset=True)
            return
        res = m.select(r[1])
        if res == "title":
            self.show_title()
        elif res is None:
            if self.menus and self.menus[-1] is m:
                self.menu_view.show(m, reset=len(getattr(m, "stack", [])) != depth)
        elif res == "close":
            self.close_menu()
        elif callable(res):
            if self.menus and self.menus[-1] is m:
                self.close_menu()
            res()

    # ------------------------------------------------------------------ состояния игры
    def clear_menus(self):
        self.menus = []
        self.menu_view.close()

    def show_title(self):
        self.clear_menus()
        self.audio.silence()
        if self.mode != "title":
            self.new_state()
            self.rebind()
        self.mode = "title"
        self.set_location("street")
        self.car3d.set_hood(False)
        self.open_menu(TitleMenu(self))

    def rebind(self):
        for c3 in self.car3ds.values():
            destroy(c3.root)
        self.car3ds = {}
        self._sync_cars()
        self.show_map = False

    def start_new_game(self):
        self.clear_menus()
        self.new_state()
        self.rebind()
        self.mode = "play"
        self.enter_apartment(silent=True)
        self.open_menu(Dialog("Добро пожаловать в Kleinbruck", INTRO, wide=True))

    def load_game(self):
        self.clear_menus()
        if self.load():
            self.rebind()
            self.mode = "play"
            self.set_location("street")
            self.yaw = 0
            if self.p.in_car:
                self.cam_mode = "cockpit"
        else:
            self.show_title()

    def show_game_over(self):
        self.clear_menus()
        reason = self.game_over
        self.game_over = None
        self.mode = "gameover"
        self.audio.silence()
        self.open_menu(GameOverMenu(reason))

    def set_location(self, loc):
        self.location = loc
        inside = loc == "apartment"
        self.apt.set_visible(inside)
        self.city.set_visible(not inside)
        for c3 in self.car3ds.values():
            c3.root.enabled = not inside
        for a in self.ai3d:
            a.root.enabled = not inside
        camera.parent = scene

    def enter_apartment(self, silent=False):
        self.set_location("apartment")
        self.apt_x, self.apt_y = 0.55, 5.1
        self.yaw, self.pitch = 0.0, 0.0
        self.p.in_car = False

    def leave_apartment(self):
        ax, ay = BUILDINGS["apartment"][7]
        self.p.x, self.p.y = ax, ay - 1.0
        self.p.in_car = False
        self.yaw, self.pitch = 0.0, 0.0
        self.set_location("street")

    def open_carwork(self):
        key = self.nearest_car(self.p.x, self.p.y)
        if key is None:
            return
        self.cur = key
        self.mode = "carwork"
        self.car3d.set_hood(True)
        self.city.garage.enabled = False
        self.orbit = 35.0
        self.orbit_dist = 4.3
        self.open_menu(CarWork(self))

    # ------------------------------------------------------------------ машина: вход/выход
    def near_car(self, dist=2.6):
        """Рядом ли своя машина (любая)."""
        return self.nearest_car(self.p.x, self.p.y, dist) is not None

    def toggle_car(self):
        p, car = self.p, self.car
        if p.in_car:
            if abs(car.speed) > 1:
                self.notify("Сначала остановитесь.", RED)
                return
            car.stop_crank()
            if car.running:
                car.gear = 0
            fx, fy = car.forward()
            for side in (1, -1):
                nx, ny = car.x + fy * 1.5 * side, car.y - fx * 1.5 * side
                if not self.world.collide_circle(nx, ny, 0.35):
                    p.x, p.y = nx, ny
                    break
            else:
                p.x, p.y = car.x - fx * 3, car.y - fy * 3
            p.in_car = False
            camera.parent = scene
            self.yaw = 90 + math.degrees(car.angle)
            self.pitch = 0
            self.play_sound("door", 0.6)
        elif self.near_car():
            key = self.nearest_car(p.x, p.y)
            if self.tow and key == self.tow["key"]:
                tug = self.cars[self.tow["by"]]
                if math.hypot(p.x - tug.x, p.y - tug.y) > 14:
                    self.notify("Эта машина на тросе. Садитесь в машину-тягач.", YELLOW)
                    return
                key = self.tow["by"]          # садимся в тягач, а не в буксируемую машину
            self.cur = key
            car = self.car
            p.in_car = True
            self.look_yaw = 0
            self.pitch = 0
            self.play_sound("door", 0.6)
            if not car.registered:
                self.notify(f"Внимание: {car.name} без номеров и страховки. Не попадитесь полиции!", (230, 140, 40), 6)

    def shift(self, gear):
        car = self.car
        if gear == car.gear:
            return
        if (gear == -1 and car.speed > 1.5) or (gear > 0 and car.speed < -1.5):
            self.notify("ХРУСТЬ! Сначала остановитесь.", RED)
            self.play_sound("grind", 0.7)
            return
        car.gear = gear

    # ------------------------------------------------------------------ ввод
    def input(self, key):
        if key == "i up":
            self.car.stop_crank()
            return
        if self.mode == "carwork" and key in ("scroll up", "scroll down"):
            self.orbit_dist = max(2.6, min(8, self.orbit_dist + (-0.4 if key == "scroll up" else 0.4)))
            return
        if self.menus:
            self.menu_key(key)
            return
        if self.mode != "play":
            return
        p, car = self.p, self.car
        if key == "escape":
            if self.show_map:
                self.show_map = False
            else:
                self.open_menu(PauseMenu(self))
            return
        if key in ("-", "="):
            self.sens = max(0.03, min(0.6, self.sens * (0.8 if key == "-" else 1.25)))
            self.notify(f"Чувствительность мыши: {self.sens / 0.15 * 100:.0f}%")
            return
        if key == "m" and self.location == "street":
            self.show_map = not self.show_map
        elif key == "tab":
            self.open_menu(Inventory(self))
        elif key == "e" and self.actions:
            self.actions[0][1]()
        elif key == "t" and self.rope_action and not p.in_car:
            self.rope_action[1]()
        elif key == "f" and self.location == "street":
            self.toggle_car()
        elif key == "v" and p.in_car:
            self.cam_mode = "chase" if self.cam_mode == "cockpit" else "cockpit"
            camera.parent = scene
        elif p.in_car:
            if key == "i":
                if car.running:
                    car.engine_off("Двигатель заглушен.")
                else:
                    car.start_crank()
            elif key == "c":
                car.choke = not car.choke
                self.notify("Подсос " + ("ВЫТЯНУТ" if car.choke else "задвинут"))
            elif key == "l":
                if car.has("lights") and car.c("lights") > 0.05:
                    car.lights = not car.lights
                else:
                    self.notify("Фары не работают.", RED)
            elif key == "h":
                if car.battery_charge > 5:
                    self.play_sound("horn", 0.7)
            elif key in ("left shift", "right shift"):
                self.shift(min(car.max_gear, car.gear + 1))
            elif key in ("left control", "right control"):
                self.shift(max(-1, car.gear - 1))
            elif key in ("1", "2", "3", "4", "5"):
                if int(key) <= car.max_gear:
                    self.shift(int(key))
            elif key == "r":
                self.shift(-1)
            elif key in ("n", "0"):
                self.shift(0)

    # ------------------------------------------------------------------ кадр
    def update(self, dt):
        dt = min(dt, 0.05)
        self.t += dt
        self.mouselook.update()
        top = self.menus[-1] if self.menus else None
        playing = self.mode in ("play", "carwork")
        flows = playing and not self.game_over and (top is None or getattr(top, "time_flows", False))
        if flows:
            self.advance(dt * GAME_MIN_PER_SEC)
            self.police_cd = max(0.0, self.police_cd - dt)
            if not (self.p.in_car and top is None):
                self.car_input = {}
            self.step_car(dt)
            self.world.update_ai(dt, list(self.cars.values()))
            for ai in self.world.ai:
                ai.siren = max(0.0, ai.siren - dt)
        else:
            self.audio.silence()
        if self.game_over and self.mode != "gameover":
            self.show_game_over()
            return

        prompt = []
        self.actions = []
        if self.mode == "title":
            self.orbit += dt * 6
            self._orbit_camera(dt)
        elif self.mode == "carwork":
            if held_keys["right mouse"] or held_keys["left mouse"]:
                self.orbit += mouse.velocity[0] * 200
            self._orbit_camera(dt)
        elif self.mode == "play":
            if self.location == "apartment":
                prompt = self.update_apartment(dt, top is None)
            else:
                prompt = self.update_street(dt, top is None)

        # визуал
        self._env_t -= dt
        if self._env_t <= 0:
            self._env_t = 0.25
            self.update_env()
        night = self.darkness()
        self._sync_cars()
        for k, c3 in self.car3ds.items():
            c3.update(dt, self.car_input if (self.p.in_car and k == self.cur) else {}, night)
        for a in self.ai3d:
            a.update(dt, self.t)
        self._sync_rope()
        d = self.delivery
        self.marker.enabled = bool(d) and self.location == "street"
        if d:
            self.marker.position = Vec3(d["x"], 0, -d["y"])
        self.audio.rain(1.0 if self.weather == "rain" and self.location == "street" and playing else 0.0)
        self.hud.fade_a = max(0.0, self.hud.fade_a - dt * 0.8)
        driving = self.p.in_car and self.location == "street" and playing
        hud_on = playing or self.mode == "gameover"
        self.hud.update(dt, {
            "hud": hud_on and self.mode != "gameover", "place": self.place(), "prompt": prompt,
            "cross": self.mode == "play" and not self.p.in_car and top is None and not self.show_map,
            "driving": driving and not isinstance(top, CarWork), "clutch": held_keys["space"],
            "yaw": self._view_yaw(), "rain": self.weather == "rain" and self.location == "street" and playing,
        })
        self.mapview.root.enabled = self.show_map and top is None
        if self.show_map:
            self.mapview.update(self)
        lock = self.mode == "play" and top is None and not self.show_map
        if lock != self._locked:
            self._locked = lock
            self.mouselook.set(lock)

    def _sync_rope(self):
        obj = self.towed_object()
        if obj is None or self.location == "apartment":
            self.rope3d.set(None, None)
            return
        car = self.cars[self.tow["by"]]
        fx, fy = car.forward()
        back = car.length / 2 + 0.1
        a = (car.x - fx * back, car.y - fy * back)
        b = (obj.x + math.cos(obj.angle) * obj.length / 2, obj.y + math.sin(obj.angle) * obj.length / 2)
        self.rope3d.set(a, b)

    def place(self):
        if self.location == "apartment":
            return "Квартира, Lindenstraße 7"
        r = self.world.road_at(self.p.x, self.p.y)
        if r:
            return r[5]
        return f"За рулём {self.car.name}" if self.p.in_car else "Kleinbruck"

    def _view_yaw(self):
        if self.p.in_car:
            return 90 + math.degrees(self.car.angle) + (self.look_yaw if self.cam_mode == "cockpit" else 0)
        return self.yaw

    def _orbit_camera(self, dt):
        car = self.car
        camera.parent = scene
        base = 90 + math.degrees(car.angle)
        a = math.radians(base + self.orbit)
        c = Vec3(car.x, 0.75, -car.y)
        dist = self.orbit_dist if self.mode == "carwork" else 6.0
        target = c + Vec3(math.sin(a) * dist, 1.1 if self.mode == "carwork" else 1.6, math.cos(a) * dist)
        camera.position = target
        camera.look_at(c)
        camera.rotation_z = 0

    def _mouse_look(self, limit_yaw=None):
        dx, dy = self.mouselook.dx * self.sens, self.mouselook.dy * self.sens
        self.pitch = max(-80, min(80, self.pitch + dy))
        if limit_yaw is None:
            self.yaw += dx
        else:
            self.look_yaw = max(-limit_yaw, min(limit_yaw, self.look_yaw + dx))

    # ------------------------------------------------------------------ улица
    def update_street(self, dt, free):
        p, car = self.p, self.car
        if free:
            if p.in_car:
                self._mouse_look(limit_yaw=110)
                if abs(self.mouselook.dx) < 0.5:
                    self.look_yaw *= max(0.0, 1 - dt * 0.8)
            else:
                self._mouse_look()
        if p.in_car:
            if free:
                thr = 1.0 if (held_keys["w"] or held_keys["up arrow"]) else 0.0
                brk = 1.0 if (held_keys["s"] or held_keys["down arrow"]) else 0.0
                self.throttle += (thr - self.throttle) * min(1, dt * 5)
                self.brake += (brk - self.brake) * min(1, dt * 8)
                steer = (held_keys["d"] or held_keys["right arrow"]) - (held_keys["a"] or held_keys["left arrow"])
                if p.drunk > 20:
                    steer += math.sin(self.t * 1.3) * p.drunk / 180
                self.car_input = {"throttle": self.throttle, "brake": self.brake, "steer": steer,
                                  "clutch": bool(held_keys["space"])}
                if car.cranking and not held_keys["i"]:
                    car.stop_crank()
            p.x, p.y = car.x, car.y
            self.check_blitzer()
            self.check_police()
            self._car_camera(dt)
        else:
            if free:
                fwd = (held_keys["w"] or held_keys["up arrow"]) - (held_keys["s"] or held_keys["down arrow"])
                side = (held_keys["d"] or held_keys["right arrow"]) - (held_keys["a"] or held_keys["left arrow"])
                if fwd or side:
                    run = held_keys["left shift"] and p.energy > 10
                    sp = (4.2 if run else 1.5) * dt
                    if run:
                        self.advance(dt * 0.5)
                    yr = math.radians(self.yaw)
                    # 3D-направление взгляда (sin, cos) -> 2D (x, -y)
                    dx = math.sin(yr) * fwd + math.cos(yr) * side
                    dy = -(math.cos(yr) * fwd - math.sin(yr) * side)
                    l = math.hypot(dx, dy)
                    for ax, ay in ((dx / l * sp, 0), (0, dy / l * sp)):
                        nx, ny = p.x + ax, p.y + ay
                        blocked = self.world.collide_circle(nx, ny, 0.35)
                        if not blocked:
                            blocked = any(math.hypot(nx - cx, ny - cy) < r + 0.3 for cx, cy, r in car.body_circles())
                        if not blocked:
                            p.x, p.y = nx, ny
                    self.bob += dt * (11 if run else 7)
            for ai in self.world.ai:
                if ai.speed > 4 and math.hypot(ai.x - p.x, ai.y - p.y) < 1.5:
                    self.hospital("Вас сбила машина! Смотрите по сторонам.")
                    self.leave_hospital()
                    return []
            camera.parent = scene
            camera.position = Vec3(p.x, EYE + math.sin(self.bob) * 0.035, -p.y)
            camera.rotation = Vec3(self.pitch, self.yaw, 0)

        # потеря сознания от усталости
        if self.pending_faint:
            self.pending_faint = False
            if p.in_car and abs(car.speed) > 3:
                self.notify("Вы уснули за рулём!", RED, 8)
                if car.impact(abs(car.speed)):
                    self.hospital("Авария: уснули за рулём.")
                    self.leave_hospital()
                    return []
                car.speed = 0
            else:
                self.notify("Вы уснули прямо на улице...", RED, 8)
            car.engine_off()
            self.sleep(360)
            if random.random() < 0.3 and p.money > 20:
                self.charge(min(p.money, random.uniform(10, 60)), "Пока вы спали, у вас украли деньги", RED, 8)
        d = self.delivery
        if d and self.minutes > d["deadline"] + 60:
            self.notify("Заказ отменён — клиент не дождался. Пиццерия недовольна.", RED)
            self.delivery = None
        return self.find_actions()

    def leave_hospital(self):
        if self.location != "street":
            self.set_location("street")
        camera.parent = scene
        self.yaw = 0

    def _car_camera(self, dt):
        car = self.car
        if self.cam_mode == "cockpit":
            c3 = self.car3d
            ex, ey, esx = car.spec["eye"]
            camera.parent = c3.body
            camera.position = Vec3(ex, ey, c3.Z(esx))
            camera.rotation = Vec3(self.pitch + 4, self.look_yaw, 0)
        else:
            camera.parent = scene
            fx, fy = car.forward()
            tgt = Vec3(car.x - fx * 6.8, 2.5, -(car.y - fy * 6.8))
            if camera.position.y < 0.5 or (camera.position - tgt).length() > 30:
                camera.position = tgt
            camera.position = camera.position + (tgt - camera.position) * min(1, dt * 5)
            camera.look_at(Vec3(car.x + fx * 2, 1.0, -(car.y + fy * 2)))
            camera.rotation_z = 0

    def find_actions(self):
        p, car = self.p, self.car
        acts = []
        self.rope_action = None
        d = self.delivery
        if d and math.hypot(p.x - d["x"], p.y - d["y"]) < (9 if p.in_car else 4):
            acts.append(("Отдать пиццу клиенту", self.deliver))
        near_drop = point_in((SCRAP_DROP[0] - 6, SCRAP_DROP[1] - 6, SCRAP_DROP[2] + 12, SCRAP_DROP[3] + 12), p.x, p.y)
        if near_drop:
            for k in self.wrecks_in_drop():
                mine = " (ваша!)" if self.owned.get(k) else ""
                acts.append((f"Сдать на лом: {self.cars[k].name}{mine} (+{self.scrap_value(k):.2f} DM)",
                             lambda k=k: self.scrap_car(k)))
        if p.in_car:
            if point_in(PUMP_ZONE, car.x, car.y):
                acts.append(("Заправиться", self.refuel))
            if point_in(TUV_YARD, car.x, car.y):
                acts.append(("Пройти TÜV (техосмотр)", self.tuv))
        else:
            for bid, b in BUILDINGS.items():
                door = b[7]
                if door and math.hypot(p.x - door[0], p.y - door[1]) < 3.0:
                    acts.append((f"Войти: {b[4]}", lambda bid=bid: self.enter_building(bid)))
                    break
            wreck = self.nearest_wreck(p.x, p.y)
            if self.near_car():
                key = self.nearest_car(p.x, p.y)
                acts.append((f"Открыть капот — {self.cars[key].name}", self.open_carwork))
                if point_in(PUMP_ZONE, self.cars[key].x, self.cars[key].y):
                    acts.append(("Заправить машину", self.refuel))
            elif self.nearest_car(p.x, p.y, 3.0, owned_only=False) == "ae86" and not self.owned["ae86"]:
                acts.append(("Осмотреть Toyota AE86 (Ковальский отдаёт даром)", self.ae86_offer))
            elif wreck is not None:
                acts.append((f"Осмотреть: {self.cars[wreck].name} — брошена, можно забрать бесплатно",
                             lambda k=wreck: self.find_offer(k)))
            # трос (T)
            towed = self.towed_object()
            if self.tow:
                tcar = self.cars[self.tow["by"]]
                tx, ty = towed.x, towed.y
                if math.hypot(p.x - tx, p.y - ty) < 4 or math.hypot(p.x - tcar.x, p.y - tcar.y) < 4:
                    self.rope_action = (f"Отвязать трос ({self.tow_name()})", self.detach_rope)
            elif wreck is not None:
                self.rope_action = (f"Привязать трос: {self.cars[wreck].name}", lambda k=wreck: self.attach_rope(k))
            elif self.near_car():
                key = self.nearest_car(p.x, p.y)
                others = [k for k, c in self.owned_cars() if k != key]
                if others:
                    self.rope_action = (f"Привязать трос: {self.cars[key].name} (тянуть другой машиной)",
                                        lambda key=key: self.attach_rope(key))
        self.actions = acts
        prompt = []
        if acts:
            prompt.append(f"E — {acts[0][0]}")
        extra = []
        if not p.in_car and self.near_car():
            nk = self.nearest_car(p.x, p.y)
            if self.tow and nk == self.tow["key"]:
                nk = self.tow["by"]
            extra.append(f"F — сесть за руль ({self.cars[nk].name})")
        elif p.in_car and abs(car.speed) < 1:
            extra.append("F — выйти   ·   V — вид")
        if self.rope_action:
            extra.append(f"T — {self.rope_action[0]}")
        if p.in_car and self.tow and self.tow["by"] == self.cur:
            warn = "  ⚠ ТИШЕ!" if car.kmh() > 45 else ""
            extra.append(f"На тросе: {self.tow_name()} — не быстрее 50 км/ч{warn}")
        if extra:
            prompt.append("   ·   ".join(extra))
        return prompt

    # ------------------------------------------------------------------ квартира
    def update_apartment(self, dt, free):
        if free:
            self._mouse_look()
            fwd = (held_keys["w"] or held_keys["up arrow"]) - (held_keys["s"] or held_keys["down arrow"])
            side = (held_keys["d"] or held_keys["right arrow"]) - (held_keys["a"] or held_keys["left arrow"])
            if fwd or side:
                yr = math.radians(self.yaw)
                dx = math.sin(yr) * fwd + math.cos(yr) * side
                dy = -(math.cos(yr) * fwd - math.sin(yr) * side)
                l = math.hypot(dx, dy)
                sp = 1.7 * dt
                for ax, ay in ((dx / l * sp, 0), (0, dy / l * sp)):
                    nx, ny = self.apt_x + ax, self.apt_y + ay
                    if not self._apt_blocked(nx, ny):
                        self.apt_x, self.apt_y = nx, ny
                self.bob += dt * 7
        camera.parent = scene
        camera.position = Vec3(AX + self.apt_x, 1.62 + math.sin(self.bob) * 0.03, AZ - self.apt_y)
        camera.rotation = Vec3(self.pitch, self.yaw, 0)
        if self.pending_faint:
            self.pending_faint = False
            self.notify("Вы уснули прямо на полу...", RED)
            self.sleep(360)
        # что перед глазами
        yr = math.radians(self.yaw)
        vx, vy = math.sin(yr), -math.cos(yr)
        best, bs = None, 99
        for key, lab, (x, y, w, h), solid in APT_OBJECTS:
            x0, y0, x1, y1 = x / 100, y / 100, (x + w) / 100, (y + h) / 100
            cx = max(x0, min(self.apt_x, x1))
            cy = max(y0, min(self.apt_y, y1))
            dist = math.hypot(self.apt_x - cx, self.apt_y - cy)
            if dist > 1.3:
                continue
            mx, my = (x0 + x1) / 2 - self.apt_x, (y0 + y1) / 2 - self.apt_y
            ml = math.hypot(mx, my) or 1
            dot = (mx * vx + my * vy) / ml
            if dot < 0.35 and dist > 0.35:
                continue
            score = dist - dot
            if score < bs:
                best, bs = (key, lab), score
        self.actions = []
        if best:
            key, lab = best
            self.actions = [(lab, lambda key=key: self.apartment_act(key))]
            return [f"E — {lab}"]
        return []

    def _apt_blocked(self, x, y):
        r = 0.25
        for (wx, wy, ww, wh) in APT_WALLS:
            if x + r > wx / 100 and x - r < (wx + ww) / 100 and y + r > wy / 100 and y - r < (wy + wh) / 100:
                return True
        for key, lab, (ox, oy, ow, oh), solid in APT_OBJECTS:
            if solid and x + r > ox / 100 and x - r < (ox + ow) / 100 and y + r > oy / 100 and y - r < (oy + oh) / 100:
                return True
        return False


class Controller(Entity):
    def __init__(self, game):
        super().__init__()
        self.game = game

    def update(self):
        self.game.update(time.dt)

    def input(self, key):
        self.game.input(key)


if __name__ == "__main__":
    game = Game3D()
    Controller(game)
    app.run()
