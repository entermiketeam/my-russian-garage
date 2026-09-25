"""Игровые действия и меню, не зависящие от графики (используются в 3D-версии).

Меню — это «модели»: у них есть заголовок, строки текста и пункты.
Графическая часть (ui3d.py) только рисует их и передаёт нажатия.

select(payload) возвращает:
  None       — остаться в меню (оно перерисуется),
  "close"    — закрыть меню,
  callable   — закрыть меню и затем вызвать функцию (она может открыть новое меню).
"""
import math
import random

from items import (ITEMS, SLOTS, SLOTS_BY_MODEL, PANELS, item_name, SHOP_SUPERMARKT, SHOP_TEILE, SHOP_TANKE,
                   SHOP_IMBISS, SHOP_TOYOTA, SHOP_MODELS, MODEL_NAMES, CONSUMABLES, shop_for_model)
from models import MODELS
from world import BUILDINGS, BLITZER, PUMP_ZONE, TUV_YARD, GARAGE, PARKING2, SCRAP_DROP, point_in
from state import WHITE, RED, GREEN, YELLOW, RENT, AE86_PRICE, CAR_NAMES, ROPE_SNAP_KMH, MAIN_CARS

ORANGE = (230, 140, 40)
FUEL_PRICE = 1.65
DIESEL_PRICE = 1.29      # дизель в 1998 году был дешевле бензина
MIX_EXTRA = 0.06         # двухтактная смесь 1:50 (бензин + 2T-масло) — чуть дороже
WASH_PRICE = 8.0
CLOSE = "__close__"

NEWS = [
    "Tagesschau: Герхард Шрёдер (SPD) выиграл выборы в Бундестаг. Конец эпохи Коля.",
    "Tagesschau: С 1 января 1999 года евро введут в безналичных расчётах. Марка пока остаётся.",
    "Sportschau: «Бавария» лидирует в Бундеслиге, «Кайзерслаутерн» — действующий чемпион.",
    "Wetter: в Нижней Саксонии дожди, ночью до +4 °C. Берегите машины от сырости.",
    "Werbung: «Opel Astra — ab 26.990 DM!» Вы смотрите на свои ржавые пороги и вздыхаете.",
    "Tagesschau: Цены на бензин выросли до 1,65 DM за литр. Автоклубы возмущены.",
    "Регион: В Kleinbruck полиция усилила контроль техосмотра старых автомобилей.",
    "Wer wird Millionär? Вы отвечаете на три вопроса и чувствуете себя умным.",
]

CONTROLS = [
    "ПЕШКОМ: WASD — идти, мышь — смотреть, Shift — бежать, E — действие, F — сесть в машину.",
    "Tab — инвентарь, M — карта, Esc — пауза, «-» / «=» — чувствительность мыши.",
    "ЗА РУЛЁМ: W — газ, S — тормоз, A/D — руль, Пробел — сцепление (держать).",
    "Shift / Ctrl — передача вверх/вниз (или 1-4, R — задняя, N — нейтраль).",
    "I (держать) — стартер / заглушить, C — подсос, L — фары, H — гудок, V — вид (салон / сзади).",
    "F — выйти, E — действие (заправка, TÜV, доставка, сдать машину на лом).",
    "T — буксировочный трос: привязать брошенную машину (или свою) к машине рядом / отвязать.",
    "НАХОДКИ: брошенные машины у дорог (серые точки на карте) можно ЗАБРАТЬ СЕБЕ бесплатно (E у машины),",
    "дотащить тросом до гаража, восстановить и ездить. Сдать на лом — только если сами захотите.",
    "У машины: E — открыть капот (детали, жидкости, сварка). Мышь/колесо — осмотр машины.",
    "",
    "СОВЕТЫ: холодный мотор заводится только с подсосом (C). Трогайтесь с 1-й передачи.",
    "Остановились на передаче — выжмите сцепление, иначе заглохнете.",
    "Первое, что нужно машине: свечи, заряд АКБ (в гараже) и масло.",
    "Чтобы ездить легально: TÜV (техосмотр), потом номера в Rathaus.",
    "Магазины закрыты в воскресенье и по вечерам (Ladenschlussgesetz). Tankstelle работает круглосуточно.",
]

INTRO = [
    "Октябрь 1998 года. Нижняя Саксония, городок Kleinbruck.",
    "У вас однокомнатная квартира на Lindenstraße 7 и ВАЗ 2102 «Жигули» 1979 года от дяди Вити: "
    "ржавая насквозь, но на ходу, с номерами KB-VZ 102 и TÜV до весны.",
    "Прямо за вашим гаражом — Autoverwertung Kowalski (въезд с Hauptstraße, справа от гаража). "
    "Там, под брезентом среди «Трабантов», гниёт Toyota Corolla AE86 Sprinter Trueno 1985 года. "
    "Ковальский отдаст её даром — лишь бы освободить место. Это ваша ГЛАВНАЯ ЦЕЛЬ: забрать AE86, починить, "
    "пройти TÜV и поставить на учёт.",
    "НАХОДКИ: у загородных дорог стоят брошенные машины — Trabant, Wartburg, Opel Kadett, VW Golf, Ford Taunus, "
    "изредка Mercedes W123 (серые точки на карте M). Любую можно ЗАБРАТЬ СЕБЕ бесплатно: подойдите и нажмите E. "
    "У каждой своё состояние — от почти живой до гнилой насквозь. Дотащите её тросом (T) к гаражу и восстанавливайте.",
    "Не нужна — тащите на площадку у пресса Ковальского и сдавайте на лом (35–120 DM).",
    "Ещё работа: смены на складе (Lager, по будням 6–9 утра) и доставка пиццы (Pizzeria Da Luigi).",
    "",
    "Квартплата (105 DM) и страховка каждой машины на учёте (24 DM) списываются каждые 7 дней. "
    "Минус больше 400 DM — выселение. Утром мотор холодный: вытяните подсос (C), держите I для стартера.",
]


def sell_price(e):
    """Скупка: всегда дешевле, чем б/у на свалке (0.45 * цена * состояние) и чем новая деталь."""
    return round(ITEMS[e["id"]]["price"] * (0.02 + 0.25 * e["cond"] / 100), 2)


def used_price(pid, cond):
    return round(ITEMS[pid]["price"] * cond / 100 * 0.45, 2)


# ====================================================================== модели меню
class Menu:
    title = ""
    time_flows = False
    wide = False

    def lines(self):
        return []

    def items(self):
        return []

    def select(self, payload):
        return "close"

    def back(self):
        return True

    def hint(self):
        return "W/S — выбор, Enter — выбрать, Esc — назад"


class Dialog(Menu):
    def __init__(self, title, lines, options=None, wide=False):
        self.title = title
        self._lines = lines if isinstance(lines, list) else [lines]
        self._opts = list(options or [])
        self.wide = wide

    def lines(self):
        return self._lines

    def items(self):
        return self._opts + [("Закрыть", CLOSE, True)]

    def select(self, payload):
        if payload == CLOSE or payload is None:
            return "close"
        return payload


class Shop(Menu):
    time_flows = True

    def __init__(self, g, title, item_ids, mode="buy", stock=None, subtitle=""):
        self.g = g
        self.title = title
        self.subtitle = subtitle
        self.ids = item_ids
        self.mode = mode
        self.stock = stock
        self.wide = True

    def sell_price(self, e):
        return sell_price(e)

    def lines(self):
        return [self.subtitle, f"Деньги: {self.g.p.money:.2f} DM"]

    def items(self):
        g = self.g
        out = []
        if self.mode == "buy":
            for iid in self.ids:
                it = ITEMS[iid]
                have = g.count(iid)
                out.append(((it["name"] + (f"  (есть {have})" if have else ""), f"{it['price']:.2f} DM"),
                            ("buy", iid), True))
        elif self.mode == "used":
            for e in self.stock:
                out.append(((f"{item_name(e['id'])} — б/у, {e['cond']:.0f}%", f"{e['price']:.2f} DM"),
                            ("used", e), True))
            if not self.stock:
                out.append(("Сегодня ничего нет. Приходите завтра.", None, False))
        else:
            for e in g.p.inventory:
                it = ITEMS.get(e["id"], {})
                if it.get("kind") in ("part", "tool"):
                    out.append(((f"{it['name']} ({e['cond']:.0f}%)", f"{self.sell_price(e):.2f} DM"), ("sell", e), True))
            if not out:
                out.append(("Нечего продавать (только детали и инструменты).", None, False))
        out.append(("Выйти", CLOSE, True))
        return out

    def select(self, payload):
        if payload == CLOSE:
            return "close"
        g = self.g
        kind, data = payload
        if kind == "buy":
            it = ITEMS[data]
            if g.pay(it["price"]):
                g.add_item(data)
                g.notify(f"Куплено: {it['name']}", GREEN)
        elif kind == "used":
            if data in self.stock and g.pay(data["price"]):
                g.add_item(data["id"], data["cond"])
                self.stock.remove(data)
                g.notify(f"Куплено б/у: {item_name(data['id'])}", GREEN)
        elif kind == "sell":
            if data in g.p.inventory:
                g.take_item(data["id"], data)
                g.earn(self.sell_price(data), "(продажа)")
        return None

    def hint(self):
        return "W/S — выбор, Enter — купить/продать, Esc — выйти"


class Inventory(Menu):
    time_flows = True

    def __init__(self, g, only_food=False, title="Инвентарь"):
        self.g = g
        self.only_food = only_food
        self.title = title

    def lines(self):
        return [f"Деньги: {self.g.p.money:.2f} DM"]

    def items(self):
        groups = {}
        for e in self.g.p.inventory:
            it = ITEMS.get(e["id"], {})
            if self.only_food and it.get("kind") not in ("food", "drink"):
                continue
            key = e["id"] if it.get("kind") != "part" else (e["id"], round(e["cond"]))
            groups.setdefault(key, []).append(e)
        order = {"food": 0, "drink": 1, "fluid": 2, "material": 3, "part": 4, "tool": 5}
        names = {"part": "деталь", "tool": "инструмент", "fluid": "жидкость", "material": "материал"}
        out = []
        for key, es in sorted(groups.items(), key=lambda kv: (order.get(ITEMS[kv[1][0]["id"]]["kind"], 9), str(kv[0]))):
            e = es[0]
            it = ITEMS[e["id"]]
            name = it["name"] + (f"  [{e['cond']:.0f}%]" if it["kind"] == "part" else "")
            usable = it["kind"] in ("food", "drink")
            out.append(((f"{name}  x{len(es)}", "съесть/выпить" if usable else names.get(it["kind"], "")), e, usable))
        if not out:
            out.append(("Пусто", None, False))
        return out

    def select(self, e):
        self.g.take_item(e["id"], e)
        self.g.consume(e["id"])
        return None

    def hint(self):
        return "Enter — использовать, Tab/Esc — закрыть"


class CarWork(Menu):
    """Капот открыт: детали, жидкости, зарядка, кузов."""
    time_flows = True
    side = True

    def __init__(self, g):
        self.g = g
        self.stack = ["root"]
        self.slot = None
        self.panel = None

    @property
    def car(self):
        return self.g.car

    def in_garage(self):
        return point_in(GARAGE, self.car.x, self.car.y)

    @property
    def title(self):
        m = self.stack[-1]
        if m == "root":
            return f"{self.car.name} — работа с машиной"
        if m == "parts":
            return "Детали"
        if m == "slot":
            return self.car.slots[self.slot][0]
        if m == "fluids":
            return "Жидкости"
        if m == "body":
            return "Кузов — ржавчина"
        return f"{PANELS[self.panel]}: {self.car.rust[self.panel]:.0f}% ржавчины"

    def lines(self):
        car, g = self.car, self.g
        tuv = "действует" if car.tuv_until >= g.day else "нет"
        return [
            f"{'Дизель' if car.sp('diesel') else 'Бензин'} {car.fuel:.1f}/{car.tank:.0f} л · "
            + (f"Масло {car.oil:.2f}/{car.oil_cap} л ({car.oil_quality:.0f}%) · " if car.oil_cap > 0 else "Масло — в бензине · ")
            + (f"Антифриз {car.coolant:.1f}/{car.coolant_cap} л" if car.coolant_cap > 0 else "Охлаждение воздушное"),
            f"Торм. жидк. {car.brake_fluid:.0f}% · АКБ {car.battery_charge:.0f}% · Темп. {car.temp:.0f}°C · "
            f"Пробег {car.odometer:.0f} км",
            f"TÜV: {tuv} · Номера: {car.plate if car.registered else 'нет'} · "
            + ("в гараже" if self.in_garage() else "на улице (сварка и зарядка недоступны)"),
        ]

    def items(self):
        g, car = self.g, self.car
        m = self.stack[-1]
        out = []
        if m == "root":
            out = [("Детали (снять / поставить)", "parts", True),
                   ("Жидкости (масло, антифриз, бензин...)", "fluids", True),
                   ("Кузов и ржавчина (сварка, покраска)", "body", True),
                   (("Зарядить аккумулятор", "3 ч, в гараже"), "charge", True),
                   ("Закрыть капот", CLOSE, True)]
        elif m == "parts":
            for s, (name, pid, mins) in car.slots.items():
                p = car.parts.get(s)
                out.append(((name, "НЕТ" if p is None else f"{p['cond']:.0f}%"), ("slot", s), True))
            out.append(("← Назад", "back", True))
        elif m == "slot":
            name, pid, mins = car.slots[self.slot]
            p = car.parts.get(self.slot)
            if p is not None:
                out.append(((f"Снять: {item_name(p['id'])} ({p['cond']:.0f}%)", f"{mins} мин"), ("remove", self.slot), True))
            else:
                cands = sorted([e for e in g.p.inventory if e["id"] == pid], key=lambda e: -e["cond"])
                for e in cands:
                    out.append(((f"Поставить: {item_name(pid)} ({e['cond']:.0f}%)", f"{mins} мин"), ("install", e), True))
                if not cands:
                    out.append((f"Нет детали «{item_name(pid)}» в инвентаре", None, False))
            out.append(("← Назад", "back", True))
        elif m == "fluids":
            out = [((f"Долить масло 15W-40 (канистр: {g.count('oil')})", "10 мин"), "oil_add", car.oil_cap > 0),
                   (("Слить старое масло", "20 мин"), "oil_drain", True),
                   ((f"Долить антифриз (канистр: {g.count('coolant')})", "10 мин"), "cool_add", car.coolant_cap > 0),
                   ((f"Долить тормозную жидкость ({g.count('brake_fl')})", "15 мин"), "brake_add", True),
                   ((f"Залить бензин из канистры ({g.count('fuel_can')})", "5 мин"), "fuel_add", True),
                   ("← Назад", "back", True)]
        elif m == "body":
            for p, name in PANELS.items():
                tag = " (покрашено)" if car.painted[p] else ""
                out.append(((name + tag, f"{car.rust[p]:.0f}%"), ("panel", p), True))
            out.append(("← Назад", "back", True))
        elif m == "panel":
            need = 2 if self.panel in ("floor", "sill_l", "sill_r") else 1
            out = [((f"Вырезать гниль и вварить металл ({need} лист.)", "2 ч"), "weld", True),
                   (("Обработать преобразователем ржавчины", "20 мин"), "conv", True),
                   (("Загрунтовать и покрасить", "40 мин"), "paint", True),
                   ("← Назад", "back", True)]
        return out

    def back(self):
        if len(self.stack) > 1:
            self.stack.pop()
            return False
        return True

    def need_off(self):
        if self.car.running:
            self.g.notify("Сначала заглушите двигатель.", RED)
            return False
        return True

    def work(self, minutes, sound="tool"):
        self.g.play_sound(sound, 0.6)
        left = minutes
        while left > 0:
            self.g.advance(min(10, left), working=True)
            left -= 10

    def select(self, sel):
        g, car = self.g, self.car
        if sel == CLOSE:
            return "close"
        if sel == "back":
            self.back()
            return None
        if sel in ("parts", "fluids", "body"):
            self.stack.append(sel)
            return None
        if isinstance(sel, tuple) and sel[0] == "slot":
            self.slot = sel[1]
            self.stack.append("slot")
            return None
        if isinstance(sel, tuple) and sel[0] == "panel":
            self.panel = sel[1]
            self.stack.append("panel")
            return None
        if sel == "charge":
            if not self.in_garage():
                g.notify("Зарядка — только в гараже (нужна розетка).", RED)
            elif not g.has("charger"):
                g.notify("Нужно зарядное устройство (Ost-Autoteile).", RED)
            elif not car.has("battery"):
                g.notify("Аккумулятор не установлен.", RED)
            else:
                g.advance(180)
                car.battery_charge = 100.0 * (0.3 + 0.7 * car.c("battery"))
                g.notify(f"Аккумулятор заряжен: {car.battery_charge:.0f}% (зависит от износа АКБ).", GREEN)
        elif isinstance(sel, tuple) and sel[0] in ("remove", "install"):
            s = self.slot
            if not self.need_off():
                return None
            if not g.has("toolbox"):
                g.notify("Нужен набор ключей.", RED)
                return None
            if s in ("engine", "clutch") and not self.in_garage():
                g.notify("Такую работу можно делать только в гараже.", RED)
                return None
            if sel[0] == "remove":
                part = car.parts[s]
                self.work(car.slots[s][2])
                car.parts[s] = None
                g.add_item(part["id"], part["cond"])
                if s == "engine":
                    car.oil = 0.0
                g.notify(f"Снято: {item_name(part['id'])} ({part['cond']:.0f}%)", GREEN)
            else:
                e = sel[1]
                g.take_item(e["id"], e)
                self.work(car.slots[s][2])
                car.parts[s] = {"id": e["id"], "cond": e["cond"]}
                if s == "battery":
                    car.battery_charge = 60.0 if e["cond"] > 95 else 20.0
                g.notify(f"Установлено: {item_name(e['id'])}", GREEN)
                if s == "engine":
                    g.notify("Не забудьте залить масло в новый двигатель!", YELLOW)
            self.stack.pop()
        elif sel == "oil_add":
            if not g.has("oil"):
                g.notify("Нет масла. Купите в Ost-Autoteile или на заправке.", RED)
            elif car.oil >= car.oil_cap - 0.1:
                g.notify("Масла и так по верхней метке.", YELLOW)
            else:
                g.take_item("oil")
                fresh = min(4.0, car.oil_cap + 0.25 - car.oil)
                total = car.oil + fresh
                car.oil_quality = (car.oil * car.oil_quality + fresh * 100) / total
                car.oil = min(car.oil_cap + 0.25, total)
                self.work(10)
                g.notify(f"Масло: {car.oil:.2f} л, качество {car.oil_quality:.0f}%.", GREEN)
        elif sel == "oil_drain":
            if self.need_off():
                self.work(20)
                car.oil = 0.0
                car.oil_quality = 100.0
                g.notify("Старое масло слито (чёрное, как нефть). Залейте новое!", YELLOW)
        elif sel == "cool_add":
            if not g.has("coolant"):
                g.notify("Нет антифриза.", RED)
            elif car.coolant >= car.coolant_cap - 0.1:
                g.notify("Антифриза достаточно.", YELLOW)
            else:
                g.take_item("coolant")
                car.coolant = min(car.coolant_cap, car.coolant + 5)
                self.work(10)
                g.notify(f"Антифриз: {car.coolant:.1f} л.", GREEN)
                if car.c("radiator") < 0.25:
                    g.notify("Радиатор течёт — антифриз будет уходить.", ORANGE)
        elif sel == "brake_add":
            if not g.has("brake_fl"):
                g.notify("Нет тормозной жидкости.", RED)
            else:
                g.take_item("brake_fl")
                car.brake_fluid = 100.0
                self.work(15)
                g.notify("Тормозная жидкость заменена, тормоза прокачаны.", GREEN)
        elif sel == "fuel_add":
            if car.sp("diesel"):
                g.notify("Это дизель! Бензин из канистры заливать нельзя — только дизтопливо на заправке.", RED)
            elif not g.has("fuel_can"):
                g.notify("Нет канистры с бензином.", RED)
            elif car.fuel > car.tank - 1:
                g.notify("Бак полон.", YELLOW)
            else:
                g.take_item("fuel_can")
                car.fuel = min(car.tank, car.fuel + 10)
                self.work(5)
                g.notify(f"В баке {car.fuel:.1f} л." + (" Подмешали 2T-масло (1:50)." if car.sp("two_stroke") else ""),
                         GREEN)
        elif sel in ("weld", "conv", "paint"):
            self.body_work(sel)
        return None

    def body_work(self, what):
        g, car, p = self.g, self.car, self.panel
        if what == "weld":
            need = 2 if p in ("floor", "sill_l", "sill_r") else 1
            if not self.in_garage():
                g.notify("Сварка — только в гараже.", RED)
            elif not g.has("welder"):
                g.notify("Нужен сварочный аппарат (Ost-Autoteile, 320 DM).", RED)
            elif g.count("metal") < need:
                g.notify(f"Нужно листов металла: {need}.", RED)
            elif car.rust[p] < 15:
                g.notify("Здесь варить нечего — только поверхностная ржавчина.", YELLOW)
            else:
                for _ in range(need):
                    g.take_item("metal")
                self.work(120, "weld")
                car.rust[p] = 6.0
                car.painted[p] = False
                g.p.hygiene = max(0, g.p.hygiene - 15)
                g.notify(f"{PANELS[p]}: гниль вырезана, вварена заплатка. Покрасьте, иначе снова заржавеет!", GREEN)
        elif what == "conv":
            if not g.has("rust_conv"):
                g.notify("Нет преобразователя ржавчины.", RED)
            elif car.rust[p] > 55:
                g.notify("Тут уже дыры — поможет только сварка.", ORANGE)
            else:
                g.take_item("rust_conv")
                self.work(20)
                car.rust[p] = max(0.0, car.rust[p] - 12)
                g.notify(f"{PANELS[p]}: ржавчина обработана.", GREEN)
        elif what == "paint":
            if not g.has("paint"):
                g.notify("Нет грунта и краски.", RED)
            elif car.rust[p] > 20:
                g.notify("Красить по ржавчине бессмысленно — сначала сварка/преобразователь.", ORANGE)
            else:
                g.take_item("paint")
                self.work(40)
                car.painted[p] = True
                g.notify(f"{PANELS[p]}: покрашено. Теперь ржавеет в 4 раза медленнее.", GREEN)

    def hint(self):
        return "Enter — выбрать, Esc — назад, мышь — осмотр машины"


# ====================================================================== действия
class ActionsMixin:
    """Методы игры: здания, работа, полиция, квартира. Требует от класса:
    open_menu(menu), flash_screen(), enter_apartment(), leave_apartment()."""

    def info(self, title, lines, wide=False):
        self.open_menu(Dialog(title, lines, wide=wide))

    def dialog(self, title, lines, options, wide=False):
        self.open_menu(Dialog(title, lines, options, wide=wide))

    # ----------------------------------------------------------------- здания
    def enter_building(self, bid):
        name = BUILDINGS[bid][4]
        if bid == "apartment":
            self.play_sound("door", 0.6)
            self.enter_apartment()
            return
        if not self.is_open(bid):
            self.info(name, ["Geschlossen. Закрыто.", f"Часы работы: {self.hours_str(bid)}"])
            return
        if bid == "supermarkt":
            self.open_menu(Shop(self, "Supermarkt Kaufgut", SHOP_SUPERMARKT, subtitle="Продукты и напитки"))
        elif bid == "autoteile":
            self.parts_shop("ost", "Ost-Autoteile",
                            "«Запчасти для Lada, Trabant, Wartburg — всё, что ездило в ГДР и СССР. Привезём из Польши.»")
        elif bid == "tanke":
            self.open_menu(Shop(self, "Tankstelle", SHOP_TANKE, subtitle="Открыто круглосуточно"))
        elif bid == "imbiss":
            self.open_menu(Shop(self, "Döner Imbiss", SHOP_IMBISS, subtitle="«Mit alles und scharf?»"))
        elif bid == "pizzeria":
            self.pizzeria()
        elif bid == "rathaus":
            self.rathaus()
        elif bid == "tuv":
            self.tuv()
        elif bid == "lager":
            self.lager()
        elif bid == "schrott":
            self.schrott()
        elif bid == "autohaus":
            self.autohaus()

    def parts_shop(self, where, title, subtitle):
        """Выбор марки, затем список запчастей этой марки."""
        owned_models = {c.model for k, c in self.owned_cars()}
        opts = []
        for m in SHOP_MODELS[where]:
            mark = "  ← ваша" if m in owned_models else ""
            opts.append((f"Запчасти: {MODEL_NAMES[m]}{mark}",
                         lambda m=m: self.open_menu(Shop(self, f"{title} — {MODEL_NAMES[m]}", shop_for_model(m),
                                                         subtitle=subtitle)), True))
        opts.append(("Расходники и инструменты", lambda: self.open_menu(
            Shop(self, f"{title} — расходники", CONSUMABLES + (["toolbox", "charger", "welder"] if where == "ost" else []),
                 subtitle="Масло, антифриз, тормозная жидкость, АКБ, трос, металл, краска")), True))
        self.dialog(title, [subtitle, "Для какой машины ищете детали?"], opts, wide=True)

    def autohaus(self):
        self.dialog("Autohaus Krüger — Toyota & West", [
            "Herr Krüger — бывший механик Toyota. Возит детали из Японии и Голландии, а заодно держит склад "
            "б/у и новых деталей для западных машин: Opel, VW, Ford, Mercedes.",
            "«AE86 у Ковальского? Ja, kenne ich. Ремень ГРМ — первым делом, sonst ist der Motor kaputt!»"],
            [("Выбрать марку и запчасти", lambda: self.parts_shop(
                "west", "Autohaus Krüger", "Toyota, Opel, VW, Ford, Mercedes — оригинал и контрактные"), True)], wide=True)

    # ----------------------------------------------------------------- свалка / приём лома
    def buy_ae86(self):
        if self.owned["ae86"]:
            return
        if not self.is_open("schrott"):
            self.info("Autoverwertung Kowalski", ["Контора закрыта — Ковальского нет.",
                                                  f"Часы работы: {self.hours_str('schrott')}"])
            return
        if AE86_PRICE <= 0 or self.pay(AE86_PRICE):
            self.owned["ae86"] = True
            self.info("Autoverwertung Kowalski", [
                "Ковальский стягивает брезент и отдаёт ключи на проволоке: «Nimm sie umsonst. "
                "Мне она только место занимает».",
                "«Zieh sie raus, wann du willst. Только ремень ГРМ сначала поменяй, а то будет металлолом.»",
                "Отбуксируйте AE86 в гараж: подгоните «двойку», у AE86 нажмите T (трос), "
                "уберите «двойку» из гаража на место рядом и затащите «панду» внутрь. "
                "Или позвоните в Abschleppdienst (телефон дома). Сварка и зарядка АКБ — только в гараже."], wide=True)
            self.notify("Toyota AE86 теперь ваша! Следующий шаг — починить и пройти TÜV.", GREEN, 8)

    def ae86_offer(self):
        ae = self.cars["ae86"]
        miss = [n for n, k in (("АКБ", "battery"), ("глушителя", "exhaust"), ("заднего колеса", "tire_rr"))
                if not ae.has(k)]
        lines = [
            "Под рваным брезентом — белая с чёрным Corolla GT Coupé (Sprinter Trueno) 1985 года, "
            "с поднимающимися фарами. Пороги в дырах, задние арки сгнили, одно колесо на кирпичах.",
            f"Мотор 4A-GE: {ae.c('engine') * 100:.0f}%, ремень ГРМ: {ae.c('belt') * 100:.0f}%, "
            f"ржавчина до {ae.max_rust():.0f}%. Нет: " + ", ".join(miss) + ".",
            "Ковальский: «Забирай даром, мне она только место занимает. Деньги понадобятся на запчасти».",
        ]
        self.dialog("Toyota AE86 на свалке", lines,
                    [("Забрать у Ковальского (бесплатно)", self.buy_ae86, not self.owned["ae86"])], wide=True)

    def find_offer(self, key):
        """Осмотр брошенной машины: описание модели, состояние, забрать себе бесплатно."""
        car = self.cars[key]
        info = MODELS[car.model]
        p = car.preservation
        grade = ("почти живая — может, и заведётся после мелочей" if p > 0.7 else
                 "потрёпанная, но целая" if p > 0.5 else
                 "уставшая — работы много" if p > 0.3 else "гнилая насквозь — проект на всю зиму")
        missing = [car.slots[s][0] for s, pt in car.parts.items() if pt is None]
        worst = sorted(((pt["cond"], car.slots[s][0]) for s, pt in car.parts.items() if pt), key=lambda x: x[0])[:4]
        lines = [f"{info['name']} ({info['origin']}), пробег {car.odometer:,.0f} км.".replace(",", " "),
                 info["desc"], "",
                 f"Состояние: {grade}. Мотор {car.c('engine') * 100:.0f}%, КПП {car.c('gearbox') * 100:.0f}%, "
                 f"ржавчина до {car.max_rust():.0f}%.",
                 "Хуже всего: " + ", ".join(f"{n} {c:.0f}%" for c, n in worst) + "."]
        if missing:
            lines.append("Нет совсем: " + ", ".join(missing[:6]) + ("…" if len(missing) > 6 else "") + ".")
        lines.append("Хозяина нет — машину можно забрать себе бесплатно.")
        opts = [("Забрать себе (бесплатно)", lambda: self.take_find(key), True)]
        if key in self.wrecks_in_drop():
            opts.append((f"Сдать на лом (+{self.scrap_value(key):.2f} DM)", lambda: self.scrap_car(key), True))
        self.dialog(f"Находка: {info['name']}", lines, opts, wide=True)

    def take_find(self, key):
        car = self.cars[key]
        self.claim_car(key)
        self.play_sound("tool", 0.6)
        self.notify(f"{car.name} теперь ваша! Дотащите её тросом (T) к гаражу и восстанавливайте.", GREEN, 8)
        self.info(car.name, [
            "Вы находите в бардачке старые бумаги: хозяин выписан, машину бросили. По закону её можно оформить на себя.",
            "Что дальше: трос (T) к своей машине и тянуть к гаражу (сварка и зарядка АКБ — только там). "
            "Запчасти: восточные — в Ost-Autoteile, западные — в Autohaus Krüger, б/у — у Ковальского.",
            "Когда машина будет готова: TÜV, потом номера в Rathaus — и она ваша полноценная машина."], wide=True)

    def scrap_car(self, key, confirmed=False):
        car = self.cars.get(key)
        if car is None or key in MAIN_CARS:
            return
        if not self.is_open("schrott"):
            self.info("Autoverwertung Kowalski", ["Приём закрыт. Оставьте машину на площадке — примем в рабочее время.",
                                                  f"Часы работы: {self.hours_str('schrott')}"])
            return
        if self.owned.get(key) and not confirmed:
            self.dialog("Сдать свою машину на лом?", [
                f"{car.name} — ваша машина. Ковальский даст за неё {self.scrap_value(key):.2f} DM, "
                "и её раздавят прессом. Это нельзя отменить."],
                [("Да, сдать на лом", lambda: self.scrap_car(key, True), True)])
            return
        value = self.scrap_value(key)
        name = car.name
        self.remove_car(key)
        self.stats["scrapped"] += 1
        self.play_sound("crash", 0.7)
        self.advance(20)
        self.earn(value, f"— {name} сдан на лом")

    def attach_rope(self, target):
        """target: ключ машины (своей или брошенной), которую тянем."""
        if not self.has("rope"):
            self.notify("Нет троса. Купите Abschleppseil на заправке или в Ost-Autoteile (15 DM).", RED)
            return
        tgt = self.cars[target]
        best, bd = None, 12.0
        for k, c in self.owned_cars():
            if k == target:
                continue
            d = math.hypot(c.x - tgt.x, c.y - tgt.y)
            if d < bd:
                best, bd = k, d
        if best is None:
            self.notify("Подгоните свою машину поближе (до 12 м), чтобы привязать трос.", YELLOW)
            return
        if tgt.running:
            tgt.engine_off()
        self.tow = {"kind": "car", "key": target, "by": best}
        self.tow["len"] = self.rope_length(self.cars[best], tgt)
        self.cur = best
        self.play_sound("tool", 0.6)
        self.notify(f"Трос привязан: {tgt.name} → {self.cars[best].name}. Садитесь (F) и тяните, "
                    f"не быстрее {ROPE_SNAP_KMH - 5} км/ч.", GREEN, 7)

    def detach_rope(self):
        if self.tow:
            self.cars[self.tow["by"]].tow_mass = 0.0
            self.notify(f"Трос отвязан ({self.tow_name()}).")
        self.tow = None
        self.play_sound("tool", 0.5)

    def refuel(self):
        key = self.car_in_zone(PUMP_ZONE)
        if key is None:
            self.info("Tankstelle", ["Подъезжайте на машине к колонке."])
            return
        self.cur = key
        car = self.car
        if car.running:
            self.info("Tankstelle", ["«Motor aus!» — кричит заправщик. Заглушите двигатель."])
            return
        space = car.tank - car.fuel
        diesel, two = car.sp("diesel"), car.sp("two_stroke")
        price = DIESEL_PRICE if diesel else FUEL_PRICE + (MIX_EXTRA if two else 0)
        fuel_name = "Diesel" if diesel else ("Gemisch 1:50" if two else "Normalbenzin")

        def fill(l):
            l = min(l, car.tank - car.fuel)
            if l <= 0.1:
                self.notify("Бак полон.")
                return
            afford = max(0.0, self.p.money) / price
            if afford < 1:
                self.notify(f"Денег не хватит даже на литр ({price:.2f} DM).", RED)
                return
            if l > afford:  # денег хватает не на всё
                l = int(afford * 10) / 10.0
                self.notify(f"Денег хватило только на {l:.1f} л.", YELLOW)
            cost = round(l * price, 2)
            if self.pay(cost):
                car.fuel = min(car.tank, car.fuel + l)
                self.advance(5)
                self.notify(f"Заправлено {l:.1f} л за {cost:.2f} DM.", GREEN)

        if diesel:
            note = "Колонка с дизтопливом. Бензин в этот мотор — нельзя!"
        elif two:
            note = "Двухтактник: заправщик из «Gemisch»-колонки — бензин с 2T-маслом 1:50, как в ГДР."
        elif car.model == "vaz2102":
            note = "Старый мотор 2101 рассчитан на А-76, но и немецкий Normal (91) переварит."
        elif car.model == "ae86":
            note = "4A-GE любит Super (95) — но и Normal переживёт."
        else:
            note = "Normalbenzin 91 — старому карбюраторному мотору в самый раз."

        def wash():
            if self.pay(WASH_PRICE):
                self.advance(15)
                car.dirt = 0.05
                self.notify(f"{car.name} помыта. Теперь видно, где ржавчина, а где краска.", GREEN)

        self.dialog(f"Tankstelle — {car.name}", [
            f"{fuel_name}. В баке: {car.fuel:.1f} / {car.tank:.0f} л. Цена: {price:.2f} DM/л. "
            f"У вас: {self.p.money:.2f} DM.", note], [
            (f"10 литров ({10 * price:.2f} DM)", lambda: fill(10), True),
            (f"20 литров ({20 * price:.2f} DM)", lambda: fill(20), True),
            (f"Полный бак ({space:.1f} л = {space * price:.2f} DM)", lambda: fill(space), True),
            (f"Waschanlage — помыть машину ({WASH_PRICE:.0f} DM)", wash, car.dirt > 0.1)])

    def tuv(self):
        if not self.is_open("tuv"):
            self.info("TÜV", ["Geschlossen.", f"Часы работы: {self.hours_str('tuv')}"])
            return
        key = self.car_in_zone(TUV_YARD)
        if key is not None:
            self.cur = key
        car = self.car
        if key is None:
            self.info("TÜV-Prüfstelle", ["«Guten Tag. Для Hauptuntersuchung пригоните машину во двор перед зданием.»",
                                         "Стоимость проверки: 95 DM."])
            return

        def check():
            if not self.pay(95):
                return
            self.advance(45)
            defects = car.tuv_defects()
            p, why = car._start_chance()
            if p <= 0 or car.battery_charge < 10:
                defects.insert(0, "Автомобиль не заводится своим ходом")
            if not defects:
                car.tuv_until = self.day + 730
                first = ("Инспектор долго смотрит на «Жигули», потом на вас, потом снова на «Жигули»."
                         if car.model == "vaz2102" else
                         "Инспектор обходит AE86 и улыбается: «Ein Hachi-Roku! Mein Sohn liebt diese Autos.»")
                self.info("TÜV — BESTANDEN!", [
                    first, "«Na gut... Ohne erhebliche Mängel.» Он клеит свежую Plakette.",
                    "TÜV действует 2 года." + ("" if car.registered else " Теперь — в Rathaus за номерами.")])
            else:
                self.info("TÜV — NICHT BESTANDEN", ["Erhebliche Mängel (существенные дефекты):", ""] +
                          [f"• {d}" for d in defects[:14]] + ["", "Устраните и приезжайте снова."])

        self.dialog("TÜV-Prüfstelle", [
            f"Hauptuntersuchung (техосмотр) для {car.name}.",
            "Проверяют: коррозию, тормоза, шины, свет, выхлоп, амортизаторы, течи."],
            [("Пройти проверку (95 DM, 45 мин)", check, True)])

    def rathaus(self):
        def register(key):
            car = self.cars[key]
            if car.tuv_until < self.day:
                self.info("Zulassungsstelle", ["«Ohne gültigen TÜV-Bericht — keine Zulassung.» Сначала TÜV."])
                return
            if self.pay(145):
                self.advance(120)
                if not car.spec.get("plate") and not car.plate_text:
                    rr = random.Random(car.seed)
                    letters = "ABCDEFGHKLMNPRSTUVWXYZ"
                    car.plate_text = f"KB-{rr.choice(letters)}{rr.choice(letters)} {rr.randint(10, 999)}"
                car.registered = True
                self.info("Zulassungsstelle", [
                    f"Два часа в очереди, три формуляра — и номера ваши: {car.plate}.",
                    "Страховка и налог (24 DM) будут списываться еженедельно.",
                    f"{car.name} можно ездить легально!"])
                if self.check_goal():
                    self.victory()

        lines = ["Nummer 47 bitte... Служащая Frau Becker смотрит поверх очков."]
        opts = []
        for key, car in self.owned_cars():
            if car.registered:
                lines.append(f"{car.name}: зарегистрирована, номера {car.plate}.")
            else:
                ok = car.tuv_until >= self.day
                lines.append(f"{car.name}: не на учёте" + ("" if ok else " (нужен действующий TÜV)") + ".")
                opts.append((f"Поставить на учёт {car.name} (145 DM: номера + страховка)",
                             lambda key=key: register(key), ok))
        self.dialog("Rathaus — Zulassungsstelle", lines, opts)

    def victory(self):
        ae = self.cars["ae86"]
        days = self.day + 1
        self.play_sound("horn", 0.8)
        self.info("ЦЕЛЬ ВЫПОЛНЕНА — Hachi-Roku!", [
            f"Toyota AE86 Sprinter Trueno на ходу, с TÜV и номерами {ae.plate}.",
            "Вы садитесь в ковшеобразное кресло, поворачиваете ключ — 4A-GE заводится с полоборота "
            "и крутится до 7600 так, как «двойке» и не снилось.",
            f"На это ушло {days} дн. Доставок пиццы: {self.stats['deliveries']}, смен на складе: {self.stats['shifts']}.",
            f"Сдано машин на лом: {self.stats.get('scrapped', 0)}. Ковальский машет вслед: «Hachi-Roku lebt!»",
            "Старую «двойку» можно оставить — ржавая, но своя. Игра продолжается: A7 без ограничения скорости ждёт!",
        ], wide=True)

    def lager(self):
        p = self.p

        def shift():
            if p.drunk > 15:
                self.info("Lager", ["Бригадир Herr Wolff: «Du bist besoffen! Nach Hause!» — сегодня без работы."])
                return
            if p.energy < 30:
                self.info("Lager", ["Вы слишком устали для смены (бодрость < 30)."])
                return
            for _ in range(48):
                self.advance(10, working=True)
                if self.game_over:
                    return
            pay = 104.0
            note = ""
            if p.hygiene < 20:
                pay = round(pay * 0.7, 2)
                note = " Бригадир ворчал, что от вас воняет (−30%)."
            self.stats["shifts"] += 1
            self.earn(pay, "за смену на складе")
            self.info("Lager", [f"8 часов таскали коробки и водили погрузчик. Заработано {pay:.0f} DM.{note}"])

        can = self.weekday() < 5 and 6 <= self.hour < 9
        self.dialog("Spedition Müller — Lager", [
            "Склад логистической компании. Платят 13 DM в час (8 часов = 104 DM).",
            "Смену можно начать по будням с 06:00 до 09:00."],
            [("Отработать смену (8 часов)", shift, can)])

    def pizzeria(self):
        def take():
            pts = [pt for pt in self.world.delivery_points if 250 < math.hypot(pt[0] - 336, pt[1] - 297) < 1200]
            x, y = random.choice(pts)
            dist = math.hypot(x - 336, y - 297)
            limit = dist / 8.0 + 60
            self.delivery = {"x": x, "y": y, "deadline": self.minutes + limit, "start": self.minutes,
                             "pay": round(10 + dist / 70, 2)}
            self.info("Pizzeria Da Luigi", [
                "Luigi: «Ecco! Eine Pizza Salami. Schnell, schnell!»",
                f"Адрес отмечен на карте (M) и жёлтым столбом света. Расстояние ~{dist:.0f} м, время ~{limit:.0f} мин.",
                f"Оплата: {self.delivery['pay']:.2f} DM + чаевые за скорость. Пешком не успеть!"])

        def buy():
            if self.pay(9):
                self.add_item("pizza_hot")

        opts = [("Купить пиццу (9 DM)", buy, True)]
        if self.delivery:
            opts.insert(0, ("Заказ уже на руках — отвезите его", None, False))
        else:
            opts.insert(0, ("Взять заказ на доставку", take, True))
        self.dialog("Pizzeria Da Luigi", ["Luigi ищет курьера со своей машиной. Платит за каждый заказ."], opts)

    def deliver(self):
        d = self.delivery
        late = self.minutes > d["deadline"]
        pay = round(d["pay"] * (0.5 if late else 1.0), 2)
        tip = 0.0 if late else round(min(8.0, (d["deadline"] - self.minutes) / 10), 2)
        self.delivery = None
        self.stats["deliveries"] += 1
        self.earn(pay + tip, "за доставку" + (" (опоздали — половина)" if late else f" (чаевые {tip:.2f})"))

    def schrott(self):
        if self.schrott_day != self.day:
            self.schrott_day = self.day
            rng = random.Random(self.day * 31 + 7)
            owned_models = [c.model for k, c in self.owned_cars()]
            pool = []
            for m in set(owned_models + ["vaz2102"]):
                pool += [v[1] for v in SLOTS_BY_MODEL[m].values()]
            self.schrott_stock = []
            for _ in range(rng.randint(4, 8)):
                pid = rng.choice(pool)
                cond = rng.uniform(20, 75)
                self.schrott_stock.append({"id": pid, "cond": round(cond, 1), "price": used_price(pid, cond)})
            if rng.random() < 0.4:
                self.schrott_stock.append({"id": "metal", "cond": 100, "price": 6.0})
        in_drop = self.wrecks_in_drop()
        opts = [(f"Сдать на лом: {self.cars[k].name}{' (ваша!)' if self.owned.get(k) else ''} "
                 f"(+{self.scrap_value(k):.2f} DM)", lambda k=k: self.scrap_car(k), True) for k in in_drop]
        if not self.owned["ae86"]:
            opts.append(("Забрать ржавую Toyota AE86 (бесплатно)", self.buy_ae86, True))
        lines = ["Пан Ковальский: «Брошенные у дорог машины — бери себе, чини, катайся. Бумаги оформим. "
                 "А если не нужна — тащи на площадку у пресса, приму на лом: 35–120 марок, смотря сколько железа.»",
                 f"Сдано машин: {self.stats['scrapped']}. Брошенных машин в округе: {len(self.wrecks)}."]
        if not in_drop:
            lines.append("На площадке приёма сейчас пусто.")
        self.dialog("Autoverwertung Kowalski", lines, opts + [
            ("Купить б/у запчасти", lambda: self.open_menu(Shop(self, "Schrottplatz — б/у", [], mode="used",
                                                                  stock=self.schrott_stock,
                                                                  subtitle="Всё как есть, без гарантии")), True),
            ("Продать старые детали", lambda: self.open_menu(Shop(self, "Schrottplatz — скупка", [], mode="sell",
                                                                    subtitle="Цена зависит от состояния")), True)])

    # ----------------------------------------------------------------- штрафы
    def check_blitzer(self):
        car = self.car
        for i, (bx, by, lim) in enumerate(BLITZER):
            if math.hypot(car.x - bx, car.y - by) < 9 and self.t > self.blitz_cd.get(i, 0):
                over = car.kmh() - lim
                if over > 5:
                    self.blitz_cd[i] = self.t + 15
                    fine = 20 if over <= 10 else (50 if over <= 20 else (100 if over <= 30 else 200))
                    self.flash_screen()
                    self.play_sound("blitz", 0.8)
                    self.charge(fine, f"БЛИЦ! {car.kmh():.0f} км/ч при {lim}. Штраф")

    def check_police(self):
        car, pol = self.car, self.world.police
        if self.police_cd > 0 or abs(car.speed) < 1:
            return
        if math.hypot(car.x - pol.x, car.y - pol.y) > 28:
            return
        reasons = []
        lim = self.world.speed_limit(car.x, car.y)
        if not car.registered:
            reasons.append(("Fahren ohne Zulassung und Versicherung (без номеров/страховки)", 250))
        elif car.tuv_until < self.day:
            reasons.append(("Просроченный TÜV", 60))
        if self.p.drunk > 25:
            reasons.append(("Alkohol am Steuer (вождение в нетрезвом виде)", 500))
        if lim and car.kmh() > lim + 20:
            reasons.append((f"Превышение скорости ({car.kmh():.0f} при {lim})", 100))
        if car.c("lights") < 0.05 and self.darkness() > 0.4:
            reasons.append(("Езда без света ночью", 30))
        if car.c("exhaust") < 0.2:
            reasons.append(("Слишком громкий выхлоп", 40))
        if not reasons:
            return
        self.police_cd = 240
        pol.siren = 8.0
        car.speed = 0
        self.play_sound("police", 0.6)
        total = sum(r[1] for r in reasons)
        self.charge(total)
        self.info("Polizei", ["«Allgemeine Verkehrskontrolle! Führerschein und Fahrzeugschein, bitte.»", ""] +
                  [f"• {r[0]}: {r[1]} DM" for r in reasons] +
                  ["", f"Итого штраф: {total} DM.", "Полицейский качает головой, глядя на ваши гнилые пороги."])

    # ----------------------------------------------------------------- квартира
    def sleep(self, minutes):
        left = minutes
        while left > 0 and not self.game_over:
            self.advance(min(10, left), sleeping=True)
            left -= 10
        self.p.energy = min(100, self.p.energy)
        self.notify(f"Вы проснулись. {self.time_str()}", GREEN)

    def apartment_act(self, key):
        p = self.p
        if key == "door":
            self.play_sound("door", 0.6)
            self.leave_apartment()
        elif key == "bed":
            if p.energy > 80:
                self.info("Кровать", ["Спать пока не хочется."])
                return

            def until_morning():
                self.sleep(max(30, ((7 - self.hour) % 24) * 60))
                self.save()

            self.dialog("Кровать", [f"Бодрость: {p.energy:.0f}%. Сон до утра также сохраняет игру."], [
                ("Вздремнуть 1 час", lambda: self.sleep(60), True),
                ("Поспать 4 часа", lambda: self.sleep(240), True),
                ("Спать до 07:00 утра (и сохранить)", until_morning, True)])
        elif key == "fridge":
            self.open_menu(Inventory(self, only_food=True, title="Холодильник (ваши продукты)"))
        elif key == "stove":
            if self.has("pizza_tk"):
                def cook():
                    self.take_item("pizza_tk")
                    self.advance(15)
                    self.add_item("pizza_hot")
                    self.notify("Пицца готова (горячая пицца в инвентаре).", GREEN)
                self.dialog("Плита", ["Разогреть замороженную пиццу? (15 мин)"], [("Разогреть", cook, True)])
            else:
                self.info("Плита", ["Нечего готовить. Купите Tiefkühlpizza в Supermarkt."])
        elif key == "sink":
            p.thirst = min(100, p.thirst + 30)
            self.advance(2)
            self.notify("Вы попили воды из-под крана.", GREEN)
        elif key == "shower":
            self.advance(15)
            p.hygiene = 100
            p.energy = min(100, p.energy + 5)
            self.notify("Вы приняли душ. Свежесть!", GREEN)
        elif key == "toilet":
            self.advance(4)
            self.notify("Вы сходили в туалет. Бачок подтекает, как и ваш карбюратор.")
        elif key == "mirror":
            look = "бодрый" if p.energy > 60 else ("уставший" if p.energy > 25 else "как зомби")
            smell = ("пахнете нормально" if p.hygiene > 50 else
                     ("пахнете бензином и потом" if p.hygiene > 20 else "пахнете ужасно — на работу так нельзя"))
            drunk = " Глаза красные — вы пьяны." if p.drunk > 25 else ""
            self.info("Зеркало", [f"Вы выглядите {look} и {smell}.{drunk}", f"Здоровье: {p.health:.0f}%"])
        elif key == "tv":
            def watch():
                self.advance(60)
                self.info("Fernsehen", [random.choice(NEWS)])
            self.dialog("Телевизор", ["Посмотреть телевизор 1 час?"], [("Смотреть", watch, True)])
        elif key == "sofa":
            self.advance(60)
            p.energy = min(100, p.energy + 4)
            self.notify("Вы посидели на диване и уставились в потолок.")
        elif key == "phone":
            self.phone()
        elif key in ("table", "calendar", "mail"):
            self.status()
        elif key == "shelf":
            self.info("Книжная полка", [
                "«Руководство по ремонту ВАЗ-2101, -2102» (1982), зачитанное до дыр.",
                "Закладка на странице: «Порядок работы цилиндров 1-3-4-2. Зазор в контактах "
                "прерывателя 0,35-0,45 мм. Уровень масла — между метками щупа (3,75 л)».",
                "Рядом — немецко-русский словарь и сборник «Deutsch für Aussiedler»."])
        elif key == "wardrobe":
            self.info("Шкаф", ["Спортивный костюм Adidas, рабочая куртка, выходная рубашка. Больше ничего полезного."])
        elif key == "ktable":
            self.info("Кухонный стол", ["Клеёнка в клетку, пепельница и счёт за электричество (оплачен)."])

    def phone(self):
        car = self.car

        def pizza():
            if self.pay(15):
                self.advance(35)
                self.add_item("pizza_hot")
                self.notify("Курьер привёз пиццу (15 DM).", GREEN)

        def tow(key):
            if not self.pay(120):
                return
            car = self.cars[key]
            other = [c for k, c in self.cars.items() if k != key and self.owned.get(k)]
            gx, gy, gw, gh = GARAGE
            px, py, pw, ph = PARKING2
            # если гараж занят другой машиной — ставим эту на место рядом
            busy = any(point_in(GARAGE, c.x, c.y) for c in other)
            if busy:
                car.x, car.y = px + pw / 2, py + ph / 2 + 0.5
            else:
                car.x, car.y = gx + gw / 2, gy + gh / 2 + 0.5
            car.angle = -math.pi / 2
            car.speed = 0
            car.engine_off()
            self.advance(90)
            self.notify(f"Abschleppdienst Meier отбуксировал {car.name} "
                        + ("на место рядом с гаражом" if busy else "в ваш гараж") + " (120 DM).", GREEN)

        def mama():
            self.advance(20)
            if self.day - self.last_mama >= 5:
                self.last_mama = self.day
                self.earn(60, "— мама перевела денег")
                self.info("Звонок маме", ["«Сынок, ты там кушаешь? Я тебе 60 марок перевела. "
                                          "И продай ты эту ржавую машину, отец твой на ней ещё в Сочи ездил!»"])
            else:
                self.info("Звонок маме", ["«Опять звонишь? Денег больше нет до следующей недели. "
                                          "Шапку надевай, октябрь на дворе!»"])

        self.dialog("Телефон", ["Кому позвонить?"], [
            ("Pizza-Service — заказать пиццу (15 DM)", pizza, True),
        ] + [(f"Abschleppdienst — {c.name} к гаражу (120 DM)", lambda k=k: tow(k), True)
             for k, c in self.owned_cars()] + [
            ("Позвонить маме в Омск", mama, True)])

    def status(self):
        lines = [self.goal_text(), "",
                 f"Деньги: {self.p.money:.2f} DM.  Квартплата {RENT:.0f} DM — через {7 - self.day % 7} дн."]
        for k, car in self.owned_cars():
            tuv = "нет" if car.tuv_until < self.day else f"до дня {car.tuv_until}"
            lines.append(f"{car.name}: TÜV — {tuv}; номера — {car.plate if car.registered else 'нет'}; "
                         f"пробег {car.odometer:.0f} км; ржавчина до {car.max_rust():.0f}%.")
        lines += [f"Сделано доставок: {self.stats['deliveries']},  смен на складе: {self.stats['shifts']},  "
                  f"сдано машин на лом: {self.stats.get('scrapped', 0)}.", ""]
        if not self.owned["ae86"]:
            lines += ["План: забрать AE86 у Ковальского (свалка за гаражом, бесплатно) и копить на запчасти.",
                      "Быстрые деньги: брошенные машины у загородных дорог (серые точки на карте M) — "
                      "трос (T) к «двойке», тащить на площадку у пресса, E — сдать на лом."]
        elif not self.goal_done:
            lines += ["План по AE86: 1) ремень ГРМ, АКБ, свечи, масло, бензин;  2) шины, тормоза, амортизаторы;",
                      "3) сварка порогов/днища и покраска (в гараже);  4) TÜV;  5) номера в Rathaus."]
        self.info("Дела и счета", lines, wide=True)
