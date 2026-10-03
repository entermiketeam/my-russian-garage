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

# Ursina при каждом присваивании enabled прячет/показывает узел — даже если значение не поменялось.
# Машин и людей в городе много, и каждый кадр это съедало заметную долю FPS: пропускаем «пустые» присваивания.
from ursina.entity import Entity as _UEntity  # noqa: E402
_enabled_prop = _UEntity.enabled


def _set_enabled_fast(self, value):
    if hasattr(self, "_enabled") and self._enabled == bool(value):
        return
    _enabled_prop.fset(self, value)


_UEntity.enabled = property(_enabled_prop.fget, _set_enabled_fast)

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

from state import GameState, RED, GREEN, YELLOW, WHITE, MAIN_CARS  # noqa: E402
from actions import ActionsMixin, Menu, Inventory, CarWork, CONTROLS, INTRO, Dialog, Dealer, Dismantle  # noqa: E402
from items import item_name  # noqa: E402
from world import BUILDINGS, ROADS, PUMP_ZONE, TUV_YARD, GARAGE, SCRAP_DROP, point_in  # noqa: E402
from places import INTERIOR_X  # noqa: E402
from config import VIEW_DIST, CAR_VIEW_DIST, SIM_DIST  # noqa: E402
import streaming  # noqa: E402
import fasteners as fast  # noqa: E402
import electrics as elec  # noqa: E402
import keys as keys_mod  # noqa: E402
import theft  # noqa: E402
import engine as eng_mod  # noqa: E402
from items import ITEMS  # noqa: E402
from city3d import City, additive  # noqa: E402
from places3d import Places3D  # noqa: E402
from winter3d import Winter3D  # noqa: E402
from car3d import Car3D, AICar3D, Rope3D  # noqa: E402
from apartment3d import Apartment3D, OBJECTS as APT_OBJECTS, WALLS as APT_WALLS, AX, AZ  # noqa: E402
from ui3d import HUD, MenuView, MapView  # noqa: E402
from audio3d import Audio3D  # noqa: E402
from hands3d import Hands3D  # noqa: E402
from window_views import WindowViews  # noqa: E402
from mirrors import Mirrors  # noqa: E402
from under_play import UnderMixin, REACH as UNDER_REACH  # noqa: E402
import underside as under_mod  # noqa: E402
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
class Game3D(UnderMixin, GameState, ActionsMixin):
    def __init__(self):
        self.hud = None
        GameState.__init__(self)
        self.audio = Audio3D(app.loader)
        self._setup_env()
        self.city = City(self.world)
        self.places3d = Places3D(self.world)
        self.winter3d = Winter3D(self.world, self.winter, self.city)
        self._under_vis = False
        self.car3ds = {}
        self.rope3d = Rope3D()
        self.rope_action = None
        self.dismantle_action = None
        from traffic3d import TrafficView
        self.traffic3d = TrafficView(self.traffic)              # машины трафика (LOD), светофоры, пешеходы
        from service3d import Service3D
        self.service3d = Service3D(self.world)                  # автосервис «Kfz-Werkstatt Schmidt»
        self.ai3d = []
        self.apt = Apartment3D()
        self.apt.set_visible(False)
        self.window_views = WindowViews(app, self.apt)       # настоящий вид из окон квартиры на улицу
        self.apt.views_ok = self.window_views.ok
        self.mirrors = Mirrors(app)                          # рабочие зеркала заднего вида у машины игрока
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
        camera.clip_plane_far = VIEW_DIST + 60        # дальше — не рисуем (туман скрывает границу)
        self.hands3d = Hands3D(self)                  # руки игрока: что в них и анимации еды/питья
        self._build_boards()
        self.show_title()

    @property
    def car3d(self):
        self._sync_cars()
        return self.car3ds[self.cur]

    def _sync_cars(self, budget=2):
        """3D-модели машин: только рядом с игроком (машин в мире ~100). Далёкие удаляются,
        близкие создаются по нескольку за кадр, чтобы не было рывков."""
        px, py = self.p.x, self.p.y
        keep = {self.cur}
        if self.tow:
            keep |= {self.tow.get("key"), self.tow.get("by")}

        lv = self.world.level_at(px, py) if px >= INTERIOR_X else None

        def dist(c):
            d = abs(c.x - px) + abs(c.y - py)
            if lv is not None and c.x >= INTERIOR_X and self.world.level_at(c.x, c.y) is not lv:
                d += 1000          # машины на другом уровне подземки не видны
            return d

        for k in list(self.car3ds):
            c3 = self.car3ds[k]
            rebuilt = getattr(c3, "_built_color", None) != c3.car.color or getattr(c3.car, "_rebuild3d", False)
            if getattr(c3.car, "_rebuild3d", False):
                c3.car._rebuild3d = False                    # после ремонта в сервисе (кузов выправлен) — новая модель
            if k not in self.cars or c3.car is not self.cars[k] or rebuilt or \
                    (k not in keep and dist(self.cars[k]) > CAR_VIEW_DIST + 40):
                destroy(c3.root)
                del self.car3ds[k]
        want = sorted((k for k, c in self.cars.items() if k not in self.car3ds and (k in keep or dist(c) < CAR_VIEW_DIST)),
                      key=lambda k: (k not in keep, dist(self.cars[k])))
        for k in want[:max(budget, sum(1 for k_ in want if k_ in keep))]:
            self.car3ds[k] = Car3D(self.cars[k])
            self.car3ds[k].root.enabled = True

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

    def _snow_shown(self):
        """Снежный покров, сугробы и слякоть видны на улице, только пока по сезону лежит снег."""
        return self.location in ("street", "apartment") and self.p.x < INTERIOR_X and self.snow_level > 0.12

    def update_env(self):
        self.city.set_season(self.month, self.climate()["leaves"])      # листва по календарю
        vis = self._snow_shown()
        if vis != self.winter3d.visible:            # снег сошёл весной / выпал осенью
            self.winter3d.set_visible(vis)
        d = self.darkness()
        rain = self.weather in ("sleet", "rain")
        snowing = self.weather == "snow"
        cloudy = self.weather == "cloudy" or snowing
        apt = self.location == "apartment"
        if apt:
            # в квартире: свой свет внутри; улица за окнами живёт своей погодой и временем суток (ниже)
            self.apt.update_env(d, rain, self.date().strftime("%d.%m.\n%Y"),
                                watching_tv=math.hypot(self.apt_x - 4.35, self.apt_y - 1.0) < 2.4, t=self.t,
                                dim=0.55 if rain else (0.7 if snowing else (0.8 if cloudy else 1.0)))
        if self.p.x >= INTERIOR_X and not apt:
            # подземный гараж: без солнца, тусклые лампы, тёмный «туман»
            self.sun.setColor((0.0, 0.0, 0.0, 1))
            self.amb.setColor((0.30, 0.31, 0.30, 1))
            window.color = color.rgb(6, 7, 8)
            self.fog.setColor(0.03, 0.035, 0.04)
            self.fog.setExpDensity(0.028)
            self.city.set_night(True)
            return
        k = 1 - d
        dim = 0.65 if rain else (0.78 if snowing else (0.85 if cloudy else 1.0))
        sky_day = (150, 162, 175) if rain else ((178, 186, 196) if snowing else
                                                ((150, 172, 200) if cloudy else (140, 178, 222)))
        sky_night = (8, 11, 22)
        sky = tuple(int(sky_night[i] + (sky_day[i] - sky_night[i]) * k) for i in range(3))
        # вечерний оттенок
        h = self.hour
        if 17.3 < h < 19.0 and not rain:
            w = 1 - abs(h - 18.2) / 0.9
            sky = (min(255, int(sky[0] + 70 * w)), int(sky[1] + 20 * w), int(sky[2] - 20 * w))
        window.color = color.rgb(*sky) if not apt else color.rgb(20, 20, 24)
        self.sky_rgb = sky
        self.fog.setColor(sky[0] / 255, sky[1] / 255, sky[2] / 255)
        # туман линейный: к краю дальности прорисовки всё растворяется в цвете неба — квадраты не «выскакивают»
        near, far = (0.18, 0.78) if snowing else ((0.25, 0.85) if rain else ((0.4, 0.97) if d < 0.5 else (0.3, 0.9)))
        self.fog.setLinearRange(VIEW_DIST * near, VIEW_DIST * far)
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
        rpm = car.rpm * (0.8 if snd == "diesel" else 1.15 if snd == "2t" else (0.62 if snd == "v8" else 1.0))
        exhaust = (car.c("exhaust") if car.has("exhaust") else 0.0) * (0.55 if snd in ("diesel", "2t") else 1.0)
        self.audio.engine(car.running, rpm, inp.get("throttle", 0), car.cranking, exhaust, vol,
                          skid=car.skidding and self.p.in_car)

    def on_garage_opened(self, gid):
        self.city.set_garage_door(gid, True)

    def open_menu(self, menu):
        self.menus.append(menu)
        self.menu_view.show(menu, reset=True)

    def flash_screen(self):
        self.hud.flash_a = 1.0

    def start_eat(self, i):
        """Съесть/выпить из руки i — с анимацией (укус/глоток засчитывается в конце)."""
        e = self.p.hands[i]
        if not self.edible(e) or self.hands3d.busy:
            return False
        if self.p.in_car and self.p.seat == "driver" and abs(self.car.speed) > 0.5:
            self.notify("За рулём на ходу — не до еды.", YELLOW)
            return False
        kind = "drink" if ITEMS[e["id"]]["kind"] == "drink" else "eat"
        if not self.hands3d.visible or self.mode != "play":
            return self.eat_hand(i)
        return self.hands3d.play(i, kind)

    def eat_action(self):
        """(подпись, действие) — съесть/выпить то, что в руках (сначала правая), или None."""
        if self.p.in_car or self.hands3d.busy:
            return None
        for i in (1, 0):
            e = self.p.hands[i]
            if self.edible(e):
                verb = "выпить" if ITEMS[e["id"]]["kind"] == "drink" else "съесть"
                return (f"{verb}: {ITEMS[e['id']]['name']} ({'правая' if i else 'левая'} рука, осталось {e['cond']:.0f}%)",
                        lambda i=i: self.start_eat(i))
        return None

    def sleep(self, minutes):
        super().sleep(minutes)
        self.hud.fade_a = 1.0

    # ------------------------------------------------------------------ меню
    def close_menu(self):
        if not self.menus:
            return
        m = self.menus.pop()
        if isinstance(m, CarWork):
            # капот остаётся открытым: можно работать руками (болты) — закрыть E на капоте
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
        self._sync_cars(budget=12)
        for ag in self.world.abandoned:
            self.city.set_garage_door(ag["id"], self.garages.get(ag["id"], {}).get("open", False))
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
        under = self.p.x >= INTERIOR_X
        self._under_vis = under
        # из квартиры улицу видно в окна — мир остаётся на месте (основная камера до него не достаёт)
        self.city.set_visible(not under)
        self.places3d.set_visible(True)
        self.winter3d.set_visible(self._snow_shown())
        for c3 in self.car3ds.values():
            c3.root.enabled = True
        for a in self.ai3d:
            a.root.enabled = not under
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

    def open_carwork(self, key=None):
        key = key or self.nearest_car(self.p.x, self.p.y)
        if key is None:
            return
        if self.cars[key].locked and not self.p.in_car:
            self.play_sound("handle", 0.5)
            self.notify("Машина заперта — капот открывается рычагом из салона. Отоприте (K с ключом в руке).", RED)
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
            for side in ((-1, 1) if p.seat == "passenger" else (1, -1)):   # выходим со своей стороны
                nx, ny = car.x + fy * 1.5 * side, car.y - fx * 1.5 * side
                if not self.world.collide_circle(nx, ny, 0.35):
                    p.x, p.y = nx, ny
                    break
            else:
                p.x, p.y = car.x - fx * 3, car.y - fy * 3
            p.in_car = False
            p.seat = "driver"
            camera.parent = scene
            self.yaw = 90 + math.degrees(car.angle)
            self.pitch = 0
            self.play_sound("door", 0.6)
            self._exit_warnings(car)
        elif self.near_car():
            key = self.nearest_car(p.x, p.y)
            if self.tow and key == self.tow["key"]:
                tug = self.cars[self.tow["by"]]
                if math.hypot(p.x - tug.x, p.y - tug.y) > 14:
                    self.notify("Эта машина на тросе. Садитесь в машину-тягач.", YELLOW)
                    return
                key = self.tow["by"]          # садимся в тягач, а не в буксируемую машину
            if getattr(self.cars[key], "service", None):
                import service
                self.notify(f"{self.cars[key].name} {service.ready_text(self, self.cars[key])}.", YELLOW, 5)
                return
            if not self._unlock_to_enter(key):
                return
            self.cur = key
            car = self.car
            p.in_car = True
            p.seat = "driver"
            self.look_yaw = 0
            self.pitch = 0
            self.play_sound("door", 0.6)
            if not car.registered:
                self.notify(f"Внимание: {car.name} без номеров и страховки. Не попадитесь полиции!", (230, 140, 40), 6)

    def _unlock_to_enter(self, key):
        """Садимся в запертую машину: нужен её ключ в руке (отпираем), иначе — заперто."""
        car = self.cars[key]
        if not car.locked:
            return True
        i = keys_mod.key_in_hands(self, car)
        if i is None:
            self.play_sound("handle", 0.6)
            self.notify(f"{car.name}: заперто. Нужен ключ от этой машины в руке (K — отпереть).", RED, 5)
            return False
        self.lock_car(car, False, i)
        return True

    def _exit_warnings(self, car):
        if car.ign_key and not car.running:
            if car.locked:
                self.notify("Вы захлопнули машину, а ключ остался в замке зажигания! Запасной — на ключнице дома, "
                            "или вскрыть дверь монтировкой.", RED, 10)
            else:
                self.notify("Ключ остался в замке зажигания — так машину угонят за минуту. E на замке (из салона) — "
                            "вынуть.", YELLOW, 8)

    def lock_car(self, car, lock, hand=None):
        """Запереть/отпереть. Снаружи — ключом (анимация руки), изнутри — кнопкой."""
        if car.lock_broken and lock:
            self.play_sound("handle", 0.5)
            self.notify(f"{car.name}: замок сломан — не запирается. Замена замков — в меню работы с машиной.", RED, 6)
            return False
        if lock:
            car.door_open = {k: False for k in car.door_open}
            car.trunk_open = False
        car.locked = lock
        if hand is not None:
            self.hands3d.play_key(hand, "door", self.p.hands[hand])
        self.play_sound("lock" if lock else "unlock", 0.7)
        if keys_mod.has_central(car):
            car._flash_t = 0.8 if lock else 0.4
        k = next((kk for kk, c in self.cars.items() if c is car), None)
        if k and self.owned.get(k):
            self.cur = k
        self.notify(f"{car.name}: " + ("заперта" + (" (центральный замок)" if keys_mod.has_central(car) else "")
                                         if lock else "отперта"), GREEN if lock else WHITE, 3)
        return True

    def key_toggle_lock(self):
        """K: изнутри — кнопка блокировки; снаружи — ключом в руке у ближайшей своей машины."""
        p = self.p
        if p.in_car:
            car = self.car
            if car.lock_broken:
                self.notify("Кнопка блокировки не держит — замок сломан.", RED)
                return
            self.lock_car(car, not car.locked)
            return
        best, bd = None, 3.2
        for k, c in self.cars.items():
            if abs(c.x - p.x) + abs(c.y - p.y) > 9:
                continue
            d = min(math.hypot(p.x - cx, p.y - cy) for cx, cy, _ in c.body_circles())
            if d < bd:
                best, bd = k, d
        if best is None:
            self.notify("Рядом нет машины.", RED)
            return
        car = self.cars[best]
        i = keys_mod.key_in_hands(self, car)
        if i is None:
            other = any(e and e.get("id") == "key" for e in p.hands)
            self.notify(f"{car.name}: " + ("этот ключ не подходит." if other else "нужен ключ от этой машины в руке."), RED, 5)
            return
        self.lock_car(car, not car.locked, i)

    def ignition_action(self):
        """(подпись, действие) для замка зажигания в салоне."""
        car = self.car
        if car.ign_key:
            if car.running:
                return ("Заглушить двигатель ключом", lambda: car.engine_off("Двигатель заглушен."))
            return ("Вынуть ключ из замка зажигания", self._take_ign_key)
        i = keys_mod.key_in_hands(self, car)
        if i is not None:
            return ("Вставить ключ в замок зажигания", lambda: self._insert_key(i))
        if car.hotwired:
            return ("Замок зажигания разобран — заводится проводами (I)", lambda: None)
        return ("Нет ключа. Завести напрямую — соединить провода (набор ключей, 4 мин)", self._hotwire)

    def _insert_key(self, i):
        car = self.car
        e = self.p.hands[i]
        if not keys_mod.fits(e, car):
            return False
        self.hands3d.play_key(i, "ign_in", e)
        self.p.hands[i] = None
        car.ign_key = e
        car._key_slide = 1.0
        self.play_sound("key", 0.6)
        return True

    def _take_ign_key(self):
        car = self.car
        if car.running:
            car.engine_off("Двигатель заглушен.")
        fh = self.free_hand()
        if fh is None:
            self.notify("Обе руки заняты — ключ некуда взять.", RED)
            return
        e = car.ign_key
        car.ign_key = None
        self.p.hands[fh] = e
        self.hands3d.play_key(fh, "ign_out", e)
        self.play_sound("key", 0.6)

    def _hotwire(self):
        car = self.car
        if not self.need("toolbox"):
            return
        self.advance(4, working=True)
        car.hotwired = True
        self.play_sound("tool", 0.6)
        self.notify("Кожух колонки снят, провода соединены: теперь машина заводится без ключа (I). Замок зажигания "
                    "испорчен — TÜV это заметит; замена замков — в меню работы с машиной.", YELLOW, 10)

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
        elif key == "k" and self.location == "street":
            self.key_toggle_lock()
        elif key == "q" and not p.in_car:
            if any(p.hands) and not self.hands3d.busy:
                self.swap_hands()
                self.play_sound("click", 0.3)
        elif key in ("z", "x") and not p.in_car and not self.hands3d.busy:
            i = 0 if key == "z" else 1
            e = p.hands[i]
            if e:
                where = self.drop_hand(i)
                if where:
                    self.notify(f"Положили: {ITEMS.get(e['id'], {}).get('name', e['id'])} — {where}.", GREEN)
                    self.play_sound("tool", 0.3)
                else:
                    self.notify("Здесь это положить некуда.", RED)
        elif key == "e" and self.actions:
            self.actions[0][1]()
        elif key == "g" and len(self.actions) > 1 and not p.in_car:
            self.actions[1][1]()
        elif key == "t" and self.rope_action and not p.in_car:
            self.rope_action[1]()
        elif key == "r" and self.dismantle_action and not p.in_car:
            self.open_menu(Dismantle(self, self.dismantle_action))
        elif key == "f" and self.location == "street" and p.under_car:
            self.crawl_out()
        elif key == "f" and self.location == "street":
            self.toggle_car()
        elif key == "v" and p.in_car:
            self.cam_mode = "chase" if self.cam_mode == "cockpit" else "cockpit"
            camera.parent = scene
        elif p.in_car and p.seat == "passenger":
            pass                                        # с пассажирского места рулём и педалями не управляют
        elif p.in_car:
            if key in ("[", "]"):
                self._blinker(-1 if key == "[" else 1)
            elif key == "i":
                if car.running:
                    car.engine_off("Двигатель заглушен.")
                elif keys_mod.can_start(car):
                    car.start_crank()
                elif keys_mod.key_in_hands(self, car) is not None:
                    self._insert_key(keys_mod.key_in_hands(self, car))     # вставили — держите I, чтобы крутить
                    self._crank_after_key = True
                else:
                    other = any(e and e.get("id") == "key" for e in p.hands)
                    self.notify("Этот ключ не подходит к замку зажигания." if other else
                                "Нет ключа. Возьмите ключ этой машины в руку (Tab) — или E на замке зажигания: "
                                "завести напрямую.", RED, 6)
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
                    car._horn_t = 0.7                     # цепь сигнала под нагрузкой (может сжечь предохранитель)
                    if elec.works(car, "horn"):
                        self.play_sound("horn", 0.7)
                    else:
                        self.notify("Сигнал молчит. Предохранитель или сам сигнал? — блок предохранителей.", YELLOW)
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
            self.traffic.update(dt, self, (self.p.x, self.p.y))     # машины трафика и пешеходы
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
            if not getattr(self, "_prebuilt", False):
                self._prebuilt = self.traffic3d.prebuild(1)       # пока открыто меню — собрать модели трафика
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
        self._stream_t = getattr(self, "_stream_t", 0.0) - dt
        lp = getattr(self, "_stream_pos", (1e9, 1e9))
        if abs(lp[0] - self.p.x) + abs(lp[1] - self.p.y) > 40:
            self._stream_t = 0.0                 # телепорт (подземка, больница, загрузка) — сразу
        if self._stream_t <= 0:                  # подгрузка квадратов карты вокруг игрока
            self._stream_pos = (self.p.x, self.p.y)
            self._stream_t = 0.2
            streaming.update(self.p.x, self.p.y)
        self._sync_cars()
        if self.location == "street":
            under = self.p.x >= INTERIOR_X
            if under != self._under_vis:
                self._under_vis = under
                self.city.set_visible(not under)
                self.winter3d.set_visible(self._snow_shown())
                for a in self.ai3d:
                    a.root.enabled = not under
                self.update_env()
            self.places3d.update(dt, self)
            self.winter3d.update(self.p.x, self.p.y, budget=3 if self.mode == "play" else 1)
        for k, c3 in self.car3ds.items():
            busy = k == self.cur or (self.tow and k in (self.tow.get("key"), self.tow.get("by")))
            c3.update(dt, self.car_input if (self.p.in_car and k == self.cur and self.p.seat == "driver") else {},
                      night, lazy=not busy)
        # трафик: машины (полная модель вблизи, лёгкая вдали), светофоры, пешеходы
        show_ai = self.location in ("street", "apartment") and self.p.x < INTERIOR_X
        self.traffic3d.peds.rain = self.weather in ("rain", "sleet", "snow")
        self.traffic3d.update(dt, self.p.x, self.p.y, night, self.traffic.t, show_ai)
        if show_ai and abs(self.p.x - 780) + abs(self.p.y - 464) < 250:
            self.service3d.update(dt, self)
        self._sync_rope()
        self._update_boards()
        in_cab = self.mode == "play" and self.p.in_car and self.cam_mode == "cockpit" and self.location == "street"
        self.mirrors.update(self.car3ds.get(self.cur) if in_cab else None, in_cab, getattr(self, "sky_rgb", (140, 178, 222)))
        self.window_views.update(dt, self.location == "apartment" and self.mode == "play",
                                 getattr(self, "sky_rgb", (140, 178, 222)), self.darkness(), self.weather)
        d = self.delivery
        self.marker.enabled = bool(d) and self.location == "street"
        if d:
            self.marker.position = Vec3(d["x"], 0, -d["y"])
        under = self.location == "street" and self.p.x >= INTERIOR_X
        outside = self.location == "street" and playing and not under
        self.audio.rain({"sleet": 0.8, "rain": 0.9, "snow": 0.25}.get(self.weather, 0.0) if outside else 0.0)
        walking = playing and top is None and not self.p.in_car and any(
            held_keys[k] for k in ("w", "a", "s", "d", "up arrow", "down arrow", "left arrow", "right arrow"))
        self.hands3d.update(dt if (top is None or getattr(top, "time_flows", False)) else 0.0,
                            self.mode == "play" and not self.p.in_car and not self.show_map and not self.p.under_car, walking)
        self.hud.fade_a = max(0.0, self.hud.fade_a - dt * 0.8)
        driving = self.p.in_car and self.location == "street" and playing
        hud_on = playing or self.mode == "gameover"
        self.hud.update(dt, {
            "hud": hud_on and self.mode != "gameover", "place": self.place(), "prompt": prompt,
            "cross": self.mode == "play" and (not self.p.in_car or self.cam_mode == "cockpit") and top is None
            and not self.show_map,
            "aim": bool(getattr(self, "aim", None)),
            "driving": driving and not isinstance(top, CarWork), "clutch": held_keys["space"],
            "yaw": self._view_yaw(),
            "precip": self.weather if self.weather in ("snow", "sleet", "rain") and outside else None,
            "speed": abs(self.car.speed) if self.p.in_car else 0.0,
            "hands": None if self.p.in_car else [self._hand_txt(i) for i in (0, 1)],
        })
        self.mapview.root.enabled = self.show_map and top is None
        if self.show_map:
            self.mapview.update(self)
        lock = self.mode == "play" and top is None and not self.show_map
        if lock != self._locked:
            self._locked = lock
            self.mouselook.set(lock)

    def _service_actions(self):
        """Автосервис: машина в ячейке цеха — сдать в ремонт; у стойки — узнать, что с машинами."""
        import service
        from world import SERVICE_DOOR_PT
        p = self.p
        out = []
        for k, c in self.owned_cars():
            if service.in_service(c) or abs(c.x - p.x) + abs(c.y - p.y) > 8:
                continue
            if service.bay_of(c) is not None and abs(c.speed) < 0.5:
                out.append((f"{service.NAME}: сдать {c.name} на осмотр и ремонт" +
                            (" (бессрочная гарантия)" if service.has_warranty(c) else ""),
                            lambda k=k: service.reception(self, k)))
        if not p.in_car and math.hypot(p.x - SERVICE_DOOR_PT[0], p.y - SERVICE_DOOR_PT[1]) < 3.0:
            out.append((f"Приёмка {service.NAME}: мои машины", lambda: service.office(self)))
        return out

    def _build_boards(self):
        """Доски объявлений у магазинов, Rathaus, вокзала, полиции: на них висят листовки «Gestohlen!»."""
        self.boards = {}
        for bid, (lab, bx, by) in theft.BOARDS.items():
            root = Entity(position=(bx, 0, -by))
            for dx in (-0.55, 0.55):
                Entity(parent=root, model="cube", color=color.rgb(90, 70, 50), position=(dx, 0.9, 0), scale=(0.07, 1.8, 0.07))
            Entity(parent=root, model="cube", color=color.rgb(150, 110, 70), position=(0, 1.45, 0), scale=(1.3, 0.85, 0.05))
            Entity(parent=root, model="cube", color=color.rgb(70, 60, 50), position=(0, 1.92, 0), scale=(1.45, 0.08, 0.2))
            for k in range(3):                                   # старые бумажки (Wohnung zu vermieten и т. п.)
                Entity(parent=root, model="cube", color=color.rgb(225, 220, 200), position=(-0.4 + k * 0.33, 1.6 - (k % 2) * 0.3, -0.03),
                       scale=(0.18, 0.24, 0.01), rotation_z=(k - 1) * 4)
            self.boards[bid] = [root, []]
        self._boards_sig = None

    def _update_boards(self):
        sig = tuple((k, tuple(c.stolen["boards"]) if c.stolen else ()) for k, c in self.owned_cars())
        if sig == self._boards_sig:
            return
        self._boards_sig = sig
        for bid, (root, papers) in self.boards.items():
            for e in papers:
                destroy(e)
            papers.clear()
            n = sum(1 for k, c in self.owned_cars() if c.stolen and bid in c.stolen["boards"] and not c.stolen["found"])
            for j in range(n):
                sh = Entity(parent=root, model="cube", color=color.rgb(245, 245, 240), position=(0.3 - j * 0.3, 1.35, -0.035),
                            scale=(0.24, 0.32, 0.01))
                Entity(parent=sh, model="cube", color=color.rgb(200, 30, 30), position=(0, 0.38, -0.6), scale=(0.9, 0.18, 1))
                papers.append(sh)

    def _hand_txt(self, i):
        e = self.p.hands[i]
        if not e:
            return ("Л" if i == 0 else "П") + ": пусто"
        if e["id"] in ("key", "flyer"):
            import storage
            return ("Л" if i == 0 else "П") + ": " + storage.label(e)
        it = ITEMS.get(e["id"], {})
        tail = f" {e['cond']:.0f}%" if it.get("kind") in ("food", "drink", "part") else ""
        return ("Л" if i == 0 else "П") + ": " + it.get("name", e["id"]).split(" (")[0] + tail

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
        L = self.world.level_at(self.p.x, self.p.y)
        if L:
            return f"{L['name']}, Ebene {'−1' if L['no'] == -1 else '−2'}"
        P = self.world.places.parking_at(self.p.x, self.p.y)
        if P:
            return P["name"]
        r = self.world.road_at(self.p.x, self.p.y)
        if r:
            return r[5]
        if self.p.in_car:
            return f"{'Пассажир' if self.p.seat == 'passenger' else 'За рулём'} {self.car.name}"
        return "Kleinbruck"

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
        theft.update(self)                                 # пропажа замечена / машина нашлась
        if p.under_car:                                    # лежит под машиной (under_play.py)
            pr = self.update_under(dt, free)
            if p.under_car:
                return pr + self.find_actions()
        if free:
            if p.in_car:
                self._mouse_look(limit_yaw=110)
                if abs(self.mouselook.dx) < 0.5:
                    self.look_yaw *= max(0.0, 1 - dt * 0.8)
            else:
                self._mouse_look()
        if p.in_car and p.seat == "passenger":
            # пассажир: машиной не управляет, просто сидит справа (может пересесть за руль или выйти)
            self.car_input = {}
            p.x, p.y = car.x, car.y
            self._car_camera(dt)
        elif p.in_car:
            if free:
                thr = 1.0 if (held_keys["w"] or held_keys["up arrow"]) else 0.0
                brk = 1.0 if held_keys["s"] else 0.0
                hb = 1.0 if held_keys["down arrow"] else 0.0          # стрелка вниз — ручник (дрифт)
                self.throttle += (thr - self.throttle) * min(1, dt * 5)
                self.brake += (brk - self.brake) * min(1, dt * 8)
                steer = (held_keys["d"] or held_keys["right arrow"]) - (held_keys["a"] or held_keys["left arrow"])
                if p.drunk > 20:
                    steer += math.sin(self.t * 1.3) * p.drunk / 180
                self.car_input = {"throttle": self.throttle, "brake": self.brake, "steer": steer,
                                  "clutch": bool(held_keys["space"]), "handbrake": hb}
                if car.cranking and not held_keys["i"]:
                    car.stop_crank()
                if getattr(self, "_crank_after_key", False) and not self.hands3d.busy:
                    self._crank_after_key = False          # ключ вставлен и повёрнут — стартер, пока держите I
                    if held_keys["i"] and keys_mod.can_start(car):
                        car.start_crank()
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
                    # пешком через въезд / пандус подземного гаража
                    pt = self.world.places.portal_for(p.x, p.y, dx, dy)
                    if pt:
                        tx, ty, ta = pt["to"]
                        p.x, p.y = tx, ty
                        self.yaw = math.degrees(math.atan2(math.cos(ta), -math.sin(ta)))
                        self.notify(pt["label"], YELLOW, 3)
                        self.play_sound("door", 0.5)
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
                car.vlat = car.ang_vel = 0.0
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
            if self.p.seat == "passenger":
                ex = -ex                                # пассажирское место — справа
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

    # ------------------------------------------------------------------ взаимодействие прицелом
    def _aim(self):
        """На что смотрит перекрестие: дверь, сиденье, капот, багажник, болт, переключатель поворотников."""
        if self.location != "street" or self.mode != "play":
            return None
        inside = self.p.in_car
        if inside and self.cam_mode != "cockpit":
            return None
        cam = camera.world_position
        fwd = camera.forward
        best, score = None, 9.0
        lying = self.p.under_car
        cands = [(self.cur, self.car3ds.get(self.cur))] if inside else \
            [(lying, self.car3ds.get(lying))] if lying else \
            [(k, c3) for k, c3 in self.car3ds.items() if abs(c3.car.x - self.p.x) + abs(c3.car.y - self.p.y) < 8]
        for key, c3 in cands:
            if c3 is None:
                continue
            owned = bool(self.owned.get(key))
            tl = list(c3.targets(inside, owned, self.p.seat))
            if not inside:
                tl += self._place_targets(key, c3)
                tl += self._uc_targets(key, c3)
                tl = self._uc_filter(key, tl)                  # сверху — верх, лёжа под машиной — низ
            for tid, pos, r in tl:
                v = pos - cam
                d = v.length()
                reach = 2.15 if tid[0] in ("bolt", "place", "part") else (1.7 if inside else 2.7)   # над отсеком можно наклониться
                if lying:
                    reach = UNDER_REACH                        # лёжа — на длину руки
                if d > reach or d < 0.05:
                    continue
                cosang = max(-1.0, min(1.0, v.normalized().dot(fwd)))
                ang = math.acos(cosang)
                lim = math.atan2(r, d) + 0.025
                if ang < lim and ang / lim < score:
                    score, best = ang / lim, (key, tid)
        return best

    def _place_targets(self, key, c3):
        """Пустые места под детали, которые есть под рукой (поставить руками), и снятие отпущенных деталей."""
        out = []
        car = c3.car
        if not c3.bolt_ents:
            return out
        seen = set()
        for k, i, e, p0 in c3.bolt_ents:
            if k in seen:
                continue
            seen.add(k)
            parent = e.parent
            pos = parent.world_position
            if fast.states(car, k):
                if fast.tight(car, k) == 0:
                    out.append((("part", k), pos, 0.12))
            elif self._inv_for(car, k) is not None:
                out.append((("place", k), pos, 0.14))
        return out

    def _pid_for(self, car, k):
        if k.startswith("eng:"):
            return eng_mod.part_id(car.model, k[4:])
        return car.slots[k][1] if k in car.slots else None

    def _inv_for(self, car, k):
        pid = self._pid_for(car, k)
        cands = [e for e in self.available() if e["id"] == pid]
        return max(cands, key=lambda e: e["cond"]) if cands else None

    def _aim_action(self, aim):
        """(подпись, действие, второе действие для G или None)."""
        key, tid = aim
        car = self.cars[key]
        c3 = self.car3ds[key]
        kind = tid[0]
        if kind in ("under", "jackpt"):
            return self._uc_action(key, tid)
        rear = " заднюю" if kind.startswith("door") and str(tid[1]).endswith("b") else ""
        if kind == "door_open_in":
            return (f"Открыть{rear} дверь", lambda: self._door(car, tid[1], True, inside=True), None)
        if kind == "door_open":
            alt = None
            if car.locked and self.has("crowbar"):
                alt = ("Вскрыть дверь монтировкой (замок сломается)", lambda: self._break_in(car, tid[1]))
            return (f"Открыть{rear} дверь", lambda: self._door(car, tid[1], True), alt)
        if kind == "ign":
            a = self.ignition_action()
            return (a[0], a[1], None)
        if kind == "door_close":
            return (f"Закрыть{rear} дверь", lambda: self._door(car, tid[1], False), None)
        if kind == "titem":
            idx = tid[1]
            if idx < len(car.trunk_items):
                e = car.trunk_items[idx]
                import storage
                return (f"Взять из багажника: {storage.label(e)}", lambda: self._trunk_take(car, e),
                        ("Положить в багажник…", lambda: self._trunk_put(car)))
            return None
        if kind == "tput":
            n = len(car.trunk_items)
            return (f"Положить в багажник… (внутри {n})", lambda: self._trunk_put(car), None)
        if kind == "seat":
            if tid[1] == "r":
                return (f"Сесть на пассажирское место — {car.name}", lambda: self._sit(key, "passenger"), None)
            return (f"Сесть за руль — {car.name}", lambda: self._sit(key), None)
        if kind == "seat_move":
            return ("Пересесть за руль", lambda: self._move_seat("driver"), None)
        if kind == "exit":
            return ("Выйти из машины", self.toggle_car, None)
        if kind == "stalk":
            d = -1 if tid[1] == "l" else 1
            lab = ("Выключить " if car.turn == d else "Включить ") + ("левый" if d < 0 else "правый") + " поворотник"
            return (lab, lambda: self._blinker(d), None)
        if kind == "hood":
            if getattr(car, "hood_open", False):
                return ("Закрыть капот", lambda: self._hood(key, False),
                        ("Работа с машиной (меню)", lambda: self.open_carwork(key)) if self.owned.get(key) else None)
            if self.owned.get(key):
                return ("Открыть капот — работа с машиной", lambda: self.open_carwork(key), None)
            return ("Открыть капот", lambda: self._hood(key, True), None)
        if kind == "fusebox":
            from actions import FuseBox
            nb = sum(1 for v in elec.data(car)["fuses"].values() if v == "blown")
            return (f"Блок предохранителей — осмотреть" + (f" (перегорело: {nb})" if nb else ""),
                    lambda: self.open_menu(FuseBox(self, key)), None)
        if kind == "efault":
            k = tid[1]
            f = elec.fault(car, k)
            if not f:
                return None
            need, what = elec.fix_needs(car, k)
            have = "" if (need is None or need.startswith("slot:") or self.has(need)) else " — нет под рукой"
            return (f"Устранить: {elec.KIND_SHORT[f['kind']]} — {elec.circuit_name(car, k).lower()} "
                    f"(нужно: {what.split(' (')[0].lower()}{have})",
                    lambda: self._elec_fix(car, k), None)
        if kind == "trunk":
            return (("Закрыть" if car.trunk_open else "Открыть") + " багажник", lambda: self._trunk(car), None)
        if kind == "bolt":
            k, i = tid[1], tid[2]
            st = fast.states(car, k)
            sp = fast.spec(car, k)
            t = sum(st)
            name = self._part_name(car, k)
            if i < len(st) and st[i]:
                lab = f"Открутить: {sp[1]} — {name} ({t}/{sp[0]} затянуто)"
                act = lambda: self._bolt(key, k, i, False)
            else:
                lab = f"Затянуть: {sp[1]} — {name} ({t}/{sp[0]} затянуто)"
                act = lambda: self._bolt(key, k, i, True)
            alt = None
            if t == 0:
                alt = (f"Снять: {name}", lambda: self._take_part(key, k))
            return (lab, act, alt)
        if kind == "part":
            k = tid[1]
            return (f"Снять: {self._part_name(car, k)} (крепёж откручен)", lambda: self._take_part(key, k), None)
        if kind == "place":
            k = tid[1]
            e = self._inv_for(car, k)
            return (f"Поставить: {ITEMS.get(e['id'], {}).get('name', e['id'])} ({e['cond']:.0f}%) — наживить",
                    lambda: self._place_part(key, k), None)
        return None

    def _part_name(self, car, k):
        if k.startswith("eng:"):
            return eng_mod.label(car, k[4:])
        return car.slots[k][0] if k in car.slots else k

    def _door(self, car, side, open_, inside=False):
        if open_ and car.locked:
            if inside:
                car.locked = False                     # изнутри ручка отпирает
                self.play_sound("unlock", 0.5)
            else:
                self.play_sound("handle", 0.7)        # подёргали ручку — заперто
                self.notify(f"{car.name}: заперто." + (" Ключ в руке — K, чтобы отпереть." if
                                                      keys_mod.key_in_hands(self, car) is not None else ""), YELLOW, 3)
                return
        car.door_open[side] = open_
        self.play_sound("door", 0.6)

    def _break_in(self, car, side):
        if not self.need("crowbar", "монтировка"):
            return
        self.advance(3, working=True)
        car.locked = False
        car.lock_broken = True
        car.door_open[side] = True
        self.play_sound("crash", 0.3)
        self.notify(f"Дверь {car.name} вскрыта монтировкой. Замок сломан — машина больше не запирается "
                    "(замена замков — в меню работы с машиной).", YELLOW, 8)

    def _elec_fix(self, car, k):
        if car.running:
            self.notify("Сначала заглушите двигатель — под напряжением не работают.", RED)
            return
        r = elec.repair(self, car, k)
        if r:
            self.notify(r, GREEN, 7)

    def _trunk_take(self, car, e):
        import storage
        if storage.take(self, car.trunk_items, e):
            self.play_sound("door", 0.3)
            self.notify(f"Взяли из багажника: {storage.label(e)}", GREEN)

    def _trunk_put(self, car):
        from actions import StoragePut
        self.open_menu(StoragePut(self, car.trunk_items, "trunk", "Положить в багажник — " + car.name))

    def _trunk(self, car):
        if not car.trunk_open and car.locked:
            self.play_sound("handle", 0.6)
            self.notify(f"{car.name}: багажник заперт.", YELLOW, 3)
            return
        car.trunk_open = not car.trunk_open
        self.play_sound("door", 0.5)

    def _hood(self, key, open_):
        c3 = self.car3ds.get(key)
        if c3:
            c3.set_hood(open_)
        self.play_sound("door", 0.5)

    def _blinker(self, d):
        car = self.car
        car.turn = 0 if car.turn == d else d
        car._turn_peak = 0.0
        car.blink_t = 0.0
        self.play_sound("click", 0.7)

    def _move_seat(self, seat):
        self.p.seat = seat
        self.look_yaw = 0
        self.notify("Вы пересели за руль." if seat == "driver" else "Вы на пассажирском месте.")

    def _sit(self, key, seat="driver"):
        """Сесть через открытую дверь (водитель — слева, пассажир — справа)."""
        if self.tow and key == self.tow.get("key"):
            self.notify("Эта машина на тросе. Садитесь в машину-тягач.", YELLOW)
            return
        if getattr(self.cars[key], "service", None):
            import service
            self.notify(f"{self.cars[key].name} {service.ready_text(self, self.cars[key])}.", YELLOW, 5)
            return
        self.cur = key
        self.p.in_car = True
        self.p.seat = seat
        self.look_yaw = 0
        self.pitch = 0
        self.cam_mode = "cockpit"
        self.play_sound("door", 0.4)
        if seat == "passenger":
            self.notify("Вы на пассажирском месте. Выйти — E на двери (или F). Пересесть за руль — E на водительском "
                        "сиденье.", YELLOW, 6)
            return
        car = self.car
        if not car.registered:
            self.notify(f"Внимание: {car.name} без номеров и страховки. Не попадитесь полиции!", (230, 140, 40), 6)
        self.notify("Закройте дверь: E на ручке двери изнутри. Выйти — E на открытой двери (или F).", YELLOW, 6)

    def _hands_ok(self, car):
        if not self.need("toolbox"):
            return False
        if car.running:
            self.notify("Сначала заглушите двигатель.", RED)
            return False
        return True

    def _bolt(self, key, k, i, tighten):
        car = self.cars[key]
        if not self._hands_ok(car):
            return
        self.advance(fast.minutes_each(car, k), working=True)
        if tighten:
            fast.screw(car, k, i)
        else:
            fast.unscrew(car, k, i)
        self.play_sound("tool", 0.5)
        left = fast.tight(car, k)
        if not tighten and left == 0:
            self.notify(f"Весь крепёж отпущен — теперь деталь можно снять (G).", GREEN)
        if tighten and fast.fully(car, k):
            self.notify(f"{self._part_name(car, k)}: весь крепёж затянут.", GREEN)

    def _take_part(self, key, k):
        car = self.cars[key]
        if not self._hands_ok(car):
            return
        if fast.tight(car, k):
            self.notify("Сначала открутите весь крепёж.", RED)
            return
        if k.startswith("eng:"):
            ok, why = eng_mod.can_remove(car, k[4:])
            if not ok:
                self.notify(why, RED)
                return
            self.advance(max(5, int(eng_mod.minutes(car, k[4:]) * 0.3)), working=True)
            entry = eng_mod.take_off(car, k[4:])
        else:
            b = eng_mod.blockers(car, "slot:" + k) if car.eng and car.parts.get("engine") else []
            if b:
                self.notify("Сначала снимите: " + ", ".join(eng_mod.label(car, x) for x in b), RED)
                return
            part = car.parts[k]
            self.advance(max(5, int(car.slots[k][2] * 0.3)), working=True)
            car.parts[k] = None
            entry = {"id": part["id"], "cond": round(float(part["cond"]), 1)}
            if k == "engine":
                entry["sub"] = eng_mod.remove_whole(car)
        fast.on_removed(car, k)
        self.give(entry)
        self.play_sound("tool", 0.6)
        self.notify(f"Снято руками: {ITEMS.get(entry['id'], {}).get('name', entry['id'])} ({entry['cond']:.0f}%)", GREEN)

    def _place_part(self, key, k):
        car = self.cars[key]
        if not self._hands_ok(car):
            return
        e = self._inv_for(car, k)
        if e is None:
            return
        if k.startswith("eng:"):
            ok, why = eng_mod.can_install(car, k[4:])
            if not ok:
                self.notify(why, RED)
                return
            self.take_item(e["id"], e)
            self.advance(max(5, int(eng_mod.minutes(car, k[4:]) * 0.3)), working=True)
            eng_mod.put_on(car, k[4:], e, True)
        else:
            mn = eng_mod.missing_needs(car, "slot:" + k) if car.eng and car.parts.get("engine") else []
            b = eng_mod.blockers(car, "slot:" + k) if car.eng and car.parts.get("engine") else []
            if mn or b:
                self.notify(("Сначала поставьте: " + ", ".join(eng_mod.label(car, x) for x in mn)) if mn else
                            ("Мешает: " + ", ".join(eng_mod.label(car, x) for x in b)), RED)
                return
            self.take_item(e["id"], e)
            self.advance(max(5, int(car.slots[k][2] * 0.3)), working=True)
            car.parts[k] = {"id": e["id"], "cond": e["cond"]}
            elec.on_slot_installed(car, k)
            if k == "engine":
                eng_mod.install_whole(car, e)
        fast.on_placed(car, k, tightened=False)
        self.play_sound("tool", 0.6)
        self.notify(f"Деталь на месте, но крепёж только наживлен — затяните все {fast.total(car, k)} шт. (E на каждом).",
                    YELLOW, 7)

    def find_actions(self):
        p, car = self.p, self.car
        if p.under_car:
            return self._find_actions_under()
        acts = []
        self.aim = self._aim()
        aim_alt = None
        if self.aim and self.aim[0] in self.cars:
            a = self._aim_action(self.aim)
            if a:
                acts.append((a[0], a[1]))
                aim_alt = a[2]
        # болты — только у машины, возле которой стоит игрок
        if not p.in_car and self.location == "street":
            near = min(self.car3ds, key=lambda k: abs(self.car3ds[k].car.x - p.x) + abs(self.car3ds[k].car.y - p.y),
                       default=None)
            for k, c3 in self.car3ds.items():
                close = k == near and abs(c3.car.x - p.x) + abs(c3.car.y - p.y) < 5.5
                c3.ensure_bolts(close)
                c3.ensure_live(k == self.cur and (close or c3.car.turn != 0))
        else:
            for k, c3 in self.car3ds.items():
                c3.ensure_bolts(False)
                c3.ensure_live(k == self.cur)
        self.rope_action = None
        self.dismantle_action = None
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
                acts.append(("Колонка «Luft»: проверить и подкачать шины (бесплатно)",
                             lambda: self.open_menu(__import__("actions").TireMenu(self, self.cur, station=True))))
            if point_in(TUV_YARD, car.x, car.y):
                acts.append(("Пройти TÜV (техосмотр)", self.tuv))
            acts += self._service_actions()
            if self.cur in self.cars_in_sell_zone() and abs(car.speed) < 1:
                acts.append((f"Предложить Weber: {car.name} ({self.dealer_offer(self.cur):.0f} DM) — выйдите и зайдите в контору",
                             lambda: self.notify("Заглушите мотор, выйдите и зайдите в контору Weber (E у двери).")))
        else:
            for bid, b in BUILDINGS.items():
                door = b[7]
                if door and math.hypot(p.x - door[0], p.y - door[1]) < 3.0:
                    acts.append((f"Войти: {b[4]}", lambda bid=bid: self.enter_building(bid)))
                    break
            # заброшенные гаражи: ворота и полки
            for ag in self.world.abandoned:
                gs = self.garages.get(ag["id"], {})
                dpx, dpy = ag["door_pt"]
                if not gs.get("open") and math.hypot(p.x - dpx, p.y - dpy) < 3.2:
                    lock = " (заперто — нужна монтировка)" if ag["locked"] and not self.has("crowbar") else ""
                    acts.append((f"Открыть ворота: {ag['name']}{lock}", lambda g_=ag["id"]: self.garage_door(g_)))
                spx, spy = ag["shelf_pt"]
                if gs.get("open") and not gs.get("looted") and math.hypot(p.x - spx, p.y - spy) < 2.0:
                    acts.append(("Обыскать полки", lambda g_=ag["id"]: self.search_shelves(g_)))
            gx, gy, gw, gh = GARAGE
            if math.hypot(p.x - (gx + 6.85), p.y - (gy + gh - 0.9)) < 2.2:
                from actions import StorageTake
                acts.append((f"Стеллаж в гараже (вещей: {len(self.shelf)})",
                             lambda: self.open_menu(StorageTake(self, self.shelf, "shelf", "Стеллаж в гараже"))))
            acts += theft.board_actions(self)
            acts += self._service_actions()
            li = self.nearest_loose(p.x, p.y)
            if li is not None:
                it = self.loose[li]
                acts.append((f"Подобрать: {item_name(it['id'])} ({it['cond']:.0f}%)", lambda i=li: self.pick_loose(i)))
            wreck = self.nearest_wreck(p.x, p.y)
            own = self.nearest_car(p.x, p.y) if self.near_car() else None
            sale = wreck if wreck is not None and wreck in self.dealer["stock"] else None
            if sale is not None:
                acts.append((f"Weber продаёт: {self.cars[sale].name} — {self.dealer['stock'][sale]:.0f} DM (осмотреть)",
                             lambda k=sale: self.open_menu(Dealer(self, k))))
                wreck = None

            def dist_to(k):
                return min(math.hypot(p.x - cx, p.y - cy) for cx, cy, _ in self.cars[k].body_circles())

            # E относится к той машине, что ближе: брошенная находка важнее, если стоим у неё
            find_first = wreck is not None and (own is None or dist_to(wreck) <= dist_to(own) + 0.3)
            if find_first:
                acts.append((f"Забрать себе бесплатно: {self.cars[wreck].name} (осмотреть)",
                             lambda k=wreck: self.find_offer(k)))
            if own is not None:
                acts.append((f"Открыть капот — {self.cars[own].name}", self.open_carwork))
                if point_in(PUMP_ZONE, self.cars[own].x, self.cars[own].y):
                    acts.append(("Заправить машину", self.refuel))
                    acts.append(("Колонка «Luft»: шины (давление, бесплатно)",
                                 lambda k=own: self.open_menu(__import__("actions").TireMenu(self, k, station=True))))
            if not find_first and self.nearest_car(p.x, p.y, 3.0, owned_only=False) == "ae86" and not self.owned["ae86"]:
                acts.append(("Осмотреть Toyota AE86 (Ковальский отдаёт даром)", self.ae86_offer))
            if wreck is not None and not find_first:
                acts.append((f"Забрать себе бесплатно: {self.cars[wreck].name} (осмотреть)",
                             lambda k=wreck: self.find_offer(k)))
            # разборка (R): бесхозные машины и свои (кроме ВАЗ/AE86 и машины на тросе)
            dk = wreck if wreck is not None else own
            if dk is not None and dk not in MAIN_CARS and not (self.tow and dk in (self.tow["key"], self.tow["by"])):
                self.dismantle_action = dk
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
        ea = self.eat_action()
        if ea:
            acts.insert(1 if (self.aim and acts and self.aim[0] in self.cars) else 0, ea)
        if aim_alt:
            acts.insert(1, aim_alt)
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
        if len(acts) > 1 and not p.in_car:
            extra.append(f"G — {acts[1][0]}")
        if self.rope_action:
            extra.append(f"T — {self.rope_action[0]}")
        if self.dismantle_action and not p.in_car:
            extra.append(f"R — разобрать на запчасти")
        if p.in_car and self.tow and self.tow["by"] == self.cur:
            warn = "  ⚠ ТИШЕ!" if car.kmh() > 45 else ""
            extra.append(f"На тросе: {self.tow_name()} — не быстрее 50 км/ч{warn}")
        if extra:
            prompt.append("   ·   ".join(extra))
        return prompt

    def _find_actions_under(self):
        """Лёжа под машиной: болты и детали снизу, меню работ снизу, вылезти."""
        p = self.p
        key = p.under_car
        for k, c3 in self.car3ds.items():
            c3.ensure_bolts(k == key)
            c3.ensure_live(False)
        self.rope_action = None
        self.dismantle_action = None
        acts = []
        self.aim = self._aim()
        alt = None
        if self.aim and self.aim[0] in self.cars:
            a = self._aim_action(self.aim)
            if a:
                acts.append((a[0], a[1]))
                alt = a[2]
        if alt:
            acts.append(alt)
        acts.append(("Работы снизу — меню (детали, низ двигателя, слить масло)", self.open_underwork))
        self.actions = acts
        prompt = [f"E — {acts[0][0]}"]
        extra = []
        if len(acts) > 1:
            extra.append(f"G — {acts[1][0]}")
        extra.append("F — вылезти")
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
        ea = self.eat_action()
        if ea:
            self.actions.append(ea)
        if not self.actions:
            return []
        pr = [f"E — {self.actions[0][0]}"]
        if len(self.actions) > 1:
            pr.append(f"G — {self.actions[1][0]}")
        return pr

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
