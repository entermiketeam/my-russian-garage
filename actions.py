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
from models import MODELS, SLOT_MINUTES, model_info
import damage
import engine as eng
import fasteners as fast
import electrics as elec
import underside
from tuning import LEGEND, is_legend
from tuning import tune_slots, TUNE_NAMES, NEEDS_TURBO, BOOST_PRESETS, BOOST_BY_KEY, TORQUE_PER_BAR
from world import JUNKYARD
from state import BASE_VALUE
from world import BUILDINGS, BLITZER, PUMP_ZONE, TUV_YARD, GARAGE, PARKING2, SCRAP_DROP, point_in
from state import WHITE, RED, GREEN, YELLOW, RENT, AE86_PRICE, CAR_NAMES, ROPE_SNAP_KMH, MAIN_CARS

ORANGE = (230, 140, 40)
FUEL_PRICE = 1.65
DIESEL_PRICE = 1.29      # дизель в 1998 году был дешевле бензина
MIX_EXTRA = 0.06         # двухтактная смесь 1:50 (бензин + 2T-масло) — чуть дороже
WASH_PRICE = 8.0
CLOSE = "__close__"

NEWS = [
    "Новости: Герхард Шрёдер (SPD) выиграл выборы в Бундестаг. Конец эпохи Коля.",
    "Новости: С 1 января 1999 года евро введут в безналичных расчётах. Марка пока остаётся.",
    "Спорт: «Бавария» лидирует в Бундеслиге, «Кайзерслаутерн» — действующий чемпион.",
    "Погода: в Нижней Саксонии дожди, ночью до +4 °C. Берегите машины от сырости.",
    "Реклама: «Opel Astra — всего от 26 990 DM!» Вы смотрите на свои ржавые пороги и вздыхаете.",
    "Новости: Цены на бензин выросли до 1,65 DM за литр. Автоклубы возмущены.",
    "Регион: В Кляйнбруке полиция усилила контроль техосмотра старых автомобилей.",
    "«Кто хочет стать миллионером?» Вы отвечаете на три вопроса и чувствуете себя умным.",
]

CONTROLS = [
    "ПЕШКОМ: WASD — идти, мышь — смотреть, Shift — бежать, E — действие, F — сесть в машину.",
    "Tab — руки (что держите), M — карта, Esc — пауза, «-» / «=» — чувствительность мыши.",
    "РУКИ: с собой только два предмета — в левой и правой руке. E на вещи — взять в свободную руку; "
    "E с едой/питьём в руке — съесть/выпить (если рядом нет другого действия, иначе G); Q — поменять руки; "
    "Z / X — положить из левой / правой (в открытый багажник рядом, на стеллаж в гараже или на землю). "
    "Инструменты и материалы для работы берутся из рук или с того, что лежит рядом: открытый багажник, "
    "стеллаж в гараже (там набор ключей). В багажнике ВАЗ — трос и предохранители.",
    "ЗА РУЛЁМ: W — газ, S — тормоз, A/D — руль, Пробел — сцепление (держать), стрелка ВНИЗ — ручник.",
    "ПРИЦЕЛ (E): смотрите на деталь машины — ручку двери (открыть), сиденье (сесть), капот, багажник, болт/гайку "
    "(открутить/затянуть). G — снять деталь, у которой откручен весь крепёж. В салоне: E на подрулевых "
    "переключателях — поворотники ([ и ] — с клавиатуры), E на ручке двери — открыть/закрыть, на проёме — выйти.",
    "ЭЛЕКТРИКА: блок предохранителей — под панелью слева от руля (у W123/Taunus — под капотом): E на нём. "
    "Сгорел снова — ищите причину: «Прозвонить мультиметром» покажет участок, место отметится на машине красным, "
    "E там — устранить. Ночью без исправных фар/фонарей полиция штрафует и может снять машину с учёта.",
    "КЛЮЧИ: у каждой машины свой ключ. K — запереть/отпереть (снаружи — с ключом в руке, изнутри — кнопкой). "
    "I — вставить ключ из руки и, держа I, завести; E на замке зажигания — вынуть ключ (или завести напрямую). "
    "Запасные ключи — на ключнице у двери квартиры. Незапертую машину на улице ночью могут угнать — "
    "тогда в полицию (Хауптштрассе, восточнее магазина «Восток»): заявление и объявления с вознаграждением.",
    "ШИНЫ: протектор и давление каждой — «Шины и давление» в меню машины; подкачать — компрессор или колонка «Воздух» "
    "на заправке. Лысые шины на мокром и снегу — длинный тормозной путь и занос; без ABS колёса блокируются.",
    "ДРИФТ: на скорости держите W + A или D и дёрните ручник (стрелка вниз), затем отпустите его и держите занос "
    "газом и контррулём. Лучше всего — заднеприводные (ВАЗ, BMW E21, Civic, AE86); передний привод сам выравнивается.",
    "Shift / Ctrl — передача вверх/вниз (или 1-4, R — задняя, N — нейтраль).",
    "I (держать) — стартер / заглушить, C — подсос, L — фары, H — гудок, V — вид (салон / сзади).",
    "F — выйти, E — действие (заправка, техосмотр, доставка, сдать машину на лом).",
    "T — буксировочный трос: привязать брошенную машину (или свою) к машине рядом / отвязать.",
    "G — второе действие рядом (например, если рядом и своя машина, и брошенная).",
    "R у брошенной или своей машины — РАЗОБРАТЬ на запчасти (на свалке можно снять и мотор с коробкой).",
    "ПОДЗЕМНЫЕ ГАРАЖИ: въезды «P» у Хауптштрассе и Ам-Вальд — въезжайте машиной или заходите пешком; пандусы "
    "ведут на уровень −2.",
    "ЗАБРОШЕННЫЕ ГАРАЖИ (коричневые квадраты на карте): E у ворот — открыть (некоторые заперты — нужна монтировка),",
    "внутри — забытая машина (забрать бесплатно) и полки с деталями и инструментами (E — обыскать).",
    "НАХОДКИ: брошенные машины у дорог (серые точки на карте) можно ЗАБРАТЬ СЕБЕ бесплатно (E у машины),",
    "дотащить тросом до гаража, восстановить и ездить. Сдать на лом — только если сами захотите.",
    "У машины: E — открыть капот (детали, жидкости, сварка). Мышь/колесо — осмотр машины.",
    "",
    "СОВЕТЫ: холодный мотор заводится только с подсосом (C). Трогайтесь с 1-й передачи.",
    "Остановились на передаче — выжмите сцепление, иначе заглохнете.",
    "Первое, что нужно машине: свечи, заряд АКБ (в гараже) и масло.",
    "Чтобы ездить легально: техосмотр (TÜV), потом номера в ратуше.",
    "Магазины закрыты в воскресенье и по вечерам (так в Германии по закону). Заправка работает круглосуточно.",
]

INTRO = [
    "Декабрь 1998 года. Нижняя Саксония, городок Кляйнбрук. Снег, мороз, на дорогах — каша из снега и соли.",
    "У вас однокомнатная квартира на Линденштрассе, 7 и ВАЗ 2102 «Жигули» 1979 года от дяди Вити: "
    "ржавая насквозь, но на ходу, с номерами KB-VZ 102 и техосмотром до весны.",
    "Прямо за вашим гаражом — авторазборка Ковальского (въезд с Хауптштрассе, справа от гаража). "
    "Там, под брезентом среди «Трабантов», гниёт Toyota Corolla AE86 Sprinter Trueno 1985 года. "
    "Ковальский отдаст её даром — лишь бы освободить место. Это ваша ГЛАВНАЯ ЦЕЛЬ: забрать AE86, починить, "
    "пройти техосмотр и поставить на учёт.",
    "НАХОДКИ: у загородных дорог стоят брошенные машины — Trabant, Wartburg, Opel Kadett, VW Golf, Ford Taunus, "
    "изредка Mercedes W123 (серые точки на карте M). Любую можно ЗАБРАТЬ СЕБЕ бесплатно: подойдите и нажмите E. "
    "У каждой своё состояние — от почти живой до гнилой насквозь. Дотащите её тросом (T) к гаражу и восстанавливайте.",
    "Не нужна — тащите на площадку у пресса Ковальского и сдавайте на лом (35–120 DM).",
    "ЗАБРОШЕННЫЕ ГАРАЖИ: по округе стоят старые гаражи и сараи (коричневые квадраты на карте). Внутри — забытые "
    "машины, которые сохранились лучше придорожных, и полки с деталями. Часть ворот заперта: нужна монтировка (12 DM).",
    "Ещё работа: смены на складе (по будням 6–9 утра) и доставка пиццы (пиццерия «У Луиджи»).",
    "",
    "ЧТО ИССЛЕДОВАТЬ: два подземных гаража (много машин, мало деталей), три заброшенные парковки "
    "(ржавые и полуразобранные машины, детали на земле), свалка Ковальского (доноры — разбирайте на запчасти, R), "
    "автоплощадка Вебера на L 342 — купить или продать машину.",
    "Зимой: холодный мотор заводится хуже, аккумулятор слабее, на снегу и в слякоти машину несёт.",
    "Квартира ваша собственная — квартплаты нет. Страховка каждой машины на учёте (24 DM) списывается каждые 7 дней. "
    "На старте у вас 3000 DM. Утром мотор холодный: вытяните подсос (C), держите I для стартера.",
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
            for e in g.available():            # в руках и рядом (открытый багажник у входа)
                it = ITEMS.get(e["id"], {})
                if it.get("kind") in ("part", "tool"):
                    out.append(((f"{it['name']} ({e['cond']:.0f}%)", f"{self.sell_price(e):.2f} DM"), ("sell", e), True))
            if not out:
                out.append(("Нечего продавать: детали — в руках или в открытом багажнике рядом.", None, False))
        out.append(("Выйти", CLOSE, True))
        return out

    def select(self, payload):
        if payload == CLOSE:
            return "close"
        g = self.g
        kind, data = payload
        if kind in ("buy", "used") and not g.can_receive(shop=True):
            g.notify("Обе руки заняты, а своей машины у входа нет — освободите руку (X / Z), потом покупайте.", RED, 6)
            return None
        if kind == "buy":
            it = ITEMS[data]
            if g.pay(it["price"]):
                where = g.give({"id": data, "cond": 100.0}, shop=True)
                g.notify(f"Куплено: {it['name']}" + (" — в руке" if where == "hand" else ""), GREEN)
        elif kind == "used":
            if data in self.stock and g.pay(data["price"]):
                g.give({"id": data["id"], "cond": data["cond"]}, shop=True)
                self.stock.remove(data)
                g.notify(f"Куплено б/у: {item_name(data['id'])}", GREEN)
        elif kind == "sell":
            if any(x is data for x in g.available()):
                g.take_item(data["id"], data)
                g.earn(self.sell_price(data), "(продажа)")
        return None

    def hint(self):
        return "W/S — выбор, Enter — купить/продать, Esc — выйти"


HAND_RU = ("левая", "правая")


class Inventory(Menu):
    """Инвентарь — две руки. Съесть/выпить, осмотреть, поменять руками, положить; взять из того, что рядом."""
    time_flows = True

    def __init__(self, g, only_food=False, title="Руки"):
        self.g = g
        self.title = title

    def lines(self):
        g = self.g
        out = [f"Деньги: {g.p.money:.2f} DM. С собой — только то, что в руках (2 предмета)."]
        for i in (0, 1):
            e = g.p.hands[i]
            out.append(f"{HAND_RU[i].capitalize()} рука: " + (self._name(e) if e else "пусто"))
        out.append("Клавиши: E — съесть/выпить (если нечего делать рядом), Q — поменять руки, Z / X — положить из левой / правой.")
        return out

    @staticmethod
    def _name(e):
        if e.get("id") in ("key", "flyer"):
            import storage
            return storage.label(e)
        it = ITEMS.get(e["id"], {})
        k = it.get("kind")
        tail = f" [{e['cond']:.0f}%]" if k in ("part", "food", "drink") else ""
        if e["id"] == "fuse_set":
            tail = f" [{int(round(e['cond'] / 10))} шт.]"
        return it.get("name", e["id"]) + tail

    def items(self):
        g = self.g
        out = []
        for i in (1, 0):
            e = g.p.hands[i]
            if not e:
                continue
            k = ITEMS.get(e["id"], {}).get("kind")
            if k == "food":
                out.append(((f"Съесть: {self._name(e)}", HAND_RU[i] + " рука"), ("eat", i), True))
            elif k == "drink":
                out.append(((f"Выпить: {self._name(e)}", HAND_RU[i] + " рука"), ("eat", i), True))
            elif k == "part":
                out.append(((f"Осмотреть: {self._name(e)}", HAND_RU[i] + " рука"), ("look", i), True))
            out.append(((f"Положить: {self._name(e)}", "рядом / на землю"), ("drop", i), True))
        if any(g.p.hands):
            out.append(("Поменять предметы между руками (Q)", ("swap", 0), True))
        for cont, kind, lab in g.nearby_stores():
            out.append(((f"Взять из: {lab}", f"внутри {len(cont)}"), ("store", kind, lab), True))
        if not out:
            out.append(("Руки пусты. Взять вещь — E на ней (на земле, в багажнике, на стеллаже, в холодильнике).",
                        None, False))
        out.append(("Закрыть", CLOSE, True))
        return out

    def select(self, sel):
        g = self.g
        if sel == CLOSE or sel is None:
            return "close"
        kind = sel[0]
        if kind == "eat":
            i = sel[1]
            return lambda: g.start_eat(i)
        if kind == "look":
            g.open_menu(Dialog("Осмотр детали", eng.inspect_lines(g.p.hands[sel[1]]), wide=True))
        elif kind == "drop":
            e = g.p.hands[sel[1]]
            where = g.drop_hand(sel[1])
            if where:
                g.notify(f"Положили: {self._name(e)} — {where}.", GREEN)
        elif kind == "swap":
            g.swap_hands()
        elif kind == "store":
            for cont, k, lab in g.nearby_stores():
                if lab == sel[2]:
                    g.open_menu(StorageTake(g, cont, k, lab.capitalize()))
        return None

    def hint(self):
        return "Enter — выбрать, Tab/Esc — закрыть"


class StoragePut(Menu):
    """Что положить в хранилище (багажник / холодильник): короткий список того, что у игрока с собой."""
    time_flows = True

    def __init__(self, g, container, kind, title, only=None):
        self.g, self.container, self.kind, self.title, self.only = g, container, kind, title, only

    def lines(self):
        import storage
        n = len(self.container)
        return [f"Внутри: {n} из {storage.CAPACITY.get(self.kind, 99)} мест. Enter — положить (по одному)."]

    def items(self):
        import storage
        out = [((f"Положить: {storage.label(e)}", f"с собой {n}"), e, True)
               for e, n in storage.grouped(self.g.p.inventory, self.only)]
        if not out:
            out.append(("В руках ничего нет.", None, False))
        out.append(("Готово", CLOSE, True))
        return out

    def select(self, e):
        import storage
        if e == CLOSE:
            return "close"
        if storage.put(self.g, self.container, e, self.kind):
            self.g.play_sound("door", 0.3)
            self.g.notify(f"Положили: {storage.label(e)}", GREEN)
        return None


class StorageTake(Menu):
    """Холодильник: взять с собой или съесть на месте; положить своё."""
    time_flows = True

    def __init__(self, g, container, kind, title):
        self.g, self.container, self.kind, self.title = g, container, kind, title

    def lines(self):
        h = self.g.p.hands
        return ["Enter — взять в свободную руку. Еду в руке можно съесть где угодно (E или Tab).",
                "В руках: " + ", ".join(Inventory._name(e) if e else "пусто" for e in (h[0], h[1])) +
                ("  — ОБЕ РУКИ ЗАНЯТЫ" if all(h) else "")]

    def items(self):
        import storage
        out = [((f"Взять: {storage.label(e)}", f"внутри {n}"), ("take", e), True) for e, n in storage.grouped(self.container)]
        if not out:
            out.append(("Пусто. Продукты — в супермаркете «Кауфгут»." if self.kind == "fridge" else "Пусто.", None, False))
        out.append(("Положить своё сюда…", "put", True))
        out.append(("Закрыть", CLOSE, True))
        return out

    def select(self, sel):
        import storage
        if sel == CLOSE:
            return "close"
        if sel == "put":
            self.g.open_menu(StoragePut(self.g, self.container, self.kind, "Положить в " + self.title.lower()))
            return None
        if isinstance(sel, tuple) and sel[0] == "take" and storage.take(self.g, self.container, sel[1]):
            self.g.notify(f"Взяли в руку: {storage.label(sel[1])}", GREEN)
        return None


class TireMenu(Menu):
    """Шины: протектор каждой, давление (с манометром — точно, без — «на глаз»), подкачка компрессором."""
    time_flows = True
    wide = True

    def __init__(self, g, key, station=False):
        self.g, self.key, self.station = g, key, station
        self.sel = None

    @property
    def car(self):
        return self.g.cars[self.key]

    @property
    def title(self):
        return f"Шины — {self.car.name}" + (" · колонка «Воздух» на заправке" if self.station else "")

    def gauge(self):
        return self.station or self.g.has("compressor") or self.g.has("tire_gauge")

    def pump(self):
        return self.station or self.g.has("compressor")

    def lines(self):
        import tires
        car, g = self.car, self.g
        amb = g.ambient_temp(car.x)
        out = [f"Норма (при +20°C): перёд {tires.nominal(car, 'tire_fl'):.1f}, зад {tires.nominal(car, 'tire_rl'):.1f} бар. "
               f"Сейчас {amb:+.0f}°C — на холоде давление ниже." +
               ("" if self.gauge() else " Манометра нет — давление только «на глаз» (манометр/компрессор — на заправке)."),
               "Протектор: новая 8 мм, по закону не меньше 1,6 мм. Лысая шина на мокром и снегу — как коньки."]
        return out

    def items(self):
        import tires
        car, g = self.car, self.g
        amb = g.ambient_temp(car.x)
        out = []
        for s in car.tire_list():
            nm = tires.SLOT_RU[s].capitalize()
            if not car.has(s):
                out.append(((f"{nm}: шины нет", "поставить — «Детали»"), None, False))
                continue
            mm = tires.tread_mm(car, s)
            p = tires.pressure(car, s, amb)
            n = tires.nominal(car, s)
            ptxt = f"{p:.1f}/{n:.1f} бар" if self.gauge() else ("на вид спущена" if p < n * 0.7 else "на вид нормально")
            out.append(((f"{nm}: протектор {mm:.1f} мм ({car.c(s) * 100:.0f}%) · {ptxt}", tires.state_text(car, s, amb)),
                        ("tire", s), True))
            if self.sel == s:
                ok = self.pump()
                out.append(((f"   ↳ подкачать +0,1 бар", "компрессор" if not self.station else "колонка"), ("add", s, 0.1), ok))
                out.append(((f"   ↳ довести до нормы {n:.1f} бар", "1–3 мин"), ("norm", s), ok))
                out.append(((f"   ↳ стравить −0,1 бар", "ниппель"), ("add", s, -0.1), True))
        if not self.pump():
            out.append(("Подкачать нечем: компрессор — заправка или магазин «Восток» (35 DM), или бесплатно у колонки «Воздух» "
                        "на заправке", None, False))
        else:
            out.append((("Все шины — до нормы", "5 мин"), "all", True))
        out.append(("Закрыть", CLOSE, True))
        return out

    def select(self, sel):
        import tires
        car, g = self.car, self.g
        if sel == CLOSE:
            return "close"
        amb = g.ambient_temp(car.x)
        tp = tires.ensure(car)
        k20 = 293 / (273 + amb)                        # сколько «на холодную» соответствует показанию сейчас

        def fix(s, target_now):
            if car.c(s) < 0.05:
                g.notify(f"{tires.SLOT_RU[s].capitalize()}: шина разорвана — держать давление не будет, только замена.", RED)
                return
            tp[s] = round(max(0.0, (target_now + 1.013) * k20 - 1.013), 2)
        if isinstance(sel, tuple) and sel[0] == "tire":
            self.sel = None if self.sel == sel[1] else sel[1]
        elif isinstance(sel, tuple) and sel[0] == "add":
            s = sel[1]
            fix(s, tires.pressure(car, s, amb) + sel[2])
            g.advance(1)
            g.play_sound("tool", 0.2)
        elif isinstance(sel, tuple) and sel[0] == "norm":
            s = sel[1]
            before = tp[s]
            if car.c(s) < 0.05:
                fix(s, 0)
            else:
                tp[s] = tires.nominal(car, s)            # норма — «на холодную», как пишут на стойке двери
            g.advance(max(1, int(abs(tp[s] - before) * 3)))
            g.play_sound("tool", 0.3)
        elif sel == "all":
            for s in car.tire_list():
                if car.has(s) and car.c(s) >= 0.05:
                    tp[s] = tires.nominal(car, s)
            g.advance(5)
            g.notify("Давление во всех шинах — по норме.", GREEN)
        return None


class FuseBox(Menu):
    """Блок предохранителей конкретной машины: осмотр, замена, проверка, прозвонка, чистка контактов."""
    time_flows = True
    wide = True

    def __init__(self, g, key):
        self.g, self.key = g, key
        self.sel = None
        self.out = []            # последний результат проверки/прозвонки

    @property
    def car(self):
        return self.g.cars[self.key]

    @property
    def title(self):
        if self.sel:
            return f"F{elec.fuse_no(self.sel)} {elec.BY_KEY[self.sel]['amp']}А — {elec.circuit_name(self.car, self.sel)}"
        return f"Блок предохранителей — {self.car.name}"

    def lines(self):
        g, car = self.g, self.car
        d = elec.data(car)
        if not self.sel:
            nb = sum(1 for v in d["fuses"].values() if v == "blown")
            return [f"Где: {elec.box_name(car)}. Крышка снята. Перегоревших: {nb}.",
                    f"Запасных предохранителей: {elec.fuses_left(g)} · мультиметр: {'есть' if g.has('multimeter') else 'нет'}"
                    f" · набор ключей: {'есть' if g.has('toolbox') else 'нет'}",
                    "Выберите предохранитель: осмотреть, заменить, проверить цепь, прозвонить."]
        k = self.sel
        c = elec.BY_KEY[k]
        st = {"ok": "цел (нить целая)", "blown": "ПЕРЕГОРЕЛ — нить разорвана, корпус потемнел",
              "bug": "вместо него — «жучок» из проволоки"}[d["fuses"][k]]
        path = " → ".join(elec.SEGMENTS[x][0].split(" — ")[0] for x in ["box"] + c["path"])
        out = [f"Предохранитель: {st}.", f"Цепь: {path}. Потребитель: {c['consumer'][0]}."]
        f = d["faults"].get(k)
        if f and f["found"]:
            need, what = elec.fix_needs(car, k)
            out.append(f"Найдено: {elec.KIND_RU[f['kind']]} — {elec.SEGMENTS[f['seg']][0]}. "
                       f"Доступ: {elec.SEGMENTS[f['seg']][1]}. Нужно: {what}.")
        return out + [""] + self.out

    def items(self):
        g, car = self.g, self.car
        d = elec.data(car)
        if not self.sel:
            out = []
            for k in elec.KEYS:
                st = d["fuses"][k]
                tag = {"ok": "цел", "blown": "ПЕРЕГОРЕЛ", "bug": "жучок"}[st]
                f = d["faults"].get(k)
                if f and f["found"]:
                    tag += " · найдена неисправность"
                out.append(((f"F{elec.fuse_no(k)} {elec.BY_KEY[k]['amp']}А  {elec.circuit_name(car, k)}", tag),
                            ("fuse", k), True))
            out.append(("Закрыть", CLOSE, True))
            return out
        k = self.sel
        st = d["fuses"][k]
        f = d["faults"].get(k)
        n = elec.fuses_left(g)
        out = []
        if st != "ok":
            out.append(((f"Поставить новый предохранитель {elec.BY_KEY[k]['amp']}А", f"запасных: {n}"), "replace", n > 0))
            if n <= 0:
                out.append(("Нет запасных: набор предохранителей — заправка или магазин «Восток» (4 DM)", None, False))
        out.append((("Включить цепь и проверить", "1 мин"), "test", True))
        out.append((("Прозвонить цепь мультиметром", "15 мин"), "probe", g.has("multimeter")))
        if not g.has("multimeter"):
            out.append(("Мультиметра нет — магазин «Восток» или автосалон Крюгера, 39 DM", None, False))
        if f and f["found"] and f["kind"] == "corrosion":
            out.append((("Зачистить окисленные контакты гнезда", "10 мин"), "clean", True))
        elif f and f["found"]:
            need, what = elec.fix_needs(car, k)
            out.append(((f"Неисправность — на машине (отмечена красным): {elec.SEGMENTS[f['seg']][1]}", what), None, False))
        if st != "bug":
            out.append((("Поставить «жучок» из проволоки (не сгорит — но при КЗ сгорит проводка!)", "2 мин"), "bug", True))
        out.append(("← Назад к блоку", "back", True))
        return out

    def back(self):
        if self.sel:
            self.sel = None
            self.out = []
            return False
        return True

    def select(self, sel):
        g, car = self.g, self.car
        if sel == CLOSE:
            return "close"
        if sel == "back":
            self.back()
            return None
        if isinstance(sel, tuple) and sel[0] == "fuse":
            self.sel, self.out = sel[1], []
            return None
        k = self.sel
        d = elec.data(car)
        if sel == "replace":
            if not elec.take_fuse(g):
                return None
            g.advance(2)
            d["fuses"][k] = "ok"
            d["t"].pop(k, None)
            g.play_sound("click", 0.6)
            self.out = [f"Новый предохранитель F{elec.fuse_no(k)} стоит. Включите цепь, чтобы проверить."]
        elif sel == "test":
            g.advance(1)
            self.out = [elec.test_circuit(car, k)]
            g.play_sound("click", 0.5)
        elif sel == "probe":
            g.advance(15, working=True)
            self.out = elec.probe(car, k)
            g.play_sound("tool", 0.4)
        elif sel == "clean":
            r = elec.repair(g, car, k)
            if r:
                self.out = [r]
                g.notify(r, GREEN, 6)
        elif sel == "bug":
            g.advance(2)
            d["fuses"][k] = "bug"
            self.out = ["«Жучок» стоит. Цепь больше не защищена: если неисправность осталась — будет плавиться проводка. "
                        "С жучком техосмотр не пройти."]
        return None


class CarWork(Menu):
    """Капот открыт: детали, жидкости, зарядка, кузов."""
    time_flows = True
    side = True

    def __init__(self, g):
        self.g = g
        self.stack = ["root"]
        self.slot = None
        self.panel = None
        self.ekey = None

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
        if m == "tune":
            return "Тюнинг — турбонаддув"
        if m == "engine":
            return f"Двигатель {eng.layout(self.car.model)['name']} — разборка и сборка"
        if m == "epart":
            return eng.label(self.car, self.ekey)
        if m == "boost":
            return "Режим наддува"
        if m == "lift":
            return "Подъём машины — домкрат и подставки"
        return f"{PANELS[self.panel]}: {self.car.rust[self.panel]:.0f}% ржавчины"

    def tune_lines(self):
        car = self.car
        if car.model in LEGEND:
            nodes = tune_slots(car.model)
            done = [n for n in nodes if car.has_tune(n)]
            sp_ = car.spec
            hp = max(sp_["tq_peak"] * (1 - 0.55 * ((r - sp_["tq_rpm"]) / sp_["tq_width"]) ** 2) * r / 7121
                     for r in range(1000, int(sp_["cut"]) + 1, 100))
            cost_left = sum(ITEMS[pid]["price"] for n, (pid, _, _) in nodes.items() if n not in done)
            head = ("ЛЕГЕНДА: " + car.name + " — собран полностью!") if is_legend(car) else \
                f"Комплект Shelby GT500: {len(done)} из {len(nodes)} · осталось купить на {cost_left:,.0f} DM".replace(",", " ")
            return [head, f"Сейчас ≈{hp:.0f} л.с., момент {car.spec['tq_peak']:.0f} Н·м · масса {car.spec['mass']:.0f} кг · "
                    f"сцепление шин ×{car.spec['grip']:.2f} · тормоза ×{car.spec['brake']:.2f}",
                    "Каждая деталь сразу меняет машину; все десять — и это уже «Eleanor». Детали — в автосалоне Крюгера."]
        base_hp = {"civic": 85}.get(car.model, 0)
        if not car.has_tune("turbo"):
            return [f"Сейчас: атмосферный мотор, {base_hp} л.с. Турбина необязательна — Civic ездит и без неё.",
                    "Сначала ставится турбокит (5 ч, только в гараже). Интеркулер снимает перегрев и детонацию, "
                    "буст-контроллер открывает режимы «Спорт» и «Гонка». Всё продаётся в автосалоне Крюгера."]
        key, bar = car.boost_setting
        eff = bar * (0.35 + 0.65 * car.tc("turbo"))
        hp = base_hp * (1 + TORQUE_PER_BAR * eff)
        ic = "есть" if car.has_tune("intercooler") else "НЕТ (на наддуве выше 0.5 бар — детонация)"
        return [f"Режим: {BOOST_BY_KEY[key][0]} · фактически ~{eff:.2f} бар · около {hp:.0f} л.с. (без турбины {base_hp})",
                f"Турбина {car.tc('turbo') * 100:.0f}% · интеркулер: {ic}. Наддув греет мотор, сильнее изнашивает "
                "двигатель, сцепление и КПП, увеличивает расход. Старое масло быстро убивает турбину."]

    def engine_lines(self):
        car = self.car
        L = eng.layout(car.model)
        if self.stack[-1] == "engine":
            fl = car.eng_flags or {}
            warn = []
            if fl.get("timing_off"):
                warn.append("метки ГРМ сбиты")
            if fl.get("head_loose"):
                warn.append("ГБЦ затянута не по схеме")
            if fl.get("gasket_reused"):
                warn.append("стоит старая прокладка ГБЦ")
            n_in = sum(1 for v in car.eng.values() if v)
            return [f"{'Двухтактный' if L['stroke'] == 2 else 'Четырёхтактный'}, {L['cyl']} цил. · деталей на месте: "
                    f"{n_in} из {len(car.eng)} · состояние мотора {car.c('engine') * 100:.0f}%",
                    f"Компрессия {eng.compression(car) * 100:.0f}% · вкладыши {eng.bearings(car) * 100:.0f}% · "
                    f"давление масла {eng.oil_pressure(car) * 100:.0f}%" + ("  ⚠ " + ", ".join(warn) if warn else ""),
                    "Снимать можно только то, до чего есть доступ; ставить — в обратном порядке. Инструмент — набор ключей."]
        k = self.ekey
        out = []
        if eng.has(car, k):
            out.append(f"Стоит на машине: {eng.cond(car, k) * 100:.0f}%. "
                       + (fast.describe(car, "eng:" + k) if not k.startswith("slot:") else fast.describe(car, k[5:])))
            covered = [c for c in eng.COVERED.get(k, ()) if eng.has(car, c)]
            if covered:
                out.append("Не видно: закрыто — " + ", ".join(eng.label(car, c).lower() for c in covered) + ".")
            else:
                pid = car.eng[k]["id"] if not k.startswith("slot:") else car.parts[k[5:]]["id"]
                out += eng.inspect_lines({"id": pid, "cond": eng.cond(car, k) * 100})[1:2]
            ok, why = eng.can_remove(car, k) if not k.startswith("slot:") else (not eng.blockers(car, k), "")
            if not ok and why:
                out.append(why)
        else:
            out.append("Не установлено.")
            ok, why = eng.can_install(car, k)
            if not ok:
                out.append(why)
        return out

    def lines(self):
        car, g = self.car, self.g
        if self.stack[-1] in ("tune", "boost"):
            return self.tune_lines()
        if self.stack[-1] in ("engine", "epart"):
            return self.engine_lines()
        tuv = "действует" if car.tuv_until >= g.day else "нет"
        pos = []
        if underside.enabled(g):
            lying = getattr(g.p, "under_car", None) == g.cur
            st = underside.status(car)
            pos = [("ВЫ ПОД МАШИНОЙ: доступно то, что снизу (поддон, КПП, сцепление, выхлоп, подвеска, рулевые тяги, "
                    "стартер, низ двигателя)" if lying else "Вы у открытого капота: доступно то, что сверху; низ машины — "
                    "лёжа под ней") + f" · просвет {underside.clearance(car, 0.5) * 100:.0f} см"
                   + (f" · поднято: {st}" if st else "")]
        if self.stack[-1] == "lift":
            return pos + ["Домкрат поднимает одну сторону на 30 см. Лежать под машиной на одном домкрате опасно — "
                          "подставьте подставки, домкрат освободится.",
                          "Поднятая машина не поедет. Домкрат и подставки — магазин «Восток» и автосалон Крюгера (расходники)."]
        return pos + [
            f"{'Дизель' if car.sp('diesel') else 'Бензин'} {car.fuel:.1f}/{car.tank:.0f} л · "
            + (f"Масло {car.oil:.2f}/{car.oil_cap} л ({car.oil_quality:.0f}%) · " if car.oil_cap > 0 else "Масло — в бензине · ")
            + (f"Антифриз {car.coolant:.1f}/{car.coolant_cap} л" if car.coolant_cap > 0 else "Охлаждение воздушное"),
            f"Торм. жидк. {car.brake_fluid:.0f}% · АКБ {car.battery_charge:.0f}% · Темп. {car.temp:.0f}°C · "
            f"Пробег {car.odometer:.0f} км",
            (f"ПОСЛЕ АВАРИИ: {damage.damage_text(car)}" + (" — «ТОТАЛ», ремонт нецелесообразен" if damage.is_totaled(car) else "")
             if car.deforms else "Кузов без аварийных повреждений") + " · "
            f"Техосмотр: {tuv} · Номера: {car.plate if car.registered else 'нет'} · "
            + ("в гараже" if self.in_garage() else "на улице (сварка и зарядка недоступны)"),
        ] + ([("⚠ Предписание полиции: " + "; ".join(car.mangel["items"]) +
               " — устранить и пройти техосмотр" + (", затем ратуша" if not car.registered else "") +
               f" (срок: ещё {max(0, car.mangel['until'] - g.day)} дн.)")] if car.mangel else [])

    def items(self):
        g, car = self.g, self.car
        m = self.stack[-1]
        out = []
        if m == "root":
            out = [("Детали (снять / поставить)", "parts", True),
                   ("Жидкости (масло, антифриз, бензин...)", "fluids", True),
                   ("Кузов и ржавчина (сварка, покраска)", "body", True),
                   (("Зарядить аккумулятор", "3 ч, в гараже"), "charge", True)]
            if car.has("engine") and car.eng:
                n_in = sum(1 for v in car.eng.values() if v)
                out.append(((f"Двигатель: разборка и сборка до болта", f"{n_in}/{len(car.eng)} деталей"), "engine", True))
            lk = []
            if car.lock_broken:
                lk.append("замок двери сломан")
            if car.hotwired:
                lk.append("замок зажигания разобран")
            out.append(((f"Заменить замки и получить 2 новых ключа" + (f" ({', '.join(lk)})" if lk else ""),
                         "1 ч, комплект замков"), "lockset", True))
            nbad = sum(1 for k in elec.KEYS if not elec.works(car, k) or elec.fault(car, k))
            import tires as _t
            worst = min((_t.tread_mm(car, s_) for s_ in car.tire_list() if car.has(s_)), default=0)
            bad_p = sum(1 for s_ in car.tire_list() if car.has(s_) and abs(_t.pressure(car, s_, g.ambient_temp(car.x))
                                                                             / _t.nominal(car, s_) - 1) > 0.12)
            out.append(((f"Шины и давление (протектор до {worst:.1f} мм" + (f", давление не в норме: {bad_p}" if bad_p else "")
                         + ")", "осмотр, подкачка"), "tires", True))
            out.append(((f"Электрика: {elec.box_name(car)}", f"проблемных цепей: {nbad}" if nbad else "всё в порядке"),
                        "fusebox", True))
            out.append((("Диагностика: электрика" + (" + двигатель (компрессия, давление масла)"
                                                     if car.has("engine") and car.eng else ""), "20 мин"), "diag", True))
            if tune_slots(car.model):
                out.append(("Тюнинг (турбина, интеркулер, наддув)", "tune", True))
            if underside.enabled(g) and getattr(g.p, "under_car", None) != g.cur:
                st = underside.status(car)
                out.append((("Подъём машины: домкрат и подставки", st or "стоит на колёсах"), "lift", True))
            out.append(("Закрыть меню" if getattr(g.p, "under_car", None) == g.cur else "Закрыть капот", CLOSE, True))
        elif m == "lift":
            lf = underside.lift(car)
            for end in ("f", "r"):
                nm = underside.END_RU[end].capitalize()
                by = underside.held_by(car, end)
                if by is None:
                    out.append(((f"{nm}: поднять домкратом", f"3 мин · домкратов под рукой: {g.count('jack')}"),
                                ("jack", end), True))
                elif by == "jack":
                    out.append(((f"{nm}: поставить на подставки (домкрат освободится)",
                                 f"4 мин · подставок под рукой: {g.count('stands')}"), ("stands", end), True))
                    out.append(((f"{nm}: опустить домкрат", "2 мин"), ("lower", end), True))
                else:
                    out.append(((f"{nm}: снять с подставок и опустить", "4 мин, нужен домкрат"), ("lower", end), True))
            out.append(("← Назад", "back", True))
        elif m == "tune":
            for node, (pid, mins, garage) in tune_slots(car.model).items():
                p = car.tune.get(node)
                nm = TUNE_NAMES[node]
                if isinstance(p, dict):
                    out.append(((f"{nm}: снять — {item_name(p['id'])} ({p['cond']:.0f}%)", f"{mins} мин"),
                                ("tune_rm", node), True))
                    continue
                cands = sorted([e for e in g.available() if e["id"] == pid], key=lambda e: -e["cond"])
                ok = node not in NEEDS_TURBO or car.has_tune("turbo")
                for e in cands[:3]:
                    out.append(((f"{nm}: поставить ({e['cond']:.0f}%)" + ("" if ok else " — сначала турбина"),
                                 f"{mins} мин" + (", гараж" if garage else "")), ("tune_in", node, e), ok))
                if not cands:
                    out.append((f"{nm}: нет под рукой (в руках / открытом багажнике / на стеллаже) — автосалон Крюгера, {ITEMS[pid]['price']:.0f} DM", None, False))
            if "turbo" in tune_slots(car.model):
                key = car.tune.get("boost", "soft")
                out.append(((f"Режим наддува: {BOOST_BY_KEY[key][0].split(' (')[0]}", "10 мин"), "boost",
                            car.has_tune("turbo")))
            out.append(("← Назад", "back", True))
        elif m == "boost":
            cur = car.tune.get("boost", "soft")
            for key, name, bar, need in BOOST_PRESETS:
                miss = [TUNE_NAMES[n] for n in need if not car.has_tune(n)]
                tag = "  ← сейчас" if key == cur else ""
                out.append(((name + tag, "нужен " + ", ".join(miss) if miss else f"{bar:.2f} бар"), ("set_boost", key),
                            not miss))
            out.append(("← Назад", "back", True))
        elif m == "parts":
            for s, (name, pid, mins) in car.slots.items():
                p = car.parts.get(s)
                tag = (" · снизу" if underside.is_under(s) else "") if underside.enabled(g) else ""
                out.append(((name + tag, "НЕТ" if p is None else f"{p['cond']:.0f}%"), ("slot", s), True))
            out.append(("← Назад", "back", True))
        elif m == "slot":
            name, pid, mins = car.slots[self.slot]
            p = car.parts.get(self.slot)
            if p is not None and fast.loose(car, self.slot):
                n_l = fast.loose(car, self.slot)
                out.append(((f"Затянуть крепёж ({n_l} шт. отпущено)", f"{int(n_l * fast.minutes_each(car, self.slot))} мин"),
                            ("tighten", self.slot), True))
            if p is not None:
                out.append(((f"Снять: {item_name(p['id'])} ({p['cond']:.0f}%) — с откручиванием крепежа", f"{mins} мин"),
                            ("remove", self.slot), True))
            else:
                cands = sorted([e for e in g.available() if e["id"] == pid], key=lambda e: -e["cond"])
                for e in cands:
                    out.append(((f"Поставить: {item_name(pid)} ({e['cond']:.0f}%)", f"{mins} мин"), ("install", e), True))
                if not cands:
                    out.append((f"Нет детали «{item_name(pid)}» под рукой (руки, открытый багажник, стеллаж)", None, False))
            out.append(("← Назад", "back", True))
        elif m == "engine":
            out.append((("Разобрать полностью (всё, что снимается)", self._chain_time(self._full_chain())),
                        "e_strip", bool(self._full_chain())))
            asm = self._assembly_plan()
            out.append((("Собрать из деталей под рукой (аккуратно, по меткам)", f"{len(asm)} дет."), "e_build", bool(asm)))
            for k in eng.keys(car.model) + [k for k in eng.graph(car.model) if k.startswith("slot:")]:
                if eng.has(car, k):
                    free = eng.can_remove(car, k)[0] if not k.startswith("slot:") else not eng.blockers(car, k)
                    st = f"{eng.cond(car, k) * 100:.0f}%" + ("" if free else "  (закрыто)")
                else:
                    have = [e for e in g.available() if e["id"] == self._pid(k)]
                    st = "СНЯТО" + (f" · под рукой {len(have)}" if have else "")
                tag = (" · снизу" if underside.is_under(underside.eng_key(k)) else "") if underside.enabled(g) else ""
                out.append(((eng.label(car, k) + tag, st), ("epart", k), True))
            out.append(("← Назад", "back", True))
        elif m == "epart":
            k = self.ekey
            mins = eng.minutes(car, k)
            if k.startswith("slot:"):
                out.append((("Открыть в меню деталей", ""), ("slot", k[5:]), True))
            elif eng.has(car, k):
                if fast.loose(car, "eng:" + k):
                    n_l = fast.loose(car, "eng:" + k)
                    out.append(((f"Затянуть крепёж ({n_l} шт. отпущено)", f"{int(n_l * fast.minutes_each(car, 'eng:' + k))} мин"),
                                ("tighten", "eng:" + k), True))
                ok, why = eng.can_remove(car, k)
                out.append(((f"Снять: {eng.label(car, k)}", f"{mins} мин"), ("e_rm", k), ok))
                if not ok:
                    chain = eng.removal_chain(car, k)
                    out.append(((f"Снять всё мешающее и её ({len(chain)} дет.)", self._chain_time(chain)), ("e_chain", k), True))
                covered = [c for c in eng.COVERED.get(k, ()) if eng.has(car, c)]
                out.append((("Осмотреть на месте", "5 мин"), ("e_look", k), not covered))
            else:
                ok, why = eng.can_install(car, k)
                cands = sorted([e for e in g.available() if e["id"] == self._pid(k)], key=lambda e: -e["cond"])[:4]
                for e in cands:
                    extra = " + ГБЦ в сборе" if (e.get("sub") or {}).get("head") else ""
                    if k == "head":
                        out.append(((f"Поставить ({e['cond']:.0f}%{extra}) — затянуть по схеме, моментом", f"{int(mins * 1.4)} мин"),
                                    ("e_in", k, e, True), ok))
                        out.append(((f"Поставить ({e['cond']:.0f}%{extra}) — быстро, «на глаз»", f"{int(mins * 0.7)} мин"),
                                    ("e_in", k, e, False), ok))
                    elif k == "timing":
                        out.append(((f"Поставить ({e['cond']:.0f}%) — выставить по меткам", f"{int(mins * 1.4)} мин"),
                                    ("e_in", k, e, True), ok))
                        out.append(((f"Поставить ({e['cond']:.0f}%) — на глаз, без меток", f"{int(mins * 0.6)} мин"),
                                    ("e_in", k, e, False), ok))
                    else:
                        out.append(((f"Поставить ({e['cond']:.0f}%)", f"{mins} мин"), ("e_in", k, e, True), ok))
                if not cands:
                    price = ITEMS.get(self._pid(k), {}).get("price", 0)
                    out.append((f"Нет под рукой — магазин запчастей ({price:.0f} DM) или донор на свалке", None, False))
            out.append(("← Назад", "back", True))
        elif m == "fluids":
            out = [((f"Долить масло 15W-40 (канистр: {g.count('oil')})", "10 мин"), "oil_add", car.oil_cap > 0),
                   (("Слить старое масло", "20 мин"), "oil_drain", True),
                   ((f"Долить антифриз (канистр: {g.count('coolant')})", "10 мин"), "cool_add", car.coolant_cap > 0),
                   ((f"Долить тормозную жидкость ({g.count('brake_fl')})", "15 мин"), "brake_add", True),
                   ((f"Залить бензин из канистры ({g.count('fuel_can')})", "5 мин"), "fuel_add", True),
                   ("← Назад", "back", True)]
        elif m == "body":
            zn = damage.zones(car)
            names = {"front": "перед", "rear": "зад", "left": "левый борт", "right": "правый борт"}
            total = damage.is_totaled(car)
            for zk, depth in zn.items():
                if depth > 0.02:
                    need = max(1, math.ceil(depth * 8))
                    hrs = max(1, round(depth * 8))
                    hrs = max(1, round(depth * 8 * (2.5 if total else 1.0)))
                    tools = f"{need} лист., сварка" if self._tools(need) else "без материалов"
                    out.append(((f"Выправить после аварии: {names[zk]} — смято {depth * 100:.0f} см",
                                 f"~{hrs} ч, {tools}"), ("straighten", zk), True))
            if total:
                out.append(((f"Стапель у Крюгера: восстановить геометрию кузова", f"{damage.FRAME_SHOP_PRICE:.0f} DM"),
                            "frame_shop", True))
            for p, name in PANELS.items():
                tag = " (покрашено)" if car.painted[p] else ""
                out.append(((name + tag, f"{car.rust[p]:.0f}%"), ("panel", p), True))
            out.append(("← Назад", "back", True))
        elif m == "panel":
            need = 2 if self.panel in ("floor", "sill_l", "sill_r") else 1
            out = [((f"Вырезать гниль и вварить металл ({need} лист.)", "2 ч"), "weld", True) if self._tools(need) else
                   (("Залатать гниль без сварки (выколотка, холодная сварка)", "4 ч"), "weld", True),
                   (("Обработать преобразователем ржавчины", "20 мин"), "conv", True),
                   (("Загрунтовать и покрасить", "40 мин"), "paint", True),
                   ("← Назад", "back", True)]
        return out

    def back(self):
        if len(self.stack) > 1:
            self.stack.pop()
            return False
        return True

    def _acc(self, k, heavy=None):
        """Доступ к детали из того места, где сейчас игрок (сверху / из-под машины)."""
        ok, why = underside.access(self.g, self.g.cur, k, heavy)
        if not ok:
            self.g.notify(why, RED, 7)
        return ok

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
        if isinstance(sel, tuple) and sel[0] == "tighten":
            if not g.need("toolbox"):
                return None
            k = sel[1]
            if not self._acc(k, heavy=False):
                return None
            self.work(int(fast.loose(car, k) * fast.minutes_each(car, k)) or 5)
            while fast.loose(car, k):
                fast.screw(car, k)
            g.notify("Весь крепёж затянут.", GREEN)
            return None
        if sel in ("parts", "fluids", "body", "tune", "boost", "engine", "lift"):
            self.stack.append(sel)
            return None
        if isinstance(sel, tuple) and sel[0] in ("jack", "stands", "lower"):
            fn = {"jack": underside.jack_up, "stands": underside.put_stands, "lower": underside.lower}[sel[0]]
            fn(g, g.cur, sel[1])
            return None
        if isinstance(sel, tuple) and sel[0] == "epart":
            self.ekey = sel[1]
            self.stack.append("epart")
            return None
        if sel == "diag":
            return self.diagnose()
        if sel == "fusebox":
            g.open_menu(FuseBox(g, g.cur))
            return None
        if sel == "tires":
            from world import PUMP_ZONE as _PZ
            g.open_menu(TireMenu(g, g.cur, station=point_in(_PZ, car.x, car.y)))
            return None
        if sel == "lockset":
            import keys
            if not g.need("toolbox") or not g.need("lockset", "комплект замков (магазин «Восток» или автосалон Крюгера, 45 DM)"):
                return None
            g.take_item("lockset")
            self.work(60)
            car.key_code = f"{random.randint(10000, 99999)}"
            car.lock_broken = car.hotwired = False
            car.locked = False
            car.ign_key = None
            g.give(keys.make(g, g.cur))
            g.keyhook.append(keys.make(g, g.cur, spare=True))
            g.notify("Новые личинки и замок зажигания стоят. Новый ключ — у вас, запасной — на ключнице дома. "
                     "Старые ключи больше не подходят.", GREEN, 10)
            return None
        if sel in ("e_strip", "e_build") or (isinstance(sel, tuple) and sel[0] in ("e_rm", "e_chain", "e_in", "e_look")):
            return self.engine_work(sel)
        if isinstance(sel, tuple) and sel[0] in ("tune_rm", "tune_in", "set_boost"):
            self.tune_work(sel)
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
            elif not g.need("charger"):
                pass
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
            if not self._acc(s):
                return None
            if not g.need("toolbox"):
                return None
            gk = eng.graph(car.model).get("slot:" + s)
            if gk and car.eng and car.parts.get("engine"):
                b = eng.blockers(car, "slot:" + s)
                if b:
                    g.notify("Сначала снимите: " + ", ".join(eng.label(car, x) for x in b), RED)
                    return None
                if sel[0] == "install":
                    mn = eng.missing_needs(car, "slot:" + s)
                    if mn:
                        g.notify("Сначала поставьте: " + ", ".join(eng.label(car, x) for x in mn), RED)
                        return None
            if sel[0] == "remove":
                part = car.parts[s]
                self.work(car.slots[s][2])
                car.parts[s] = None
                fast.on_removed(car, s)
                entry = {"id": part["id"], "cond": round(float(part["cond"]), 1)}
                if s == "engine":
                    car.oil = 0.0
                    entry["sub"] = eng.remove_whole(car)          # внутренности едут вместе с двигателем
                g.give(entry)
                g.notify(f"Снято: {item_name(part['id'])} ({part['cond']:.0f}%)", GREEN)
            else:
                e = sel[1]
                g.take_item(e["id"], e)
                self.work(car.slots[s][2])
                car.parts[s] = {"id": e["id"], "cond": e["cond"]}
                fast.on_placed(car, s, tightened=True)
                elec.on_slot_installed(car, s)
                if s == "engine":
                    eng.install_whole(car, e)
                if s == "battery":
                    car.battery_charge = 60.0 if e["cond"] > 95 else 20.0
                g.notify(f"Установлено: {item_name(e['id'])}", GREEN)
                if s == "engine":
                    g.notify("Не забудьте залить масло в новый двигатель!", YELLOW)
            self.stack.pop()
        elif sel == "oil_add" and car.eng and car.has("engine") and ("oil_pan" in car.eng and car.eng["oil_pan"] is None):
            g.notify("Масло выльется на землю — не стоит масляный поддон.", RED)
        elif sel == "cool_add" and car.eng and car.has("engine") and any(
                k in car.eng and car.eng[k] is None for k in ("water_pump", "thermostat", "head", "head_gasket")):
            g.notify("Антифриз вытечет — система охлаждения разобрана (помпа/термостат/ГБЦ).", RED)
        elif sel == "oil_add":
            if not g.has("oil"):
                g.notify("Нет масла. Купите в магазине «Восток» или на заправке.", RED)
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
            if self.need_off() and self._acc("eng:oil_pan", heavy=False):      # пробка — внизу поддона
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
        elif isinstance(sel, tuple) and sel[0] == "straighten":
            self.straighten(sel[1])
        elif sel == "frame_shop":
            if g.pay(damage.FRAME_SHOP_PRICE):
                g.advance(60 * 24 * 2)
                car.deforms = []
                car.align = 0.0
                car._total_said = False
                g.notify("Крюгер забрал машину на стапель и через два дня вернул с ровной геометрией.", GREEN, 8)
        elif sel in ("weld", "conv", "paint"):
            self.body_work(sel)
        return None

    # ------------------------------------------------------------ двигатель «до болта»
    def _pid(self, k):
        car = self.car
        if k.startswith("slot:"):
            return car.slots[k[5:]][1]
        return eng.part_id(car.model, k)

    def _chain_time(self, chain):
        m = sum(eng.minutes(self.car, k) for k in chain)
        return f"{m // 60} ч {m % 60:02d} мин" if m >= 60 else f"{m} мин"

    class _Sim:
        """Копия машины для расчёта порядка работ (ничего не меняет на самой машине)."""
        def __init__(self, car):
            self.model, self.slots, self.eng_flags = car.model, car.slots, dict(car.eng_flags or {})
            self.eng = dict(car.eng)
            self.parts = dict(car.parts)

    def _full_chain(self):
        """Порядок полной разборки: всё внутреннее + навесное, которое мешает (впуск, выпуск, КПП...)."""
        car = self.car
        if not car.has("engine") or not car.eng:
            return []
        sim = self._Sim(car)
        g_ = eng.graph(car.model)
        cand = eng.keys(car.model) + sorted({b for d in g_.values() for b in d["blocked"] if b.startswith("slot:")})
        order = []
        progress = True
        while progress:
            progress = False
            for k in cand:
                if not eng.has(sim, k):
                    continue
                if k.startswith("slot:"):
                    ok = not eng.blockers(sim, k)
                else:
                    ok = eng.can_remove(sim, k)[0]
                if ok:
                    order.append(k)
                    if k.startswith("slot:"):
                        sim.parts[k[5:]] = None
                    else:
                        sim.eng[k] = None
                        if k == "head":
                            for ch in eng.HEAD_CHILDREN:
                                sim.eng[ch] = None
                    progress = True
        return order

    def _assembly_plan(self):
        """Что можно поставить из того, что под рукой, и в каком порядке (лучшие по состоянию)."""
        car, g = self.car, self.g
        if not car.has("engine") or not car.eng:
            return []
        sim = self._Sim(car)
        g_ = eng.graph(car.model)
        cand = list(reversed(eng.keys(car.model))) + [k for k in g_ if k.startswith("slot:")] + \
            sorted({b for d in g_.values() for b in d["blocked"] if b.startswith("slot:")})
        used = set()
        plan = []

        def avail(k):
            return [e for e in g.available() if e["id"] == self._pid(k) and id(e) not in used]

        progress = True
        while progress:
            progress = False
            for k in cand:
                if eng.has(sim, k):
                    continue
                have = sorted(avail(k), key=lambda e: -e["cond"])
                if not have:
                    continue
                # не закрывать доступ: если эта деталь мешает другой, которую ещё предстоит поставить, — позже
                if any(k in g_[y]["blocked"] for y in cand if y != k and y in g_ and not eng.has(sim, y) and avail(y)):
                    continue
                if k.startswith("slot:"):
                    ok = not eng.blockers(sim, k) and not eng.missing_needs(sim, k)
                else:
                    ok = eng.can_install(sim, k)[0]
                if ok:
                    e = have[0]
                    used.add(id(e))
                    plan.append((k, e))
                    if k.startswith("slot:"):
                        sim.parts[k[5:]] = {"id": e["id"], "cond": e["cond"]}
                    else:
                        sim.eng[k] = {"id": e["id"], "cond": e["cond"]}
                        for ch, p_ in ((e.get("sub") or {}).get("head") or {}).items():
                            sim.eng[ch] = p_
                    progress = True
        return plan

    def _remove_one(self, k):
        g, car = self.g, self.car
        self.work(eng.minutes(car, k))
        if k.startswith("slot:"):
            s_ = k[5:]
            part = car.parts[s_]
            car.parts[s_] = None
            fast.on_removed(car, s_)
            entry = {"id": part["id"], "cond": round(float(part["cond"]), 1)}
        else:
            entry = eng.take_off(car, k)
        g.give(entry)
        return entry

    def _install_one(self, k, e, careful=True):
        g, car = self.g, self.car
        mins = eng.minutes(car, k)
        if k in ("head", "timing"):
            mins = int(mins * (1.4 if careful else (0.7 if k == "head" else 0.6)))
        g.take_item(e["id"], e)
        self.work(mins)
        if k.startswith("slot:"):
            car.parts[k[5:]] = {"id": e["id"], "cond": e["cond"]}
            fast.on_placed(car, k[5:], tightened=True)
        else:
            eng.put_on(car, k, e, careful)

    def engine_work(self, sel):
        g, car = self.g, self.car
        if not self.need_off():
            return None
        if not g.need("toolbox"):
            return None
        kind = sel if isinstance(sel, str) else sel[0]
        if kind in ("e_look", "e_rm", "e_in") and not self._acc(underside.eng_key(sel[1])):
            return None
        if kind == "e_look":
            self.work(5)
            k = sel[1]
            pid = self._pid(k)
            lines = eng.inspect_lines({"id": pid, "cond": eng.cond(car, k) * 100})
            self.g.open_menu(Dialog(eng.label(car, k), lines, wide=True))
            return None
        if kind == "e_rm":
            ok, why = eng.can_remove(car, sel[1])
            if not ok:
                g.notify(why, RED)
                return None
            e = self._remove_one(sel[1])
            g.notify(f"Снято: {item_name(e['id'])} ({e['cond']:.0f}%)" + (" — вместе с распредвалом и клапанами"
                                                                          if e.get("sub") else ""), GREEN)
            self.stack.pop()
            return None
        if kind in ("e_chain", "e_strip"):
            chain = eng.removal_chain(car, sel[1]) if kind == "e_chain" else self._full_chain()
            done = 0
            stop = ""
            target = sel[1] if kind == "e_chain" else None
            progress = True
            while progress:                       # снимаем всё, что доступно отсюда (сверху / снизу), по порядку
                progress = False
                skipped = []
                for k in chain:
                    if not eng.has(car, k):
                        continue
                    ok = (not eng.blockers(car, k)) if k.startswith("slot:") else eng.can_remove(car, k)[0]
                    if not ok:
                        if kind == "e_chain":
                            break
                        continue
                    acc_ok, why = underside.access(g, g.cur, underside.eng_key(k))
                    if not acc_ok:
                        skipped.append((k, why))
                        if kind == "e_chain":
                            break
                        continue
                    self._remove_one(k)
                    done += 1
                    progress = True
                    if kind == "e_chain":
                        break
                if kind == "e_chain" and target and not eng.has(car, target):
                    break
            if skipped:
                k, why = skipped[0]
                rest = ", ".join(eng.label(car, x).lower() for x, _ in skipped[:4])
                stop = (f" Осталось {'снизу' if underside.is_under(underside.eng_key(k)) else 'сверху'}: {rest}"
                        + ("…" if len(skipped) > 4 else "") + f". {why}")
            g.notify(f"Снято деталей: {done}. Детали — в руках, на стеллаже / в открытом багажнике или на земле рядом."
                     + stop, GREEN if not stop else YELLOW, 9)
            if kind == "e_chain":
                self.stack.pop()
            return None
        if kind == "e_in":
            k, e, careful = sel[1], sel[2], sel[3]
            ok, why = eng.can_install(car, k)
            if not ok:
                g.notify(why, RED)
                return None
            self._install_one(k, e, careful)
            msg = f"Установлено: {item_name(e['id'])} ({e['cond']:.0f}%)"
            if k == "head_gasket" and e["cond"] < 60:
                msg += ". Старая прокладка — скоро потечёт!"
            if not careful and k == "head":
                msg += ". Болты затянуты как попало — прокладка долго не проживёт."
            if not careful and k == "timing":
                msg += (". Метки не совпали — мотор будет троить!" if car.eng_flags.get("timing_off")
                        else ". Повезло — метки совпали.")
            g.notify(msg, YELLOW if (not careful or e["cond"] < 40) else GREEN, 7)
            self.stack.pop()
            return None
        if kind == "e_build":
            plan = self._assembly_plan()
            n = 0
            stop = ""
            for k, e in plan:
                acc_ok, why = underside.access(g, g.cur, underside.eng_key(k))
                if not acc_ok:
                    stop = f" Дальше — {eng.label(car, k).lower()}: {why}"
                    break
                self._install_one(k, e, True)
                n += 1
            left = [k for k in eng.keys(car.model) if not eng.has(car, k)]
            txt = f"Собрано деталей: {n}." + stop
            if stop:
                g.notify(txt, YELLOW, 9)
                return None
            if left:
                txt += " Не хватает: " + ", ".join(eng.label(car, k).lower() for k in left[:5]) + (
                    "…" if len(left) > 5 else "") + " — купите или снимите с донора."
            else:
                txt += " Двигатель собран! Залейте масло и антифриз."
            g.notify(txt, GREEN if not left else YELLOW, 9)
            return None
        return None

    def diagnose(self):
        """Тестер: сначала электрика (всегда), потом компрессия и давление масла — если мотор можно прокрутить."""
        g, car = self.g, self.car
        self.work(20)
        lines = elec.report(car, g.has("multimeter")) + [""]
        if not car.has("engine") or not car.eng:
            lines.append("ДВИГАТЕЛЬ: не установлен.")
        else:
            why = eng.start_problem(car)
            if why:
                lines.append("ДВИГАТЕЛЬ: компрессию не замерить — " + why)
            elif not car.has("starter") or car.battery_charge < 15 or not elec.works(car, "starter"):
                lines.append("ДВИГАТЕЛЬ: компрессию не замерить — стартер не крутит (стартер, АКБ или цепь стартера F2).")
            else:
                car.battery_charge = max(0.0, car.battery_charge - 6)
                lines += ["ДВИГАТЕЛЬ:"] + eng.diagnose(car)
        g.open_menu(Dialog(f"Диагностика: {car.name}", lines, wide=True))
        return None

    def tune_work(self, sel):
        g, car = self.g, self.car
        if sel[0] == "set_boost":
            if not g.need("toolbox"):
                return
            self.work(10)
            car.tune["boost"] = sel[1]
            g.notify(f"Наддув: {BOOST_BY_KEY[sel[1]][0]}", GREEN)
            if sel[1] == "race" and not car.has_tune("intercooler"):
                g.notify("Без интеркулера на 0.85 бар мотор будет детонировать и перегреваться!", ORANGE, 8)
            if sel[1] == "race":
                g.notify("В режиме «Гонка» машина не пройдёт техосмотр.", YELLOW, 8)
            self.stack.pop()
            return
        node = sel[1]
        pid, mins, garage = tune_slots(car.model)[node]
        if not self.need_off():
            return
        if not g.need("toolbox"):
            return
        if garage and not self.in_garage():
            g.notify("Такую работу можно делать только в гараже.", RED)
            return
        if sel[0] == "tune_rm":
            part = car.tune[node]
            self.work(mins)
            car.tune[node] = None
            if node == "paint" and getattr(car, "base_color", None):
                car.color = tuple(car.base_color)               # сняли «покраску» — вернулся старый цвет
            car.refresh_spec()
            g.add_item(part["id"], part["cond"])
            g.notify(f"Снято: {item_name(part['id'])} ({part['cond']:.0f}%)", GREEN)
            if node == "turbo":
                g.notify("Мотор снова атмосферный — машина ездит как стоковая.", YELLOW)
        else:
            e = sel[2]
            if node in NEEDS_TURBO and not car.has_tune("turbo"):
                g.notify("Сначала поставьте турбину.", RED)
                return
            g.take_item(e["id"], e)
            self.work(mins)
            car.tune[node] = {"id": e["id"], "cond": e["cond"]}
            if node == "paint":
                car.base_color = car.color
                car.color = (96, 99, 104)                       # Pepper Grey, чёрные полосы — в 3D
                car.fade = 0.0
                for pn in car.rust:
                    car.rust[pn] = min(car.rust[pn], 2.0)
                    car.painted[pn] = True
            car.refresh_spec()
            if is_legend(car):
                g.notify(f"Готово: {car.name}! 428 Cobra Jet, Toploader, обвес GT500, полосы — легенда ожила.", GREEN, 10)
                g.play_sound("start", 1.0)
            g.notify(f"Установлено: {item_name(e['id'])}", GREEN)
            if node == "turbo":
                g.notify("Турбина стоит! Режим «Мягкий» 0.4 бар. Меняйте масло чаще — турбина его не любит.", YELLOW, 8)

    # ------------------------------------------------------------ кузов: ремонт где угодно
    def _tools(self, need_metal=0):
        """Есть ли сварка и металл: с ними быстрее, но без них тоже можно (выколотка, рихтовка, эпоксидка)."""
        g = self.g
        return g.has("welder") and g.count("metal") >= need_metal

    def straighten(self, zk):
        g, car = self.g, self.car
        depth = damage.zones(car).get(zk, 0.0)
        if depth <= 0:
            return
        total = damage.is_totaled(car)
        hours = max(1.0, depth * 8) * (2.5 if total else 1.0)
        need = max(1, math.ceil(depth * 8))
        how = "руками: домкрат, цепь за столб, кувалда и выколотка"
        if self._tools(need):
            for _ in range(need):
                g.take_item("metal")
            hours *= 0.6
            how = "вытянули цепями, вырезали рваное, вварили заплаты"
        elif g.has("toolbox"):
            hours *= 0.85
        self.work(int(hours * 60), "weld" if "вварили" in how else "tool")
        car.deforms = [d for d in car.deforms if damage.zone_of(d["ds"], d["dl"]) != zk]
        # кузов по-настоящему в норме: геометрия, панели этой зоны, увод
        panels = {"front": ("hood", "lights"), "rear": ("trunk",), "left": ("door_l",), "right": ("door_r",)}[zk]
        for sl in panels:
            pt = car.parts.get(sl)
            if pt is not None and sl != "lights":
                pt["cond"] = max(pt["cond"], 85.0)
        if not car.deforms:
            car.align = 0.0
        elif zk in ("front", "left", "right"):
            car.align *= 0.3
        car._total_said = False
        car._def_cache = None
        where = "в гараже" if self.in_garage() else "прямо на месте"
        g.notify(f"Кузов выправлен {where} ({how}), {hours:.0f} ч. Геометрия в норме, увода нет.", GREEN, 8)

    def body_work(self, what):
        g, car, p = self.g, self.car, self.panel
        if what == "weld":
            need = 2 if p in ("floor", "sill_l", "sill_r") else 1
            if car.rust[p] < 15:
                g.notify("Здесь латать нечего — только поверхностная ржавчина.", YELLOW)
            elif self._tools(need):
                for _ in range(need):
                    g.take_item("metal")
                self.work(120, "weld")
                car.rust[p] = 6.0
                car.painted[p] = False
                g.p.hygiene = max(0, g.p.hygiene - 15)
                g.notify(f"{PANELS[p]}: гниль вырезана, вварена заплатка. Покрасьте, иначе снова заржавеет!", GREEN)
            else:
                # без сварки: вычистить гниль, выколотить, закрыть холодной сваркой/стеклотканью — дольше, но надёжно
                self.work(240, "tool")
                car.rust[p] = 8.0
                car.painted[p] = False
                g.p.hygiene = max(0, g.p.hygiene - 20)
                g.notify(f"{PANELS[p]}: гниль вычищена и закрыта без сварки (выколотка, холодная сварка). "
                         "Покрасьте, иначе снова заржавеет!", GREEN, 7)
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


class Dealer(Menu):
    """Автоплощадка Вебера: купить машину с площадки или продать свою."""
    wide = True

    def __init__(self, g, start=None):
        self.g = g
        self.stack = ["root"]
        self.key = None
        if start:
            self.key = start
            self.stack.append("car")

    def score(self, car):
        base = BASE_VALUE.get(car.model, 900)
        return max(0, min(100, int((self.g.car_value(car) - (250 if car.tuv_until >= self.g.day else 0)) / base * 100)))

    @property
    def title(self):
        m = self.stack[-1]
        if m == "car":
            return f"Вебер: {self.g.cars[self.key].name}"
        if m == "sell":
            return "Вебер: продать машину"
        if m == "confirm":
            return "Продать машину?"
        return "Автоплощадка Вебера — покупка и продажа"

    def lines(self):
        g = self.g
        m = self.stack[-1]
        if m == "root":
            return ["Господин Вебер, в дублёнке и с термосом: «Всё с гарантией... до ворот площадки.»",
                    f"На площадке {len(g.dealer['stock'])} машин. Хотите продать свою — поставьте её на "
                    "площадку приёма (правая часть стоянки, у таблички «Скупка»).",
                    f"У вас: {g.p.money:.2f} DM."]
        if m == "car":
            car = g.cars[self.key]
            info = model_info(car.model) or {}
            price = g.dealer["stock"].get(self.key)
            tuv = "свежий техосмотр (2 года)" if car.tuv_until >= g.day else "без техосмотра"
            worst = sorted(((pt["cond"], car.slots[sl][0]) for sl, pt in car.parts.items() if pt), key=lambda x: x[0])[:3]
            return [f"{car.name}, пробег {car.odometer:,.0f} км, {tuv}, без номеров.".replace(",", " "),
                    info.get("desc", "Проверенная «двойка» — ездит, и ладно.") if car.model != "vaz2102" else
                    "ВАЗ 2102 — «Жигули»-универсал. Простой, ремонтопригодный.",
                    f"Состояние: {self.score(car)}% · мотор {car.c('engine') * 100:.0f}% · КПП {car.c('gearbox') * 100:.0f}% · "
                    f"ржавчина до {car.max_rust():.0f}%.",
                    "Слабые места: " + ", ".join(f"{n} {c:.0f}%" for c, n in worst) + ".",
                    f"Цена: {price:.0f} DM. У вас: {g.p.money:.2f} DM." if price else "Эта машина уже продана."]
        if m == "sell":
            ks = g.cars_in_sell_zone()
            return ["Вебер осматривает машины на площадке приёма и называет цену (обычно ~60% от рыночной).",
                    "" if ks else "На площадке приёма нет ваших машин. Подгоните машину к табличке «Скупка»."]
        if m == "confirm":
            car = g.cars[self.key]
            return [f"Вебер даст за {car.name} {g.dealer_offer(self.key):.0f} DM наличными.",
                    "После продажи машина станет товаром на площадке — выкупить обратно можно, но дороже."]
        return []

    def items(self):
        g = self.g
        m = self.stack[-1]
        if m == "root":
            return [("Купить машину", "buy", True), ("Продать свою машину", "sell", True), ("Уйти", CLOSE, True)]
        if m == "buy":
            out = []
            for k, price in sorted(g.dealer["stock"].items(), key=lambda kv: kv[1]):
                car = g.cars.get(k)
                if car is None:
                    continue
                tuv = " · техосмотр" if car.tuv_until >= g.day else ""
                out.append(((f"{car.name} · {car.odometer / 1000:.0f} тыс. км · {self.score(car)}%{tuv}",
                             f"{price:.0f} DM"), ("car", k), True))
            if not out:
                out.append(("Площадка пуста — новые машины по понедельникам.", None, False))
            out.append(("← Назад", "back", True))
            return out
        if m == "car":
            price = g.dealer["stock"].get(self.key)
            return [((f"Купить за {price:.0f} DM", ""), "buy_it", price is not None), ("← Назад", "back", True)]
        if m == "sell":
            out = []
            for k in g.cars_in_sell_zone():
                car = g.cars[k]
                ok = not (k == "ae86" and not g.goal_done)
                out.append(((f"{car.name} · {self.score(car)}%", f"{g.dealer_offer(k):.0f} DM"), ("sell", k), ok))
            out.append(("← Назад", "back", True))
            return out
        if m == "confirm":
            return [("Да, продать", "sell_it", True), ("← Нет", "back", True)]
        return []

    def back(self):
        if len(self.stack) > 1:
            self.stack.pop()
            return False
        return True

    def select(self, sel):
        g = self.g
        if sel == CLOSE:
            return "close"
        if sel == "back":
            self.back()
            return None
        if sel in ("buy", "sell"):
            if not g.is_open("dealer"):
                g.notify(f"Вебер закрыт. {g.hours_str('dealer')}.", RED)
                return None
            self.stack.append(sel)
            return None
        if isinstance(sel, tuple) and sel[0] == "car":
            self.key = sel[1]
            self.stack.append("car")
            return None
        if sel == "buy_it":
            car = g.cars[self.key]
            if g.buy_from_dealer(self.key):
                g.notify(f"Вы купили {car.name}! Ключи у вас, машина на площадке Вебера. Номера — в ратуше.", GREEN, 8)
                return "close"
            return None
        if isinstance(sel, tuple) and sel[0] == "sell":
            self.key = sel[1]
            self.stack.append("confirm")
            return None
        if sel == "sell_it":
            if g.tow and self.key in (g.tow.get("key"), g.tow.get("by")):
                g.notify("Сначала отвяжите трос.", RED)
                return None
            g.sell_to_dealer(self.key)
            return "close"
        return None


class Dismantle(Menu):
    """Разборка машины на запчасти. Детали — в руки, в открытый багажник рядом или на землю, ставятся на машины той же модели."""
    time_flows = True
    side = True
    HEAVY = ("engine", "gearbox", "clutch")

    def __init__(self, g, key):
        self.g = g
        self.key = key

    @property
    def car(self):
        return self.g.cars[self.key]

    def crane(self):
        c = self.car
        return point_in(JUNKYARD, c.x, c.y) or point_in(GARAGE, c.x, c.y)

    @property
    def title(self):
        return f"Разборка: {self.car.name}"

    def lines(self):
        c = self.car
        whose = "ваша машина" if self.g.owned.get(self.key) else (
            "машина Ковальского — «бери, что открутишь»" if point_in(JUNKYARD, c.x, c.y) else "бесхозная машина")
        n = sum(1 for p_ in c.parts.values() if p_)
        return [f"{whose}. Осталось деталей: {n} из {len(c.slots)}.",
                "Снятые детали подходят к машинам той же модели." +
                ("" if self.crane() else " Мотор, коробку и сцепление без крана не снять — только на свалке или в гараже.")]

    def items(self):
        c = self.car
        out = []
        for sl, (name, pid, mins) in c.slots.items():
            p_ = c.parts.get(sl)
            if p_ is None:
                continue
            heavy_ok = sl not in self.HEAVY or self.crane()
            if c.eng and c.parts.get("engine") and eng.blockers(c, "slot:" + sl):
                heavy_ok = False                       # например, ремень ГРМ под кожухом
            out.append(((f"Снять: {name} ({p_['cond']:.0f}%)", f"{max(5, int(mins * 0.6))} мин"), ("take", sl), heavy_ok))
        # внутренности двигателя донора — то, до чего сейчас есть доступ
        if c.eng and c.parts.get("engine"):
            for k in eng.keys(c.model):
                if eng.has(c, k) and eng.can_remove(c, k)[0]:
                    out.append(((f"Снять с двигателя: {eng.label(c, k)} ({eng.cond(c, k) * 100:.0f}%)",
                                 f"{max(5, int(eng.minutes(c, k) * 0.6))} мин"), ("etake", k), True))
        for node, (pid, mins, garage) in tune_slots(c.model).items():
            p_ = c.tune.get(node)
            if isinstance(p_, dict):
                out.append(((f"Снять: {item_name(p_['id'])} ({p_['cond']:.0f}%)", f"{max(5, int(mins * 0.6))} мин"),
                            ("tune", node), not garage or self.crane()))
        if not out:
            out.append(("Снимать больше нечего — только кузов на пресс.", None, False))
        out.append(("Закончить", CLOSE, True))
        return out

    def select(self, sel):
        g = self.g
        if sel == CLOSE:
            return "close"
        if isinstance(sel, tuple) and sel[0] == "take":
            sl = sel[1]
            c = self.car
            if not g.need("toolbox"):
                return None
            if c.running:
                c.engine_off()
            part = c.parts.get(sl)
            if part is None:
                return None
            mins = max(5, int(c.slots[sl][2] * 0.6))
            g.play_sound("tool", 0.6)
            left = mins
            while left > 0:
                g.advance(min(10, left), working=True)
                left -= 10
            c.parts[sl] = None
            fast.on_removed(c, sl)
            entry = {"id": part["id"], "cond": round(float(part["cond"]), 1)}
            if sl == "engine" and c.eng:
                entry["sub"] = eng.remove_whole(c)
            g.give(entry)
            g.notify(f"Снято: {item_name(part['id'])} ({part['cond']:.0f}%)", GREEN)
        if isinstance(sel, tuple) and sel[0] == "etake":
            c = self.car
            if not g.need("toolbox"):
                return None
            k = sel[1]
            if not eng.can_remove(c, k)[0]:
                return None
            left = max(5, int(eng.minutes(c, k) * 0.6))
            g.play_sound("tool", 0.6)
            while left > 0:
                g.advance(min(10, left), working=True)
                left -= 10
            e = eng.take_off(c, k)
            g.give(e)
            g.notify(f"Снято: {item_name(e['id'])} ({e['cond']:.0f}%)", GREEN)
        if isinstance(sel, tuple) and sel[0] == "tune":
            c = self.car
            if not g.need("toolbox"):
                return None
            part = c.tune.get(sel[1])
            if not isinstance(part, dict):
                return None
            mins = max(5, int(tune_slots(c.model)[sel[1]][1] * 0.6))
            left = mins
            while left > 0:
                g.advance(min(10, left), working=True)
                left -= 10
            c.tune[sel[1]] = None
            g.add_item(part["id"], part["cond"])
            g.notify(f"Снято: {item_name(part['id'])} ({part['cond']:.0f}%)", GREEN)
        return None

    def hint(self):
        return "Enter — снять деталь, Esc — закончить"


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
            self.info(name, ["Закрыто.", f"Часы работы: {self.hours_str(bid)}"])
            return
        if bid == "supermarkt":
            self.open_menu(Shop(self, "Супермаркет «Кауфгут»", SHOP_SUPERMARKT, subtitle="Продукты и напитки"))
        elif bid == "autoteile":
            self.parts_shop("ost", "Запчасти «Восток»",
                            "«Запчасти для Lada, Trabant, Wartburg — всё, что ездило в ГДР и СССР. Привезём из Польши.»")
        elif bid == "tanke":
            self.open_menu(Shop(self, "Заправка", SHOP_TANKE, subtitle="Открыто круглосуточно"))
        elif bid == "imbiss":
            self.open_menu(Shop(self, "Дёнер-закусочная", SHOP_IMBISS, subtitle="«Со всем и поострее?»"))
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
        elif bid == "dealer":
            self.open_menu(Dealer(self))
        elif bid == "polizei":
            import theft
            theft.police_station(self)

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
        self.dialog("Автосалон Крюгера — Toyota и западные марки", [
            "Господин Крюгер — бывший механик Toyota. Возит детали из Японии и Голландии, а заодно держит склад "
            "б/у и новых деталей для западных машин: Opel, VW, Ford, Mercedes, Volvo, BMW, Audi и Honda.",
            "Для Honda Civic есть тюнинг: турбокит IHI, интеркулер и буст-контроллер (в списке запчастей Civic).",
            "«AE86 у Ковальского? Да, знаю такую. Ремень ГРМ — первым делом, иначе мотору конец!»"],
            [("Выбрать марку и запчасти", lambda: self.parts_shop(
                "west", "Автосалон Крюгера", "Toyota, Opel, VW, Ford, Mercedes — оригинал и контрактные"), True)], wide=True)

    # ----------------------------------------------------------------- свалка / приём лома
    def buy_ae86(self):
        if self.owned["ae86"]:
            return
        if not self.is_open("schrott"):
            self.info("Авторазборка Ковальского", ["Контора закрыта — Ковальского нет.",
                                                  f"Часы работы: {self.hours_str('schrott')}"])
            return
        if AE86_PRICE <= 0 or self.pay(AE86_PRICE):
            self.owned["ae86"] = True
            self.info("Авторазборка Ковальского", [
                "Ковальский стягивает брезент и отдаёт ключи на проволоке: «Забирай даром. "
                "Мне она только место занимает».",
                "«Вытаскивай, когда хочешь. Только ремень ГРМ сначала поменяй, а то будет металлолом.»",
                "Отбуксируйте AE86 в гараж: подгоните «двойку», у AE86 нажмите T (трос), "
                "уберите «двойку» из гаража на место рядом и затащите «панду» внутрь. "
                "Или вызовите эвакуатор (телефон дома). Сварка и зарядка АКБ — только в гараже."], wide=True)
            self.notify("Toyota AE86 теперь ваша! Следующий шаг — починить и пройти техосмотр.", GREEN, 8)

    def ae86_offer(self):
        ae = self.cars["ae86"]
        miss = [n for n, k in (("АКБ", "battery"), ("глушителя", "exhaust"), ("заднего колеса", "tire_rr"))
                if not ae.has(k)]
        lines = [
            "Под рваным брезентом — белая с чёрным Corolla GT купе (Sprinter Trueno) 1985 года, "
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
        info = dict(model_info(car.model) or {})
        info.setdefault("origin", "СССР" if car.model == "vaz2102" else "?")
        info.setdefault("desc", "«Жигули»-универсал: простой, ремонтопригодный, запчасти есть в магазине «Восток».")
        if key in self.dealer["stock"]:
            self.open_menu(Dealer(self, key))
            return
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
        if car.has_tune("turbo"):
            lines.append(f"Под капотом — самодельная турбина IHI ({car.tc('turbo') * 100:.0f}%)! Прошлый хозяин "
                         "явно любил скорость.")
        if key.startswith("j"):
            lines.append("Ковальский: «Забирай даром, если утащишь. Или разбери на запчасти (R) — тоже бесплатно.»")
        else:
            lines.append("Хозяина нет — машину можно забрать себе бесплатно. Или разобрать на запчасти (R).")
        opts = [("Забрать себе (бесплатно)", lambda: self.take_find(key), True),
                ("Разобрать на запчасти", lambda: self.open_menu(Dismantle(self, key)), True)]
        if key in self.wrecks_in_drop():
            opts.append((f"Сдать на лом (+{self.scrap_value(key):.2f} DM)", lambda: self.scrap_car(key), True))
        self.dialog(f"Находка: {info['name']}", lines, opts, wide=True)

    # ----------------------------------------------------------------- заброшенные гаражи
    def garage_door(self, gid):
        ag = self.world.abandoned_by_id(gid)
        gs = self.garages[gid]
        if gs["open"]:
            return
        if ag["locked"] and not self.has("crowbar"):
            self.info(ag["name"], [
                "Ржавые ворота заперты на амбарный замок. Сквозь щель видно силуэт машины под слоем пыли.",
                "Хозяин давно уехал, соседи говорят — «забирай, всё равно сгниёт». Но замок так не открыть.",
                "Нужна монтировка: магазин «Восток» или заправка, 12 DM."], wide=True)
            return
        self.advance(15)
        self.play_sound("grind", 0.8)
        self.open_garage(gid)
        how = "Монтировка, скрежет — замок сдался." if ag["locked"] else "Ворота заржавели, но поддались."
        car = self.cars.get("g" + gid)
        what = f" Внутри под пыльным брезентом — {car.name}!" if car and not self.owned.get("g" + gid) else ""
        self.notify(f"{how}{what}", GREEN, 8)

    def search_shelves(self, gid):
        gs = self.garages[gid]
        if gs["looted"]:
            self.notify("Полки пустые — вы уже всё забрали.")
            return
        self.advance(20)
        gs["looted"] = True
        names = []
        for e in gs["loot"]:
            self.add_item(e["id"], e["cond"])
            it = ITEMS.get(e["id"], {})
            names.append(it.get("name", e["id"]) + (f" ({e['cond']:.0f}%)" if it.get("kind") == "part" else ""))
        self.play_sound("tool", 0.6)
        self.info("Полки в гараже", ["Под пылью и паутиной нашлось:", ""] + [f"• {n}" for n in names], wide=True)

    def pick_loose(self, idx):
        it = self.pickup(idx)
        if it is None:
            return
        self.play_sound("tool", 0.4)
        self.notify(f"Подобрано: {item_name(it['id'])} ({it['cond']:.0f}%)", GREEN)

    def take_find(self, key):
        car = self.cars[key]
        self.claim_car(key)
        self.play_sound("tool", 0.6)
        self.notify(f"{car.name} теперь ваша! Дотащите её тросом (T) к гаражу и восстанавливайте.", GREEN, 8)
        self.info(car.name, [
            "Вы находите в бардачке старые бумаги: хозяин выписан, машину бросили. По закону её можно оформить на себя.",
            "Что дальше: трос (T) к своей машине и тянуть к гаражу (сварка и зарядка АКБ — только там). "
            "Запчасти: восточные — в магазине «Восток», западные — в автосалоне Крюгера, б/у — у Ковальского.",
            "Когда машина будет готова: техосмотр, потом номера в ратуше — и она ваша полноценная машина."], wide=True)

    def scrap_car(self, key, confirmed=False):
        car = self.cars.get(key)
        if car is None or key in MAIN_CARS:
            return
        if not self.is_open("schrott"):
            self.info("Авторазборка Ковальского", ["Приём закрыт. Оставьте машину на площадке — примем в рабочее время.",
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
            w = self.where_is("rope")
            self.notify("Трос не под рукой: лежит " + w + "." if w else
                        "Нет троса. Купите буксировочный трос на заправке или в магазине «Восток» (15 DM).", RED, 6)
            return
        tgt = self.cars[target]
        best, bd = None, 14.0
        for k, c in self.owned_cars():
            if k == target:
                continue
            d = math.hypot(c.x - tgt.x, c.y - tgt.y)
            if d < bd:
                best, bd = k, d
        if best is None:
            self.notify("Подгоните свою машину поближе (до 14 м), чтобы привязать трос.", YELLOW)
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
            self.info("Заправка", ["Подъезжайте на машине к колонке."])
            return
        self.cur = key
        car = self.car
        if car.running:
            self.info("Заправка", ["«Мотор заглушите!» — кричит заправщик. Заглушите двигатель."])
            return
        space = car.tank - car.fuel
        diesel, two = car.sp("diesel"), car.sp("two_stroke")
        price = DIESEL_PRICE if diesel else FUEL_PRICE + (MIX_EXTRA if two else 0)
        fuel_name = "Дизель" if diesel else ("Смесь 1:50" if two else "Бензин 91")

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
            note = "Двухтактник: заправщик из колонки со смесью — бензин с 2T-маслом 1:50, как в ГДР."
        elif car.model == "vaz2102":
            note = "Старый мотор 2101 рассчитан на А-76, но и немецкий 91-й переварит."
        elif car.model == "ae86":
            note = "4A-GE любит 95-й — но и 91-й переживёт."
        else:
            note = "Бензин 91 — старому карбюраторному мотору в самый раз."

        def wash():
            if self.pay(WASH_PRICE):
                self.advance(15)
                car.dirt = 0.05
                self.notify(f"{car.name} помыта. Теперь видно, где ржавчина, а где краска.", GREEN)

        self.dialog(f"Заправка — {car.name}", [
            f"{fuel_name}. В баке: {car.fuel:.1f} / {car.tank:.0f} л. Цена: {price:.2f} DM/л. "
            f"У вас: {self.p.money:.2f} DM.", note], [
            (f"10 литров ({10 * price:.2f} DM)", lambda: fill(10), True),
            (f"20 литров ({20 * price:.2f} DM)", lambda: fill(20), True),
            (f"Полный бак ({space:.1f} л = {space * price:.2f} DM)", lambda: fill(space), True),
            (f"Автомойка — помыть машину ({WASH_PRICE:.0f} DM)", wash, car.dirt > 0.1)])

    def tuv(self):
        if not self.is_open("tuv"):
            self.info("Техосмотр TÜV", ["Закрыто.", f"Часы работы: {self.hours_str('tuv')}"])
            return
        key = self.car_in_zone(TUV_YARD)
        if key is not None:
            self.cur = key
        car = self.car
        if key is None:
            self.info("Техосмотр TÜV", ["«Добрый день. Для техосмотра пригоните машину во двор перед зданием.»",
                                         "Стоимость проверки: 95 DM."])
            return

        nach = bool(car.mangel) and car.tuv_until >= self.day      # только перепроверка дефектов
        price = 25 if nach else 95

        def check():
            if not self.pay(price):
                return
            self.advance(20 if nach else 45)
            defects = car.tuv_defects() + elec.tuv_defects(car)
            if nach:          # перепроверка — только то, что в предписании: свет, сигналы, электрика
                defects = [x for x in defects if x.startswith(("Освещение", "Предохранитель", "Фары", "Электрика"))]
            p, why = car._start_chance()
            if p <= 0 or car.battery_charge < 10:
                defects.insert(0, "Автомобиль не заводится своим ходом")
            if not defects and nach:
                car.mangel = None
                self.info("Техосмотр — повторная проверка пройдена", [
                    "«Дефекты устранены.» Инспектор ставит штамп в предписание.",
                    "Предписание закрыто." + ("" if car.registered else " Теперь — в ратушу: заново поставить на учёт.")])
                return
            if not defects:
                car.mangel = None
                car.tuv_until = self.day + 730
                first = ("Инспектор долго смотрит на «Жигули», потом на вас, потом снова на «Жигули»."
                         if car.model == "vaz2102" else
                         "Инспектор обходит AE86 и улыбается: «Хати-року! Мой сын обожает эти машины.»")
                self.info("Техосмотр ПРОЙДЕН!", [
                    first, "«Ну что ж... Существенных дефектов нет.» Он клеит свежую наклейку техосмотра.",
                    "Техосмотр действует 2 года." + ("" if car.registered else " Теперь — в ратушу за номерами.")])
            else:
                self.info("Техосмотр НЕ ПРОЙДЕН", ["Существенные дефекты:", ""] +
                          [f"• {d}" for d in defects[:14]] + ["", "Устраните и приезжайте снова."])

        mg = ["", "Предписание полиции: " + "; ".join(car.mangel["items"])] if car.mangel else []
        self.dialog("Техосмотр TÜV", [
            f"Техосмотр для {car.name}.",
            "Проверяют: коррозию, тормоза, шины, свет и сигналы, предохранители, выхлоп, амортизаторы, течи."] + mg,
            [("Повторная проверка дефектов (25 DM, 20 мин)" if nach else "Пройти проверку (95 DM, 45 мин)",
              check, True)])

    def rathaus(self):
        def register(key):
            car = self.cars[key]
            if car.tuv_until < self.day:
                self.info("Регистрация машин", ["«Без действующего техосмотра регистрации не будет.» Сначала техосмотр."])
                return
            if car.mangel:
                self.info("Регистрация машин", ["«На машину выписано предписание.» Сначала устраните дефекты "
                                               "и пройдите повторную проверку на техосмотре: " + "; ".join(car.mangel["items"])])
                return
            if self.pay(145):
                self.advance(120)
                if not car.spec.get("plate") and not car.plate_text:
                    rr = random.Random(car.seed)
                    letters = "ABCDEFGHKLMNPRSTUVWXYZ"
                    car.plate_text = f"KB-{rr.choice(letters)}{rr.choice(letters)} {rr.randint(10, 999)}"
                car.registered = True
                self.info("Регистрация машин", [
                    f"Два часа в очереди, три формуляра — и номера ваши: {car.plate}.",
                    "Страховка и налог (24 DM) будут списываться еженедельно.",
                    f"{car.name} можно ездить легально!"])
                if self.check_goal():
                    self.victory()

        lines = ["«Номер сорок семь, пожалуйста...» Служащая госпожа Беккер смотрит поверх очков."]
        opts = []
        for key, car in self.owned_cars():
            if car.registered:
                lines.append(f"{car.name}: зарегистрирована, номера {car.plate}.")
            else:
                ok = car.tuv_until >= self.day
                lines.append(f"{car.name}: не на учёте" + ("" if ok else " (нужен действующий техосмотр)") + ".")
                opts.append((f"Поставить на учёт {car.name} (145 DM: номера + страховка)",
                             lambda key=key: register(key), ok))
        self.dialog("Ратуша — регистрация машин", lines, opts)

    def victory(self):
        ae = self.cars["ae86"]
        days = self.day + 1
        self.play_sound("horn", 0.8)
        self.info("ЦЕЛЬ ВЫПОЛНЕНА — Хати-року!", [
            f"Toyota AE86 Sprinter Trueno на ходу, с техосмотром и номерами {ae.plate}.",
            "Вы садитесь в ковшеобразное кресло, поворачиваете ключ — 4A-GE заводится с полоборота "
            "и крутится до 7600 так, как «двойке» и не снилось.",
            f"На это ушло {days} дн. Доставок пиццы: {self.stats['deliveries']}, смен на складе: {self.stats['shifts']}.",
            f"Сдано машин на лом: {self.stats.get('scrapped', 0)}. Ковальский машет вслед: «Хати-року жива!»",
            "Старую «двойку» можно оставить — ржавая, но своя. Игра продолжается: A7 без ограничения скорости ждёт!",
        ], wide=True)

    def lager(self):
        p = self.p

        def shift():
            if p.drunk > 15:
                self.info("Склад", ["Бригадир Вольф: «Да ты пьян! Марш домой!» — сегодня без работы."])
                return
            if p.energy < 30:
                self.info("Склад", ["Вы слишком устали для смены (бодрость < 30)."])
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
            self.info("Склад", [f"8 часов таскали коробки и водили погрузчик. Заработано {pay:.0f} DM.{note}"])

        can = self.weekday() < 5 and 6 <= self.hour < 9
        self.dialog("Склад транспортной фирмы Мюллера", [
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
            self.info("Пиццерия «У Луиджи»", [
                "Луиджи: «Вот! Пицца с салями. Быстро, быстро!»",
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
        self.dialog("Пиццерия «У Луиджи»", ["Луиджи ищет курьера со своей машиной. Платит за каждый заказ."], opts)

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
        self.dialog("Авторазборка Ковальского", lines, opts + [
            ("Купить б/у запчасти", lambda: self.open_menu(Shop(self, "Свалка — б/у запчасти", [], mode="used",
                                                                  stock=self.schrott_stock,
                                                                  subtitle="Всё как есть, без гарантии")), True),
            ("Продать старые детали", lambda: self.open_menu(Shop(self, "Свалка — скупка", [], mode="sell",
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
            reasons.append(("Езда без регистрации и страховки", 250))
        elif car.tuv_until < self.day:
            reasons.append(("Просроченный техосмотр", 60))
        if self.p.drunk > 25:
            reasons.append(("Вождение в нетрезвом виде", 500))
        if lim and car.kmh() > lim + 20:
            reasons.append((f"Превышение скорости ({car.kmh():.0f} при {lim})", 100))
        night = self.darkness() > 0.4
        light = elec.light_defects(car, night)          # неисправный свет, который видно со стороны
        if night and not car.lights and not any(r[1] for r in light):
            reasons.append(("Езда без включённого света ночью", 30))
        for txt, serious, fine in light:
            reasons.append((txt, fine))
        if car.c("exhaust") < 0.2:
            reasons.append(("Слишком громкий выхлоп", 40))
        if not reasons:
            return
        self.police_cd = 240
        pol.siren = 8.0
        car.speed = 0
        car.vlat = car.ang_vel = 0.0
        self.play_sound("police", 0.6)
        total = sum(r[1] for r in reasons)
        self.charge(total)
        extra = []
        if light:
            serious = any(x[1] for x in light)
            items = [x[0] for x in light]
            if serious and car.registered:
                car.registered = False
                car.mangel = {"items": items, "until": self.day + 14, "serious": True}
                extra = ["«Дальше ехать запрещено!» Машина не соответствует требованиям — полицейский снимает печать "
                         "с номеров: регистрация аннулирована.",
                         "Что делать: устранить неисправность света → пройти повторную проверку на техосмотре → заново поставить на учёт "
                         "в ратуше. До тех пор езда — уже без регистрации."]
            elif serious:
                car.mangel = {"items": items, "until": self.day + 14, "serious": True}
                extra = ["«Дальше ехать запрещено!» Без исправного света ехать нельзя. Почините, пройдите техосмотр."]
            elif not car.mangel:
                car.mangel = {"items": items, "until": self.day + 7, "serious": False}
                extra = ["Выписано предписание: устранить дефекты и в течение 7 дней предъявить машину на техосмотр "
                         "(повторная проверка, 25 DM). Иначе регистрацию аннулируют."]
        self.info("Полиция", ["«Плановая проверка! Права и документы на машину, пожалуйста.»", ""] +
                  [f"• {r[0]}: {r[1]} DM" for r in reasons] +
                  ["", f"Итого штраф: {total} DM."] + (extra or
                  ["Полицейский качает головой, глядя на ваши гнилые пороги."]))

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
            self.open_menu(StorageTake(self, self.fridge, "fridge", "Холодильник"))
        elif key == "keyhook":
            self.open_menu(StorageTake(self, self.keyhook, "hook", "Ключница у двери"))
        elif key == "stove":
            if self.has("pizza_tk"):
                def cook():
                    self.take_item("pizza_tk")
                    self.advance(15)
                    self.add_item("pizza_hot")
                    self.notify("Пицца готова — горячая пицца в руке (или в холодильнике, если руки заняты).", GREEN)
                self.dialog("Плита", ["Разогреть замороженную пиццу? (15 мин)"], [("Разогреть", cook, True)])
            else:
                self.info("Плита", ["Нечего готовить. Купите замороженную пиццу в супермаркете."])
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
                self.info("Телевизор", [random.choice(NEWS)])
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
                "Рядом — немецко-русский словарь и учебник «Немецкий для переселенцев»."])
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
            car.vlat = car.ang_vel = 0.0
            car.engine_off()
            self.advance(90)
            self.notify(f"Эвакуатор Майера отбуксировал {car.name} "
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
            ("Доставка пиццы — заказать (15 DM)", pizza, True),
        ] + [(f"Эвакуатор — {c.name} к гаражу (120 DM)", lambda k=k: tow(k), True)
             for k, c in self.owned_cars()] + [
            ("Позвонить маме в Омск", mama, True)])

    def status(self):
        lines = [self.goal_text(), "",
                 f"Деньги: {self.p.money:.2f} DM.  Квартира своя — за жильё платить не нужно."]
        for k, car in self.owned_cars():
            tuv = "нет" if car.tuv_until < self.day else f"до дня {car.tuv_until}"
            lines.append(f"{car.name}: техосмотр — {tuv}; номера — {car.plate if car.registered else 'нет'}; "
                         f"пробег {car.odometer:.0f} км; ржавчина до {car.max_rust():.0f}%.")
        lines += [f"Сделано доставок: {self.stats['deliveries']},  смен на складе: {self.stats['shifts']},  "
                  f"сдано машин на лом: {self.stats.get('scrapped', 0)}.", ""]
        if not self.owned["ae86"]:
            lines += ["План: забрать AE86 у Ковальского (свалка за гаражом, бесплатно) и копить на запчасти.",
                      "Быстрые деньги: брошенные машины у загородных дорог (серые точки на карте M) — "
                      "трос (T) к «двойке», тащить на площадку у пресса, E — сдать на лом."]
        elif not self.goal_done:
            lines += ["План по AE86: 1) ремень ГРМ, АКБ, свечи, масло, бензин;  2) шины, тормоза, амортизаторы;",
                      "3) сварка порогов/днища и покраска (в гараже);  4) техосмотр;  5) номера в ратуше."]
        self.info("Дела и счета", lines, wide=True)
