"""Ускорение движка Ursina (без изменения самой библиотеки) — применяется в main.py до создания окна.

Замеры показали, что больше половины времени кадра уходило не на игру и не на рисование, а на служебный код Ursina:

* Entity.children перебирает ВСЕ сущности сцены (~10 тыс.), а destroy() зовёт его для каждого потомка
  и ещё ищет каждого в общем списке — уничтожение одной надписи стоило сотни тысяч проверок.
  → реестр «родитель → дети» и уничтожение с одним проходом по списку сцены.
* Каждый кадр Ursina обходит все ~4 тыс. включённых сущностей, чтобы найти 4–5 с методом update().
  → список «у кого есть update/скрипты» пересобирается только при появлении/удалении сущностей.
* Мышь каждый кадр бросает луч в весь мир и интерфейс (наведение на объекты) — в игре это не используется.
* Text.get_width создаёт и тут же уничтожает временную надпись — интерфейс звал его каждый кадр.
  → ширина считается одним TextNode, результаты кэшируются.
"""
from panda3d.core import TextNode

_KIDS = {}            # id(родителя) -> [дети]
_STATE = {"version": 0}


def _unlink(child, parent):
    if parent is None:
        return
    lst = _KIDS.get(id(parent))
    if lst:
        try:
            lst.remove(child)
        except ValueError:
            pass


def children_of(ent):
    return [c for c in _KIDS.get(id(ent), ()) if c.__dict__.get("_parent") is ent and not c.__dict__.get("_perf_dead")]


def apply():
    import ursina
    from ursina import entity as entity_mod, ursinastuff, scene, application
    from ursina.entity import Entity
    Ent = Entity

    # ------------------------------------------------------------ родитель/дети
    prop = Ent.parent

    def _set_parent(self, value):
        old = self.__dict__.get("_parent")
        if old is not value:
            _unlink(self, old)
            if value is not None:
                _KIDS.setdefault(id(value), []).append(self)
        prop.fset(self, value)

    Ent.parent = property(prop.fget, _set_parent)
    _reparent = Ent.reparent_to

    def reparent_to(self, entity):
        old = self.__dict__.get("_parent")
        if old is not entity:
            _unlink(self, old)
            if entity is not None:
                _KIDS.setdefault(id(entity), []).append(self)
        _reparent(self, entity)

    Ent.reparent_to = reparent_to
    Ent.children = property(children_of)

    # ------------------------------------------------------------ быстрое уничтожение
    def _destroy_rec(entity, force_destroy, dead):
        from ursina import camera
        if not entity or entity is camera:
            return
        if entity.eternal and not force_destroy:
            return
        if hasattr(entity, "stop"):
            entity.stop(False)
        if hasattr(entity, "on_destroy"):
            entity.on_destroy()
        for c in children_of(entity):
            _destroy_rec(c, False, dead)
        entity.__dict__["_perf_dead"] = True
        dead.append(entity)
        if hasattr(entity, "scripts"):
            for s in entity.scripts:
                del s
        if hasattr(entity, "animations"):
            for anim in entity.animations:
                anim.finish()
                anim.kill()
        if hasattr(entity, "tooltip"):
            _destroy_rec(entity.tooltip, False, dead)
        if hasattr(entity, "_on_click") and isinstance(entity._on_click, ursinastuff.Sequence):
            entity._on_click.kill()
        try:
            entity.removeNode()
        except Exception:
            print("already destroyed")
        _unlink(entity, entity.__dict__.get("_parent"))
        _KIDS.pop(id(entity), None)

    def fast_destroy(entity, force_destroy=False):
        dead = []
        _destroy_rec(entity, force_destroy, dead)
        if dead:
            ids = {id(e) for e in dead}
            scene.entities[:] = [e for e in scene.entities if id(e) not in ids]
            _STATE["version"] += 1

    ursinastuff._destroy = fast_destroy
    try:
        import ursina.audio as _audio
        _audio._destroy = fast_destroy
    except Exception:
        pass

    # ------------------------------------------------------------ новые сущности → пересобрать список update
    _init = Ent.__init__

    def __init__(self, *a, **kw):
        _init(self, *a, **kw)
        _STATE["version"] += 1

    Ent.__init__ = __init__

    # ------------------------------------------------------------ цикл update только по тем, кому он нужен
    from direct.task import Task
    from ursina import mouse, time as utime
    import __main__
    from panda3d.core import ClockObject
    clock = ClockObject.getGlobalClock()
    cache = {"version": -1, "list": [], "frame": 0}

    def _candidates():
        out = []
        for e in scene.entities:
            d = e.__dict__
            if d.get("_perf_dead"):
                continue
            if callable(getattr(e, "update", None)) or d.get("scripts"):
                out.append(e)
        return out

    def _update(self, task):
        utime.dt = clock.getDt() * application.time_scale
        mouse.update()
        if hasattr(__main__, "update") and __main__.update and not application.paused:
            __main__.update()
        for seq in application.sequences:
            seq.update()
        cache["frame"] += 1
        # пересборка — при появлении/удалении сущностей и раз в секунду (вдруг кому-то присвоили update позже)
        if cache["version"] != _STATE["version"] or cache["frame"] % 60 == 0:
            cache["list"] = _candidates()
            cache["version"] = _STATE["version"]
        paused = application.paused
        for entity in cache["list"]:
            if entity.enabled is False or entity.ignore or entity.__dict__.get("_perf_dead"):
                continue
            if paused and entity.ignore_paused is False:
                continue
            upd = getattr(entity, "update", None)
            if upd is not None and callable(upd):
                upd()
            scripts = entity.__dict__.get("scripts")
            if scripts:
                for script in scripts:
                    if script.enabled and hasattr(script, "update") and callable(script.update):
                        script.update()
        return Task.cont

    ursina.Ursina._update = _update

    # ------------------------------------------------------------ ширина текста без временных надписей
    from ursina.text import Text
    measure = {"node": None, "font": None, "cache": {}}

    def get_width(string, font=None):
        if font is not None:                       # редкий случай — как раньше
            t = Text(string)
            t.font = font
            w = t.width
            fast_destroy(t)
            return w
        c = measure["cache"]
        w = c.get(string)
        if w is None:
            if measure["node"] is None or measure["font"] != Text.default_font:
                tmp = Text("")
                measure["node"] = TextNode("perf_measure")
                measure["node"].setFont(tmp._font)
                measure["font"] = Text.default_font
                fast_destroy(tmp)
                c.clear()
            tn = measure["node"]
            import fonts
            w = max(fonts.measure(line, tn) for line in str(string).split("\n")) * Text.size
            if len(c) > 4000:
                c.clear()
            c[string] = w
        return w

    Text.get_width = staticmethod(get_width)


def tune_after_start():
    """Настройки, которые можно применить только после создания окна."""
    from ursina import mouse
    mouse.update_step = 10 ** 9          # не бросать луч наведения каждый кадр (в игре мышь — только обзор)
    mouse.traverse_target = None
