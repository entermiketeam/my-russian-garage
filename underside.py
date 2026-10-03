"""Работа под машиной: просвет, домкрат и подставки, что доступно снизу, а что — только сверху.

* Детали низа (UNDER_SLOTS и нижняя часть двигателя UNDER_ENG) снимаются/ставятся/затягиваются только лёжа
  под машиной; детали моторного отсека — только стоя у открытого капота (из-под машины до них не достать).
* Под машину можно залезть, если хватает просвета. Без подъёма — тесно (сантиметров 17–18): пролезают голова
  и плечи у борта, мелкий крепёж достаётся, но КПП, коленвал и т. п. так не снять — поднимите машину.
* Домкрат (Rangierwagenheber) поднимает перёд или зад; подставки (Unterstellböcke) держат поднятую сторону.
  Лежать под машиной на одном домкрате опасно: во время работы он может соскочить.
* Поднятая машина не едет (колёса висят в воздухе).

car.lift = {"f": м, "r": м} — насколько поднят перёд/зад; car.lift_by = {"f": запись предмета, ...} — что держит.
Правила доступа включает 3D-игра (g.underside_rules = True); старая 2D-версия и прочее работают как раньше.
"""
import math
import random
from i18n import T

UNDER_SLOTS = {"exhaust", "gearbox", "clutch", "shocks", "steering", "starter"}
UNDER_ENG = {"oil_pan", "oil_pump", "rod_bearings", "conrods", "crankshaft", "main_bearings"}
# тяжёлые/крупные работы: лёжа в 17 см под порогом их не сделать — нужен подъём
HEAVY = {"gearbox", "clutch", "eng:crankshaft", "eng:main_bearings", "eng:conrods", "exhaust"}

JACK_H = 0.30          # насколько поднимает домкрат (м)
STAND_H = 0.28         # высота на подставках
MIN_CRAWL = 0.13       # меньше — под машину не пролезть совсем
FREE = 0.24            # от этого — можно ползать под машиной целиком
HEAVY_NEED = 0.30      # для тяжёлых работ
SLIP_PER_MIN = 0.004   # шанс соскочить с домкрата за минуту работы под машиной без подставок

END_RU = {"f": T("перёд"), "r": T("зад")}
# где деталь по длине: 0 — задняя ось, 1 — передняя (для просвета в этом месте)
POS_T = {"gearbox": 0.72, "clutch": 0.82, "exhaust": 0.45, "steering": 1.0, "starter": 0.9, "shocks": 0.5}

try:                                   # высота порога у моделей (как в 3D)
    from models import MODELS as _MODELS
    SILL = {m: v["body"]["sill"] for m, v in _MODELS.items()}
except Exception:                      # pragma: no cover
    SILL = {}
SILL.setdefault("vaz2102", 0.30)
SILL.setdefault("ae86", 0.30)


def norm(k):
    """Ключ детали в едином виде: слот ("gearbox") или "eng:<деталь>"."""
    if k.startswith("slot:"):
        return k[5:]
    return k


def is_under(k):
    k = norm(k)
    if k.startswith("eng:"):
        return k[4:] in UNDER_ENG
    return k in UNDER_SLOTS


def eng_key(k):
    """Деталь двигателя из меню (без префикса) → ключ."""
    return k if k.startswith("slot:") else "eng:" + k


def enabled(g):
    return bool(getattr(g, "underside_rules", False))


# ------------------------------------------------------------------ подъём
def lift(car):
    lf = getattr(car, "lift", None)
    if not isinstance(lf, dict):
        lf = {"f": 0.0, "r": 0.0}
        car.lift = lf
    lf.setdefault("f", 0.0)
    lf.setdefault("r", 0.0)
    if not isinstance(getattr(car, "lift_by", None), dict):
        car.lift_by = {}
    return lf


def is_lifted(car):
    lf = getattr(car, "lift", None)
    return isinstance(lf, dict) and (lf.get("f", 0) > 0.01 or lf.get("r", 0) > 0.01)


def held_by(car, end):
    e = (getattr(car, "lift_by", None) or {}).get(end)
    return e.get("id") if isinstance(e, dict) else None


def base_clear(car):
    """Просвет под порогом машины, стоящей на колёсах (м)."""
    c = SILL.get(car.model, 0.30) - 0.12
    if car.has_tune("susp"):
        c -= 0.035
    try:
        c -= 0.03 * len(car.flat_tires())
    except Exception:
        pass
    c -= getattr(car, "sink", 0.0)
    return c


def clearance(car, t=0.5):
    """Просвет в точке t по длине (0 — задняя ось, 1 — передняя), с учётом подъёма."""
    lf = lift(car)
    return base_clear(car) + lf["r"] + (lf["f"] - lf["r"]) * t


def t_of(car, z_local):
    """Локальная координата вдоль кузова (центр машины = 0) → t."""
    r, f = car.spec["axles"]
    sx = z_local + car.length / 2
    return (sx - r) / max(0.5, (f - r))


def part_t(k):
    k = norm(k)
    if k.startswith("eng:"):
        return 0.95
    if k == "shocks":
        return 0.5
    return POS_T.get(k, 0.6)


def where_text(k):
    return T("снизу (под машиной)") if is_under(k) else T("сверху (у открытого капота)")


# ------------------------------------------------------------------ доступ
def access(g, key, k, heavy=None):
    """Можно ли сейчас работать с деталью k машины key: (да/нет, почему нет)."""
    if not enabled(g):
        return True, ""
    k = norm(k)
    car = g.cars[key]
    lying = getattr(g.p, "under_car", None) == key
    if is_under(k):
        if not lying:
            return False, T("Эта деталь — снизу машины. Лягте под машину (подойдите к порогу, E «Лечь под машину»).")
        need_heavy = (k in HEAVY) if heavy is None else heavy
        c = clearance(car, part_t(k))
        if need_heavy and c < HEAVY_NEED:
            return False, (T("Тесно: просвет здесь {0:.0f} см — так это не снять. Поднимите машину домкратом "
                           "и поставьте на подставки (нужно ≥ {1:.0f} см).", c * 100, HEAVY_NEED * 100))
        return True, ""
    if lying and k not in ("tire_fl", "tire_fr", "tire_rl", "tire_rr"):
        return False, T("Из-под машины до этого не дотянуться — вылезьте (F) и работайте сверху.")
    return True, ""


def chain_split(g, key, chain):
    """Сколько деталей цепочки можно сделать подряд из текущего положения (до первой «из другого места»)."""
    n = 0
    for k in chain:
        ok, _ = access(g, key, k if k.startswith("slot:") else eng_key(k))
        if not ok:
            break
        n += 1
    return n


# ------------------------------------------------------------------ домкрат и подставки
def can_lift(g, key):
    car = g.cars[key]
    if car.running:
        return T("Сначала заглушите двигатель.")
    if abs(car.speed) > 0.1:
        return T("Машина катится.")
    if g.p.in_car:
        return T("Выйдите из машины.")
    if getattr(g.p, "under_car", None):
        return T("Сначала вылезьте из-под машины.")
    return None


def jack_up(g, key, end):
    car = g.cars[key]
    lf = lift(car)
    why = can_lift(g, key)
    if why:
        g.notify(why, (255, 80, 80))
        return False
    if lf[end] > 0.01:
        g.notify(T("{0} уже поднят.", END_RU[end].capitalize()), (255, 210, 60))
        return False
    for k2, c2 in g.cars.items():
        for e2, it in (getattr(c2, "lift_by", None) or {}).items():
            if isinstance(it, dict) and it.get("id") == "jack" and not g.has("jack"):
                g.notify(T("Домкрат стоит под машиной {name} ({0}). Подставьте там подставки или опустите.", END_RU[e2], name=c2.name),
                         (255, 80, 80), 6)
                return False
    if not g.need("jack", T("домкрат — магазин «Восток» или автосалон Крюгера")):
        return False
    e = g.take_item("jack")
    car.lift_by[end] = e
    g.play_sound("tool", 0.6)
    g.advance(3, working=True)
    lf[end] = JACK_H
    g.notify(T("{name}: {0} поднят домкратом на {1:.0f} см. Лежать под машиной на одном "
             "домкрате опасно — подставьте подставки.", END_RU[end], JACK_H * 100, name=car.name), (255, 210, 60), 7)
    return True


def put_stands(g, key, end):
    car = g.cars[key]
    lf = lift(car)
    if held_by(car, end) != "jack":
        g.notify(T("Подставки ставят под сторону, поднятую домкратом."), (255, 80, 80))
        return False
    if not g.need("stands", T("подставки — магазин «Восток» или автосалон Крюгера")):
        return False
    st = g.take_item("stands")
    jack = car.lift_by[end]
    car.lift_by[end] = st
    g.advance(4, working=True)
    lf[end] = STAND_H
    g.give(jack)
    g.play_sound("tool", 0.5)
    g.notify(T("{name}: {0} стоит на подставках ({1:.0f} см). Домкрат свободен.", END_RU[end], STAND_H * 100, name=car.name), (90, 220, 90), 6)
    return True


def lower(g, key, end):
    car = g.cars[key]
    lf = lift(car)
    if getattr(g.p, "under_car", None) == key:
        g.notify(T("Сначала вылезьте из-под машины!"), (255, 80, 80))
        return False
    what = held_by(car, end)
    if what is None:
        return False
    if what == "stands":
        if not g.need("jack", T("домкрат — приподнять машину, чтобы убрать подставки")):
            return False
        g.advance(4, working=True)
    else:
        g.advance(2, working=True)
    it = car.lift_by.pop(end)
    lf[end] = 0.0
    g.give(it)
    g.play_sound("tool", 0.5)
    wheels = ("tire_fl", "tire_fr") if end == "f" else ("tire_rl", "tire_rr")
    g.notify(T("{name}: {0} опущен", END_RU[end], name=car.name) + (T(" на колёса.") if all(car.has(w) for w in wheels)
                                                    else T(" — колеса нет, встала на кирпичи.")), (90, 220, 90))
    return True


def tick(g, minutes, working):
    """Время работы под машиной на одном домкрате: может соскочить."""
    key = getattr(g.p, "under_car", None)
    if not key or not working or key not in g.cars:
        return
    car = g.cars[key]
    for end in ("f", "r"):
        if held_by(car, end) == "jack" and random.random() < 1 - (1 - SLIP_PER_MIN) ** minutes:
            lift(car)[end] = 0.0
            jack = car.lift_by.pop(end)
            g.loose.append({"id": jack["id"], "cond": max(0.0, jack["cond"] - 25), "x": round(car.x, 2),
                            "y": round(car.y, 2), "place": "road", "rot": 0.0})
            g.p.health = max(1.0, g.p.health - 45)
            g.p.under_car = None
            g.notify(T("Домкрат соскочил — машина рухнула! Вы чудом успели откатиться, но сильно ударились. "
                     "Под машину — только на подставках."), (255, 80, 80), 10)
            if hasattr(g, "on_crawl_out"):
                g.on_crawl_out(key, None)
            return


def status(car):
    lf = lift(car)
    parts = []
    for end in ("f", "r"):
        if lf[end] > 0.01:
            parts.append(T("{0} — {1}", END_RU[end], T('подставки') if held_by(car, end) == 'stands' else T('домкрат')))
    return ", ".join(parts)
