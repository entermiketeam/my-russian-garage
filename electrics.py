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

# участок цепи: (описание, как добраться)
SEGMENTS = {
    "box":    ("блок предохранителей", "блок"),
    "column": ("рулевая колонка — замок зажигания и подрулевой переключатель", "изнутри, с водительского места"),
    "dash":   ("под панелью приборов — разъёмы щитка, выключатель стоп-сигнала у педали", "изнутри или через открытую левую дверь"),
    "bay_l":  ("моторный отсек, левый лонжерон — жгут и разъём левой фары", "открыть капот"),
    "bay_r":  ("моторный отсек, правый лонжерон — жгут правой фары и звукового сигнала", "открыть капот"),
    "bay_c":  ("моторный отсек у щита — катушка зажигания, реле, провод стартера", "открыть капот"),
    "sill_l": ("под ковриком вдоль левого порога — жгут назад", "открыть левую дверь"),
    "trunk":  ("багажник — разъёмы и патроны задних фонарей", "открыть багажник"),
    "tank":   ("у бака под задним сиденьем — разъём бензонасоса", "открыть левую дверь"),
}

# цепи в порядке номеров предохранителей. consumer: (что это, участок, чем чинить: id предмета или "slot:...")
CIRCUITS = [
    dict(key="ign", name="Зажигание", amp=16, path=["column", "bay_c"], critical=True,
         consumer=("катушка зажигания", "bay_c", "coil")),
    dict(key="starter", name="Стартер (реле)", amp=10, path=["column", "bay_c"], critical=True,
         consumer=("втягивающее реле стартера", "bay_c", "relay")),
    dict(key="fuel", name="Топливо (бензонасос / клапан карбюратора)", amp=15, path=["sill_l", "tank"], critical=True,
         consumer=("бензонасос", "tank", "slot:fuel_pump")),
    dict(key="dash", name="Приборы и подсветка щитка", amp=8, path=["dash"], critical=False,
         consumer=("лампы щитка приборов", "dash", "bulb")),
    dict(key="head_l", name="Фара левая", amp=10, path=["dash", "bay_l"], critical=False,
         consumer=("лампа и патрон левой фары", "bay_l", "bulb")),
    dict(key="head_r", name="Фара правая", amp=10, path=["dash", "bay_r"], critical=False,
         consumer=("лампа и патрон правой фары", "bay_r", "bulb")),
    dict(key="tail", name="Габариты и задние фонари", amp=8, path=["sill_l", "trunk"], critical=False,
         consumer=("патрон заднего фонаря", "trunk", "bulb")),
    dict(key="brake", name="Стоп-сигналы", amp=10, path=["dash", "sill_l", "trunk"], critical=False,
         consumer=("лампа стоп-сигнала", "trunk", "bulb")),
    dict(key="turn", name="Поворотники и аварийка", amp=10, path=["column", "sill_l", "trunk"], critical=False,
         consumer=("реле-прерыватель поворотников", "column", "relay")),
    dict(key="horn", name="Звуковой сигнал", amp=15, path=["column", "bay_r"], critical=False,
         consumer=("звуковой сигнал", "bay_r", "horn")),
]
BY_KEY = {c["key"]: c for c in CIRCUITS}
KEYS = [c["key"] for c in CIRCUITS]
LIGHTING = ("head_l", "head_r", "tail", "brake", "turn")

KIND_SHORT = {"short": "КЗ провода", "open": "обрыв провода", "consumer": "неисправен потребитель",
              "corrosion": "окисленные контакты"}
KIND_RU = {"short": "короткое замыкание провода на массу", "open": "обрыв провода",
           "consumer": "неисправен потребитель", "corrosion": "окислены контакты в блоке предохранителей"}

# где блок предохранителей: под панелью слева (большинство) или в моторном отсеке
BOX_BAY = {"w123", "taunus"}
BOX_NAME = {"vaz2102": "блок ПР-12 под панелью, слева от руля", "trabant": "коробка предохранителей под панелью слева",
            "w123": "блок в моторном отсеке у левого щита", "taunus": "блок в моторном отсеке у левого щита"}

ITEM_DEFS = {
    "fuse_set":  dict(name="Набор предохранителей (10 шт.)", kind="material", price=4.0),
    "multimeter": dict(name="Мультиметр (прозвонка цепей)", kind="tool", price=39.0),
    "wire_kit":  dict(name="Ремкомплект проводки (провод, клеммы, изолента)", kind="material", price=9.0),
    "bulb":      dict(name="Лампа с патроном (фара / фонарь / щиток)", kind="part", price=6.0),
    "relay":     dict(name="Реле (стартера / поворотов)", kind="part", price=14.0),
    "coil":      dict(name="Катушка зажигания", kind="part", price=38.0),
    "horn":      dict(name="Звуковой сигнал", kind="part", price=19.0),
}
FIX_MIN = {"short": 30, "open": 25, "consumer": 15, "corrosion": 10}
CONSUMER_BLOW = 2.5        # сек работы неисправного потребителя до того, как сгорит предохранитель


def box_place(car):
    return "bay" if car.model in BOX_BAY else "dash"


def box_name(car):
    return BOX_NAME.get(car.model, "блок предохранителей в моторном отсеке" if box_place(car) == "bay"
                        else "блок предохранителей под панелью слева от руля")


def fuse_no(key):
    return KEYS.index(key) + 1


def circuit_name(car, key):
    c = BY_KEY[key]
    if key == "fuel":
        if car.sp("diesel"):
            return "Топливо (стоп-клапан ТНВД)"
        return "Бензонасос" if not car.spec.get("carb") else "Клапан карбюратора (ЭПХХ) и бензонасос"
    if key == "ign" and car.sp("diesel"):
        return "Зажигание (свечи накаливания, реле)"
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
    car.say(f"Щёлк — пропало: {circuit_name(car, key).lower()}. {why}")
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
                car.say("Пахнет горелой изоляцией! Вместо предохранителя «жучок» — плавится проводка.")
            if f["kind"] == "short" and random.random() < 0.05 * dt:
                other = random.choice([k for k in KEYS if k != key])
                if other not in d["faults"]:
                    d["faults"][other] = _fault(other, "short", random.Random())
                    car.say("Оплавились соседние провода в жгуте — появилось новое замыкание.")
            return False
        if f["kind"] == "short":
            _blow(car, key, "Предохранитель сгорел сразу — в цепи замыкание.")
            return False
        d["t"][key] = d["t"].get(key, 0.0) + dt
        if d["t"][key] >= CONSUMER_BLOW:
            _blow(car, key, "Предохранитель не выдержал нагрузки — что-то с потребителем.")
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
                    car.engine_off("Мотор заглох разом, как выключили — пропало питание зажигания.")
                elif key == "fuel":
                    car.fuel_cut = getattr(car, "fuel_cut", 0.0) + dt
                    if car.fuel_cut > 2.5:
                        car.fuel_cut = 0.0
                        car.engine_off("Мотор почихал и заглох — топливо не подаётся (нет питания цепи топлива).")


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
        return "Аккумулятор сел или снят — проверять нечем."
    if not _harness(car):
        return "Проводка сгнила целиком — нужен новый жгут (деталь «Электропроводка»)."
    st = d["fuses"][key]
    if st == "blown":
        return f"Не работает: {name}. Предохранитель F{fuse_no(key)} перегорел — замените его."
    f = d["faults"].get(key)
    if f and f["kind"] == "short" and st == "ok":
        _blow(car, key, "")
        return f"ХЛОП! Новый предохранитель F{fuse_no(key)} сгорел сразу, как только включили. В цепи КЗ — " \
               "ищите причину мультиметром, иначе будет гореть каждый раз."
    if f and f["kind"] == "consumer" and st == "ok":
        _blow(car, key, "")
        return f"{circuit_name(car, key)} заработал(а) на пару секунд — и предохранитель F{fuse_no(key)} снова сгорел. " \
               "Перегружает сам потребитель — прозвоните цепь."
    if f and f["kind"] in ("open", "corrosion"):
        return f"Предохранитель F{fuse_no(key)} цел, но {name} не работает — питание не доходит. " \
               "Обрыв или плохой контакт: прозвоните мультиметром."
    if st == "bug":
        return f"Работает — но на «жучке». При любой неисправности сгорит уже проводка."
    return f"Работает: {name}."


def probe(car, key):
    """Прозвонка мультиметром (предохранитель вынут, ключ выключен). Находит место неисправности."""
    d = data(car)
    f = d["faults"].get(key)
    c = BY_KEY[key]
    path = " → ".join(SEGMENTS[s][0].split(" — ")[0] for s in ["box"] + c["path"])
    lines = [f"Цепь F{fuse_no(key)} ({circuit_name(car, key)}): {path}."]
    if not f:
        lines.append("Сопротивление на массу — как у исправного потребителя, обрывов нет. Цепь в порядке.")
        if d["fuses"][key] == "blown":
            lines.append("Предохранитель сгорел когда-то от скачка — просто замените.")
        return lines
    f["found"] = True
    seg = SEGMENTS[f["seg"]]
    if f["kind"] == "short":
        lines += ["Сопротивление на массу 0,2 Ом — КОРОТКОЕ ЗАМЫКАНИЕ.",
                  f"Отключая разъёмы по очереди, нашли участок: {seg[0]}.",
                  f"Там перетёрта изоляция о кузов. Доступ: {seg[1]}. Нужен ремкомплект проводки — "
                  "место отмечено на машине красным."]
    elif f["kind"] == "open":
        lines += ["Цепи нет: сопротивление — бесконечность. ОБРЫВ.",
                  f"Прозванивая по участкам, нашли разрыв: {seg[0]}.",
                  f"Доступ: {seg[1]}. Нужен ремкомплект проводки — место отмечено на машине."]
    elif f["kind"] == "consumer":
        fix = c["consumer"][2]
        what = ("заменить деталь «" + car.slots[fix[5:]][0] + "» (снимается как обычная деталь, по болтам)"
                if fix.startswith("slot:") else "поставить новую: " + ITEM_DEFS[fix]["name"].lower())
        lines += ["С отключённым потребителем КЗ пропадает — провода целы.",
                  f"Неисправен сам потребитель: {c['consumer'][0]} ({seg[0]}).",
                  f"Что делать: {what}. Место отмечено на машине."]
    else:
        lines += ["Провода целы, но на гнезде предохранителя падает 3–4 вольта.",
                  "Окислены контакты в блоке предохранителей — почистите их (набор ключей, 10 минут)."]
    return lines


def fix_needs(car, key):
    """(id предмета или None, описание) — что нужно, чтобы устранить найденную неисправность."""
    f = fault(car, key)
    if not f:
        return None, ""
    if f["kind"] in ("short", "open"):
        return "wire_kit", ITEM_DEFS["wire_kit"]["name"]
    if f["kind"] == "corrosion":
        return None, "набор ключей и наждачка"
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
        g.notify(f"Нужно заменить «{car.slots[slot][0]}» — открутите её крепёж и снимите (G), "
                 "потом поставьте новую. Электрика вылечится вместе с деталью.", (240, 200, 60), 8)
        return None
    if need and not g.has(need):
        g.notify(f"Нужно: {what}. Купить — в магазине «Восток» или в автосалоне Крюгера.", (210, 60, 50), 6)
        return None
    if need:
        g.take_item(need)
    g.advance(FIX_MIN[f["kind"]], working=True)
    del data(car)["faults"][key]
    g.play_sound("tool", 0.5)
    txt = {"short": "Перетёртое место заизолировали, провод уложили в держатель подальше от кромки.",
           "open": "Разрыв спаяли, поставили новые клеммы.",
           "consumer": f"Поставили новую деталь: {BY_KEY[key]['consumer'][0]}.",
           "corrosion": "Контакты зачистили до блеска — питание идёт."}[f["kind"]]
    if fuse(car, key) == "blown":
        txt += f" Осталось заменить сгоревший предохранитель F{fuse_no(key)}."
    return txt


# ------------------------------------------------------------------ последствия: полиция и TÜV
def light_defects(car, night):
    """Неисправности света, которые видно со стороны. [(текст, серьёзно ли, штраф)]."""
    out = []
    hl, hr = works(car, "head_l") and car.has("lights") and car.c("lights") > 0.05, \
        works(car, "head_r") and car.has("lights") and car.c("lights") > 0.05
    if night:
        if not hl and not hr:
            out.append(("Ночью без фар: обе фары не работают", True, 60))
        elif not (hl and hr):
            out.append(("Не горит " + ("левая" if not hl else "правая") + " фара («одноглазый»)", False, 20))
        if not works(car, "tail"):
            out.append(("Ночью не горят задние габаритные фонари", True, 50))
    if getattr(car, "_braked_t", 99.0) < 4.0 and not works(car, "brake"):
        out.append(("Не горят стоп-сигналы", False, 35))
    if getattr(car, "_turned_t", 99.0) < 6.0 and not works(car, "turn"):
        out.append(("Не работают указатели поворота", False, 20))
    return out


def tuv_defects(car):
    d = data(car)
    out = []
    names = {"head_l": "левая фара", "head_r": "правая фара", "tail": "задние габаритные огни",
             "brake": "стоп-сигналы", "turn": "указатели поворота", "horn": "звуковой сигнал"}
    for key, nm in names.items():
        pre = "Звуковой сигнал" if key == "horn" else "Освещение"
        if not works(car, key):
            out.append(f"{pre}: не работает — {nm} (F{fuse_no(key)})")
        elif (d["faults"].get(key) or {}).get("kind") == "consumer":
            out.append(f"{pre}: неисправен потребитель — {nm}")
    for key, st in d["fuses"].items():
        if st == "bug":
            out.append(f"Предохранитель F{fuse_no(key)} закорочен: «жучок» вместо предохранителя (пожароопасно)")
    return out


def report(car, multimeter=False):
    """Строки для компьютерной диагностики / тестера: состояние всех цепей."""
    d = data(car)
    lines = [f"ЭЛЕКТРИКА — {box_name(car)}. Напряжение АКБ: "
             f"{(11.2 + 1.5 * min(100, car.battery_charge) / 100) if car.has('battery') else 0:.1f} В."]
    bad = 0
    for key in KEYS:
        st = d["fuses"][key]
        f = d["faults"].get(key)
        ok = works(car, key)
        tag = {"ok": "цел", "blown": "ПЕРЕГОРЕЛ", "bug": "«жучок»"}[st]
        line = f"F{fuse_no(key)} {BY_KEY[key]['amp']}А {circuit_name(car, key)}: предохранитель {tag}"
        if not ok or f:
            bad += 1
            if f and f["found"]:
                line += f" · {KIND_RU[f['kind']]} — {SEGMENTS[f['seg']][0].split(' — ')[0]}"
            elif st == "ok" and f:
                line += " · питание не доходит" if f["kind"] in ("open", "corrosion") else " · нагрузка ненормальная"
            elif st == "blown" and f and multimeter:
                line += " · при включении сгорит снова — прозвоните"
            line += "  ✗"
        else:
            line += "  ✓"
        lines.append(line)
    if not bad:
        lines.append("Все цепи в порядке.")
    else:
        lines.append("Как искать: блок предохранителей → «Включить и проверить» → если снова горит или нет питания — "
                     "«Прозвонить мультиметром»: он покажет участок, место отметится на машине красным.")
    return lines
