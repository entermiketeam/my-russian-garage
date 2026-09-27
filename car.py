"""Машины игры: ВАЗ 2102 «Жигули» (1979) и Toyota Sprinter Trueno AE86 (1985).

Физика упрощённая, но на реальных цифрах (SPECS):
  ВАЗ 2102: двигатель 2101 1.2 л, 64 л.с., 87 Н·м @ 3400, КПП 3.753/2.303/1.493/1.000,
            главная пара 4.44, шины 165/80 R13, бак 39 л, масла 3.75 л.
  AE86:     4A-GE 1.6 16V, 124 л.с. @ 6600, ~142 Н·м @ 5200, отсечка 7600,
            КПП T50 3.587/2.022/1.384/1.000/0.861, главная пара 4.30, шины 185/70 R13, бак 50 л.
"""
import math
import random
import pygame

from items import SLOTS, SLOTS_BY_MODEL, PANELS
from config import PPM
from models import MODELS, model_info

SPECS = {
    "vaz2102": dict(
        name="ВАЗ 2102", length=4.03, width=1.61, wheelbase=2.424, mass=1100.0, wheel_r=0.287,
        final=4.44, gears={-1: -3.867, 0: 0.0, 1: 3.753, 2: 2.303, 3: 1.493, 4: 1.0},
        idle=850, tank=39.0, oil=3.75, coolant=9.85, tq_peak=88.0, tq_rpm=3400.0, tq_width=3200.0,
        cut=6000, overrev=6300, limiter=False, cda=0.45 * 1.85, carb=True,
        axles=(0.83, 3.25), track=0.685, eye=(-0.36, 1.17, 1.72), plate="KB-VZ 102",
    ),
    "ae86": dict(
        name="Toyota AE86 Trueno", length=4.20, width=1.625, wheelbase=2.40, mass=1030.0, wheel_r=0.29,
        final=4.30, gears={-1: -3.484, 0: 0.0, 1: 3.587, 2: 2.022, 3: 1.384, 4: 1.0, 5: 0.861},
        idle=900, tank=50.0, oil=3.7, coolant=5.6, tq_peak=140.0, tq_rpm=5200.0, tq_width=4200.0,
        cut=7600, overrev=7900, limiter=True, cda=0.35 * 1.75, carb=False,
        axles=(0.90, 3.30), track=0.69, eye=(-0.36, 1.09, 1.80), plate="KB-AE 86",
    ),
}

for _m, _info in MODELS.items():
    SPECS[_m] = dict(name=_info["name"], plate=None, **_info["spec"])

# Константы ВАЗ — для старой 2D-версии
_V = SPECS["vaz2102"]
LENGTH = _V["length"]
WIDTH_M = _V["width"]
WHEELBASE = _V["wheelbase"]
MASS = _V["mass"]
WHEEL_R = _V["wheel_r"]
FINAL = _V["final"]
GEARS = _V["gears"]
GEAR_NAMES = {-1: "R", 0: "N", 1: "1", 2: "2", 3: "3", 4: "4", 5: "5"}
IDLE_RPM = _V["idle"]
TANK = _V["tank"]
OIL_CAP = _V["oil"]
COOLANT_CAP = _V["coolant"]

PAINT = (196, 186, 150)       # выцветший «Сафари»
PAINT_DOOR = (150, 72, 52)    # дверь с разборки другого цвета
PRIMER = (128, 128, 122)      # пятна грунта от прошлого хозяина

AE_WHITE = (238, 238, 232)    # «панда»: белый верх
AE_BLACK = (32, 32, 34)       # чёрный низ


def torque_curve(rpm, spec=_V):
    if rpm < 450:
        return 0.0
    x = (rpm - spec["tq_rpm"]) / spec["tq_width"]
    t = spec["tq_peak"] * (1.0 - 0.55 * x * x)
    if rpm > spec["cut"]:
        t *= max(0.0, 1.0 - (rpm - spec["cut"]) / 900.0)
    return max(0.0, t)


def _rng_blobs(seed, n):
    r = random.Random(seed)
    return [(r.random(), r.random(), 0.4 + r.random() * 0.8, r.random()) for _ in range(n)]


_BLOBS = {p: _rng_blobs("rust-" + p, 34) for p in PANELS}

# Стартовые состояния
PRESETS = {
    # ВАЗ: на ходу, с номерами и TÜV, но ржавый и уставший
    "vaz2102": dict(
        parts={"engine": 55, "battery": 70, "plugs": 60, "distributor": 60, "carb": 55,
               "fuel_pump": 65, "fuel_filter": 50, "air_filter": 45, "starter": 60,
               "alternator": 65, "belt": 55, "radiator": 60, "clutch": 55,
               "brakes_f": 45, "brakes_r": 45, "shocks": 35, "exhaust": 35, "lights": 60,
               "tire_fl": 50, "tire_fr": 45, "tire_rl": 55, "tire_rr": 48,
               "gearbox": 55, "wiring": 55, "steering": 50, "glass": 70,
               "door_l": 60, "door_r": 55, "hood": 50, "trunk": 45, "seats": 50},
        rust={"sill_l": 78.0, "sill_r": 64.0, "floor": 58.0, "arch_f": 55.0,
              "arch_r": 81.0, "fender": 47.0, "doors": 52.0, "tailgate": 69.0},
        fuel=25.0, oil=3.5, oil_quality=60.0, coolant=9.0, brake_fluid=80.0, battery_charge=80.0,
        odometer=187342.0, registered=True, tuv_until=200,
    ),
    # AE86: гниёт на свалке Ковальского — сильно ржавая, мотор стучит, АКБ, глушителя и колеса нет
    "ae86": dict(
        parts={"engine": 15, "battery": None, "plugs": 10, "distributor": 40, "carb": 25,
               "fuel_pump": 15, "fuel_filter": 5, "air_filter": 5, "starter": 35,
               "alternator": 40, "belt": 6, "radiator": 20, "clutch": 25,
               "brakes_f": 10, "brakes_r": 8, "shocks": 15, "exhaust": None, "lights": 15,
               "tire_fl": 20, "tire_fr": 3, "tire_rl": 15, "tire_rr": None,
               "gearbox": 40, "wiring": 35, "steering": 30, "glass": 55,
               "door_l": 45, "door_r": 40, "hood": 50, "trunk": 35, "seats": 55},
        rust={"sill_l": 82.0, "sill_r": 76.0, "floor": 68.0, "arch_f": 61.0,
              "arch_r": 88.0, "fender": 55.0, "doors": 49.0, "tailgate": 72.0},
        fuel=0.0, oil=1.2, oil_quality=10.0, coolant=1.0, brake_fluid=30.0, battery_charge=0.0,
        odometer=212480.0, registered=False, tuv_until=-1,
    ),
}


class Car:
    def __init__(self, model="vaz2102", x=370.5, y=321.0, angle=-math.pi / 2, rng=None, pres=None):
        self.model = model
        self.spec = SPECS[model]
        self.x, self.y = x, y
        self.angle = angle
        self.speed = 0.0
        self.ang_vel = 0.0
        self.steer = 0.0
        self.rpm = 0.0
        self.gear = 0
        self.running = False
        self.cranking = False
        self.crank_time = 0.0
        self.choke = False
        self.lights = False
        self.temp = 12.0
        self.skidding = False
        self.misfire = 0.0
        self.events = []           # сообщения для интерфейса
        self.sounds = []           # имена звуков
        self.shake = 0.0
        self.tow_mass = 0.0        # масса того, что тянем на тросе
        self.snow = 0.0            # слой снега на крыше/капоте (0..1)
        self.sink = 0.0            # насколько колёса ушли в слякоть (м) — для графики
        self._ambient = 5.0
        # внешний вид (для найденных машин — случайный)
        self.color = None
        self.fade = 0.0
        self.dirt = 0.2
        self.dents = []
        self.seed = 1
        self.plate_text = ""
        self.preservation = 1.0
        self.painted = {p: False for p in PANELS}
        if model in PRESETS:
            pre = PRESETS[model]
            slots = SLOTS_BY_MODEL[model]
            self.parts = {s: (None if c is None else {"id": slots[s][1], "cond": float(c)})
                          for s, c in pre["parts"].items()}
            self.rust = dict(pre["rust"])
            for k in ("fuel", "oil", "oil_quality", "coolant", "brake_fluid", "battery_charge",
                      "odometer", "registered", "tuv_until"):
                setattr(self, k, pre[k])
        else:
            self._random_condition(rng or random.Random(), pres)
        self._fill_slots()
        self._sprite_key = None
        self._sprite = None

    # ---- состояние найденной машины: у каждой своё
    def _random_condition(self, rng, pres=None):
        info = model_info(self.model)
        p = pres if pres is not None else 0.08 + 0.8 * rng.betavariate(2.0, 2.2)   # 0.08 (труп) … 0.88 (почти живая)
        self.preservation = p
        self.seed = rng.randint(1, 99999)
        slots = self.slots
        miss = {"battery": 0.55, "exhaust": 0.25, "lights": 0.10, "glass": 0.06, "carb": 0.10,
                "starter": 0.08, "alternator": 0.10, "radiator": 0.10, "plugs": 0.12, "tire": 0.15,
                "shocks": 0.04, "wiring": 0.03}
        self.parts = {}
        for sl in slots:
            key = "tire" if sl.startswith("tire_") else sl
            if rng.random() < miss.get(key, 0.02) * (1.35 - p):
                self.parts[sl] = None
                continue
            c = rng.gauss(p * 100, 25 if sl == "engine" else 20)
            if sl == "battery":
                c = min(c, rng.uniform(5, 45))           # аккумулятор всегда убитый
            elif sl in ("plugs", "fuel_filter", "air_filter"):
                c = min(c, rng.uniform(5, 55))
            elif key == "tire" and rng.random() < 0.35:
                c = rng.uniform(0, 4)                     # спущено
            elif sl == "brakes_f" or sl == "brakes_r":
                c = min(c, rng.uniform(10, 80))           # диски/барабаны прикипели
            self.parts[sl] = {"id": slots[sl][1], "cond": round(max(0.0, min(100.0, c)), 1)}
        if self.parts.get("engine") and rng.random() < 0.25 * (1 - p):
            self.parts["engine"]["cond"] = round(rng.uniform(0, 3), 1)   # мотор заклинило
        # ржавчина: у каждой модели свои слабые места
        weak = {"kadett": {"sill_l": 12, "sill_r": 12, "floor": 10, "arch_r": 8},
                "golf": {"arch_r": 14, "sill_l": 8, "sill_r": 8, "tailgate": 12},
                "taunus": {"doors": 12, "arch_f": 10, "arch_r": 10},
                "wartburg": {"sill_l": 8, "sill_r": 8, "floor": 12},
                "w123": {k: -12 for k in PANELS},
                "trabant": {"floor": 12, "sill_l": 10, "sill_r": 10}}.get(self.model, {})
        self.rust = {}
        for pn in PANELS:
            r = (1 - p) * 100 * rng.uniform(0.65, 1.2) + rng.uniform(-8, 8) + weak.get(pn, 0)
            if "tough_body" in info["quirks"]:
                r *= 0.6        # толстый металл и хорошая антикоррозийка
            if "duroplast" in info["quirks"] and pn in ("fender", "doors", "tailgate", "arch_f", "arch_r"):
                r *= 0.08 if pn in ("fender", "doors", "tailgate") else 0.5   # пластиковые панели не ржавеют
            self.rust[pn] = round(max(0.0, min(100.0, r)), 1)
        sp = self.spec
        self.snow = round(rng.uniform(0.3, 1.0), 2)
        self.fuel = round(rng.uniform(0, 3), 1)
        self.oil = round(sp["oil"] * rng.uniform(0.25, 1.0), 2) if sp["oil"] > 0 else 0.0
        self.oil_quality = round(rng.uniform(5, 45), 1)
        self.coolant = round(sp["coolant"] * rng.uniform(0.0, 0.7), 1) if sp["coolant"] > 0 else 0.0
        self.brake_fluid = round(rng.uniform(10, 70), 1)
        self.battery_charge = 0.0 if rng.random() < 0.8 else round(rng.uniform(5, 30), 1)
        lo, hi = info["odo"]
        self.odometer = float(rng.randint(lo, hi))
        self.registered = False
        self.tuv_until = -1
        body = info["body"]
        self.color = tuple(body["colors"][rng.randrange(len(body["colors"]))])
        self.fade = round(0.2 + (1 - p) * 0.6 * rng.uniform(0.7, 1.1), 2)
        self.dirt = round(0.35 + rng.random() * 0.65, 2)
        L = sp["length"]
        self.dents = [(round(rng.uniform(0.3, L - 0.3), 2), round(rng.uniform(sp["axles"][0] * 0 + 0.4, 0.8), 2),
                       round(rng.uniform(0.08, 0.2), 2), rng.choice("lr"))
                      for _ in range(int((1 - p) * 7 * rng.uniform(0.5, 1.2)))]

    def _fill_slots(self):
        """Старые сохранения: добавить новые слоты (КПП, проводка, рулевое, стекло)."""
        for sl, (name, pid, _) in self.slots.items():
            if sl not in self.parts:
                self.parts[sl] = {"id": pid, "cond": 60.0}

    def sp(self, key, default=None):
        return self.spec.get(key, default)

    @property
    def paint(self):
        """Цвет краски с учётом выцветания."""
        c = self.color or (196, 186, 150)
        f = self.fade * 0.5
        return tuple(int(c[i] * (1 - f) + 205 * f) for i in range(3))

    @property
    def odd_door(self):
        """Дверь другого цвета (с разборки) — у своей «двойки» и у некоторых доноров."""
        return self.color is None or self.seed % 4 == 0

    @property
    def lights_ok(self):
        return (self.lights and self.battery_charge > 2 and self.c("lights") > 0.05
                and self.c("wiring") > 0.05)

    # ---- характеристики модели
    @property
    def name(self):
        return self.spec["name"]

    @property
    def slots(self):
        return SLOTS_BY_MODEL[self.model]

    @property
    def tank(self):
        return self.spec["tank"]

    @property
    def oil_cap(self):
        return self.spec["oil"]

    @property
    def coolant_cap(self):
        return self.spec["coolant"]

    @property
    def max_gear(self):
        return max(self.spec["gears"])

    @property
    def plate(self):
        return self.spec.get("plate") or self.plate_text or "—"

    @property
    def length(self):
        return self.spec["length"]

    # ------------------------------------------------------------ сохранение
    SAVE_FIELDS = ["model", "color", "fade", "dirt", "dents", "seed", "plate_text", "preservation", "snow",
                   "x", "y", "angle", "gear", "choke", "lights", "temp", "fuel", "oil",
                   "oil_quality", "coolant", "brake_fluid", "battery_charge", "odometer",
                   "registered", "tuv_until", "parts", "rust", "painted"]

    def to_dict(self):
        return {k: getattr(self, k) for k in self.SAVE_FIELDS}

    def from_dict(self, d):
        for k in self.SAVE_FIELDS:
            if k in d:
                setattr(self, k, d[k])
        self.spec = SPECS[self.model]
        if isinstance(self.color, list):
            self.color = tuple(self.color)
        self.dents = [tuple(x) for x in self.dents]
        self._fill_slots()
        self.speed = 0.0
        self.running = False
        self._sprite_key = None

    # ------------------------------------------------------------ помощники
    def c(self, slot):
        """Состояние детали 0..1 (0 если детали нет)."""
        p = self.parts.get(slot)
        return 0.0 if p is None else max(0.0, p["cond"]) / 100.0

    def has(self, slot):
        return self.parts.get(slot) is not None

    def wear(self, slot, amount):
        p = self.parts.get(slot)
        if p is not None:
            p["cond"] = max(0.0, p["cond"] - amount)

    def say(self, s):
        if s not in self.events:
            self.events.append(s)

    def forward(self):
        return math.cos(self.angle), math.sin(self.angle)

    def tire_list(self):
        return ["tire_fl", "tire_fr", "tire_rl", "tire_rr"]

    def flat_tires(self):
        return [t for t in self.tire_list() if self.c(t) < 0.05]

    def kmh(self):
        return abs(self.speed) * 3.6

    def body_circles(self):
        fx, fy = self.forward()
        off = self.length / 2 - 0.85
        return [(self.x + fx * off, self.y + fy * off, 0.85),
                (self.x - fx * off, self.y - fy * off, 0.85)]

    def max_rust(self):
        return max(self.rust.values())

    # ------------------------------------------------------------ запуск
    def start_crank(self):
        if self.running:
            return
        if not self.has("battery") or self.battery_charge < 8:
            self.say("Щёлк... Аккумулятор сел.")
            self.sounds.append("click")
            return
        if not self.has("starter") or self.c("starter") < 0.05:
            self.say("Стартер не крутит (неисправен).")
            self.sounds.append("click")
            return
        if not self.has("wiring") or self.c("wiring") < 0.04:
            self.say("Тишина: проводка сгнила — ток не доходит до стартера.")
            self.sounds.append("click")
            return
        self.cranking = True
        self.crank_time = 0.0

    def stop_crank(self):
        self.cranking = False

    def engine_off(self, reason=None):
        if self.running and reason:
            self.say(reason)
        self.running = False
        self.cranking = False

    @property
    def ch(self):
        """Обогащение на холодную: у ВАЗ — ручной подсос, у AE86 (впрыск) — автоматически."""
        if self.sp("diesel"):
            return False
        if self.spec["carb"]:
            return self.choke
        return self.temp < 45

    def _start_chance(self):
        """Вероятность схватить за секунду прокрутки."""
        if self.c("engine") < 0.04:
            return 0.0, "Двигатель заклинило — нужен ремонт/замена."
        diesel = self.sp("diesel")
        if self.fuel <= 0.05:
            return 0.0, "Нет дизтоплива." if diesel else "Нет бензина."
        if not self.has("fuel_pump") or self.c("fuel_pump") < 0.03:
            return 0.0, "Топливо не поступает (" + self.slots["fuel_pump"][0].lower() + ")."
        if not self.has("carb"):
            return 0.0, "Нет: " + self.slots["carb"][0].lower() + "."
        if diesel:
            if not self.has("distributor") or self.c("distributor") < 0.03:
                return 0.0, "ТНВД не качает — дизель не заведётся."
            p = 1.8 * (0.4 + 0.6 * self.c("distributor")) * (0.4 + 0.6 * self.c("carb"))
            p *= 0.5 + 0.5 * self.c("engine")
            p *= 0.3 + 0.7 * min(1.0, self.c("fuel_filter") * 3)
            if self.temp < 45:     # холодный дизель: всё решают свечи накаливания
                glow = self.c("plugs") if self.has("plugs") else 0.0
                p *= 0.08 + 0.92 * glow
                if glow < 0.2 and self.crank_time > 1.5:
                    return p, "Свечи накаливания не греют — холодный дизель не схватывает."
            p *= min(1.0, self.battery_charge / 100 * 1.6 * (0.7 if self._ambient < 0 else 1.0))
            return p, None
        if not self.has("plugs") or self.c("plugs") < 0.02:
            return 0.0, "Нет искры (свечи)."
        if not self.has("distributor") or self.c("distributor") < 0.03:
            return 0.0, "Нет искры (трамблёр)."
        p = 2.4
        p *= self.c("plugs") ** 0.8
        p *= 0.4 + 0.6 * self.c("distributor")
        p *= 0.4 + 0.6 * self.c("carb")
        p *= 0.5 + 0.5 * self.c("engine")
        p *= 0.3 + 0.7 * min(1.0, self.c("fuel_filter") * 3)
        cold = self.temp < 45
        if cold and not self.ch:
            p *= 0.2
        if not cold and self.ch:
            p *= 0.35  # заливает свечи
        charge = self.battery_charge / 100 * (0.75 if self._ambient < 0 else 1.0)   # на морозе АКБ слабее
        p *= min(1.0, charge * 2)
        return p, None

    # ------------------------------------------------------------ обновление
    def update(self, dt, inp, rain=False, ambient=11.0, grip_mult=1.0, slush=0.0):
        """grip_mult — сцепление поверхности (снег, лёд); slush — толщина слякоти под колёсами (м)."""
        self._ambient = ambient
        throttle = inp.get("throttle", 0.0)
        brake = inp.get("brake", 0.0)
        steer_in = inp.get("steer", 0.0)
        clutch = inp.get("clutch", False)
        self.skidding = False

        # --- стартер
        if self.cranking:
            self.crank_time += dt
            self.battery_charge -= 3.5 * dt
            self.wear("starter", 0.04 * dt)
            self.rpm = 220 + random.random() * 60
            if self.battery_charge < 6:
                self.cranking = False
                self.say("Аккумулятор разрядился...")
            else:
                p, reason = self._start_chance()
                if reason and self.crank_time > 1.5:
                    self.say(reason)
                if random.random() < p * dt:
                    self.cranking = False
                    self.running = True
                    self.rpm = 1300 if self.ch else 1000
                    self.sounds.append("start")
                    self.say("Завелась!")

        # --- батарея
        if self.running:
            if self.has("alternator") and self.c("belt") > 0.05:
                self.battery_charge += 0.35 * self.c("alternator") * dt
            elif self.battery_charge > 0:
                self.battery_charge -= 0.05 * dt
        if self.lights:
            self.battery_charge -= (0.02 if self.running else 0.08) * dt
        cap = 100.0 * (0.3 + 0.7 * self.c("battery")) if self.has("battery") else 0.0
        self.battery_charge = max(0.0, min(cap, self.battery_charge))
        if self.running and self.battery_charge <= 0.5 and not self.has("alternator") and not self.sp("diesel"):
            self.engine_off("Всё электричество село — двигатель заглох.")
        # гнилая проводка: пропадает искра (дизелю искра не нужна)
        elec = self.c("wiring")
        if self.running and not self.sp("diesel") and elec < 0.3 and random.random() < (0.3 - elec) * 0.06 * dt:
            self.engine_off("Мотор заглох: пропала искра — гниёт проводка.")

        # --- двигатель работает
        drive_force = 0.0
        if self.running:
            eng = self.c("engine")
            diesel = self.sp("diesel")
            two = self.sp("two_stroke")
            plug_f = 1.0 if diesel else (0.35 + 0.65 * self.c("plugs") ** 0.5)
            pf = (0.55 + 0.45 * eng) * plug_f
            pf *= (0.6 + 0.4 * self.c("distributor")) * (0.6 + 0.4 * self.c("carb"))
            pf *= 0.8 + 0.2 * self.c("air_filter")
            if self.temp < 45 and not self.ch:
                pf *= 0.7
            if self.ch and self.temp > 60:
                pf *= 0.8
            # пропуски зажигания
            self.misfire = max(0.0, self.misfire - dt)
            if not diesel and random.random() < (1 - self.c("plugs")) * 1.5 * dt + (1 - self.c("distributor")) * 0.6 * dt:
                self.misfire = 0.12
                self.sounds.append("misfire")
            if self.misfire > 0:
                pf *= 0.3
            # топливное голодание
            if self.c("fuel_filter") < 0.15 and self.rpm > 3200:
                pf *= 0.5
            if self.fuel <= 0 or self.c("fuel_pump") < 0.02:
                self.engine_off("Двигатель заглох: нет подачи топлива.")

            ratio = self.spec["gears"][self.gear] * self.spec["final"]
            wheel_rpm = self.speed / (2 * math.pi * self.spec["wheel_r"]) * 60
            box = self.c("gearbox")
            engaged = self.gear != 0 and not clutch and self.has("clutch") and box > 0.03
            # изношенная КПП: выбивает передачу под нагрузкой
            if engaged and box < 0.35 and throttle > 0.5 and random.random() < (0.35 - box) * 0.35 * dt:
                self.gear = 0
                self.say("Выбило передачу! Коробка изношена.")
                self.sounds.append("grind")
                engaged = False
            if engaged:
                rpm_wheels = abs(wheel_rpm * ratio)
                slip = False
                if rpm_wheels < 1100 and throttle > 0.05:
                    # водитель сам «ловит» сцепление
                    slip = True
                    target = 1100 + throttle * 1500
                    self.rpm += (target - self.rpm) * min(1, dt * 5)
                    sf = 1.0 if abs(self.gear) <= 2 else 0.35
                    self.wear("clutch", 0.03 * dt * throttle)
                    if abs(self.gear) >= 3 and rpm_wheels < 350 and random.random() < 0.8 * dt:
                        self.engine_off("Заглохла! Трогайтесь с первой передачи.")
                        self.sounds.append("stall")
                else:
                    sf = 1.0
                    self.rpm = max(rpm_wheels, 0)
                if self.running and not slip and rpm_wheels < 520:
                    self.engine_off("Заглохла! (выжмите сцепление — Пробел)")
                    self.sounds.append("stall")
                if self.running:
                    tq = torque_curve(self.rpm, self.spec) * throttle * pf * sf
                    if self.spec["limiter"] and self.rpm > self.spec["cut"] + 100:
                        tq = 0.0   # отсечка топлива
                    # изношенное сцепление пробуксовывает под нагрузкой
                    cl = self.c("clutch")
                    if cl < 0.3 and tq > 50 * cl / 0.3:
                        self.rpm += 400 * dt * 10
                        tq *= 0.4 + cl
                    drive_force = tq * ratio * 0.9 / self.spec["wheel_r"]
                    # торможение двигателем
                    if throttle < 0.05:
                        drive_force -= math.copysign(min(abs(self.speed) * 40, 900), self.speed) * (abs(ratio) / 16.7)
            else:
                top = self.spec["cut"] + (200 if self.spec["limiter"] else -400)
                target = self.spec["idle"] + throttle * (top - self.spec["idle"]) * pf
                if self.ch and self.temp < 60:
                    target += 400
                target += (random.random() - 0.5) * (1 - self.c("plugs")) * 300
                self.rpm += (target - self.rpm) * min(1, dt * (6 if target > self.rpm else 2.5))
                # холодный без подсоса — глохнет на холостых
                if self.temp < 30 and not self.ch and throttle < 0.05 and random.random() < 0.08 * dt:
                    self.engine_off("Холодный двигатель заглох — включите подсос (C).")
                    self.sounds.append("stall")

            self.rpm = max(0.0, self.rpm)
            if self.rpm > self.spec["overrev"]:
                self.wear("engine", 0.25 * dt)
                self.say("Перекрут двигателя!")
            # 4A-GE — «клапанобойный»: оборвался ремень ГРМ — мотору конец
            if self.model == "ae86" and self.c("belt") < 0.03:
                self.wear("engine", 100)
                self.engine_off("Оборвался ремень ГРМ! Клапаны встретились с поршнями...")
                self.sounds.append("crash")

            # расход топлива (л/с)
            cons = 0.0002 + 6.1e-7 * self.rpm * (0.3 + throttle)
            if self.ch:
                cons *= 1.5
            if two:
                cons *= 1.25
            if diesel:
                cons *= 0.7
            cons *= 1 + (1 - self.c("carb")) * 0.5
            self.fuel = max(0.0, self.fuel - cons * dt)

            # температура
            if self.sp("air_cooled"):
                # воздушное охлаждение: всё держится на ремне вентилятора
                cool = 0.25 + 0.75 * self.c("belt")
            else:
                cool = (0.3 + 0.7 * self.c("radiator")) * min(1.0, self.coolant / (self.coolant_cap * 0.6))
                if self.c("radiator") < 0.25:
                    self.coolant = max(0.0, self.coolant - 0.004 * dt)
            target_t = 86 + (1 - cool) * 75 + self.rpm / 6000 * 7
            self.temp += (target_t - self.temp) * dt * 0.03

            # масло
            if not two:
                burn = (1 - eng) * 0.00012 * max(0.3, self.rpm / 3000)
                self.oil = max(0.0, self.oil - burn * dt)
                self.oil_quality = max(0.0, self.oil_quality - 0.004 * dt)

            # износ двигателя
            w = 0.0004 * max(0.3, self.rpm / 3000) * self.sp("wear", 1.0)
            if not two:   # у двухтакта масло в бензине — картера нет
                if self.oil < min(1.3, self.oil_cap * 0.35):
                    w *= 40
                    self.say("Лампа давления масла! Долейте масло.")
                if self.oil_quality < 20:
                    w *= 3
            if self.temp > 110:
                w += 0.08
                self.say("ПЕРЕГРЕВ! Остановитесь.")
            if self.temp > 122:
                w += 0.5
                self.say("Пар из-под капота! Пробило прокладку?")
            self.wear("engine", w * dt)
            no_oil = (not two) and self.oil <= 0.05
            if self.c("engine") < 0.03 or no_oil:
                if no_oil:
                    self.wear("engine", 100)
                self.engine_off("Двигатель ЗАКЛИНИЛО!")
                self.sounds.append("crash")
            self.wear("plugs", 0.0015 * dt * max(0.4, self.rpm / 3000))
            self.wear("belt", 0.0008 * dt)
            self.wear("air_filter", 0.0006 * dt)
            self.wear("fuel_filter", 0.0005 * dt)
            self.wear("exhaust", 0.0004 * dt)
            self.wear("alternator", 0.0003 * dt)
            self.wear("distributor", 0.0003 * dt)
            self.wear("carb", 0.0002 * dt)
            self.wear("fuel_pump", 0.0002 * dt)
            self.wear("wiring", 0.00005 * dt)
            if engaged:
                self.wear("gearbox", 0.00015 * dt * (1 + throttle))
        else:
            if not self.cranking:
                self.rpm = max(0.0, self.rpm - 3000 * dt)
            self.temp += (ambient - self.temp) * dt * 0.004

        # --- ходовая
        tires = self.tire_list()
        grip = 0.55 + 0.45 * sum(min(1, self.c(t) * 3) for t in tires) / 4
        if rain:
            grip *= 0.78
        grip *= 0.85 + 0.15 * self.c("shocks")
        grip *= self.sp("grip", 1.0)
        grip *= grip_mult
        if slush > 0.015:
            grip *= 1.0 - min(0.35, slush * 3.0)
        self.sink = slush * 0.6
        flats = self.flat_tires()
        missing = [t for t in tires if not self.has(t)]

        roll = 0.015 * (self.spec["mass"] + self.tow_mass) * 9.81 + 350 * len(flats) + 3500 * len(missing)
        if slush > 0.015:     # колёса продавливают слякоть — как езда по песку
            roll += slush * 26000 * (0.35 + min(1.0, abs(self.speed) / 8))
        drag = 0.5 * 1.2 * self.spec["cda"] * self.speed * self.speed
        brake_eff = (0.72 * min(1, self.c("brakes_f") * 4 + 0.15) + 0.28 * min(1, self.c("brakes_r") * 4 + 0.15))
        brake_eff *= min(1.0, self.brake_fluid / 50.0 + 0.2)
        brake_eff *= self.sp("brake", 1.0)
        brake_force = brake * 8.5 * self.spec["mass"] * brake_eff * min(1.0, grip + 0.2)
        if brake > 0 and abs(self.speed) > 1:
            self.wear("brakes_f", 0.012 * brake * abs(self.speed) * dt)
            self.wear("brakes_r", 0.007 * brake * abs(self.speed) * dt)
            if self.c("brakes_f") < 0.05:
                self.say("Скрежет тормозов: колодки стёрты до металла!")
                self.sounds.append("grind")

        resist = roll + drag + brake_force
        acc = drive_force / (self.spec["mass"] + self.tow_mass)
        v = self.speed
        v += acc * dt
        if abs(v) > 0:
            dv = resist / (self.spec["mass"] + self.tow_mass) * dt
            if abs(v) <= dv:
                v = 0.0
            else:
                v -= math.copysign(dv, v)
        self.speed = v

        # руление
        self.steer += (steer_in - self.steer) * min(1, dt * 6)
        st = self.c("steering")
        max_steer = math.radians(self.sp("steer_max", 33)) / (1 + abs(self.speed) / 14)
        max_steer *= (0.55 + 0.45 * st) if self.has("steering") else 0.1
        ang = self.speed / self.spec["wheelbase"] * math.tan(self.steer * max_steer)
        # люфт рулевого: машину водит по дороге
        if st < 0.6 and abs(self.speed) > 3:
            ang += math.sin(self.odometer * 900 + self.seed) * (0.6 - st) * 0.012 * abs(self.speed) / 10
        # спущенное колесо тянет в сторону
        pull = 0.0
        for t in flats + missing:
            pull += -0.02 if t.endswith("l") else 0.02
        ang += pull * self.speed * 0.15
        lat = abs(self.speed * ang)
        lim = grip * 9.81 * 0.9
        if lat > lim and abs(self.speed) > 3:
            ang *= lim / lat
            self.skidding = True
            for t in tires:
                self.wear(t, 0.02 * dt)
        self.ang_vel = ang
        self.angle += ang * dt

        # износ
        spd = abs(self.speed)
        for t in tires:
            self.wear(t, 0.00004 * spd * dt)
        self.wear("shocks", 0.00002 * spd * dt)
        self.wear("steering", 0.00001 * spd * dt)
        self.odometer += spd * dt / 1000.0

        # вибрация кузова от плохих амортизаторов
        self.shake = (1 - self.c("shocks")) * min(1, spd / 15)

        fx, fy = self.forward()
        self.x += fx * self.speed * dt
        self.y += fy * self.speed * dt

    # ------------------------------------------------------------ удары
    def impact(self, speed_ms):
        """Удар о препятствие. Возвращает True, если водителю очень плохо."""
        s = abs(speed_ms)
        if s < 2:
            return False
        self.sounds.append("crash")
        dmg = (s - 2) * 2.2
        self.wear("lights", dmg * 1.5)
        self.wear("radiator", dmg * (0.8 if s > 8 else 0.1))
        if s > 12:
            self.wear("engine", dmg * 0.5)
            self.wear("shocks", dmg * 0.5)
            self.say("Сильный удар! Радиатор и фары пострадали.")
        for p in ("fender", "arch_f", "doors"):
            self.rust[p] = min(100.0, self.rust[p] + dmg * 0.15)
        self._sprite_key = None
        return s > 22

    # ------------------------------------------------------------ ржавчина
    def rust_tick(self, minutes, wet=False, in_garage=False):
        rate = 0.00045
        if wet:
            rate *= 3.0
        if in_garage:
            rate *= 0.3
        for p in self.rust:
            r = rate * (0.25 if self.painted[p] else 1.0)
            if self.model in MODELS and "duroplast" in MODELS[self.model]["quirks"] and p in ("fender", "doors", "tailgate"):
                r *= 0.05
            if p in ("floor", "doors") and not (self.has("door_l") and self.has("door_r")):
                r *= 1.8          # без дверей в салон задувает снег — пол гниёт быстрее
            # чем больше ржавчины, тем быстрее она ест дальше
            r *= 0.6 + self.rust[p] / 100.0
            self.rust[p] = min(100.0, self.rust[p] + r * minutes)
        self.wear("exhaust", 0.0006 * minutes * (2 if wet else 1))
        if self.has("battery") and not self.running:
            self.battery_charge = max(0.0, self.battery_charge - 0.0015 * minutes)
        if not self.running:
            self.temp += (11 - self.temp) * min(1.0, minutes * 0.02)

    # ------------------------------------------------------------ TÜV
    def tuv_defects(self):
        d = []
        names = {"sill_l": "порог левый", "sill_r": "порог правый", "floor": "днище"}
        for p, v in self.rust.items():
            lim = 30 if p in names else 45
            if v > lim:
                d.append(f"Коррозия: {PANELS[p]} ({v:.0f}%)")
        if self.c("brakes_f") < 0.35:
            d.append("Тормоза передние: колодки изношены")
        if self.c("brakes_r") < 0.3:
            d.append("Тормоза задние: колодки изношены")
        if self.brake_fluid < 60:
            d.append("Уровень тормозной жидкости")
        for t in self.tire_list():
            if self.c(t) < 0.3:
                d.append(f"Шина: {self.slots[t][0]} — протектор/повреждение")
        if self.c("lights") < 0.4:
            d.append("Фары: неисправны / разбиты")
        if self.c("exhaust") < 0.4:
            d.append("Выхлоп негерметичен (громко, CO)")
        if self.c("shocks") < 0.3:
            d.append("Амортизаторы: не держат")
        if self.c("engine") < 0.3:
            d.append("Двигатель: сильная течь масла")
        if self.c("steering") < 0.35:
            d.append("Люфт рулевого управления")
        if self.c("wiring") < 0.3:
            d.append("Электрика: проводка неисправна (свет, сигналы)")
        if self.c("glass") < 0.4:
            d.append("Лобовое стекло: трещины в зоне обзора")
        for sl, txt in (("door_l", "Нет левых дверей"), ("door_r", "Нет правых дверей"), ("hood", "Нет капота"),
                        ("trunk", "Нет крышки багажника"), ("seats", "Нет сидений")):
            if not self.has(sl):
                d.append(txt)
            elif self.c(sl) < 0.2:
                d.append(self.slots[sl][0] + ": сгнили петли / не закрывается")
        if not self.running and self.c("engine") > 0:
            pass
        return d

    # ------------------------------------------------------------ отрисовка сверху
    def _make_top_sprite(self, s):
        if self.model != "vaz2102":
            L, W = int(self.length * s), int(self.spec["width"] * s)
            img = pygame.Surface((L, W), pygame.SRCALPHA)
            pygame.draw.rect(img, AE_WHITE if self.model == "ae86" else self.paint, (0, 0, L, W), border_radius=int(0.25 * s))
            pygame.draw.rect(img, (40, 50, 60), (int(1.5 * s), int(0.15 * s), int(1.5 * s), W - int(0.3 * s)))
            return img
        L, W = int(LENGTH * s), int(WIDTH_M * s)
        img = pygame.Surface((L, W), pygame.SRCALPHA)
        m = lambda v: int(v * s)
        pygame.draw.rect(img, PAINT, (0, 0, L, W), border_radius=m(0.28))
        # капот
        pygame.draw.rect(img, (186, 176, 142), (m(2.95), m(0.1), m(0.95), W - m(0.2)), border_radius=m(0.1))
        pygame.draw.rect(img, PRIMER, (m(3.25), m(0.35), m(0.35), m(0.45)), border_radius=m(0.1))
        # лобовое
        pygame.draw.polygon(img, (38, 52, 62), [(m(2.45), m(0.18)), (m(2.95), m(0.1)),
                                                (m(2.95), W - m(0.1)), (m(2.45), W - m(0.18))])
        # крыша (универсал — длинная)
        pygame.draw.rect(img, (206, 198, 164), (m(0.5), m(0.16), m(1.95), W - m(0.32)))
        # багажник на крыше
        for yy in (0.3, WIDTH_M - 0.3):
            pygame.draw.line(img, (70, 60, 50), (m(0.6), m(yy)), (m(2.3), m(yy)), max(1, m(0.05)))
        for xx in (0.8, 1.4, 2.0):
            pygame.draw.line(img, (70, 60, 50), (m(xx), m(0.3)), (m(xx), m(WIDTH_M - 0.3)), max(1, m(0.04)))
        # заднее стекло
        pygame.draw.rect(img, (38, 52, 62), (m(0.15), m(0.2), m(0.35), W - m(0.4)))
        # боковые стёкла
        for yy in (0.06, WIDTH_M - 0.16):
            pygame.draw.rect(img, (50, 64, 74), (m(0.25), m(yy), m(2.6), m(0.1)))
        # бамперы
        pygame.draw.rect(img, (170, 168, 160), (L - m(0.1), m(0.05), m(0.1), W - m(0.1)))
        pygame.draw.rect(img, (170, 168, 160), (0, m(0.05), m(0.08), W - m(0.1)))
        # фары и фонари
        for yy in (0.32, WIDTH_M - 0.32):
            pygame.draw.circle(img, (235, 232, 200), (L - m(0.12), m(yy)), max(2, m(0.12)))
            pygame.draw.rect(img, (170, 30, 30), (0, m(yy) - m(0.12), m(0.06), m(0.24)))
        # ржавчина по краям
        regions = {
            "sill_l": [(1.0, 2.9, 0.0, 0.12)], "sill_r": [(1.0, 2.9, WIDTH_M - 0.12, WIDTH_M)],
            "arch_f": [(2.95, 3.6, 0.0, 0.15), (2.95, 3.6, WIDTH_M - 0.15, WIDTH_M)],
            "arch_r": [(0.5, 1.15, 0.0, 0.15), (0.5, 1.15, WIDTH_M - 0.15, WIDTH_M)],
            "fender": [(3.3, 4.0, 0.05, 0.3), (3.3, 4.0, WIDTH_M - 0.3, WIDTH_M - 0.05)],
            "doors": [(1.2, 2.8, 0.1, 0.2), (1.2, 2.8, WIDTH_M - 0.2, WIDTH_M - 0.1)],
            "tailgate": [(0.0, 0.45, 0.2, WIDTH_M - 0.2)],
        }
        for p, regs in regions.items():
            self._draw_blobs(img, p, regs, lambda x, y: (m(x), m(y)), s * 0.09)
        return img

    def _draw_blobs(self, img, panel, regs, tf, rscale):
        rv = self.rust[panel]
        for i, (fx, fy, rr, th) in enumerate(_BLOBS[panel]):
            if rv / 100.0 < th * 0.9:
                continue
            x0, x1, y0, y1 = regs[i % len(regs)]
            px, py = tf(x0 + (x1 - x0) * fx, y0 + (y1 - y0) * fy)
            rad = max(1, int(rscale * rr * (0.6 + rv / 70)))
            col = (140, 70, 30) if th < 0.5 else (110, 50, 22)
            pygame.draw.circle(img, col, (px, py), rad)
            if rv > 80 and th > 0.75:
                pygame.draw.circle(img, (20, 14, 10), (px, py), max(1, rad // 2))

    def top_sprite(self):
        key = tuple(int(v // 5) for v in self.rust.values())
        if key != self._sprite_key:
            self._sprite = self._make_top_sprite(PPM * 3)
            self._sprite_key = key
        return self._sprite

    def draw_top(self, surf, cam, t=0.0):
        img = self.top_sprite()
        rot = pygame.transform.rotozoom(img, -math.degrees(self.angle), 1 / 3)
        sx = (self.x - cam[0]) * PPM
        sy = (self.y - cam[1]) * PPM
        if self.shake > 0.05:
            sx += math.sin(t * 37) * self.shake * 1.5
            sy += math.cos(t * 41) * self.shake * 1.5
        # тень
        mask = pygame.mask.from_surface(rot)
        sh = mask.to_surface(setcolor=(0, 0, 0, 80), unsetcolor=(0, 0, 0, 0))
        surf.blit(sh, sh.get_rect(center=(sx + 3, sy + 3)))
        surf.blit(rot, rot.get_rect(center=(sx, sy)))

    # ------------------------------------------------------------ вид сбоку (гараж)
    def draw_side(self, surf, ox, oy, s, texture=False, side="l"):
        """Вид сбоку (перед справа). texture=True — для 3D: без колёс и тени, арки прозрачные."""
        if self.model == "ae86":
            return self._draw_side_ae86(surf, ox, oy, s, texture, side)
        if self.model in MODELS:
            return self._draw_side_generic(surf, ox, oy, s, texture, side)
        return self._draw_side_vaz(surf, ox, oy, s, texture, side)

    def _clear_doors(self, surf, P, side, texture, polys):
        """Снятые двери: в борту дыра, видно салон (в текстуре — прозрачно)."""
        if self.has("door_" + side):
            return
        for poly_ in polys:
            pts = [P(x, y) for x, y in poly_]
            pygame.draw.polygon(surf, (0, 0, 0, 0) if texture else (35, 33, 30), pts)
            pygame.draw.lines(surf, (60, 55, 50), True, pts, 3)     # край проёма
            # петли и замок
            x0 = min(p_[0] for p_ in poly_)
            x1 = max(p_[0] for p_ in poly_)
            y0 = min(p_[1] for p_ in poly_)
            for hy in (y0 + 0.2, y0 + 0.45):
                pygame.draw.rect(surf, (90, 85, 80), (*P(x1 - 0.03, hy + 0.04), 5, 6))
            pygame.draw.rect(surf, (90, 85, 80), (*P(x0 + 0.01, y0 + 0.4), 4, 7))

    def _rust_blob(self, surf, P, panel, regs, rscale):
        self._draw_blobs(surf, panel, regs, lambda x, y: P(x, y), rscale)

    def _draw_side_ae86(self, surf, ox, oy, s, texture, side):
        P = lambda x, y: (int(ox + x * s), int(oy - y * s))
        poly = lambda pts: [P(x, y) for x, y in pts]
        if not texture:
            pygame.draw.ellipse(surf, (20, 20, 22), (ox - 0.2 * s, oy - 0.08 * s, 4.6 * s, 0.2 * s))
        body = [(0.02, 0.30), (0.0, 0.42), (0.02, 0.80), (0.15, 0.86), (0.55, 0.88), (3.05, 0.86),
                (3.9, 0.76), (4.18, 0.70), (4.2, 0.55), (4.18, 0.33), (3.8, 0.30)]
        upper = [(0.0, 0.56), (0.02, 0.80), (0.15, 0.86), (0.55, 0.88), (3.05, 0.86), (3.9, 0.76),
                 (4.18, 0.70), (4.2, 0.56)]
        green = [(0.40, 0.87), (1.45, 1.30), (1.6, 1.34), (2.45, 1.34), (2.6, 1.31), (3.1, 0.87)]
        pygame.draw.polygon(surf, AE_WHITE, poly(green))
        pygame.draw.polygon(surf, AE_BLACK, poly(body))
        pygame.draw.polygon(surf, AE_WHITE, poly(upper))
        # вырезы арок
        old = surf.get_clip()
        surf.set_clip(pygame.Rect(0, 0, surf.get_width(), P(0, 0.30)[1]))
        for wx in self.spec["axles"]:
            pygame.draw.circle(surf, (0, 0, 0, 0) if texture else (22, 20, 20), P(wx, 0.30), int(0.40 * s))
        surf.set_clip(old)
        glass = (40, 50, 60)
        pygame.draw.polygon(surf, AE_BLACK, poly([(1.0, 0.89), (1.5, 1.29), (2.5, 1.30), (3.0, 0.89)]))
        pygame.draw.polygon(surf, glass, poly([(2.02, 0.92), (2.02, 1.27), (2.45, 1.28), (2.93, 0.92)]))
        pygame.draw.polygon(surf, glass, poly([(1.08, 0.92), (1.54, 1.25), (1.92, 1.26), (1.92, 0.92)]))
        pygame.draw.polygon(surf, glass, poly([(0.45, 0.90), (1.40, 1.28), (1.47, 1.26), (0.56, 0.90)]))
        dl = (120, 120, 118)
        pygame.draw.line(surf, dl, P(1.97, 0.34), P(1.97, 0.9), 2)
        pygame.draw.line(surf, dl, P(3.02, 0.36), P(3.02, 0.86), 2)
        pygame.draw.rect(surf, (60, 60, 60), (*P(2.2, 0.80), int(0.14 * s), max(3, int(0.03 * s))))   # ручка
        pygame.draw.rect(surf, AE_BLACK, (*P(2.92, 1.0), int(0.12 * s), int(0.08 * s)))              # зеркало
        # бамперы (чёрный пластик), фонари, поворотник
        pygame.draw.rect(surf, (25, 25, 25), (*P(3.96, 0.52), int(0.3 * s), int(0.19 * s)))
        pygame.draw.rect(surf, (25, 25, 25), (*P(-0.06, 0.50), int(0.28 * s), int(0.17 * s)))
        pygame.draw.rect(surf, (190, 30, 30), (*P(0.0, 0.80), int(0.14 * s), int(0.18 * s)))
        pygame.draw.rect(surf, (230, 140, 30), (*P(4.02, 0.48), int(0.1 * s), int(0.05 * s)))
        pygame.draw.line(surf, (150, 150, 150), P(3.72, 0.745), P(4.08, 0.715), 2)                   # щель поп-ап фары
        if self.has("exhaust"):
            ex = (100, 95, 90) if self.c("exhaust") > 0.4 else (110, 60, 30)
            pygame.draw.rect(surf, ex, (*P(-0.1, 0.24), int(0.6 * s), int(0.07 * s)))
        # ржавчина
        self._rust_blob(surf, P, "sill_" + side, [(1.25, 2.9, 0.30, 0.40)], s * 0.035)
        self._rust_blob(surf, P, "doors", [(2.0, 2.95, 0.38, 0.50)], s * 0.03)
        self._rust_blob(surf, P, "fender", [(3.5, 4.1, 0.45, 0.72), (0.12, 0.55, 0.46, 0.78)], s * 0.03)
        self._rust_blob(surf, P, "tailgate", [(0.0, 0.18, 0.5, 0.84)], s * 0.025)
        for p, cx in (("arch_f", self.spec["axles"][1]), ("arch_r", self.spec["axles"][0])):
            rv = self.rust[p]
            for i, (fx, fy, rr, th) in enumerate(_BLOBS[p]):
                if rv / 100 < th * 0.9:
                    continue
                a = math.pi * (0.1 + 0.8 * fx)
                rad = 0.41 + 0.08 * fy
                px, py = P(cx + math.cos(a) * rad, 0.30 + math.sin(a) * rad)
                r = max(1, int(s * 0.03 * rr * (0.6 + rv / 70)))
                pygame.draw.circle(surf, (135, 66, 28) if th < 0.5 else (100, 46, 20), (px, py), r)
                if rv > 80 and th > 0.75:
                    pygame.draw.circle(surf, (15, 10, 8), (px, py), max(1, r // 2))
        self._clear_doors(surf, P, side, texture, [
            [(1.97, 0.34), (1.97, 1.28), (2.45, 1.29), (2.97, 0.9), (3.02, 0.36)]])
        if texture:
            return
        for slot, wx in (("tire_rl", self.spec["axles"][0]), ("tire_fl", self.spec["axles"][1])):
            c = P(wx, 0.29)
            if not self.has(slot):
                pygame.draw.circle(surf, (90, 85, 80), c, int(0.1 * s))
                continue
            r = int(0.29 * s)
            pygame.draw.circle(surf, (28, 28, 28), c, r)
            pygame.draw.circle(surf, (170, 170, 170), c, int(0.18 * s))
            for k in range(6):
                a = k * math.pi / 3
                pygame.draw.line(surf, (110, 110, 110), c, (int(c[0] + math.cos(a) * 0.17 * s), int(c[1] + math.sin(a) * 0.17 * s)), 3)

    def _draw_side_generic(self, surf, ox, oy, s, texture, side):
        """Борт найденной машины по параметрам кузова модели (models.py): краска, окна, хром,
        выцветание, грязь, вмятины, ржавчина, битые стёкла."""
        B = MODELS[self.model]["body"]
        L = self.length
        P = lambda x, y: (int(ox + x * s), int(oy - y * s))
        poly = lambda pts: [P(x, y) for x, y in pts]
        rng = random.Random(self.seed * 7 + (1 if side == "r" else 0))
        paint = self.paint
        dark = tuple(max(0, int(c * 0.72)) for c in paint)
        sill, belt, roof_y = B["sill"], B["belt"], B["roof_y"]
        style = B["style"]
        rb_y = belt if style == "hatch" else B["trunk_y"]
        rgb, rs, re, wb = B["rgb"], B["roof_start"], B["roof_end"], B["ws_base"]
        ar, af = self.spec["axles"]
        wr = self.spec["wheel_r"]
        if not texture:
            pygame.draw.ellipse(surf, (20, 20, 22), (ox - 0.2 * s, oy - 0.08 * s, (L + 0.4) * s, 0.2 * s))
        lower = [(0.02, sill), (0.0, sill + 0.12), (0.0, rb_y - 0.04), (0.10, rb_y), (rgb, rb_y), (wb, belt),
                 (wb + 0.15, B["hood_y"]), (L - 0.15, B["nose_y"] + 0.03), (L, B["nose_y"]), (L, sill + 0.08),
                 (L - 0.25, sill)]
        green = [(rgb, rb_y), (rs, roof_y), (re, roof_y), (wb, belt)]
        pygame.draw.polygon(surf, paint, poly(green))
        pygame.draw.polygon(surf, paint, poly(lower))
        # вырезы арок
        old = surf.get_clip()
        surf.set_clip(pygame.Rect(0, 0, surf.get_width(), P(0, sill)[1]))
        for wx in (ar, af):
            pygame.draw.circle(surf, (0, 0, 0, 0) if texture else (22, 20, 20), P(wx, sill), int((wr + 0.11) * s))
        surf.set_clip(old)
        # окна
        glass_c = self.c("glass")
        gl = (46, 58, 66) if glass_c > 0.2 else (70, 78, 80)
        yb, yt = belt + 0.05, roof_y - 0.06
        rear_x = lambda y: rgb + (y - rb_y) / max(0.01, roof_y - rb_y) * (rs - rgb)
        ws_x = lambda y: wb + (y - belt) / max(0.01, roof_y - belt) * (re - wb)
        bp = B["b_pillar"]
        cpil = 0.08 if style == "hatch" else 0.16
        front_win = [(bp + 0.04, yb), (bp + 0.04, yt), (ws_x(yt) - 0.05, yt), (ws_x(yb) - 0.08, yb)]
        rear_win = [(max(rear_x(yb) + cpil, 0.2), yb), (rear_x(yt) + cpil * 0.7, yt), (bp - 0.04, yt), (bp - 0.04, yb)]
        for w in (front_win, rear_win):
            pygame.draw.polygon(surf, gl, poly(w))
        if B["doors"] == 4:     # форточка за задней дверью
            qx = rear_win[0][0] + 0.28
            pygame.draw.line(surf, dark, P(qx, yb), P(qx, yt), max(2, int(0.04 * s)))
        pygame.draw.line(surf, (40, 40, 40), P(bp, yb - 0.02), P(bp, yt + 0.02), max(2, int(0.06 * s)))
        # битые стёкла
        if glass_c < 0.45:
            for w in (front_win, rear_win):
                if rng.random() < 0.6 * (1 - glass_c):
                    cx = sum(p_[0] for p_ in w) / 4
                    cy = sum(p_[1] for p_ in w) / 4
                    for k in range(6):
                        a = rng.uniform(0, math.tau)
                        ln = rng.uniform(0.08, 0.25)
                        pygame.draw.line(surf, (190, 195, 195), P(cx, cy), P(cx + math.cos(a) * ln, cy + math.sin(a) * ln * 0.7), 1)
        # двери, ручки, молдинг
        dl = dark
        doors = [(bp - 0.02, wb - 0.08)] if B["doors"] == 2 else [(bp - 0.02, wb - 0.08), (rear_win[0][0] + 0.28, bp - 0.02)]
        for x0, x1 in doors:
            for x in (x0, x1):
                pygame.draw.line(surf, dl, P(x, sill + 0.03), P(x, belt), 2)
            pygame.draw.rect(surf, (185, 185, 180), (*P(x0 + 0.08, belt - 0.07), int(0.15 * s), max(3, int(0.03 * s))))
        chrome = (185, 185, 180) if B["bumper"] != "black" else (30, 30, 30)
        pygame.draw.line(surf, chrome, P(0.08, sill + (belt - sill) * 0.55), P(L - 0.08, sill + (belt - sill) * 0.55),
                         max(2, int(0.025 * s)))
        # бамперы, фонари, поворотники
        by0 = sill + 0.07
        bh = 0.12
        bcol = (30, 30, 30) if B["bumper"] == "black" else (185, 185, 180)
        pygame.draw.rect(surf, bcol, (*P(L - 0.06, by0 + bh), int(0.16 * s), int(bh * s)))
        pygame.draw.rect(surf, bcol, (*P(-0.10, by0 + bh), int(0.16 * s), int(bh * s)))
        if B["bumper"] == "chrome_rubber":
            pygame.draw.line(surf, (25, 25, 25), P(L - 0.06, by0 + bh / 2), P(L + 0.1, by0 + bh / 2), max(2, int(0.03 * s)))
            pygame.draw.line(surf, (25, 25, 25), P(-0.10, by0 + bh / 2), P(0.06, by0 + bh / 2), max(2, int(0.03 * s)))
        pygame.draw.rect(surf, (230, 140, 30), (*P(L - 0.12, B["nose_y"] - 0.06), int(0.1 * s), int(0.05 * s)))
        tail_h = 0.22 if B["tail"] in ("small_vertical", "vertical_rect") else 0.12
        pygame.draw.rect(surf, (160, 25, 25), (*P(0.0, rb_y - 0.05), int(0.07 * s), int(tail_h * s)))
        if side == "r":           # лючок бака
            pygame.draw.circle(surf, dark, P(0.45, belt - 0.12), max(2, int(0.06 * s)), 2)
        if self.has("exhaust"):
            ex = (100, 95, 90) if self.c("exhaust") > 0.4 else (110, 60, 30)
            pygame.draw.rect(surf, ex, (*P(-0.12, sill - 0.04), int(0.8 * s), int(0.06 * s)))
        # вмятины
        for (dx, dy, dr, dside) in self.dents:
            if dside != side:
                continue
            c = P(dx, sill + dy * (belt - sill) + 0.05)
            r = int(dr * s)
            pygame.draw.ellipse(surf, dark, (c[0] - r, c[1] - r // 2, 2 * r, r))
            pygame.draw.arc(surf, tuple(min(255, v + 30) for v in paint), (c[0] - r, c[1] - r // 2, 2 * r, r), 0.3, 2.6, 2)
        # выцветание: пятна окисленной краски
        layer = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        for _ in range(int(self.fade * 40)):
            x = rng.uniform(0.2, L - 0.2)
            y = rng.uniform(belt - 0.1, roof_y - 0.1) if rng.random() < 0.5 else rng.uniform(sill + 0.2, belt)
            r = int(rng.uniform(0.05, 0.18) * s)
            pygame.draw.circle(layer, (235, 230, 220, int(40 + 50 * self.fade)), P(x, y), r)
        # грязь снизу и брызги у колёс
        dirt_h = 0.15 + 0.35 * self.dirt
        steps = 12
        for k in range(steps):
            y0 = sill + dirt_h * k / steps
            a = int(115 * self.dirt * (1 - k / steps))
            pygame.draw.rect(layer, (95, 75, 50, a), (*P(-0.1, y0 + dirt_h / steps), int((L + 0.2) * s), int(dirt_h / steps * s) + 1))
        for wx in (ar, af):
            for _ in range(int(12 * self.dirt)):
                a = rng.uniform(0.2, math.pi - 0.2)
                rr = wr + 0.12 + rng.uniform(0, 0.12)
                pygame.draw.circle(layer, (80, 62, 40, int(110 * self.dirt)), P(wx + math.cos(a) * rr, sill + math.sin(a) * rr * 0.8),
                                   max(1, int(rng.uniform(0.01, 0.03) * s)))
        # слой пятен и грязи — только в пределах кузова (без неба и вырезов арок)
        sil = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        pygame.draw.polygon(sil, (255, 255, 255, 255), poly(green))
        pygame.draw.polygon(sil, (255, 255, 255, 255), poly(lower))
        sil.set_clip(pygame.Rect(0, 0, surf.get_width(), P(0, sill)[1]))
        for wx in (ar, af):
            pygame.draw.circle(sil, (0, 0, 0, 0), P(wx, sill), int((wr + 0.11) * s))
        sil.set_clip(None)
        layer.blit(sil, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        surf.blit(layer, (0, 0))
        # ржавчина по панелям
        mid_f = af + wr + 0.1
        self._rust_blob(surf, P, "sill_" + side, [(ar + wr + 0.15, af - wr - 0.15, sill, sill + 0.1)], s * 0.035)
        self._rust_blob(surf, P, "doors", [(doors[-1][0], wb - 0.1, sill + 0.08, sill + 0.24)], s * 0.03)
        self._rust_blob(surf, P, "fender", [(mid_f, L - 0.1, sill + 0.14, B["nose_y"] - 0.05),
                                            (0.1, max(0.15, ar - wr - 0.12), sill + 0.14, rb_y - 0.06)], s * 0.03)
        self._rust_blob(surf, P, "tailgate", [(0.0, 0.16, sill + 0.2, rb_y - 0.02)], s * 0.025)
        for pn, cx in (("arch_f", af), ("arch_r", ar)):
            rv = self.rust[pn]
            for i, (fx, fy, rr, th) in enumerate(_BLOBS[pn]):
                if rv / 100 < th * 0.9:
                    continue
                a = math.pi * (0.1 + 0.8 * fx)
                rad = wr + 0.12 + 0.08 * fy
                px, py = P(cx + math.cos(a) * rad, sill + math.sin(a) * rad)
                r = max(1, int(s * 0.03 * rr * (0.6 + rv / 70)))
                pygame.draw.circle(surf, (135, 66, 28) if th < 0.5 else (100, 46, 20), (px, py), r)
                if rv > 80 and th > 0.75:
                    pygame.draw.circle(surf, (15, 10, 8), (px, py), max(1, r // 2))
        door_polys = [[(bp - 0.02, sill + 0.03), (bp - 0.02, yt + 0.02), (ws_x(yt) - 0.03, yt + 0.02),
                       (wb - 0.08, belt), (wb - 0.08, sill + 0.03)]]
        if B["doors"] == 4:
            rx0 = rear_win[0][0] + 0.28
            door_polys.append([(rx0, sill + 0.03), (rx0, yt + 0.02), (bp - 0.02, yt + 0.02), (bp - 0.02, sill + 0.03)])
        self._clear_doors(surf, P, side, texture, door_polys)
        if texture:
            return
        for slot, wx in (("tire_rl" if side == "l" else "tire_rr", ar), ("tire_fl" if side == "l" else "tire_fr", af)):
            c = P(wx, wr)
            if not self.has(slot):
                pygame.draw.circle(surf, (90, 85, 80), c, int(0.1 * s))
                continue
            flat = self.c(slot) < 0.05
            r = int(wr * s)
            cy = c[1] + (int(0.05 * s) if flat else 0)
            pygame.draw.circle(surf, (28, 28, 28), (c[0], cy), r)
            pygame.draw.circle(surf, (120, 116, 108), (c[0], cy), int(wr * 0.6 * s))
            pygame.draw.circle(surf, (190, 188, 180), (c[0], cy), int(wr * 0.25 * s))

    def _draw_side_vaz(self, surf, ox, oy, s, texture=False, side="l"):
        P = lambda x, y: (int(ox + x * s), int(oy - y * s))
        paint_ = self.paint if self.color else PAINT
        poly = lambda pts: [P(x, y) for x, y in pts]

        # тень на полу
        if not texture:
            pygame.draw.ellipse(surf, (20, 20, 22), (ox - 0.2 * s, oy - 0.08 * s, 4.4 * s, 0.2 * s))
        # колёсные арки (тёмные)
        body = [(0.02, 0.30), (0.0, 0.45), (0.0, 0.86), (0.3, 0.88), (2.95, 0.88),
                (3.9, 0.84), (4.0, 0.78), (4.02, 0.55), (4.0, 0.33), (3.62, 0.30)]
        green = [(0.06, 0.86), (0.12, 1.38), (0.22, 1.44), (2.35, 1.44), (2.52, 1.40), (3.0, 0.88)]
        pygame.draw.polygon(surf, paint_, poly(green))
        pygame.draw.polygon(surf, paint_, poly(body))
        # вырезы колёсных арок (только выше линии порога)
        old_clip = surf.get_clip()
        surf.set_clip(pygame.Rect(0, 0, surf.get_width(), P(0, 0.30)[1]))
        for wx in (0.83, 3.25):
            pygame.draw.circle(surf, (0, 0, 0, 0) if texture else (22, 20, 20), P(wx, 0.30), int(0.39 * s))
        surf.set_clip(old_clip)
        if side == "l" and self.odd_door:
            # другая дверь (с разборки)
            pygame.draw.polygon(surf, PAINT_DOOR, poly([(1.87, 0.34), (1.87, 0.88), (2.93, 0.88), (2.93, 0.36)]))
            pygame.draw.polygon(surf, PAINT_DOOR, poly([(1.87, 0.88), (1.87, 1.36), (2.36, 1.36), (2.9, 0.9)]))
            # пятна грунта
            pygame.draw.ellipse(surf, PRIMER, (*P(3.35, 0.78), int(0.4 * s), int(0.22 * s)))
            pygame.draw.ellipse(surf, PRIMER, (*P(0.2, 0.62), int(0.3 * s), int(0.18 * s)))
        else:
            pygame.draw.ellipse(surf, PRIMER, (*P(1.1, 0.66), int(0.7 * s), int(0.25 * s)))
            pygame.draw.ellipse(surf, PRIMER, (*P(3.5, 0.74), int(0.3 * s), int(0.2 * s)))
        # стёкла
        glass = (48, 66, 78)
        pygame.draw.polygon(surf, glass, poly([(0.2, 0.94), (0.24, 1.34), (0.95, 1.34), (0.95, 0.94)]))
        pygame.draw.polygon(surf, glass, poly([(1.03, 0.94), (1.03, 1.34), (1.80, 1.34), (1.80, 0.94)]))
        pygame.draw.polygon(surf, glass, poly([(1.93, 0.94), (1.93, 1.33), (2.35, 1.33), (2.8, 0.94)]))
        pygame.draw.line(surf, (90, 110, 120), P(1.1, 1.3), P(1.3, 1.0), 2)
        # линии дверей
        dl = (70, 64, 50)
        for x in (1.0, 1.86, 2.93):
            pygame.draw.line(surf, dl, P(x, 0.34), P(x, 1.36 if x < 2.9 else 0.9), 2)
        pygame.draw.line(surf, dl, P(0.12, 0.5), P(0.12, 1.36), 2)  # дверь багажника
        # молдинг
        pygame.draw.line(surf, (175, 172, 165), P(0.05, 0.72), P(3.95, 0.70), 3)
        # ручки
        for x in (1.1, 1.95):
            pygame.draw.rect(surf, (175, 172, 165), (*P(x, 0.80), int(0.18 * s), max(3, int(0.04 * s))))
        # багажник на крыше
        pygame.draw.line(surf, (60, 55, 50), P(0.3, 1.52), P(2.2, 1.52), max(2, int(0.04 * s)))
        for x in (0.4, 1.2, 2.1):
            pygame.draw.line(surf, (60, 55, 50), P(x, 1.44), P(x, 1.52), 3)
        # бамперы (хром с ржавчиной)
        pygame.draw.rect(surf, (178, 176, 170), (*P(3.94, 0.49), int(0.18 * s), int(0.11 * s)))
        pygame.draw.rect(surf, (178, 176, 170), (*P(-0.1, 0.51), int(0.18 * s), int(0.11 * s)))
        pygame.draw.circle(surf, RUST_C, P(4.05, 0.43), max(2, int(0.03 * s)))
        pygame.draw.circle(surf, RUST_C, P(-0.03, 0.45), max(2, int(0.035 * s)))
        # фара, поворотник, фонарь
        pygame.draw.ellipse(surf, (210, 210, 190) if self.has("lights") else (30, 30, 30),
                            (*P(3.98, 0.72), int(0.06 * s), int(0.16 * s)))
        pygame.draw.rect(surf, (230, 140, 30), (*P(3.9, 0.34), int(0.12 * s), int(0.05 * s)))
        pygame.draw.rect(surf, (170, 30, 30), (*P(0.0, 0.82), int(0.05 * s), int(0.22 * s)))
        # глушитель
        if self.has("exhaust"):
            ex = (100, 95, 90) if self.c("exhaust") > 0.4 else (110, 60, 30)
            pygame.draw.rect(surf, ex, (*P(-0.12, 0.26), int(0.9 * s), int(0.07 * s)))

        # ржавчина
        tf = lambda x, y: P(x, y)
        self._draw_blobs(surf, "sill_" + side, [(1.1, 2.85, 0.30, 0.40)], tf, s * 0.035)
        self._draw_blobs(surf, "doors", [(1.02, 2.9, 0.38, 0.52)], tf, s * 0.03)
        self._draw_blobs(surf, "fender", [(3.35, 3.95, 0.45, 0.8), (0.05, 0.45, 0.48, 0.8)], tf, s * 0.03)
        self._draw_blobs(surf, "tailgate", [(0.0, 0.14, 0.5, 1.3)], tf, s * 0.025)
        for p, cx in (("arch_f", 3.25), ("arch_r", 0.83)):
            rv = self.rust[p]
            for i, (fx, fy, rr, th) in enumerate(_BLOBS[p]):
                if rv / 100 < th * 0.9:
                    continue
                a = math.pi * (0.1 + 0.8 * fx)
                rad = 0.40 + 0.08 * fy
                px, py = P(cx + math.cos(a) * rad, 0.30 + math.sin(a) * rad)
                r = max(1, int(s * 0.03 * rr * (0.6 + rv / 70)))
                pygame.draw.circle(surf, (135, 66, 28) if th < 0.5 else (100, 46, 20), (px, py), r)
                if rv > 80 and th > 0.75:
                    pygame.draw.circle(surf, (15, 10, 8), (px, py), max(1, r // 2))
        # днище — рыжие подтёки
        fr = self.rust["floor"]
        rr = random.Random(7)
        for i in range(int(fr / 4)):
            x = 0.4 + rr.random() * 3.0
            pygame.draw.line(surf, (120, 58, 24), P(x, 0.30), P(x, 0.30 - 0.03 - rr.random() * 0.04), 2)

        self._clear_doors(surf, P, side, texture, [
            [(1.87, 0.34), (1.87, 1.36), (2.36, 1.36), (2.9, 0.9), (2.93, 0.36)],
            [(1.0, 0.34), (1.0, 1.34), (1.80, 1.34), (1.84, 0.34)]])
        if texture:
            return
        # колёса
        for slot, wx in (("tire_rl", 0.83), ("tire_fl", 3.25)):
            c = P(wx, 0.29)
            if not self.has(slot):
                # машина на кирпичах
                for k in range(3):
                    pygame.draw.rect(surf, (150, 70, 50), (c[0] - int(0.15 * s), P(0, 0.08 * (k + 1))[1],
                                                           int(0.3 * s), int(0.075 * s)))
                    pygame.draw.rect(surf, (90, 40, 30), (c[0] - int(0.15 * s), P(0, 0.08 * (k + 1))[1],
                                                          int(0.3 * s), int(0.075 * s)), 1)
                pygame.draw.circle(surf, (90, 85, 80), P(wx, 0.29), int(0.1 * s))
                continue
            flat = self.c(slot) < 0.05
            r = int(0.29 * s)
            if flat:
                pygame.draw.ellipse(surf, (28, 28, 28), (c[0] - r - 3, c[1] - r + int(0.06 * s), 2 * r + 6, 2 * r - int(0.06 * s)))
            else:
                pygame.draw.circle(surf, (28, 28, 28), c, r)
            cy = c[1] + (int(0.05 * s) if flat else 0)
            pygame.draw.circle(surf, (112, 104, 92), (c[0], cy), int(0.18 * s))
            pygame.draw.circle(surf, (130, 70, 35), (c[0], cy), int(0.18 * s), max(1, int(0.02 * s)))
            pygame.draw.circle(surf, (190, 188, 180), (c[0], cy), int(0.07 * s))
            for k in range(4):
                a = k * math.pi / 2 + 0.4
                pygame.draw.circle(surf, (70, 66, 60), (int(c[0] + math.cos(a) * 0.12 * s), int(cy + math.sin(a) * 0.12 * s)), 2)


RUST_C = (130, 62, 28)
