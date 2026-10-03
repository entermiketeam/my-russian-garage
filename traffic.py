"""Дорожное движение Kleinbruck: граф дорог, светофоры, водители на настоящей физике, пешеходы.

Машины трафика — обычные car.Car (свои модель, масса, мотор, КПП, шины, электрика). Водитель (Driver) каждый кадр
решает, куда рулить (преследование точки на своей полосе), газ/тормоз (модель IDM: дистанция до впереди идущего,
светофоры, уступить дорогу, пешеходы на переходе, повороты) и какую передачу включить — и отдаёт это в Car.update,
как игрок с клавиатуры. Ближе PHYS_DIST к игроку — полная физика, дальше — упрощённое движение по тем же полосам
(машины не исчезают, просто считаются дешевле).

Правила: правостороннее движение; на 4 крестообразных перекрёстках — светофоры (фазы: ось «запад–восток» / «север–юг»,
жёлтый, «все красные»); на Т-перекрёстке у Ringstraße второстепенная уступает; поворачивающий налево уступает
встречным; все уступают пешеходам на переходе. Обгон — по встречной, только когда она свободна и до перекрёстка
далеко; на автобане — по левой полосе.
"""
import math
import random

from world import ROADS, BUILDINGS, point_in
from i18n import T

PHYS_DIST = 160.0          # ближе — полная физика Car.update
SIM_RATE_FAR = 0.1         # дальше — упрощённое движение раз в 0.1 с
LANE = {"town": 2.5, "land": 2.6, "autobahn": 8.0}
LANE_FAST = 4.5            # левая полоса автобана
JN = 7.5                   # полуразмер перекрёстка (центр → край)
JT = 10.0                  # где начинается/кончается дуга поворота (от центра) — радиус, который машина реально проходит
CYCLE = [("h", "green", 18.0), ("h", "yellow", 3.0), ("-", "red", 2.0),
         ("v", "green", 18.0), ("v", "yellow", 3.0), ("-", "red", 2.0)]


def _ang_diff(a, b):
    return (a - b + math.pi) % (2 * math.pi) - math.pi


# ======================================================================== дорожный граф
class Road:
    def __init__(self, r):
        x, y, w, h, kind, name, lim = r
        self.rect, self.kind, self.name = (x, y, w, h), kind, name
        self.limit = lim or 130
        self.horiz = w > h
        self.c = y + h / 2 if self.horiz else x + w / 2          # координата осевой
        self.a, self.b = (x, x + w) if self.horiz else (y, y + h)
        self.half = h / 2 if self.horiz else w / 2

    def point(self, s):
        return (s, self.c) if self.horiz else (self.c, s)


class Node:
    def __init__(self, i, x, y):
        self.i, self.x, self.y = i, x, y
        self.edges = []            # исходящие рёбра
        self.light = None          # светофор
        self.major = None          # «главная» ось для нерегулируемого Т-перекрёстка ("h"/"v")

    @property
    def degree(self):
        return len(self.edges)


class Edge:
    def __init__(self, a, b, road):
        self.a, self.b, self.road = a, b, road
        dx, dy = b.x - a.x, b.y - a.y
        self.len = math.hypot(dx, dy) or 1.0
        self.dx, self.dy = dx / self.len, dy / self.len
        self.rx, self.ry = -self.dy, self.dx                      # вправо по ходу
        self.axis = "h" if abs(dx) > abs(dy) else "v"
        self.back = None

    @property
    def heading(self):
        return math.atan2(self.dy, self.dx)


class Graph:
    def __init__(self):
        roads = [Road(r) for r in ROADS]
        self.roads = roads
        pts = []

        def add(x, y):
            for n in pts:
                if abs(n.x - x) < 9 and abs(n.y - y) < 9:
                    return n
            n = Node(len(pts), x, y)
            pts.append(n)
            return n
        on_road = {id(r): [] for r in roads}
        # пересечения осевых
        for i, r1 in enumerate(roads):
            for r2 in roads[i + 1:]:
                if r1.horiz == r2.horiz:
                    continue
                h, v = (r1, r2) if r1.horiz else (r2, r1)
                x, y = v.c, h.c
                if h.a - v.half - 1 <= x <= h.b + v.half + 1 and v.a - h.half - 1 <= y <= v.b + h.half + 1:
                    n = add(x, y)
                    on_road[id(h)].append((x, n))
                    on_road[id(v)].append((y, n))
        # концы дорог (тупики и стыки одной линии)
        for r in roads:
            for s in (r.a, r.b):
                x, y = r.point(s)
                # конец дороги у края широкой поперечной (автобан) — это тот же перекрёсток, а не отдельный тупик
                if not any(abs(s - s2) < r.half + 14 for s2, _ in on_road[id(r)]):
                    n = add(x, y)
                    on_road[id(r)].append((s, n))
        self.nodes = pts
        self.edges = []
        for r in roads:
            lst = sorted(on_road[id(r)], key=lambda t: t[0])
            seen = []
            for s, n in lst:
                if not seen or seen[-1] is not n:
                    seen.append(n)
            for a, b in zip(seen, seen[1:]):
                e1, e2 = Edge(a, b, r), Edge(b, a, r)
                e1.back, e2.back = e2, e1
                a.edges.append(e1)
                b.edges.append(e2)
                self.edges += [e1, e2]
        # светофоры — на крестовинах (4 направления) в городе
        self.lights = []
        for n in pts:
            axes = {e.axis for e in n.edges}
            if n.degree >= 4 and all(e.road.kind == "town" for e in n.edges):
                n.light = TrafficLight(n, len(self.lights))
                self.lights.append(n.light)
            elif n.degree == 3 and len(axes) == 2:
                cnt = {"h": 0, "v": 0}
                for e in n.edges:
                    cnt[e.axis] += 1
                n.major = "h" if cnt["h"] >= cnt["v"] else "v"

    def nearest_edge(self, x, y):
        best, bd = None, 1e9
        for e in self.edges:
            ax, ay = e.a.x, e.a.y
            t = max(0.0, min(e.len, (x - ax) * e.dx + (y - ay) * e.dy))
            px, py = ax + e.dx * t, ay + e.dy * t
            side = (x - px) * e.rx + (y - py) * e.ry
            d = math.hypot(x - px, y - py) + (0 if side >= 0 else 3.0)       # предпочесть «свою» сторону
            if d < bd:
                best, bd = (e, t), d
        return best


class TrafficLight:
    def __init__(self, node, i):
        self.node = node
        self.offset = i * 11.0                                      # перекрёстки не синхронны

    def phase(self, t):
        total = sum(c[2] for c in CYCLE)
        tt = (t + self.offset) % total
        for axis, st, d in CYCLE:
            if tt < d:
                return axis, st, d - tt
            tt -= d
        return "-", "red", 1.0

    def state(self, axis, t):
        """Для машин с оси axis: green / yellow / red."""
        ax, st, _ = self.phase(t)
        if ax == axis:
            return st
        return "red"

    def walk(self, crossing_axis, t):
        """Пешеходу можно переходить дорогу оси crossing_axis, когда у неё красный, а у другой — зелёный."""
        ax, st, left = self.phase(t)
        return ax != "-" and ax != crossing_axis and st == "green" and left > 4.0


# ======================================================================== путь по полосам
class Path:
    """Очередь точек пути: (x, y, nx, ny, fixed, vmax, edge). fixed — точка поворота (смещение полосы не применяется)."""

    def __init__(self):
        self.pts = []

    def extend_edge(self, e, off, t0=0.0):
        step = 4.0
        s = max(t0, JT if e.a.degree > 1 else 0.0)
        end = e.len - (JT if e.b.degree > 1 else 3.0)
        while s < end:
            self.pts.append((e.a.x + e.dx * s, e.a.y + e.dy * s, e.rx, e.ry, None, e.road.limit / 3.6, e))
            s += step

    def extend_turn(self, e_in, e_out, off_in, off_out):
        n = e_in.b
        if e_out is e_in.back:                                   # разворот в тупике: широкая петля R=6 м за концом дороги
            R = 6.0
            cx, cy = n.x + e_in.dx * 4, n.y + e_in.dy * 4
            self.pts.append((n.x + e_in.rx * (off_in + 1.5), n.y + e_in.ry * (off_in + 1.5), 0, 0, True, 4.0, e_out))
            for k in range(0, 13):
                a = -math.pi / 2 + math.pi * k / 12              # справа → вперёд → слева (поворот налево)
                ox = -e_in.rx * math.sin(a) * R + e_in.dx * math.cos(a) * R
                oy = -e_in.ry * math.sin(a) * R + e_in.dy * math.cos(a) * R
                self.pts.append((cx + ox, cy + oy, 0, 0, True, 4.0, e_out))
            self.pts.append((n.x - e_in.rx * off_in, n.y - e_in.ry * off_in, 0, 0, True, 5.0, e_out))
            return
        r_in = JT if n.degree > 1 else 3.0
        p0 = (n.x - e_in.dx * r_in + e_in.rx * off_in, n.y - e_in.dy * r_in + e_in.ry * off_in)
        p2 = (n.x + e_out.dx * JT + e_out.rx * off_out, n.y + e_out.dy * JT + e_out.ry * off_out)
        straight = abs(_ang_diff(e_in.heading, e_out.heading)) < 0.3
        # контрольная точка — пересечение линий полос (для поворота), середина — для прямо
        if straight:
            c = ((p0[0] + p2[0]) / 2, (p0[1] + p2[1]) / 2)
        else:
            c = (n.x + e_in.rx * off_in + e_out.rx * off_out, n.y + e_in.ry * off_in + e_out.ry * off_out)
            # для поворота налево контрольная точка — дальше по ходу (широкая дуга через центр)
        v = 22 / 3.6 if not straight else min(e_in.road.limit, e_out.road.limit) / 3.6
        right = _ang_diff(e_out.heading, e_in.heading) > 0.3            # в экранных осях y вниз: + — направо
        if not straight and not right:
            v = 20 / 3.6
        elif not straight:
            v = 15 / 3.6
        for k in range(1, 9):
            t = k / 8
            x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * c[0] + t * t * p2[0]
            y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * c[1] + t * t * p2[1]
            self.pts.append((x, y, 0, 0, True, v, e_out))


# ======================================================================== водители
PROFILES = {
    # скорость к ограничению, резвость газа, дистанция (с), порог обгона, агрессия
    "calm":   dict(vk=(0.88, 1.0), thr=0.55, T=1.6, s0=3.5, overtake=0.55, amber=0.0, a=1.6),
    "normal": dict(vk=(0.95, 1.08), thr=0.7, T=1.3, s0=3.0, overtake=0.7, amber=0.2, a=2.0),
    "racer":  dict(vk=(1.45, 1.9), thr=1.0, T=0.7, s0=2.2, overtake=0.9, amber=0.9, a=4.5),
    "police": dict(vk=(0.95, 1.0), thr=0.7, T=1.5, s0=3.5, overtake=0.6, amber=0.0, a=2.2),
}
NORMAL_MODELS = ["golf", "kadett", "w123", "audi80", "volvo240", "taunus", "bmw_e21", "civic", "trabant",
                 "wartburg", "moskvich", "golf", "kadett", "audi80"]
RACER_MODELS = ["bmw_e21", "civic", "mustang", "golf", "w123"]
COLORS = [(200, 200, 205), (40, 60, 120), (150, 20, 20), (30, 30, 30), (230, 210, 60), (60, 110, 60),
          (170, 170, 175), (110, 70, 40), (220, 220, 215), (90, 30, 30)]
RACER_COLORS = [(250, 200, 20), (20, 20, 20), (200, 30, 30), (30, 90, 200), (240, 240, 240)]


class Driver:
    def __init__(self, traffic, car, profile, rng, edge, t0=0.0, police=False, name=""):
        self.tr = traffic
        self.car = car
        car._driver = self
        Driver._n = getattr(Driver, "_n", 0) + 1
        self.idx = Driver._n
        self.profile = profile
        self.P = PROFILES[profile]
        self.rng = rng
        self.police = police
        self.name = name
        self.vk = rng.uniform(*self.P["vk"])
        self.path = Path()
        self.edge = edge
        self.off = self._lane(edge)
        self.off_target = self.off
        self.path.extend_edge(edge, self.off, t0)
        self.next_edge = None
        self.inp = {}
        self.siren = 0.0
        self.stuck = 0.0
        self.overtake_t = 0.0
        self.passing = None
        self.fallback = None
        self.still_t = 0.0
        self.blocker = None
        self.block_t = 0.0
        self.phys = False
        self.far_acc = 0.0
        self.wait_t = 0.0
        self.blocked_t = 0.0
        self.color = car.color
        self.leaving = None
        self.last_fixed = False
        self.gk = 1.0             # как держит дорога (снег, лёд, мокро) — водитель едет по погоде

    # --- интерфейс «старого» AI (полиция, столкновения, 2D-карта)
    @property
    def x(self):
        return self.car.x

    @x.setter
    def x(self, v):
        self.car.x = v

    @property
    def y(self):
        return self.car.y

    @y.setter
    def y(self, v):
        self.car.y = v

    @property
    def angle(self):
        return self.car.angle

    @angle.setter
    def angle(self, v):
        self.car.angle = v

    @property
    def speed(self):
        return self.car.speed

    @speed.setter
    def speed(self, v):
        self.car.speed = v

    def _lane(self, e):
        return LANE.get(e.road.kind, 2.5)

    # --- путь
    def _choose_next(self, e):
        n = e.b
        outs = [o for o in n.edges if o is not e.back]
        if not outs:
            self.leaving = e                                      # тупик = выезд из города: уедет и вернётся с другого края
            return e.back
        # к выезду из города, рядом с которым игрок, не сворачиваем (там машину было бы видно «исчезающей»)
        pc = self.tr.center
        ok = [o for o in outs if not (o.b.degree == 1 and abs(o.b.x - pc[0]) + abs(o.b.y - pc[1]) < 260)]
        outs = ok or outs
        if self.profile == "racer":
            straight = [o for o in outs if abs(_ang_diff(o.heading, e.heading)) < 0.3]
            if straight and self.rng.random() < 0.75:
                return straight[0]
        return self.rng.choice(outs)

    def _refill(self):
        # держим впереди путь не короче, чем нужно, чтобы вовремя затормозить перед поворотом
        need = max(18, int((abs(self.car.speed) ** 2 / (2 * 3.0) + 40) / 4))
        while len(self.path.pts) < need:
            last_e = self.path.pts[-1][6] if self.path.pts else self.edge
            if self.next_edge is None or self.next_edge is last_e:
                nxt = self._choose_next(last_e)
                off_in = self._lane(last_e)
                if last_e.road.kind == "autobahn" and self._left_turn(last_e, nxt):
                    off_in = LANE_FAST                            # налево с автобана — из левой полосы
                off_out = self._lane(nxt)
                self.path.extend_turn(last_e, nxt, off_in, off_out)
                self.path.extend_edge(nxt, off_out)
                self.next_edge = None
            else:
                break

    def _advance_path(self):
        """Выбросить точки, которые машина миновала — по направлению самого пути (не капота: в повороте/заносе
        капот смотрит в сторону), не больше нескольких за кадр."""
        c = self.car
        pts = self.path.pts
        for _ in range(6):
            if not pts:
                break
            x0, y0 = self._pt(pts[0])
            if len(pts) > 1:
                x1, y1 = self._pt(pts[1])
            else:
                x1, y1 = x0 + math.cos(c.angle), y0 + math.sin(c.angle)
            L = math.hypot(x1 - x0, y1 - y0) or 1.0
            proj = ((c.x - x0) * (x1 - x0) + (c.y - y0) * (y1 - y0)) / L
            if proj > -0.5 or math.hypot(c.x - x0, c.y - y0) < 2.0:
                p = pts.pop(0)
                self.edge = p[6]
                self.last_fixed = bool(p[4])                      # True — уже внутри перекрёстка
            else:
                break
        self._refill()

    def _pt(self, p):
        if p[4]:
            return p[0], p[1]
        return p[0] + p[2] * self.off, p[1] + p[3] * self.off

    def _target(self, look):
        c = self.car
        acc = 0.0
        px, py = c.x, c.y
        for p in self.path.pts:
            x, y = self._pt(p)
            acc += math.hypot(x - px, y - py)
            px, py = x, y
            if acc >= look:
                return x, y
        if self.path.pts:
            return self._pt(self.path.pts[-1])
        return c.x + math.cos(c.angle) * look, c.y + math.sin(c.angle) * look

    # --- чего ждать впереди
    def _limit_ahead(self, reach=200.0):
        """Минимальная скорость, которую требуют повороты впереди (с учётом торможения)."""
        c = self.car
        v = 99.0
        acc = 0.0
        px, py = c.x, c.y
        for p in self.path.pts:
            x, y = self._pt(p)
            acc += math.hypot(x - px, y - py)
            px, py = x, y
            if acc > reach:
                break
            vmax = p[5] * (self.vk if not p[4] else (1.0 if self.profile != "racer" else 1.2))
            if p[4]:
                vmax *= 0.45 + 0.55 * self.gk                     # на снегу/льду в поворот — заметно медленнее
            v = min(v, math.sqrt(vmax * vmax + 2 * 2.8 * self.gk * max(0.0, acc - 4.0)))
        return v

    def _stop_point(self, t):
        """Расстояние до места, где надо остановиться (светофор, уступить), или None."""
        c = self.car
        e = self.edge
        acc = 0.0
        px, py = c.x, c.y
        # последняя пройденная точка — на дороге: следующая «поворотная» точка = въезд на перекрёсток этого ребра
        cur_e = None if self.last_fixed else self.edge
        for p in self.path.pts[:20]:
            x, y = self._pt(p)
            acc += math.hypot(x - px, y - py)
            px, py = x, y
            pe = p[6]
            if p[4] and cur_e is not None:                       # первая точка поворота = въезд на перекрёсток
                n = cur_e.b
                if n.degree == 1:
                    return acc + 2.0                              # выезд из города — дальше не едем, ждём у края
                d = acc - 1.0
                if n.light is not None:
                    st = n.light.state(cur_e.axis, t)
                    if st == "red":
                        return d
                    if st == "yellow":
                        v = abs(c.speed)
                        can_stop = v * v / (2 * (4.0 if self.profile != "racer" else 6.5)) < d - 2
                        if can_stop:
                            return d
                    # зелёный: налево — уступить встречным
                    if self._left_turn(cur_e, pe) and self._oncoming_near(cur_e, 45):
                        return d
                elif n.major is not None and cur_e.axis != n.major:
                    if self._cross_traffic(n, 55):
                        return d
                elif n.major is not None and self._left_turn(cur_e, pe) and self._oncoming_near(cur_e, 60):
                    return d                                      # с главной налево — пропустить встречных
                if self._peds_on_turn(n, cur_e, pe):
                    return d
                return None
            if not p[4]:
                cur_e = pe
            if acc > 70:
                break
        return None

    def at_red(self, t):
        """Стоит перед красным своего светофора (это не пробка, а нормальное ожидание)."""
        n = self.edge.b
        return n.light is not None and n.light.state(self.edge.axis, t) != "green" \
            and math.hypot(self.x - n.x, self.y - n.y) < 80

    def _left_turn(self, e_in, e_out):
        return _ang_diff(e_out.heading, e_in.heading) < -0.3

    def _oncoming_near(self, e_in, dist):
        n = e_in.b
        # встречные едут к узлу по ребру, обратному нашему «прямо»
        ahead = [o for o in n.edges if abs(_ang_diff(o.heading, e_in.heading)) < 0.3]
        opp = [o.back for o in ahead]
        for d in self.tr.drivers:
            if d is self:
                continue
            if d.edge in opp and math.hypot(d.x - n.x, d.y - n.y) < dist and abs(d.speed) > 1:
                return True
        return False

    def _cross_traffic(self, n, dist):
        """Есть ли на главной дороге кто-то, кто подъедет к узлу раньше, чем мы его проедем (≈6 с), или уже в нём."""
        for d in self.tr.drivers:
            if d is self:
                continue
            dd = math.hypot(d.x - n.x, d.y - n.y)
            moving = abs(d.speed) > 1.0
            if dd < (12 if moving else JN - 1.0):
                return True                                           # кто-то прямо на перекрёстке
            if not moving:
                continue                                              # стоящие у перекрёстка (ждут сами) — не помеха
            t_need = 8.0 if d.edge.road.kind == "autobahn" else 6.0      # на автобан вливаются с запасом
            if d.edge.b is n and d.edge.axis == n.major and (dd < dist or dd / max(1.0, abs(d.speed)) < t_need):
                return True
        for pc in self.tr.player_cars:
            dd = math.hypot(pc.x - n.x, pc.y - n.y)
            if dd < 12 or (abs(pc.speed) > 1.5 and (dd < dist or dd / abs(pc.speed) < 6.0)):
                return True
        return False

    def _peds_on_turn(self, n, e_in, e_out):
        for p in self.tr.peds.near(n.x, n.y, 16):
            if p.crossing and not p.waiting and p.cross_node is n and not p.down:
                return True
        return False

    def _leader(self, look=None):
        """(расстояние по пути, скорость вдоль пути, объект) ближайшего препятствия на своей траектории:
        машины трафика, машины игрока, пешеходы на проезжей части. Смотрит вдоль точек пути (и в повороте)."""
        c = self.car
        v = abs(c.speed)
        look = look or max(45.0, v * 4.0 + 10)
        # точки пути вперёд (с накопленным расстоянием)
        pts = []
        acc = 0.0
        px, py = c.x, c.y
        pts.append((px, py, 0.0, math.cos(c.angle), math.sin(c.angle)))
        for p in self.path.pts:
            x, y = self._pt(p)
            seg = math.hypot(x - px, y - py)
            if seg < 0.01:
                continue
            acc += seg
            pts.append((x, y, acc, (x - px) / seg, (y - py) / seg))
            px, py = x, y
            if acc > look:
                break
        best = None
        cands = [d.car for d in self.tr.near_drivers(c.x, c.y, look) if d is not self] + self.tr.player_cars
        for o in cands:
            if abs(o.x - c.x) > look or abs(o.y - c.y) > look:
                continue
            ol = getattr(o, "length", 4.2)
            for (x, y, s_, dx, dy) in pts:
                ox, oy = o.x - x, o.y - y
                along = ox * dx + oy * dy
                lat = -ox * dy + oy * dx
                if abs(lat) < 2.3 and -3.0 < along < 5.0 and s_ + along > 0.5:
                    gap = s_ + along - (c.length + ol) / 2
                    vo = o.speed * math.cos(_ang_diff(o.angle, math.atan2(dy, dx)))
                    if best is None or gap < best[0]:
                        best = (gap, vo, o)
                    break
        for pd in self.tr.peds.near(c.x, c.y, 30):
            if pd.down:
                continue
            for (x, y, s_, dx, dy) in pts[:8]:
                ox, oy = pd.x - x, pd.y - y
                along = ox * dx + oy * dy
                lat = -ox * dy + oy * dx
                if abs(lat) < 2.4 and -3.0 < along < 5.0 and s_ + along > 0:
                    gap = s_ + along - c.length / 2 - 1.5
                    if best is None or gap < best[0]:
                        best = (gap, 0.0, pd)
                    break
        return best

    def _oncoming_clear(self, dist, need_t=9.0):
        """Свободна ли встречная для обгона: ни одна встречная машина не встретится с нами раньше need_t секунд
        и ближе dist метров."""
        c = self.car
        fx, fy = math.cos(c.angle), math.sin(c.angle)
        v = abs(c.speed)
        look = max(dist, (v + 30) * need_t)
        for d in self.tr.near_drivers(c.x, c.y, look + 10):
            if d is self:
                continue
            ox, oy = d.x - c.x, d.y - c.y
            ahead = ox * fx + oy * fy
            side = -ox * fy + oy * fx
            if -8 < ahead < look and side < 1.5 and math.cos(_ang_diff(d.angle, c.angle)) < 0:
                meet = ahead / max(1.0, v + abs(d.speed))
                if ahead < dist or meet < need_t:
                    return False
        for pc in self.tr.player_cars:
            ox, oy = pc.x - c.x, pc.y - c.y
            ahead = ox * fx + oy * fy
            if -8 < ahead < look and abs(-ox * fy + oy * fx) < 6:
                if ahead < dist or ahead / max(1.0, v + abs(pc.speed)) < need_t:
                    return False
        return True

    def _turn_left_ahead(self, dist):
        """Впереди (не дальше dist) поворот налево с автобана."""
        if self.edge.road.kind != "autobahn":
            return False
        c = self.car
        acc = 0.0
        px, py = c.x, c.y
        for p in self.path.pts:
            x, y = self._pt(p)
            acc += math.hypot(x - px, y - py)
            px, py = x, y
            if acc > dist:
                return False
            if p[4]:
                return p[5] < 8.0 and self._left_turn(self.edge, p[6])
        return False

    def _lane_clear(self, off_new):
        """Полоса со смещением off_new свободна рядом и сзади (с учётом того, кто догоняет)."""
        c = self.car
        e = self.edge
        v = abs(c.speed)
        fx, fy = math.cos(c.angle), math.sin(c.angle)
        others = [d.car for d in self.tr.near_drivers(c.x, c.y, 90) if d is not self] + self.tr.player_cars
        for o in others:
            if math.cos(o.angle - c.angle) < 0.8:
                continue                                          # встречные и поперечные — не в нашей полосе
            o_off = (o.x - e.a.x) * e.rx + (o.y - e.a.y) * e.ry
            if abs(o_off - off_new) > 2.2:
                continue
            rel = (o.x - c.x) * fx + (o.y - c.y) * fy
            behind = max(8.0, (abs(o.speed) - v) * 4.0 + 8.0)
            if -behind < rel < 10.0 + v * 0.3:
                return False
        return True

    def _dist_to_turn(self):
        """Расстояние по пути до начала следующей дуги поворота (None — впереди прямо)."""
        c = self.car
        acc = 0.0
        px, py = c.x, c.y
        for p in self.path.pts[:30]:
            x, y = self._pt(p)
            acc += math.hypot(x - px, y - py)
            px, py = x, y
            if p[4] and p[5] < 8.0:                               # дуга поворота (не «прямо через перекрёсток»)
                return acc
        return None

    def _junction_within(self, dist):
        acc = 0.0
        c = self.car
        px, py = c.x, c.y
        for p in self.path.pts:
            x, y = self._pt(p)
            acc += math.hypot(x - px, y - py)
            px, py = x, y
            if p[4]:
                return True
            if acc > dist:
                return False
        return False

    def _off_road(self):
        c = self.car
        for r in self.tr.graph.roads:
            x, y, w, h = r.rect
            if x - 4 <= c.x <= x + w + 4 and y - 4 <= c.y <= y + h + 4:
                return False
        return True

    def replan(self):
        """Потерял полосу (съехал, развернуло) — путь заново от ближайшей точки своей полосы."""
        c = self.car
        e, t0 = self.tr.graph.nearest_edge(c.x, c.y)
        self.edge = e
        self.path = Path()
        self.path.extend_edge(e, self._lane(e), max(0.0, t0))
        self.next_edge = None
        self.passing = None
        self.fallback = None
        self.off = self.off_target = self._lane(e)
        self.last_fixed = False
        self.leaving = None

    # --- решение
    def decide(self, dt, t):
        c = self.car
        P = self.P
        self.offroad_t = (getattr(self, "offroad_t", 0.0) + dt) if self._off_road() else 0.0
        if self.offroad_t > 1.0 and not getattr(self, "_replanned", False):
            self.replan()
            self._replanned = True
        elif self.offroad_t == 0.0:
            self._replanned = False
        self._advance_path()
        v = abs(c.speed)
        gk = self.gk
        # ограничение поворотов впереди меняется медленно — пересчёт раз в 0.1 с
        self._lim_t = getattr(self, "_lim_t", 0.0) - dt
        if self._lim_t <= 0.0 or getattr(self, "_lim", None) is None:
            self._lim = self._limit_ahead(min(200.0, v * v / (2 * 2.8 * max(0.35, gk)) + 40.0))
            self._lim_t = 0.1
        lim = self._lim
        v0 = min(lim, self.edge.road.limit / 3.6 * self.vk)
        v0 *= 0.5 + 0.5 * gk                                     # скользко — медленнее
        if self.profile == "racer":
            v0 = min(v0, 58.0 if self.edge.road.kind == "autobahn" else (41.0 if self.edge.road.kind == "land" else 20.0))
        if self.police and self.siren > 0:
            v0 = 0.0
        if self.offroad_t > 0:
            v0 = min(v0, 3.0)                                     # вне дороги — медленно назад на свою полосу
        # обгон / объезд
        self.overtake_t = max(0.0, self.overtake_t - dt)
        lead = self._leader()
        kind = self.edge.road.kind
        normal_off = self._lane(self.edge)
        if kind == "autobahn":
            target = self.off_target
            if self._turn_left_ahead(260):
                target = LANE_FAST                                # заранее в левую полосу, чтобы повернуть налево
            elif lead and lead[0] < max(40.0, v * 3.5) and lead[1] < v0 * P["overtake"] + 3:
                target = LANE_FAST
                self.overtake_t = 4.0
            elif self.overtake_t <= 0:
                target = normal_off
            # перестраиваются, только посмотрев в зеркало: соседняя полоса свободна
            if target != self.off_target and self._lane_clear(target):
                self.off_target = target
        else:
            slow = lead and lead[0] < 25 and (lead[1] < max(2.0, v0 * P["overtake"]))
            self.blocked_t = self.blocked_t + dt if slow else 0.0
            need = 2.0 if self.profile == "racer" else (4.0 if lead and abs(lead[1]) < 0.5 else 6.0)
            if slow and self.blocked_t > need and self.passing is None and self.fallback is None:
                # обгон начинают, только если успеют его закончить: хватает запаса скорости и прямой дороги
                dv = v0 - max(0.0, lead[1])
                pass_d = (lead[0] + 2 * c.length + 8) / max(0.5, dv) * v0 + 15
                if dv > (3.0 if self.profile == "racer" else 4.0) and pass_d < 160 and not self._junction_within(max(70.0, pass_d)) \
                        and self._oncoming_clear(max(110 if self.profile != "racer" else 70, pass_d)):
                    self.passing = lead[2]
                    self.off_target = -normal_off
            if self.passing is not None:
                o = self.passing
                fx, fy = math.cos(c.angle), math.sin(c.angle)
                past = ((o.x - c.x) * fx + (o.y - c.y) * fy) < -(c.length + 3)
                if past or self._junction_within(25) or not self._oncoming_clear(35):
                    self.passing = None
                    self.off_target = normal_off
                    self.blocked_t = 0.0
                    if not past:
                        self.fallback = o                   # не успел — отстать и встать позади, а не подрезать
            else:
                self.off_target = normal_off
        if self.fallback is not None:
            o = self.fallback
            fx, fy = math.cos(c.angle), math.sin(c.angle)
            ahead = (o.x - c.x) * fx + (o.y - c.y) * fy
            if ahead > c.length + 2.5 or ahead < -(c.length + 3) or math.hypot(o.x - c.x, o.y - c.y) > 40:
                self.fallback = None                        # уже позади него (или всё-таки впереди) — можно в свою полосу
            else:
                v0 = min(v0, max(0.0, abs(o.speed) - 3.0))
                if kind != "autobahn":
                    # ещё на встречке и встречных нет — подождать там, пока он проедет; иначе — сразу к себе
                    out = abs(self.off - normal_off) > 1.0 and self._oncoming_clear(35)
                    self.off_target = -normal_off if out else normal_off
        # плавная смена полосы (~2–3 с)
        rate = (3.5 if self.profile == "racer" else 1.6) * dt
        self.off += max(-rate, min(rate, self.off_target - self.off))
        # IDM (на скользком — мягче газ, дольше дистанция, тормозить раньше)
        a_max, b = P["a"] * (0.4 + 0.6 * gk), 3.0 * gk
        acc = a_max * (1 - (v / max(1.0, v0)) ** 4) if v0 > 0.1 else -b * 2
        if lead and not (self.passing is not None and lead[2] is self.passing):
            gap, vl, _ = lead
            s_star = P["s0"] * (2 - gk) + v * P["T"] / max(0.45, gk) + v * (v - vl) / (2 * math.sqrt(a_max * max(0.6, b)))
            acc -= a_max * (max(0.0, s_star) / max(0.5, gap)) ** 2
        sp = self._stop_point(t)
        if sp is not None:
            gap = sp - c.length / 2 - 1.5
            s_star = 1.0 + v * 1.0 + v * v / (2 * math.sqrt(a_max * b))
            acc = min(acc, -a_max * (max(0.0, s_star) / max(0.3, gap)) ** 2 + a_max * 0.3)
            if gap < 0.8:
                acc = min(acc, -6.0)
        # последний рубеж: кто-то прямо по курсу ближе, чем нужно для остановки — тормоз в пол
        fx, fy = math.cos(c.angle), math.sin(c.angle)
        stop_d = v * v / (2 * max(1.5, 5.0 * gk)) + 3.5 + c.length / 2
        # смотрят и по капоту, и туда, куда ведёт полоса (в повороте это разные стороны)
        px, py = self._target(8.0)
        pd = math.hypot(px - c.x, py - c.y)
        dirs = [(fx, fy)] + ([((px - c.x) / pd, (py - c.y) / pd)] if pd > 1.0 else [])
        reach = min(14.0 + (1.0 - gk) * 16.0, stop_d + 2)
        hw = c.spec["width"] / 2
        blocker = None
        creep = False
        for o in [dd.car for dd in self.tr.near_drivers(c.x, c.y, 30) if dd is not self] + self.tr.player_cars:
            ox, oy = o.x - c.x, o.y - c.y
            hit = False
            for ux, uy in dirs:
                ahead = ox * ux + oy * uy
                if not (-1.0 < ahead < reach):
                    continue
                # габариты другой машины поперёк нашего курса (стоит наискось — корма торчит в полосу)
                ca = abs(math.cos(o.angle) * ux + math.sin(o.angle) * uy)
                sa = math.sqrt(max(0.0, 1.0 - ca * ca))
                ext = sa * o.length / 2 + ca * o.spec["width"] / 2
                along = ca * o.length / 2 + sa * o.spec["width"] / 2
                if abs(-ox * uy + oy * ux) < hw + ext + 0.25 + ahead * 0.03 and 0 < ahead + along:
                    hit = True
                    break
            if hit:
                od = getattr(o, "_driver", None)
                if v < 0.5 and od is not None and abs(o.speed) < 0.5 and od.block_t > 3.0 and self.block_t > 3.0 \
                        and self.idx < od.idx and od.blocker is c:
                    creep = True                                  # оба стоят «нос к носу» — этот проезжает первым, шагом
                    continue
                acc = -9.0
                blocker = o
                break
        self.blocker = blocker
        self.block_t = (self.block_t + dt) if blocker is not None or creep else 0.0
        if creep and blocker is None:
            acc = min(acc, 1.0) if v < 1.5 else min(acc, -1.0)
        acc = max(-9.0, min(a_max, acc))
        # руль: преследование точки на полосе
        look = max(5.0, min(22.0, v * 0.9 + 3.0))
        dturn = self._dist_to_turn()
        if dturn is not None:
            look = min(look, max(4.5, 3.5 + dturn * 0.45))        # перед поворотом не «срезать» угол через тротуар
        tx, ty = self._target(look)
        alpha = _ang_diff(math.atan2(ty - c.y, tx - c.x), c.angle)
        L = c.spec["wheelbase"]
        delta = math.atan2(2 * L * math.sin(alpha), look)
        full = math.radians(c.sp("steer_max", 33))
        max_steer = full / (1 + max(0.0, v - 2) / 14) * ((0.55 + 0.45 * c.c("steering")) if c.has("steering") else 0.1)
        steer = max(-1.0, min(1.0, delta / max(0.05, max_steer)))
        # газ / тормоз / сцепление / передачи
        # занос: водитель ловит машину контррулём (руль в сторону заноса)
        beta = c.drift_angle
        if abs(beta) > 0.06 and v > 3:
            steer = max(-1.0, min(1.0, steer - beta * 2.2))
        thr = brk = 0.0
        if acc > 0.05:
            thr = min(P["thr"], acc / a_max * P["thr"] + 0.15)
            # газ дозируют: руль вывернут — меньше газа; зад пошёл или колёса буксуют — сбросить
            if v > 4.0:
                thr *= 0.35 + 0.65 * (1.0 - min(1.0, abs(steer)))
            else:
                thr = max(thr, 0.4)                               # трогаются уверенно, даже с вывернутым рулём
            if abs(beta) > 0.1 or c.spin_v > 1.5:
                thr *= 0.25
        elif acc < -0.3:
            # сколько тормоза даёт педаль у этой машины (эффективность колодок/жидкости), с запасом
            beff = (0.72 * min(1, c.c("brakes_f") * 4 + 0.15) + 0.28 * min(1, c.c("brakes_r") * 4 + 0.15))
            beff *= min(1.0, c.brake_fluid / 50.0 + 0.2) * c.sp("brake", 1.0)
            brk = min(1.0, -acc / max(2.0, 8.5 * beff * 0.85) + 0.05)
            if v > 3.0:
                brk = min(brk, 0.4 + 0.6 * gk)                    # на снегу/льду — не в пол (колёса не блокируют)
        clutch = False
        if c.gear <= 0:
            c.gear = 1
        cut = c.spec["cut"]
        up = cut * (0.92 if self.profile == "racer" else 0.62)
        if c.rpm > up and c.gear < c.max_gear and v > 3:
            c.gear += 1
        elif c.gear > 1 and c.rpm < 1500:
            c.gear -= 1
        if v < 2.0 and brk > 0:
            clutch = True
            c.gear = 1
        if v < 0.4 and thr <= 0:
            clutch = True
        self.inp = {"throttle": thr, "brake": brk, "steer": steer, "clutch": clutch}
        self.stuck = self.stuck + dt if (v < 0.3 and thr > 0.2) else 0.0
        return self.inp

    # --- дальний (упрощённый) режим: движение вдоль тех же точек
    def far_step(self, dt, t):
        c = self.car
        self._advance_path()
        lead = self._leader(25.0)                                 # дальний режим смотрит только на 20 м
        vv = abs(c.speed)
        v0 = min(self._limit_ahead(vv * vv / 12.0 + 25.0), self.edge.road.limit / 3.6 * self.vk)
        sp = self._stop_point(t)
        if sp is not None and sp < 25:
            v0 = min(v0, max(0.0, (sp - 3) * 0.6))
        if lead and lead[0] < 20:
            v0 = min(v0, max(0.0, lead[1], (lead[0] - 5) * 0.7))
        v = c.speed
        v += max(-6 * dt, min(2.5 * dt, v0 - v))
        c.speed = max(0.0, v)
        c.vlat = c.ang_vel = 0.0
        tx, ty = self._target(max(4.0, v * 0.6 + 3))
        ang = math.atan2(ty - c.y, tx - c.x)
        c.angle += _ang_diff(ang, c.angle) * min(1.0, dt * 4)
        c.x += math.cos(c.angle) * c.speed * dt
        c.y += math.sin(c.angle) * c.speed * dt
        c.running = True
        c.front_delta = 0.0


def _draw2d(self, surf, cam, t):
    """Для старой 2D-версии."""
    from world import AICar
    AICar.draw(self, surf, cam, t)


Driver.draw = _draw2d


# ======================================================================== трафик целиком
class Traffic:
    def __init__(self, world, n_cars=26, n_racers=3, n_peds=90, seed=1998):
        from car import Car
        import electrics, engine, keys
        self.world = world
        self.graph = Graph()
        self.t = 0.0
        self.drivers = []
        self.player_cars = []
        rng = random.Random(seed)
        edges = [e for e in self.graph.edges if e.len > 40]
        edges = edges + [e for e in edges if e.road.kind == "town"] * 2     # в городе машин больше, чем на трассах

        def make(model, color, profile, police=False, name=""):
            for _try in range(40):                                # не ставить машины друг в друга
                e = rng.choice(edges)
                t0 = rng.uniform(JT + 5, e.len - JT - 10)
                x_ = e.a.x + e.dx * t0
                y_ = e.a.y + e.dy * t0
                if all(math.hypot(d.x - x_, d.y - y_) > 25 for d in self.drivers):
                    break
            x = e.a.x + e.dx * t0 + e.rx * LANE.get(e.road.kind, 2.5)
            y = e.a.y + e.dy * t0 + e.ry * LANE.get(e.road.kind, 2.5)
            c = Car(model, x, y, e.heading, rng=random.Random(rng.randint(0, 10 ** 9)), pres=0.9)
            for sl in c.slots:
                c.parts[sl] = {"id": c.slots[sl][1], "cond": round(rng.uniform(65, 95), 1)}
            engine.init(c, base=c.parts["engine"]["cond"])
            electrics.clean(c)
            keys.ensure(c)
            c.hotwired = True                                    # водитель с ключом: заводится всегда
            c.fuel, c.oil, c.coolant, c.battery_charge = 30.0, c.oil_cap, c.coolant_cap, 90.0
            c.oil_quality, c.brake_fluid, c.temp = 90.0, 95.0, 85.0
            c.rust = {k: round(v * 0.3, 1) for k, v in c.rust.items()}
            c.dirt, c.snow, c.fade = 0.15, 0.0, 0.1
            c.color = color
            c.running = True
            c.gear = 2
            c.speed = 8.0
            c.traffic = True
            if profile == "racer":
                c.spec = dict(c.spec, tq_peak=c.spec["tq_peak"] * 1.25, grip=c.spec.get("grip", 1.0) * 1.08)
            import tires
            tires.ensure(c)
            for s in c.tire_list():
                c.tire_p[s] = tires.nominal(c, s)
            d = Driver(self, c, profile, random.Random(rng.randint(0, 10 ** 9)), e, t0, police, name)
            self.drivers.append(d)
            return d
        for i in range(n_cars):
            make(NORMAL_MODELS[i % len(NORMAL_MODELS)], rng.choice(COLORS), rng.choice(["calm", "normal", "normal"]))
        names = [T("«Турбо-Тимо»"), T("«Молния»"), T("«Калле GTI»"), T("«Ночной сокол»")]
        for i in range(n_racers):
            make(RACER_MODELS[i % len(RACER_MODELS)], RACER_COLORS[i % len(RACER_COLORS)], "racer", name=names[i % 4])
        self.police = make("audi80", (235, 235, 235), "police", police=True, name=T("Полиция"))
        self.police.car.spec = dict(self.police.car.spec, drive="fwd")
        self.peds = Pedestrians(self, n_peds, random.Random(seed + 1))
        self._grid = {}

    # --- соседи (сетка 50 м)
    def _rebuild_grid(self):
        g = {}
        for d in self.drivers:
            g.setdefault((int(d.x // 50), int(d.y // 50)), []).append(d)
        self._grid = g

    def near_drivers(self, x, y, r):
        out = []
        gx0, gx1 = int((x - r) // 50), int((x + r) // 50)
        gy0, gy1 = int((y - r) // 50), int((y + r) // 50)
        for gx in range(gx0, gx1 + 1):
            for gy in range(gy0, gy1 + 1):
                out += self._grid.get((gx, gy), [])
        return out

    @property
    def ai(self):
        return self.drivers

    center = (0.0, 0.0)

    def edge_of_map(self, n):
        from world import MAP_W, MAP_H
        return n.x < 20 or n.y < 20 or n.x > MAP_W - 20 or n.y > MAP_H - 20

    def _recycle(self, d, center):
        """Машина уехала из города — «приезжает» с другого выезда (игрок далеко от обоих)."""
        ends = [n for n in self.graph.nodes if n.degree == 1 and n is not d.leaving.b]
        rng = d.rng
        c = d.car
        cands = []
        for n in ends:
            if abs(n.x - center[0]) + abs(n.y - center[1]) < 250:
                continue
            e = n.edges[0]
            off = LANE.get(e.road.kind, 2.5)
            sx, sy = n.x + e.dx * 12 + e.rx * off, n.y + e.dy * 12 + e.ry * off
            if all(math.hypot(o.x - sx, o.y - sy) > 25 for o in self.drivers if o is not d):
                cands.append(n)
        if not cands:
            return                                             # все въезды заняты — подождёт
        n = rng.choice(cands)
        e = n.edges[0]
        off = LANE.get(e.road.kind, 2.5)
        c.x, c.y = n.x + e.dx * 12 + e.rx * off, n.y + e.dy * 12 + e.ry * off
        c.angle = e.heading
        c.speed = min(abs(c.speed), 20.0)
        c.vlat = c.ang_vel = 0.0
        d.edge = e
        d.path = Path()
        d.path.extend_edge(e, off, 12.0)
        d.leaving = None
        d.off = d.off_target = off
        d.passing = None
        d.fallback = None

    def light_state(self, node, axis):
        return node.light.state(axis, self.t) if node.light else "green"

    def update(self, dt, game, center):
        """dt — шаг кадра; game — GameState (для поверхности, погоды); center — позиция игрока."""
        self.t += dt
        self.center = center
        self.player_cars = [c for c in game.cars.values() if abs(c.x - center[0]) + abs(c.y - center[1]) < 300]
        self._rebuild_grid()
        cx, cy = center
        for d in self.drivers:
            c = d.car
            near = abs(c.x - cx) + abs(c.y - cy) < PHYS_DIST
            if near:
                if not d.phys:
                    d.phys = True
                grip, slush = game.winter.surface(c)
                d.gk = max(0.35, min(1.0, grip * (0.8 if game.wet() else 1.0) - min(0.3, slush * 3)))
                inp = d.decide(dt, self.t)
                c.lights = game.darkness() > 0.35 or game.weather in ("snow", "rain", "sleet")
                c.update(dt, inp, rain=game.wet(), ambient=game.ambient_temp(c.x), grip_mult=grip, slush=slush)
                c.events.clear()
                c.sounds.clear()
                if not c.running:
                    c.running = True                             # заглох — водитель сразу заводит снова
                c.fuel = max(c.fuel, 10.0)
                if d.stuck > 6.0:                                # застрял (в сугробе/в стене) — водитель сдаёт назад
                    c.speed = -2.0
                    d.stuck = 0.0
            else:
                if d.phys:
                    d.phys = False
                d.far_acc += dt
                if d.far_acc >= SIM_RATE_FAR:
                    d.far_step(d.far_acc, self.t)
                    d.far_acc = 0.0
            d.siren = max(0.0, d.siren - dt)
            if getattr(d, "offroad_t", 0.0) > 3.0 and abs(d.x - cx) + abs(d.y - cy) > 150:
                e, t0 = self.graph.nearest_edge(d.x, d.y)             # далеко от игрока — поставить обратно на полосу
                off = LANE.get(e.road.kind, 2.5)
                t0 = max(JT + 2, min(e.len - JT - 2, t0))
                c.x, c.y = e.a.x + e.dx * t0 + e.rx * off, e.a.y + e.dy * t0 + e.ry * off
                c.angle = e.heading
                c.speed = c.vlat = c.ang_vel = 0.0
                d.replan()
                d.offroad_t = 0.0
            if d.leaving is not None:
                n = d.leaving.b
                if math.hypot(d.x - n.x, d.y - n.y) < 30 and abs(d.x - cx) + abs(d.y - cy) > 150:
                    self._recycle(d, center)
            # страховка от «вечных» пробок: долго стоит не на красный и игрок далеко — уехал из города, приедет с другого края
            d.still_t = (d.still_t + dt) if abs(c.speed) < 0.3 else 0.0
            if d.still_t > 30.0 and abs(d.x - cx) + abs(d.y - cy) > 180 and not d.at_red(self.t):
                prev = d.leaving
                d.leaving = prev or d.edge
                self._recycle(d, center)                   # удалось — leaving сброшен; нет свободного въезда — как было
                if d.leaving is not None:
                    d.leaving = prev
                d.still_t = 0.0
        self.peds.update(dt, game, center)


# ======================================================================== пешеходы
class Ped:
    def __init__(self, i, rng):
        self.i = i
        self.rng = rng
        self.x = self.y = 0.0
        self.angle = 0.0
        self.speed = 0.0
        self.walk = rng.uniform(1.15, 1.55)
        self.phase = rng.uniform(0, 6.28)
        self.edge = None            # (x0, y0, x1, y1, crossing_node or None, crossing_axis)
        self.s = 0.0
        self.crossing = False
        self.cross_node = None
        self.down = 0.0             # сбит машиной — лежит
        self.scared = 0.0
        self.side = rng.uniform(-0.6, 0.6)
        self.looks = (rng.choice([(60, 70, 90), (120, 40, 40), (40, 70, 50), (90, 80, 60), (30, 30, 35), (150, 120, 80),
                                  (70, 90, 130), (170, 170, 175)]),
                      rng.choice([(40, 40, 50), (60, 60, 70), (30, 40, 70), (80, 70, 60)]),
                      rng.choice([(230, 190, 160), (200, 160, 130), (150, 110, 80)]),
                      rng.choice([(40, 30, 20), (120, 90, 50), (200, 190, 150), (20, 20, 20), (150, 150, 150)]),
                      rng.uniform(0.92, 1.08))


class Pedestrians:
    """Люди на тротуарах: ходят по сети тротуаров, переходят дорогу по переходам (на светофорах — на зелёный
    для пешеходов, без светофора — когда машин нет), уступают, отскакивают от машин; сбитый падает."""
    SIDE = 7.3               # тротуар от осевой (дорога 10 м + 2,3 м)

    def __init__(self, traffic, count, rng):
        self.tr = traffic
        self.rng = rng
        g = traffic.graph
        # углы тротуаров у каждого узла городских дорог
        self.corners = {}        # (node.i, sx, sy) -> (x, y)
        town_nodes = [n for n in g.nodes if any(e.road.kind == "town" for e in n.edges)]
        for n in town_nodes:
            for sx in (-1, 1):
                for sy in (-1, 1):
                    self.corners[(n.i, sx, sy)] = (n.x + sx * self.SIDE, n.y + sy * self.SIDE)
        self.links = {}          # угол -> [(угол, crossing_node, axis_of_road_crossed)]

        def link(a, b, node=None, axis=None):
            self.links.setdefault(a, []).append((b, node, axis))
            self.links.setdefault(b, []).append((a, node, axis))
        for e in g.edges:
            if e.road.kind != "town" or e.a.i > e.b.i:
                continue
            a, b = e.a, e.b
            if e.axis == "h":
                for sy in (-1, 1):
                    link((a.i, 1 if b.x > a.x else -1, sy), (b.i, -1 if b.x > a.x else 1, sy))
            else:
                for sx in (-1, 1):
                    link((a.i, sx, 1 if b.y > a.y else -1), (b.i, sx, -1 if b.y > a.y else 1))
        # переходы через каждую «руку» перекрёстка
        for n in town_nodes:
            dirs = {(round(e.dx), round(e.dy)) for e in n.edges}
            for dx, dy in dirs:
                if dx:        # рука по x: переход через горизонтальную дорогу (между углами sy=-1 и sy=+1)
                    link((n.i, dx, -1), (n.i, dx, 1), n, "h")
                else:
                    link((n.i, -1, dy), (n.i, 1, dy), n, "v")
            # углы, у которых нет дороги с этой стороны, соединяем вдоль (обход тупиковой стороны)
            if n.degree <= 3:
                for (sx, sy) in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
                    if not self.links.get((n.i, sx, sy)):
                        link((n.i, sx, sy), (n.i, -sx, sy))
        keys = [k for k in self.corners if self.links.get(k)]
        self.peds = []
        for i in range(count):
            p = Ped(i, rng)
            a = rng.choice(keys)
            b, node, axis = rng.choice(self.links[a])
            if node is not None:
                b, node, axis = next(((bb, nn, aa) for bb, nn, aa in self.links[a] if nn is None), (b, node, axis))
            self._start(p, a, b, node, axis)
            p.s = rng.uniform(0, 0.9) * self._len(p)
            self._place(p)
            self.peds.append(p)
        self._grid = {}

    def _len(self, p):
        x0, y0, x1, y1 = p.edge[:4]
        return math.hypot(x1 - x0, y1 - y0) or 0.1

    def _start(self, p, a, b, node, axis):
        (x0, y0), (x1, y1) = self.corners[a], self.corners[b]
        p.edge = (x0, y0, x1, y1, node, axis, a, b)
        p.s = 0.0
        p.crossing = node is not None
        p.cross_node = node
        p.waiting = node is not None

    def _place(self, p):
        x0, y0, x1, y1 = p.edge[:4]
        L = self._len(p)
        t = max(0.0, min(1.0, p.s / L))
        dx, dy = (x1 - x0) / L, (y1 - y0) / L
        side = 0.0 if p.crossing else p.side
        p.x = x0 + (x1 - x0) * t - dy * side
        p.y = y0 + (y1 - y0) * t + dx * side
        p.angle = math.atan2(dy, dx)

    def near(self, x, y, r):
        out = []
        for gx in range(int((x - r) // 40), int((x + r) // 40) + 1):
            for gy in range(int((y - r) // 40), int((y + r) // 40) + 1):
                out += self._grid.get((gx, gy), [])
        return out

    def _can_cross(self, p):
        node, axis = p.edge[4], p.edge[5]
        if node.light is not None:
            return node.light.walk(axis, self.tr.t)
        # без светофора: нет машин ближе 35 м, едущих к переходу
        for d in self.tr.near_drivers(p.x, p.y, 45):
            if abs(d.speed) > 1.0 and math.hypot(d.x - p.x, d.y - p.y) < 35:
                return False
        return True

    def update(self, dt, game, center):
        tr = self.tr
        g = {}
        for p in self.peds:
            g.setdefault((int(p.x // 40), int(p.y // 40)), []).append(p)
        self._grid = g
        cx, cy = center
        cars = [d.car for d in tr.near_drivers(cx, cy, 160)] + tr.player_cars
        for p in self.peds:
            far = abs(p.x - cx) + abs(p.y - cy) > 180
            if far and int(tr.t * 10 + p.i) % 5:                 # дальние — реже (но продолжают ходить)
                continue
            step = dt * (5 if far else 1)
            if p.down > 0:
                p.down -= step
                if p.down <= 0:
                    p.scared = 3.0
                continue
            v = p.walk * (1.5 if game.weather in ("rain", "sleet", "snow") else 1.0)
            if p.scared > 0:
                p.scared -= step
                v *= 2.2
            if p.waiting:
                if self._can_cross(p):
                    p.waiting = False
                else:
                    p.speed = 0.0
                    continue
            # машины рядом: не лезть под колёса, отскочить
            blocked = False
            if not far:
                fx, fy = math.cos(p.angle), math.sin(p.angle)
                for c in cars:
                    if abs(c.x - p.x) > 12 or abs(c.y - p.y) > 12:
                        continue
                    for bx, by, br in c.body_circles():
                        dx, dy = p.x - bx, p.y - by
                        dist = math.hypot(dx, dy)
                        if dist < br + 0.35:
                            if abs(c.speed) > 2.5 or abs(c.vlat) > 2.5:
                                self.hit(p, c, game)
                            else:                                # стоящая/ползущая машина — вытолкнуть
                                p.x += dx / (dist or 1) * (br + 0.4 - dist)
                                p.y += dy / (dist or 1) * (br + 0.4 - dist)
                            blocked = True
                            break
                        cfx, cfy = math.cos(c.angle), math.sin(c.angle)
                        closing = -(dx * (cfx * c.speed) + dy * (cfy * c.speed)) / (dist or 1)
                        if dist < 7 and closing > 3.0:
                            p.scared = 1.5                       # машина летит на него — отпрыгнуть в сторону
                            side = 1 if (-dx * cfy + dy * cfx) > 0 else -1
                            p.x += -cfy * side * 3.0 * step
                            p.y += cfx * side * 3.0 * step
                        elif 0 < ((c.x - p.x) * fx + (c.y - p.y) * fy) < 2.5 and dist < 3.5:
                            blocked = True                        # стоит машина поперёк тротуара — подождать/обойти
                            p.side = max(-2.5, min(2.5, p.side + (1 if p.side >= 0 else -1) * 0.5 * step))
                    if blocked:
                        break
            if blocked and p.down <= 0:
                p.speed = 0.0
                continue
            p.speed = v
            p.s += v * step
            p.phase += v * step * 2.2
            if p.s >= self._len(p):
                a = p.edge[7]
                opts = [o for o in self.links.get(a, []) if o[0] != p.edge[6]] or self.links.get(a, [])
                b, node, axis = self.rng.choice(opts)
                self._start(p, a, b, node, axis)
            self._place(p)

    def hit(self, p, car, game):
        if p.down > 0:
            return
        v = math.hypot(car.speed, car.vlat)
        p.down = 6.0 + v * 0.5
        fx, fy = math.cos(car.angle), math.sin(car.angle)
        p.x += fx * min(4.0, v * 0.25)
        p.y += fy * min(4.0, v * 0.25)
        car.speed *= 0.85
        hook = getattr(game, "on_ped_hit", None)
        if hook:
            hook(p, car, v)
