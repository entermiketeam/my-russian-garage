"""Каталог предметов: еда, расходники, инструменты и запчасти ВАЗ 2102.

Цены в рублях (₽), 1998 год.
Запчасти «Жигулей» в Германии — редкость, поэтому они дорогие и их везут
из магазина «Ost-Autoteile» (там торгует переселенец из Казахстана).
"""

from i18n import T

# Слоты автомобиля: id -> (название, id запчасти, минут на замену)
SLOTS = {
    "engine":      (T("Двигатель 2101 (1.2 л)"), "engine", 480),
    "battery":     (T("Аккумулятор"), "battery", 10),
    "plugs":       (T("Свечи зажигания"), "plugs", 20),
    "distributor": (T("Трамблёр"), "distributor", 40),
    "carb":        (T("Карбюратор ДААЗ"), "carb", 60),
    "fuel_pump":   (T("Бензонасос"), "fuel_pump", 30),
    "fuel_filter": (T("Топливный фильтр"), "fuel_filter", 10),
    "air_filter":  (T("Воздушный фильтр"), "air_filter", 5),
    "starter":     (T("Стартер"), "starter", 45),
    "alternator":  (T("Генератор Г-221"), "alternator", 45),
    "belt":        (T("Ремень генератора"), "belt", 15),
    "radiator":    (T("Радиатор"), "radiator", 60),
    "clutch":      (T("Диск сцепления"), "clutch", 180),
    "brakes_f":    (T("Колодки передние"), "brakes_f", 40),
    "brakes_r":    (T("Колодки задние (барабан)"), "brakes_r", 60),
    "shocks":      (T("Амортизаторы"), "shocks", 90),
    "exhaust":     (T("Глушитель"), "exhaust", 50),
    "lights":      (T("Фары"), "lights", 30),
    "tire_fl":     (T("Шина перед. лев."), "tire", 20),
    "tire_fr":     (T("Шина перед. прав."), "tire", 20),
    "tire_rl":     (T("Шина зад. лев."), "tire", 20),
    "tire_rr":     (T("Шина зад. прав."), "tire", 20),
}

# Слоты Toyota AE86: те же ключи, свои детали (японские, дорогие — везут через Autohaus Krüger)
SLOTS_AE86 = {
    "engine":      (T("Двигатель 4A-GE (1.6 16V)"), "ae_engine", 540),
    "battery":     (T("Аккумулятор"), "battery", 10),
    "plugs":       (T("Свечи зажигания Denso"), "ae_plugs", 25),
    "distributor": (T("Трамблёр Toyota"), "ae_distributor", 45),
    "carb":        (T("Форсунки впрыска (EFI)"), "ae_injectors", 70),
    "fuel_pump":   (T("Электробензонасос"), "ae_fuel_pump", 40),
    "fuel_filter": (T("Топливный фильтр"), "ae_fuel_filter", 15),
    "air_filter":  (T("Воздушный фильтр"), "ae_air_filter", 5),
    "starter":     (T("Стартер"), "ae_starter", 45),
    "alternator":  (T("Генератор"), "ae_alternator", 45),
    "belt":        (T("Ремень ГРМ (!)"), "ae_belt", 150),
    "radiator":    (T("Радиатор"), "ae_radiator", 60),
    "clutch":      (T("Сцепление"), "ae_clutch", 200),
    "brakes_f":    (T("Колодки передние"), "ae_brakes_f", 40),
    "brakes_r":    (T("Колодки задние"), "ae_brakes_r", 40),
    "shocks":      (T("Амортизаторы"), "ae_shocks", 100),
    "exhaust":     (T("Глушитель"), "ae_exhaust", 50),
    "lights":      (T("Фары (поднимающиеся)"), "ae_lights", 45),
    "tire_fl":     (T("Шина перед. лев."), "ae_tire", 20),
    "tire_fr":     (T("Шина перед. прав."), "ae_tire", 20),
    "tire_rl":     (T("Шина зад. лев."), "ae_tire", 20),
    "tire_rr":     (T("Шина зад. прав."), "ae_tire", 20),
}

SLOTS_BY_MODEL = {"vaz2102": SLOTS, "ae86": SLOTS_AE86}

# Кузовные панели (ржавчина)
PANELS = {
    "sill_l":   T("Порог левый"),
    "sill_r":   T("Порог правый"),
    "floor":    T("Днище"),
    "arch_f":   T("Передние арки"),
    "arch_r":   T("Задние арки"),
    "fender":   T("Крылья"),
    "doors":    T("Низ дверей"),
    "tailgate": T("Дверь багажника"),
}

# id -> словарь свойств
# kind: food / drink / part / fluid / tool / material
ITEMS = {
    # ---- Еда и напитки (Supermarkt) ----
    "brot":      dict(name=T("Хлеб"), kind="food", price=2.5, hunger=25),
    "wurst":     dict(name=T("Жареные колбаски"), kind="food", price=4.0, hunger=35),
    "pizza_tk":  dict(name=T("Замороженная пицца"), kind="food", price=3.5, hunger=10,
                      note=T("Лучше разогреть на плите дома")),
    "pizza_hot": dict(name=T("Горячая пицца"), kind="food", price=0, hunger=60),
    "apfel":     dict(name=T("Яблоки"), kind="food", price=2.0, hunger=12, thirst=5),
    "wasser":    dict(name=T("Минеральная вода 1,5 л"), kind="drink", price=0.9, thirst=45),
    "cola":      dict(name=T("Кола"), kind="drink", price=1.5, thirst=30, energy=6),
    "kaffee":    dict(name=T("Кофе"), kind="drink", price=6.0, thirst=10, energy=25),
    "bier":      dict(name=T("Пиво 0,5"), kind="drink", price=1.2, thirst=20, drunk=18),
    "doener":    dict(name=T("Дёнер-кебаб"), kind="food", price=6.0, hunger=55),

    # ---- Жидкости ----
    "fuel_can":  dict(name=T("Канистра бензина 10 л"), kind="fluid", price=22.0),
    "oil":       dict(name=T("Моторное масло 15W-40, 4 л"), kind="fluid", price=24.0),
    "coolant":   dict(name=T("Антифриз, 5 л"), kind="fluid", price=15.0),
    "brake_fl":  dict(name=T("Тормозная жидкость"), kind="fluid", price=9.0),

    # ---- Инструменты / материалы ----
    "toolbox":   dict(name=T("Набор ключей"), kind="tool", price=85.0),
    "rope":      dict(name=T("Буксировочный трос"), kind="tool", price=15.0),
    "crowbar":   dict(name=T("Монтировка"), kind="tool", price=12.0),
    "old_radio": dict(name=T("Старая магнитола Blaupunkt"), kind="part", price=60.0),
    "jerrycan_old": dict(name=T("Старая канистра с бензином (5 л)"), kind="fluid", price=8.0),
    "charger":   dict(name=T("Зарядное устройство"), kind="tool", price=69.0),
    "welder":    dict(name=T("Сварочный аппарат"), kind="tool", price=320.0),
    "metal":     dict(name=T("Лист металла"), kind="material", price=18.0),
    "paint":     dict(name=T("Грунт + краска (баллон)"), kind="material", price=14.0),
    "rust_conv": dict(name=T("Преобразователь ржавчины"), kind="material", price=11.0),

    # ---- Запчасти (новые). slot = id запчасти ----
    "engine":      dict(name=T("Двигатель 2101 (контрактный)"), kind="part", price=950.0),
    "battery":     dict(name=T("Аккумулятор 55 А·ч"), kind="part", price=110.0),
    "plugs":       dict(name=T("Свечи А17ДВ (4 шт.)"), kind="part", price=16.0),
    "distributor": dict(name=T("Трамблёр 2101"), kind="part", price=65.0),
    "carb":        dict(name=T("Карбюратор ДААЗ-2101"), kind="part", price=180.0),
    "fuel_pump":   dict(name=T("Бензонасос"), kind="part", price=45.0),
    "fuel_filter": dict(name=T("Топливный фильтр"), kind="part", price=6.0),
    "air_filter":  dict(name=T("Воздушный фильтр"), kind="part", price=9.0),
    "starter":     dict(name=T("Стартер"), kind="part", price=140.0),
    "alternator":  dict(name=T("Генератор Г-221"), kind="part", price=160.0),
    "belt":        dict(name=T("Ремень генератора"), kind="part", price=12.0),
    "radiator":    dict(name=T("Радиатор медный"), kind="part", price=150.0),
    "clutch":      dict(name=T("Диск сцепления"), kind="part", price=90.0),
    "brakes_f":    dict(name=T("Колодки передние"), kind="part", price=35.0),
    "brakes_r":    dict(name=T("Колодки задние"), kind="part", price=40.0),
    "shocks":      dict(name=T("Амортизаторы (компл.)"), kind="part", price=120.0),
    "exhaust":     dict(name=T("Глушитель"), kind="part", price=75.0),
    "lights":      dict(name=T("Фары (пара)"), kind="part", price=60.0),
    "tire":        dict(name=T("Шина 165/80 R13"), kind="part", price=55.0),

    # ---- Запчасти Toyota AE86 (Autohaus Krüger, заказ из Японии/Голландии) ----
    "ae_engine":      dict(name=T("Двигатель 4A-GE (контрактный, Япония)"), kind="part", price=1450.0),
    "ae_plugs":       dict(name=T("Свечи Denso (4 шт.) для 4A-GE"), kind="part", price=28.0),
    "ae_distributor": dict(name=T("Трамблёр Toyota 4A-GE"), kind="part", price=190.0),
    "ae_injectors":   dict(name=T("Форсунки EFI (комплект 4 шт.)"), kind="part", price=240.0),
    "ae_fuel_pump":   dict(name=T("Электробензонасос Toyota"), kind="part", price=130.0),
    "ae_fuel_filter": dict(name=T("Топливный фильтр Toyota"), kind="part", price=19.0),
    "ae_air_filter":  dict(name=T("Воздушный фильтр Toyota"), kind="part", price=22.0),
    "ae_starter":     dict(name=T("Стартер Toyota"), kind="part", price=210.0),
    "ae_alternator":  dict(name=T("Генератор Toyota"), kind="part", price=240.0),
    "ae_belt":        dict(name=T("Ремень ГРМ + ролик 4A-GE"), kind="part", price=85.0),
    "ae_radiator":    dict(name=T("Радиатор AE86"), kind="part", price=220.0),
    "ae_clutch":      dict(name=T("Комплект сцепления AE86"), kind="part", price=230.0),
    "ae_brakes_f":    dict(name=T("Колодки передние AE86"), kind="part", price=60.0),
    "ae_brakes_r":    dict(name=T("Колодки задние AE86 (диск)"), kind="part", price=60.0),
    "ae_shocks":      dict(name=T("Амортизаторы Tokico (компл.)"), kind="part", price=390.0),
    "ae_exhaust":     dict(name=T("Глушитель AE86"), kind="part", price=180.0),
    "ae_lights":      dict(name=T("Поднимающиеся фары (пара)"), kind="part", price=160.0),
    "ae_tire":        dict(name=T("Шина 185/70 R13"), kind="part", price=82.0),
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
    "gearbox":  (T("Коробка передач 2101 (4-ступ.)"), "gearbox", 240),
    "wiring":   (T("Электропроводка"), "wiring", 150),
    "steering": (T("Рулевые тяги + маятник"), "steering", 60),
    "glass":    (T("Лобовое стекло"), "glass", 90),
})
SLOTS.update({
    "door_l": (T("Двери левые (с разборки!)"), "door_l", 40), "door_r": (T("Двери правые"), "door_r", 40),
    "hood": (T("Капот"), "hood", 20), "trunk": (T("Дверь багажника"), "trunk", 25), "seats": (T("Сиденья"), "seats", 40),
})
SLOTS_AE86.update({
    "door_l": (T("Дверь левая"), "ae_door_l", 40), "door_r": (T("Дверь правая"), "ae_door_r", 40),
    "hood": (T("Капот"), "ae_hood", 20), "trunk": (T("Дверь багажника (люк)"), "ae_trunk", 25),
    "seats": (T("Ковшеобразные сиденья"), "ae_seats", 40),
})
SLOTS_AE86.update({
    "gearbox":  (T("КПП T50 (5-ступ.)"), "ae_gearbox", 240),
    "wiring":   (T("Электропроводка"), "ae_wiring", 150),
    "steering": (T("Рулевая рейка и тяги"), "ae_steering", 60),
    "glass":    (T("Лобовое стекло"), "ae_glass", 90),
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
    "gearbox":     dict(name=T("КПП 2101 (4-ступ.)"), kind="part", price=230.0),
    "wiring":      dict(name=T("Жгут проводки ВАЗ"), kind="part", price=65.0),
    "steering":    dict(name=T("Рулевые тяги + маятник ВАЗ"), kind="part", price=45.0),
    "glass":       dict(name=T("Лобовое стекло ВАЗ"), kind="part", price=75.0),
    "ae_gearbox":  dict(name=T("КПП T50 (5-ступ.) AE86"), kind="part", price=420.0),
    "ae_wiring":   dict(name=T("Жгут проводки AE86"), kind="part", price=150.0),
    "ae_steering": dict(name=T("Рулевая рейка и тяги AE86"), kind="part", price=160.0),
    "ae_glass":    dict(name=T("Лобовое стекло AE86"), kind="part", price=190.0),
    "door_l":      dict(name=T("Дверь левая ВАЗ 2102 (пара)"), kind="part", price=90.0),
    "door_r":      dict(name=T("Дверь правая ВАЗ 2102 (пара)"), kind="part", price=90.0),
    "hood":        dict(name=T("Капот ВАЗ 2102"), kind="part", price=70.0),
    "trunk":       dict(name=T("Дверь багажника ВАЗ 2102"), kind="part", price=85.0),
    "seats":       dict(name=T("Сиденья ВАЗ (комплект)"), kind="part", price=60.0),
    "ae_door_l":   dict(name=T("Дверь левая AE86"), kind="part", price=240.0),
    "ae_door_r":   dict(name=T("Дверь правая AE86"), kind="part", price=240.0),
    "ae_hood":     dict(name=T("Капот AE86"), kind="part", price=210.0),
    "ae_trunk":    dict(name=T("Дверь багажника AE86 (люк со стеклом)"), kind="part", price=260.0),
    "ae_seats":    dict(name=T("Ковшеобразные сиденья AE86"), kind="part", price=280.0),
})
ITEMS.update(model_items())
from tuning import TUNE_ITEMS, tune_items_for   # noqa: E402
ITEMS.update(TUNE_ITEMS)
import engine as _engine   # noqa: E402
ITEMS.update(_engine.items())          # внутренние детали двигателей: ГБЦ, поршни, вкладыши, помпа...
import electrics as _electrics   # noqa: E402
ITEMS.update(_electrics.ITEM_DEFS)     # электрика: предохранители, мультиметр, лампы, реле...
ITEMS["key"] = dict(name=T("Ключ зажигания"), kind="key", price=0.0)           # у каждого свой код (keys.py)
ITEMS["lockset"] = dict(name=T("Комплект замков: личинки дверей + замок зажигания (2 новых ключа)"), kind="part", price=45.0)
ITEMS["compressor"] = dict(name=T("Автомобильный компрессор 12 В с манометром"), kind="tool", price=35.0)
ITEMS["tire_gauge"] = dict(name=T("Манометр для шин"), kind="tool", price=6.0)
ITEMS["flyer"] = dict(name=T("Листовки «Угнана машина!» (объявления об угоне)"), kind="material", price=5.0)
_ELEC_SHOP = ["fuse_set", "multimeter", "wire_kit", "bulb", "relay", "coil", "horn", "lockset", "compressor", "tire_gauge"]
SHOP_TANKE += ["fuse_set", "bulb", "tire_gauge", "compressor"]
SHOP_TOYOTA += _ELEC_SHOP
SHOP_TEILE += _ELEC_SHOP + ["gearbox", "wiring", "steering", "glass", "door_l", "door_r", "hood", "trunk", "seats"]
SHOP_TOYOTA += ["ae_gearbox", "ae_wiring", "ae_steering", "ae_glass", "ae_door_l", "ae_door_r", "ae_hood",
                "ae_trunk", "ae_seats"]

ITEMS["jack"] = dict(name=T("Домкрат подкатной (2 т)"), kind="tool", price=59.0)
ITEMS["stands"] = dict(name=T("Подставки под машину (пара)"), kind="tool", price=29.0)
CONSUMABLES = ["battery", "oil", "coolant", "brake_fl", "fuel_can", "rope", "crowbar", "metal", "paint", "rust_conv",
               "jack", "stands"]


def shop_for_model(model):
    """Список запчастей для машины этой модели (без повторов)."""
    ids = []
    for s, (name, pid, _) in SLOTS_BY_MODEL[model].items():
        if pid not in ids:
            ids.append(pid)
    if model in _engine.LAYOUTS:           # детали двигателя «до болтика» — после навесного
        ids += [_engine.part_id(model, k) for k in _engine.keys(model)]
    ids += [pid for pid in tune_items_for(model) if pid not in ids]   # тюнинг — в конце списка
    return ids


# Где продаются запчасти: Ost-Autoteile — восточные машины, Autohaus Krüger — Toyota и западные
SHOP_MODELS = {
    "ost": ["vaz2102", "trabant", "wartburg", "moskvich"],
    "west": ["ae86", "kadett", "golf", "taunus", "w123", "volvo240", "bmw_e21", "audi80", "civic", "mustang"],
}
MODEL_NAMES = {"vaz2102": T("ВАЗ 2102"), "ae86": "Toyota AE86"}
MODEL_NAMES.update({m: info["name"] for m, info in MODELS.items()})
