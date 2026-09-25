"""Модели машин, которые можно найти брошенными и восстановить.

Всё на реальных цифрах конца 70-х — 80-х. Файл только с данными (без импорта игры):
  spec   — характеристики для физики (car.py),
  body   — форма кузова для отрисовки бортов и 3D-модели (car.py / car3d.py),
  slots  — названия деталей этой модели (items.py строит из них каталог запчастей),
  quirks — особенности (двухтактный мотор, воздушное охлаждение, дизель, дюропласт...).
"""

# Общий набор слотов (порядок в меню ремонта)
SLOT_ORDER = ["engine", "gearbox", "clutch", "battery", "starter", "alternator", "belt", "wiring",
              "plugs", "distributor", "carb", "fuel_pump", "fuel_filter", "air_filter", "radiator",
              "exhaust", "lights", "glass", "brakes_f", "brakes_r", "shocks", "steering",
              "tire_fl", "tire_fr", "tire_rl", "tire_rr"]

BASE_NAMES = {
    "engine": "Двигатель", "gearbox": "Коробка передач", "clutch": "Сцепление", "battery": "Аккумулятор",
    "starter": "Стартер", "alternator": "Генератор", "belt": "Ремень", "wiring": "Электропроводка",
    "plugs": "Свечи зажигания", "distributor": "Трамблёр", "carb": "Карбюратор", "fuel_pump": "Бензонасос",
    "fuel_filter": "Топливный фильтр", "air_filter": "Воздушный фильтр", "radiator": "Радиатор",
    "exhaust": "Глушитель", "lights": "Фары", "glass": "Лобовое стекло", "brakes_f": "Тормоза передние",
    "brakes_r": "Тормоза задние", "shocks": "Амортизаторы", "steering": "Рулевые тяги",
    "tire_fl": "Шина перед. лев.", "tire_fr": "Шина перед. прав.", "tire_rl": "Шина зад. лев.",
    "tire_rr": "Шина зад. прав.",
}

SLOT_MINUTES = {
    "engine": 480, "gearbox": 240, "clutch": 180, "battery": 10, "starter": 45, "alternator": 45,
    "belt": 15, "wiring": 150, "plugs": 20, "distributor": 40, "carb": 60, "fuel_pump": 30,
    "fuel_filter": 10, "air_filter": 5, "radiator": 60, "exhaust": 50, "lights": 30, "glass": 90,
    "brakes_f": 40, "brakes_r": 60, "shocks": 90, "steering": 60,
    "tire_fl": 20, "tire_fr": 20, "tire_rl": 20, "tire_rr": 20,
}

# Базовые цены деталей (уровень ВАЗ, DM 1998); у модели — множитель price
BASE_PRICES = {
    "engine": 900, "gearbox": 260, "clutch": 90, "starter": 140, "alternator": 160, "belt": 12,
    "wiring": 80, "plugs": 16, "distributor": 65, "carb": 180, "fuel_pump": 45, "fuel_filter": 6,
    "air_filter": 9, "radiator": 150, "exhaust": 75, "lights": 60, "glass": 90, "brakes_f": 35,
    "brakes_r": 40, "shocks": 120, "steering": 55,
}

# Шины разных размеров (общие для нескольких моделей)
TIRES = {
    "tire_145": ("Шина 145 SR 13", 42.0),
    "tire_155": ("Шина 155 SR 13", 48.0),
    "tire_175": ("Шина 175 SR 13", 58.0),
    "tire_w123": ("Шина 175 SR 14", 72.0),
}

MODELS = {
    # ------------------------------------------------------------------ Trabant 601
    "trabant": dict(
        name="Trabant 601", short="P601", origin="ГДР, Sachsenring Zwickau", shop="ost", price=0.45,
        scrap=35, spawn=3.0, odo=(60000, 190000),
        desc=("Двухтактный двухцилиндровый мотор 594 см³ воздушного охлаждения, 26 л.с. Кузов из дюропласта — "
              "наружные панели не ржавеют, зато гниют стальные пороги и днище. Масло доливается прямо в бензин (1:50). "
              "Рычаг КПП — на торпедо."),
        quirks=["two_stroke", "air_cooled", "duroplast"],
        spec=dict(length=3.56, width=1.51, wheelbase=2.02, mass=700.0, wheel_r=0.28, final=4.33,
                  gears={-1: -3.90, 0: 0.0, 1: 4.08, 2: 2.32, 3: 1.52, 4: 1.10},
                  idle=950, tank=24.0, oil=0.0, coolant=0.0, tq_peak=54.0, tq_rpm=3000.0, tq_width=2600.0,
                  cut=4700, overrev=5300, limiter=False, cda=0.52, carb=True,
                  two_stroke=True, air_cooled=True, diesel=False, drive="fwd",
                  grip=0.9, steer_max=34, brake=0.75, soft=1.5, sound="2t", wear=1.2,
                  axles=(0.60, 2.62), track=0.62, eye=(-0.30, 1.12, 1.30)),
        slots={"engine": "Двигатель P60 (2-такт., 594 см³)", "gearbox": "КПП 4-ступ. (рычаг на торпедо)",
               "carb": "Карбюратор BVF 28 HB", "distributor": "Прерыватель-распределитель",
               "belt": "Ремень вентилятора (охлаждение!)", "plugs": "Свечи Isolator M14",
               "exhaust": "Глушитель двухтактный", "brakes_f": "Барабаны передние", "brakes_r": "Барабаны задние",
               "shocks": "Амортизаторы + поперечные рессоры", "steering": "Рулевая рейка и тяги",
               "wiring": "Проводка 12 В", "fuel_pump": "Бензокран (самотёк)", "alternator": "Динамо-генератор"},
        no_slots=["radiator"], tire="tire_145",
        body=dict(style="notch", sill=0.28, belt=0.80, trunk_y=0.84, rgb=0.62, roof_start=1.05, roof_end=2.05,
                  roof_y=1.40, ws_base=2.55, hood_y=0.82, nose_y=0.70, b_pillar=1.95, doors=2,
                  lights="round2", grille="slots", bumper="chrome_thin", tail="small_vertical",
                  seats="bench_front", wheel="two_spoke", dash_shift=True,
                  colors=[(225, 222, 200), (150, 185, 200), (100, 130, 160), (150, 170, 90), (220, 205, 140)]),
    ),
    # ------------------------------------------------------------------ Wartburg 353
    "wartburg": dict(
        name="Wartburg 353", short="353", origin="ГДР, Automobilwerk Eisenach", shop="ost", price=0.55,
        scrap=55, spawn=2.0, odo=(80000, 220000),
        desc=("Трёхцилиндровый двухтактный 992 см³ с водяным охлаждением, 50 л.с. Переднеприводный, "
              "рычаг КПП на рулевой колонке, «свободный ход» трансмиссии. Кузов стальной — ржавеет охотно."),
        quirks=["two_stroke"],
        spec=dict(length=4.22, width=1.64, wheelbase=2.45, mass=1000.0, wheel_r=0.29, final=4.22,
                  gears={-1: -3.30, 0: 0.0, 1: 3.77, 2: 2.18, 3: 1.40, 4: 1.00},
                  idle=900, tank=44.0, oil=0.0, coolant=6.5, tq_peak=98.0, tq_rpm=3000.0, tq_width=2800.0,
                  cut=4600, overrev=5100, limiter=False, cda=0.62, carb=True,
                  two_stroke=True, air_cooled=False, diesel=False, drive="fwd",
                  grip=0.95, steer_max=32, brake=0.85, soft=1.3, sound="2t", wear=1.1,
                  axles=(0.85, 3.30), track=0.66, eye=(-0.36, 1.13, 1.80)),
        slots={"engine": "Двигатель 353 (2-такт., 3 цил., 992 см³)", "gearbox": "КПП 4-ступ. (рычаг на руле)",
               "carb": "Карбюратор BVF 40 F2", "distributor": "Прерыватели (3 шт.)",
               "exhaust": "Глушитель двухтактный", "brakes_f": "Колодки передние (диск)",
               "brakes_r": "Колодки задние (барабан)", "wiring": "Проводка 12 В", "plugs": "Свечи Isolator (3 шт.)"},
        no_slots=[], tire="tire",
        body=dict(style="sedan", sill=0.30, belt=0.84, trunk_y=0.88, rgb=0.95, roof_start=1.45, roof_end=2.65,
                  roof_y=1.42, ws_base=3.15, hood_y=0.86, nose_y=0.74, b_pillar=2.05, c_pillar=1.45, doors=4,
                  lights="rect2", grille="wide_chrome", bumper="chrome", tail="wide_rect",
                  seats="separate", wheel="two_spoke", dash_shift=False,
                  colors=[(205, 195, 160), (160, 190, 210), (130, 40, 45), (110, 130, 90), (230, 225, 210)]),
    ),
    # ------------------------------------------------------------------ Opel Kadett C
    "kadett": dict(
        name="Opel Kadett C", short="Kadett C", origin="ФРГ, Opel Bochum", shop="west", price=0.8,
        scrap=60, spawn=2.0, odo=(90000, 210000),
        desc=("Opel 1.2 OHV, 60 л.с., задний привод и простая, крепкая механика. "
              "Классическая беда Kadett C — пороги, арки и днище: гниют насквозь."),
        quirks=["rwd"],
        spec=dict(length=4.12, width=1.58, wheelbase=2.395, mass=930.0, wheel_r=0.285, final=4.11,
                  gears={-1: -3.64, 0: 0.0, 1: 3.636, 2: 2.211, 3: 1.429, 4: 1.00},
                  idle=850, tank=45.0, oil=3.0, coolant=5.2, tq_peak=88.0, tq_rpm=3400.0, tq_width=3200.0,
                  cut=5700, overrev=6200, limiter=False, cda=0.62, carb=True,
                  two_stroke=False, air_cooled=False, diesel=False, drive="rwd",
                  grip=0.95, steer_max=33, brake=0.95, soft=1.1, sound="4t", wear=1.0,
                  axles=(0.85, 3.25), track=0.65, eye=(-0.36, 1.08, 1.75)),
        slots={"engine": "Двигатель Opel 1.2 OHV (60 л.с.)", "carb": "Карбюратор Solex 35 PDSI",
               "gearbox": "КПП Opel 4-ступ.", "brakes_f": "Колодки передние (диск)",
               "brakes_r": "Колодки задние (барабан)"},
        no_slots=[], tire="tire_155",
        body=dict(style="sedan", sill=0.30, belt=0.80, trunk_y=0.84, rgb=1.00, roof_start=1.50, roof_end=2.55,
                  roof_y=1.36, ws_base=3.05, hood_y=0.82, nose_y=0.70, b_pillar=2.00, doors=2,
                  lights="round2", grille="black_bars", bumper="chrome", tail="rect_small",
                  seats="separate", wheel="four_spoke", dash_shift=False,
                  colors=[(200, 110, 30), (230, 190, 40), (120, 80, 50), (170, 40, 30), (90, 120, 150)]),
    ),
    # ------------------------------------------------------------------ VW Golf I
    "golf": dict(
        name="VW Golf I", short="Golf I", origin="ФРГ, Volkswagen Wolfsburg", shop="west", price=0.8,
        scrap=65, spawn=2.0, odo=(100000, 240000),
        desc=("VW 1.1, 50 л.с., передний привод, хэтчбек. Лёгкий и цепкий в поворотах. "
              "Ржавеют задние арки, пороги и низ двери багажника."),
        quirks=["fwd"],
        spec=dict(length=3.73, width=1.61, wheelbase=2.40, mass=860.0, wheel_r=0.28, final=4.27,
                  gears={-1: -3.17, 0: 0.0, 1: 3.45, 2: 1.96, 3: 1.37, 4: 0.97},
                  idle=900, tank=45.0, oil=3.5, coolant=6.0, tq_peak=77.0, tq_rpm=3500.0, tq_width=3300.0,
                  cut=6000, overrev=6500, limiter=False, cda=0.58, carb=True,
                  two_stroke=False, air_cooled=False, diesel=False, drive="fwd",
                  grip=1.05, steer_max=34, brake=1.0, soft=0.9, sound="4t", wear=1.0,
                  axles=(0.62, 3.02), track=0.66, eye=(-0.36, 1.10, 1.55)),
        slots={"engine": "Двигатель VW 1.1 (50 л.с.)", "carb": "Карбюратор Solex 31 PICT",
               "gearbox": "КПП VW 4-ступ.", "brakes_f": "Колодки передние (диск)",
               "brakes_r": "Колодки задние (барабан)"},
        no_slots=[], tire="tire_145",
        body=dict(style="hatch", sill=0.30, belt=0.82, trunk_y=0.82, rgb=0.10, roof_start=0.35, roof_end=2.30,
                  roof_y=1.38, ws_base=2.85, hood_y=0.86, nose_y=0.78, b_pillar=1.90, doors=2,
                  lights="round2", grille="black_bars", bumper="black", tail="vertical_rect",
                  seats="separate", wheel="four_spoke", dash_shift=False,
                  colors=[(180, 40, 35), (210, 190, 150), (175, 178, 182), (80, 120, 70), (225, 190, 50)]),
    ),
    # ------------------------------------------------------------------ Ford Taunus TC2
    "taunus": dict(
        name="Ford Taunus", short="Taunus", origin="ФРГ, Ford Köln", shop="west", price=0.9,
        scrap=75, spawn=1.5, odo=(110000, 250000),
        desc=("Ford 1.6 OHC (Pinto), 72 л.с., задний привод, мягкая подвеска и длинный кузов. "
              "Катится плавно, но в повороте кренится. Ржавчина — арки и низ дверей."),
        quirks=["rwd"],
        spec=dict(length=4.34, width=1.70, wheelbase=2.58, mass=1110.0, wheel_r=0.295, final=3.89,
                  gears={-1: -3.66, 0: 0.0, 1: 3.65, 2: 1.97, 3: 1.37, 4: 1.00},
                  idle=800, tank=54.0, oil=3.75, coolant=7.3, tq_peak=118.0, tq_rpm=2900.0, tq_width=3300.0,
                  cut=5600, overrev=6100, limiter=False, cda=0.68, carb=True,
                  two_stroke=False, air_cooled=False, diesel=False, drive="rwd",
                  grip=0.95, steer_max=31, brake=1.0, soft=1.5, sound="4t", wear=1.0,
                  axles=(0.90, 3.48), track=0.71, eye=(-0.38, 1.10, 1.90)),
        slots={"engine": "Двигатель Ford 1.6 OHC (72 л.с.)", "carb": "Карбюратор Weber 32/36 DGV",
               "belt": "Ремень ГРМ + приводной", "gearbox": "КПП Ford 4-ступ.",
               "brakes_f": "Колодки передние (диск)", "brakes_r": "Колодки задние (барабан)"},
        no_slots=[], tire="tire_175",
        body=dict(style="sedan", sill=0.30, belt=0.82, trunk_y=0.86, rgb=1.05, roof_start=1.60, roof_end=2.75,
                  roof_y=1.37, ws_base=3.25, hood_y=0.84, nose_y=0.72, b_pillar=2.20, c_pillar=1.60, doors=4,
                  lights="rect2", grille="egg_crate", bumper="chrome", tail="wide_rect",
                  seats="separate", wheel="four_spoke", dash_shift=False,
                  colors=[(110, 80, 55), (90, 110, 70), (180, 180, 185), (230, 230, 225), (150, 60, 40)]),
    ),
    # ------------------------------------------------------------------ Mercedes W123 200 D
    "w123": dict(
        name="Mercedes W123 200 D", short="W123", origin="ФРГ, Daimler-Benz Sindelfingen", shop="west",
        price=1.3, scrap=110, spawn=0.6, odo=(250000, 520000),
        desc=("Дизель OM615 2.0 л, 55 л.с. — медленный, но почти вечный мотор. Перед пуском — прогрев "
              "свечей накаливания. Тяжёлый, мягкий и устойчивый. Бывшее такси? Пробег огромный."),
        quirks=["diesel", "rwd"],
        spec=dict(length=4.72, width=1.79, wheelbase=2.795, mass=1475.0, wheel_r=0.31, final=3.69,
                  gears={-1: -3.64, 0: 0.0, 1: 3.98, 2: 2.29, 3: 1.46, 4: 1.00},
                  idle=750, tank=65.0, oil=6.5, coolant=10.0, tq_peak=113.0, tq_rpm=2400.0, tq_width=2600.0,
                  cut=4400, overrev=4800, limiter=True, cda=0.72, carb=False,
                  two_stroke=False, air_cooled=False, diesel=True, drive="rwd",
                  grip=1.0, steer_max=30, brake=1.1, soft=1.2, sound="diesel", wear=0.5,
                  axles=(1.00, 3.80), track=0.74, eye=(-0.40, 1.16, 2.05)),
        slots={"engine": "Дизель OM615 (2.0 л, 55 л.с.)", "plugs": "Свечи накаливания Bosch (4 шт.)",
               "distributor": "ТНВД Bosch (топливный насос)", "carb": "Форсунки дизельные (4 шт.)",
               "fuel_pump": "Подкачивающий насос", "gearbox": "КПП W123 4-ступ.",
               "brakes_f": "Колодки передние (диск)", "brakes_r": "Колодки задние (диск)",
               "starter": "Стартер Bosch (дизельный)"},
        no_slots=[], tire="tire_w123",
        body=dict(style="sedan", sill=0.32, belt=0.88, trunk_y=0.92, rgb=1.12, roof_start=1.70, roof_end=3.00,
                  roof_y=1.44, ws_base=3.52, hood_y=0.90, nose_y=0.82, b_pillar=2.40, c_pillar=1.75, doors=4,
                  lights="rect_tall", grille="tall_chrome", bumper="chrome_rubber", tail="ribbed_wide",
                  seats="separate", wheel="four_spoke", dash_shift=False,
                  colors=[(230, 215, 170), (200, 185, 150), (40, 50, 80), (180, 180, 185), (120, 30, 30)]),
    ),
}


def part_id(model, slot):
    """id запчасти для слота модели."""
    info = MODELS[model]
    if slot == "battery":
        return "battery"
    if slot.startswith("tire_"):
        return info["tire"]
    return f"{model}_{slot}"


def model_slots(model):
    """{слот: (название, id запчасти, минут)} для модели."""
    info = MODELS[model]
    out = {}
    for s in SLOT_ORDER:
        if s in info["no_slots"]:
            continue
        name = info["slots"].get(s, BASE_NAMES[s])
        out[s] = (name, part_id(model, s), SLOT_MINUTES[s])
    return out


def model_items():
    """Каталог запчастей всех моделей: id -> dict(name, kind, price, model)."""
    items = {}
    for m, info in MODELS.items():
        for s, (name, pid, _) in model_slots(m).items():
            if pid in items or pid == "battery" or pid == "tire" or pid in TIRES:
                continue
            price = round(BASE_PRICES[s] * info["price"])
            items[pid] = dict(name=f"{name} — {info['short']}", kind="part", price=float(price), model=m)
    for pid, (name, price) in TIRES.items():
        items[pid] = dict(name=name, kind="part", price=price)
    return items
