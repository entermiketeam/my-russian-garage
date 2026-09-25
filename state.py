"""Логика игры без графики: время, потребности, деньги, погода, машина, сохранение.

Используется и 3D-версией (main.py), и старой 2D-версией (main2d.py)."""
import datetime
import json
import math
import os
import random


SAVE_FILE = "savegame.json"
WHITE = (240, 240, 235)
RED = (210, 60, 50)
GREEN = (90, 190, 90)
YELLOW = (240, 200, 60)
from car import Car
from world import World, BUILDINGS, GARAGE, AE86_SPOT, SCRAP_DROP, point_in
from items import ITEMS, item_name
from models import MODELS

START_DATE = datetime.datetime(1998, 10, 1, 0, 0)  # четверг
WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
RENT = 105.0
INSURANCE = 24.0
AE86_PRICE = 0.0          # Ковальский отдаёт AE86 бесплатно — лишь бы забрали со свалки
ROPE_LEN = 4.0
ROPE_SNAP_KMH = 55
CAR_NAMES = {"vaz": "ВАЗ 2102", "ae86": "Toyota AE86"}
MAIN_CARS = ("vaz", "ae86")      # стартовые машины: их нельзя сдать на лом
MAX_FINDS = 7                    # сколько бесхозных находок может стоять на карте одновременно

# Часы работы: id -> {день недели: (открытие, закрытие)}; нет ключа — закрыто
_WD = {d: None for d in range(7)}


def hours(week, sat=None, sun=None):
    h = {d: week for d in range(5)}
    if sat:
        h[5] = sat
    if sun:
        h[6] = sun
    return h


OPEN_HOURS = {
    "supermarkt": hours((8, 20), (8, 16)),        # Ladenschlussgesetz 1998
    "autoteile": hours((9, 18), (9, 13)),
    "imbiss": hours((11, 23), (11, 23), (12, 22)),
    "pizzeria": hours((11, 23), (11, 23), (12, 22)),
    "rathaus": hours((8, 16)),
    "tuv": hours((8, 17), (9, 13)),
    "schrott": hours((7, 19), (7, 16)),
    "lager": hours((6, 18)),
    "tanke": hours((0, 24), (0, 24), (0, 24)),
}


class Player:
    def __init__(self):
        self.x, self.y = 330.0, 311.0
        self.in_car = False
        self.money = 420.0
        self.hunger = 70.0
        self.thirst = 60.0
        self.energy = 85.0
        self.hygiene = 70.0
        self.health = 100.0
        self.drunk = 0.0
        self.inventory = [{"id": "toolbox", "cond": 100}, {"id": "rope", "cond": 100},
                          {"id": "wasser", "cond": 100}, {"id": "brot", "cond": 100}]

    FIELDS = ["x", "y", "in_car", "money", "hunger", "thirst", "energy", "hygiene", "health",
              "drunk", "inventory"]

    def to_dict(self):
        return {k: getattr(self, k) for k in self.FIELDS}

    def from_dict(self, d):
        for k in self.FIELDS:
            if k in d:
                setattr(self, k, d[k])


class GameState:
    def __init__(self):
        self.world = World()
        self.t = 0.0
        self.new_state()

    # ---- «крючки» для графической части
    def notify(self, s, color=WHITE, t=5.0):
        print(s)

    def play_sound(self, name, vol=1.0):
        pass

    def engine_audio(self, inp):
        pass

    # ---------------------------------------------------------------- состояние
    def new_state(self):
        self.p = Player()
        self.cars = {"vaz": Car("vaz2102"),
                     "ae86": Car("ae86", AE86_SPOT[0], AE86_SPOT[1], angle=math.pi)}
        self.owned = {"vaz": True, "ae86": False}
        self.cur = "vaz"
        self.goal_done = False
        self.minutes = 8 * 60.0
        self.weather = "cloudy"
        self.weather_timer = 180.0
        self.last_day = 0
        self.last_mama = -10
        self.delivery = None
        self.schrott_stock = []
        self.schrott_day = -1
        self.car_input = {}
        self.fines = 0.0
        self.pending_faint = False
        self.game_over = None
        self.police_cd = 0.0
        self.blitz_cd = {}
        self.stats = {"deliveries": 0, "shifts": 0, "scrapped": 0, "km_start": self.car.odometer, "day_goal": None}
        self.wreck_id = 0
        self.tow = None      # {"kind": "car", "key": ..., "by": ключ машины-тягача}
        rng = random.Random(5)
        first = ["trabant", "kadett", "golf", "wartburg", "taunus", "w123"]
        rng.shuffle(first)
        levels = [0.80, 0.62, 0.46, 0.30, 0.14]      # от почти живой до трупа
        rng.shuffle(levels)
        for spot, model, lvl in zip(rng.sample(self.world.wreck_spots, 5), first, levels):
            self.spawn_wreck(spot, rng, model, lvl)     # на старте — пять разных моделей

    # ---------------------------------------------------------------- найденные машины
    @property
    def wrecks(self):
        """Бесхозные машины на карте (их можно забрать себе бесплатно)."""
        return [c for k, c in self.cars.items() if k not in MAIN_CARS and not self.owned.get(k)]

    def wreck_keys(self):
        return [k for k in self.cars if k not in MAIN_CARS and not self.owned.get(k)]

    def spawn_wreck(self, spot=None, rng=random, model=None, pres=None):
        if spot is None:
            free = [sp for sp in self.world.wreck_spots
                    if all(math.hypot(sp[0] - c.x, sp[1] - c.y) > 8 for c in self.cars.values())]
            if not free:
                return None
            spot = rng.choice(free)
        if model is None:
            model = rng.choices(list(MODELS), [m["spawn"] for m in MODELS.values()])[0]
        self.wreck_id += 1
        key = f"w{self.wreck_id}"
        angle = spot[2] + rng.uniform(-0.25, 0.25) + (math.pi if rng.random() < 0.5 else 0)
        car = Car(model, spot[0], spot[1], angle, rng=random.Random(rng.randint(0, 10 ** 9)), pres=pres)
        self.cars[key] = car
        self.owned[key] = False
        return key

    def scrap_value(self, key):
        car = self.cars[key]
        base = MODELS[car.model]["scrap"] if car.model in MODELS else 60
        parts = [pp["cond"] for pp in car.parts.values() if pp]
        avg = sum(parts) / len(parts) / 100 if parts else 0
        return round(base * (0.85 + 0.35 * avg) * (0.95 + (car.seed % 11) / 100), 2)

    def claim_car(self, key):
        """Забрать находку себе — бесплатно."""
        self.owned[key] = True

    def nearest_wreck(self, x, y, maxd=3.2):
        """Ключ ближайшей бесхозной находки (или None)."""
        best, bd = None, maxd
        for k in self.wreck_keys():
            c = self.cars[k]
            d = min(math.hypot(x - cx, y - cy) for cx, cy, _ in c.body_circles())
            if d < bd:
                best, bd = k, d
        return best

    def wrecks_in_drop(self):
        """Ключи машин на площадке приёма лома (кроме ВАЗ и AE86)."""
        return [k for k, c in self.cars.items() if k not in MAIN_CARS and point_in(SCRAP_DROP, c.x, c.y)]

    def remove_car(self, key):
        if self.tow and key in (self.tow.get("key"), self.tow.get("by")):
            self.cars[self.tow["by"]].tow_mass = 0.0
            self.tow = None
        if self.cur == key:
            self.cur = "vaz"
            self.p.in_car = False
        self.cars.pop(key, None)
        self.owned.pop(key, None)

    def towed_object(self):
        t = self.tow
        if not t:
            return None
        return self.cars.get(t.get("key"))

    def tow_name(self):
        obj = self.towed_object()
        return obj.name if obj else ""

    def rope_length(self, car, obj):
        """Длина троса: как машины стояли при привязке (4–10 м между бамперами), без рывка."""
        fx, fy = car.forward()
        back = car.length / 2 + 0.2
        hx, hy = car.x - fx * back, car.y - fy * back
        d = math.hypot(obj.x - hx, obj.y - hy)
        lo = ROPE_LEN + obj.length / 2
        return max(lo, min(lo + 6.0, d))

    def _step_tow(self, dt=1 / 60):
        t = self.tow
        if not t:
            return
        car = self.cars.get(t["by"])
        obj = self.towed_object()
        if obj is None or car is None:
            if car:
                car.tow_mass = 0.0
            self.tow = None
            return
        L = t.get("len") or self.rope_length(car, obj)
        t["len"] = L
        fx, fy = car.forward()
        back = car.length / 2 + 0.2
        hx, hy = car.x - fx * back, car.y - fy * back
        vx, vy = obj.x - hx, obj.y - hy
        d = math.hypot(vx, vy) or 1e-6
        taut = d > L
        if taut:
            ox, oy = hx + vx / d * L, hy + vy / d * L
            ang = math.atan2(hy - oy, hx - ox)
            # машина на тросе скользит вдоль заборов и деревьев, а не рвёт трос сразу
            for _ in range(3):
                hit = self.world.collide_circle(ox, oy, 0.9)
                if not hit:
                    break
                ox += hit[0] * hit[2]
                oy += hit[1] * hit[2]
            obj.x, obj.y, obj.angle, obj.speed = ox, oy, ang, 0.0
            stuck = math.hypot(ox - hx, oy - hy) > L + 1.5
            t["stuck"] = t.get("stuck", 0.0) + dt if stuck and abs(car.speed) > 1.5 else 0.0
            if t["stuck"] > 1.5:
                self.snap_rope("Трос соскочил — машина на тросе упёрлась в препятствие. "
                               "Отъедьте назад и привяжите снова (T).", lost=False)
                return
        car.tow_mass = obj.spec["mass"] * (0.85 if taut else 0.0)
        kmh = car.kmh()
        if kmh > ROPE_SNAP_KMH - 10 and not t.get("warned"):
            t["warned"] = True
            self.notify("Трос натянут как струна! На тросе — не быстрее 50 км/ч.", YELLOW, 5)
        if kmh < ROPE_SNAP_KMH - 15:
            t["warned"] = False
        t["over"] = t.get("over", 0.0) + dt if (kmh > ROPE_SNAP_KMH + 5 and taut) else 0.0
        if t["over"] > 1.0:
            self.snap_rope(f"Трос лопнул на {kmh:.0f} км/ч! Вы связали его узлом — привяжите снова (T) "
                           "и не гоните быстрее 50.", lost=False)

    def snap_rope(self, msg, lost=False):
        if self.tow and self.tow["by"] in self.cars:
            self.cars[self.tow["by"]].tow_mass = 0.0
        self.tow = None
        if lost:
            self.take_item("rope")
        self.play_sound("crash", 0.5)
        self.notify(msg, RED, 8)

    @property
    def car(self):
        """Текущая машина: за рулём которой сидим / которую чиним."""
        return self.cars[self.cur]

    def owned_cars(self):
        return [(k, c) for k, c in self.cars.items() if self.owned.get(k)]

    def nearest_car(self, x, y, maxd=2.6, owned_only=True):
        best, bd = None, maxd
        for k, c in self.cars.items():
            if owned_only and not self.owned.get(k):
                continue
            d = min(math.hypot(x - cx, y - cy) for cx, cy, _ in c.body_circles())
            if d < bd:
                best, bd = k, d
        return best

    def car_in_zone(self, rect):
        if self.p.in_car and point_in(rect, self.car.x, self.car.y):
            return self.cur
        for k, c in self.owned_cars():
            if point_in(rect, c.x, c.y):
                return k
        return None

    def goal_text(self):
        ae = self.cars["ae86"]
        if self.goal_done:
            return "Цель выполнена: AE86 на ходу и на учёте!"
        if not self.owned["ae86"]:
            return "Цель: забрать ржавую AE86 у Ковальского за гаражом (бесплатно)"
        if ae.tuv_until < self.day:
            return "Цель: починить AE86 и пройти TÜV"
        return "Цель: поставить AE86 на учёт в Rathaus"

    def check_goal(self):
        ae = self.cars["ae86"]
        if not self.goal_done and self.owned["ae86"] and ae.registered and ae.tuv_until >= self.day:
            self.goal_done = True
            self.stats["day_goal"] = self.day
            return True
        return False

    def save(self):
        d = {
            "player": self.p.to_dict(), "cars": {k: c.to_dict() for k, c in self.cars.items()},
            "owned": self.owned, "cur": self.cur, "goal_done": self.goal_done, "minutes": self.minutes,
            "wreck_id": self.wreck_id, "tow": self.tow,
            "weather": self.weather, "weather_timer": self.weather_timer,
            "last_day": self.last_day, "last_mama": self.last_mama, "stats": self.stats,
            "schrott_stock": self.schrott_stock, "schrott_day": self.schrott_day,
        }
        with open(SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        self.notify("Игра сохранена.", GREEN)

    def load(self):
        if not os.path.exists(SAVE_FILE):
            self.notify("Нет сохранения.", RED)
            return False
        with open(SAVE_FILE, encoding="utf-8") as f:
            d = json.load(f)
        self.new_state()
        self.p.from_dict(d["player"])
        if "cars" in d:
            # находки из нового сохранения заменят стартовые
            for k in self.wreck_keys():
                self.cars.pop(k, None)
                self.owned.pop(k, None)
            for k, cd in d["cars"].items():
                if k not in self.cars:
                    self.cars[k] = Car(cd.get("model", "vaz2102"))
                self.cars[k].from_dict(cd)
        elif "car" in d:                       # сохранение старой версии (одна машина)
            self.cars["vaz"].from_dict(d["car"])
        for k in ("minutes", "weather", "weather_timer", "last_day", "last_mama", "stats",
                  "schrott_stock", "schrott_day", "owned", "cur", "goal_done", "wreck_id", "tow"):
            if k in d:
                setattr(self, k, d[k])
        # сохранения прошлой версии: брошенные машины были простыми записями — превращаем в настоящие машины
        old_names = {"trabant", "wartburg", "kadett", "golf", "taunus", "w123"}
        for w in d.get("wrecks", []) if isinstance(d.get("wrecks"), list) else []:
            if w.get("model") in old_names:
                key = self.spawn_wreck((w["x"], w["y"], w.get("angle", 0.0)), random.Random(w.get("seed", 1)))
                if key:
                    self.cars[key].model = w["model"]
                    self.cars[key].__init__(w["model"], w["x"], w["y"], w.get("angle", 0.0),
                                            rng=random.Random(w.get("seed", 1)))
        for k in list(self.owned):
            if k not in self.cars:
                self.owned.pop(k)
        for k in self.cars:
            self.owned.setdefault(k, False)
        if self.tow and (self.tow.get("kind") != "car" or self.tow.get("key") not in self.cars
                         or self.tow.get("by") not in self.cars):
            self.tow = None
        if self.cur not in self.cars:
            self.cur = "vaz"
        self.stats.setdefault("scrapped", 0)
        # AE86 теперь продаётся на свалке Ковальского за гаражом
        if not self.owned.get("ae86"):
            self.cars["ae86"] = Car("ae86", AE86_SPOT[0], AE86_SPOT[1], angle=math.pi)
        self.notify("Игра загружена.", GREEN)
        return True

    # ---------------------------------------------------------------- время
    @property
    def day(self):
        return int(self.minutes // 1440)

    @property
    def hour(self):
        return (self.minutes % 1440) / 60.0

    def date(self):
        return START_DATE + datetime.timedelta(minutes=self.minutes)

    def weekday(self):
        return self.date().weekday()

    def time_str(self):
        d = self.date()
        return f"{WEEKDAYS_RU[d.weekday()]} {d.day:02d}.{d.month:02d}.{d.year}  {d.hour:02d}:{d.minute:02d}"

    def darkness(self):
        h = self.hour
        # октябрь: рассвет ~7:15, закат ~18:45
        if 7.5 <= h <= 18.3:
            return 0.0
        if 6.5 < h < 7.5:
            return (7.5 - h) * 0.8
        if 18.3 < h < 19.3:
            return (h - 18.3) * 0.8
        return 0.8

    def is_open(self, bid):
        oh = OPEN_HOURS.get(bid)
        if oh is None:
            return True
        span = oh.get(self.weekday())
        if not span:
            return False
        return span[0] <= self.hour < span[1]

    def hours_str(self, bid):
        oh = OPEN_HOURS.get(bid, {})
        wk = oh.get(0)
        sat = oh.get(5)
        s = f"Пн–Пт {wk[0]:02d}–{wk[1]:02d}" if wk else ""
        s += f", Сб {sat[0]:02d}–{sat[1]:02d}" if sat else ", Сб закрыто"
        s += ", Вс закрыто" if not oh.get(6) else ""
        return s

    def advance(self, minutes, sleeping=False, working=False):
        """Проходит игровое время: голод, жажда, усталость, ржавчина, счета."""
        if minutes <= 0:
            return
        self.minutes += minutes
        p = self.p
        k = 0.5 if sleeping else 1.0
        w = 1.35 if working else 1.0
        p.hunger -= 0.075 * minutes * k * w
        p.thirst -= 0.11 * minutes * k * w
        if sleeping:
            p.energy += 0.22 * minutes
        else:
            p.energy -= 0.085 * minutes * w * (1.3 if p.drunk > 30 else 1.0)
        p.hygiene -= 0.035 * minutes * (2.5 if working else 1.0)
        p.drunk = max(0.0, p.drunk - 0.07 * minutes)
        if p.hunger <= 0 or p.thirst <= 0:
            p.health -= 0.25 * minutes
            if int(self.minutes) % 30 == 0:
                self.notify("Вам плохо: " + ("голод" if p.hunger <= 0 else "жажда") + "!", RED)
        else:
            p.health = min(100.0, p.health + 0.05 * minutes)
        for a in ("hunger", "thirst", "energy", "hygiene"):
            setattr(p, a, max(0.0, min(100.0, getattr(p, a))))

        # машины: ржавчина
        for c in self.cars.values():
            c.rust_tick(minutes, wet=self.weather == "rain", in_garage=point_in(GARAGE, c.x, c.y))

        # погода
        self.weather_timer -= minutes
        if self.weather_timer <= 0:
            self.weather = random.choices(["clear", "cloudy", "rain"], [0.3, 0.4, 0.3])[0]
            self.weather_timer = random.uniform(120, 420)

        # новый день
        while self.day > self.last_day:
            self.last_day += 1
            self.on_new_day(self.last_day)

        if p.health <= 0:
            self.hospital("Вы потеряли сознание от истощения.")
        elif p.energy <= 0 and not sleeping:
            self.pending_faint = True

    def on_new_day(self, day):
        if len(self.wreck_keys()) < MAX_FINDS and random.random() < 0.8:
            key = self.spawn_wreck()
            if key:
                self.notify(f"Слух: у дороги бросили {self.cars[key].name}. Можно забрать себе (карта — M).", YELLOW, 8)
        if day % 7 == 0:
            self.charge(RENT, "Квартплата (Miete)", YELLOW, 8)
            for k, c in self.owned_cars():
                if c.registered:
                    self.charge(INSURANCE, f"Страховка и налог: {c.name}", YELLOW, 8)
            if self.p.money < -400:
                self.game_over = ("Вас выселили из квартиры за долги.\n"
                                  "Хозяин Herr Schröder сменил замки, а «копейку» увёз эвакуатор.")
        for k, c in self.owned_cars():
            if c.registered and 0 <= c.tuv_until < day:
                self.notify(f"{c.name}: срок TÜV истёк! Нужно пройти техосмотр.", RED, 8)

    def hospital(self, reason):
        self.notify(reason, RED, 8)
        self.charge(250, "Krankenhaus: счёт за лечение", RED, 8)
        self.p.health = 60
        self.p.hunger = max(self.p.hunger, 50)
        self.p.thirst = max(self.p.thirst, 50)
        self.p.energy = 70
        self.p.drunk = 0
        self.p.in_car = False
        ax, ay = BUILDINGS["apartment"][7]
        self.p.x, self.p.y = ax, ay - 1.5
        self.minutes += 10 * 60
        self.delivery = None
        for c in self.cars.values():
            c.engine_off()
            c.speed = 0

    # ---------------------------------------------------------------- инвентарь
    def count(self, item_id):
        return sum(1 for e in self.p.inventory if e["id"] == item_id)

    def has(self, item_id):
        return self.count(item_id) > 0

    def add_item(self, item_id, cond=100.0):
        self.p.inventory.append({"id": item_id, "cond": round(float(cond), 1)})

    def take_item(self, item_id, entry=None):
        if entry is not None and entry in self.p.inventory:
            self.p.inventory.remove(entry)
            return entry
        # берём лучший по состоянию
        cands = [e for e in self.p.inventory if e["id"] == item_id]
        if not cands:
            return None
        best = max(cands, key=lambda e: e["cond"])
        self.p.inventory.remove(best)
        return best

    # ---- деньги: всё в DM, округление до пфеннига
    def _add_money(self, delta):
        self.p.money = round(self.p.money + round(delta, 2), 2)

    def pay(self, amount, what=""):
        """Добровольная покупка: только если хватает денег."""
        amount = round(amount, 2)
        if self.p.money + 1e-9 < amount:
            self.notify(f"Не хватает денег: нужно {amount:.2f} DM, есть {max(0.0, self.p.money):.2f} DM.", RED)
            return False
        self._add_money(-amount)
        self.play_sound("cash", 0.5)
        return True

    def charge(self, amount, what="", color=RED, t=7.0):
        """Обязательный платёж (штраф, счёт, аренда) — может увести в минус."""
        amount = round(amount, 2)
        if amount <= 0:
            return 0.0
        self._add_money(-amount)
        if what:
            self.notify(f"{what}: -{amount:.2f} DM", color, t)
        return amount

    def earn(self, amount, what=""):
        amount = round(amount, 2)
        if amount <= 0:
            return
        self._add_money(amount)
        self.play_sound("cash", 0.6)
        self.notify(f"+{amount:.2f} DM {what}", GREEN)

    def consume(self, item_id):
        it = ITEMS[item_id]
        p = self.p
        p.hunger = min(100, p.hunger + it.get("hunger", 0))
        p.thirst = min(100, p.thirst + it.get("thirst", 0))
        p.energy = min(100, p.energy + it.get("energy", 0))
        p.drunk = min(100, p.drunk + it.get("drunk", 0))
        self.advance(3)
        self.notify(f"Вы употребили: {item_name(item_id)}")

    # ---------------------------------------------------------------- машина
    def step_car(self, dt):
        towed_key = self.tow["key"] if self.tow else None
        towing_key = self.tow["by"] if self.tow else None
        for key, car in list(self.cars.items()):
            driven = key == self.cur and self.p.in_car
            idle = (not driven and not car.running and not car.cranking and abs(car.speed) < 0.01
                    and key not in (towed_key, towing_key))
            if idle:
                continue     # стоящая заглушенная машина: физику не считаем
            inp = self.car_input if driven else {}
            car.update(dt, inp, rain=self.weather == "rain")
            if self._collide(car, driven):
                return
            if key == self.cur:
                for ev in car.events:
                    self.notify(ev, YELLOW if "!" not in ev else RED, 4)
                for s_ in car.sounds:
                    self.play_sound(s_, 0.6)
            car.events.clear()
            car.sounds.clear()
        self._step_tow(dt)
        # машины друг с другом (кроме пары «тягач — на тросе»)
        items = list(self.cars.items())
        for i, (ka, a) in enumerate(items):
            for kb, b in items[i + 1:]:
                if {ka, kb} == {towed_key, towing_key}:
                    continue
                if abs(a.x - b.x) > 7 or abs(a.y - b.y) > 7:
                    continue
                if abs(a.speed) < 0.01 and abs(b.speed) < 0.01:
                    continue
                for ax_, ay_, ar in a.body_circles():
                    hit = False
                    for bx_, by_, br in b.body_circles():
                        dx, dy = ax_ - bx_, ay_ - by_
                        d = math.hypot(dx, dy)
                        if 1e-6 < d < ar + br:
                            push = (ar + br - d) / 2
                            a.x += dx / d * push
                            a.y += dy / d * push
                            b.x -= dx / d * push
                            b.y -= dy / d * push
                            rel = abs(a.speed - b.speed)
                            if rel > 2:
                                a.impact(rel)
                                b.impact(rel)
                                if self.p.in_car and self.cur in (ka, kb):
                                    self.notify("Бум! Вы врезались в стоящую машину.", RED)
                            a.speed *= 0.3
                            b.speed *= 0.3
                            hit = True
                            break
                    if hit:
                        break
        self.engine_audio(self.car_input if self.p.in_car else {})

    def _collide(self, car, driven):
        """Столкновения со статикой и трафиком. True — если игрок попал в больницу."""
        for _ in range(2):
            for cx, cy, r in car.body_circles():
                hit = self.world.collide_circle(cx, cy, r)
                if hit:
                    nx, ny, depth = hit
                    car.x += nx * depth
                    car.y += ny * depth
                    fx, fy = car.forward()
                    vn = -(fx * nx + fy * ny) * car.speed
                    if vn > 1.5:
                        if car.impact(vn) and driven:
                            self.hospital("Тяжёлая авария!")
                            return True
                        if vn > 4 and driven:
                            self.notify(f"Удар! ({vn * 3.6:.0f} км/ч)", RED)
                    car.speed *= -0.15 if vn > 3 else 0.6
                    break
        for ai in self.world.ai:
            for cx, cy, r in car.body_circles():
                dx, dy = cx - ai.x, cy - ai.y
                d = math.hypot(dx, dy)
                if d < r + 1.4 and d > 1e-6:
                    push = (r + 1.4 - d)
                    car.x += dx / d * push * 0.7
                    car.y += dy / d * push * 0.7
                    ai.x -= dx / d * push * 0.3
                    ai.y -= dy / d * push * 0.3
                    fx, fy = car.forward()
                    ax, ay = math.cos(ai.angle), math.sin(ai.angle)
                    rel = abs((fx * car.speed - ax * ai.speed) * dx / d + (fy * car.speed - ay * ai.speed) * dy / d)
                    if rel > 2:
                        if car.impact(rel) and driven:
                            self.hospital("Тяжёлое ДТП!")
                            return True
                        if driven:
                            self.notify("ДТП! Вы врезались в машину.", RED)
                            if rel > 4:
                                self.charge(min(600, rel * 25), "Ущерб другому водителю")
                    car.speed *= 0.3
                    ai.speed = 0
                    break
        return False
