"""Хранилища предметов: багажник машины, холодильник дома, стеллаж в гараже.

С собой у игрока только две руки: взять из хранилища — в свободную руку, положить — из руки.

Предметы — те же записи, что и в инвентаре ({"id", "cond", ...}): переложили — запись переехала из одного
списка в другой, ничего не создаётся и не теряется. Сохраняются вместе с машиной / квартирой.
"""
from items import ITEMS, item_name

GAME = None          # ссылка на игру (для имён ключей: «Ключ ВАЗ 2102 (KB-VZ 102)»)


def key_label(e):
    if GAME is not None:
        import keys
        return keys.name(GAME, e)
    return "Ключ зажигания"


CAPACITY = {"trunk": 24, "fridge": 30, "shelf": 60, "hook": 12}
ORDER = {"food": 0, "drink": 1, "fluid": 2, "material": 3, "part": 4, "tool": 5}


def label(e):
    if e.get("id") == "key":
        return key_label(e)
    if e.get("id") == "flyer":
        return f"Листовки «Gestohlen!» ({int(round(e.get('cond', 100) / 10))} шт.)"
    it = ITEMS.get(e["id"], {})
    return it.get("name", e["id"]) + (f" [{e['cond']:.0f}%]" if it.get("kind") == "part" else "")


def put(g, container, entry, kind="trunk"):
    """Переложить запись из инвентаря в хранилище. Возвращает True, если получилось."""
    if len(container) >= CAPACITY.get(kind, 99):
        g.notify("Больше не помещается.", (210, 60, 50))
        return False
    if not g.release(entry):                 # класть можно только то, что в руках
        return False
    container.append(entry)
    return True


def take(g, container, entry):
    """Взять из хранилища — в свободную руку. Обе руки заняты — нельзя."""
    if not any(x is entry for x in container):
        return False
    fh = g.free_hand()
    if fh is None:
        g.notify("Обе руки заняты — сначала положите что-нибудь (X / Z).", (210, 60, 50))
        return False
    container.remove(entry)
    g.p.hands[fh] = entry
    return True


def grouped(entries, only=None):
    """Группы одинаковых предметов: [(первая запись, сколько)] — чтобы список был коротким."""
    groups = {}
    for e in entries:
        it = ITEMS.get(e["id"], {})
        if only and it.get("kind") not in only:
            continue
        key = e["id"] if it.get("kind") != "part" else (e["id"], round(e["cond"]))
        groups.setdefault(key, []).append(e)
    out = sorted(groups.values(), key=lambda es: (ORDER.get(ITEMS.get(es[0]["id"], {}).get("kind"), 9), label(es[0])))
    return [(es[0], len(es)) for es in out]
