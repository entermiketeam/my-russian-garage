"""Модели машин, которые можно найти брошенными и восстановить.

Всё на реальных цифрах конца 70-х — 80-х. Файл только с данными (без импорта игры):
  spec   — характеристики для физики (car.py),
  body   — форма кузова для отрисовки бортов и 3D-модели (car.py / car3d.py),
  slots  — названия деталей этой модели (items.py строит из них каталог запчастей),
  quirks — особенности (двухтактный мотор, воздушное охлаждение, дизель, дюропласт...).
"""

from i18n import T

# Общий набор слотов (порядок в меню ремонта)
SLOT_ORDER = ["engine", "gearbox", "clutch", "battery", "starter", "alternator", "belt", "wiring",
              "plugs", "distributor", "carb", "fuel_pump", "fuel_filter", "air_filter", "radiator",
              "exhaust", "lights", "glass", "brakes_f", "brakes_r", "shocks", "steering",
              "tire_fl", "tire_fr", "tire_rl", "tire_rr", "door_l", "door_r", "hood", "trunk", "seats"]

BASE_NAMES = {
    "engine": T("Двигатель"), "gearbox": T("Коробка передач"), "clutch": T("Сцепление"), "battery": T("Аккумулятор"),
    "starter": T("Стартер"), "alternator": T("Генератор"), "belt": T("Ремень"), "wiring": T("Электропроводка"),
    "plugs": T("Свечи зажигания"), "distributor": T("Трамблёр"), "carb": T("Карбюратор"), "fuel_pump": T("Бензонасос"),
    "fuel_filter": T("Топливный фильтр"), "air_filter": T("Воздушный фильтр"), "radiator": T("Радиатор"),
    "exhaust": T("Глушитель"), "lights": T("Фары"), "glass": T("Лобовое стекло"), "brakes_f": T("Тормоза передние"),
    "brakes_r": T("Тормоза задние"), "shocks": T("Амортизаторы"), "steering": T("Рулевые тяги"),
    "tire_fl": T("Шина перед. лев."), "tire_fr": T("Шина перед. прав."), "tire_rl": T("Шина зад. лев."),
    "tire_rr": T("Шина зад. прав."), "door_l": T("Двери левые"), "door_r": T("Двери правые"), "hood": T("Капот"),
    "trunk": T("Крышка багажника"), "seats": T("Сиденья (комплект)"),
}

SLOT_MINUTES = {
    "engine": 480, "gearbox": 240, "clutch": 180, "battery": 10, "starter": 45, "alternator": 45,
    "belt": 15, "wiring": 150, "plugs": 20, "distributor": 40, "carb": 60, "fuel_pump": 30,
    "fuel_filter": 10, "air_filter": 5, "radiator": 60, "exhaust": 50, "lights": 30, "glass": 90,
    "brakes_f": 40, "brakes_r": 60, "shocks": 90, "steering": 60,
    "tire_fl": 20, "tire_fr": 20, "tire_rl": 20, "tire_rr": 20,
    "door_l": 40, "door_r": 40, "hood": 20, "trunk": 25, "seats": 40,
}

# Базовые цены деталей (уровень ВАЗ, ₽ 1998); у модели — множитель price
BASE_PRICES = {
    "engine": 900, "gearbox": 260, "clutch": 90, "starter": 140, "alternator": 160, "belt": 12,
    "wiring": 80, "plugs": 16, "distributor": 65, "carb": 180, "fuel_pump": 45, "fuel_filter": 6,
    "air_filter": 9, "radiator": 150, "exhaust": 75, "lights": 60, "glass": 90, "brakes_f": 35,
    "brakes_r": 40, "shocks": 120, "steering": 55,
    "door_l": 95, "door_r": 95, "hood": 80, "trunk": 85, "seats": 70,
}

# Шины разных размеров (общие для нескольких моделей)
TIRES = {
    "tire_145": (T("Шина 145 SR 13"), 42.0),
    "tire_155": (T("Шина 155 SR 13"), 48.0),
    "tire_175": (T("Шина 175 SR 13"), 58.0),
    "tire_w123": (T("Шина 175 SR 14"), 72.0),
    "tire_185_14": (T("Шина 185/70 R 14"), 76.0),
    "tire_165_13": (T("Шина 165 SR 13"), 52.0),
    "tire_mustang": (T("Шина 7.35-14 (Mustang)"), 95.0),
}

MODELS = {
    # ------------------------------------------------------------------ Trabant 601
    "trabant": dict(
        name="Trabant 601", short="P601", origin=T("ГДР, Sachsenring Zwickau"), shop="ost", price=0.45,
        scrap=35, spawn=3.0, odo=(60000, 190000),
        desc=(T("Двухтактный двухцилиндровый мотор 594 см³ воздушного охлаждения, 26 л.с. Кузов из дюропласта — "
              "наружные панели не ржавеют, зато гниют стальные пороги и днище. Масло доливается прямо в бензин (1:50). "
              "Рычаг КПП — на торпедо.")),
        quirks=["two_stroke", "air_cooled", "duroplast"],
        spec=dict(length=3.56, width=1.51, wheelbase=2.02, mass=700.0, wheel_r=0.28, final=4.33,
                  gears={-1: -3.90, 0: 0.0, 1: 4.08, 2: 2.32, 3: 1.52, 4: 1.10},
                  idle=950, tank=24.0, oil=0.0, coolant=0.0, tq_peak=54.0, tq_rpm=3000.0, tq_width=2600.0,
                  cut=4700, overrev=5300, limiter=False, cda=0.52, carb=True,
                  two_stroke=True, air_cooled=True, diesel=False, drive="fwd",
                  grip=0.9, steer_max=34, brake=0.75, soft=1.5, sound="2t", wear=1.2,
                  axles=(0.60, 2.62), track=0.62, eye=(-0.30, 1.12, 1.30)),
        slots={"engine": T("Двигатель P60 (2-такт., 594 см³)"), "gearbox": T("КПП 4-ступ. (рычаг на торпедо)"),
               "carb": T("Карбюратор BVF 28 HB"), "distributor": T("Прерыватель-распределитель"),
               "belt": T("Ремень вентилятора (охлаждение!)"), "plugs": T("Свечи Isolator M14"),
               "exhaust": T("Глушитель двухтактный"), "brakes_f": T("Барабаны передние"), "brakes_r": T("Барабаны задние"),
               "shocks": T("Амортизаторы + поперечные рессоры"), "steering": T("Рулевая рейка и тяги"),
               "wiring": T("Проводка 12 В"), "fuel_pump": T("Бензокран (самотёк)"), "alternator": T("Динамо-генератор")},
        no_slots=["radiator"], tire="tire_145",
        body=dict(style="notch", sill=0.28, belt=0.80, trunk_y=0.84, rgb=0.62, roof_start=1.05, roof_end=2.05,
                  roof_y=1.40, ws_base=2.55, hood_y=0.82, nose_y=0.70, b_pillar=1.95, doors=2,
                  lights="round2", grille="slots", bumper="chrome_thin", tail="small_vertical",
                  seats="bench_front", wheel="two_spoke", dash_shift=True,
                  colors=[(225, 222, 200), (150, 185, 200), (100, 130, 160), (150, 170, 90), (220, 205, 140)]),
    ),
    # ------------------------------------------------------------------ Wartburg 353
    "wartburg": dict(
        name="Wartburg 353", short="353", origin=T("ГДР, Automobilwerk Eisenach"), shop="ost", price=0.55,
        scrap=55, spawn=2.0, odo=(80000, 220000),
        desc=(T("Трёхцилиндровый двухтактный 992 см³ с водяным охлаждением, 50 л.с. Переднеприводный, "
              "рычаг КПП на рулевой колонке, «свободный ход» трансмиссии. Кузов стальной — ржавеет охотно.")),
        quirks=["two_stroke"],
        spec=dict(length=4.22, width=1.64, wheelbase=2.45, mass=1000.0, wheel_r=0.29, final=4.22,
                  gears={-1: -3.30, 0: 0.0, 1: 3.77, 2: 2.18, 3: 1.40, 4: 1.00},
                  idle=900, tank=44.0, oil=0.0, coolant=6.5, tq_peak=98.0, tq_rpm=3000.0, tq_width=2800.0,
                  cut=4600, overrev=5100, limiter=False, cda=0.62, carb=True,
                  two_stroke=True, air_cooled=False, diesel=False, drive="fwd",
                  grip=0.95, steer_max=32, brake=0.85, soft=1.3, sound="2t", wear=1.1,
                  axles=(0.85, 3.30), track=0.66, eye=(-0.36, 1.13, 1.80)),
        slots={"engine": T("Двигатель 353 (2-такт., 3 цил., 992 см³)"), "gearbox": T("КПП 4-ступ. (рычаг на руле)"),
               "carb": T("Карбюратор BVF 40 F2"), "distributor": T("Прерыватели (3 шт.)"),
               "exhaust": T("Глушитель двухтактный"), "brakes_f": T("Колодки передние (диск)"),
               "brakes_r": T("Колодки задние (барабан)"), "wiring": T("Проводка 12 В"), "plugs": T("Свечи Isolator (3 шт.)")},
        no_slots=[], tire="tire",
        body=dict(style="sedan", sill=0.30, belt=0.84, trunk_y=0.88, rgb=0.95, roof_start=1.45, roof_end=2.65,
                  roof_y=1.42, ws_base=3.15, hood_y=0.86, nose_y=0.74, b_pillar=2.05, c_pillar=1.45, doors=4,
                  lights="rect2", grille="wide_chrome", bumper="chrome", tail="wide_rect",
                  seats="separate", wheel="two_spoke", dash_shift=False,
                  colors=[(205, 195, 160), (160, 190, 210), (130, 40, 45), (110, 130, 90), (230, 225, 210)]),
    ),
    # ------------------------------------------------------------------ Opel Kadett C
    "kadett": dict(
        name="Opel Kadett C", short="Kadett C", origin=T("ФРГ, Opel Bochum"), shop="west", price=0.8,
        scrap=60, spawn=2.0, odo=(90000, 210000),
        desc=(T("Opel 1.2 OHV, 60 л.с., задний привод и простая, крепкая механика. "
              "Классическая беда Kadett C — пороги, арки и днище: гниют насквозь.")),
        quirks=["rwd"],
        spec=dict(length=4.12, width=1.58, wheelbase=2.395, mass=930.0, wheel_r=0.285, final=4.11,
                  gears={-1: -3.64, 0: 0.0, 1: 3.636, 2: 2.211, 3: 1.429, 4: 1.00},
                  idle=850, tank=45.0, oil=3.0, coolant=5.2, tq_peak=88.0, tq_rpm=3400.0, tq_width=3200.0,
                  cut=5700, overrev=6200, limiter=False, cda=0.62, carb=True,
                  two_stroke=False, air_cooled=False, diesel=False, drive="rwd",
                  grip=0.95, steer_max=33, brake=0.95, soft=1.1, sound="4t", wear=1.0,
                  axles=(0.85, 3.25), track=0.65, eye=(-0.36, 1.08, 1.75)),
        slots={"engine": T("Двигатель Opel 1.2 OHV (60 л.с.)"), "carb": T("Карбюратор Solex 35 PDSI"),
               "gearbox": T("КПП Opel 4-ступ."), "brakes_f": T("Колодки передние (диск)"),
               "brakes_r": T("Колодки задние (барабан)")},
        no_slots=[], tire="tire_155",
        body=dict(style="sedan", sill=0.30, belt=0.80, trunk_y=0.84, rgb=1.00, roof_start=1.50, roof_end=2.55,
                  roof_y=1.36, ws_base=3.05, hood_y=0.82, nose_y=0.70, b_pillar=2.00, doors=2,
                  lights="round2", grille="black_bars", bumper="chrome", tail="rect_small",
                  seats="separate", wheel="four_spoke", dash_shift=False,
                  colors=[(200, 110, 30), (230, 190, 40), (120, 80, 50), (170, 40, 30), (90, 120, 150)]),
    ),
    # ------------------------------------------------------------------ VW Golf I
    "golf": dict(
        name="VW Golf I", short="Golf I", origin=T("ФРГ, Volkswagen Wolfsburg"), shop="west", price=0.8,
        scrap=65, spawn=2.0, odo=(100000, 240000),
        desc=(T("VW 1.1, 50 л.с., передний привод, хэтчбек. Лёгкий и цепкий в поворотах. "
              "Ржавеют задние арки, пороги и низ двери багажника.")),
        quirks=["fwd"],
        spec=dict(length=3.73, width=1.61, wheelbase=2.40, mass=860.0, wheel_r=0.28, final=4.27,
                  gears={-1: -3.17, 0: 0.0, 1: 3.45, 2: 1.96, 3: 1.37, 4: 0.97},
                  idle=900, tank=45.0, oil=3.5, coolant=6.0, tq_peak=77.0, tq_rpm=3500.0, tq_width=3300.0,
                  cut=6000, overrev=6500, limiter=False, cda=0.58, carb=True,
                  two_stroke=False, air_cooled=False, diesel=False, drive="fwd",
                  grip=1.05, steer_max=34, brake=1.0, soft=0.9, sound="4t", wear=1.0,
                  axles=(0.62, 3.02), track=0.66, eye=(-0.36, 1.10, 1.55)),
        slots={"engine": T("Двигатель VW 1.1 (50 л.с.)"), "carb": T("Карбюратор Solex 31 PICT"),
               "gearbox": T("КПП VW 4-ступ."), "brakes_f": T("Колодки передние (диск)"),
               "brakes_r": T("Колодки задние (барабан)")},
        no_slots=[], tire="tire_145",
        body=dict(style="hatch", sill=0.30, belt=0.82, trunk_y=0.82, rgb=0.10, roof_start=0.35, roof_end=2.30,
                  roof_y=1.38, ws_base=2.85, hood_y=0.86, nose_y=0.78, b_pillar=1.90, doors=2,
                  lights="round2", grille="black_bars", bumper="black", tail="vertical_rect",
                  seats="separate", wheel="four_spoke", dash_shift=False,
                  colors=[(180, 40, 35), (210, 190, 150), (175, 178, 182), (80, 120, 70), (225, 190, 50)]),
    ),
    # ------------------------------------------------------------------ Ford Taunus TC2
    "taunus": dict(
        name="Ford Taunus", short="Taunus", origin=T("ФРГ, Ford Köln"), shop="west", price=0.9,
        scrap=75, spawn=1.5, odo=(110000, 250000),
        desc=(T("Ford 1.6 OHC (Pinto), 72 л.с., задний привод, мягкая подвеска и длинный кузов. "
              "Катится плавно, но в повороте кренится. Ржавчина — арки и низ дверей.")),
        quirks=["rwd"],
        spec=dict(length=4.34, width=1.70, wheelbase=2.58, mass=1110.0, wheel_r=0.295, final=3.89,
                  gears={-1: -3.66, 0: 0.0, 1: 3.65, 2: 1.97, 3: 1.37, 4: 1.00},
                  idle=800, tank=54.0, oil=3.75, coolant=7.3, tq_peak=118.0, tq_rpm=2900.0, tq_width=3300.0,
                  cut=5600, overrev=6100, limiter=False, cda=0.68, carb=True,
                  two_stroke=False, air_cooled=False, diesel=False, drive="rwd",
                  grip=0.95, steer_max=31, brake=1.0, soft=1.5, sound="4t", wear=1.0,
                  axles=(0.90, 3.48), track=0.71, eye=(-0.38, 1.10, 1.90)),
        slots={"engine": T("Двигатель Ford 1.6 OHC (72 л.с.)"), "carb": T("Карбюратор Weber 32/36 DGV"),
               "belt": T("Ремень ГРМ + приводной"), "gearbox": T("КПП Ford 4-ступ."),
               "brakes_f": T("Колодки передние (диск)"), "brakes_r": T("Колодки задние (барабан)")},
        no_slots=[], tire="tire_175",
        body=dict(style="sedan", sill=0.30, belt=0.82, trunk_y=0.86, rgb=1.05, roof_start=1.60, roof_end=2.75,
                  roof_y=1.37, ws_base=3.25, hood_y=0.84, nose_y=0.72, b_pillar=2.20, c_pillar=1.60, doors=4,
                  lights="rect2", grille="egg_crate", bumper="chrome", tail="wide_rect",
                  seats="separate", wheel="four_spoke", dash_shift=False,
                  colors=[(110, 80, 55), (90, 110, 70), (180, 180, 185), (230, 230, 225), (150, 60, 40)]),
    ),
    # ------------------------------------------------------------------ Mercedes W123 200 D
    "w123": dict(
        name="Mercedes W123 200 D", short="W123", origin=T("ФРГ, Daimler-Benz Sindelfingen"), shop="west",
        price=1.3, scrap=110, spawn=0.6, odo=(250000, 520000),
        desc=(T("Дизель OM615 2.0 л, 55 л.с. — медленный, но почти вечный мотор. Перед пуском — прогрев "
              "свечей накаливания. Тяжёлый, мягкий и устойчивый. Бывшее такси? Пробег огромный.")),
        quirks=["diesel", "rwd"],
        spec=dict(length=4.72, width=1.79, wheelbase=2.795, mass=1475.0, wheel_r=0.31, final=3.69,
                  gears={-1: -3.64, 0: 0.0, 1: 3.98, 2: 2.29, 3: 1.46, 4: 1.00},
                  idle=750, tank=65.0, oil=6.5, coolant=10.0, tq_peak=113.0, tq_rpm=2400.0, tq_width=2600.0,
                  cut=4400, overrev=4800, limiter=True, cda=0.72, carb=False,
                  two_stroke=False, air_cooled=False, diesel=True, drive="rwd",
                  grip=1.0, steer_max=30, brake=1.1, soft=1.2, sound="diesel", wear=0.5,
                  axles=(1.00, 3.80), track=0.74, eye=(-0.40, 1.16, 2.05)),
        slots={"engine": T("Дизель OM615 (2.0 л, 55 л.с.)"), "plugs": T("Свечи накаливания Bosch (4 шт.)"),
               "distributor": T("ТНВД Bosch (топливный насос)"), "carb": T("Форсунки дизельные (4 шт.)"),
               "fuel_pump": T("Подкачивающий насос"), "gearbox": T("КПП W123 4-ступ."),
               "brakes_f": T("Колодки передние (диск)"), "brakes_r": T("Колодки задние (диск)"),
               "starter": T("Стартер Bosch (дизельный)")},
        no_slots=[], tire="tire_w123",
        body=dict(style="sedan", sill=0.32, belt=0.88, trunk_y=0.92, rgb=1.12, roof_start=1.70, roof_end=3.00,
                  roof_y=1.44, ws_base=3.52, hood_y=0.90, nose_y=0.82, b_pillar=2.40, c_pillar=1.75, doors=4,
                  lights="rect_tall", grille="tall_chrome", bumper="chrome_rubber", tail="ribbed_wide",
                  seats="separate", wheel="four_spoke", dash_shift=False,
                  colors=[(230, 215, 170), (200, 185, 150), (40, 50, 80), (180, 180, 185), (120, 30, 30)]),
    ),
    # ------------------------------------------------------------------ Москвич-2140
    "moskvich": dict(
        name=T("Москвич-2140"), short=T("М-2140"), origin=T("СССР, АЗЛК Москва"), shop="ost", price=0.6,
        scrap=60, spawn=1.6, odo=(90000, 260000),
        desc=(T("УЗАМ-412, 1.5 л, 75 л.с., задний привод. Привезли переселенцы или купили в ГДР. Крепкий, "
              "но тяжёлый руль и слабые тормоза. Гниёт всё: пороги, днище, крылья, низ дверей.")),
        quirks=["rwd"],
        spec=dict(length=4.25, width=1.55, wheelbase=2.40, mass=1160.0, wheel_r=0.29, final=4.22,
                  gears={-1: -3.39, 0: 0.0, 1: 3.49, 2: 2.04, 3: 1.33, 4: 1.00},
                  idle=850, tank=46.0, oil=4.5, coolant=7.8, tq_peak=110.0, tq_rpm=3800.0, tq_width=3200.0,
                  cut=5800, overrev=6300, limiter=False, cda=0.68, carb=True,
                  two_stroke=False, air_cooled=False, diesel=False, drive="rwd",
                  grip=0.92, steer_max=31, brake=0.85, soft=1.35, sound="4t", wear=1.1,
                  axles=(0.85, 3.25), track=0.63, eye=(-0.36, 1.12, 1.80)),
        slots={"engine": T("Двигатель УЗАМ-412 (1.5 л, 75 л.с.)"), "carb": T("Карбюратор ДААЗ-2140"),
               "gearbox": T("КПП 4-ступ. Москвич"), "brakes_f": T("Колодки передние (диск)"),
               "brakes_r": T("Колодки задние (барабан)")},
        no_slots=[], tire="tire_165_13",
        body=dict(style="sedan", sill=0.30, belt=0.84, trunk_y=0.88, rgb=0.98, roof_start=1.48, roof_end=2.60,
                  roof_y=1.42, ws_base=3.10, hood_y=0.86, nose_y=0.76, b_pillar=2.05, c_pillar=1.45, doors=4,
                  lights="rect2", grille="black_bars", bumper="chrome", tail="wide_rect",
                  seats="separate", wheel="two_spoke", dash_shift=False,
                  colors=[(120, 30, 30), (200, 190, 140), (60, 90, 70), (150, 170, 180), (220, 215, 200)]),
    ),
    # ------------------------------------------------------------------ Volvo 240
    "volvo240": dict(
        name="Volvo 240 GL", short="240", origin=T("Швеция, Volvo Torslanda"), shop="west", price=1.1,
        scrap=95, spawn=1.2, odo=(180000, 420000),
        desc=(T("B21A, 2.1 л, 107 л.с., задний привод. «Кирпич» — толстый металл и хорошая антикоррозийка, "
              "ржавеет медленнее всех. Тяжёлый, неторопливый, почти вечный.")),
        quirks=["rwd", "tough_body"],
        spec=dict(length=4.79, width=1.71, wheelbase=2.64, mass=1380.0, wheel_r=0.31, final=3.91,
                  gears={-1: -3.68, 0: 0.0, 1: 4.03, 2: 2.16, 3: 1.37, 4: 1.00},
                  idle=800, tank=60.0, oil=3.85, coolant=9.5, tq_peak=170.0, tq_rpm=2500.0, tq_width=3300.0,
                  cut=5600, overrev=6100, limiter=False, cda=0.78, carb=True,
                  two_stroke=False, air_cooled=False, diesel=False, drive="rwd",
                  grip=0.97, steer_max=31, brake=1.05, soft=1.25, sound="4t", wear=0.7,
                  axles=(1.05, 3.69), track=0.72, eye=(-0.38, 1.14, 2.05)),
        slots={"engine": T("Двигатель Volvo B21A (2.1 л)"), "carb": T("Карбюратор SU HIF6"),
               "gearbox": T("КПП Volvo M45"), "brakes_f": T("Колодки передние (диск)"), "brakes_r": T("Колодки задние (диск)")},
        no_slots=[], tire="tire_185_14",
        body=dict(style="sedan", sill=0.32, belt=0.88, trunk_y=0.92, rgb=1.12, roof_start=1.70, roof_end=3.05,
                  roof_y=1.43, ws_base=3.55, hood_y=0.90, nose_y=0.82, b_pillar=2.45, c_pillar=1.75, doors=4,
                  lights="rect2", grille="wide_chrome", bumper="black", tail="ribbed_wide",
                  seats="separate", wheel="four_spoke", dash_shift=False,
                  colors=[(40, 60, 90), (150, 30, 30), (200, 195, 180), (90, 110, 80), (170, 170, 175)]),
    ),
    # ------------------------------------------------------------------ BMW 316 E21
    "bmw_e21": dict(
        name="BMW 316 (E21)", short="E21", origin=T("ФРГ, BMW München"), shop="west", price=1.05,
        scrap=70, spawn=1.2, odo=(130000, 280000),
        desc=(T("M10 1.6 л, 90 л.с., задний привод, отзывчивый руль и лёгкий зад — на слякоти любит выходить "
              "в занос. Классическая ржавчина: арки, пороги, низ дверей.")),
        quirks=["rwd"],
        spec=dict(length=4.36, width=1.61, wheelbase=2.56, mass=1110.0, wheel_r=0.29, final=4.10,
                  gears={-1: -4.10, 0: 0.0, 1: 3.764, 2: 2.043, 3: 1.320, 4: 1.00},
                  idle=850, tank=52.0, oil=4.0, coolant=7.0, tq_peak=123.0, tq_rpm=4000.0, tq_width=3200.0,
                  cut=6200, overrev=6600, limiter=False, cda=0.62, carb=True,
                  two_stroke=False, air_cooled=False, diesel=False, drive="rwd",
                  grip=0.98, steer_max=34, brake=1.0, soft=0.95, sound="4t", wear=1.0,
                  axles=(0.95, 3.51), track=0.68, eye=(-0.36, 1.08, 1.95)),
        slots={"engine": T("Двигатель BMW M10 (1.6 л, 90 л.с.)"), "carb": T("Карбюратор Solex 32/32 DIDTA"),
               "gearbox": T("КПП Getrag 242"), "brakes_f": T("Колодки передние (диск)"), "brakes_r": T("Колодки задние (барабан)")},
        no_slots=[], tire="tire_165_13",
        body=dict(style="sedan", sill=0.30, belt=0.82, trunk_y=0.86, rgb=1.02, roof_start=1.55, roof_end=2.70,
                  roof_y=1.37, ws_base=3.18, hood_y=0.84, nose_y=0.72, b_pillar=2.15, doors=2,
                  lights="round4", grille="kidney", bumper="chrome", tail="wide_rect",
                  seats="separate", wheel="four_spoke", dash_shift=False,
                  colors=[(230, 225, 215), (120, 140, 60), (60, 70, 110), (160, 60, 40), (190, 190, 195)]),
    ),
    # ------------------------------------------------------------------ Audi 80 B2
    "audi80": dict(
        name="Audi 80 (B2)", short="80 B2", origin=T("ФРГ, Audi Ingolstadt"), shop="west", price=0.95,
        scrap=70, spawn=1.3, odo=(140000, 300000),
        desc=(T("1.6 л, 75 л.с., передний привод. Ровная, предсказуемая, на снегу ведёт себя лучше "
              "заднеприводных. Ржавеют пороги и низ крышки багажника.")),
        quirks=["fwd"],
        spec=dict(length=4.38, width=1.68, wheelbase=2.54, mass=1030.0, wheel_r=0.29, final=4.11,
                  gears={-1: -3.17, 0: 0.0, 1: 3.45, 2: 1.94, 3: 1.29, 4: 0.91},
                  idle=850, tank=60.0, oil=3.5, coolant=6.5, tq_peak=125.0, tq_rpm=2800.0, tq_width=3200.0,
                  cut=5800, overrev=6300, limiter=False, cda=0.64, carb=True,
                  two_stroke=False, air_cooled=False, diesel=False, drive="fwd",
                  grip=1.02, steer_max=33, brake=1.0, soft=1.05, sound="4t", wear=1.0,
                  axles=(0.85, 3.39), track=0.70, eye=(-0.36, 1.10, 1.95)),
        slots={"engine": T("Двигатель Audi 1.6 (75 л.с.)"), "carb": T("Карбюратор Keihin 2E2"),
               "gearbox": T("КПП Audi 4-ступ."), "brakes_f": T("Колодки передние (диск)"), "brakes_r": T("Колодки задние (барабан)")},
        no_slots=[], tire="tire_165_13",
        body=dict(style="sedan", sill=0.30, belt=0.82, trunk_y=0.87, rgb=1.05, roof_start=1.60, roof_end=2.78,
                  roof_y=1.38, ws_base=3.28, hood_y=0.84, nose_y=0.74, b_pillar=2.25, c_pillar=1.60, doors=4,
                  lights="rect2", grille="black_bars", bumper="black", tail="wide_rect",
                  seats="separate", wheel="four_spoke", dash_shift=False,
                  colors=[(170, 175, 180), (40, 50, 70), (160, 40, 35), (210, 200, 170), (80, 100, 70)]),
    ),
    # ------------------------------------------------------------------ Honda Civic (3-е поколение)
    "civic": dict(
        name="Honda Civic 1.5 GL", short="Civic", origin=T("Япония, Honda Suzuka"), shop="west", price=0.95,
        scrap=60, spawn=0.75, odo=(120000, 260000),
        desc=(T("Хэтчбек 1985 года: мотор EW 1.5 л 12V, 85 л.с., 5-ступенчатая КПП, 850 кг. Этот Civic — "
              "заднеприводный (привод переделан под дрифт — таких в Германии гоняют по зимним парковкам). "
              "Лёгкий, крутится до 6500 и почти не ломается, зато японский металл 80-х гниёт быстро: "
              "задние арки, пороги, низ двери багажника. Под капотом много места — сюда просится турбина "
              "(тюнинг: турбокит, интеркулер и буст-контроллер — в автосалоне Крюгера).")),
        quirks=["rwd", "tuneable"],
        spec=dict(length=3.81, width=1.63, wheelbase=2.38, mass=850.0, wheel_r=0.28, final=4.27,
                  gears={-1: -3.00, 0: 0.0, 1: 3.25, 2: 1.90, 3: 1.25, 4: 0.95, 5: 0.78},
                  idle=800, tank=45.0, oil=3.5, coolant=4.8, tq_peak=104.0, tq_rpm=3800.0, tq_width=3600.0,
                  cut=6500, overrev=6900, limiter=False, cda=0.56, carb=True,
                  two_stroke=False, air_cooled=False, diesel=False, drive="rwd",
                  grip=1.03, steer_max=35, brake=1.0, soft=1.0, sound="4t", wear=0.8,
                  axles=(0.66, 3.04), track=0.68, eye=(-0.36, 1.06, 1.62)),
        slots={"engine": T("Двигатель Honda EW 1.5 12V (85 л.с.)"), "carb": T("Карбюратор Keihin (2 камеры)"),
               "gearbox": T("КПП Honda 5-ступ."), "belt": T("Ремень ГРМ Honda"),
               "brakes_f": T("Колодки передние (диск)"), "brakes_r": T("Колодки задние (барабан)")},
        no_slots=[], tire="tire_165_13",
        body=dict(style="hatch", sill=0.29, belt=0.80, trunk_y=0.80, rgb=0.12, roof_start=0.22, roof_end=2.45,
                  roof_y=1.33, ws_base=3.05, hood_y=0.78, nose_y=0.66, b_pillar=1.95, doors=2,
                  lights="rect2", grille="black_bars", bumper="black", tail="wide_rect",
                  seats="separate", wheel="four_spoke", dash_shift=False,
                  colors=[(175, 178, 184), (170, 30, 32), (228, 226, 218), (40, 55, 95), (190, 165, 110),
                          (30, 30, 34)]),
    ),
    # ------------------------------------------------------------------ Ford Mustang 1967
    "mustang": dict(
        name="Ford Mustang 289 (1967)", short="Mustang", origin=T("США, Ford Dearborn"), shop="west", price=1.6,
        scrap=140, spawn=0.0, odo=(140000, 230000),
        desc=(T("Hardtop 1967 года, V8 289 (4.7 л, 2-камерный карбюратор, 200 л.с.), 4-ступенчатая КПП, задний привод. "
              "Привёз американский офицер из Рамштайна и продал Веберу. Длинный капот, тяжёлый нос, мягкая подвеска — "
              "на снегу заносит от одного взгляда. Автосалон Крюгера возит тюнинг-комплект Shelby GT500: большой V8 428 "
              "Cobra Jet, Toploader, подвеска, тормоза, обвес, капот, покраска — из него получится «Eleanor».")),
        quirks=["rwd", "tuneable", "v8"],
        spec=dict(length=4.61, width=1.73, wheelbase=2.74, mass=1380.0, wheel_r=0.32, final=2.8,
                  gears={-1: -2.78, 0: 0.0, 1: 2.78, 2: 1.93, 3: 1.36, 4: 1.00},
                  idle=650, tank=61.0, oil=4.7, coolant=14.0, tq_peak=300.0, tq_rpm=2600.0, tq_width=3000.0,
                  cut=4800, overrev=5400, limiter=False, cda=0.82, carb=True,
                  two_stroke=False, air_cooled=False, diesel=False, drive="rwd",
                  grip=0.95, steer_max=31, brake=0.85, soft=1.45, sound="v8", wear=0.8,
                  axles=(0.95, 3.69), track=0.74, eye=(-0.38, 1.02, 2.05)),
        slots={"engine": T("Двигатель Ford 289 V8 (4.7 л, 200 л.с.)"), "carb": T("Карбюратор Autolite 2100"),
               "gearbox": T("КПП Ford 4-ступ."), "brakes_f": T("Тормоза передние (барабан)"),
               "brakes_r": T("Тормоза задние (барабан)"), "distributor": T("Трамблёр Autolite V8"),
               "plugs": T("Свечи Autolite (8 шт.)"), "exhaust": T("Двойной глушитель V8")},
        no_slots=[], tire="tire_mustang",
        body=dict(style="sedan", sill=0.30, belt=0.80, trunk_y=0.84, rgb=0.95, roof_start=1.35, roof_end=2.45,
                  roof_y=1.30, ws_base=3.00, hood_y=0.82, nose_y=0.72, b_pillar=2.05, doors=2,
                  lights="round2", grille="egg_crate", bumper="chrome", tail="wide_rect",
                  seats="separate", wheel="two_spoke", dash_shift=False,
                  colors=[(228, 226, 218), (170, 25, 30), (30, 45, 90), (40, 80, 55), (200, 180, 110)]),
    ),
}

# Данные для случайного состояния ВАЗ-доноров (на свалке, в гаражах)
DONOR_INFO = {
    "vaz2102": dict(name=T("ВАЗ 2102"), quirks=[], odo=(120000, 320000),
                    body=dict(colors=[(196, 186, 150), (180, 40, 35), (230, 230, 220), (70, 110, 150), (120, 140, 90)])),
}


def model_info(model):
    return MODELS.get(model) or DONOR_INFO.get(model)


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
