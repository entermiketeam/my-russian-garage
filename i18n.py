"""Локализация: все тексты игры проходят через T().

    T("Новая игра")                         -> "New game" / "Новая игра" / ...
    T("Купили {name} за {price:.2f} ₽", name=n, price=p)

Ключ перевода (msgid) — исходный русский текст прямо в коде, как в gettext: код остаётся читаемым,
а переводы лежат в locales/<код>.json:

    {"_meta": {"name": "English"}, "strings": {"Новая игра": "New game", ...}}

Новый язык = новый файл в locales/ (скопируйте en.json, переведите значения) — он сам появится
в меню «Language». Проверить, чего не хватает:  python3 i18n.py check de

Если перевода нет (или он пустой / сломан) — берётся английский, если нет и его — исходный текст.
Выбранный язык хранится в settings.json; при первом запуске — английский.

Смена языка на лету: T() возвращает Msg — обычную строку, которая помнит свой msgid и аргументы.
set_language() перепереводит все Msg в таблицах модулей игры (ITEMS, CONTROLS, заголовки меню...) и в
объектах, переданных в relocalize(), а подписчики on_change() перестраивают уже созданные надписи.
"""
import json
import os
import sys
import types
import weakref

ROOT = os.path.dirname(os.path.abspath(__file__))
LOCALE_DIR = os.path.join(ROOT, "locales")
SETTINGS_FILE = os.path.join(ROOT, "settings.json")
SOURCE_LANG = "ru"        # язык текстов в коде (msgid)
DEFAULT_LANG = "en"       # язык при первом запуске
FALLBACK_LANG = "en"      # чем заменять отсутствующий перевод

_catalogs = {}            # код -> {"_meta": {...}, "strings": {...}}
_lang = DEFAULT_LANG
_strings = {}             # переводы текущего языка
_fallback = {}            # переводы языка FALLBACK_LANG
_listeners = []


class Msg(str):
    """Переведённая строка, которая помнит, из чего получилась, — чтобы перевести её заново."""
    __slots__ = ("msgid", "args", "kwargs")

    def again(self):
        return T(self.msgid, *[_again(a) for a in self.args], **{k: _again(v) for k, v in self.kwargs.items()})


def _again(v):
    return v.again() if isinstance(v, Msg) else v


def _fmt(tpl, args, kwargs):
    if not args and not kwargs:
        return tpl
    return tpl.format(*args, **kwargs)


def T(msgid, /, *args, **kwargs):
    """Перевести msgid на текущий язык и подставить аргументы (как str.format)."""
    out = None
    for tpl in (_strings.get(msgid), _fallback.get(msgid) if _lang != SOURCE_LANG else None, msgid):
        if not tpl:
            continue
        try:
            out = _fmt(tpl, args, kwargs)
            break
        except (IndexError, KeyError, ValueError, AttributeError, TypeError):
            continue                       # кривой перевод (не тот плейсхолдер) — пробуем следующий вариант
    if out is None:
        out = msgid
    m = Msg(out)
    m.msgid, m.args, m.kwargs = msgid, args, kwargs
    return m


def src(s):
    """Исходный текст (msgid) строки — для сравнений, которые не должны зависеть от языка."""
    return s.msgid if isinstance(s, Msg) else s


# ---------------------------------------------------------------------- каталоги и настройки
def _load_catalog(code):
    if code not in _catalogs:
        data = {}
        try:
            with open(os.path.join(LOCALE_DIR, code + ".json"), encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as e:
            print(f"[i18n] не удалось прочитать locales/{code}.json: {e}")
        data.setdefault("_meta", {})
        data.setdefault("strings", {})
        _catalogs[code] = data
    return _catalogs[code]


def languages():
    """[(код, название на этом языке)] — все языки из папки locales/."""
    out = []
    try:
        files = sorted(os.listdir(LOCALE_DIR))
    except OSError:
        files = []
    for fn in files:
        if fn.endswith(".json") and not fn.startswith("_"):
            code = fn[:-5]
            out.append((code, _load_catalog(code)["_meta"].get("name", code)))
    if not any(c == SOURCE_LANG for c, _ in out):
        out.append((SOURCE_LANG, SOURCE_LANG))
    order = {DEFAULT_LANG: 0, SOURCE_LANG: 1}
    return sorted(out, key=lambda x: (order.get(x[0], 2), x[1].lower()))


def current():
    return _lang


def language_name(code=None):
    return _load_catalog(code or _lang)["_meta"].get("name", code or _lang)


def _read_settings():
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_settings(**kw):
    d = _read_settings()
    d.update(kw)
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
    except OSError as e:
        print(f"[i18n] не удалось сохранить настройки: {e}")


def _activate(code):
    global _lang, _strings, _fallback
    known = [c for c, _ in languages()]
    if code not in known:
        code = DEFAULT_LANG if DEFAULT_LANG in known else SOURCE_LANG
    _lang = code
    _strings = _load_catalog(code)["strings"] if code != SOURCE_LANG or os.path.exists(
        os.path.join(LOCALE_DIR, code + ".json")) else {}
    _fallback = _load_catalog(FALLBACK_LANG)["strings"] if FALLBACK_LANG != SOURCE_LANG else {}


def set_language(code, save=True, roots=()):
    """Сменить язык сразу во всей игре. roots — живые объекты (сама игра), в которых тоже перевести тексты."""
    _activate(code)
    if save:
        _write_settings(language=_lang)
    relocalize(*roots)
    for ref in list(_listeners):
        fn = ref()
        if fn is None:
            _listeners.remove(ref)
            continue
        try:
            fn()
        except Exception as e:             # надпись уже уничтожена и т. п. — больше не вызываем
            print(f"[i18n] on_change: {e}")
            _listeners.remove(ref)


def on_change(fn):
    """Вызвать fn() после каждой смены языка (держится слабая ссылка — подписчик не мешает удалению объекта)."""
    ref = weakref.WeakMethod(fn) if isinstance(fn, types.MethodType) else weakref.ref(fn)
    _listeners.append(ref)
    return fn


def live(ent, text, after=None):
    """Надпись (ursina Text), которая создаётся один раз: при смене языка текст в ней переведётся заново."""
    if not isinstance(text, Msg):
        return ent
    holder = {"ent": weakref.ref(ent)}

    def upd():
        e = holder["ent"]()
        if e is None:
            return
        e.text = text.again()
        if after:
            after(e)
    holder["fn"] = upd                     # держим замыкание вместе с надписью
    try:
        ent._i18n_live = holder
    except AttributeError:
        pass
    if len(_listeners) % 256 == 255:           # чистим подписки уже удалённых надписей
        _listeners[:] = [r for r in _listeners if r() is not None]
    _listeners.append(lambda: holder["fn"] if holder["ent"]() is not None else None)
    return ent


# ---------------------------------------------------------------------- сохранения
# В сохранение тексты пишутся не переведёнными, а как {"$T": msgid, "a": [...], "k": {...}}:
# сохранились на русском — загрузятся на английском. Старые сохранения (обычные строки) читаются как есть.
def to_json(o):
    if isinstance(o, Msg):
        d = {"$T": o.msgid}
        if o.args:
            d["a"] = [to_json(a) for a in o.args]
        if o.kwargs:
            d["k"] = {k: to_json(v) for k, v in o.kwargs.items()}
        return d
    if isinstance(o, dict):
        return {k: to_json(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [to_json(v) for v in o]
    return o


def from_json(o):
    if isinstance(o, dict):
        if "$T" in o and isinstance(o["$T"], str):
            return T(o["$T"], *[from_json(a) for a in o.get("a", [])],
                     **{k: from_json(v) for k, v in o.get("k", {}).items()})
        return {k: from_json(v) for k, v in o.items()}
    if isinstance(o, list):
        return [from_json(v) for v in o]
    return o


# ---------------------------------------------------------------------- перевод уже созданных таблиц
def _game_modules():
    for m in list(sys.modules.values()):
        f = getattr(m, "__file__", None)
        if f and os.path.dirname(os.path.abspath(f)) == ROOT and m.__name__ != __name__:
            yield m


def relocalize(*roots):
    """Перевести заново все Msg в глобальных таблицах модулей игры, атрибутах классов, значениях по умолчанию
    функций и (вглубь) в объектах roots — экземплярах классов игры. Обход — без рекурсии (графы дорог и т. п.)."""
    mods = {m.__name__ for m in _game_modules()}
    seen = set()
    todo = []

    def val(v):
        """Новое значение для v (Msg и кортежи пересоздаются); изменяемые контейнеры — в очередь на обход."""
        if isinstance(v, Msg):
            return v.again()
        if v is None or isinstance(v, (str, bytes, int, float, bool)):
            return v
        if isinstance(v, tuple):
            new = [val(x) for x in v]
            if all(a is b for a, b in zip(new, v)):
                return v
            return type(v)._make(new) if hasattr(type(v), "_make") else tuple(new)
        if id(v) in seen:
            return v
        if isinstance(v, (dict, list, types.FunctionType, staticmethod, classmethod)) or (
                isinstance(v, type) and v.__module__ in mods) or (
                getattr(type(v), "__module__", None) in mods and hasattr(v, "__dict__")):
            seen.add(id(v))
            todo.append(v)
        return v

    def visit(o):
        if isinstance(o, dict):
            if any(isinstance(k, Msg) for k in o):
                items = [(val(k), val(v)) for k, v in o.items()]
                o.clear()
                o.update(items)
            else:
                for k, v in list(o.items()):
                    nv = val(v)
                    if nv is not v:
                        o[k] = nv
        elif isinstance(o, list):
            for i, v in enumerate(o):
                nv = val(v)
                if nv is not v:
                    o[i] = nv
        elif isinstance(o, types.FunctionType):
            if o.__defaults__:
                o.__defaults__ = val(o.__defaults__)
            if o.__kwdefaults__:
                visit(o.__kwdefaults__)
        elif isinstance(o, (staticmethod, classmethod)):
            val(o.__func__)
        else:                                    # класс игры или его экземпляр
            for k, v in list(vars(o).items()):
                if k.startswith("__"):
                    continue
                nv = val(v)
                if nv is not v:
                    try:
                        setattr(o, k, nv)
                    except (AttributeError, TypeError):    # свойство без сеттера и т. п.
                        pass

    for m in _game_modules():
        for k, v in list(vars(m).items()):
            if k.startswith("__") or isinstance(v, types.ModuleType):
                continue
            nv = val(v)
            if nv is not v:
                setattr(m, k, nv)
    for r in roots:
        val(r)
    while todo:
        visit(todo.pop())


# ---------------------------------------------------------------------- старт: язык из настроек
_activate(_read_settings().get("language", DEFAULT_LANG))


# ---------------------------------------------------------------------- инструменты переводчика
def _all_msgids():
    """Все тексты игры из исходников (то же, что видит T): {msgid: [файл:строка]}."""
    import ast
    out = {}
    for fn in sorted(os.listdir(ROOT)):
        if not fn.endswith(".py"):
            continue
        path = os.path.join(ROOT, fn)
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), fn)
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "T" and node.args
                    and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
                out.setdefault(node.args[0].value, []).append(f"{fn}:{node.lineno}")
    return out


def _main(argv):
    """python3 i18n.py check <код>   — каких переводов не хватает / какие лишние
       python3 i18n.py update <код>  — дописать недостающие строки (пустыми) в locales/<код>.json"""
    if len(argv) < 2 or argv[0] not in ("check", "update"):
        print(_main.__doc__)
        return 1
    cmd, code = argv[0], argv[1]
    ids = _all_msgids()
    if code == SOURCE_LANG:
        print(f"{code}: исходный язык — все {len(ids)} строк берутся прямо из кода.")
        return 0
    cat = _load_catalog(code)
    strings = cat["strings"]
    missing = [m for m in ids if not strings.get(m)]
    unused = [m for m in strings if m not in ids]
    bad = []
    import string
    for m, tr in strings.items():
        if not tr or m not in ids:
            continue
        want = {f for _, f, _, _ in string.Formatter().parse(m) if f is not None}
        have = {f for _, f, _, _ in string.Formatter().parse(tr) if f is not None}
        if want != have:
            bad.append((m, sorted(want), sorted(have)))
    if cmd == "update":
        for m in missing:
            strings.setdefault(m, "")
        cat.setdefault("_meta", {}).setdefault("name", code)
        with open(os.path.join(LOCALE_DIR, code + ".json"), "w", encoding="utf-8") as f:
            json.dump(cat, f, ensure_ascii=False, indent=1)
            f.write("\n")
    print(f"{code}: строк в игре {len(ids)}, переведено {len(ids) - len(missing)}, нет перевода {len(missing)}, "
          f"лишних {len(unused)}, с неверными плейсхолдерами {len(bad)}")
    for m in missing[:40]:
        print("  нет:", m[:100], " ", ids[m][0])
    for m, w, h in bad[:40]:
        print("  плейсхолдеры:", m[:80], w, "->", h)
    return 0 if code == SOURCE_LANG or not (missing or bad) else 2


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
