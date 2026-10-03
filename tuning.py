"""Тюнинг: детали, которые ставятся ПОВЕРХ стандартной комплектации (турбонаддув и т.п.).

Это обычные детали из инвентаря (покупаются в магазине, продаются, снимаются при разборке, изнашиваются),
но хранятся не в car.parts (стандартные слоты), а в car.tune — поэтому машина без тюнинга
считается полностью комплектной и нормально ездит. Какие модели что поддерживают — TUNING.
Физика влияния — в car.py (Car.update), меню установки — actions.CarWork («Тюнинг»).
"""

# детали тюнинга (попадают в общий каталог ITEMS)
TUNE_ITEMS = {
    "civic_turbo": dict(name="Турбокит IHI RHB5 для Honda Civic (турбина, коллектор, маслопровод)",
                        kind="part", price=1450.0, model="civic"),
    "civic_intercooler": dict(name="Интеркулер фронтальный — Honda Civic", kind="part", price=380.0, model="civic"),
    "boost_ctrl": dict(name="Механический буст-контроллер (регулятор наддува)", kind="part", price=120.0),
    # ---- Ford Mustang → Shelby GT500 «Eleanor»
    "mus_engine": dict(name="Big-Block V8 428 Cobra Jet (7.0 л, 355 л.с.) — двигатель в сборе", kind="part",
                       price=14500.0, model="mustang"),
    "mus_gearbox": dict(name="КПП Toploader 4-ступ. с близкими передачами + мост 3.50", kind="part", price=3200.0, model="mustang"),
    "mus_susp": dict(name="Подвеска Shelby: пружины, стабилизаторы, амортизаторы Koni", kind="part", price=2800.0,
                     model="mustang"),
    "mus_brakes": dict(name="Дисковые тормоза Kelsey-Hayes, 4 поршня", kind="part", price=2100.0, model="mustang"),
    "mus_wheels": dict(name="Диски Shelby 17\" + шины 245/45 (комплект)", kind="part", price=2600.0, model="mustang"),
    "mus_exhaust": dict(name="Боковые выпускные трубы", kind="part", price=1900.0, model="mustang"),
    "mus_body": dict(name="Обвес GT500: бампер с «пастью», противотуманки, пороги, боковые воздухозаборники, спойлер",
                     kind="part", price=5200.0, model="mustang"),
    "mus_hood": dict(name="Капот GT500 с воздухозаборниками и замками-шпильками", kind="part", price=1400.0,
                     model="mustang"),
    "mus_paint": dict(name="Покраска в серый «Pepper Grey» + чёрные гоночные полосы (работа маляра)", kind="part", price=3800.0,
                      model="mustang"),
    "mus_interior": dict(name="Салон: ковши, трёхспицевый руль, приборы Stewart-Warner", kind="part", price=1200.0,
                         model="mustang"),
}

# модель -> {узел: (id детали, минут на установку, нужен гараж)}
TUNING = {
    "civic": {
        "turbo": ("civic_turbo", 300, True),
        "intercooler": ("civic_intercooler", 120, True),
        "boost_ctrl": ("boost_ctrl", 40, False),
    },
}
TUNING["mustang"] = {
    "engine428": ("mus_engine", 600, True),
    "toploader": ("mus_gearbox", 300, True),
    "susp": ("mus_susp", 240, True),
    "brakes": ("mus_brakes", 180, False),
    "wheels": ("mus_wheels", 60, False),
    "sidepipes": ("mus_exhaust", 120, False),
    "bodykit": ("mus_body", 480, True),
    "hood": ("mus_hood", 90, False),
    "paint": ("mus_paint", 1440, True),
    "interior": ("mus_interior", 150, False),
}
TUNE_NAMES = {"turbo": "Турбина", "intercooler": "Интеркулер", "boost_ctrl": "Буст-контроллер",
              "engine428": "Двигатель 428 Cobra Jet", "toploader": "КПП Toploader", "susp": "Подвеска Shelby",
              "brakes": "Тормоза Kelsey-Hayes", "wheels": "Колёса Shelby 17\"", "sidepipes": "Боковой выхлоп",
              "bodykit": "Обвес GT500", "hood": "Капот GT500", "paint": "Покраска и полосы",
              "interior": "Салон GT500"}
# что делает каждая деталь: mul — умножить, add — прибавить, set — заменить значение в характеристиках
TUNE_EFFECTS = {
    "mustang": {
        "engine428": dict(mul={"tq_peak": 1.75}, set={"tq_rpm": 3400.0, "tq_width": 3400.0, "cut": 5800, "overrev": 6300,
                                                     "idle": 750},
                          add={"mass": 60.0}),
        "toploader": dict(set={"gears": {-1: -2.32, 0: 0.0, 1: 2.32, 2: 1.69, 3: 1.29, 4: 1.00}, "final": 3.5}),
        "susp": dict(add={"grip": 0.08, "steer_max": 2}, set={"soft": 0.75}),
        "brakes": dict(set={"brake": 1.35}),
        "wheels": dict(add={"grip": 0.07}, set={"wheel_r": 0.33}),
        "sidepipes": dict(mul={"tq_peak": 1.05}),
        "bodykit": dict(add={"cda": -0.06, "grip": 0.02, "mass": 15.0}),
        "hood": dict(add={"cda": -0.01}),
        "paint": dict(),
        "interior": dict(add={"mass": -10.0}),
    },
}
LEGEND = {"mustang": dict(name="Ford Mustang Shelby GT500 «Eleanor»", mul={"tq_peak": 1.05})}
# узлы, которые без турбины не имеют смысла
NEEDS_TURBO = ("intercooler", "boost_ctrl")

# режимы наддува: (ключ, название, давление бар, что нужно кроме турбины)
BOOST_PRESETS = [
    ("soft", "Мягкий — 0.4 бар (пружина вестгейта)", 0.40, ()),
    ("sport", "Спорт — 0.6 бар", 0.60, ("boost_ctrl",)),
    ("race", "Гонка — 0.85 бар (без интеркулера — детонация!)", 0.85, ("boost_ctrl",)),
]
BOOST_BY_KEY = {k: (name, bar, need) for k, name, bar, need in BOOST_PRESETS}

TORQUE_PER_BAR = 0.9          # +90 % крутящего момента на 1 бар (с поправкой на потери)


def tune_slots(model):
    return TUNING.get(model, {})


def default_tune(model):
    if model not in TUNING:
        return {}
    t = {k: None for k in TUNING[model]}
    t["boost"] = "soft"
    return t


def fix_tune(model, tune):
    """Сохранения старых версий / мусор — привести к нормальному виду."""
    base = default_tune(model)
    if not isinstance(tune, dict):
        return base
    for k in base:
        if k in tune:
            base[k] = tune[k]
    if base and base.get("boost") not in BOOST_BY_KEY:
        base["boost"] = "soft"
    return base


def is_legend(car):
    """Полный комплект установлен — машина превращается в легенду."""
    t = tune_slots(car.model)
    return bool(t) and car.model in LEGEND and all(isinstance(car.tune.get(n), dict) for n in t)


def apply_spec(car, base):
    """Характеристики машины с учётом установленного тюнинга (копия — общие SPECS не трогаем)."""
    eff = TUNE_EFFECTS.get(car.model)
    if not eff or not car.tune:
        return base
    sp = dict(base)
    installed = [n for n in eff if isinstance(car.tune.get(n), dict)]
    for n in installed:
        e = eff[n]
        for k, v in e.get("mul", {}).items():
            sp[k] = sp[k] * v
        for k, v in e.get("add", {}).items():
            sp[k] = sp.get(k, 0) + v
        for k, v in e.get("set", {}).items():
            sp[k] = dict(v) if isinstance(v, dict) else v
    if is_legend(car):
        L = LEGEND[car.model]
        for k, v in L.get("mul", {}).items():
            sp[k] = sp[k] * v
        sp["name"] = L["name"]
    elif installed:
        sp["name"] = f"{base['name']} · тюнинг {len(installed)}/{len(eff)}"
    return sp


def tune_items_for(model):
    return [pid for pid, _, _ in tune_slots(model).values()]
