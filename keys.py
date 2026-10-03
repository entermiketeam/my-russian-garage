"""Ключи, замки и зажигание.

У каждой машины свой код ключа (car.key_code). Ключ — обычный предмет инвентаря (носится в руке):
{"id": "key", "cond": 100, "car": ключ машины в g.cars, "code": код, "spare": запасной ли}.
  * завести машину можно только своим ключом в замке зажигания (car.ign_key) — или «напрямую», если
    замок зажигания раскурочен (car.hotwired: угонщики или сам игрок соединил провода);
  * двери запираются ключом снаружи (K) или кнопкой изнутри; запертую машину не открыть обычным способом —
    только взломать (монтировка), после чего замок сломан (car.lock_broken) до замены личинок;
  * замена замков (личинки + замок зажигания) даёт новый код: старые ключи больше не подходят.
"""
import random
from i18n import T

CENTRAL = {"civic", "w123", "bmw_e21", "volvo240", "audi80", "golf", "mustang", "ae86"}   # центральный замок + мигание
LOCKSET_PRICE = 45.0


TAKEN = set()          # выданные коды — чтобы у двух машин не оказалось одинаковых ключей


def ensure(car, rng=None):
    """Код ключа и поля замков (для машин из старых сохранений тоже). Коды уникальны."""
    if not getattr(car, "key_code", None):
        r = rng or random.Random(car.seed * 31 + 7)
        code = f"{r.randint(10000, 99999)}"
        while code in TAKEN:
            code = f"{r.randint(10000, 99999)}"
        car.key_code = code
    TAKEN.add(car.key_code)
    for k, v in (("locked", False), ("ign_key", None), ("lock_broken", False), ("hotwired", False), ("stolen", None)):
        if not hasattr(car, k):
            setattr(car, k, v)
    return car.key_code


def make(g, car_key, spare=False):
    car = g.cars[car_key]
    ensure(car)
    return {"id": "key", "cond": 100.0, "car": car_key, "code": car.key_code, "spare": bool(spare)}


def fits(e, car):
    return bool(e) and e.get("id") == "key" and e.get("code") == getattr(car, "key_code", None)


def name(g, e):
    car = g.cars.get(e.get("car")) if hasattr(g, "cars") else None
    if car is None:
        return T("Ключ от чужой машины")
    tail = f" ({car.plate})" if car.registered else ""
    if car.key_code != e.get("code"):
        return T("Старый ключ {name} — замки поменяны", name=car.name)
    return (T("Запасной ключ ") if e.get("spare") else T("Ключ ")) + car.name + tail


def key_in_hands(g, car):
    for i, e in enumerate(g.p.hands):
        if fits(e, car):
            return i
    return None


def has_central(car):
    return car.model in CENTRAL


def can_start(car):
    """Можно ли крутить стартер: свой ключ в замке или провода напрямую."""
    return fits(car.ign_key, car) or car.hotwired


def color_name(rgb):
    """Цвет кузова словами (для заявления в полицию и объявлений)."""
    if rgb is None:
        return T("непонятного цвета (грунт и ржавчина)")
    r, g, b = rgb
    mx, mn = max(rgb), min(rgb)
    if mx < 60:
        return T("чёрный")
    if mx - mn < 25:
        return T("белый") if mx > 200 else (T("серебристый") if mx > 150 else T("серый"))
    if r >= g and r >= b:
        if g > 150 and b < 120:
            return T("бежевый") if g > 170 else T("жёлтый")
        if g > 100:
            return T("оранжевый") if b < 80 else T("бежевый")
        return T("красный") if r > 140 else T("бордовый")
    if g >= r and g >= b:
        return T("зелёный") if g > 90 else T("тёмно-зелёный")
    return T("синий") if b > 120 else T("тёмно-синий")


def features(car):
    """Особые приметы машины — то, по чему её узнают."""
    out = []
    if car.max_rust() > 55:
        out.append(T("сильно ржавая, дыры в порогах"))
    elif car.max_rust() > 30:
        out.append(T("заметная ржавчина"))
    if getattr(car, "odd_door", False) and car.model == "vaz2102":
        out.append(T("левая дверь другого цвета"))
    if car.deforms:
        out.append(T("битая: вмятины кузова"))
    if car.dirt > 0.6:
        out.append(T("очень грязная"))
    if any(isinstance(p, dict) for p in (car.tune or {}).values()):
        out.append(T("тюнинг"))
    miss = [car.slots[s][0].lower() for s in ("hood", "trunk", "door_l", "door_r") if s in car.slots and not car.has(s)]
    if miss:
        out.append(T("нет: ") + ", ".join(miss))
    if not out:
        out.append(T("без особых примет"))
    return out


def describe(car):
    """Строка для заявления/объявления: марка, модель, цвет, номер, приметы."""
    plate = T("номер {plate}", plate=car.plate) if car.registered else T("без номеров")
    return T("{name}, {color_name}, {plate}; приметы: ", name=car.name, color_name=color_name(car.color), plate=plate) + ", ".join(features(car))
