"""Шины: протектор, давление, сцепление, износ, повреждения — у каждой шины своё.

Состояние шины (часть «tire_*», cond 0..100) — это протектор: 100% = 8 мм нового, 20% = 1,6 мм (минимум по закону).
Давление — car.tire_p[слот] в барах «на холодную при +20°C»; реальное давление зависит от температуры воздуха
(зимой каждые −10°C — примерно −0,07 бар), шина медленно травит, повреждённая — быстро.

Как это влияет на машину (car.update → _chassis): у каждой оси своё сцепление = среднее двух её шин.
Сцепление шины = покрытие × протектор (на сухом почти не важен, на мокром/снегу/льду — очень) × давление
(недокачанная «плывёт» и держит хуже, перекачанная — маленькое пятно) × повреждения. Разница левых и правых шин
тянет машину в сторону. Мягкая (недокачанная) шина медленнее реагирует на руль. Лысая шина на мокром выше
скорости аквапланирования теряет сцепление. Тормоза упираются в сцепление шин: изношенные — длиннее тормозной путь,
при превышении — колёса блокируются (ABS в 1998-м на этих машинах нет) и машина не рулится.
Износ: пробег × скорость, пробуксовка, скольжение в заносе, блокировка при торможении, боковые перегрузки,
давление (мало — изнашиваются края, много — центр), грунт. Критически лысая шина при скорости и нагреве может лопнуть.
"""
import math
import random

NEW_MM = 8.0
LEGAL_MM = 1.6
# давление по заводу (перёд, зад), бар
NOMINAL = {"vaz2102": (1.6, 2.0), "ae86": (1.9, 1.9), "trabant": (1.6, 1.8), "wartburg": (1.7, 1.9),
           "moskvich": (1.7, 1.9), "kadett": (1.8, 1.9), "golf": (1.8, 1.8), "taunus": (1.8, 2.0),
           "w123": (1.8, 2.1), "volvo240": (1.9, 2.1), "bmw_e21": (1.9, 2.1), "audi80": (1.8, 1.8),
           "civic": (1.9, 1.9), "mustang": (1.9, 1.9)}
SLOT_RU = {"tire_fl": "переднее левое", "tire_fr": "переднее правое", "tire_rl": "заднее левое", "tire_rr": "заднее правое"}
FLAT_BAR = 0.4


def nominal(car, slot):
    f, r = NOMINAL.get(car.model, (1.9, 2.0))
    return f if slot in ("tire_fl", "tire_fr") else r


def ensure(car):
    tp = getattr(car, "tire_p", None)
    if not isinstance(tp, dict):
        tp = {}
        rng = random.Random(car.seed * 3 + 11)
        for s in car.tire_list():
            n = nominal(car, s)
            tp[s] = round(n * rng.uniform(0.72, 1.02), 2)      # у старых машин шины обычно подспущены
        car.tire_p = tp
    for s in car.tire_list():
        if s not in tp:                                          # (не считать норму каждый раз — это горячий путь физики)
            tp[s] = nominal(car, s)
    return tp


def tread_mm(car, slot):
    return NEW_MM * car.c(slot)


def pressure(car, slot, ambient=20.0):
    """Давление сейчас, с учётом температуры воздуха."""
    p20 = ensure(car)[slot]
    return max(0.0, (p20 + 1.013) * (273 + ambient) / 293 - 1.013)


def is_flat(car, slot):
    return car.has(slot) and (car.c(slot) < 0.05 or ensure(car)[slot] < FLAT_BAR)


def set_nominal(car, slot):
    ensure(car)[slot] = nominal(car, slot)


def surface_at(world, x, y):
    """Покрытие под машиной: асфальт (дороги, дворы, подземка), гравий (свалка, заброшенные парковки), трава."""
    from places import INTERIOR_X
    from world import JUNKYARD, point_in
    if x >= INTERIOR_X or world.road_at(x, y):
        return "asphalt"
    if point_in(JUNKYARD, x, y) or world.places.parking_at(x, y):
        return "gravel"
    for r in getattr(world, "paved", ()):
        if point_in(r, x, y):
            return "asphalt"
    from world import GARAGE, PUMP_ZONE, TUV_YARD, AUTOHAUS_LOT, SCRAP_DROP, PARKING2
    from places import DEALER_LOT
    for r in (GARAGE, PUMP_ZONE, TUV_YARD, AUTOHAUS_LOT, SCRAP_DROP, PARKING2, DEALER_LOT):
        if point_in(r, x, y):
            return "asphalt"
    for c in world.crossings:
        if point_in(c, x, y):
            return "asphalt"
    return "grass"


# ------------------------------------------------------------------ сцепление
def tire_mu(car, slot, wet, snow, speed, ambient=20.0):
    """Множитель сцепления одной шины (новая, правильно накачанная, сухой асфальт = 1.0)."""
    if not car.has(slot):
        return 0.25                                    # на тормозном барабане
    t = min(1.0, car.c(slot) / 0.8)                    # 0..1 «сколько протектора» (80%+ = как новая)
    mu = 0.88 + 0.12 * t                               # на сухом лысая почти не хуже
    if wet:
        mu *= 0.8 * (0.55 + 0.45 * t ** 0.7)           # вода уходит через канавки — нет канавок, нет сцепления
        v_aq = 17.0 + 16.0 * t                         # аквапланирование: лысая — уже с ~60 км/ч
        if speed > v_aq:
            mu *= max(0.35, 1.0 - (speed - v_aq) * 0.05)
    if snow > 0:
        mu *= 1.0 - min(1.0, snow * 1.6) * 0.6 * (1.0 - t)   # снег/лёд (поверх зимней физики): лысая — как коньки
    p = pressure(car, slot, ambient)
    n = nominal(car, slot)
    if p < FLAT_BAR:
        mu *= 0.35                                     # спущенная — едет на ободе
    else:
        dev = (p - n) / n
        mu *= 1.0 - (0.45 * -dev if dev < 0 else 0.25 * dev) if abs(dev) > 0.05 else 1.0
        if wet and dev > 0.1:
            mu *= 1.0 - 0.3 * (dev - 0.1)              # перекачанная: узкое пятно, на мокром ещё хуже
    if car.c(slot) < 0.05:
        mu *= 0.5                                      # разорванная шина
    return max(0.12, mu)


def stiffness(car, slot, ambient=20.0):
    """Жёсткость боковины: мягкая (недокачанная) шина медленнее отвечает на руль, перекачанная — резче."""
    if not car.has(slot):
        return 0.5
    r = pressure(car, slot, ambient) / nominal(car, slot)
    return max(0.45, min(1.25, 0.55 + 0.45 * r if r < 1 else 1.0 + 0.25 * (r - 1)))


def axle_grip(car, wet, snow, speed, ambient=20.0):
    """(сцепление передней оси, задней, жёсткость перед/зад, увод влево-вправо)."""
    m = {s: tire_mu(car, s, wet, snow, speed, ambient) for s in car.tire_list()}
    k = {s: stiffness(car, s, ambient) for s in car.tire_list()}
    gf = (m["tire_fl"] + m["tire_fr"]) / 2
    gr = (m["tire_rl"] + m["tire_rr"]) / 2
    # разница левых и правых: машину тянет в сторону более слабой (спущенной, лысой) шины
    def dz(x):                                         # мелкие различия (±10% давления) в жизни не чувствуются
        return math.copysign(max(0.0, abs(x) - 0.06), x)
    pull = (dz(m["tire_fr"] - m["tire_fl"]) * 1.0 + dz(m["tire_rr"] - m["tire_rl"]) * 0.4) * 0.03
    return gf, gr, (k["tire_fl"] + k["tire_fr"]) / 2, (k["tire_rl"] + k["tire_rr"]) / 2, pull


# ------------------------------------------------------------------ износ и повреждения
def wear_step(car, dt, info):
    """info: speed, lat_acc, spin (пробуксовка ведущих), skid (скольжение в заносе), lock (блокировка), surface,
    throttle, drive ("rwd"/"fwd"/"awd"), steer."""
    spd = info["speed"]
    if spd < 0.2 and info["spin"] < 0.5:
        return
    km = spd * dt / 1000.0
    rough = {"asphalt": 1.0, "gravel": 2.2, "grass": 1.3, "snow": 0.6}.get(info["surface"], 1.0)
    base = 0.016 * km * (1 + (spd / 30) ** 2) * rough      # ~6000 км спокойной езды на комплект
    lat = min(3.0, abs(info["lat_acc"]) / 9.81)
    drive = info["drive"]
    for s in car.tire_list():
        if not car.has(s):
            continue
        front = s in ("tire_fl", "tire_fr")
        driven = drive == "awd" or (drive == "fwd") == front
        w = base * (1 + 1.5 * lat * lat * (1.3 if front else 1.0))
        if driven:
            w += 0.06 * info["spin"] * dt                    # пробуксовка «жжёт» резину
        w += 0.05 * info["skid"] * dt                        # скольжение боком
        if info["lock"] and front:
            w += 0.35 * dt                                   # заблокированное колесо — «лыска»
        if info["lock_r"] and not front:
            w += 0.3 * dt
        r = pressure(car, s) / nominal(car, s)
        if r < 0.85:
            w *= 1 + (0.85 - r) * 3                          # недокачанная: края, перегрев
        elif r > 1.15:
            w *= 1 + (r - 1.15) * 2                          # перекачанная: середина
        align = abs(getattr(car, "align", 0.0))
        if front and align > 0.002:
            w *= 1 + align * 60                              # развал после аварии съедает передние
        car.wear(s, w)
        # критический износ + скорость + перегрев = разрыв
        c = car.c(s)
        heat = (spd / 25) ** 2 * (1.6 if r < 0.7 else 1.0)
        if c < 0.12 and spd > 12 and random.random() < (0.12 - c) * heat * 0.02 * dt:
            blowout(car, s)
        elif r < 0.55 and spd > 20 and random.random() < (0.55 - r) * 0.02 * dt:
            blowout(car, s)                                  # на спущенной быстро — боковина рвётся


def blowout(car, slot):
    ensure(car)[slot] = 0.0
    p = car.parts.get(slot)
    if p:
        p["cond"] = min(p["cond"], 3.0)
    car.say(f"БАХ! Лопнула шина: {SLOT_RU[slot]}. Машину тянет — тормозите плавно.")
    car.sounds.append("crash")


def leak(car, minutes, ambient=20.0):
    """Со временем шины травят: исправная — чуть-чуть, изношенная/повреждённая — заметно."""
    tp = ensure(car)
    for s in car.tire_list():
        if not car.has(s) or tp[s] <= 0:
            continue
        c = car.c(s)
        rate = 0.00012 if c > 0.3 else (0.0006 if c > 0.1 else 0.004)      # бар/минута-ish (в день 0.2..5 бар)
        tp[s] = max(0.0, tp[s] - rate * minutes / 60 * (1 + getattr(car, "_puncture", {}).get(s, 0)))


def on_crash(car, zone, depth):
    """Удар в зоне колёс: боковой порез, погнутый диск — шина травит/лопается."""
    if depth < 0.08:
        return
    sl = {"front": ("tire_fl", "tire_fr"), "rear": ("tire_rl", "tire_rr"), "left": ("tire_fl", "tire_rl"),
          "right": ("tire_fr", "tire_rr")}.get(zone, ())
    tp = ensure(car)
    for s in sl:
        if car.has(s) and random.random() < min(0.8, depth * 2.5):
            car.wear(s, depth * 60)
            tp[s] = max(0.0, tp[s] - random.uniform(0.3, 2.0))
            if tp[s] < FLAT_BAR:
                car.say(f"После удара спустило колесо: {SLOT_RU[s]}.")


# ------------------------------------------------------------------ осмотр
def state_text(car, slot, ambient=20.0):
    if not car.has(slot):
        return "шины нет (машина на тормозном барабане)"
    mm = tread_mm(car, slot)
    p = pressure(car, slot, ambient)
    n = nominal(car, slot)
    bits = []
    if car.c(slot) < 0.05:
        bits.append("РАЗОРВАНА")
    elif mm < LEGAL_MM:
        bits.append("ЛЫСАЯ (меньше 1,6 мм — запрещено)")
    elif mm < 3:
        bits.append("изношена — на мокром и снегу опасна")
    if p < FLAT_BAR:
        bits.append("СПУЩЕНА")
    elif p < n * 0.85:
        bits.append("недокачана")
    elif p > n * 1.15:
        bits.append("перекачана")
    return ", ".join(bits) if bits else "в порядке"
