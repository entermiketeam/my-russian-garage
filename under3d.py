"""3D низа машины (underside.py): КПП, сцепление, выхлоп, амортизаторы, рулевые тяги, стартер — каждая деталь
на своём месте, со своим крепежом (те же болты, что сверху: E — открутить/затянуть, G — снять, поставить из рук).
Плюс подъём кузова (домкрат / подставки) и сами домкрат и подставки под машиной.

Детали строятся вместе с болтами — только у машины, возле которой стоит (или под которой лежит) игрок.
"""
import math

from ursina import Entity, color, Vec3, destroy, scene

import underside as U

STEEL = (70, 70, 74)
ALU = (150, 150, 145)
RUST = (110, 72, 45)


def _geo(c3):
    car = c3.car
    sp = car.spec
    g = c3._geo
    eb = getattr(c3, "_engine_box", None)
    if eb is None:
        L = car.length
        eb = (0.0, g["sill"] + 0.3, c3.Z(L - 0.75), 0.4, 0.4, 0.46)
    return car, sp, g, eb


def build(c3):
    """Создать детали низа (если ещё нет). Возвращает [(ключ крепежа, родитель, [точки])] для болтов."""
    if getattr(c3, "under_parts", None):
        return c3._under_anchors
    car, sp, g, (cx, cy, cz, w, h, l) = _geo(c3)
    b = c3.body
    Z = c3.Z
    sill = g["sill"]
    tr = sp["track"]
    wr = sp["wheel_r"]
    rz, fz = Z(sp["axles"][0]), Z(sp["axles"][1])
    rear_end = cz - l / 2                      # задний торец двигателя
    parts = {}
    anchors = []

    def ent(parent, pos, sc, col, model="cube"):
        return Entity(parent=parent, model=model, position=pos, scale=sc, color=color.rgb(*col))

    # КПП: картер за двигателем, хвостовик к карданному валу
    gb = Entity(parent=b)
    gy = cy - h * 0.15
    ent(gb, (cx, gy, rear_end - 0.28), (0.26, 0.24, 0.5), ALU)
    ent(gb, (cx, gy - 0.02, rear_end - 0.62), (0.12, 0.12, 0.3), ALU)
    ent(gb, (cx, gy - 0.04, rear_end - 1.35), (0.06, 0.06, 1.2), STEEL)              # кардан
    parts["gearbox"] = gb
    anchors.append(("gearbox", b, [(cx + sx * 0.14, gy + dy, rear_end - 0.06) for sx in (-1, 1) for dy in (-0.1, 0.0, 0.1)]))
    # сцепление: корзина в колоколе (видна, когда КПП снята)
    cl = Entity(parent=b)
    ent(cl, (cx, cy - h * 0.1, rear_end - 0.03), (0.3, 0.3, 0.05), (120, 120, 118))
    ent(cl, (cx, cy - h * 0.1, rear_end - 0.06), (0.22, 0.22, 0.02), (160, 140, 110))
    parts["clutch"] = cl
    anchors.append(("clutch", b, [(cx + math.cos(a) * 0.12, cy - h * 0.1 + math.sin(a) * 0.12, rear_end - 0.09)
                                  for a in [2 * math.pi * i / 6 for i in range(6)]]))
    # выхлоп: приёмная труба вниз от коллектора, труба под днищем, глушитель, хомуты
    ex = Entity(parent=b)
    py = sill - 0.07
    xp = cx - w * 0.45
    ent(ex, (xp, (py + cy) / 2, cz - l * 0.2), (0.06, max(0.05, cy - py), 0.06), RUST)
    z0, z1 = Z(0.25), cz - l * 0.2
    ent(ex, (xp, py, (z0 + z1) / 2), (0.055, 0.055, z1 - z0), RUST)
    ent(ex, (xp, py - 0.01, Z(1.0)), (0.26, 0.13, 0.55), (60, 58, 55))              # глушитель
    parts["exhaust"] = ex
    anchors.append(("exhaust", b, [(xp, py - 0.035, z1 - 0.15), (xp, py - 0.075, Z(1.0) + 0.3)]))
    # амортизаторы — у каждого колеса, изнутри
    sh = Entity(parent=b)
    pts = []
    for x_, z_ in ((-tr, fz), (tr, fz), (-tr, rz), (tr, rz)):
        xi = x_ - math.copysign(0.2, x_)
        ent(sh, (xi, wr + 0.12, z_ - 0.08), (0.05, 0.36, 0.05), (40, 40, 42))
        ent(sh, (xi, wr + 0.02, z_ - 0.08), (0.07, 0.12, 0.07), (170, 140, 40))
        pts += [(xi, wr - 0.06, z_ - 0.08), (xi, wr + 0.3, z_ - 0.08)]
    parts["shocks"] = sh
    anchors.append(("shocks", b, pts))
    # рулевое: тяги поперёк перед передней осью, рейка/трапеция
    st = Entity(parent=b)
    sy = wr - 0.04
    sz = fz + 0.16
    ent(st, (0, sy, sz), (2 * tr - 0.35, 0.03, 0.03), STEEL)
    ent(st, (0, sy + 0.03, sz + 0.02), (0.45, 0.07, 0.07), (55, 55, 58))
    parts["steering"] = st
    anchors.append(("steering", b, [(-(tr - 0.2), sy - 0.02, sz), (tr - 0.2, sy - 0.02, sz),
                                    (-0.2, sy - 0.01, sz + 0.02), (0.2, sy - 0.01, sz + 0.02)]))
    # стартер: сбоку внизу на стыке двигателя и КПП
    sx_ = cx + w * 0.5
    sa = Entity(parent=b)
    ent(sa, (sx_, cy - h * 0.3, rear_end + 0.06), (0.1, 0.1, 0.2), (30, 30, 32))
    ent(sa, (sx_, cy - h * 0.3 + 0.07, rear_end + 0.1), (0.06, 0.06, 0.08), (150, 150, 150))
    parts["starter"] = sa
    anchors.append(("starter", b, [(sx_ + 0.055, cy - h * 0.3 - 0.03, rear_end + dz) for dz in (-0.02, 0.06, 0.14)]))
    # днище (тёмный лист с рёбрами), видно только снизу — чтобы не «просвечивало»
    fl = Entity(parent=b)
    ent(fl, (0, sill - 0.005, Z(car.length / 2)), (g["W2"] * 2 - 0.2, 0.01, car.length - 1.6), (62, 58, 54))
    for k in range(3):
        ent(fl, (-(g["W2"] - 0.35) + k * (g["W2"] - 0.35), sill - 0.02, Z(car.length / 2)), (0.05, 0.03, car.length - 1.9), (80, 76, 70))
    parts["_floor"] = fl
    c3.under_parts = parts
    c3._under_anchors = anchors
    c3._under_key = None
    update(c3)
    return anchors


def update(c3):
    """Видимость деталей низа: снятой детали нет."""
    parts = getattr(c3, "under_parts", None)
    if not parts:
        return
    car = c3.car
    key = tuple(car.has(k) for k in U.UNDER_SLOTS)
    if key == c3._under_key:
        return
    c3._under_key = key
    for k, e in parts.items():
        if not k.startswith("_"):
            e.enabled = car.has(k)


def destroy_parts(c3):
    for e in (getattr(c3, "under_parts", None) or {}).values():
        destroy(e)
    c3.under_parts = None
    c3._under_anchors = []


# ------------------------------------------------------------------ подъём: кузов, домкрат и подставки
def apply_lift(c3):
    """Поднять/наклонить машину (корень модели) по car.lift; домкрат и подставки под ней."""
    car = c3.car
    lf = getattr(car, "lift", None)
    f, r = (lf.get("f", 0.0), lf.get("r", 0.0)) if isinstance(lf, dict) else (0.0, 0.0)
    if f <= 0.001 and r <= 0.001 and not getattr(c3, "_lift_ents", None):
        if c3.root.y or c3.root.rotation_x:
            c3.root.y = 0
            c3.root.rotation_x = 0
        return                                      # на колёсах (почти все машины) — ничего не делать
    if f > 0.001 or r > 0.001:
        wb = max(1.0, car.spec["axles"][1] - car.spec["axles"][0])
        c3.root.y = (f + r) / 2
        c3.root.rotation_x = -math.degrees(math.atan2(f - r, wb))
    elif c3.root.y or c3.root.rotation_x:
        c3.root.y = 0
        c3.root.rotation_x = 0
    key = (round(car.x, 2), round(car.y, 2), round(car.angle, 3), round(f, 3), round(r, 3),
           U.held_by(car, "f"), U.held_by(car, "r"))
    if key == getattr(c3, "_lift_key", None):
        return
    c3._lift_key = key
    for e in getattr(c3, "_lift_ents", []):
        destroy(e)
    c3._lift_ents = []
    if not (f > 0.001 or r > 0.001):
        return
    fx, fy = math.cos(car.angle), math.sin(car.angle)
    rx, ry = -math.sin(car.angle), math.cos(car.angle)
    yaw = 90 + math.degrees(car.angle)
    for end, h in (("f", f), ("r", r)):
        if h < 0.001:
            continue
        what = U.held_by(car, end)
        top = U.SILL.get(car.model, 0.30) + h - 0.03          # до днища поднятой машины
        ax = car.spec["axles"][1 if end == "f" else 0] - car.length / 2
        if what == "jack":
            z = ax + (0.55 if end == "f" else -0.55)
            px, py = car.x + fx * z, car.y + fy * z
            j = Entity(parent=scene, position=(px, 0, -py), rotation_y=yaw)
            Entity(parent=j, model="cube", color=color.rgb(200, 40, 30), position=(0, 0.06, 0), scale=(0.3, 0.12, 0.75))
            Entity(parent=j, model="cube", color=color.rgb(60, 60, 62), position=(0, 0.06, 0.36), scale=(0.04, 0.04, 0.6))
            Entity(parent=j, model="cube", color=color.rgb(170, 30, 25), position=(0, top / 2, -0.25),
                   scale=(0.1, top, 0.1))
            Entity(parent=j, model="cube", color=color.rgb(40, 40, 40), position=(0, top, -0.25), scale=(0.16, 0.03, 0.16))
            c3._lift_ents.append(j)
        else:
            for side in (-1, 1):
                d = car.spec["track"] - 0.25
                px = car.x + fx * ax + rx * side * d
                py = car.y + fy * ax + ry * side * d
                s = Entity(parent=scene, position=(px, 0, -py), rotation_y=yaw)
                Entity(parent=s, model="cube", color=color.rgb(220, 160, 30), position=(0, 0.04, 0), scale=(0.28, 0.08, 0.28))
                Entity(parent=s, model="cube", color=color.rgb(200, 140, 25), position=(0, top * 0.45, 0),
                       scale=(0.12, top * 0.9, 0.12))
                Entity(parent=s, model="cube", color=color.rgb(60, 60, 62), position=(0, top * 0.95, 0), scale=(0.07, top * 0.1, 0.07))
                c3._lift_ents.append(s)
