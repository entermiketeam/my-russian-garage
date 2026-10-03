"""Крепёж: болты и гайки у каждой детали.

car.bolts = {ключ детали: сколько крепежа затянуто}. Ключ — слот ("tire_fl", "battery", "hood"...) или
внутренняя деталь двигателя ("eng:head"). Нет ключа — всё затянуто (по умолчанию так стоит любая деталь).
  * снять деталь можно, только открутив весь её крепёж (в мире — по одному болту, E; в меню — «открутить всё»);
  * поставленная в мире деталь сначала «наживлена» (0 затянуто) — её надо закрутить;
  * недокрученная деталь работает плохо: колесо может отвалиться, ГБЦ прогорит, поддон течёт...
Это та же система, что и меню ремонта двигателя/кузова: engine.py и CarWork учитывают крепёж.
"""
import random

# ключ: (сколько, что это, минут на одну штуку)
SLOT_BOLTS = {
    "tire": (4, "гайка колеса", 1.5),
    "battery": (3, "гайка клеммы / прижима", 1.0),
    "hood": (4, "болт петли капота", 2.0),
    "trunk": (4, "болт петли крышки", 2.0),
    "door_l": (4, "болт петли двери", 3.0),
    "door_r": (4, "болт петли двери", 3.0),
    "seats": (4, "болт салазок", 3.0),
    "alternator": (3, "болт генератора", 4.0),
    "starter": (3, "болт стартера", 6.0),
    "radiator": (4, "болт радиатора", 4.0),
    "carb": (4, "гайка карбюратора", 3.0),
    "air_filter": (1, "гайка-барашек корпуса", 1.0),
    "distributor": (1, "гайка трамблёра", 3.0),
    "fuel_pump": (2, "гайка бензонасоса", 4.0),
    "exhaust": (2, "хомут глушителя", 6.0),
    "lights": (6, "винт фары", 2.0),
    "clutch": (6, "болт корзины сцепления", 5.0),
    "gearbox": (6, "болт КПП к блоку", 8.0),
    "engine": (4, "гайка подушки двигателя", 10.0),
    "shocks": (8, "гайка амортизатора", 5.0),
    "brakes_f": (4, "болт суппорта / барабана", 4.0),
    "brakes_r": (4, "болт суппорта / барабана", 4.0),
    "steering": (4, "гайка рулевой тяги", 6.0),
    "belt": (2, "болт натяжения ремня", 3.0),
}
ENG_BOLTS = {
    "valve_cover": (8, "гайка клапанной крышки", 1.0),
    "fuel_rail": (4, "болт топливной рампы", 3.0),
    "intake": (6, "гайка впускного коллектора", 3.0),
    "exhaust_mf": (6, "гайка выпускного коллектора", 4.0),
    "crank_pulley": (1, "болт шкива коленвала", 10.0),
    "water_pump": (4, "болт помпы", 4.0),
    "thermostat": (2, "болт крышки термостата", 3.0),
    "timing_cover": (7, "болт крышки ГРМ", 2.0),
    "timing": (1, "болт звёздочки распредвала", 5.0),
    "tensioner": (2, "болт натяжителя", 4.0),
    "camshaft": (10, "гайка постели распредвала", 2.0),
    "head": (10, "болт ГБЦ", 4.0),
    "oil_pan": (16, "болт поддона", 1.0),
    "oil_pump": (3, "болт масляного насоса", 3.0),
    "conrods": (8, "гайка крышки шатуна", 3.0),
    "crankshaft": (10, "болт крышки коренной опоры", 4.0),
}
# сколько гаек на колесе у разных машин
LUGS = {"w123": 5, "volvo240": 5, "bmw_e21": 4, "mustang": 5, "trabant": 4, "wartburg": 4}


def spec(car, key):
    """(сколько, название, минут) для детали машины или None, если крепежа нет (стекло, вкладыши...)."""
    if key.startswith("eng:"):
        k = key[4:]
        base = ENG_BOLTS.get(k)
        if base and k in ("head", "crankshaft", "conrods", "camshaft", "valve_cover", "oil_pan"):
            try:
                import engine
                cyl = engine.layout(car.model)["cyl"]
                n = {"head": cyl * 2 + 2, "crankshaft": (cyl + 1) * 2, "conrods": cyl * 2,
                     "camshaft": (cyl + 1) * 2, "valve_cover": 6 + cyl // 2, "oil_pan": 10 + cyl * 2}[k]
                base = (n, base[1], base[2])
            except Exception:
                pass
        return base
    if key.startswith("tire_"):
        n, name, m = SLOT_BOLTS["tire"]
        return (LUGS.get(car.model, n), name, m)
    return SLOT_BOLTS.get(key)


def _installed(car, key):
    if key.startswith("eng:"):
        return bool(car.eng) and car.eng.get(key[4:]) is not None and car.parts.get("engine") is not None
    return car.parts.get(key) is not None


def total(car, key):
    s = spec(car, key)
    return s[0] if s else 0


def states(car, key):
    """Список по болтам: 1 — затянут, 0 — отпущен (наживлен). Нет записи — всё затянуто."""
    n = total(car, key)
    if not n or not _installed(car, key):
        return []
    v = car.bolts.get(key)
    if isinstance(v, int):                     # старый формат (число затянутых)
        v = [1] * min(n, v) + [0] * max(0, n - v)
    if not isinstance(v, list):
        return [1] * n
    v = (list(v) + [1] * n)[:n]
    return v


def _store(car, key, st):
    if all(st):
        car.bolts.pop(key, None)
        if key == "eng:head" and getattr(car, "eng_flags", None) is not None:
            car.eng_flags.pop("head_loose", None)      # затянули по-человечески
    else:
        car.bolts[key] = st


def tight(car, key):
    """Сколько крепежа затянуто сейчас."""
    return sum(states(car, key))


def loose(car, key):
    return total(car, key) - tight(car, key) if _installed(car, key) else 0


def fully(car, key):
    return loose(car, key) == 0


def unscrew(car, key, index=None, count=1):
    """Отпустить болт (конкретный или первый попавшийся затянутый)."""
    st = states(car, key)
    idx = [index] if index is not None else [i for i, v in enumerate(st) if v][:count]
    for i in idx:
        if 0 <= i < len(st):
            st[i] = 0
    _store(car, key, st)
    return sum(st)


def screw(car, key, index=None, count=1):
    st = states(car, key)
    idx = [index] if index is not None else [i for i, v in enumerate(st) if not v][:count]
    for i in idx:
        if 0 <= i < len(st):
            st[i] = 1
    _store(car, key, st)
    return sum(st)


def on_removed(car, key):
    car.bolts.pop(key, None)


def on_placed(car, key, tightened=True):
    """Деталь поставили: из меню — сразу закрутили, руками в мире — наживили (всё отпущено)."""
    n = total(car, key)
    if key.startswith("tire_"):
        import tires
        tires.set_nominal(car, key)                   # колесо ставят накачанным до нормы
    if tightened or not n:
        car.bolts.pop(key, None)
    else:
        car.bolts[key] = [0] * n


def minutes_each(car, key):
    s = spec(car, key)
    return s[2] if s else 0


def fix(car):
    if not isinstance(getattr(car, "bolts", None), dict):
        car.bolts = {}


def describe(car, key):
    s = spec(car, key)
    if not s:
        return "Крепежа нет (снимается руками/стоит на месте)."
    t = tight(car, key)
    return f"Крепёж: {s[1]} — затянуто {t} из {s[0]}."


# --------------------------------------------------------------------------- что делает недокрученная деталь
def running_effects(car, dt):
    """Каждый кадр движения/работы. Возвращает множитель мощности."""
    if not car.bolts:
        return 1.0
    power = 1.0
    spd = abs(car.speed)
    for key in list(car.bolts):
        n = total(car, key)
        if not n or not _installed(car, key):
            car.bolts.pop(key, None)
            continue
        t = tight(car, key)
        frac = t / n
        if frac >= 1:
            continue
        if key.startswith("tire_"):
            # болтается колесо: бьёт в руль, гайки откручиваются сами, потом колесо уходит
            if spd > 3:
                car._bolt_shake = max(getattr(car, "_bolt_shake", 0.0), 0.7 * (1 - frac))
                if random.random() < (1 - frac) * 0.5 * dt:
                    car.say("Колесо болтается — не затянуты гайки!")
                if t > 0 and random.random() < (1 - frac) * spd * 0.004 * dt:
                    unscrew(car, key)                      # гайки сами откручиваются от вибрации
                if t <= n // 2 and random.random() < (1 - frac) * spd * 0.003 * dt:
                    part = car.parts.get(key)
                    car.parts[key] = None
                    car.bolts.pop(key, None)
                    car.lost_wheels = getattr(car, "lost_wheels", []) + [part]
                    car.say("Колесо отвалилось! Гайки не были затянуты.")
                    car.sounds.append("crash")
        elif key == "eng:head":
            car.eng_flags["head_loose"] = True
        elif key == "eng:oil_pan":
            car.oil = max(0.0, car.oil - (1 - frac) * 0.03 * dt)
            if random.random() < 0.3 * dt:
                car.say("Масло капает из-под поддона — болты не затянуты.")
        elif key == "eng:valve_cover":
            car.oil = max(0.0, car.oil - (1 - frac) * 0.004 * dt)
        elif key in ("eng:exhaust_mf", "exhaust"):
            power *= 1 - 0.08 * (1 - frac)
            if random.random() < 0.3 * dt:
                car.say("Выхлоп пропускает — не затянут крепёж.")
        elif key == "eng:intake":
            power *= 1 - 0.25 * (1 - frac)
            if random.random() < (1 - frac) * 0.8 * dt:
                car.misfire = 0.12
        elif key in ("eng:water_pump", "eng:thermostat", "radiator"):
            if car.coolant_cap > 0:
                car.coolant = max(0.0, car.coolant - (1 - frac) * 0.01 * dt)
        elif key == "battery":
            if random.random() < (1 - frac) * 0.3 * dt and car.running and not car.has("alternator"):
                car.engine_off("Клемма аккумулятора болтается — пропало питание.")
        elif key == "alternator":
            if random.random() < 0.2 * dt:
                car.say("Генератор болтается — ремень проскальзывает, зарядки нет.")
        elif key in ("eng:crank_pulley", "eng:timing", "eng:tensioner", "eng:camshaft", "eng:conrods", "eng:crankshaft"):
            # самое опасное: разболтанный шатун/коленвал/ГРМ — мотору конец
            if car.running and random.random() < (1 - frac) * 0.6 * dt:
                car.say("Страшный стук в двигателе — внутри не затянут крепёж!")
                car.wear("engine", 3.0 * (1 - frac))
        else:
            if spd > 5 and random.random() < 0.15 * dt:
                car.say("Что-то гремит — не до конца закручен крепёж.")
    return power
