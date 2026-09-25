"""Сборщик статической геометрии: тысячи коробок/крыш/деревьев в один меш.

Система координат Ursina: x — вправо, y — вверх, z — вперёд.
Координаты 2D-мира (x, y) переводятся в 3D как (x, высота, -y).
"""
import math

from ursina import Mesh


def w3(x, y, h=0.0):
    """2D-точка мира -> 3D."""
    return (x, h, -y)


def _norm(v):
    l = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) or 1.0
    return (v[0] / l, v[1] / l, v[2] / l)


def _face_normal(p0, p1, p2):
    e1 = (p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2])
    e2 = (p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2])
    # в левосторонней системе «лицевая» нормаль = e2 x e1
    return _norm((e2[1] * e1[2] - e2[2] * e1[1], e2[2] * e1[0] - e2[0] * e1[2], e2[0] * e1[1] - e2[1] * e1[0]))


def rgba(c, a=1.0):
    if len(c) == 4:
        return (c[0] / 255, c[1] / 255, c[2] / 255, c[3] / 255)
    return (c[0] / 255, c[1] / 255, c[2] / 255, a)


class MeshBuilder:
    def __init__(self, uv_tile=None):
        self.v, self.t, self.c, self.n, self.uv = [], [], [], [], []
        self.uv_tile = uv_tile  # если задано — uv = мировые координаты / tile

    def __len__(self):
        return len(self.v)

    def _uv(self, p):
        if self.uv_tile:
            return (p[0] / self.uv_tile, p[2] / self.uv_tile)
        return (0.0, 0.0)

    def poly(self, pts, color, normal=None, uvs=None):
        """Выпуклый многоугольник. normal — желаемое направление «наружу»."""
        n = _face_normal(pts[0], pts[1], pts[2])
        if normal is not None and n[0] * normal[0] + n[1] * normal[1] + n[2] * normal[2] < 0:
            pts = list(reversed(pts))
            if uvs:
                uvs = list(reversed(uvs))
            n = (-n[0], -n[1], -n[2])
        base = len(self.v)
        col = rgba(color) if max(color[:3]) > 1.0 or isinstance(color[0], int) else tuple(color)
        for i, p in enumerate(pts):
            self.v.append(p)
            self.c.append(col)
            self.n.append(n)
            self.uv.append(uvs[i] if uvs else self._uv(p))
        for i in range(1, len(pts) - 1):
            self.t += (base, base + i, base + i + 1)

    def box(self, x0, y0, z0, x1, y1, z1, color, top=None, sides=None, bottom=False, faces="all"):
        """Коробка по двум углам (3D). top/sides — отдельные цвета граней."""
        if x0 > x1:
            x0, x1 = x1, x0
        if y0 > y1:
            y0, y1 = y1, y0
        if z0 > z1:
            z0, z1 = z1, z0
        sc = sides or color
        tc = top or color
        self.poly([(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)], tc, (0, 1, 0))
        if bottom:
            self.poly([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], sc, (0, -1, 0))
        self.poly([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)], sc, (0, 0, -1))
        self.poly([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], sc, (0, 0, 1))
        self.poly([(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)], sc, (-1, 0, 0))
        self.poly([(x1, y0, z0), (x1, y0, z1), (x1, y1, z1), (x1, y1, z0)], sc, (1, 0, 0))

    def box2d(self, rx, ry, rw, rh, h0, h1, color, **kw):
        """Коробка по прямоугольнику 2D-мира (x, y, w, h) и высотам h0..h1."""
        self.box(rx, h0, -(ry + rh), rx + rw, h1, -ry, color, **kw)

    def flat2d(self, rx, ry, rw, rh, h, color):
        self.poly([(rx, h, -ry), (rx + rw, h, -ry), (rx + rw, h, -(ry + rh)), (rx, h, -(ry + rh))], color, (0, 1, 0))

    def gable2d(self, rx, ry, rw, rh, h, height, color, gable_color):
        """Двускатная крыша над прямоугольником 2D-мира; конёк вдоль длинной стороны."""
        x0, x1 = rx, rx + rw
        z0, z1 = -(ry + rh), -ry
        o = 0.4  # свес
        top = h + height
        if rw >= rh:
            zm = (z0 + z1) / 2
            self.poly([(x0 - o, h, z0 - o), (x1 + o, h, z0 - o), (x1 + o, top, zm), (x0 - o, top, zm)], color, (0, 1, -1))
            self.poly([(x0 - o, h, z1 + o), (x1 + o, h, z1 + o), (x1 + o, top, zm), (x0 - o, top, zm)], color, (0, 1, 1))
            self.poly([(x0, h, z0), (x0, h, z1), (x0, top, zm)], gable_color, (-1, 0, 0))
            self.poly([(x1, h, z0), (x1, h, z1), (x1, top, zm)], gable_color, (1, 0, 0))
        else:
            xm = (x0 + x1) / 2
            self.poly([(x0 - o, h, z0 - o), (x0 - o, h, z1 + o), (xm, top, z1 + o), (xm, top, z0 - o)], color, (-1, 1, 0))
            self.poly([(x1 + o, h, z0 - o), (x1 + o, h, z1 + o), (xm, top, z1 + o), (xm, top, z0 - o)], color, (1, 1, 0))
            self.poly([(x0, h, z0), (x1, h, z0), (xm, top, z0)], gable_color, (0, 0, -1))
            self.poly([(x0, h, z1), (x1, h, z1), (xm, top, z1)], gable_color, (0, 0, 1))

    def cylinder(self, cx, cy, cz, r, h, color, seg=8, cap=True):
        """Вертикальный цилиндр (ствол, столб)."""
        pts = [(cx + math.cos(2 * math.pi * i / seg) * r, cz + math.sin(2 * math.pi * i / seg) * r) for i in range(seg)]
        for i in range(seg):
            a, b = pts[i], pts[(i + 1) % seg]
            mx, mz = (a[0] + b[0]) / 2 - cx, (a[1] + b[1]) / 2 - cz
            self.poly([(a[0], cy, a[1]), (b[0], cy, b[1]), (b[0], cy + h, b[1]), (a[0], cy + h, a[1])], color, (mx, 0, mz))
        if cap:
            self.poly([(p[0], cy + h, p[1]) for p in pts], color, (0, 1, 0))

    def cone(self, cx, cy, cz, r, h, color, seg=7):
        pts = [(cx + math.cos(2 * math.pi * i / seg) * r, cz + math.sin(2 * math.pi * i / seg) * r) for i in range(seg)]
        tip = (cx, cy + h, cz)
        for i in range(seg):
            a, b = pts[i], pts[(i + 1) % seg]
            mx, mz = (a[0] + b[0]) / 2 - cx, (a[1] + b[1]) / 2 - cz
            self.poly([(a[0], cy, a[1]), (b[0], cy, b[1]), tip], color, (mx, r * 0.5, mz))
        self.poly([(p[0], cy, p[1]) for p in pts], color, (0, -1, 0))

    def blob(self, cx, cy, cz, r, color, shade=0.8):
        """Низкополигональная «крона» — октаэдр с двойными гранями."""
        top = (cx, cy + r, cz)
        bot = (cx, cy - r * 0.6, cz)
        ring = [(cx + math.cos(a) * r, cy, cz + math.sin(a) * r) for a in [i * math.pi / 3 + 0.3 for i in range(6)]]
        dark = tuple(int(c * shade) for c in color[:3])
        for i in range(6):
            a, b = ring[i], ring[(i + 1) % 6]
            mx, mz = (a[0] + b[0]) / 2 - cx, (a[2] + b[2]) / 2 - cz
            self.poly([a, b, top], color, (mx, r * 0.7, mz))
            self.poly([a, b, bot], dark, (mx, -r * 0.5, mz))

    def build(self):
        return Mesh(vertices=self.v, triangles=self.t, colors=self.c, normals=self.n,
                    uvs=self.uv if self.uv_tile else None)
