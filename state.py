"""Логика игры без графики: время, потребности, деньги, погода, машина, сохранение.

Используется и 3D-версией (main.py), и старой 2D-версией (main2d.py)."""
import underside as _under
import datetime
import json
import math
import os
import random
import i18n
from i18n import T


SAVE_FILE = "savegame.json"
WHITE = (240, 240, 235)
RED = (210, 60, 50)
GREEN = (90, 190, 90)
YELLOW = (240, 200, 60)
from car import Car
from world import World, BUILDINGS, GARAGE, AE86_SPOT, SCRAP_DROP, point_in
from items import ITEMS, item_name
from models import MODELS, model_info
from places import JUNK_SPOTS, DEALER_SPOTS, DEALER_SELL, INTERIOR_X
import winter as _winter
import damage as _damage
import engine as _engine
import electrics as _elec
import keys as _keys
import theft as _theft
import tires as _tires

START_DATE = datetime.datetime(1998, 12, 1, 0, 0)  # вторник, начало зимы
WEEKDAYS = [T("Понедельник"), T("Вторник"), T("Среда"), T("Четверг"), T("Пятница"), T("Суббота"), T("Воскресенье")]
WEEKDAYS_RU = [T("Пн"), T("Вт"), T("Ср"), T("Чт"), T("Пт"), T("Сб"), T("Вс")]
RENT = 0.0                # квартира своя — квартплаты нет (оставлено для совместимости)
START_MONEY = 3000.0      # стартовый баланс новой игры
INSURANCE = 24.0
# стоимость машины в хорошем состоянии (₽, рынок подержанных машин 1998)
BASE_VALUE = {"vaz2102": 900, "ae86": 4500, "trabant": 500, "wartburg": 800, "moskvich": 700, "kadett": 1200,
              "golf": 1700, "taunus": 1300, "w123": 3200, "volvo240": 2600, "bmw_e21": 2200, "audi80": 1600, "civic": 1900,
              "mustang": 7500}
WEATHER_RU = {"clear": T("ясно"), "cloudy": T("облачно"), "snow": T("снегопад"), "sleet": T("мокрый снег"), "rain": T("дождь")}
import calendar_de as cal
PART_KINDS = ["door_l", "door_r", "hood", "trunk", "seats", "lights", "tire_fl", "tire_fr", "tire_rl", "tire_rr",
              "engine", "gearbox", "battery", "alternator", "starter", "carb", "radiator", "exhaust", "glass"]
AE86_PRICE = 0.0          # Ковальский отдаёт AE86 бесплатно — лишь бы забрали со свалки
ROPE_LEN = 4.0
ROPE_SNAP_KMH = 55
CAR_NAMES = {"vaz": T("ВАЗ 2102"), "ae86": "Toyota AE86"}
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
    "dealer": hours((9, 18), (9, 14)),
}


class Player:
    def __init__(self):
        self.x, self.y = 330.0, 311.0
        self.in_car = False
        self.money = START_MONEY
        self.hunger = 70.0
        self.thirst = 60.0
        self.energy = 85.0
        self.hygiene = 70.0
        self.health = 100.0
        self.drunk = 0.0
        # инвентарь — ровно две руки: [левая, правая]; всё остальное лежит в мире (багажник, стеллаж, холодильник, земля)
        self.hands = [{"id": "wasser", "cond": 100.0}, {"id": "brot", "cond": 100.0}]
        self.legacy_items = []
        self.under_car = None       # под какой машиной лежит игрок (underside.py) — не сохраняется
        self.uc_pos = [0.0, 0.0]    # где под ней: поперёк (x) и вдоль (z) кузова, м

    FIELDS = ["x", "y", "in_car", "seat", "money", "hunger", "thirst", "energy", "hygiene", "health",
              "drunk", "hands"]
    seat = "driver"             # "driver" / "passenger" — где сидит игрок

    @property
    def inventory(self):
        """Что у игрока с собой — только то, что в руках (список для чтения)."""
        return [e for e in self.hands if e]

    def to_dict(self):
        return {k: getattr(self, k) for k in self.FIELDS}

    def from_dict(self, d):
        for k in self.FIELDS:
            if k in d:
                setattr(self, k, d[k])
        if not isinstance(self.hands, list) or len(self.hands) != 2:
            self.hands = [None, None]
        if "hands" not in d and isinstance(d.get("inventory"), list):
            # старое сохранение: безразмерный рюкзак → в руки еду/питьё, остальное — на стеллаж в гараже
            items = list(d["inventory"])
            food = [e for e in items if ITEMS.get(e.get("id"), {}).get("kind") in ("food", "drink")][:2]
            self.hands = (food + [None, None])[:2]
            self.legacy_items = [e for e in items if not any(e is f for f in food)]


class GameState:
    def __init__(self):
        self.world = World()
        self.winter = _winter.Winter(self.world)
        import traffic as _traffic
        self.traffic = _traffic.Traffic(self.world)          # движение: машины на физике, светофоры, пешеходы
        self.world.ai = self.traffic.drivers
        self.world.police = self.traffic.police
        self.t = 0.0
        import storage
        storage.GAME = self                   # подписи ключей: «Ключ ВАЗ 2102 (KB-VZ 102)»
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
        vaz = self.cars["vaz"]
        _elec.clean(vaz)
        _elec.add_fault(vaz, "horn", "consumer")          # у «двойки» барахлит сигнал — первая загадка по электрике
        vaz.trunk_items = [{"id": "fuse_set", "cond": 100.0}, {"id": "rope", "cond": 100.0}]   # предохранители и трос
        self.keyhook = []    # ключница у двери в квартире: запасные ключи
        self.trust = 1.0     # насколько в городе верят вашим объявлениям (не заплатили нашедшему — меньше)
        self.cur = "vaz"
        self.goal_done = False
        self.minutes = 8 * 60.0
        self.weather = "snow"
        self.weather_timer = 180.0
        self.last_day = 0
        self.last_month = START_DATE.month      # последний «наступивший» месяц (для события смены месяца)
        self.snow_level = cal.climate(START_DATE.month)["snow"]   # снег на земле 0..1 (тает/выпадает по сезону)
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
        self.garages = {}    # заброшенные гаражи: id -> {"open", "looted", "loot"}
        self.world.reset_doors()
        grng = random.Random(1979)
        for ag in self.world.abandoned:
            self.spawn_barn_find(ag, grng)
        self.loose = []      # детали, лежащие на земле: {"id", "cond", "x", "y", "place"}
        # стеллаж в своём гараже — настоящее хранилище: инструменты, канистры, детали (в руках — только два предмета)
        self.shelf = [{"id": "toolbox", "cond": 100.0}]
        # холодильник в квартире — настоящее хранилище (storage.py): взять с собой / положить
        self.fridge = [{"id": i, "cond": 100.0} for i in ("brot", "wurst", "apfel", "wasser", "wasser", "pizza_tk")]
        self.dealer = {"stock": {}, "restock": 7}
        self.spawn_junkyard(random.Random(401))
        self.spawn_underground(random.Random(402))
        self.spawn_parkings(random.Random(403))
        self.spawn_dealer_stock(random.Random(404))
        self.regrow_acc = 0.0
        if hasattr(self, "winter"):
            self.winter.slush = _winter.SlushField(self.world)
            self.winter.level = self.snow_level
        rng = random.Random(5)
        first = ["trabant", "kadett", "golf", "wartburg", "taunus", "w123"]
        rng.shuffle(first)
        levels = [0.80, 0.62, 0.46, 0.30, 0.14]      # от почти живой до трупа
        rng.shuffle(levels)
        for spot, model, lvl in zip(rng.sample(self.world.wreck_spots, 5), first, levels):
            self.spawn_wreck(spot, rng, model, lvl)     # на старте — пять разных моделей
        self.ensure_spread("civic", random.Random(406))
        self.spawn_mustang()
        _keys.TAKEN.clear()
        for c in self.cars.values():
            _keys.ensure(c)
        # ключ от «двойки» — в правой руке, запасной — на ключнице у двери
        self.p.hands[1] = _keys.make(self, "vaz")
        self.keyhook = [_keys.make(self, "vaz", spare=True)]
        for s_ in vaz.tire_list():
            _tires.set_nominal(vaz, s_)                   # свою «двойку» хозяин подкачивает

    # ---------------------------------------------------------------- найденные машины
    @property
    def wrecks(self):
        """Бесхозные машины на карте (их можно забрать себе бесплатно)."""
        return [c for k, c in self.cars.items() if k not in MAIN_CARS and not self.owned.get(k)]

    def wreck_keys(self):
        return [k for k in self.cars if k not in MAIN_CARS and not self.owned.get(k)]

    def spawn_wreck(self, spot=None, rng=random, model=None, pres=None):
        if spot is None:
            # примерно поровну: у загородных дорог и у жилых домов
            pool = self.world.road_spots if rng.random() < 0.55 else self.world.house_spots
            free = [sp for sp in pool if all(math.hypot(sp[0] - c.x, sp[1] - c.y) > 8 for c in self.cars.values())]
            if not free:
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

    def spawn_barn_find(self, ag, rng):
        """Забытая в гараже машина: под крышей — меньше ржавчины и выцветания, зато пыль, спущенные шины,
        севший аккумулятор. Плюс полки с добычей."""
        gid = ag["id"]
        weights = {"w123": 2.0, "taunus": 2.0, "kadett": 1.6, "golf": 1.6, "wartburg": 1.2, "trabant": 1.2,
                   "civic": 0.8}
        model = rng.choices(list(weights), list(weights.values()))[0]
        key = "g" + gid
        car = Car(model, ag["car_spot"][0], ag["car_spot"][1], ag["car_angle"],
                  rng=random.Random(rng.randint(0, 10 ** 9)), pres=rng.uniform(0.45, 0.9))
        for pn in car.rust:
            car.rust[pn] = round(car.rust[pn] * 0.45, 1)
        car.fade = round(car.fade * 0.4, 2)
        car.dirt = round(rng.uniform(0.75, 1.0), 2)      # толстый слой пыли
        car.battery_charge = 0.0
        car.fuel = round(rng.uniform(0, 1.5), 1)         # бензин выдохся
        for t in car.tire_list():
            if car.parts.get(t) and rng.random() < 0.6:
                car.parts[t]["cond"] = round(rng.uniform(0, 4), 1)   # колёса спустили за годы
        self.cars[key] = car
        self.owned[key] = False
        loot = []
        slots = list(car.slots.items())
        for _ in range(rng.randint(2, 4)):
            sl, (nm, pid, _) = rng.choice(slots)
            loot.append({"id": pid, "cond": round(rng.uniform(35, 90), 1)})
        extra = ["oil", "oil", "coolant", "brake_fl", "rope", "metal", "paint", "rust_conv", "jerrycan_old",
                 "old_radio", "charger", "toolbox"]
        for _ in range(rng.randint(1, 3)):
            loot.append({"id": rng.choice(extra), "cond": 100.0})
        if rng.random() < 0.18:
            loot.append({"id": "welder", "cond": round(rng.uniform(40, 80), 1)})   # редкая удача
        self.garages[gid] = {"open": False, "looted": False, "loot": loot}
        return key

    # ---------------------------------------------------------------- машины новых мест
    def _new_find(self, key, model, x, y, angle, rng, pres):
        car = Car(model, x, y, angle, rng=random.Random(rng.randint(0, 10 ** 9)), pres=pres)
        self.cars[key] = car
        self.owned[key] = False
        return car

    def ensure_spread(self, model, rng):
        """Редкая модель должна реально встречаться: если случайность её не выдала, по одной машине
        в подземке, на заброшенной парковке, на свалке и у дома (остальные — как повезёт)."""
        have = {k[0] for k, c in self.cars.items() if c.model == model and not self.owned.get(k)}
        for prefix in ("u", "p", "j"):
            if prefix in have:
                continue
            keys = sorted(k for k in self.cars if k[0] == prefix and k[1:].isdigit() and not self.owned.get(k))
            if not keys:
                continue
            k = rng.choice(keys)
            old = self.cars[k]
            car = Car(model, old.x, old.y, old.angle, rng=random.Random(rng.randint(0, 10 ** 9)), pres=old.preservation)
            if prefix == "u":           # под крышей: ржавчины меньше, пыль, шины сели
                for pn in car.rust:
                    car.rust[pn] = round(car.rust[pn] * 0.42, 1)
                car.fade = round(car.fade * 0.35, 2)
                car.snow = 0.0
            elif prefix == "p":
                self.strip_parts(car, rng, rng.uniform(0.15, 0.35))
            else:
                car.junk_cat = getattr(old, "junk_cat", "donor")
            car.dirt, car.battery_charge = old.dirt, 0.0
            self.cars[k] = car
        if "w" not in have:
            free = [sp for sp in self.world.house_spots
                    if all(math.hypot(sp[0] - c.x, sp[1] - c.y) > 8 for c in self.cars.values())]
            if free:
                self.spawn_wreck(rng.choice(free), rng, model)

    @staticmethod
    def strip_parts(car, rng, frac):
        """Частично разобранная машина: чего-то нет (двери, капот, колёса, мотор...)."""
        slots = [sl for sl in PART_KINDS if sl in car.parts]
        rng.shuffle(slots)
        for sl in slots[:int(len(slots) * frac)]:
            car.parts[sl] = None

    def _pick_model(self, rng, extra_vaz=0.0):
        names = list(MODELS) + (["vaz2102"] if extra_vaz else [])
        weights = [MODELS[m]["spawn"] for m in MODELS] + ([extra_vaz] if extra_vaz else [])
        return rng.choices(names, weights)[0]

    def spawn_junkyard(self, rng):
        """Свалка Ковальского: доноры всех сортов — от трупов до почти целых."""
        spots = list(JUNK_SPOTS)
        rng.shuffle(spots)
        cats = (["rotten"] * 4 + ["damaged"] * 3 + ["stripped"] * 4 + ["intact"] * 2 + ["donor"] * 3)
        for i, (x, y, a) in enumerate(spots[:len(cats)]):
            cat = cats[i]
            model = self._pick_model(rng, extra_vaz=2.5)
            pres = {"rotten": rng.uniform(0.03, 0.12), "damaged": rng.uniform(0.2, 0.4), "stripped": rng.uniform(0.25, 0.6),
                    "intact": rng.uniform(0.6, 0.8), "donor": rng.uniform(0.15, 0.3)}[cat]
            car = self._new_find(f"j{i + 1}", model, x, y, a, rng, pres)
            if cat in ("damaged", "rotten") and rng.random() < (0.9 if cat == "damaged" else 0.3):
                _damage.random_crash(car, rng, 1.0 if cat == "damaged" else 0.7)     # битая: настоящие вмятины
            car.snow = round(rng.uniform(0.5, 1.0), 2)
            if cat == "damaged":
                L = car.length
                car.dents += [(round(rng.uniform(0.3, L - 0.3), 2), round(rng.uniform(0.3, 0.8), 2),
                               round(rng.uniform(0.12, 0.3), 2), rng.choice("lr")) for _ in range(6)]
                for sl in ("lights", "glass"):
                    if car.parts.get(sl):
                        car.parts[sl]["cond"] = round(rng.uniform(0, 12), 1)
                for pn in ("fender", "arch_f", "doors"):
                    car.rust[pn] = min(100.0, car.rust[pn] + 15)
            elif cat == "stripped":
                self.strip_parts(car, rng, rng.uniform(0.3, 0.6))
            elif cat == "donor":
                # кузов — труха, а мотор и коробка живые
                for sl in ("engine", "gearbox", "carb", "starter", "alternator"):
                    if car.parts.get(sl):
                        car.parts[sl]["cond"] = round(rng.uniform(60, 90), 1)
                for pn in car.rust:
                    car.rust[pn] = min(100.0, car.rust[pn] + 20)
            car.junk_cat = cat

    def spawn_underground(self, rng):
        """Подземные гаражи: МНОГО машин, мало деталей. Под крышей ржавчины меньше, но пыль."""
        n_cars = 0
        per_level = {"tg1_1": 13, "tg1_2": 9, "tg2_1": 13, "tg2_2": 7}
        k = 0
        for L in self.world.places.levels:
            bays = list(L["bays"])
            rng.shuffle(bays)
            for (x, y, a, _) in bays[:per_level[L["id"]]]:
                k += 1
                model = self._pick_model(rng, extra_vaz=1.2)
                car = self._new_find(f"u{k}", model, x, y, a, rng, rng.uniform(0.45, 0.9))
                for pn in car.rust:
                    car.rust[pn] = round(car.rust[pn] * 0.42, 1)
                car.fade = round(car.fade * 0.35, 2)
                car.dirt = round(rng.uniform(0.55, 0.95), 2)      # пыль десятилетий
                car.snow = 0.0
                car.battery_charge = 0.0
                for t in car.tire_list():
                    if car.parts.get(t) and rng.random() < 0.5:
                        car.parts[t]["cond"] = round(rng.uniform(0, 5), 1)
                if rng.random() < 0.12:
                    self.strip_parts(car, rng, rng.uniform(0.15, 0.35))
                n_cars += 1
        # деталей заметно меньше, чем машин
        spots = [sp for sp in self.world.places.loot_spots if sp[2].startswith("tg")]
        rng.shuffle(spots)
        for (x, y, place) in spots[:max(3, n_cars // 3)]:
            self._drop_part(rng, x, y, place, cond=(40, 90))

    def spawn_parkings(self, rng):
        """Заброшенные парковки: ржавые и полуразобранные машины, детали на земле."""
        k = 0
        per = {"p1": 5, "p2": 5, "p3": 4}
        for P in self.world.places.parkings:
            bays = list(P["bays"])
            rng.shuffle(bays)
            for (x, y, a) in bays[:per[P["id"]]]:
                k += 1
                model = self._pick_model(rng, extra_vaz=1.5)
                car = self._new_find(f"p{k}", model, x, y, a, rng, rng.uniform(0.05, 0.5))
                car.snow = round(rng.uniform(0.6, 1.0), 2)
                if rng.random() < 0.55:
                    self.strip_parts(car, rng, rng.uniform(0.2, 0.55))
        for (x, y, place) in [sp for sp in self.world.places.loot_spots if sp[2].startswith("p")]:
            self._drop_part(rng, x, y, place, cond=(15, 70))

    def _drop_part(self, rng, x, y, place, cond=(20, 80)):
        model = self._pick_model(rng, extra_vaz=1.5)
        from items import SLOTS_BY_MODEL
        slots = SLOTS_BY_MODEL[model]
        sl = rng.choice(["door_l", "door_r", "hood", "trunk", "seats", "engine", "gearbox", "radiator", "exhaust",
                         "lights", "tire_fl", "battery", "alternator", "starter", "carb", "shocks", "brakes_f", "glass"])
        pid = slots[sl][1]
        self.loose.append({"id": pid, "cond": round(rng.uniform(*cond), 1), "x": round(x, 2), "y": round(y, 2),
                           "place": place, "slot": sl, "rot": round(rng.uniform(0, 6.28), 2)})

    def pickup(self, idx):
        """Подобрать с земли — только в свободную руку."""
        if self.free_hand() is None:
            self.notify(T("Обе руки заняты — сначала положите что-нибудь (X / Z) или уберите в багажник."), RED)
            return None
        it = self.loose.pop(idx)
        entry = {k: v for k, v in it.items() if k not in ("x", "y", "place", "slot", "rot")}
        self.give(entry)
        return it

    def nearest_loose(self, x, y, maxd=1.8):
        best, bd = None, maxd
        for i, it in enumerate(self.loose):
            d = math.hypot(x - it["x"], y - it["y"])
            if d < bd:
                best, bd = i, d
        return best

    # ---------------------------------------------------------------- рынок подержанных машин
    def car_value(self, car):
        base = BASE_VALUE.get(car.model, 900)
        parts = [car.c(sl) for sl in car.slots]
        missing = sum(1 for sl in car.slots if not car.has(sl))
        mech = sum(parts) / len(parts)
        core = 0.6 * car.c("engine") + 0.4 * car.c("gearbox")
        body = 1.0 - car.max_rust() / 100 * 0.8 - sum(car.rust.values()) / len(car.rust) / 100 * 0.2
        score = max(0.0, 0.35 * core + 0.3 * body + 0.35 * mech - 0.02 * missing)
        v = base * (0.12 + 0.88 * score)
        if car.tuv_until >= self.day:
            v += 250
        if car.deforms:                                  # битая машина стоит заметно дешевле
            zn = _damage.zones(car)
            v *= max(0.15, 1.0 - 1.2 * sum(zn.values()))
            if _damage.is_totaled(car):
                v = min(v, self.scrap_value(next((k for k, c in self.cars.items() if c is car), None)) * 1.2
                        if any(c is car for c in self.cars.values()) else v)
        from items import ITEMS as _IT
        for node, p_ in (car.tune or {}).items():
            if isinstance(p_, dict):                     # тюнинг добавляет цену (б/у)
                v += _IT.get(p_["id"], {}).get("price", 0) * p_["cond"] / 100 * 0.45
        return max(40.0, round(v / 10) * 10)

    def dealer_price(self, key):
        return self.dealer["stock"].get(key)

    def dealer_offer(self, key):
        """Сколько Weber даст за машину игрока."""
        return max(round(self.scrap_value(key)), round(self.car_value(self.cars[key]) * 0.6 / 10) * 10)

    def spawn_mustang(self):
        """Ford Mustang 1967 в обычном, живом состоянии — на площадке Weber, под будущий тюнинг GT500."""
        if any(c.model == "mustang" for c in self.cars.values()):
            return None
        rng = random.Random(1967)
        used = [(c.x, c.y) for k, c in self.cars.items() if k.startswith("s")]
        free = [sp for sp in DEALER_SPOTS if all(math.hypot(sp[0] - ux, sp[1] - uy) > 1.5 for ux, uy in used)]
        if not free:
            return None
        x, y, a = free[0]
        self.dealer["n"] = self.dealer.get("n", 0) + 1
        key = f"s{self.dealer['n']}"
        car = self._new_find(key, "mustang", x, y, a, rng, 0.85)
        for sl in car.slots:
            car.parts[sl] = {"id": car.slots[sl][1], "cond": round(rng.uniform(70, 88), 1)}
        _engine.init(car, base=car.parts["engine"]["cond"])
        for pn in car.rust:
            car.rust[pn] = round(rng.uniform(2, 12), 1)
        car.fade, car.dirt, car.snow = 0.08, 0.05, 0.0
        car.color = (228, 226, 218)                      # Wimbledon White
        car.fuel, car.oil, car.oil_quality = 20.0, car.oil_cap, 80.0
        car.coolant, car.brake_fluid, car.battery_charge = car.coolant_cap, 95.0, 90.0
        car.tuv_until = self.day + 700
        self.dealer["stock"][key] = 8900.0
        _keys.ensure(car)
        car.locked = True                            # машины на площадке заперты
        self.dealer["mustang"] = key
        return key

    def spawn_dealer_stock(self, rng, fill_to=8):
        used = [(c.x, c.y) for k, c in self.cars.items() if k.startswith("s") and k in self.dealer["stock"]]
        free = [sp for sp in DEALER_SPOTS if all(math.hypot(sp[0] - ux, sp[1] - uy) > 1.5 for ux, uy in used)]
        rng.shuffle(free)
        n = fill_to - len(self.dealer["stock"])
        for (x, y, a) in free[:max(0, n)]:
            self.dealer["n"] = self.dealer.get("n", 0) + 1
            key = f"s{self.dealer['n']}"
            model = self._pick_model(rng, extra_vaz=1.0)
            car = self._new_find(key, model, x, y, a, rng, rng.uniform(0.7, 0.95))
            for pn in car.rust:
                car.rust[pn] = round(car.rust[pn] * 0.35, 1)
                car.painted[pn] = rng.random() < 0.5
            car.fade = round(car.fade * 0.3, 2)
            car.dirt = 0.08
            car.snow = 0.0
            for sl in car.slots:                 # у продавца всё на месте и живое
                if car.parts.get(sl) is None:
                    car.parts[sl] = {"id": car.slots[sl][1], "cond": round(rng.uniform(55, 85), 1)}
                car.parts[sl]["cond"] = max(car.parts[sl]["cond"], round(rng.uniform(45, 70), 1))
            _engine.init(car, base=car.parts["engine"]["cond"])     # и внутренности мотора — под стать
            car.fuel = 8.0
            car.oil = car.oil_cap
            car.oil_quality = 70.0
            car.coolant = car.coolant_cap
            car.brake_fluid = 90.0
            car.battery_charge = 85.0
            if rng.random() < 0.5:
                car.tuv_until = self.day + 700      # «mit frischem TÜV»
            self.dealer["stock"][key] = round(self.car_value(car) * 1.35 / 50) * 50
            _keys.ensure(car)
            car.locked = True

    def buy_from_dealer(self, key):
        price = self.dealer["stock"].get(key)
        if price is None or not self.pay(price):
            return False
        del self.dealer["stock"][key]
        self.owned[key] = True
        self.hand_over_keys(key, T("Вебер отдаёт ключи — один уже в замке зажигания"))
        return True

    def sell_to_dealer(self, key):
        offer = self.dealer_offer(key)
        car = self.cars[key]
        self.earn(offer, T("— Вебер купил {name}", name=car.name))
        self.owned[key] = False
        if self.cur == key:
            self.cur = "vaz"
            self.p.in_car = False
        # машина становится товаром на площадке; ключи — Weber
        car.ign_key = None
        car.locked = True
        for i, e in enumerate(self.p.hands):
            if _keys.fits(e, car):
                self.p.hands[i] = None
        self.keyhook = [e for e in self.keyhook if not _keys.fits(e, car)]
        self.dealer["stock"][key] = round(self.car_value(car) * 1.35 / 50) * 50
        return offer

    def cars_in_sell_zone(self):
        from world import point_in as _pi
        return [k for k, c in self.owned_cars() if _pi(DEALER_SELL, c.x, c.y)]

    # ---------------------------------------------------------------- подземные гаражи: порталы
    def teleport_car(self, key, to):
        car = self.cars[key]
        x, y, a = to
        spd = car.speed
        car.x, car.y, car.angle = x, y, a
        car.speed = min(spd, 6.0)
        car.vlat = car.ang_vel = 0.0
        self.winter._last.pop(key, None)
        # машина на тросе едет следом
        if self.tow and self.tow["by"] == key and self.tow["key"] in self.cars:
            ob = self.cars[self.tow["key"]]
            back = car.length / 2 + self.tow.get("len", 6.0) - ob.length / 2 + ob.length / 2
            ob.x = x - math.cos(a) * back
            ob.y = y - math.sin(a) * back
            ob.angle = a
            ob.speed = 0.0
            ob.vlat = ob.ang_vel = 0.0

    def check_portals(self):
        """Машина игрока въехала в портал (въезд в подземный гараж / пандус между уровнями)."""
        if not self.p.in_car:
            return None
        car = self.car
        fx, fy = car.forward()
        pt = self.world.places.portal_for(car.x, car.y, fx * car.speed, fy * car.speed)
        if pt:
            self.teleport_car(self.cur, pt["to"])
            self.p.x, self.p.y = car.x, car.y
            self.notify(pt["label"], YELLOW, 3)
        return pt

    def underground_at(self, x, y):
        return self.world.level_at(x, y)

    # ---------------------------------------------------------------- погода
    def wet(self):
        return self.weather in ("snow", "sleet", "rain")

    def ambient_temp(self, x=None):
        h = self.hour
        d = self.date()
        dim = (d.replace(day=28) + datetime.timedelta(days=4)).replace(day=1) - d.replace(day=1)
        t = cal.temp(d.month, h, (d.day - 0.5) / dim.days)
        t += {"clear": -2.0 if self.darkness() > 0.4 else 0.5, "cloudy": 0.5, "snow": -1.0, "sleet": 1.5,
              "rain": -1.0}.get(self.weather, 0)
        if self.weather == "snow":
            t = min(t, 0.5)                 # снегопад бывает только около нуля и ниже
        elif self.weather == "sleet":
            t = max(-0.5, min(t, 2.5))
        if x is not None and x >= INTERIOR_X:
            t = 6.0                     # под землёй теплее
        return round(t, 1)

    def weather_text(self):
        return WEATHER_RU.get(self.weather, self.weather)

    def open_garage(self, gid):
        g = self.garages.get(gid)
        if g is None:
            return
        g["open"] = True
        self.world.open_door(gid)
        self.on_garage_opened(gid)

    def on_garage_opened(self, gid):
        """Крючок для графики (поднять ворота)."""
        pass

    def visible_finds(self):
        """Находки, которые игрок может видеть: у дорог и в уже открытых гаражах."""
        out = []
        for k in self.wreck_keys():
            if k in self.dealer["stock"] or self.cars[k].x >= INTERIOR_X:
                continue
            if k.startswith("ga"):
                gid = k[1:]
                if not self.garages.get(gid, {}).get("open"):
                    continue
            out.append(self.cars[k])
        return out

    def scrap_value(self, key):
        car = self.cars[key]
        base = MODELS[car.model]["scrap"] if car.model in MODELS else 60
        parts = [pp["cond"] for pp in car.parts.values() if pp]
        avg = sum(parts) / len(parts) / 100 if parts else 0
        return round(base * (0.85 + 0.35 * avg) * (0.95 + (car.seed % 11) / 100), 2)

    def claim_car(self, key):
        """Забрать находку себе — бесплатно. Ключ — в замке зажигания, запасной — на ключницу дома."""
        self.owned[key] = True
        self.hand_over_keys(key, T("Ключ нашёлся в бардачке — вставлен в замок зажигания"))

    def hand_over_keys(self, key, how):
        car = self.cars[key]
        _keys.ensure(car)
        car.locked = False
        if not _keys.fits(car.ign_key, car) and not car.hotwired:
            car.ign_key = _keys.make(self, key)
        if not any(_keys.fits(e, car) for e in self.keyhook):
            self.keyhook.append(_keys.make(self, key, spare=True))
        self.notify(T("{name}: {how}. Запасной ключ — на ключнице у двери квартиры.", name=car.name, how=how), GREEN, 8)

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
        return max(lo, min(lo + 8.0, d))

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
                self.snap_rope(T("Трос соскочил — машина на тросе упёрлась в препятствие. "
                               "Отъедьте назад и привяжите снова (T)."), lost=False)
                return
        car.tow_mass = obj.spec["mass"] * (0.85 if taut else 0.0)
        kmh = car.kmh()
        if kmh > ROPE_SNAP_KMH - 10 and not t.get("warned"):
            t["warned"] = True
            self.notify(T("Трос натянут как струна! На тросе — не быстрее 50 км/ч."), YELLOW, 5)
        if kmh < ROPE_SNAP_KMH - 15:
            t["warned"] = False
        t["over"] = t.get("over", 0.0) + dt if (kmh > ROPE_SNAP_KMH + 5 and taut) else 0.0
        if t["over"] > 1.0:
            self.snap_rope(T("Трос лопнул на {kmh:.0f} км/ч! Вы связали его узлом — привяжите снова (T) "
                           "и не гоните быстрее 50.", kmh=kmh), lost=False)

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
            return T("Цель выполнена: AE86 на ходу и на учёте!")
        if not self.owned["ae86"]:
            return T("Цель: забрать ржавую AE86 у Ковальского за гаражом (бесплатно)")
        if ae.tuv_until < self.day:
            return T("Цель: починить AE86 и пройти техосмотр")
        return T("Цель: поставить AE86 на учёт в ратуше")

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
            "wreck_id": self.wreck_id, "tow": self.tow, "garages": self.garages,
            "loose": self.loose, "dealer": self.dealer,
            "weather": self.weather, "weather_timer": self.weather_timer, "fridge": self.fridge, "shelf": self.shelf,
            "keyhook": self.keyhook, "trust": self.trust,
            "last_month": self.last_month, "snow_level": round(self.snow_level, 3),
            "last_day": self.last_day, "last_mama": self.last_mama, "stats": self.stats,
            "schrott_stock": self.schrott_stock, "schrott_day": self.schrott_day,
        }
        with open(SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(i18n.to_json(d), f, ensure_ascii=False, indent=1)     # тексты — как msgid, не на языке сейчас
        self.notify(T("Игра сохранена."), GREEN)

    def load(self):
        if not os.path.exists(SAVE_FILE):
            self.notify(T("Нет сохранения."), RED)
            return False
        with open(SAVE_FILE, encoding="utf-8") as f:
            d = i18n.from_json(json.load(f))
        self.new_state()
        self.p.from_dict(d["player"])
        if "cars" in d:
            # находки из нового сохранения заменят стартовые (гаражные — только если они есть в сохранении)
            for k in self.wreck_keys():
                if k.startswith("ga") and not ("garages" in d and k in d["cars"]):
                    continue
                self.cars.pop(k, None)
                self.owned.pop(k, None)
            for k, cd in d["cars"].items():
                if k not in self.cars:
                    self.cars[k] = Car(cd.get("model", "vaz2102"))
                self.cars[k].from_dict(cd)
        elif "car" in d:                       # сохранение старой версии (одна машина)
            self.cars["vaz"].from_dict(d["car"])
        for k in ("minutes", "weather", "weather_timer", "last_day", "last_mama", "stats",
                  "schrott_stock", "schrott_day", "owned", "cur", "goal_done", "wreck_id", "tow", "garages",
                  "loose", "dealer", "fridge", "shelf", "keyhook", "trust", "last_month", "snow_level"):
            if k in d:
                setattr(self, k, d[k])
        if self.p.legacy_items:
            self.shelf += self.p.legacy_items
            self.notify(T("Теперь с собой — только две руки. Остальные вещи ({0} шт.) лежат на "
                        "стеллаже в вашем гараже.", len(self.p.legacy_items)), YELLOW, 10)
            self.p.legacy_items = []
        if "last_month" not in d:                # старое сохранение: месяц — по дате, без поздравления
            self.last_month = self.month
        if "snow_level" not in d:
            self.snow_level = cal.climate(self.month)["snow"]
        if not isinstance(self.fridge, list):
            self.fridge = []
        # сохранения прошлой версии: брошенные машины были простыми записями — превращаем в настоящие машины
        old_names = {"trabant", "wartburg", "kadett", "golf", "taunus", "w123"}
        for w in d.get("wrecks", []) if isinstance(d.get("wrecks"), list) else []:
            if w.get("model") in old_names:
                key = self.spawn_wreck((w["x"], w["y"], w.get("angle", 0.0)), random.Random(w.get("seed", 1)))
                if key:
                    self.cars[key].model = w["model"]
                    self.cars[key].__init__(w["model"], w["x"], w["y"], w.get("angle", 0.0),
                                            rng=random.Random(w.get("seed", 1)))
        self.weather = cal.valid_weather(self.month, self.weather)
        self.winter.level = self.snow_level
        # новые места в старом сохранении: заселить
        if "loose" not in d:
            self.loose = []
        prefixes = {k[0] for k in self.cars if k[0] in "jups" and k[1:].isdigit()}
        if "j" not in prefixes:
            self.spawn_junkyard(random.Random(401))
        if "u" not in prefixes:
            self.spawn_underground(random.Random(402))
        if "p" not in prefixes:
            self.spawn_parkings(random.Random(403))
        if "dealer" not in d:
            self.dealer = {"stock": {}, "restock": 7}
            self.spawn_dealer_stock(random.Random(404))
        # новая модель в старом сохранении: Honda Civic должна где-то найтись
        if not any(c.model == "civic" for c in self.cars.values()):
            self.ensure_spread("civic", random.Random(406))
        self.spawn_mustang()
        # бесхозные машины в заброшенных гаражах — на своё место (раскладка карты могла измениться)
        for ag in self.world.abandoned:
            key = "g" + ag["id"]
            if key in self.cars and not self.owned.get(key):
                c = self.cars[key]
                c.x, c.y = ag["car_spot"]
                c.angle = ag["car_angle"]
        # гаражи из старого сохранения (которых тогда не было) — закрыты, с машинами
        for ag in self.world.abandoned:
            if ag["id"] not in self.garages:
                self.spawn_barn_find(ag, random.Random(1000 + int(ag["id"][1:])))
        self.world.reset_doors()
        for gid, gs in self.garages.items():
            if gs.get("open"):
                self.world.open_door(gid)
        for k in list(self.owned):
            if k not in self.cars:
                self.owned.pop(k)
        for k in self.cars:
            self.owned.setdefault(k, False)
        for k, c in self.owned_cars():
            if not isinstance(c.elec, dict):
                _elec.clean(c)            # старое сохранение: своя машина — с исправной электрикой
        self._ensure_keys("keyhook" not in d)
        for k, c in self.owned_cars():
            if not isinstance(c.tire_p, dict):            # старое сохранение: давление — чуть ниже нормы
                _tires.ensure(c)
                for s_ in c.tire_list():
                    c.tire_p[s_] = round(_tires.nominal(c, s_) * 0.93, 2)
        if self.tow and (self.tow.get("kind") != "car" or self.tow.get("key") not in self.cars
                         or self.tow.get("by") not in self.cars):
            self.tow = None
        if self.cur not in self.cars:
            self.cur = "vaz"
        self.stats.setdefault("scrapped", 0)
        # AE86 теперь продаётся на свалке Ковальского за гаражом
        if not self.owned.get("ae86"):
            self.cars["ae86"] = Car("ae86", AE86_SPOT[0], AE86_SPOT[1], angle=math.pi)
        self.notify(T("Игра загружена."), GREEN)
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

    # ---- месяцы и сезоны (calendar_de.py): к ним привязаны температура, свет, погода, снег
    @property
    def month(self):
        return self.date().month

    @property
    def year(self):
        return self.date().year

    def month_name(self):
        return cal.month_name(self.month)

    def season(self):
        return cal.season(self.month)

    def climate(self):
        return cal.climate(self.month)

    def date_text(self):
        d = self.date()
        return T("{day} {month} {year}", day=d.day, month=cal.MONTHS_GEN[d.month - 1], year=d.year)

    def on_new_month(self, month, year):
        """Наступил новый месяц: сообщение и сезонные перемены (погода подстраивается под климат)."""
        self.notify(T("Наступил {month_name} {year} года ({0}).", cal.SEASON_RU[cal.season(month)], month_name=cal.month_name(month), year=year), YELLOW, 8)
        self.weather = cal.valid_weather(month, self.weather)
        c = cal.climate(month)
        if c["snow"] > self.snow_level + 0.3:
            self.notify(T("Похолодало: земля снова под снегом."), WHITE, 6)
        elif c["snow"] < self.snow_level - 0.3:
            self.notify(T("Снег сходит — дороги становятся чище и суше."), WHITE, 6)

    def _step_season(self, minutes):
        """Снег на земле плавно идёт к норме месяца; снегопад добавляет, дождь и тепло съедают."""
        target = cal.climate(self.month)["snow"]
        t = self.ambient_temp()
        lv = self.snow_level
        if self.weather == "snow":
            lv += 0.0012 * minutes
        elif self.weather == "rain" or t > 3:
            lv -= 0.0006 * minutes * (1 + max(0.0, t - 3) / 4)
        lv += (target - lv) * min(1.0, minutes / (60 * 24 * 6))      # за ~неделю к сезонной норме
        self.snow_level = max(0.0, min(1.0, lv))
        self.winter.level = self.snow_level

    def time_str(self):
        d = self.date()
        return T("{weekday} {day} {month} {year}  {hour:02d}:{minute:02d}", weekday=WEEKDAYS_RU[d.weekday()], day=d.day,
                 month=cal.MONTHS_GEN[d.month - 1], year=d.year, hour=d.hour, minute=d.minute)

    def darkness(self):
        # рассвет и закат — по месяцу (декабрь: ~8:25 и ~16:05, июнь: ~5:00 и ~21:50)
        return cal.darkness(self.month, self.hour)

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
        s = T("Пн–Пт {0:02d}–{1:02d}", wk[0], wk[1]) if wk else ""
        s += T(", Сб {0:02d}–{1:02d}", sat[0], sat[1]) if sat else T(", Сб закрыто")
        s += T(", Вс закрыто") if not oh.get(6) else ""
        return s

    def advance(self, minutes, sleeping=False, working=False):
        """Проходит игровое время: голод, жажда, усталость, ржавчина, счета."""
        if minutes <= 0:
            return
        self.minutes += minutes
        p = self.p
        _under.tick(self, minutes, working)              # под машиной на одном домкрате — может соскочить
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
                self.notify(T("Вам плохо: ") + (T("голод") if p.hunger <= 0 else T("жажда")) + "!", RED)
        else:
            p.health = min(100.0, p.health + 0.05 * minutes)
        for a in ("hunger", "thirst", "energy", "hygiene"):
            setattr(p, a, max(0.0, min(100.0, getattr(p, a))))

        # машины: ржавчина, шины, снег на крыше — раз в игровую минуту одним шагом (машин ~100, каждый кадр — дорого)
        self._car_acc = getattr(self, "_car_acc", 0.0) + minutes
        if self._car_acc >= 1.0:
            m_ = self._car_acc
            self._car_acc = 0.0
            for c in self.cars.values():
                c.rust_tick(m_, wet=self.wet(),
                            in_garage=point_in(GARAGE, c.x, c.y) or self.world.abandoned_at(c.x, c.y) is not None)
            # снег на стоящих под открытым небом машинах; под крышей тает
            for k, c in self.cars.items():
                roofed = (point_in(GARAGE, c.x, c.y) or c.x >= INTERIOR_X or self.world.abandoned_at(c.x, c.y) is not None)
                if roofed:
                    c.snow = max(0.0, c.snow - 0.01 * m_)
                elif self.weather == "snow":
                    c.snow = min(1.0, c.snow + 0.004 * m_)
                elif self.weather == "sleet":
                    c.snow = max(0.0, c.snow - 0.002 * m_)
        # снегопад заносит колеи в слякоти (раз в полчаса игрового времени)
        if self.weather == "snow":
            self.regrow_acc = getattr(self, "regrow_acc", 0.0) + minutes
            if self.regrow_acc > 30:
                self.winter.slush.regrow(0.12)
                self.regrow_acc = 0.0
        # ночью угоняют, днём ищут (theft.py)
        m_prev = self.minutes - minutes
        _theft.tick(self, m_prev, self.minutes)
        import service as _service
        _service.tick(self)                               # готовые машины из автосервиса
        _theft.hourly(self, m_prev, self.minutes)
        # погода — по климату текущего месяца
        self.weather_timer -= minutes
        if self.weather_timer <= 0:
            self.weather = cal.pick_weather(self.month, random)
            self.weather_timer = random.uniform(120, 420)
        self._step_season(minutes)

        # новый день
        while self.day > self.last_day:
            self.last_day += 1
            self.on_new_day(self.last_day)
        # новый месяц (строго по порядку, даже если проспали несколько)
        while self.last_month != self.month:
            self.last_month = self.last_month % 12 + 1
            yr = self.year if self.last_month <= self.month else self.year - 1
            self.on_new_month(self.last_month, yr)

        if p.health <= 0:
            self.hospital(T("Вы потеряли сознание от истощения."))
        elif p.energy <= 0 and not sleeping:
            self.pending_faint = True

    def on_new_day(self, day):
        if day % 7 == 6:
            before = len(self.dealer["stock"])
            self.spawn_dealer_stock(random.Random(day * 17 + 3))
            if len(self.dealer["stock"]) > before:
                self.notify(T("Автоплощадка Вебера: пригнали новые машины."), YELLOW, 6)
        if len([k for k in self.wreck_keys() if k.startswith("w")]) < MAX_FINDS and random.random() < 0.8:
            key = self.spawn_wreck()
            if key:
                self.notify(T("Слух: у дороги бросили {name}. Можно забрать себе (карта — M).", name=self.cars[key].name), YELLOW, 8)
        if day % 7 == 0:
            # квартира своя: квартплаты и выселения нет; остаётся только страховка машин на учёте
            for k, c in self.owned_cars():
                if c.registered:
                    self.charge(INSURANCE, T("Страховка и налог: {name}", name=c.name), YELLOW, 8)
        for k, c in self.owned_cars():
            mg = c.mangel
            if mg and c.registered and day > mg.get("until", 1e9):
                c.registered = False
                self.notify(T("{name}: срок предписания истёк, устранение дефектов не подтверждено на техосмотре — "
                            "регистрация аннулирована. Устраните дефекты, пройдите техосмотр и снова в ратушу.", name=c.name), RED, 10)
            elif mg and c.registered and day == mg.get("until"):
                self.notify(T("{name}: сегодня последний день по предписанию — предъявите машину на техосмотр.", name=c.name), YELLOW, 8)
        for k, c in self.owned_cars():
            if c.registered and 0 <= c.tuv_until < day:
                self.notify(T("{name}: срок техосмотра истёк! Нужно пройти его заново.", name=c.name), RED, 8)

    def hospital(self, reason):
        self.notify(reason, RED, 8)
        self.notify(T("Вы очнулись дома. Лечение бесплатное — деньги не списаны."), GREEN, 8)
        self.p.health = 60
        self.p.hunger = max(self.p.hunger, 50)
        self.p.thirst = max(self.p.thirst, 50)
        self.p.energy = 70
        self.p.drunk = 0
        self.p.in_car = False
        self.p.under_car = None
        ax, ay = BUILDINGS["apartment"][7]
        self.p.x, self.p.y = ax, ay - 1.5
        self.minutes += 10 * 60
        self.delivery = None
        for c in self.cars.values():
            c.engine_off()
            c.speed = 0
            c.vlat = c.ang_vel = 0.0

    def all_key_entries(self):
        """Все ключи в мире: руки, ключница, стеллаж, холодильник, багажники, замки зажигания, земля."""
        out = [e for e in self.p.hands if e] + list(self.keyhook) + list(self.shelf) + list(self.fridge) + list(self.loose)
        for c in self.cars.values():
            out += list(c.trunk_items)
            if c.ign_key:
                out.append(c.ign_key)
        return [e for e in out if e.get("id") == "key"]

    def _ensure_keys(self, old_save):
        """У каждой машины есть код; у своих машин — хотя бы один подходящий ключ где-то в мире."""
        if getattr(self, "keyhook", None) is None:
            self.keyhook = []
        _keys.TAKEN.clear()
        seen = set()
        for c in self.cars.values():
            if getattr(c, "key_code", None) in seen and not self.owned.get(next(k for k, v in self.cars.items() if v is c)):
                c.key_code = None                      # совпадение у чужой машины — перевыпустить
            _keys.ensure(c)
            seen.add(c.key_code)
        have = self.all_key_entries()
        for k, c in self.owned_cars():
            if not any(_keys.fits(e, c) for e in have):
                c.ign_key = _keys.make(self, k)                      # старое сохранение: ключ в замке
                self.keyhook.append(_keys.make(self, k, spare=True))
        if old_save and self.owned_cars():
            self.notify(T("Теперь у каждой машины свой ключ: он в замке зажигания, запасные — на ключнице у двери "
                        "квартиры. Запирайте машину на ночь (K с ключом в руке)."), YELLOW, 12)

    # ---------------------------------------------------------------- инвентарь: две руки + то, что лежит рядом
    def free_hand(self):
        """Индекс свободной руки (сначала правая) или None."""
        h = self.p.hands
        return 1 if h[1] is None else (0 if h[0] is None else None)

    def hand_of(self, entry):
        for i, e in enumerate(self.p.hands):
            if e is entry:
                return i
        return None

    def release(self, entry):
        """Убрать запись из рук (её переложили / съели / поставили на машину)."""
        i = self.hand_of(entry)
        if i is not None:
            self.p.hands[i] = None
            return True
        return False

    def swap_hands(self):
        h = self.p.hands
        h[0], h[1] = h[1], h[0]

    def nearby_stores(self):
        """Хранилища, до которых можно дотянуться, не таская вещи с собой: стеллаж (когда вы в своём гараже)
        и открытые багажники машин в паре шагов. [(список, вид, подпись)]."""
        out = []
        p = self.p
        if getattr(self, "location", "street") == "apartment":
            return out
        gx, gy, gw, gh = GARAGE
        if gx - 1 <= p.x <= gx + gw + 1 and gy - 1 <= p.y <= gy + gh + 1:
            out.append((self.shelf, "shelf", T("стеллаж в гараже")))
        if not p.in_car:
            for c in self.cars.values():
                if abs(c.x - p.x) + abs(c.y - p.y) > 9:
                    continue
                if (c.trunk_open or not c.has("trunk")) and \
                        min(math.hypot(p.x - cx, p.y - cy) for cx, cy, _ in c.body_circles()) < 3.0:
                    out.append((c.trunk_items, "trunk", T("багажник ") + c.name))
        return out

    def available(self):
        """Всё, чем можно пользоваться прямо сейчас: руки + открытый багажник рядом + стеллаж в гараже."""
        out = list(self.p.inventory)
        for cont, _, _ in self.nearby_stores():
            out += cont
        return out

    def count(self, item_id):
        return sum(1 for e in self.available() if e["id"] == item_id)

    def has(self, item_id):
        return self.count(item_id) > 0

    def where_is(self, item_id):
        """Подсказка, где лежит вещь, которой нет под рукой."""
        if any(e["id"] == item_id for e in self.shelf):
            return T("на стеллаже в гараже")
        for k, c in self.owned_cars():
            if any(e["id"] == item_id for e in c.trunk_items):
                return T("в багажнике {name} (откройте его или возьмите в руку)", name=c.name)
        if any(e["id"] == item_id for e in getattr(self, "fridge", [])):
            return T("в холодильнике")
        return None

    def need(self, item_id, what=None):
        """Проверка инструмента с понятной подсказкой, где он."""
        if self.has(item_id):
            return True
        nm = what or ITEMS.get(item_id, {}).get("name", item_id)
        w = self.where_is(item_id)
        self.notify(T("Нужен(а): {nm}", nm=nm) + (T(" — лежит {w}.", w=w) if w else T(" — купите в магазине.")), RED, 6)
        return False

    def give(self, entry, shop=False):
        """Отдать игроку вещь: в свободную руку; руки заняты — в открытый багажник рядом / на стеллаж;
        при покупке — продавец отнесёт в багажник вашей машины у входа; иначе — на землю под ноги.
        Возвращает, куда попало (None — некуда)."""
        fh = self.free_hand()
        if fh is not None:
            self.p.hands[fh] = entry
            return "hand"
        import storage
        for cont, kind, lab in self.nearby_stores():
            if len(cont) < storage.CAPACITY.get(kind, 99):
                cont.append(entry)
                self.notify(T("Руки заняты — положили: {lab}.", lab=lab), YELLOW, 5)
                return kind
        if getattr(self, "location", "street") == "apartment":
            if ITEMS.get(entry["id"], {}).get("kind") in ("food", "drink"):
                self.fridge.append(entry)
                self.notify(T("Руки заняты — убрали в холодильник."), YELLOW, 5)
                return "fridge"
            return None
        p = self.p
        if shop:
            best = None
            for k, c in self.owned_cars():
                d = math.hypot(c.x - p.x, c.y - p.y)
                if d < 45 and len(c.trunk_items) < storage.CAPACITY["trunk"] and (best is None or d < best[0]):
                    best = (d, c)
            if best:
                best[1].trunk_items.append(entry)
                self.notify(T("Руки заняты — продавец отнёс покупку в багажник {name}.", name=best[1].name), YELLOW, 6)
                return "trunk"
            return None
        if p.in_car:
            c = self.car
            if len(c.trunk_items) < storage.CAPACITY["trunk"]:
                c.trunk_items.append(entry)
                self.notify(T("Руки заняты — положили в багажник {name}.", name=c.name), YELLOW, 5)
                return "trunk"
        e = dict(entry)
        e.update(x=round(p.x + random.uniform(-0.4, 0.4), 2), y=round(p.y + random.uniform(-0.4, 0.4), 2),
                 place="drop", rot=round(random.uniform(0, 6.28), 2))
        self.loose.append(e)
        self.notify(T("Руки заняты — {name} лежит на земле (E — подобрать).", name=ITEMS.get(entry['id'], {}).get('name', entry['id'])),
                    YELLOW, 6)
        return "ground"

    def can_receive(self, shop=False):
        if self.free_hand() is not None or any(True for _ in self.nearby_stores()):
            return True
        if shop:
            import storage
            return any(math.hypot(c.x - self.p.x, c.y - self.p.y) < 45 and len(c.trunk_items) < storage.CAPACITY["trunk"]
                       for k, c in self.owned_cars())
        return getattr(self, "location", "street") != "apartment"

    def add_item(self, item_id, cond=100.0):
        return self.give({"id": item_id, "cond": round(float(cond), 1)})

    def take_item(self, item_id, entry=None):
        """Забрать вещь (израсходовать / поставить на машину): сначала из рук, потом из того, что лежит рядом."""
        if entry is not None:
            if self.release(entry):
                return entry
            for cont, _, _ in self.nearby_stores():
                if any(x is entry for x in cont):
                    cont.remove(entry)
                    return entry
        hand = [e for e in self.p.inventory if e["id"] == item_id]
        if hand:
            best = max(hand, key=lambda e: e["cond"])
            self.release(best)
            return best
        for cont, _, _ in self.nearby_stores():
            cands = [e for e in cont if e["id"] == item_id]
            if cands:
                best = max(cands, key=lambda e: e["cond"])
                cont.remove(best)
                return best
        return None

    def drop_hand(self, i):
        """Положить то, что в руке: в открытый багажник / на стеллаж рядом, иначе на землю."""
        e = self.p.hands[i]
        if e is None:
            return None
        self.p.hands[i] = None
        import storage
        for cont, kind, lab in self.nearby_stores():
            if len(cont) < storage.CAPACITY.get(kind, 99):
                cont.append(e)
                return lab
        if getattr(self, "location", "street") == "apartment":
            if ITEMS.get(e["id"], {}).get("kind") in ("food", "drink"):
                self.fridge.append(e)
                return T("холодильник")
            self.p.hands[i] = e
            return None
        p = self.p
        yr = math.radians(getattr(self, "yaw", 0.0))
        e2 = dict(e)
        e2.update(x=round(p.x + math.sin(yr) * 0.7, 2), y=round(p.y - math.cos(yr) * 0.7, 2), place="drop",
                  rot=round(random.uniform(0, 6.28), 2))
        self.loose.append(e2)
        return T("земля")

    PORTION = {"food": 34.0, "drink": 25.0}      # сколько % предмета за один укус / глоток

    def edible(self, e):
        return bool(e) and ITEMS.get(e["id"], {}).get("kind") in ("food", "drink")

    def eat_hand(self, i):
        """Один укус / глоток из руки i: питательность пропорционально, предмет убывает, кончился — исчез."""
        e = self.p.hands[i]
        if not self.edible(e):
            return False
        it = ITEMS[e["id"]]
        part = min(self.PORTION[it["kind"]], e["cond"])
        k = part / 100.0
        p = self.p
        p.hunger = min(100, p.hunger + it.get("hunger", 0) * k)
        p.thirst = min(100, p.thirst + it.get("thirst", 0) * k)
        p.energy = min(100, p.energy + it.get("energy", 0) * k)
        p.drunk = min(100, p.drunk + it.get("drunk", 0) * k)
        e["cond"] = round(e["cond"] - part, 1)
        self.advance(1)
        if e["cond"] <= 0.5:
            self.p.hands[i] = None
            self.notify((T("Выпили до дна: ") if it["kind"] == "drink" else T("Доели: ")) + it["name"], GREEN)
        return True

    def start_eat(self, i):
        """Крючок: в 3D — анимация, в конце вызывается eat_hand. Без графики — сразу."""
        return self.eat_hand(i)

    # ---- деньги: всё в ₽, округление до копейки
    def _add_money(self, delta):
        self.p.money = round(self.p.money + round(delta, 2), 2)

    def pay(self, amount, what=""):
        """Добровольная покупка: только если хватает денег."""
        amount = round(amount, 2)
        if self.p.money + 1e-9 < amount:
            self.notify(T("Не хватает денег: нужно {amount:.2f} ₽, есть {0:.2f} ₽.", max(0.0, self.p.money), amount=amount), RED)
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
            self.notify(f"{what}: -{amount:.2f} ₽", color, t)
        return amount

    def earn(self, amount, what=""):
        amount = round(amount, 2)
        if amount <= 0:
            return
        self._add_money(amount)
        self.play_sound("cash", 0.6)
        self.notify(f"+{amount:.2f} ₽ {what}", GREEN)

    def consume(self, item_id):
        it = ITEMS[item_id]
        p = self.p
        p.hunger = min(100, p.hunger + it.get("hunger", 0))
        p.thirst = min(100, p.thirst + it.get("thirst", 0))
        p.energy = min(100, p.energy + it.get("energy", 0))
        p.drunk = min(100, p.drunk + it.get("drunk", 0))
        self.advance(3)
        self.notify(T("Вы употребили: {item_name}", item_name=item_name(item_id)))

    # ---------------------------------------------------------------- машина
    def step_car(self, dt):
        towed_key = self.tow["key"] if self.tow else None
        towing_key = self.tow["by"] if self.tow else None
        for key, car in list(self.cars.items()):
            driven = key == self.cur and self.p.in_car
            idle = (not driven and not car.running and not car.cranking and abs(car.speed) < 0.01
                    and abs(car.vlat) < 0.01 and abs(car.ang_vel) < 0.01 and key not in (towed_key, towing_key))
            if idle:
                continue     # стоящая заглушенная машина: физику не считаем
            inp = self.car_input if driven else {}
            grip, slush = self.winter.surface(car)
            surf = _tires.surface_at(self.world, car.x, car.y) if driven or abs(car.speed) > 0.5 else "asphalt"
            lifted = _under.is_lifted(car)
            if lifted:
                hold = (car.x, car.y, car.angle)
            car.update(dt, inp, rain=self.wet(), ambient=self.ambient_temp(car.x), grip_mult=grip, slush=slush,
                       surface=surf)
            if lifted:                                       # на домкрате/подставках колёса висят — машина стоит
                car.x, car.y, car.angle = hold
                car.speed = car.vlat = car.ang_vel = 0.0
            self.winter.drive(key, car)
            for part in getattr(car, "lost_wheels", None) or []:       # отвалившееся колесо лежит на дороге
                if part:
                    fx_, fy_ = car.forward()
                    self.loose.append({"id": part["id"], "cond": part["cond"], "x": round(car.x - fx_ * 3, 2),
                                       "y": round(car.y - fy_ * 3, 2), "place": "road", "slot": "tire_fl", "rot": 0.3})
            car.lost_wheels = []
            if abs(car.speed) > 8 and car.snow > 0:
                car.snow = max(0.0, car.snow - dt * 0.15)
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
        self.check_portals()
        # машины трафика рядом: стены/столбы — как у всех
        tr = getattr(self, "traffic", None)
        tcars = []
        if tr is not None:
            for i, d in enumerate(tr.drivers):
                if d.phys:
                    self._collide(d.car, False)
                    tcars.append(("t%d" % i, d.car))
        # машины друг с другом (кроме пары «тягач — на тросе»), в том числе с трафиком — по настоящей физике
        items = list(self.cars.items()) + tcars
        moving = [(k, c) for k, c in items if abs(c.speed) >= 0.01 or abs(c.vlat) >= 0.01]
        seen = set()
        for ka, a in moving:
            for kb, b in items:
                if abs(a.x - b.x) > 7 or abs(a.y - b.y) > 7:      # сначала дешёвая проверка — далеко друг от друга
                    continue
                if kb == ka or (kb, ka) in seen:
                    continue
                seen.add((ka, kb))
                if {ka, kb} == {towed_key, towing_key}:
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
                            fa_, fb_ = a.forward(), b.forward()
                            avx, avy = fa_[0] * a.speed - fa_[1] * a.vlat, fa_[1] * a.speed + fa_[0] * a.vlat
                            bvx, bvy = fb_[0] * b.speed - fb_[1] * b.vlat, fb_[1] * b.speed + fb_[0] * b.vlat
                            ux, uy = dx / d, dy / d
                            rel = abs((avx - bvx) * ux + (avy - bvy) * uy)
                            if rel > 2:
                                mx, my = (ax_ + bx_) / 2, (ay_ + by_) / 2       # место удара — между машинами
                                _damage.record_impact(a, mx, my, ux, uy, rel, 0.0, "car", now=self.minutes * 60)
                                _damage.record_impact(b, mx, my, -ux, -uy, rel, 0.0, "car", now=self.minutes * 60)
                                a.impact(rel)
                                b.impact(rel)
                                if self.p.in_car and self.cur in (ka, kb):
                                    self.notify(T("Бум! Вы врезались в стоящую машину."), RED)
                            a.speed *= 0.3
                            b.speed *= 0.3
                            a.vlat *= 0.3
                            b.vlat *= 0.3
                            hit = True
                            break
                    if hit:
                        break
        self.engine_audio(self.car_input if self.p.in_car else {})

    def on_ped_hit(self, p, car, v):
        """Машина сбила пешехода. Если это машина игрока — последствия."""
        if not any(c is car for c in self.cars.values()):
            return
        kmh = v * 3.6
        if kmh < 15:
            self.notify(T("Вы задели пешехода — он падает, ругаясь. Хорошо, что на малой скорости."), RED, 6)
            self.charge(120, T("Штраф: неосторожное вождение"))
        else:
            self.notify(T("Вы сбили пешехода на {kmh:.0f} км/ч! Скорая, полиция, протокол.", kmh=kmh), RED, 10)
            self.charge(min(4000, 300 + kmh * 25), T("Штраф и компенсация пострадавшему"))
            self.police_cd = 0.0
        self.play_sound("crash", 0.4)

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
                    vx = fx * car.speed - fy * car.vlat
                    vy = fy * car.speed + fx * car.vlat
                    vn = -(vx * nx + vy * ny)
                    vt = abs(-vx * ny + vy * nx)
                    px, py = cx - nx * (r - depth), cy - ny * (r - depth)      # точка контакта на кузове
                    if vn > 1.5:
                        kind, width = getattr(self.world, "last_hit", ("wall", 3.0))
                        crush = _damage.record_impact(car, px, py, nx, ny, vn, vt, kind, width, now=self.minutes * 60)
                        if car.impact(vn) and driven:
                            self.hospital(T("Тяжёлая авария!"))
                            return True
                        if vn > 4 and driven:
                            what = T(" Кузов смят на {0:.0f} см.", crush * 100) if crush > 0.03 else ""
                            self.notify(T("Удар! ({0:.0f} км/ч){what}", vn * 3.6, what=what), RED)
                            if _damage.is_totaled(car) and not getattr(car, "_total_said", False):
                                car._total_said = True
                                self.notify(T("{name}: геометрия кузова уведена — похоже на «тотал». "
                                            "Ремонт дороже машины, проще сдать на лом.", name=car.name), RED, 10)
                    _damage.bounce(car, nx, ny, px, py, 0.15 if vn > 3 else 0.05)
                    break
        return False
