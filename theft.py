"""Угон машин, полиция и объявления о пропаже.

Ночью (01:00–05:00) каждая машина игрока, оставленная не в своём гараже, может быть угнана. Шанс зависит от
места стоянки, заперта ли она, торчит ли ключ в замке, насколько машина привлекательна (ржавый ВАЗ никому
особо не нужен, Mustang — очень), и длины ночи по календарю. Угнанная машина реально уезжает в другое место
города (улица, парковка, подземный гараж) — с тем же состоянием плюс следы угона: сломанный замок, провода
вместо ключа, разбитая форточка, пробег, меньше бензина, иногда снятые детали и вмятины.
Неездящую машину не угоняют — могут раскурочить на месте.

car.stolen = {"day", "from": [x, y], "place", "at", "discovered", "reported", "found", "finder", "reward",
              "boards": [id доски], "paper": до какого дня газета, "paid"}
"""
import math
import random

from world import GARAGE, BUILDINGS, point_in
from places import INTERIOR_X
import keys as K
from i18n import T

# доски объявлений: id -> (подпись, x, y)
BOARDS = {
    "b_super": (T("доска у супермаркета"), 441.5, 297.8),
    "b_rathaus": (T("доска у ратуши"), 521.5, 297.8),
    "b_imbiss": (T("доска у дёнер-закусочной"), 281.0, 312.2),
    "b_tanke": (T("доска у заправки"), 712.0, 277.0),
    "b_polizei": (T("доска у полиции"), 1031.5, 297.8),
    "b_bahnhof": (T("доска на вокзале"), 352.0, 98.5),
}
FINDERS = [T("господин Шульце"), T("госпожа Беккер"), T("господин Вагнер"), T("госпожа Хоффман"), T("господин Шрёдер"), T("госпожа Нойман"),
           T("дедушка Краузе"), T("господин Йылмаз"), T("госпожа Циммерман"), T("господин Ланге"), T("разносчик газет Тимо")]
PAPER_PRICE = 25.0
FLYER_PRICE = 5.0
REWARDS = [0, 20, 50, 100, 150, 200, 300, 500, 800, 1000]

ITEM_DEFS = {"flyer": dict(name=T("Объявления «Угнана машина!» (листовки)"), kind="material", price=FLYER_PRICE),
             "key": dict(name=T("Ключ зажигания"), kind="key", price=0.0)}


# ------------------------------------------------------------------ где стоит машина
def place_name(g, x, y):
    if point_in(GARAGE, x, y):
        return T("свой гараж")
    if x >= INTERIOR_X:
        L = g.world.level_at(x, y)
        return T("{name}, уровень {0}", '−1' if L['no'] == -1 else '−2', name=L['name']) if L else T("подземный гараж")
    ax, ay = BUILDINGS["apartment"][7]
    if math.hypot(x - ax, y - ay) < 45:
        return T("у дома, Линденштрассе, 7")
    P = g.world.places.parking_at(x, y)
    if P:
        return P["name"]
    r = g.world.road_at(x, y)
    if r:
        return r[5]
    for bid, b in BUILDINGS.items():
        bx, by, bw, bh = b[:4]
        if bx - 15 <= x <= bx + bw + 15 and by - 15 <= y <= by + bh + 15:
            return T("у здания «") + b[4] + "»"
    return T("на окраине Кляйнбрука")


def spot_risk(g, car):
    """Базовый шанс угона за ночь по месту стоянки."""
    x, y = car.x, car.y
    if point_in(GARAGE, x, y) or g.world.abandoned_at(x, y) is not None:
        return 0.0                                   # свой гараж / заброшенный гараж с воротами
    if x >= INTERIOR_X:
        return 0.06                                  # подземка: темно и никого
    ax, ay = BUILDINGS["apartment"][7]
    if math.hypot(x - ax, y - ay) < 45:
        return 0.018                                 # под окнами, соседи рядом
    if g.world.places.parking_at(x, y):
        return 0.07                                  # заброшенная парковка
    r = g.world.road_at(x, y)
    if r and r[4] == "town":
        return 0.03
    return 0.05                                      # загородные дороги, окраины


def drivable(car):
    return (car.has("engine") and car.has("gearbox") and car.has("battery") and car.fuel > 1.0
            and all(car.has(t) and car.c(t) > 0.05 for t in car.tire_list()) and car.c("engine") > 0.1)


def night_chance(g, key, car):
    """Шанс угона за одну ночь (для подсказок и логики)."""
    if getattr(car, "service", None) or car.stolen or (g.p.in_car and g.cur == key) or (g.tow and key in (g.tow.get("key"), g.tow.get("by"))):
        return 0.0
    base = spot_risk(g, car)
    if base <= 0:
        return 0.0
    if getattr(g, "location", "street") == "street" and math.hypot(g.p.x - car.x, g.p.y - car.y) < 40:
        return 0.0                                    # хозяин рядом (чинит, стоит у машины) — не полезут
    if getattr(g, "location", "street") == "street" and math.hypot(g.p.x - car.x, g.p.y - car.y) < 40:
        return 0.0                                    # хозяин рядом (чинит, стоит у машины) — не полезут
    if getattr(g, "location", "street") == "street" and math.hypot(g.p.x - car.x, g.p.y - car.y) < 40:
        return 0.0                                    # хозяин рядом (чинит, стоит у машины) — не полезут
    value = g.car_value(car)
    attract = max(0.3, min(2.6, value / 2200))
    m = 1.0
    if not car.locked or car.lock_broken:
        m *= 2.5
    if K.fits(car.ign_key, car):
        m *= 6.0                                      # ключ в замке — подарок угонщику
    if any(car.door_open.values()):
        m *= 1.5
    dark = 24 - (g.climate()["set"] - g.climate()["rise"])
    m *= 0.7 + dark / 30                              # длинные зимние ночи
    return min(0.65, base * attract * m)


# ------------------------------------------------------------------ ночная проверка
def tick(g, m0, m1):
    """Время прошло с m0 до m1 минут: на каждом ночном часе (01..04) — проверка угона."""
    h0, h1 = int(m0 // 60), int(m1 // 60)
    for hh in range(h0 + 1, h1 + 1):
        if hh % 24 in (1, 2, 3, 4):
            for key, car in list(g.owned_cars()):
                p = night_chance(g, key, car) / 4
                if p > 0 and random.random() < p:
                    steal(g, key, random.Random())


def steal(g, key, rng):
    car = g.cars[key]
    K.ensure(car)
    frm = (car.x, car.y)
    place = place_name(g, car.x, car.y)
    if not drivable(car):
        # не заводится — угонять нечего; раскурочили на месте
        took = []
        for sl in rng.sample(["battery", "lights", "seats", "radiator", "alternator", "starter"], 3):
            if car.parts.get(sl) and rng.random() < 0.6:
                took.append(car.slots[sl][0])
                car.parts[sl] = None
        if took:
            car.pilfered = took
            if car.locked:
                car.lock_broken = True
                car.locked = False
        return None
    dest = pick_destination(g, car, rng)
    if dest is None:
        return None
    was_locked = bool(car.locked)
    if car.locked:
        car.lock_broken = True                        # замок вскрыли
        if rng.random() < 0.5 and car.parts.get("glass"):
            car.parts["glass"]["cond"] = max(0.0, car.parts["glass"]["cond"] - 30)
    car.locked = False
    had_key = K.fits(car.ign_key, car)
    if not had_key:
        car.hotwired = True                           # замок зажигания раскурочен, провода напрямую
    elif rng.random() < 0.4:
        car.ign_key = None                            # ключ унесли с собой
    x, y, a = dest
    dist = math.hypot(x - frm[0], y - frm[1])
    car.x, car.y, car.angle = x, y, a
    car.speed = car.vlat = car.ang_vel = 0.0
    car.running = car.cranking = False
    car.gear = 0
    car.door_open = {k: False for k in car.door_open}
    car.trunk_open = False
    car.hood_open = False
    car.lights = False
    car.fuel = max(0.3, car.fuel - rng.uniform(2, 12))
    car.odometer += dist / 1000 + rng.uniform(20, 140)
    car.battery_charge = max(0.0, car.battery_charge - rng.uniform(10, 50))
    for sl, w in (("engine", 3), ("clutch", 5), ("brakes_f", 3)):
        car.wear(sl, rng.uniform(0.5, w))
    for t in car.tire_list():
        car.wear(t, rng.uniform(0.5, 3))
    car.dirt = min(1.0, car.dirt + 0.25)
    if rng.random() < 0.3:
        try:
            import damage
            damage.random_crash(car, rng, 0.3)        # «поцеловали» столб
        except Exception:
            pass
    stripped = []
    if rng.random() < 0.35:
        for sl in rng.sample(["battery", "lights", "seats", "tire_rl", "exhaust"], rng.randint(1, 2)):
            if car.parts.get(sl):
                stripped.append(car.slots[sl][0])
                car.parts[sl] = None
    gone = []
    for e in list(car.trunk_items):
        if e.get("id") != "key" and rng.random() < 0.5:
            from items import ITEMS
            if ITEMS.get(e["id"], {}).get("kind") in ("tool", "part"):
                car.trunk_items.remove(e)
                gone.append(ITEMS[e["id"]]["name"])
    car.stolen = {"day": g.day, "from": [round(frm[0], 1), round(frm[1], 1)], "place": place,
                  "at": place_name(g, x, y), "discovered": False, "reported": None, "found": None,
                  "finder": None, "reward": 0, "boards": [], "paper": -1, "paid": False,
                  "stripped": stripped, "trunk_gone": gone, "was_locked": was_locked, "date": g.date_text()}
    g.winter._last.pop(key, None) if hasattr(g, "winter") else None
    return dest


def pick_destination(g, car, rng):
    w = g.world
    cands = [(x, y, a) for (x, y, a) in w.road_spots + w.house_spots]
    for P in w.places.parkings:
        cands += [(x, y, a) for (x, y, a) in P["bays"]]
    for L in w.places.levels:
        cands += [(x, y, a) for (x, y, a, _) in L["bays"]]
    rng.shuffle(cands)
    for x, y, a in cands:
        if math.hypot(x - car.x, y - car.y) < 260 or point_in(GARAGE, x, y):
            continue
        if any(c is not car and math.hypot(c.x - x, c.y - y) < 6 for c in g.cars.values()):
            continue
        return (x, y, a)
    return None


# ------------------------------------------------------------------ день: обнаружение, поиск, звонки
def update(g):
    """Каждый кадр (дёшево): игрок заметил пропажу / нашёл машину сам."""
    p = g.p
    for key, car in g.owned_cars():
        st = car.stolen
        if getattr(car, "pilfered", None) and math.hypot(p.x - car.x, p.y - car.y) < 20:
            g.notify(T("{name}: ночью кто-то раскурочил машину — нет: ", name=car.name) + ", ".join(car.pilfered).lower() + ".",
                     (210, 60, 50), 10)
            car.pilfered = None
        if not st:
            continue
        if not st["discovered"] and math.hypot(p.x - st["from"][0], p.y - st["from"][1]) < 25:
            st["discovered"] = True
            g.notify(T("ВАШ {name} ИСЧЕЗ! На месте ({place}) — осколки стекла. Похоже, угнали. "
                     "Полиция — участок на Хауптштрассе (восточнее магазина «Восток»).", name=car.name.upper(), place=st['place']), (210, 60, 50), 12)
            g.play_sound("crash", 0.2)
        if not st["found"] and math.hypot(p.x - car.x, p.y - car.y) < 18:
            st["found"] = "self"
            st["discovered"] = True
            g.notify(T("Это же ваш {name}! Угонщики бросили его здесь ({at}).", name=car.name, at=st['at']), (90, 190, 90), 10)
        if st["found"] and math.hypot(p.x - car.x, p.y - car.y) < 9 and st.get("finder") and not st["paid"] \
                and st["reward"] > 0 and not st.get("asked"):
            st["asked"] = True
            ask_reward(g, key)
        if st["found"] and p.in_car and g.cur == key:
            recovered(g, key)


def recovered(g, key):
    car = g.cars[key]
    st = car.stolen
    car.stolen = None
    notes = []
    if car.hotwired:
        notes.append(T("замок зажигания раскурочен — заводится проводами (I), ключ не нужен"))
    if car.lock_broken:
        notes.append(T("дверной замок сломан — не запирается"))
    if st.get("stripped"):
        notes.append(T("сняли: ") + ", ".join(st["stripped"]).lower())
    if st.get("trunk_gone"):
        notes.append(T("из багажника пропало: ") + ", ".join(st["trunk_gone"]).lower())
    g.notify(T("{name} снова ваш.", name=car.name) + (" " + "; ".join(notes).capitalize() + "." if notes else "") +
             (T(" Замки меняют в меню работы с машиной (личинки + замок зажигания, 45 ₽).") if car.hotwired or car.lock_broken else ""),
             (90, 190, 90), 12)


def hourly(g, m0, m1):
    """Каждый игровой час: поиск полицией, звонки нашедших по объявлениям."""
    h0, h1 = int(m0 // 60), int(m1 // 60)
    for hh in range(h0 + 1, h1 + 1):
        hour = hh % 24
        for key, car in g.owned_cars():
            st = car.stolen
            if not st or st["found"]:
                continue
            days = g.day - st["day"]
            if st["reported"] is not None and 6 <= hour < 22:
                p = 0.012 * (1.6 if car.registered else 0.8) * (0.5 if car.x >= INTERIOR_X else 1.0)
                p *= max(0.35, 1.0 - 0.12 * days)        # по горячим следам — выше
                if random.random() < p:
                    st["found"] = "police"
                    g.notify(T("Полиция: ваш {name} найден — {at}. Заберите машину (на карте, M).", name=car.name, at=st['at']),
                             (90, 190, 90), 12)
                    continue
            if 7 <= hour < 21:
                n = len(st["boards"])
                paper = st["paper"] >= g.day
                if n or paper:
                    trust = getattr(g, "trust", 1.0)
                    p = trust * (0.0018 * n + (0.008 if paper else 0.0)) * (1 + st["reward"] / 200)
                    if random.random() < p:
                        who = random.choice(FINDERS)
                        st["found"] = "finder"
                        st["finder"] = who
                        g.notify(T("Звонок: «Добрый день, это {who}. Кажется, ваша машина нашлась!» — ваш {name}: "
                                 "{at}.", who=who, name=car.name, at=st['at']) + (T(" {who} ждёт обещанные {reward:.0f} ₽.", who=who, reward=st['reward']) if st["reward"] else ""),
                                 (240, 200, 60), 14)


def ask_reward(g, key):
    car = g.cars[key]
    st = car.stolen
    who, R = st["finder"], st["reward"]

    def pay():
        g.charge(R, T("Вознаграждение: {who}", who=who), (240, 200, 60), 6)
        st["paid"] = True
        g.trust = min(1.3, getattr(g, "trust", 1.0) + 0.1)
        g.notify(T("{who}: «Большое спасибо! Удачи с машиной.»", who=who), (90, 190, 90))

    def refuse():
        st["paid"] = True
        g.trust = max(0.3, getattr(g, "trust", 1.0) - 0.4)
        g.notify(T("{who} уходит, ругаясь. В городе заговорят — следующим объявлениям будут верить меньше.", who=who),
                 (210, 60, 50), 8)

    g.dialog(T("{who} у вашей машины", who=who), [T("«Вот ваша машина — {name}! Ещё вчера здесь стояла.»", name=car.name),
                                       T("По объявлению вы обещали {R:.0f} ₽ тому, кто найдёт машину.", R=R),
                                       T("У вас: {money:.2f} ₽.", money=g.p.money)],
             [(T("Заплатить {R:.0f} ₽", R=R), pay, True), (T("Не платить"), refuse, True)])


# ------------------------------------------------------------------ полиция и объявления
def ad_lines(g, key, reward=None):
    car = g.cars[key]
    st = car.stolen or {}
    R = st.get("reward", 0) if reward is None else reward
    return [T("УГНАНА МАШИНА!"),
            K.describe(car),
            T("Последний раз видели: {place}, в ночь на {date}.", place=st.get('place', '?'), date=st.get('date', g.date_text())),
            T("Вознаграждение нашедшему: {R:.0f} ₽.", R=R) if R else T("Вознаграждение: не назначено (просто просьба о помощи)."),
            T("Звонить: Линденштрассе, 7, тел. 0 51 23 / 4 71 02")]


def police_station(g):
    """Полиция: заявить об угоне, узнать о поиске, составить объявление."""
    stolen = [(k, c) for k, c in g.owned_cars() if c.stolen and not c.stolen["found"]]
    found = [(k, c) for k, c in g.owned_cars() if c.stolen and c.stolen["found"]]
    lines = [T("Старший полицейский Брандт за стойкой, кофе в кружке с гербом Нижней Саксонии.")]
    opts = []
    for k, c in found:
        lines.append(T("«Ваша машина {name} найдена» — {at}. Заберите его.", name=c.name, at=c.stolen['at']))
    for k, c in stolen:
        st = c.stolen
        if st["reported"] is None:
            opts.append((T("Заявить об угоне: {name}", name=c.name), lambda k=k: report(g, k), True))
        else:
            d = g.day - st["reported"]
            lines.append(T("{name}: заявление от {d} дн. назад — «Ещё ищем.»", name=c.name, d=d)
                         + (T(" Шансы тают: лучше развесить объявления.") if d >= 2 else ""))
        opts.append((T("Составить объявление о пропаже: {name}", name=c.name), lambda k=k: g.open_menu(_ad_menu(g, k)), True))
    if not stolen and not found:
        lines.append(T("«Добрый день. Если угонят машину — приходите к нам.» Пока заявлять не о чем."))
        lines.append(T("Совет: запирайте машину (K с ключом в руке) и не оставляйте ключ в замке."))
    g.dialog(T("Полицейский участок Кляйнбрука"), lines, opts)


def report(g, key):
    car = g.cars[key]
    st = car.stolen
    g.advance(40)
    st["reported"] = g.day
    st["discovered"] = True
    g.info(T("Заявление об угоне автомобиля"), [
        T("Брандт печатает на машинке, одним пальцем:"),
        T("Марка и модель: ") + car.name,
        T("Цвет: ") + K.color_name(car.color) + (T(" · номер {plate}", plate=car.plate) if car.registered else T(" · без номеров")),
        T("Приметы: ") + ", ".join(K.features(car)),
        T("Где стояла: {place} · пропала в ночь на {date}", place=st['place'], date=st.get('date', g.date_text())),
        T("Заперта ли была: {0} · ключ: у владельца", T('нет') if not st.get('was_locked') else T('да')),
        "",
        T("«Передадим всем патрулям. Обещать ничего не могу — иногда это занимает недели.»"),
        T("Если долго не найдут — можно развесить объявления с вознаграждением (бланк здесь же).")])


def _ad_menu(g, key):
    from actions import Menu, CLOSE

    class AdMenu(Menu):
        time_flows = True
        wide = True
        title = T("Объявление о пропаже машины")

        def __init__(self):
            st = g.cars[key].stolen
            self.i = REWARDS.index(st["reward"]) if st["reward"] in REWARDS else 0

        def lines(self):
            return ad_lines(g, key, REWARDS[self.i]) + ["", T("Деньги: {money:.2f} ₽. Вознаграждение платите "
                                                             "только если машину найдут.", money=g.p.money)]

        def items(self):
            st = g.cars[key].stolen
            R = REWARDS[self.i]
            return [((T("Вознаграждение: {R} ₽", R=R), "− / +"), "rew", True),
                    ((T("Напечатать 10 листовок и развесить самому"), f"{FLYER_PRICE:.0f} ₽"), "flyers", True),
                    ((T("Дать объявление в «Кляйнбрукский вестник» (3 дня)"), f"{PAPER_PRICE:.0f} ₽"), "paper",
                     st["paper"] < g.day),
                    (T("Готово"), CLOSE, True)]

        def select(self, sel):
            st = g.cars[key].stolen
            if sel == CLOSE:
                return "close"
            if sel == "rew":
                self.i = (self.i + 1) % len(REWARDS)
                st["reward"] = REWARDS[self.i]
            elif sel == "flyers":
                if not g.can_receive() and g.free_hand() is None:
                    g.notify(T("Руки заняты — освободите одну (Z / X)."), (210, 60, 50))
                elif g.pay(FLYER_PRICE):
                    st["reward"] = REWARDS[self.i]
                    g.give({"id": "flyer", "cond": 100.0, "car": key})
                    g.notify(T("10 листовок. Развесьте на досках объявлений (E у доски): супермаркет, ратуша, закусочная, "
                             "заправка, вокзал, у полиции."), (90, 190, 90), 10)
            elif sel == "paper":
                if g.pay(PAPER_PRICE):
                    st["reward"] = REWARDS[self.i]
                    st["paper"] = g.day + 3
                    g.notify(T("Объявление выйдет в «Кляйнбрукский вестник» — 3 дня его будут читать."), (90, 190, 90))
            return None

        def back(self):
            return True

    return AdMenu()


def board_actions(g):
    """Действия у досок объявлений: повесить листовку (если она в руке)."""
    p = g.p
    out = []
    for bid, (lab, bx, by) in BOARDS.items():
        if math.hypot(p.x - bx, p.y - by) > 2.6:
            continue
        fl = [e for e in p.hands if e and e.get("id") == "flyer"]
        for e in fl:
            car = g.cars.get(e.get("car"))
            if car and car.stolen and not car.stolen["found"] and bid not in car.stolen["boards"]:
                out.append((T("Повесить объявление о {name} ({lab}, листовок: {0})", int(round(e['cond'] / 10)), name=car.name, lab=lab),
                            lambda e=e, bid=bid: post(g, e, bid)))
        posted = [c for k, c in g.owned_cars() if c.stolen and bid in c.stolen["boards"]]
        if posted and not fl:
            out.append((T("Прочитать объявления ({lab})", lab=lab), lambda cs=posted: g.info(
                T("Доска объявлений"), sum((ad_lines(g, next(k for k, c2 in g.cars.items() if c2 is c)) + [""] for c in cs), []))))
    return out


def post(g, e, bid):
    car = g.cars[e["car"]]
    car.stolen["boards"].append(bid)
    e["cond"] = round(e["cond"] - 10, 1)
    if e["cond"] < 5:
        g.release(e)
    g.advance(3)
    g.play_sound("tool", 0.3)
    g.notify(T("Объявление висит ({0}). Досок с объявлением: {1}.", BOARDS[bid][0], len(car.stolen['boards'])), (90, 190, 90))
