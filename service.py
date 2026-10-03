"""Автосервис «Kfz-Werkstatt Schmidt» (Industriestraße) и бессрочная гарантия.

Гарантия: у каждой машины поле car.warranty = "lifetime" (бессрочная, уже оформлена; не сбрасывается и не
продлевается). Сервис при приёмке сам проверяет гарантию и, если она есть, всё делает бесплатно.

Как это работает: машину ставят в свободную ячейку цеха (двигатель заглушен) → мастер принимает (в часы работы),
осматривает (30 мин) и выдаёт список неисправностей по системам со сметой → «ремонт» — машина остаётся в цеху,
механики работают (время зависит от объёма) → по готовности машину выгоняют на парковку сервиса и зовут забрать.
Ремонт по-настоящему меняет состояние: детали, внутренности двигателя, шины, кузов, электрика, замки, жидкости.
"""
import math

from world import SERVICE_BAYS, SERVICE_PARK, SERVICE_DOOR_PT, point_in
from items import ITEMS
from i18n import T, src

NAME = T("Автосервис Шмидта")
HOURS = {d: (7, 18) for d in range(5)}
HOURS[5] = (8, 13)
LABOR = 65.0              # ₽ в час (для сметы)
MECHANICS = 2


def has_warranty(car):
    return getattr(car, "warranty", None) == "lifetime"


def ensure_warranty(car):
    """Бессрочная гарантия есть у всех машин: если поля нет (старое сохранение) — ставим, существующее не трогаем."""
    if not getattr(car, "warranty", None):
        car.warranty = "lifetime"


def is_open(g):
    span = HOURS.get(g.weekday())
    return bool(span) and span[0] <= g.hour < span[1]


def hours_text():
    return T("Пн–Пт 7–18, Сб 8–13, Вс закрыто")


def bay_of(car):
    for i, b in enumerate(SERVICE_BAYS):
        if point_in(b, car.x, car.y):
            return i
    return None


def bay_busy(g, i, except_key=None):
    for k, c in g.cars.items():
        if k != except_key and getattr(c, "service", None) and c.service.get("bay") == i:
            return True
    return False


# ------------------------------------------------------------------ осмотр
def inspect(car):
    """Список неисправностей по системам: [(система, что, деталь-ид или None, минут работы)]."""
    import engine as eng
    import electrics as el
    import tires as T
    import damage
    out = []

    def part(sl, what, lim=0.6):
        if sl not in car.slots:
            return
        p = car.parts.get(sl)
        nm = car.slots[sl][0]
        if p is None:
            out.append((what, T("{nm}: отсутствует — поставить новую", nm=nm), car.slots[sl][1], car.slots[sl][2]))
        elif p["cond"] < lim * 100:
            out.append((what, T("{nm}: износ {0:.0f}% — заменить", 100 - p['cond'], nm=nm), car.slots[sl][1], car.slots[sl][2]))
    if car.parts.get("engine") is None:
        part("engine", T("Двигатель"), 1.1)
    elif car.eng:
        for k in eng.keys(car.model):
            e = car.eng.get(k)
            if e is None or e["cond"] < 60:
                nm = eng.label(car, k)
                out.append((T("Двигатель"), f"{nm}: " + (T("нет — поставить") if e is None else T("износ {0:.0f}% — заменить", 100 - e['cond'])),
                            eng.part_id(car.model, k), max(20, eng.minutes(car, k) // 2)))
        fl = car.eng_flags or {}
        for f_, txt in (("timing_off", T("метки ГРМ сбиты — выставить")), ("head_loose", T("ГБЦ затянута не по схеме — перетянуть")),
                        ("gasket_reused", T("старая прокладка ГБЦ — заменить"))):
            if fl.get(f_):
                out.append((T("Двигатель"), txt, None, 90))
    for sl, sys_ in (("gearbox", T("Трансмиссия")), ("clutch", T("Трансмиссия")), ("shocks", T("Подвеска")), ("steering", T("Рулевое")),
                     ("brakes_f", T("Тормоза")), ("brakes_r", T("Тормоза")), ("radiator", T("Охлаждение")), ("exhaust", T("Выхлоп")),
                     ("battery", T("Электрика")), ("alternator", T("Электрика")), ("starter", T("Электрика")), ("wiring", T("Электрика")),
                     ("lights", T("Свет")), ("glass", T("Кузов")), ("carb", T("Топливо/зажигание")), ("fuel_pump", T("Топливо/зажигание")),
                     ("fuel_filter", T("Топливо/зажигание")), ("air_filter", T("Топливо/зажигание")), ("plugs", T("Топливо/зажигание")),
                     ("distributor", T("Топливо/зажигание")), ("belt", T("Двигатель")), ("seats", T("Салон")),
                     ("door_l", T("Кузов")), ("door_r", T("Кузов")), ("hood", T("Кузов")), ("trunk", T("Кузов"))):
        part(sl, sys_, 0.55 if src(sys_) not in ("Тормоза", "Рулевое") else 0.7)
    for t in car.tire_list():
        if not car.has(t) or T.tread_mm(car, t) < 3.0 or car.c(t) < 0.05:
            out.append((T("Шины"), T("{0}: протектор {tread_mm:.1f} мм — новая шина", car.slots[t][0], tread_mm=T.tread_mm(car, t)), car.slots[t][1], 20))
        elif abs(T.pressure(car, t) / T.nominal(car, t) - 1) > 0.1:
            out.append((T("Шины"), T("{0}: давление {pressure:.1f} бар — подкачать", car.slots[t][0], pressure=T.pressure(car, t)), None, 3))
    if car.deforms or car.dents or abs(getattr(car, "align", 0.0)) > 0.001:
        zn = damage.zones(car) if car.deforms else {}
        depth = sum(zn.values()) if zn else 0.1
        out.append((T("Кузов"), T("после аварии: выправить кузов, развал-схождение") + (T(" (стапель)") if damage.is_totaled(car) else ""),
                    None, int(120 + depth * 900)))
    rust = [(p, v) for p, v in car.rust.items() if v > 20]
    if rust:
        out.append((T("Кузов"), T("ржавчина ({0} мест, до {1:.0f}%) — вырезать, вварить, покрасить", len(rust), max(v for _, v in rust)),
                    None, 60 * len(rust)))
    d = el.data(car)
    bad = [k for k in el.KEYS if d["fuses"][k] != "ok" or k in d["faults"]]
    if bad:
        out.append((T("Электрика"), T("цепи: ") + ", ".join(el.circuit_name(car, k).lower() for k in bad[:5]) +
                    (" …" if len(bad) > 5 else "") + T(" — найти и устранить"), None, 30 * len(bad)))
    if car.lock_broken or car.hotwired:
        out.append((T("Замки"), T("сломан замок") + (T(" и разобран замок зажигания") if car.hotwired else "") + T(" — новые замки и ключи"),
                    "lockset", 60))
    if car.oil_cap > 0 and (car.oil < car.oil_cap * 0.9 or car.oil_quality < 60):
        out.append((T("Жидкости"), T("масло: замена"), "oil", 25))
    if car.coolant_cap > 0 and car.coolant < car.coolant_cap * 0.9:
        out.append((T("Жидкости"), T("антифриз: долить"), "coolant", 10))
    if car.brake_fluid < 80:
        out.append((T("Жидкости"), T("тормозная жидкость: прокачать"), "brake_fl", 20))
    if car.bolts:
        out.append((T("Крепёж"), T("недотянутый крепёж ({0} узлов) — протянуть", len(car.bolts)), None, 10 * len(car.bolts)))
    for node, p in (car.tune or {}).items():
        if isinstance(p, dict) and p.get("cond", 100) < 55:
            out.append((T("Тюнинг"), T("{name}: износ — восстановить", name=ITEMS.get(p['id'], {}).get('name', node)), p["id"], 90))
    return out


def estimate(found):
    parts = sum(ITEMS.get(pid, {}).get("price", 0) for _, _, pid, _ in found if pid)
    minutes = sum(m for *_, m in found)
    return parts, minutes, parts + minutes / 60 * LABOR


# ------------------------------------------------------------------ ремонт
def repair_all(g, car):
    """Полный ремонт по списку осмотра. Меняет реальное состояние машины."""
    import engine as eng
    import electrics as el
    import tires as T
    import fasteners as fast
    for sl, (nm, pid, _) in car.slots.items():
        p = car.parts.get(sl)
        if p is None:
            car.parts[sl] = {"id": pid, "cond": 100.0}
        elif p["cond"] < 100:
            p["cond"] = 100.0
    if car.parts.get("engine") is not None:
        eng.init(car, base=100)
        car.eng_flags = {}
    car.bolts = {}
    for t in car.tire_list():
        T.set_nominal(car, t)
    # кузов: вмятины, геометрия, ржавчина
    car.deforms = []
    car.dents = []
    car.align = 0.0
    car._total_said = False
    for pn in car.rust:
        car.rust[pn] = 0.0
        car.painted[pn] = True
    el.clean(car)
    car.mangel = getattr(car, "mangel", None)
    if car.lock_broken or car.hotwired:
        import keys
        car.lock_broken = car.hotwired = False
    car.oil, car.oil_quality = car.oil_cap, 100.0
    car.coolant = car.coolant_cap
    car.brake_fluid = 100.0
    car.battery_charge = 100.0
    car.dirt = 0.05                                   # помыли
    for node, p in (car.tune or {}).items():
        if isinstance(p, dict):
            p["cond"] = 100.0
    if hasattr(car, "refresh_spec"):
        car.refresh_spec()
    car._rebuild3d = True


def start(g, key, found):
    car = g.cars[key]
    parts, minutes, total = estimate(found)
    hours = max(1.0, minutes / 60 / MECHANICS)
    bay = bay_of(car)
    car.service = {"bay": bay, "until": g.minutes + 30 + hours * 60, "since": g.minutes, "found": [f[1] for f in found],
                   "total": round(total, 2), "warranty": has_warranty(car), "stage": "repair"}
    car.running = False
    car.hood_open = True
    car.door_open = {k: False for k in car.door_open}
    car.locked = False
    if not has_warranty(car):
        g.charge(total, T("{NAME}: ремонт {name}", NAME=NAME, name=car.name))
    return hours


def tick(g):
    """Готовые машины — на парковку сервиса и сообщение."""
    for k, car in list(g.cars.items()):
        sv = getattr(car, "service", None)
        if not sv or g.minutes < sv["until"]:
            continue
        repair_all(g, car)
        spot = free_spot(g, k)
        if spot:
            car.x, car.y, car.angle = spot
        car.speed = car.vlat = car.ang_vel = 0.0
        car.hood_open = False
        car.service = None
        car.service_done = {"day": g.day, "found": sv["found"], "total": sv["total"], "warranty": sv["warranty"]}
        g.notify(T("{NAME}: ваш {name} готов — стоит на парковке у мастерской. ", NAME=NAME, name=car.name)
                 + (T("Всё по бессрочной гарантии — 0 ₽.") if sv["warranty"] else T("Оплачено {total:.0f} ₽.", total=sv['total'])),
                 (90, 190, 90), 12)


def free_spot(g, key):
    for x, y, a in SERVICE_PARK:
        if all(math.hypot(c.x - x, c.y - y) > 3.0 for k, c in g.cars.items() if k != key):
            return (x, y, a + math.pi)                    # носом к цеху
    x, y, a = SERVICE_PARK[0]
    return (x, y + 3, a)


def in_service(car):
    return bool(getattr(car, "service", None))


def ready_text(g, car):
    sv = car.service
    left = max(0.0, sv["until"] - g.minutes)
    return T("в ремонте — готово примерно через {0:.1f} ч", left / 60)


# ------------------------------------------------------------------ приёмка (диалог)
def reception(g, key):
    """Мастер-приёмщик у машины в ячейке."""
    car = g.cars[key]
    if not is_open(g):
        g.info(NAME, [T("Закрыто. Мастерская не работает."), T("Часы работы: {hours_text}.", hours_text=hours_text()),
                      T("Машину можно оставить на парковке и приехать в рабочее время.")])
        return
    if car.running:
        g.notify(T("Заглушите двигатель — мастер не примет машину с работающим мотором."), (230, 140, 40))
        return
    ensure_warranty(car)
    g.advance(30)                                     # осмотр
    found = inspect(car)
    parts, minutes, total = estimate(found)
    hours = max(1.0, minutes / 60 / MECHANICS)
    lines = [T("Мастер Уве Шмидт обходит {name} с фонарём, заглядывает под капот и под днище (подъёмник).", name=car.name),
             T("Гарантия: ") + (T("БЕССРОЧНАЯ — действует (проверено по сервисной книжке)") if has_warranty(car) else T("нет")), ""]
    if not found:
        g.info(NAME, lines + [T("«Всё в порядке!» — неисправностей не найдено. Можно ехать.")])
        return
    by = {}
    for sys_, what, pid, m in found:
        by.setdefault(sys_, []).append(what)
    for sys_, ws in by.items():
        lines.append(f"{sys_}:")
        for w in ws[:6]:
            lines.append("   • " + w)
        if len(ws) > 6:
            lines.append(T("   • … и ещё {0}", len(ws) - 6))
    lines += ["", T("Смета: детали {parts:.0f} ₽ + работа {0:.1f} н·ч × {LABOR:.0f} ₽ = {total:.0f} ₽.", minutes / 60, parts=parts, LABOR=LABOR, total=total),
              (T("К оплате: 0 ₽ — всё по бессрочной гарантии.") if has_warranty(car) else T("К оплате: {total:.0f} ₽.", total=total)),
              T("Срок: около {hours:.1f} ч (работают {MECHANICS} механика). Машина остаётся в цеху.", hours=hours, MECHANICS=MECHANICS)]

    def go():
        if not has_warranty(car) and g.p.money < total:
            g.notify(T("Не хватает денег на ремонт."), (210, 60, 50))
            return
        h = start(g, key, found)
        if g.p.in_car and g.cur == key:
            g.p.in_car = False
            g.p.x, g.p.y = SERVICE_DOOR_PT[0] + 2.5, SERVICE_DOOR_PT[1]
        g.notify(T("{name} в работе — примерно {h:.1f} ч. Мы сообщим, когда будет готово.", name=car.name, h=h), (90, 190, 90), 8)
    g.dialog(NAME, lines, [(T("Ремонтировать всё") + (T(" (по гарантии, 0 ₽)") if has_warranty(car) else f" ({total:.0f} ₽)"),
                            go, True)], wide=True)


def office(g):
    """Стойка приёмки: какие машины в работе, какие готовы."""
    lines = [f"{NAME} · {hours_text()}", T("Заехать в свободную ячейку цеха, заглушить мотор — мастер примет машину."),
             T("Бессрочная гарантия на все ваши машины: ремонт бесплатно.")]
    for k, c in g.owned_cars():
        if in_service(c):
            lines.append(f"• {c.name}: {ready_text(g, c)}")
        elif getattr(c, "service_done", None) and c.service_done.get("day", -9) >= g.day - 1:
            lines.append(T("• {name}: готов, стоит на парковке", name=c.name))
    g.info(NAME, lines)
