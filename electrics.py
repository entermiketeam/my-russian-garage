"""Электрика автомобиля: блок предохранителей, цепи, неисправности и их поиск.

car.elec = {"fuses": {цепь: "ok" | "blown" | "bug"}, "faults": {цепь: {"kind", "seg", "found"}}, "t": {цепь: сек под КЗ}}
Нет car.elec — создаётся при первом обращении (по seed машины и её сохранности), старые сохранения работают.

Логика как в жизни:
  * предохранитель защищает цепь; перегорел — цепь без питания (стартер молчит, фара не горит...);
  * перегорает он не просто так: КЗ провода на массу — сразу, как только цепь включили;
    неисправный потребитель (лампа, реле, мотор насоса) — через несколько секунд работы;
  * новый предохранитель при оставшейся неисправности снова сгорит — причину надо найти мультиметром
    (прозвонка показывает, на каком участке КЗ/обрыв, или что виноват потребитель) и устранить на месте;
  * обрыв провода и окисленные контакты предохранитель не жгут — просто нет питания;
  * «жучок» из проволоки вместо предохранителя не сгорит, но при КЗ плавится проводка.
Где что находится (участки цепи) — SEGMENTS: по ним 3D рисует найденную неисправность прямо на машине.
"""
import random
from i18n import T

# участок цепи: (описание, как добраться)
SEGMENTS = {
    "box":    (T("блок предохранителей"), T("блок")),
    "column": (T("рулевая колонка — замок зажигания и подрулевой переключатель"), T("изнутри, с водительского места")),
    "dash":   (T("под панелью приборов — разъёмы щитка, выключатель стоп-сигнала у педали"), T("изнутри или через открытую левую дверь")),
    "bay_l":  (T("моторный отсек, левый лонжерон — жгут и разъём левой фары"), T("открыть капот")),
    "bay_r":  (T("моторный отсек, правый лонжерон — жгут правой фары и звукового сигнала"), T("открыть капот")),
    "bay_c":  (T("моторный отсек у щита — катушка зажигания, реле, провод стартера"), T("открыть капот")),
    "sill_l": (T("под ковриком вдоль левого порога — жгут назад"), T("открыть левую дверь")),
    "trunk":  (T("багажник — разъёмы и патроны задних фонарей"), T("открыть багажник")),
    "tank":   (T("у бака под задним сиденьем — разъём бензонасоса"), T("открыть левую дверь")),
}

# цепи в порядке номеров предохранителей. consumer: (что это, участок, чем чинить: id предмета или "slot:...")
CIRCUITS = [
    dict(key="ign", name=T("Зажигание"), amp=16, path=["column", "bay_c"], critical=True,
         consumer=(T("катушка зажигания"), "bay_c", "coil")),
    dict(key="starter", name=T("Стартер (реле)"), amp=10, path=["column", "bay_c"], critical=True,
         consumer=(T("втягивающее реле стартера"), "bay_c", "relay")),
    dict(key="fuel", name=T("Топливо (бензонасос / клапан карбюратора)"), amp=15, path=["sill_l", "tank"], critical=True,
         consumer=(T("бензонасос"), "tank", "slot:fuel_pump")),
    dict(key="dash", name=T("Приборы и подсветка щитка"), amp=8, path=["dash"], critical=False,
         consumer=(T("лампы щитка приборов"), "dash", "bulb")),
    dict(key="head_l", name=T("Фара левая"), amp=10, path=["dash", "bay_l"], critical=False,
         consumer=(T("лампа и патрон левой фары"), "bay_l", "bulb")),
    dict(key="head_r", name=T("Фара правая"), amp=10, path=["dash", "bay_r"], critical=False,
         consumer=(T("лампа и патрон правой фары"), "bay_r", "bulb")),
    dict(key="tail", name=T("Габариты и задние фонари"), amp=8, path=["sill_l", "trunk"], critical=False,
         consumer=(T("патрон заднего фонаря"), "trunk", "bulb")),
    dict(key="brake", name=T("Стоп-сигналы"), amp=10, path=["dash", "sill_l", "trunk"], critical=False,
         consumer=(T("лампа стоп-сигнала"), "trunk", "bulb")),
    dict(key="turn", name=T("Поворотники и аварийка"), amp=10, path=["column", "sill_l", "trunk"], critical=False,
         consumer=(T("реле-прерыватель поворотников"), "column", "relay")),
    dict(key="horn", name=T("Звуковой сигнал"), amp=15, path=["column", "bay_r"], critical=False,
         consumer=(T("звуковой сигнал"), "bay_r", "horn")),
]
BY_KEY = {c["key"]: c for c in CIRCUITS}
KEYS = [c["key"] for c in CIRCUITS]
LIGHTING = ("head_l", "head_r", "tail", "brake", "turn")

KIND_SHORT = {"short": T("КЗ провода"), "open": T("обрыв провода"), "consumer": T("неисправен потребитель"),
              "corrosion": T("окисленные контакты")}
KIND_RU = {"short": T("короткое замыкание провода на массу"), "open": T("обрыв провода"),
           "consumer": T("неисправен потребитель"), "corrosion": T("окислены контакты в блоке предохранителей")}

# где блок предохранителей: под панелью слева (большинство) или в моторном отсеке
BOX_BAY = {"w123", "taunus"}
BOX_NAME = {"vaz2102": T("блок ПР-12 под панелью, слева от руля"), "trabant": T("коробка предохранителей под панелью слева"),
            "w123": T("блок в моторном отсеке у левого щита"), "taunus": T("блок в моторном отсеке у левого щита")}

ITEM_DEFS = {
    "fuse_set":  dict(name=T("Набор предохранителей (10 шт.)"), kind="material", price=4.0),
    "multimeter": dict(name=T("Мультиметр (прозвонка цепей)"), kind="tool", price=39.0),
    "wire_kit":  dict(name=T("Ремкомплект проводки (провод, клеммы, изолента)"), kind="material", price=9.0),
    "bulb":      dict(name=T("Лампа с патроном (фара / фонарь / щиток)"), kind="part", price=6.0),
    "relay":     dict(name=T("Реле (стартера / поворотов)"), kind="part", price=14.0),
    "coil":      dict(name=T("Катушка зажигания"), kind="part", price=38.0),
    "horn":      dict(name=T("Звуковой сигнал"), kind="part", price=19.0),
}
FIX_MIN = {"short": 30, "open": 25, "consumer": 15, "corrosion": 10}
CONSUMER_BLOW = 2.5        # сек работы неисправного потребителя до того, как сгорит предохранитель


def box_place(car):
    return "bay" if car.model in BOX_BAY else "dash"


def box_name(car):
    return BOX_NAME.get(car.model, T("блок предохранителей в моторном отсеке") if box_place(car) == "bay"
                        else T("блок предохранителей под панелью слева от руля"))


def fuse_no(key):
    return KEYS.index(key) + 1


def circuit_name(car, key):
    c = BY_KEY[key]
    if key == "fuel":
        if car.sp("diesel"):
            return T("Топливо (стоп-клапан ТНВД)")
        return T("Бензонасос") if not car.spec.get("carb") else T("Клапан карбюратора (ЭПХХ) и бензонасос")
    if key == "ign" and car.sp("diesel"):
        return T("Зажигание (свечи накаливания, реле)")
    return c["name"]


# ------------------------------------------------------------------ состояние
def _new(car, rng=None, level=None):
    """Состояние электрики найденной машины: чем хуже сохранилась, тем больше проблем."""
    d = {"fuses": {k: "ok" for k in KEYS}, "faults": {}, "t": {}}
    if rng is None:
        rng = random.Random(car.seed * 7 + 3)
    if level is None:
        level = max(0.0, 1.0 - getattr(car, "preservation", 0.6))
    for k in KEYS:
        if rng.random() < 0.22 * level:
            kind = rng.choices(["short", "open", "consumer", "corrosion"], [0.3, 0.2, 0.35, 0.15])[0]
            d["faults"][k] = _fault(k, kind, rng)
            if kind in ("short", "consumer") and rng.random() < 0.8:
                d["fuses"][k] = "blown"
        elif rng.random() < 0.05 * level:
            d["fuses"][k] = "blown"          # когда-то сгорел от скачка — просто заменить
    return d


def _fault(key, kind, rng):
    c = BY_KEY[key]
    if kind == "corrosion":
        seg = "box"
    elif kind == "consumer":
        seg = c["consumer"][1]
    else:
        seg = rng.choice(c["path"])
    return {"kind": kind, "seg": seg, "found": False}


def data(car):
    d = getattr(car, "elec", None)
    if not isinstance(d, dict) or "fuses" not in d:
        d = _new(car)
        car.elec = d
    for k in KEYS:
        d["fuses"].setdefault(k, "ok")
    d.setdefault("faults", {})
    d.setdefault("t", {})
    return d


def clean(car):
    car.elec = {"fuses": {k: "ok" for k in KEYS}, "faults": {}, "t": {}}
    return car.elec


def add_fault(car, key, kind, seg=None, blown=False):
    d = data(car)
    f = _fault(key, kind, random.Random())
    if seg:
        f["seg"] = seg
    d["faults"][key] = f
    if blown and d["fuses"][key] == "ok":
        d["fuses"][key] = "blown"
    return f


def fuse(car, key):
    return data(car)["fuses"][key]


def fault(car, key):
    return data(car)["faults"].get(key)


def _harness(car):
    return car.has("wiring") and car.c("wiring") > 0.04


def powered(car):
    return car.has("battery") and car.battery_charge > 1


def works(car, key):
    """Доходит ли питание до потребителя (без побочных эффектов)."""
    d = data(car)
    if not powered(car) or not _harness(car):
        return False
    if d["fuses"][key] == "blown":
        return False
    f = d["faults"].get(key)
    if f:
        if f["kind"] in ("open", "corrosion"):
            return False
        if f["kind"] == "short":
            return False              # ток уходит в массу (или сразу сгорит предохранитель)
        if f["kind"] == "consumer" and d["fuses"][key] == "bug":
            return False
    return True


def _blow(car, key, why):
    d = data(car)
    d["fuses"][key] = "blown"
    d["t"].pop(key, None)
    car.say(T("Щёлк — пропало: {circuit_name}. {why}", circuit_name=circuit_name(car, key).lower(), why=why))
    car.sounds.append("click")


def energize(car, key, dt=0.0):
    """Цепь включили (ключ, фары, педаль тормоза...). Возвращает, работает ли потребитель."""
    d = data(car)
    if not powered(car) or not _harness(car):
        return False
    f = d["faults"].get(key)
    st = d["fuses"][key]
    if st == "blown":
        return False
    if f and f["kind"] in ("short", "consumer"):
        if st == "bug":
            # проволока не перегорает: греется и плавится проводка
            car.battery_charge = max(0.0, car.battery_charge - 4.0 * dt)
            car.wear("wiring", 1.2 * dt)
            if random.random() < 0.6 * dt:
                car.say(T("Пахнет горелой изоляцией! Вместо предохранителя «жучок» — плавится проводка."))
            if f["kind"] == "short" and random.random() < 0.05 * dt:
                other = random.choice([k for k in KEYS if k != key])
                if other not in d["faults"]:
                    d["faults"][other] = _fault(other, "short", random.Random())
                    car.say(T("Оплавились соседние провода в жгуте — появилось новое замыкание."))
            return False
        if f["kind"] == "short":
            _blow(car, key, T("Предохранитель сгорел сразу — в цепи замыкание."))
            return False
        d["t"][key] = d["t"].get(key, 0.0) + dt
        if d["t"][key] >= CONSUMER_BLOW:
            _blow(car, key, T("Предохранитель не выдержал нагрузки — что-то с потребителем."))
            return False
    return works(car, key)


def step(car, dt, active):
    """Каждый кадр: active — {цепь: включена ли сейчас}. Критичные цепи глушат мотор."""
    if not getattr(car, "elec", None) and not active:
        return
    if getattr(car, "traffic", False) and not data(car)["faults"]:
        return                                                   # исправная проводка у машин трафика — считать нечего
    for key, on in active.items():
        if on:
            ok = energize(car, key, dt)
            if not ok and car.running:
                if key == "ign":
                    car.engine_off(T("Мотор заглох разом, как выключили — пропало питание зажигания."))
                elif key == "fuel":
                    car.fuel_cut = getattr(car, "fuel_cut", 0.0) + dt
                    if car.fuel_cut > 2.5:
                        car.fuel_cut = 0.0
                        car.engine_off(T("Мотор почихал и заглох — топливо не подаётся (нет питания цепи топлива)."))


def age(car, minutes, wet=False):
    """Со временем гнилая проводка сама даёт сбои (сырость, ржавчина, вибрация)."""
    if not car.has("wiring"):
        return
    p = 0.000012 * minutes * (1.6 - car.c("wiring")) * (2.0 if wet else 1.0)
    if random.random() < p:
        d = data(car)
        key = random.choice(KEYS)
        if key not in d["faults"]:
            kind = random.choices(["short", "open", "consumer", "corrosion"], [0.3, 0.2, 0.3, 0.2])[0]
            d["faults"][key] = _fault(key, kind, random.Random())


CRASH_CIRCUITS = {"front": ["head_l", "head_r", "horn", "ign"], "rear": ["tail", "brake", "turn"],
                  "left": ["tail", "fuel", "brake", "head_l"], "right": ["head_r", "horn", "turn"]}
CRASH_SEG = {"front": {"head_l": "bay_l", "head_r": "bay_r", "horn": "bay_r", "ign": "bay_c"},
             "rear": {"tail": "trunk", "brake": "trunk", "turn": "trunk"},
             "left": {"tail": "sill_l", "fuel": "sill_l", "brake": "sill_l", "head_l": "bay_l"},
             "right": {"head_r": "bay_r", "horn": "bay_r", "turn": "trunk"}}


def on_crash(car, zone, depth):
    """Авария мнёт жгуты: перебитые провода и замыкания в зоне удара."""
    if depth < 0.05:
        return
    d = data(car)
    for key in CRASH_CIRCUITS.get(zone, []):
        if key in d["faults"] or random.random() > min(0.85, depth * 3.5):
            continue
        seg = CRASH_SEG[zone][key]
        kind = "short" if random.random() < 0.55 else ("consumer" if seg == BY_KEY[key]["consumer"][1] else "open")
        d["faults"][key] = {"kind": kind, "seg": seg if kind != "consumer" else BY_KEY[key]["consumer"][1],
                            "found": False}


def on_slot_installed(car, slot):
    """Поставили деталь из обычной системы запчастей — она лечит свои электрические неисправности."""
    d = data(car)
    for key, f in list(d["faults"].items()):
        fix = BY_KEY[key]["consumer"][2]
        if f["kind"] == "consumer" and fix == "slot:" + slot:
            del d["faults"][key]
        elif slot == "wiring" and f["kind"] in ("short", "open"):
            del d["faults"][key]              # новый жгут целиком
        elif slot == "lights" and f["kind"] == "consumer" and key in ("head_l", "head_r"):
            del d["faults"][key]              # новые фары в сборе — с лампами и патронами


# ------------------------------------------------------------------ действия игрока
def fuses_left(g):
    return sum(int(round(e.get("cond", 100) / 10)) for e in g.available() if e["id"] == "fuse_set")


def take_fuse(g):
    """Один предохранитель из набора — в руке или рядом (багажник, стеллаж)."""
    for e in sorted([e for e in g.available() if e["id"] == "fuse_set"], key=lambda e: e.get("cond", 100)):
        e["cond"] = round(e.get("cond", 100) - 10, 1)
        if e["cond"] < 5:
            g.take_item("fuse_set", e)
        return True
    return False


def test_circuit(car, key):
    """«Включить и проверить»: что увидит игрок, включив потребитель (сжигает предохранитель при неисправности)."""
    d = data(car)
    name = circuit_name(car, key).lower()
    if not powered(car):
        return T("Аккумулятор сел или снят — проверять нечем.")
    if not _harness(car):
        return T("Проводка сгнила целиком — нужен новый жгут (деталь «Электропроводка»).")
    st = d["fuses"][key]
    if st == "blown":
        return T("Не работает: {name}. Предохранитель F{fuse_no} перегорел — замените его.", name=name, fuse_no=fuse_no(key))
    f = d["faults"].get(key)
    if f and f["kind"] == "short" and st == "ok":
        _blow(car, key, "")
        return T("ХЛОП! Новый предохранитель F{fuse_no} сгорел сразу, как только включили. В цепи КЗ — " \
               "ищите причину мультиметром, иначе будет гореть каждый раз.", fuse_no=fuse_no(key))
    if f and f["kind"] == "consumer" and st == "ok":
        _blow(car, key, "")
        return T("{circuit_name} заработал(а) на пару секунд — и предохранитель F{fuse_no} снова сгорел. " \
               "Перегружает сам потребитель — прозвоните цепь.", circuit_name=circuit_name(car, key), fuse_no=fuse_no(key))
    if f and f["kind"] in ("open", "corrosion"):
        return T("Предохранитель F{fuse_no} цел, но {name} не работает — питание не доходит. " \
               "Обрыв или плохой контакт: прозвоните мультиметром.", fuse_no=fuse_no(key), name=name)
    if st == "bug":
        return T("Работает — но на «жучке». При любой неисправности сгорит уже проводка.")
    return T("Работает: {name}.", name=name)


def probe(car, key):
    """Прозвонка мультиметром (предохранитель вынут, ключ выключен). Находит место неисправности."""
    d = data(car)
    f = d["faults"].get(key)
    c = BY_KEY[key]
    path = " → ".join(SEGMENTS[s][0].split(" — ")[0] for s in ["box"] + c["path"])
    lines = [T("Цепь F{fuse_no} ({circuit_name}): {path}.", fuse_no=fuse_no(key), circuit_name=circuit_name(car, key), path=path)]
    if not f:
        lines.append(T("Сопротивление на массу — как у исправного потребителя, обрывов нет. Цепь в порядке."))
        if d["fuses"][key] == "blown":
            lines.append(T("Предохранитель сгорел когда-то от скачка — просто замените."))
        return lines
    f["found"] = True
    seg = SEGMENTS[f["seg"]]
    if f["kind"] == "short":
        lines += [T("Сопротивление на массу 0,2 Ом — КОРОТКОЕ ЗАМЫКАНИЕ."),
                  T("Отключая разъёмы по очереди, нашли участок: {0}.", seg[0]),
                  T("Там перетёрта изоляция о кузов. Доступ: {0}. Нужен ремкомплект проводки — "
                  "место отмечено на машине красным.", seg[1])]
    elif f["kind"] == "open":
        lines += [T("Цепи нет: сопротивление — бесконечность. ОБРЫВ."),
                  T("Прозванивая по участкам, нашли разрыв: {0}.", seg[0]),
                  T("Доступ: {0}. Нужен ремкомплект проводки — место отмечено на машине.", seg[1])]
    elif f["kind"] == "consumer":
        fix = c["consumer"][2]
        what = (T("заменить деталь «") + car.slots[fix[5:]][0] + T("» (снимается как обычная деталь, по болтам)")
                if fix.startswith("slot:") else T("поставить новую: ") + ITEM_DEFS[fix]["name"].lower())
        lines += [T("С отключённым потребителем КЗ пропадает — провода целы."),
                  T("Неисправен сам потребитель: {0} ({1}).", c['consumer'][0], seg[0]),
                  T("Что делать: {what}. Место отмечено на машине.", what=what)]
    else:
        lines += [T("Провода целы, но на гнезде предохранителя падает 3–4 вольта."),
                  T("Окислены контакты в блоке предохранителей — почистите их (набор ключей, 10 минут).")]
    return lines


def fix_needs(car, key):
    """(id предмета или None, описание) — что нужно, чтобы устранить найденную неисправность."""
    f = fault(car, key)
    if not f:
        return None, ""
    if f["kind"] in ("short", "open"):
        return "wire_kit", ITEM_DEFS["wire_kit"]["name"]
    if f["kind"] == "corrosion":
        return None, T("набор ключей и наждачка")
    fix = BY_KEY[key]["consumer"][2]
    if fix.startswith("slot:"):
        return fix, car.slots[fix[5:]][0]
    return fix, ITEM_DEFS[fix]["name"]


def repair(g, car, key):
    """Устранить найденную неисправность на месте. Возвращает текст результата (или None — не получилось)."""
    f = fault(car, key)
    if not f:
        return None
    if not g.need("toolbox"):
        return None
    need, what = fix_needs(car, key)
    if need and need.startswith("slot:"):
        slot = need[5:]
        g.notify(T("Нужно заменить «{0}» — открутите её крепёж и снимите (G), "
                 "потом поставьте новую. Электрика вылечится вместе с деталью.", car.slots[slot][0]), (240, 200, 60), 8)
        return None
    if need and not g.has(need):
        g.notify(T("Нужно: {what}. Купить — в магазине «Восток» или в автосалоне Крюгера.", what=what), (210, 60, 50), 6)
        return None
    if need:
        g.take_item(need)
    g.advance(FIX_MIN[f["kind"]], working=True)
    del data(car)["faults"][key]
    g.play_sound("tool", 0.5)
    txt = {"short": T("Перетёртое место заизолировали, провод уложили в держатель подальше от кромки."),
           "open": T("Разрыв спаяли, поставили новые клеммы."),
           "consumer": T("Поставили новую деталь: {0}.", BY_KEY[key]['consumer'][0]),
           "corrosion": T("Контакты зачистили до блеска — питание идёт.")}[f["kind"]]
    if fuse(car, key) == "blown":
        txt += T(" Осталось заменить сгоревший предохранитель F{fuse_no}.", fuse_no=fuse_no(key))
    return txt


# ------------------------------------------------------------------ последствия: полиция и TÜV
def light_defects(car, night):
    """Неисправности света, которые видно со стороны. [(текст, серьёзно ли, штраф)]."""
    out = []
    hl, hr = works(car, "head_l") and car.has("lights") and car.c("lights") > 0.05, \
        works(car, "head_r") and car.has("lights") and car.c("lights") > 0.05
    if night:
        if not hl and not hr:
            out.append((T("Ночью без фар: обе фары не работают"), True, 60))
        elif not (hl and hr):
            out.append((T("Не горит ") + (T("левая") if not hl else T("правая")) + T(" фара («одноглазый»)"), False, 20))
        if not works(car, "tail"):
            out.append((T("Ночью не горят задние габаритные фонари"), True, 50))
    if getattr(car, "_braked_t", 99.0) < 4.0 and not works(car, "brake"):
        out.append((T("Не горят стоп-сигналы"), False, 35))
    if getattr(car, "_turned_t", 99.0) < 6.0 and not works(car, "turn"):
        out.append((T("Не работают указатели поворота"), False, 20))
    return out


def tuv_defects(car):
    d = data(car)
    out = []
    names = {"head_l": T("левая фара"), "head_r": T("правая фара"), "tail": T("задние габаритные огни"),
             "brake": T("стоп-сигналы"), "turn": T("указатели поворота"), "horn": T("звуковой сигнал")}
    for key, nm in names.items():
        pre = T("Звуковой сигнал") if key == "horn" else T("Освещение")
        if not works(car, key):
            out.append(T("{pre}: не работает — {nm} (F{fuse_no})", pre=pre, nm=nm, fuse_no=fuse_no(key)))
        elif (d["faults"].get(key) or {}).get("kind") == "consumer":
            out.append(T("{pre}: неисправен потребитель — {nm}", pre=pre, nm=nm))
    for key, st in d["fuses"].items():
        if st == "bug":
            out.append(T("Предохранитель F{fuse_no} закорочен: «жучок» вместо предохранителя (пожароопасно)", fuse_no=fuse_no(key)))
    return out


def report(car, multimeter=False):
    """Строки для компьютерной диагностики / тестера: состояние всех цепей."""
    d = data(car)
    lines = [T("ЭЛЕКТРИКА — {box_name}. Напряжение АКБ: "
             "{0:.1f} В.", (11.2 + 1.5 * min(100, car.battery_charge) / 100) if car.has('battery') else 0, box_name=box_name(car))]
    bad = 0
    for key in KEYS:
        st = d["fuses"][key]
        f = d["faults"].get(key)
        ok = works(car, key)
        tag = {"ok": T("цел"), "blown": T("ПЕРЕГОРЕЛ"), "bug": T("«жучок»")}[st]
        line = T("F{fuse_no} {amp}А {circuit_name}: предохранитель {tag}", fuse_no=fuse_no(key), amp=BY_KEY[key]['amp'], circuit_name=circuit_name(car, key), tag=tag)
        if not ok or f:
            bad += 1
            if f and f["found"]:
                line += f" · {KIND_RU[f['kind']]} — {SEGMENTS[f['seg']][0].split(' — ')[0]}"
            elif st == "ok" and f:
                line += T(" · питание не доходит") if f["kind"] in ("open", "corrosion") else T(" · нагрузка ненормальная")
            elif st == "blown" and f and multimeter:
                line += T(" · при включении сгорит снова — прозвоните")
            line += "  ✗"
        else:
            line += "  ✓"
        lines.append(line)
    if not bad:
        lines.append(T("Все цепи в порядке."))
    else:
        lines.append(T("Как искать: блок предохранителей → «Включить и проверить» → если снова горит или нет питания — "
                     "«Прозвонить мультиметром»: он покажет участок, место отметится на машине красным."))
    return lines
