"""Двигатель «до последнего болтика»: внутренние детали, порядок разборки/сборки, их влияние на работу.

Слот car.parts["engine"] остаётся — это БЛОК ЦИЛИНДРОВ (и сам двигатель как агрегат: его можно снять целиком).
Всё остальное внутри — в car.eng = {ключ: {"id", "cond"} или None}. Навесное (генератор, стартер, свечи,
карбюратор, ремень, радиатор...) — по-прежнему обычные слоты car.parts; они участвуют в порядке разборки.

Для каждой детали:
  blocked — что закрывает к ней доступ (снять сначала, поставить — только когда этого ещё нет);
  needs   — на что она крепится (ставится только после них).
Состояние двигателя для всей физики (car.c("engine")) считается из деталей: компрессия, вкладыши, смазка.
"""
import math
import random

# --------------------------------------------------------------------------- раскладки двигателей
# stroke — такт; vt — газораспределение (ohc / dohc / ohv / None); timing — chain / belt / None;
# belt_slot — слот «belt» и есть ремень ГРМ; fuel — carb / efi / diesel; cooling — water / air; inter — клапанобойный
LAYOUTS = {
    "vaz2102": dict(name="2101", stroke=4, cyl=4, vt="ohc", timing="chain", fuel="carb", cooling="water", inter=False),
    "ae86": dict(name="4A-GE", stroke=4, cyl=4, vt="dohc", timing="belt", belt_slot=True, fuel="efi", cooling="water",
                 inter=True),
    "trabant": dict(name="P60", stroke=2, cyl=2, vt=None, timing=None, fuel="carb", cooling="air"),
    "wartburg": dict(name="353", stroke=2, cyl=3, vt=None, timing=None, fuel="carb", cooling="water"),
    "kadett": dict(name="1.2 OHV", stroke=4, cyl=4, vt="ohv", timing="chain", fuel="carb", cooling="water"),
    "golf": dict(name="EA111", stroke=4, cyl=4, vt="ohc", timing="belt", fuel="carb", cooling="water"),
    "taunus": dict(name="Pinto", stroke=4, cyl=4, vt="ohc", timing="belt", belt_slot=True, fuel="carb",
                   cooling="water"),
    "w123": dict(name="OM615", stroke=4, cyl=4, vt="ohc", timing="chain", fuel="diesel", cooling="water", inter=True),
    "moskvich": dict(name="УЗАМ-412", stroke=4, cyl=4, vt="ohc", timing="chain", fuel="carb", cooling="water"),
    "volvo240": dict(name="B21", stroke=4, cyl=4, vt="ohc", timing="belt", fuel="carb", cooling="water"),
    "bmw_e21": dict(name="M10", stroke=4, cyl=4, vt="ohc", timing="chain", fuel="carb", cooling="water"),
    "audi80": dict(name="1.6", stroke=4, cyl=4, vt="ohc", timing="belt", fuel="carb", cooling="water", inter=True),
    "mustang": dict(name="289 V8", stroke=4, cyl=8, vt="ohv", timing="chain", fuel="carb", cooling="water"),
    "civic": dict(name="EW", stroke=4, cyl=4, vt="ohc", timing="belt", belt_slot=True, fuel="carb", cooling="water",
                  inter=True),
}
PRICE = {"vaz2102": 1.0, "ae86": 1.7}          # множитель цен; у остальных — из models.py


def layout(model):
    return LAYOUTS.get(model, LAYOUTS["vaz2102"])


# ключ: (название, базовая цена DM, минут)
BASE = {
    "oil_filter": ("Масляный фильтр", 9, 10),
    "valve_cover": ("Клапанная крышка с прокладкой", 32, 15),
    "fuel_rail": ("Топливная рампа и регулятор давления", 95, 30),
    "intake": ("Впускной коллектор", 70, 40),
    "exhaust_mf": ("Выпускной коллектор", 60, 40),
    "crank_pulley": ("Шкив коленвала", 22, 15),
    "water_pump": ("Водяной насос (помпа)", 48, 40),
    "thermostat": ("Термостат", 16, 20),
    "timing_cover": ("Крышка привода ГРМ", 28, 30),
    "timing": ("Цепь ГРМ", 40, 60),
    "tensioner": ("Натяжитель и успокоитель цепи", 30, 30),
    "camshaft": ("Распределительный вал", 110, 50),
    "springs": ("Клапанные пружины и сухари", 32, 60),
    "valves": ("Клапаны (комплект)", 75, 60),
    "head": ("Головка блока цилиндров (ГБЦ)", 380, 120),
    "head_gasket": ("Прокладка ГБЦ", 18, 15),
    "oil_pan": ("Масляный поддон с прокладкой", 42, 30),
    "oil_pump": ("Масляный насос", 62, 30),
    "rod_bearings": ("Вкладыши шатунные", 26, 40),
    "conrods": ("Шатуны", 120, 60),
    "pistons": ("Поршни с кольцами", 160, 60),
    "crankshaft": ("Коленчатый вал", 260, 90),
    "main_bearings": ("Вкладыши коренные", 30, 30),
}
ORDER = ["oil_filter", "valve_cover", "fuel_rail", "intake", "exhaust_mf", "crank_pulley", "water_pump", "thermostat",
         "timing_cover", "timing", "tensioner", "camshaft", "springs", "valves", "head", "head_gasket", "oil_pan",
         "oil_pump", "rod_bearings", "conrods", "pistons", "crankshaft", "main_bearings"]
ESSENTIAL = {"head", "head_gasket", "pistons", "conrods", "crankshaft", "camshaft", "valves", "springs", "timing",
             "intake", "fuel_rail"}
# что закрыто чем (для отображения в 3D и осмотра на месте)
COVERED = {"pistons": ("head", "head_gasket"), "head_gasket": ("head",), "camshaft": ("valve_cover",),
           "valves": ("valve_cover", "springs"), "springs": ("valve_cover", "camshaft"),
           "timing": ("timing_cover",), "tensioner": ("timing_cover",), "crankshaft": ("oil_pan",),
           "conrods": ("oil_pan",), "rod_bearings": ("oil_pan",), "main_bearings": ("oil_pan", "crankshaft"),
           "oil_pump": ("oil_pan",)}
# что уезжает вместе с ГБЦ, если снять её в сборе
HEAD_CHILDREN = ("camshaft", "springs", "valves")


_GRAPH = {}


def graph(model):
    if model not in _GRAPH:
        _GRAPH[model] = _graph(model)
    return _GRAPH[model]


def _graph(model):
    """{ключ: dict(name, price, minutes, blocked, needs)} для этого двигателя. Слоты car.parts — с префиксом 'slot:'."""
    L = layout(model)
    two = L["stroke"] == 2
    keys = []
    if two:
        keys = ["intake", "exhaust_mf", "head", "head_gasket", "pistons", "conrods", "crankshaft", "main_bearings"]
        if L["cooling"] == "water":
            keys[2:2] = ["water_pump", "thermostat"]
    else:
        keys = list(ORDER)
        if L["fuel"] not in ("efi", "diesel"):
            keys.remove("fuel_rail")
        if L["cooling"] != "water":
            keys.remove("water_pump")
            keys.remove("thermostat")
        if L.get("belt_slot"):
            keys.remove("timing")               # ремень ГРМ — это существующий слот «belt»
    tkey = "slot:belt" if L.get("belt_slot") else "timing"
    g = {}
    for k in keys:
        name, price, mins = BASE[k]
        blocked, needs = [], []
        if two:
            blocked, needs = {
                "intake": (["slot:carb"], []), "exhaust_mf": (["slot:exhaust"], []),
                "water_pump": (["slot:belt"], []), "thermostat": ([], []),
                "head": (["slot:plugs", "exhaust_mf", "thermostat"] if "thermostat" in keys else ["slot:plugs", "exhaust_mf"],
                         ["head_gasket"]),
                "head_gasket": (["head"], []), "pistons": (["head_gasket"], ["conrods"]),
                "conrods": (["pistons", "slot:gearbox", "slot:clutch"], ["crankshaft"]),
                "crankshaft": (["conrods", "slot:gearbox", "slot:clutch"], ["main_bearings"]),
                "main_bearings": (["crankshaft"], []),
            }[k]
            if k == "conrods":
                name = "Шатуны с игольчатыми подшипниками"
        else:
            cam_in_head = L["vt"] in ("ohc", "dohc")
            fuel_block = {"carb": "slot:carb", "efi": "fuel_rail", "diesel": "slot:air_filter"}[L["fuel"]]
            belt_timing_pump = L["timing"] == "belt"
            table = {
                "oil_filter": ([], []),
                "valve_cover": (["slot:air_filter"], ["head"]),
                "fuel_rail": (["slot:air_filter"], ["intake"]),
                "intake": ([fuel_block], ["head"]),
                "exhaust_mf": (["slot:exhaust"], ["head"]),
                "crank_pulley": ([] if L.get("belt_slot") else ["slot:belt"], ["crankshaft"]),
                "water_pump": ([tkey] if belt_timing_pump else ["slot:belt"], []),
                "thermostat": ([], ["head"]),
                "timing_cover": (["crank_pulley"], []),
                "timing": (["timing_cover"] + (["valve_cover"] if cam_in_head else []), ["camshaft", "crankshaft", "tensioner"]),
                "tensioner": ([tkey], []),
                "camshaft": ((["valve_cover", tkey] if cam_in_head else [tkey]), (["head"] if cam_in_head else [])),
                "springs": ((["camshaft"] if cam_in_head else ["valve_cover"]), ["valves"]),
                "valves": (["springs"], ["head"]),
                "head": ([tkey, "intake", "exhaust_mf", "valve_cover"] + (["thermostat"] if "thermostat" in keys else [])
                         + (["slot:carb"] if L["fuel"] == "diesel" else []), ["head_gasket"]),
                "head_gasket": (["head"], []),
                "oil_pan": ([], []),
                "oil_pump": (["oil_pan"], ["crankshaft"]),
                "rod_bearings": (["oil_pan"], ["conrods"]),
                "conrods": (["oil_pan", "rod_bearings", "head_gasket"], ["pistons", "crankshaft"]),
                "pistons": (["conrods", "head_gasket"], []),
                "crankshaft": (["conrods", "oil_pump", tkey, "crank_pulley", "timing_cover", "slot:gearbox", "slot:clutch"],
                               ["main_bearings"]),
                "main_bearings": (["crankshaft"], []),
            }
            blocked, needs = table[k]
            if k == "timing" and L["timing"] == "belt":
                name, price = "Ремень ГРМ", 25
            if k == "tensioner" and L["timing"] == "belt":
                name = "Натяжной и обводной ролики ГРМ"
            if k == "camshaft" and L["vt"] == "dohc":
                name, price = "Распредвалы (впуск и выпуск)", 190
            if k == "timing_cover" and L["timing"] == "belt":
                name = "Кожух ремня ГРМ"
            if k == "fuel_rail" and L["fuel"] == "diesel":
                name, price = "Трубки высокого давления ТНВД", 60
        g[k] = dict(name=name, price=price, minutes=mins, blocked=list(blocked), needs=list(needs))
    # слоты, которым теперь что-то мешает (ремень ГРМ под кожухом, форсунки под рампой)
    if L.get("belt_slot") and not two:
        g["slot:belt"] = dict(blocked=["timing_cover"], needs=["camshaft", "crankshaft", "tensioner"])
    if L["fuel"] in ("efi", "diesel") and not two:
        g["slot:carb"] = dict(blocked=["fuel_rail"], needs=[])
    return g


def keys(model):
    return [k for k in graph(model) if not k.startswith("slot:")]


def part_id(model, key):
    return f"{model}_eng_{key}"


def items():
    """Каталог внутренних деталей всех двигателей для ITEMS."""
    from models import MODELS
    out = {}
    for model in LAYOUTS:
        L = layout(model)
        pf = PRICE.get(model, MODELS.get(model, {}).get("price", 1.0))
        for k, d in graph(model).items():
            if k.startswith("slot:"):
                continue
            out[part_id(model, k)] = dict(name=f"{d['name']} — {L['name']}", kind="part",
                                          price=float(round(d["price"] * pf)), model=model, eng=k)
    return out


# --------------------------------------------------------------------------- состояние машины
def _slot_has(car, slot):
    return car.parts.get(slot) is not None


def has(car, key):
    if key.startswith("slot:"):
        return _slot_has(car, key[5:])
    return bool(car.eng) and car.eng.get(key) is not None


def cond(car, key):
    if key.startswith("slot:"):
        p = car.parts.get(key[5:])
    else:
        p = car.eng.get(key) if car.eng else None
    return 0.0 if p is None else max(0.0, p["cond"]) / 100.0


def label(car, key):
    if key.startswith("slot:"):
        s = key[5:]
        return car.slots[s][0] if s in car.slots else s
    return graph(car.model)[key]["name"]


def init(car, rng=None, base=None):
    """Внутренности двигателя для машины (новой, найденной или из старого сохранения)."""
    rng = rng or random.Random(car.seed * 31 + 7)
    eng = car.parts.get("engine")
    car.eng = {}
    car.eng_flags = {}
    if eng is None:
        car.eng = {k: None for k in keys(car.model)}
        return
    e = eng["cond"] if base is None else base
    for k in keys(car.model):
        # расходники изношены сильнее, чугун — меньше
        spread = {"head_gasket": 12, "oil_filter": 25, "timing": 15, "tensioner": 15, "rod_bearings": 10,
                  "main_bearings": 8, "crankshaft": 5, "head": 6, "oil_pan": 10, "valve_cover": 10}.get(k, 8)
        bias = {"oil_filter": -20, "timing": -8, "head_gasket": -4, "crankshaft": 8, "head": 6, "oil_pan": 10,
                "valve_cover": 5, "intake": 10, "exhaust_mf": 0, "timing_cover": 12, "crank_pulley": 12}.get(k, 0)
        k_ = max(0.0, min(1.0, (100.0 - e) / 40.0))     # новый мотор — все детали новые, без разброса
        c = e + (bias + rng.gauss(0, spread)) * k_
        car.eng[k] = {"id": part_id(car.model, k), "cond": round(max(0.0, min(100.0, c)), 1)}
    # «блок» — чугун, изнашивается меньше, чем сам двигатель в целом
    eng["cond"] = round(max(eng["cond"], min(100.0, e + 10)), 1) if base is None else eng["cond"]


def fix(car):
    """Из сохранения: дописать недостающие ключи (новая версия игры)."""
    if not isinstance(getattr(car, "eng", None), dict) or not car.eng:
        init(car)
        return
    for k in keys(car.model):
        if k not in car.eng:
            car.eng[k] = ({"id": part_id(car.model, k), "cond": car.parts["engine"]["cond"]}
                          if car.parts.get("engine") else None)
    if not isinstance(getattr(car, "eng_flags", None), dict):
        car.eng_flags = {}


def snapshot(car):
    """Внутренности — вместе со снятым целиком двигателем (едут в инвентарь в записи детали)."""
    return {"eng": {k: (dict(v) if v else None) for k, v in (car.eng or {}).items()},
            "flags": dict(getattr(car, "eng_flags", {}) or {})}


def install_whole(car, entry):
    """Поставили двигатель целиком: внутренности из записи или новые (из магазина — всё новое)."""
    sub = entry.get("sub") if isinstance(entry, dict) else None
    if sub and isinstance(sub.get("eng"), dict):
        car.eng = {k: (dict(v) if v else None) for k, v in sub["eng"].items()}
        car.eng_flags = dict(sub.get("flags", {}))
        fix(car)
    else:
        init(car, base=entry["cond"])
        car.eng_flags = {}


def remove_whole(car):
    s = snapshot(car)
    car.eng = {k: None for k in keys(car.model)}
    car.eng_flags = {}
    return s


# --------------------------------------------------------------------------- порядок разборки
def blockers(car, key):
    """Что установлено и мешает снять/поставить эту деталь."""
    g = graph(car.model)
    d = g.get(key)
    if d is None:
        return []
    return [b for b in d["blocked"] if has(car, b)]


def dependents(car, key):
    """Что держится на этой детали (снять её нельзя, пока они стоят) — кроме деталей, уезжающих с ГБЦ."""
    g = graph(car.model)
    out = []
    for k, d in g.items():
        if key in d["needs"] and has(car, k):
            if key == "head" and k in HEAD_CHILDREN:
                continue
            out.append(k)
    return out


def missing_needs(car, key):
    g = graph(car.model)
    d = g.get(key)
    return [n for n in (d["needs"] if d else []) if not has(car, n)]


def can_remove(car, key):
    if not has(car, key) or not car.parts.get("engine"):
        return False, "Детали нет."
    b = blockers(car, key) + dependents(car, key)
    if b:
        return False, "Сначала снимите: " + ", ".join(label(car, x) for x in dict.fromkeys(b))
    return True, ""


def can_install(car, key):
    if not car.parts.get("engine"):
        return False, "Двигатель снят целиком."
    if has(car, key):
        return False, "Уже стоит."
    m = missing_needs(car, key)
    if m:
        return False, "Сначала поставьте: " + ", ".join(label(car, x) for x in m)
    b = blockers(car, key)
    if b:
        return False, "Мешает: " + ", ".join(label(car, x) for x in b)
    return True, ""


def removal_chain(car, key, _seen=None):
    """Всё, что надо снять (в правильном порядке), чтобы добраться до детали, включая её саму."""
    _seen = _seen if _seen is not None else set()
    out = []
    for b in blockers(car, key) + dependents(car, key):
        if b in _seen:
            continue
        _seen.add(b)
        out += removal_chain(car, b, _seen)
    if key not in [o for o in out]:
        out.append(key)
    return out


def minutes(car, key):
    if key.startswith("slot:"):
        s = key[5:]
        return car.slots[s][2] if s in car.slots else 30
    return graph(car.model)[key]["minutes"]


def take_off(car, key):
    """Снять деталь (проверки — заранее). Возвращает запись для инвентаря."""
    part = car.eng[key]
    car.eng[key] = None
    getattr(car, "bolts", {}).pop("eng:" + key, None)
    entry = {"id": part["id"], "cond": part["cond"]}
    if key == "head":           # ГБЦ снимается в сборе: распредвал, клапаны и пружины уезжают вместе с ней
        sub = {}
        for ch in HEAD_CHILDREN:
            if car.eng.get(ch) is not None:
                sub[ch] = car.eng[ch]
                car.eng[ch] = None
        if sub:
            entry["sub"] = {"head": sub}
        car.eng_flags.pop("head_loose", None)
    if key == "oil_pan":
        car.oil = 0.0            # масло слили
    if key in ("water_pump", "thermostat", "head", "head_gasket") and car.coolant_cap > 0:
        car.coolant = 0.0        # антифриз слили
    if key in ("timing", "tensioner", "camshaft") or (key == "crankshaft"):
        car.eng_flags.pop("timing_off", None)
    return entry


def put_on(car, key, entry, careful=True):
    """Поставить деталь. careful=False — «быстро, на глаз»: ошибки сборки."""
    car.eng[key] = {"id": entry["id"], "cond": entry["cond"]}
    getattr(car, "bolts", {}).pop("eng:" + key, None)     # из меню — сразу затянуто (руками в мире — fasteners)
    sub = (entry.get("sub") or {}).get("head") if key == "head" else None
    if sub:
        for ch, p in sub.items():
            if car.eng.get(ch) is None:
                car.eng[ch] = p
    if key == "head":
        if careful:
            car.eng_flags.pop("head_loose", None)
        else:
            car.eng_flags["head_loose"] = True
    if key in ("timing", "slot:belt"):
        if careful:
            car.eng_flags.pop("timing_off", None)
        elif random.random() < 0.6:
            car.eng_flags["timing_off"] = random.choice((1, 2)) * random.choice((-1, 1))   # на сколько зубьев
    if key == "head_gasket" and entry["cond"] < 60:
        car.eng_flags["gasket_reused"] = True
    elif key == "head_gasket":
        car.eng_flags.pop("gasket_reused", None)


# --------------------------------------------------------------------------- влияние на работу
def _g(car, k):
    return cond(car, k) if (car.eng and k in car.eng) else 1.0


def compression(car):
    """0..1: поршни/кольца, клапаны, пружины, прокладка, ГБЦ, фазы."""
    L = layout(car.model)
    ks = ["pistons", "head_gasket", "head"] + (["valves", "springs"] if L["stroke"] == 4 else [])
    vals = [_g(car, k) for k in ks]
    c = 0.5 * min(vals) + 0.5 * sum(vals) / len(vals)
    if car.eng_flags.get("timing_off"):
        c *= 0.55 if abs(car.eng_flags["timing_off"]) == 1 else 0.3
    return c


def bearings(car):
    ks = ["rod_bearings", "main_bearings", "crankshaft", "conrods"]
    vals = [_g(car, k) for k in ks if k in (car.eng or {})]
    return min(vals) if vals else 1.0


def oil_pressure(car):
    """0..1 — давление масла (насос, вкладыши, уровень)."""
    if layout(car.model)["stroke"] == 2:
        return 1.0
    pump = _g(car, "oil_pump") if has(car, "oil_pump") else 0.0
    lvl = min(1.0, car.oil / max(0.1, car.oil_cap * 0.5)) if car.oil_cap > 0 else 1.0
    return pump * (0.35 + 0.65 * bearings(car)) * lvl


def effective(car, block):
    """Состояние двигателя для физики (0..1): самое слабое из блока, компрессии, вкладышей."""
    if not car.eng:
        return block
    return max(0.0, min(block, compression(car), 0.15 + 0.85 * bearings(car)))


def start_problem(car):
    """Причина, по которой двигатель не заведётся из-за внутренностей (или None)."""
    if not car.eng:
        return None
    miss = [k for k in ESSENTIAL if k in car.eng and car.eng[k] is None]
    L = layout(car.model)
    if L.get("belt_slot") and not car.parts.get("belt"):
        miss.append("slot:belt")
    if miss:
        return "Двигатель не соберёт компрессию: нет — " + ", ".join(label(car, k).lower() for k in miss[:4]) + "."
    return None


def distribute_wear(car, amount):
    """Износ «двигателя» из физики раскладывается по деталям (кольца, вкладыши, клапаны...)."""
    w = {"pistons": 1.0, "rod_bearings": 1.0, "main_bearings": 0.8, "valves": 0.7, "camshaft": 0.6,
         "springs": 0.4, "conrods": 0.3, "crankshaft": 0.3, "head_gasket": 0.5, "oil_pump": 0.3, "timing": 0.4,
         "tensioner": 0.4, "head": 0.2}
    for k, f in w.items():
        p = car.eng.get(k) if car.eng else None
        if p is not None:
            p["cond"] = max(0.0, p["cond"] - amount * f * (0.8 + 0.4 * random.random()))
    blk = car.parts.get("engine")
    if blk is not None:
        blk["cond"] = max(0.0, blk["cond"] - amount * 0.35)


def running_effects(car, dt, throttle):
    """Вызывается каждый кадр работающего двигателя. Возвращает (множитель мощности, множитель охлаждения)."""
    if not car.eng:
        return 1.0, 1.0
    L = layout(car.model)
    fl = car.eng_flags
    power, cool = 1.0, 1.0
    # клапанобойный мотор с неверными фазами — клапаны встречаются с поршнями
    if fl.get("timing_off") and L.get("inter") and not fl.get("bent"):
        fl["bent"] = True
        if car.eng.get("valves"):
            car.eng["valves"]["cond"] = min(car.eng["valves"]["cond"], 2.0)
        car.say("Удар в двигателе! Метки ГРМ не совпали — клапаны встретились с поршнями.")
        car.sounds.append("crash")
    if fl.get("timing_off"):
        power *= 0.6
        if random.random() < 0.8 * dt:
            car.misfire = 0.15
            car.say("Мотор троит и стреляет — сбиты метки ГРМ.")
    # натяжитель: без него/убитый — цепь/ремень перескакивает
    if L["stroke"] == 4 and "tensioner" in car.eng:
        t = _g(car, "tensioner") if has(car, "tensioner") else 0.0
        if t < 0.15 and not fl.get("timing_off") and random.random() < (0.15 - t) * 0.3 * dt:
            fl["timing_off"] = 1
            car.say("Цепь/ремень ГРМ перескочил на зуб — натяжитель!" if t > 0 else "Без натяжителя ГРМ перескочил!")
    # масло
    if L["stroke"] == 4:
        if not has(car, "oil_pan"):
            car.oil = 0.0
        if not has(car, "oil_filter"):
            car.oil = max(0.0, car.oil - 0.05 * dt)
            car.say("Масло хлещет — не стоит масляный фильтр!")
        if not has(car, "valve_cover"):
            car.oil = max(0.0, car.oil - 0.004 * dt)
            car.say("Масло брызжет из-под открытой ГБЦ — нет клапанной крышки.")
        pv = oil_pressure(car)
        if pv < 0.25:
            car.say("Лампа давления масла! " + ("Нет масляного насоса." if not has(car, "oil_pump") else "Насос/вкладыши."))
            distribute_wear(car, (0.25 - pv) * 1.2 * dt)
        b = bearings(car)
        if b < 0.25:
            if random.random() < 1.5 * dt:
                car.say("Стук вкладышей в двигателе!")
            distribute_wear(car, (0.25 - b) * 0.3 * dt)
    # прокладка ГБЦ и затяжка
    gk = _g(car, "head_gasket")
    if fl.get("head_loose") and car.eng.get("head_gasket"):
        car.eng["head_gasket"]["cond"] = max(0.0, car.eng["head_gasket"]["cond"] - 0.6 * dt)
    if gk < 0.35 and car.coolant_cap > 0:
        car.coolant = max(0.0, car.coolant - (0.35 - gk) * 0.02 * dt)
        if random.random() < 0.5 * dt:
            car.say("Белый дым и пузыри в расширительном бачке — прогорела прокладка ГБЦ.")
        cool *= 0.7
    # охлаждение
    if L["cooling"] == "water":
        if "water_pump" in car.eng:
            wp = _g(car, "water_pump") if has(car, "water_pump") else 0.0
            cool *= 0.2 + 0.8 * wp
            if wp < 0.2 and random.random() < 0.4 * dt:
                car.say("Помпа не качает — антифриз не циркулирует.")
        if "thermostat" in car.eng and not has(car, "thermostat"):
            cool *= 1.3                       # без термостата мотор недогревается (и течёт из патрубка)
            car.coolant = max(0.0, car.coolant - 0.01 * dt)
    # выпуск и впуск
    if "exhaust_mf" in car.eng and not has(car, "exhaust_mf"):
        power *= 0.9
        car.say("Выхлоп рвётся прямо из ГБЦ — нет выпускного коллектора!")
    if "crank_pulley" in car.eng and not has(car, "crank_pulley"):
        car.say("Шкив коленвала снят — генератор и помпа не крутятся.")
    return power, cool


def drives_accessories(car):
    return not (car.eng and "crank_pulley" in car.eng and car.eng["crank_pulley"] is None)


# --------------------------------------------------------------------------- осмотр и диагностика
INSPECT = {
    "pistons": ["Юбки чистые, кольца подвижные — можно ставить.", "Нагар на днищах, кольца слегка залегли.",
                "Задиры на юбках, кольца залегли в канавках — масложор и слабая компрессия.",
                "Прогар днища, сломана перемычка между кольцами — только замена."],
    "rod_bearings": ["Ровный антифрикционный слой.", "Потёртости, местами видна подложка.",
                     "Стёрты до меди — отсюда стук и падение давления.", "Провёрнуты и сплавлены — менять вместе с шатунами."],
    "main_bearings": ["Как новые.", "Равномерный износ.", "Стёрты до меди.", "Разрушены, есть задиры."],
    "crankshaft": ["Шейки гладкие, в размере.", "Лёгкие риски на шейках — можно шлифовать.",
                   "Шейки в задирах, овал — под шлифовку в ремразмер.", "Шейки прижжены, вал погнут — замена."],
    "conrods": ["Ровные, без люфта.", "Небольшой люфт в поршневой головке.", "Шатун погнут — перекос поршня.",
                "Шатун деформирован, крышка сорвана."],
    "head": ["Плоскость ровная, седла целые.", "Небольшой нагар, седла подгорели.",
             "Коробление плоскости — перед установкой шлифовать.", "Трещина между сёдлами — ГБЦ под замену."],
    "head_gasket": ["Новая, окантовка целая.", "Слегка прижата — повторно ставить не стоит.",
                    "Прогорела между цилиндрами — отсюда потеря компрессии.", "Разрушена — антифриз уходил в масло."],
    "valves": ["Фаски ровные, стержни прямые.", "Нагар, фаски надо притереть.", "Прогар тарелки на выпускном.",
               "Погнуты — был удар о поршни."],
    "springs": ["Упругие, длина в норме.", "Немного просели.", "Просели — клапаны зависают на оборотах.",
                "Одна сломана."],
    "camshaft": ["Кулачки без износа.", "Кулачки слегка стёрты.", "Кулачки стёрты — клапаны открываются не полностью.",
                 "Задиры на опорных шейках — вал заклинивал."],
    "timing": ["Натянута правильно, звенья целые.", "Немного вытянута.", "Сильно вытянута — гремит на холостых.",
               "Порвётся в любой момент."],
    "tensioner": ["Работает.", "Подтекает.", "Не держит натяжение.", "Разрушен."],
    "oil_pump": ["Шестерни без износа.", "Небольшой зазор.", "Большой зазор — давление падает на горячую.",
                 "Шестерни разбиты."],
    "water_pump": ["Крыльчатка целая, подшипник тихий.", "Подшипник шумит.", "Течёт через сальник, люфт вала.",
                   "Крыльчатка разрушена."],
    "thermostat": ["Открывается при 87°C.", "Открывается поздно.", "Заедает.", "Заклинил закрытым."],
}


def inspect_lines(entry, model=None):
    """Что видно при осмотре детали из инвентаря."""
    from items import ITEMS
    it = ITEMS.get(entry["id"], {})
    key = it.get("eng")
    c = entry["cond"]
    idx = 0 if c >= 80 else (1 if c >= 50 else (2 if c >= 20 else 3))
    out = [f"{it.get('name', entry['id'])}: состояние {c:.0f}%."]
    if key in INSPECT:
        out.append(INSPECT[key][idx])
    else:
        out.append(["Как новая.", "Обычный износ — ещё послужит.", "Сильно изношена — лучше заменить.",
                    "Неисправна — только замена."][idx])
    verdict = ["ставить можно", "ставить можно, но ресурс небольшой", "лучше заменить", "на замену"][idx]
    out.append("Вердикт: " + verdict + ".")
    sub = (entry.get("sub") or {})
    if "head" in sub:
        out.append("В сборе с ГБЦ: " + ", ".join(f"{ITEMS.get(p['id'], {}).get('name', k)} {p['cond']:.0f}%"
                                                  for k, p in sub["head"].items()))
    if "eng" in sub:
        n = sum(1 for v in sub["eng"].values() if v)
        out.append(f"Двигатель в сборе: {n} внутренних деталей (компрессия и вкладыши — как были на машине).")
    return out


def diagnose(car):
    """Компрессия по цилиндрам, давление масла, выводы. Двигатель должен быть собран и крутиться стартером."""
    L = layout(car.model)
    base = 30.0 if L["fuel"] == "diesel" else (8.0 if L["stroke"] == 2 else 12.0)
    rng = random.Random(car.seed * 13 + int(sum(p["cond"] for p in car.eng.values() if p)))
    cyl = L["cyl"]
    vals = []
    gk = _g(car, "head_gasket")
    bad_gasket_pair = rng.randrange(max(1, cyl - 1)) if gk < 0.35 else None
    bad_valve = rng.randrange(cyl) if _g(car, "valves") < 0.4 else None
    for i in range(cyl):
        c = 0.35 + 0.65 * (0.6 * _g(car, "pistons") + 0.4 * _g(car, "head")) * rng.uniform(0.95, 1.03)
        if L["stroke"] == 4:
            c *= 0.7 + 0.3 * _g(car, "springs")
        if bad_valve == i:
            c *= 0.3 + _g(car, "valves")
        if bad_gasket_pair is not None and i in (bad_gasket_pair, bad_gasket_pair + 1):
            c *= 0.35 + gk
        if car.eng_flags.get("timing_off"):
            c *= 0.5
        vals.append(round(base * min(1.1, c), 1))
    lines = ["Компрессия: " + "  ".join(f"{i + 1}-й: {v:.1f} бар" for i, v in enumerate(vals)),
             f"Норма: {base * 0.85:.0f}–{base * 1.05:.0f} бар, разница между цилиндрами — не больше 1 бар."]
    if L["stroke"] == 4:
        lines.append(f"Давление масла на холостых: {oil_pressure(car) * 2.2:.1f} бар (норма 1.5–2.5).")
    hints = []
    if bad_gasket_pair is not None:
        hints.append(f"Низко в соседних {bad_gasket_pair + 1}-м и {bad_gasket_pair + 2}-м — прогорела прокладка ГБЦ.")
    if bad_valve is not None:
        hints.append(f"Провал в {bad_valve + 1}-м — клапан (прогар/погнут).")
    if min(vals) < base * 0.7 and bad_gasket_pair is None and bad_valve is None:
        hints.append("Низко во всех — кольца/поршни или фазы ГРМ.")
    if car.eng_flags.get("timing_off"):
        hints.append("Компрессия низкая везде, мотор троит — проверьте метки ГРМ.")
    if L["stroke"] == 4 and oil_pressure(car) < 0.4:
        hints.append("Давление масла низкое — масляный насос или вкладыши.")
    if car.eng_flags.get("head_loose"):
        hints.append("Под ГБЦ подтекает антифриз — болты затянуты не по схеме.")
    return lines + (hints or ["По компрессии и давлению двигатель в порядке."])
