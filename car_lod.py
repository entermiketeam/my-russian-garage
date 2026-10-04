"""Простая модель машины для дальнего плана (между подробной моделью и туманом).

Один меш на машину (кузов, кабина, стёкла, колёса) — один вызов отрисовки вместо десятков у Car3D и ~150 вершин
вместо нескольких тысяч. Форма и цвет — по размерам модели, поэтому силуэт узнаётся; вблизи (CAR_VIEW_DIST)
её сменяет полная модель со всеми деталями, ржавчиной и ремонтом.
"""
import math

from ursina import Entity, Vec3

from mesh3d import MeshBuilder
from models import MODELS


def _dims(car):
    W2, L2 = car.spec["width"] / 2, car.length / 2
    if car.model in MODELS:
        B = MODELS[car.model]["body"]
        return W2, L2, B["sill"], B["belt"], B["roof_y"]
    if car.model == "ae86":
        return W2, L2, 0.30, 0.80, 1.30
    return W2, L2, 0.30, 0.86, 1.42


def _mesh(car):
    W2, L2, sill, belt, roof = _dims(car)
    c = tuple(car.paint[:3])                      # цвет с выцветанием, как у полной модели
    dark = tuple(int(v * 0.7) for v in c)
    mb = MeshBuilder()
    mb.box(-W2, sill, -L2, W2, belt, L2, c)                                    # кузов
    cab0, cab1 = -L2 * 0.55, L2 * 0.25                                         # кабина ближе к задку
    mb.box(-W2 * 0.92, belt, cab0, W2 * 0.92, roof, cab1, c)
    mb.box(-W2 * 0.93, belt + 0.06, cab0 + 0.12, W2 * 0.93, roof - 0.06, cab1 - 0.12, (40, 50, 60))   # стёкла
    mb.box(-W2 - 0.01, sill, -L2 - 0.03, W2 + 0.01, sill + 0.14, -L2 + 0.05, dark)                  # бамперы
    mb.box(-W2 - 0.01, sill, L2 - 0.05, W2 + 0.01, sill + 0.14, L2 + 0.03, dark)
    r = car.spec.get("wheel_r", 0.29)
    tr = car.spec.get("track", 0.65)
    axles = car.spec.get("axles", (0.6, 3.0))
    for az in (axles[0] - L2, axles[1] - L2):
        for sx in (-1, 1):
            x = sx * tr
            mb.box(x - 0.09, 0.0, az - r, x + 0.09, 2 * r, az + r, (25, 25, 25))
    return mb.build()


class ProxyCar3D:
    def __init__(self, car):
        self.car = car
        self.root = Entity(model=_mesh(car), double_sided=True)
        self.root.ignore = True                   # статичная: движку не нужно звать её update()
        self._key = None
        self.update()

    def update(self):
        car = self.car
        key = (round(car.x, 2), round(car.y, 2), round(car.angle, 3))
        if key != self._key:
            self._key = key
            self.root.position = Vec3(car.x, 0, -car.y)
            self.root.rotation_y = 90 + math.degrees(car.angle)
