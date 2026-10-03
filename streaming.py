"""Подгрузка мира вокруг игрока.

Большие меши карты (дома, деревья, снег, парковки...) нарезаны на квадраты CHUNK×CHUNK м.
Квадрат рисуется, только если он ближе VIEW_DIST к игроку; при приближении — включается снова.
Карта при этом существует целиком (ничего не удаляется), просто дальние части не рисуются.

Group ведёт себя как обычная сущность: group.enabled = False прячет всё (квартира, подземка, ночь/день),
а внутри включённой группы видны только ближние квадраты.
"""
import math

from ursina import Entity, Mesh

from config import VIEW_DIST, CHUNK
from mesh3d import MeshBuilder, split_chunks

GROUPS = []
_player = [0.0, 0.0]
HYST = 15.0            # м: запас, чтобы квадраты не мигали на границе


class Group:
    def __init__(self, name=""):
        self.name = name
        self.items = []            # [сущность, x, y, радиус, видна_ли]
        self._on = True
        GROUPS.append(self)

    def add(self, ent, x, y, r):
        # статичная геометрия: движку не нужно звать её update() каждый кадр
        stack = [ent]
        while stack:
            e_ = stack.pop()
            e_.ignore = True
            stack.extend(getattr(e_, "children", []))
        item = [ent, x, y, r, None]
        self.items.append(item)
        self._apply(item)
        return ent

    def _apply(self, item, force=False):
        ent, x, y, r, vis = item
        d = math.hypot(x - _player[0], y - _player[1]) - r
        lim = VIEW_DIST + (HYST if vis else 0.0)
        want = self._on and d < lim
        if want != vis or force:
            item[4] = want
            ent.enabled = want

    @property
    def enabled(self):
        return self._on

    @enabled.setter
    def enabled(self, v):
        v = bool(v)
        if v != self._on:
            self._on = v
            for it in self.items:
                self._apply(it, force=True)

    @property
    def entities(self):
        return [it[0] for it in self.items]

    def visible_count(self):
        return sum(1 for it in self.items if it[4])


def mesh_group(mb, name="", with_uvs=False, setup=None, **kw):
    """Нарезать MeshBuilder на квадраты и сделать из них группу. setup(entity) — доп. настройка (свечение и т.п.)."""
    g = Group(name)
    parts, big = split_chunks(mb, CHUNK)
    for key, sub in list(parts.items()) + ([("big", big)] if len(big) else []):
        m = Mesh(vertices=sub.v, triangles=sub.t, colors=sub.c, normals=sub.n,
                 uvs=sub.uv if (with_uvs or sub.uv_tile) else None)
        e = Entity(model=m, **kw)
        if setup:
            setup(e)
        if key == "big":
            xs = [v[0] for v in sub.v]
            zs = [-v[2] for v in sub.v]
            cx, cy = (min(xs) + max(xs)) / 2, (min(zs) + max(zs)) / 2
            r = math.hypot(max(xs) - min(xs), max(zs) - min(zs)) / 2 + 1e6   # крупное — всегда
        else:
            cx, cy = (key[0] + 0.5) * CHUNK, (key[1] + 0.5) * CHUNK
            r = CHUNK * 0.75
        g.add(e, cx, cy, r)
    return g


def point_group(ent, x, y, r=5.0, name=""):
    """Отдельный объект (вывеска, ворота) — виден в пределах дальности."""
    g = Group(name)
    g.add(ent, x, y, r)
    return g


def update(px, py):
    """Вызывать несколько раз в секунду: включает ближние квадраты, выключает дальние."""
    _player[0], _player[1] = px, py
    for g in GROUPS:
        if not g._on:
            continue
        for it in g.items:
            g._apply(it)


def stats():
    tot = sum(len(g.items) for g in GROUPS)
    vis = sum(g.visible_count() for g in GROUPS)
    return vis, tot
