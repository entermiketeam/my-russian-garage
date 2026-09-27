"""Каталог предметов: еда, расходники, инструменты и запчасти ВАЗ 2102.

Цены в немецких марках (DM), 1998 год.
Запчасти «Жигулей» в Германии — редкость, поэтому они дорогие и их везут
из магазина «Ost-Autoteile» (там торгует переселенец из Казахстана).
"""

# Слоты автомобиля: id -> (название, id запчасти, минут на замену)
SLOTS = {
    "engine":      ("Двигатель 2101 (1.2 л)", "engine", 480),
    "battery":     ("Аккумулятор", "battery", 10),
    "plugs":       ("Свечи зажигания", "plugs", 20),
    "distributor": ("Трамблёр", "distributor", 40),
    "carb":        ("Карбюратор ДААЗ", "carb", 60),
    "fuel_pump":   ("Бензонасос", "fuel_pump", 30),
    "fuel_filter": ("Топливный фильтр", "fuel_filter", 10),
    "air_filter":  ("Воздушный фильтр", "air_filter", 5),
    "starter":     ("Стартер", "starter", 45),
    "alternator":  ("Генератор Г-221", "alternator", 45),
    "belt":        ("Ремень генератора", "belt", 15),
    "radiator":    ("Радиатор", "radiator", 60),
    "clutch":      ("Диск сцепления", "clutch", 180),
    "brakes_f":    ("Колодки передние", "brakes_f", 40),
    "brakes_r":    ("Колодки задние (барабан)", "brakes_r", 60),
    "shocks":      ("Амортизаторы", "shocks", 90),
    "exhaust":     ("Глушитель", "exhaust", 50),
    "lights":      ("Фары", "lights", 30),
    "tire_fl":     ("Шина перед. лев.", "tire", 20),
    "tire_fr":     ("Шина перед. прав.", "tire", 20),
    "tire_rl":     ("Шина зад. лев.", "tire", 20),
    "tire_rr":     ("Шина зад. прав.", "tire", 20),
}

# Слоты Toyota AE86: те же ключи, свои детали (японские, дорогие — везут через Autohaus Krüger)
SLOTS_AE86 = {
    "engine":      ("Двигатель 4A-GE (1.6 16V)", "ae_engine", 540),
    "battery":     ("Аккумулятор", "battery", 10),
    "plugs":       ("Свечи зажигания Denso", "ae_plugs", 25),
    "distributor": ("Трамблёр Toyota", "ae_distributor", 45),
    "carb":        ("Форсунки впрыска (EFI)", "ae_injectors", 70),
    "fuel_pump":   ("Электробензонасос", "ae_fuel_pump", 40),
    "fuel_filter": ("Топливный фильтр", "ae_fuel_filter", 15),
    "air_filter":  ("Воздушный фильтр", "ae_air_filter", 5),
    "starter":     ("Стартер", "ae_starter", 45),
    "alternator":  ("Генератор", "ae_alternator", 45),
    "belt":        ("Ремень ГРМ (!)", "ae_belt", 150),
    "radiator":    ("Радиатор", "ae_radiator", 60),
    "clutch":      ("Сцепление", "ae_clutch", 200),
    "brakes_f":    ("Колодки передние", "ae_brakes_f", 40),
    "brakes_r":    ("Колодки задние", "ae_brakes_r", 40),
    "shocks":      ("Амортизаторы", "ae_shocks", 100),
    "exhaust":     ("Глушитель", "ae_exhaust", 50),
    "lights":      ("Фары (поднимающиеся)", "ae_lights", 45),
    "tire_fl":     ("Шина перед. лев.", "ae_tire", 20),
    "tire_fr":     ("Шина перед. прав.", "ae_tire", 20),
    "tire_rl":     ("Шина зад. лев.", "ae_tire", 20),
    "tire_rr":     ("Шина зад. прав.", "ae_tire", 20),
}

SLOTS_BY_MODEL = {"vaz2102": SLOTS, "ae86": SLOTS_AE86}

# Кузовные панели (ржавчина)
PANELS = {
    "sill_l":   "Порог левый",
    "sill_r":   "Порог правый",
    "floor":    "Днище",
    "arch_f":   "Передние арки",
    "arch_r":   "Задние арки",
    "fender":   "Крылья",
    "doors":    "Низ дверей",
    "tailgate": "Дверь багажника",
}

# id -> словарь свойств
# kind: food / drink / part / fluid / tool / material
ITEMS = {
    # ---- Еда и напитки (Supermarkt) ----
    "brot":      dict(name="Brot (хлеб)", kind="food", price=2.5, hunger=25),
    "wurst":     dict(name="Bratwurst (колбаски)", kind="food", price=4.0, hunger=35),
    "pizza_tk":  dict(name="Tiefkühlpizza (заморож.)", kind="food", price=3.5, hunger=10,
                      note="Лучше разогреть на плите дома"),
    "pizza_hot": dict(name="Горячая пицца", kind="food", price=0, hunger=60),
    "apfel":     dict(name="Äpfel (яблоки)", kind="food", price=2.0, hunger=12, thirst=5),
    "wasser":    dict(name="Mineralwasser 1.5 л", kind="drink", price=0.9, thirst=45),
    "cola":      dict(name="Cola", kind="drink", price=1.5, thirst=30, energy=6),
    "kaffee":    dict(name="Kaffee (кофе)", kind="drink", price=6.0, thirst=10, energy=25),
    "bier":      dict(name="Bier (пиво 0.5)", kind="drink", price=1.2, thirst=20, drunk=18),
    "doener":    dict(name="Döner Kebab", kind="food", price=6.0, hunger=55),

    # ---- Жидкости ----
    "fuel_can":  dict(name="Канистра бензина 10 л", kind="fluid", price=22.0),
    "oil":       dict(name="Моторное масло 15W-40, 4 л", kind="fluid", price=24.0),
    "coolant":   dict(name="Антифриз, 5 л", kind="fluid", price=15.0),
    "brake_fl":  dict(name="Тормозная жидкость", kind="fluid", price=9.0),

    # ---- Инструменты / материалы ----
    "toolbox":   dict(name="Набор ключей", kind="tool", price=85.0),
    "rope":      dict(name="Буксировочный трос (Abschleppseil)", kind="tool", price=15.0),
    "crowbar":   dict(name="Монтировка (Brecheisen)", kind="tool", price=12.0),
    "old_radio": dict(name="Старая магнитола Blaupunkt", kind="part", price=60.0),
    "jerrycan_old": dict(name="Старая канистра с бензином (5 л)", kind="fluid", price=8.0),
    "charger":   dict(name="Зарядное устройство", kind="tool", price=69.0),
    "welder":    dict(name="Сварочный аппарат", kind="tool", price=320.0),
    "metal":     dict(name="Лист металла", kind="material", price=18.0),
    "paint":     dict(name="Грунт + краска (баллон)", kind="material", price=14.0),
    "rust_conv": dict(name="Преобразователь ржавчины", kind="material", price=11.0),

    # ---- Запчасти (новые). slot = id запчасти ----
    "engine":      dict(name="Двигатель 2101 (контрактный)", kind="part", price=950.0),
    "battery":     dict(name="Аккумулятор 55 А·ч", kind="part", price=110.0),
    "plugs":       dict(name="Свечи А17ДВ (4 шт.)", kind="part", price=16.0),
    "distributor": dict(name="Трамблёр 2101", kind="part", price=65.0),
    "carb":        dict(name="Карбюратор ДААЗ-2101", kind="part", price=180.0),
    "fuel_pump":   dict(name="Бензонасос", kind="part", price=45.0),
    "fuel_filter": dict(name="Топливный фильтр", kind="part", price=6.0),
    "air_filter":  dict(name="Воздушный фильтр", kind="part", price=9.0),
    "starter":     dict(name="Стартер", kind="part", price=140.0),
    "alternator":  dict(name="Генератор Г-221", kind="part", price=160.0),
    "belt":        dict(name="Ремень генератора", kind="part", price=12.0),
    "radiator":    dict(name="Радиатор медный", kind="part", price=150.0),
    "clutch":      dict(name="Диск сцепления", kind="part", price=90.0),
    "brakes_f":    dict(name="Колодки передние", kind="part", price=35.0),
    "brakes_r":    dict(name="Колодки задние", kind="part", price=40.0),
    "shocks":      dict(name="Амортизаторы (компл.)", kind="part", price=120.0),
    "exhaust":     dict(name="Глушитель", kind="part", price=75.0),
    "lights":      dict(name="Фары (пара)", kind="part", price=60.0),
    "tire":        dict(name="Шина 165/80 R13", kind="part", price=55.0),

    # ---- Запчасти Toyota AE86 (Autohaus Krüger, заказ из Японии/Голландии) ----
    "ae_engine":      dict(name="Двигатель 4A-GE (контрактный, Япония)", kind="part", price=1450.0),
    "ae_plugs":       dict(name="Свечи Denso (4 шт.) для 4A-GE", kind="part", price=28.0),
    "ae_distributor": dict(name="Трамблёр Toyota 4A-GE", kind="part", price=190.0),
    "ae_injectors":   dict(name="Форсунки EFI (комплект 4 шт.)", kind="part", price=240.0),
    "ae_fuel_pump":   dict(name="Электробензонасос Toyota", kind="part", price=130.0),
    "ae_fuel_filter": dict(name="Топливный фильтр Toyota", kind="part", price=19.0),
    "ae_air_filter":  dict(name="Воздушный фильтр Toyota", kind="part", price=22.0),
    "ae_starter":     dict(name="Стартер Toyota", kind="part", price=210.0),
    "ae_alternator":  dict(name="Генератор Toyota", kind="part", price=240.0),
    "ae_belt":        dict(name="Ремень ГРМ + ролик 4A-GE", kind="part", price=85.0),
    "ae_radiator":    dict(name="Радиатор AE86", kind="part", price=220.0),
    "ae_clutch":      dict(name="Комплект сцепления AE86", kind="part", price=230.0),
    "ae_brakes_f":    dict(name="Колодки передние AE86", kind="part", price=60.0),
    "ae_brakes_r":    dict(name="Колодки задние AE86 (диск)", kind="part", price=60.0),
    "ae_shocks":      dict(name="Амортизаторы Tokico (компл.)", kind="part", price=390.0),
    "ae_exhaust":     dict(name="Глушитель AE86", kind="part", price=180.0),
    "ae_lights":      dict(name="Поднимающиеся фары (пара)", kind="part", price=160.0),
    "ae_tire":        dict(name="Шина 185/70 R13", kind="part", price=82.0),
}

SHOP_SUPERMARKT = ["brot", "wurst", "pizza_tk", "apfel", "wasser", "cola", "kaffee", "bier"]
SHOP_TEILE = ["battery", "plugs", "distributor", "carb", "fuel_pump", "fuel_filter", "air_filter",
              "starter", "alternator", "belt", "radiator", "clutch", "brakes_f", "brakes_r",
              "shocks", "exhaust", "lights", "tire", "oil", "coolant", "brake_fl", "fuel_can",
              "metal", "paint", "rust_conv", "toolbox", "rope", "charger", "welder"]
SHOP_TANKE = ["fuel_can", "oil", "coolant", "rope", "crowbar", "wasser", "cola", "kaffee", "bier"]
SHOP_IMBISS = ["doener", "cola", "bier"]
SHOP_TOYOTA = ["ae_engine", "ae_plugs", "ae_distributor", "ae_injectors", "ae_fuel_pump", "ae_fuel_filter",
               "ae_air_filter", "ae_starter", "ae_alternator", "ae_belt", "ae_radiator", "ae_clutch",
               "ae_brakes_f", "ae_brakes_r", "ae_shocks", "ae_exhaust", "ae_lights", "ae_tire",
               "battery", "oil", "coolant", "brake_fl"]


def item_name(item_id):
    return ITEMS.get(item_id, {}).get("name", item_id)


def part_for_slot(slot, model="vaz2102"):
    return SLOTS_BY_MODEL[model][slot][1]


def slots_for_part(part_id):
    out = []
    for slots in SLOTS_BY_MODEL.values():
        out += [s for s, v in slots.items() if v[1] == part_id and s not in out]
    return out


# ====================================================================== новые общие слоты и модели-находки
from models import MODELS, SLOT_ORDER, model_slots, model_items   # noqa: E402

# КПП, проводка, рулевое и стекло теперь есть у всех машин
SLOTS.update({
    "gearbox":  ("Коробка передач 2101 (4-ступ.)", "gearbox", 240),
    "wiring":   ("Электропроводка", "wiring", 150),
    "steering": ("Рулевые тяги + маятник", "steering", 60),
    "glass":    ("Лобовое стекло", "glass", 90),
})
SLOTS.update({
    "door_l": ("Двери левые (с разборки!)", "door_l", 40), "door_r": ("Двери правые", "door_r", 40),
    "hood": ("Капот", "hood", 20), "trunk": ("Дверь багажника", "trunk", 25), "seats": ("Сиденья", "seats", 40),
})
SLOTS_AE86.update({
    "door_l": ("Дверь левая", "ae_door_l", 40), "door_r": ("Дверь правая", "ae_door_r", 40),
    "hood": ("Капот", "ae_hood", 20), "trunk": ("Дверь багажника (люк)", "ae_trunk", 25),
    "seats": ("Ковшеобразные сиденья", "ae_seats", 40),
})
SLOTS_AE86.update({
    "gearbox":  ("КПП T50 (5-ступ.)", "ae_gearbox", 240),
    "wiring":   ("Электропроводка", "ae_wiring", 150),
    "steering": ("Рулевая рейка и тяги", "ae_steering", 60),
    "glass":    ("Лобовое стекло", "ae_glass", 90),
})


def _reorder(slots):
    return {k: slots[k] for k in SLOT_ORDER if k in slots}


SLOTS = _reorder(SLOTS)
SLOTS_AE86 = _reorder(SLOTS_AE86)
SLOTS_BY_MODEL["vaz2102"] = SLOTS
SLOTS_BY_MODEL["ae86"] = SLOTS_AE86
for _m in MODELS:
    SLOTS_BY_MODEL[_m] = model_slots(_m)

ITEMS.update({
    "gearbox":     dict(name="КПП 2101 (4-ступ.)", kind="part", price=230.0),
    "wiring":      dict(name="Жгут проводки ВАЗ", kind="part", price=65.0),
    "steering":    dict(name="Рулевые тяги + маятник ВАЗ", kind="part", price=45.0),
    "glass":       dict(name="Лобовое стекло ВАЗ", kind="part", price=75.0),
    "ae_gearbox":  dict(name="КПП T50 (5-ступ.) AE86", kind="part", price=420.0),
    "ae_wiring":   dict(name="Жгут проводки AE86", kind="part", price=150.0),
    "ae_steering": dict(name="Рулевая рейка и тяги AE86", kind="part", price=160.0),
    "ae_glass":    dict(name="Лобовое стекло AE86", kind="part", price=190.0),
    "door_l":      dict(name="Дверь левая ВАЗ 2102 (пара)", kind="part", price=90.0),
    "door_r":      dict(name="Дверь правая ВАЗ 2102 (пара)", kind="part", price=90.0),
    "hood":        dict(name="Капот ВАЗ 2102", kind="part", price=70.0),
    "trunk":       dict(name="Дверь багажника ВАЗ 2102", kind="part", price=85.0),
    "seats":       dict(name="Сиденья ВАЗ (комплект)", kind="part", price=60.0),
    "ae_door_l":   dict(name="Дверь левая AE86", kind="part", price=240.0),
    "ae_door_r":   dict(name="Дверь правая AE86", kind="part", price=240.0),
    "ae_hood":     dict(name="Капот AE86", kind="part", price=210.0),
    "ae_trunk":    dict(name="Дверь багажника AE86 (люк со стеклом)", kind="part", price=260.0),
    "ae_seats":    dict(name="Ковшеобразные сиденья AE86", kind="part", price=280.0),
})
ITEMS.update(model_items())
SHOP_TEILE += ["gearbox", "wiring", "steering", "glass", "door_l", "door_r", "hood", "trunk", "seats"]
SHOP_TOYOTA += ["ae_gearbox", "ae_wiring", "ae_steering", "ae_glass", "ae_door_l", "ae_door_r", "ae_hood",
                "ae_trunk", "ae_seats"]

CONSUMABLES = ["battery", "oil", "coolant", "brake_fl", "fuel_can", "rope", "crowbar", "metal", "paint", "rust_conv"]


def shop_for_model(model):
    """Список запчастей для машины этой модели (без повторов)."""
    ids = []
    for s, (name, pid, _) in SLOTS_BY_MODEL[model].items():
        if pid not in ids:
            ids.append(pid)
    return ids


# Где продаются запчасти: Ost-Autoteile — восточные машины, Autohaus Krüger — Toyota и западные
SHOP_MODELS = {
    "ost": ["vaz2102", "trabant", "wartburg", "moskvich"],
    "west": ["ae86", "kadett", "golf", "taunus", "w123", "volvo240", "bmw_e21", "audi80"],
}
MODEL_NAMES = {"vaz2102": "ВАЗ 2102", "ae86": "Toyota AE86"}
MODEL_NAMES.update({m: info["name"] for m, info in MODELS.items()})
