"""3D-модель ВАЗ 2102 (универсал), машины трафика и эффекты (дым, свет фар).

Локальные оси модели: x — вправо, y — вверх, z — вперёд. Центр кузова — (0, 0, 0) на земле.
Профиль из 2D-рисунка: sx от 0 (задний край) до 4.02 (передний) -> z = sx - 2.015.
"""
import math
import random

from panda3d.core import TransparencyAttrib
from ursina import Entity, Text, color, Vec3, destroy

from mesh3d import MeshBuilder
from city3d import additive
import textures3d
from car import WHEELBASE
from models import MODELS

PAINT = (196, 186, 150)
PAINT_DARK = (178, 168, 134)
CHROME = (185, 185, 180)
GLASS = (70, 92, 108)
VINYL = (108, 62, 42)
DASH = (38, 34, 32)


def Z(sx):
    return sx - 2.015


def wheel_mesh(r=0.29, w=0.165, seg=14, rim=(112, 106, 96)):
    """Колесо вдоль оси x: шина, диск, колпак."""
    mb = MeshBuilder()
    pts = [(math.cos(2 * math.pi * i / seg), math.sin(2 * math.pi * i / seg)) for i in range(seg)]
    x0, x1 = -w / 2, w / 2
    for i in range(seg):
        a, b = pts[i], pts[(i + 1) % seg]
        mb.poly([(x0, a[1] * r, a[0] * r), (x1, a[1] * r, a[0] * r), (x1, b[1] * r, b[0] * r), (x0, b[1] * r, b[0] * r)],
                (28, 28, 28), (0, (a[1] + b[1]), (a[0] + b[0])))
    for side, xs in ((1, x1), (-1, x0)):
        mb.poly([(xs, p[1] * r, p[0] * r) for p in pts], (32, 32, 32), (side, 0, 0))
        rr = r * 0.62
        mb.poly([(xs + side * 0.005, p[1] * rr, p[0] * rr) for p in pts], rim, (side, 0, 0))
        hr = r * 0.25
        mb.poly([(xs + side * 0.012, p[1] * hr, p[0] * hr) for p in pts], (200, 198, 190), (side, 0, 0))
        # болты (чтобы было видно вращение)
        for k in range(4):
            a = k * math.pi / 2 + 0.3
            cy, cz = math.sin(a) * r * 0.42, math.cos(a) * r * 0.42
            s = 0.022
            mb.poly([(xs + side * 0.01, cy - s, cz - s), (xs + side * 0.01, cy + s, cz - s),
                     (xs + side * 0.01, cy + s, cz + s), (xs + side * 0.01, cy - s, cz + s)], (60, 58, 55), (side, 0, 0))
    return mb.build()


def ring_entity(parent, radius, thick, col, **kw):
    """Руль: кольцо из маленьких коробок."""
    root = Entity(parent=parent, **kw)
    n = 16
    for i in range(n):
        a = 2 * math.pi * i / n
        Entity(parent=root, model="cube", color=col, position=(math.cos(a) * radius, math.sin(a) * radius, 0),
               rotation_z=-math.degrees(a), scale=(thick, radius * 2 * math.pi / n * 1.05, thick))
    return root


def glass_entity(parent, pts, col=GLASS, alpha=0.35):
    mb = MeshBuilder()
    mb.poly(pts, (*col, int(alpha * 255)), None)
    e = Entity(parent=parent, model=mb.build(), double_sided=True)
    e.setTransparency(TransparencyAttrib.MAlpha)
    e.setDepthWrite(False)
    e.setBin("transparent", 20)
    return e


class Car3D:
    def __init__(self, car):
        self.car = car
        self.root = Entity()
        self.body = Entity(parent=self.root)
        self.t = 0.0
        self.spin = 0.0
        self._rust_key = None
        self._build()
        self.smoke = Smoke()

    # ------------------------------------------------------------------ сборка
    def _build(self):
        b = self.body
        L = self.car.length
        self.Z = lambda sx: sx - L / 2
        self.popups = []
        self.hood_rest = 0.0
        self.plate_texts = []
        if self.car.model == "ae86":
            self._build_ae86(b)
        elif self.car.model in MODELS:
            self._build_generic(b)
        else:
            self._build_vaz(b)
        Z = self.Z
        # борта (текстура с ржавчиной)
        from textures3d import SIDE_W, SIDE_H, SIDE_PPM, SIDE_X0
        qw, qh = SIDE_W / SIDE_PPM, SIDE_H / SIDE_PPM
        cz = Z(-SIDE_X0 + qw / 2)
        cy = qh / 2 - 2 / SIDE_PPM
        sx_ = self.car.spec["width"] / 2 + 0.005
        self.side_r = Entity(parent=b, model="quad", position=(sx_, cy, cz), rotation_y=-90, scale=(qw, qh))
        # левый борт: картинка в текстуре отражена (перед слева)
        self.side_l = Entity(parent=b, model="quad", position=(-sx_, cy, cz), rotation_y=90, scale=(qw, qh))
        for e in (self.side_r, self.side_l):
            e.setTransparency(TransparencyAttrib.MBinary)
        self.refresh_rust(force=True)

        # колёса
        self.wheels = {}
        sp = self.car.spec
        rz, fz = Z(sp["axles"][0]), Z(sp["axles"][1])
        tr = sp["track"]
        self.wr = sp["wheel_r"]
        rim = {"ae86": (170, 170, 172), "w123": (185, 185, 188), "golf": (150, 150, 150),
               "trabant": (200, 200, 195)}.get(self.car.model, (112, 106, 96))
        for slot, (x, z) in {"tire_fl": (-tr, fz), "tire_fr": (tr, fz),
                             "tire_rl": (-tr, rz), "tire_rr": (tr, rz)}.items():
            pivot = Entity(parent=self.root, position=(x, self.wr, z))
            tw = {"ae86": 0.18, "trabant": 0.145, "golf": 0.145, "kadett": 0.155, "taunus": 0.175, "w123": 0.175}
            spin = Entity(parent=pivot, model=wheel_mesh(self.wr, tw.get(self.car.model, 0.165), rim=rim),
                          double_sided=True)
            bricks = Entity(parent=self.root, position=(x, 0, z), enabled=False)
            for k in range(3):
                Entity(parent=bricks, model="cube", color=color.rgb(150, 70, 50), position=(0, 0.05 + k * 0.08, 0),
                       scale=(0.12, 0.075, 0.25))
            self.wheels[slot] = (pivot, spin, bricks)

        # свет фар на асфальте
        self.beams = []
        for x in (-0.55, 0.55):
            bm = Entity(parent=self.root, model="quad", texture=textures3d.beam(), rotation_x=90,
                        position=(x * 3, 0.13, self.car.length / 2 + 14), scale=(9, 28), color=color.rgba(255, 240, 200, 120))
            additive(bm)
            bm.enabled = False
            self.beams.append(bm)
        self.set_hood(False)

    def _build_generic(self, b):
        """3D-кузов найденной машины по параметрам модели (models.py)."""
        import random as _r
        Z = self.Z
        car = self.car
        info = MODELS[car.model]
        B = info["body"]
        sp = car.spec
        rng = _r.Random(car.seed)
        L = car.length
        W2 = sp["width"] / 2
        paint = car.paint
        top_c = tuple(max(0, int(c * 0.93)) for c in paint)
        dark = (26, 24, 22)
        chrome = (185, 185, 180)
        black = (28, 28, 30)
        sill, belt, roof_y = B["sill"], B["belt"], B["roof_y"]
        style = B["style"]
        rb_y = belt if style == "hatch" else B["trunk_y"]
        rgb, rs, re, wb = B["rgb"], B["roof_start"], B["roof_end"], B["ws_base"]
        nose_y, hood_y = B["nose_y"], B["hood_y"]
        seat_c = rng.choice([(108, 62, 42), (40, 40, 44), (60, 70, 110), (170, 150, 110), (120, 40, 35)])
        mb = MeshBuilder()
        for sx in sp["axles"]:
            for side in (-1, 1):
                mb.box(side * 0.28, sill + 0.02, Z(sx - 0.42), side * (W2 - 0.23), sill + 0.44, Z(sx + 0.42), dark)
        mb.box(-(W2 - 0.1), sill + 0.02, Z(wb), W2 - 0.1, sill + 0.1, Z(L - 0.1), (30, 28, 26))
        mb.box(-(W2 - 0.08), sill, Z(0.3), W2 - 0.08, sill + 0.06, Z(wb), (38, 36, 34))
        # нос
        mb.box(-(W2 - 0.01), sill + 0.03, Z(L - 0.08), W2 - 0.01, nose_y, Z(L), paint, top=top_c)
        g = B["grille"]
        fz = Z(L) + 0.005
        if g == "slots":
            for k in range(3):
                mb.box(-0.30, nose_y - 0.24 + k * 0.05, fz, 0.30, nose_y - 0.215 + k * 0.05, fz + 0.01, black)
        elif g == "wide_chrome":
            mb.box(-(W2 - 0.45), nose_y - 0.22, fz, W2 - 0.45, nose_y - 0.05, fz + 0.01, chrome)
            mb.box(-(W2 - 0.48), nose_y - 0.20, fz + 0.01, W2 - 0.48, nose_y - 0.07, fz + 0.015, black)
        elif g == "black_bars":
            mb.box(-(W2 - 0.38), nose_y - 0.20, fz, W2 - 0.38, nose_y - 0.04, fz + 0.01, black)
            for k in range(3):
                mb.box(-(W2 - 0.39), nose_y - 0.17 + k * 0.045, fz + 0.01, W2 - 0.39, nose_y - 0.16 + k * 0.045,
                       fz + 0.015, (60, 60, 62))
        elif g == "egg_crate":
            mb.box(-(W2 - 0.42), nose_y - 0.22, fz, W2 - 0.42, nose_y - 0.04, fz + 0.01, (40, 40, 42))
            for k in range(-4, 5):
                mb.box(k * 0.1 - 0.008, nose_y - 0.22, fz + 0.01, k * 0.1 + 0.008, nose_y - 0.04, fz + 0.016, chrome)
        elif g == "tall_chrome":
            mb.box(-0.24, nose_y - 0.28, fz, 0.24, nose_y + 0.08, fz + 0.03, chrome)
            for k in range(-4, 5):
                mb.box(k * 0.045 - 0.006, nose_y - 0.25, fz + 0.03, k * 0.045 + 0.006, nose_y + 0.05, fz + 0.035, black)
        for x in (-(W2 - 0.12), W2 - 0.12):
            mb.box(x - 0.07, sill + 0.21, Z(L) - 0.01, x + 0.07, sill + 0.26, fz + 0.01, (230, 140, 30))
        # бамперы
        bh = 0.07 if B["bumper"] == "chrome_thin" else 0.12
        bcol = black if B["bumper"] == "black" else chrome
        for z0, z1 in ((Z(L), Z(L) + 0.1), (Z(0) - 0.1, Z(0))):
            mb.box(-(W2 + 0.02), sill + 0.07, z0, W2 + 0.02, sill + 0.07 + bh, z1, bcol)
            if B["bumper"] == "chrome_rubber":
                mb.box(-(W2 + 0.03), sill + 0.10, z0 - 0.005, W2 + 0.03, sill + 0.14, z1 + 0.005, black)
        # корма, крышка багажника / дверь хэтчбека
        mb.box(-(W2 - 0.01), sill + 0.03, Z(0), W2 - 0.01, rb_y, Z(0.08), paint, top=top_c)
        if style != "hatch":
            mb.box(-(W2 - 0.02), rb_y - 0.04, Z(0.05), W2 - 0.02, rb_y, Z(rgb), paint, top=top_c)
        mb.box(-0.26, sill + 0.24, Z(0) - 0.012, 0.26, sill + 0.37, Z(0), (20, 20, 20))      # место под номер
        # крыша и стойки
        mb.box(-(W2 - 0.08), roof_y - 0.05, Z(rs), W2 - 0.08, roof_y, Z(re), paint, top=top_c)
        for x in (-(W2 - 0.05), W2 - 0.05):
            d = 0.035
            for (y0, z0), (y1, z1) in (((belt, Z(wb)), (roof_y, Z(re))), ((rb_y, Z(rgb)), (roof_y, Z(rs)))):
                mb.poly([(x - d, y0, z0), (x + d, y0, z0), (x + d, y1, z1), (x - d, y1, z1)], paint, (0, 0.5, 0.5))
                mb.poly([(x - d, y0, z0 - 0.05), (x + d, y0, z0 - 0.05), (x + d, y1, z1 - 0.05), (x - d, y1, z1 - 0.05)],
                        paint, (0, -0.5, -0.5))
            mb.box(x - 0.03, belt, Z(B["b_pillar"] - 0.03), x + 0.03, roof_y - 0.03, Z(B["b_pillar"] + 0.03), (40, 40, 40))
        mb.box(-(W2 + 0.11), belt + 0.08, Z(wb - 0.25), -(W2 - 0.01), belt + 0.16, Z(wb - 0.19), chrome)   # зеркало
        mb.box(0.30, sill - 0.10, Z(0) - 0.12, 0.36, sill - 0.05, Z(0.5), (90, 80, 70))                  # выхлоп
        # салон
        mb.box(-(W2 - 0.1), belt - 0.16, Z(wb - 0.35), W2 - 0.1, belt + 0.06, Z(wb), (32, 30, 30), top=(26, 24, 24))
        mb.box(-(W2 - 0.3), belt + 0.02, Z(wb - 0.35), -0.14, belt + 0.14, Z(wb - 0.26), (22, 22, 22))   # щиток
        seat_z0, seat_z1 = B["b_pillar"] - 0.45, B["b_pillar"] + 0.1
        if B["seats"] == "bench_front":
            mb.box(-(W2 - 0.12), sill + 0.10, Z(seat_z0), W2 - 0.12, sill + 0.24, Z(seat_z1), seat_c)
            mb.box(-(W2 - 0.12), sill + 0.24, Z(seat_z0 - 0.08), W2 - 0.12, sill + 0.80, Z(seat_z0 + 0.02), seat_c)
        else:
            for x0 in (-(W2 - 0.12), 0.1):
                mb.box(x0, sill + 0.10, Z(seat_z0), x0 + W2 - 0.24, sill + 0.24, Z(seat_z1), seat_c)
                mb.box(x0, sill + 0.24, Z(seat_z0 - 0.08), x0 + W2 - 0.24, sill + 0.82, Z(seat_z0 + 0.02), seat_c)
                mb.box(x0 + 0.1, sill + 0.82, Z(seat_z0 - 0.07), x0 + W2 - 0.34, sill + 0.96, Z(seat_z0), seat_c)
        rz = max(rgb + 0.35, 0.6)
        mb.box(-(W2 - 0.12), sill + 0.10, Z(rz), W2 - 0.12, sill + 0.24, Z(seat_z0 - 0.35), seat_c)
        mb.box(-(W2 - 0.12), sill + 0.24, Z(rz - 0.08), W2 - 0.12, sill + 0.72, Z(rz + 0.02), seat_c)
        for x in (-(W2 - 0.09), W2 - 0.13):
            mb.box(x, sill + 0.06, Z(0.4), x + 0.04, belt, Z(wb - 0.05), tuple(int(c * 0.8) for c in seat_c))
        mb.box(-(W2 - 0.1), roof_y - 0.06, Z(rs + 0.05), W2 - 0.1, roof_y - 0.055, Z(re - 0.05), (165, 160, 150))
        mb.box(-0.08, roof_y - 0.16, Z(re - 0.12), 0.08, roof_y - 0.11, Z(re - 0.1), (30, 30, 30))
        if B.get("dash_shift"):     # Trabant: рычаг КПП торчит из торпедо
            mb.box(0.05, belt - 0.04, Z(wb - 0.55), 0.08, belt - 0.01, Z(wb - 0.3), (30, 30, 30))
            mb.box(0.04, belt - 0.05, Z(wb - 0.58), 0.09, belt, Z(wb - 0.53), (20, 20, 20))
        else:
            mb.box(-0.02, sill + 0.06, Z(wb - 0.75), 0.02, sill + 0.42, Z(wb - 0.71), (30, 30, 30))
            mb.box(-0.035, sill + 0.40, Z(wb - 0.77), 0.035, sill + 0.47, Z(wb - 0.69), (20, 20, 20))
        self.shell = Entity(parent=b, model=mb.build(), double_sided=True)

        # руль
        self.wheel_pivot = Entity(parent=b, position=(sp["eye"][0], belt + 0.06, Z(wb - 0.42)), rotation_x=-28)
        big = car.model in ("w123", "trabant", "wartburg")
        ring_entity(self.wheel_pivot, 0.2 if big else 0.18, 0.025, color.rgb(20, 20, 20))
        self.steer_spokes = Entity(parent=self.wheel_pivot)
        spokes = (0, 180) if B["wheel"] == "two_spoke" else (30, 150, 210, 330)
        for a in spokes:
            Entity(parent=self.steer_spokes, model="cube", color=color.rgb(25, 25, 25), rotation_z=a,
                   position=(math.cos(math.radians(a)) * 0.09, math.sin(math.radians(a)) * 0.09, 0),
                   scale=(0.18, 0.025, 0.02))
        Entity(parent=self.steer_spokes, model="cube", color=color.rgb(40, 40, 40), scale=(0.08, 0.08, 0.03))

        # капот: от лобового к носу, с естественным наклоном
        run = (L - 0.08) - wb
        self.hood_rest = math.degrees(math.atan2(belt - (nose_y + 0.02), run))
        self.hood = Entity(parent=b, position=(0, belt, Z(wb)))
        hm = MeshBuilder()
        hm.box(-(W2 - 0.02), -0.045, 0.0, W2 - 0.02, 0.0, math.hypot(run, belt - nose_y), paint, top=top_c)
        Entity(parent=self.hood, model=hm.build(), double_sided=True)

        # фары
        self.headlamps = []
        lt = B["lights"]
        for sgn in (-1, 1):
            if lt == "round2":
                x = sgn * (W2 - 0.25)
                Entity(parent=b, model="cube", color=color.rgb(*chrome), position=(x, nose_y - 0.12, Z(L) + 0.006),
                       scale=(0.22, 0.22, 0.01))
                self.headlamps.append(Entity(parent=b, model="sphere", color=color.rgb(200, 200, 185),
                                             position=(x, nose_y - 0.12, Z(L) + 0.012), scale=(0.18, 0.18, 0.04)))
            elif lt == "rect2":
                x = sgn * (W2 - 0.26)
                self.headlamps.append(Entity(parent=b, model="cube", color=color.rgb(200, 200, 185),
                                             position=(x, nose_y - 0.12, Z(L) + 0.008), scale=(0.30, 0.13, 0.02)))
            else:   # rect_tall — W123: высокие фары с поворотниками сбоку
                x = sgn * (W2 - 0.3)
                self.headlamps.append(Entity(parent=b, model="cube", color=color.rgb(200, 200, 185),
                                             position=(x, nose_y - 0.12, Z(L) + 0.008), scale=(0.26, 0.2, 0.02)))
                Entity(parent=b, model="cube", color=color.rgb(230, 140, 30),
                       position=(sgn * (W2 - 0.1), nose_y - 0.12, Z(L) + 0.008), scale=(0.1, 0.2, 0.02))
        # фонари
        self.taillights = []
        tail = B["tail"]
        for sgn in (-1, 1):
            if tail == "small_vertical":
                pos, sc = (sgn * (W2 - 0.12), rb_y - 0.16, Z(0) - 0.006), (0.1, 0.18, 0.02)
            elif tail == "vertical_rect":
                pos, sc = (sgn * (W2 - 0.14), rb_y - 0.17, Z(0) - 0.006), (0.18, 0.24, 0.02)
            elif tail == "rect_small":
                pos, sc = (sgn * (W2 - 0.2), rb_y - 0.12, Z(0) - 0.006), (0.3, 0.12, 0.02)
            elif tail == "ribbed_wide":
                pos, sc = (sgn * (W2 - 0.28), rb_y - 0.14, Z(0) - 0.006), (0.46, 0.2, 0.02)
            else:
                pos, sc = (sgn * (W2 - 0.25), rb_y - 0.12, Z(0) - 0.006), (0.42, 0.14, 0.02)
            tl = Entity(parent=b, model="cube", color=color.rgb(120, 20, 20), position=pos, scale=sc)
            self.taillights.append(tl)
            if tail == "ribbed_wide":
                for k in range(4):
                    Entity(parent=tl, model="cube", color=color.rgb(30, 30, 30), position=(0, -0.4 + k * 0.27, -0.6),
                           scale=(1, 0.05, 0.5))
        # номера (появятся после регистрации)
        self.plates = []
        for z, y, rot in ((Z(L) + 0.11, sill + 0.14, 180), (Z(0) - 0.015, sill + 0.305, 0)):
            pl = Entity(parent=b, model="cube", color=color.rgb(240, 240, 240), position=(0, y, z), scale=(0.52, 0.11, 0.01))
            t = Text(car.plate, parent=pl, scale=(1 / 0.52 * 0.9, 1 / 0.11 * 0.9), origin=(0, 0), color=color.black,
                     position=(0, 0, -0.6 if rot == 0 else 0.6), rotation_y=rot)
            self.plate_texts.append(t)
            self.plates.append(pl)
        # стёкла
        glass_entity(b, [(-(W2 - 0.06), belt + 0.01, Z(wb)), (W2 - 0.06, belt + 0.01, Z(wb)),
                         (W2 - 0.1, roof_y - 0.01, Z(re)), (-(W2 - 0.1), roof_y - 0.01, Z(re))],
                     (95, 105, 105) if car.c("glass") < 0.3 else GLASS, 0.55 if car.c("glass") < 0.3 else 0.35)
        glass_entity(b, [(-(W2 - 0.08), rb_y + 0.01, Z(rgb)), (W2 - 0.08, rb_y + 0.01, Z(rgb)),
                         (W2 - 0.1, roof_y - 0.01, Z(rs)), (-(W2 - 0.1), roof_y - 0.01, Z(rs))])

        # моторный отсек
        self.bay = Entity(parent=b)
        ez = Z((wb + L) / 2)
        diesel, two = sp.get("diesel"), sp.get("two_stroke")
        eng_len = 0.62 if diesel else (0.32 if two else 0.46)
        Entity(parent=self.bay, model="cube", color=color.rgb(95, 97, 100), position=(0, sill + 0.30, ez),
               scale=(0.40 if not two else 0.46, 0.40, eng_len))
        Entity(parent=self.bay, model="cube", color=color.rgb(20, 20, 20) if not diesel else color.rgb(150, 150, 155),
               position=(0, sill + 0.53, ez), scale=(0.32, 0.06, eng_len * 0.9))
        cool_part = "belt"
        self.bay_parts = {
            "air_filter": Entity(parent=self.bay, model="cube", color=color.rgb(40, 40, 42),
                                 position=(0.18, sill + 0.62, ez), scale=(0.26, 0.08, 0.26)),
            "carb": Entity(parent=self.bay, model="cube", color=color.rgb(160, 150, 120),
                           position=(0.2, sill + 0.48, ez), scale=(0.1, 0.1, 0.1)),
            "battery": Entity(parent=self.bay, model="cube", color=color.rgb(25, 25, 25),
                              position=(W2 - 0.3, sill + 0.35, Z(wb + 0.2)), scale=(0.22, 0.2, 0.28)),
            "alternator": Entity(parent=self.bay, model="cube", color=color.rgb(170, 170, 170),
                                 position=(-0.3, sill + 0.25, ez + 0.15), scale=(0.14, 0.14, 0.16)),
            "distributor": Entity(parent=self.bay, model="cube", color=color.rgb(30, 30, 30) if not diesel else color.rgb(90, 90, 95),
                                  position=(-0.2, sill + 0.5, ez - 0.1), scale=(0.08, 0.12, 0.08) if not diesel else (0.12, 0.18, 0.25)),
            cool_part: Entity(parent=self.bay, model="cube", color=color.rgb(15, 15, 15),
                              position=(-0.2, sill + 0.22, Z(L - 0.25)), scale=(0.25, 0.03, 0.02)),
        }
        if sp.get("air_cooled"):   # Trabant: кожух вентилятора вместо радиатора
            Entity(parent=self.bay, model="cube", color=color.rgb(70, 70, 72), position=(-0.1, sill + 0.4, Z(L - 0.3)),
                   scale=(0.35, 0.3, 0.12))
        else:
            self.bay_parts["radiator"] = Entity(parent=self.bay, model="cube", color=color.rgb(150, 90, 50),
                                                position=(0, sill + 0.3, Z(L - 0.14)), scale=(W2 * 1.1, 0.34, 0.04))
        Entity(parent=self.bay_parts["battery"], model="cube", color=color.red, position=(0.3, 0.55, 0.3), scale=(0.15, 0.1, 0.1))
        Entity(parent=self.bay_parts["battery"], model="cube", color=color.blue, position=(-0.3, 0.55, 0.3), scale=(0.15, 0.1, 0.1))

    def _build_vaz(self, b):
        Z = self.Z
        mb = MeshBuilder()
        # колёсные ниши (видны сквозь вырезы арок) и дно моторного отсека
        for sx in (0.83, 3.25):
            for side in (-1, 1):
                mb.box(side * 0.30, 0.26, Z(sx - 0.42), side * 0.58, 0.74, Z(sx + 0.42), (24, 22, 20))
        mb.box(-0.70, 0.26, Z(2.98), 0.70, 0.40, Z(3.95), (30, 28, 26))
        mb.box(-0.70, 0.30, Z(0.08), 0.70, 0.60, Z(0.45), (40, 36, 34))   # пол багажника
        # днище/пол салона
        mb.box(-0.72, 0.30, Z(0.3), 0.72, 0.36, Z(2.95), (40, 36, 34))
        # передняя панель
        mb.box(-0.80, 0.33, Z(3.94), 0.80, 0.82, Z(4.01), PAINT)
        mb.box(-0.52, 0.52, Z(4.01), 0.52, 0.76, Z(4.03), (22, 22, 22))              # решётка
        for x in (-0.53, 0.53):
            mb.box(x - 0.012, 0.51, Z(4.0), x + 0.012, 0.77, Z(4.04), CHROME)
        mb.box(-0.53, 0.755, Z(4.0), 0.53, 0.775, Z(4.04), CHROME)
        # задняя панель (универсал) и дверь багажника
        mb.box(-0.80, 0.33, Z(0.0), 0.80, 0.86, Z(0.07), PAINT)
        mb.box(-0.78, 0.86, Z(0.06), 0.78, 0.94, Z(0.12), PAINT)
        # багажник на крыше и крыша
        mb.box(-0.80, 1.38, Z(0.10), 0.80, 1.45, Z(2.36), PAINT_DARK, top=(205, 197, 162))
        for x in (-0.62, 0.62):
            mb.box(x - 0.025, 1.52, Z(0.3), x + 0.025, 1.56, Z(2.2), (60, 55, 50))
        for sx in (0.4, 1.2, 2.1):
            mb.box(-0.64, 1.45, Z(sx) - 0.02, -0.60, 1.53, Z(sx) + 0.02, (60, 55, 50))
            mb.box(0.60, 1.45, Z(sx) - 0.02, 0.64, 1.53, Z(sx) + 0.02, (60, 55, 50))
            mb.box(-0.64, 1.52, Z(sx) - 0.02, 0.64, 1.555, Z(sx) + 0.02, (60, 55, 50))
        # стойки (видны и изнутри)
        mb.box(-0.80, 0.86, Z(1.84), -0.74, 1.40, Z(1.90), PAINT)      # B-стойка
        mb.box(0.74, 0.86, Z(1.84), 0.80, 1.40, Z(1.90), PAINT)
        mb.box(-0.80, 0.86, Z(0.96), -0.74, 1.40, Z(1.02), PAINT)      # C-стойка
        mb.box(0.74, 0.86, Z(0.96), 0.80, 1.40, Z(1.02), PAINT)
        mb.box(-0.80, 0.86, Z(0.06), -0.70, 1.40, Z(0.2), PAINT)       # D-стойка
        mb.box(0.70, 0.86, Z(0.06), 0.80, 1.40, Z(0.2), PAINT)
        for x in (-0.77, 0.77):   # A-стойки
            p0 = (x, 0.87, Z(2.98))
            p1 = (x, 1.40, Z(2.52))
            d = 0.035
            mb.poly([(x - d, p0[1], p0[2]), (x + d, p0[1], p0[2]), (x + d, p1[1], p1[2]), (x - d, p1[1], p1[2])], PAINT, (0, 0.5, 0.5))
            mb.poly([(x - d, p0[1], p0[2] - 0.06), (x + d, p0[1], p0[2] - 0.06), (x + d, p1[1], p1[2] - 0.06),
                     (x - d, p1[1], p1[2] - 0.06)], PAINT, (0, -0.5, -0.5))
        # бамперы
        mb.box(-0.84, 0.36, Z(4.0), 0.84, 0.47, Z(4.11), CHROME)
        mb.box(-0.84, 0.38, Z(-0.09), 0.84, 0.49, Z(0.0), CHROME)
        for x in (-0.55, 0.55):
            mb.box(x - 0.08, 0.30, Z(4.02), x + 0.08, 0.35, Z(4.06), (230, 140, 30))   # поворотники
        # зеркало
        mb.box(-0.93, 0.93, Z(2.78), -0.80, 1.0, Z(2.84), (30, 30, 30))
        # выхлопная труба
        mb.box(0.35, 0.18, Z(-0.12), 0.41, 0.24, Z(0.5), (90, 80, 70))
        # салон: приборная панель, сиденья, обивка дверей
        mb.box(-0.72, 0.70, Z(2.62), 0.72, 0.93, Z(2.98), DASH, top=(30, 28, 27))
        mb.box(-0.56, 0.88, Z(2.62), -0.16, 1.02, Z(2.72), (26, 24, 23))                # щиток приборов
        for x0 in (-0.62, 0.12):
            mb.box(x0, 0.40, Z(1.55), x0 + 0.50, 0.54, Z(2.1), VINYL)
            mb.box(x0, 0.54, Z(1.47), x0 + 0.50, 1.12, Z(1.57), VINYL)
            mb.box(x0 + 0.1, 1.12, Z(1.49), x0 + 0.40, 1.28, Z(1.56), VINYL)             # подголовник
        mb.box(-0.64, 0.40, Z(0.62), 0.64, 0.54, Z(1.15), VINYL)
        mb.box(-0.64, 0.54, Z(0.55), 0.64, 1.05, Z(0.66), VINYL)
        for x in (-0.73, 0.69):
            mb.box(x, 0.36, Z(0.4), x + 0.04, 0.86, Z(2.9), (95, 66, 52))
        mb.box(-0.72, 1.37, Z(0.2), 0.72, 1.38, Z(2.45), (170, 160, 140))               # потолок
        mb.box(-0.09, 1.30, Z(2.47), 0.09, 1.35, Z(2.49), (30, 30, 30))                 # салонное зеркало
        mb.box(-0.02, 0.36, Z(2.2), 0.02, 0.72, Z(2.24), (30, 30, 30))                  # рычаг КПП
        mb.box(-0.035, 0.70, Z(2.18), 0.035, 0.77, Z(2.25), (20, 20, 20))
        self.shell = Entity(parent=b, model=mb.build(), double_sided=True)

        # руль
        self.wheel_pivot = Entity(parent=b, position=(-0.36, 0.98, Z(2.55)), rotation_x=-28)
        ring_entity(self.wheel_pivot, 0.19, 0.03, color.rgb(20, 20, 20))
        self.steer_spokes = Entity(parent=self.wheel_pivot)
        for a in (0, 180, 270):
            Entity(parent=self.steer_spokes, model="cube", color=color.rgb(25, 25, 25),
                   rotation_z=a, position=(math.cos(math.radians(a)) * 0.09, math.sin(math.radians(a)) * 0.09, 0),
                   scale=(0.18, 0.025, 0.02))
        Entity(parent=self.steer_spokes, model="cube", color=color.rgb(40, 40, 40), scale=(0.07, 0.07, 0.03))

        # капот (открывается в гараже)
        self.hood = Entity(parent=b, position=(0, 0.86, Z(2.99)))
        hm = MeshBuilder()
        hm.box(-0.80, -0.05, 0.0, 0.80, 0.0, Z(3.95) - Z(2.99), PAINT, top=(190, 180, 146))
        hm.box(-0.30, 0.0, 0.25, 0.05, 0.004, 0.55, (128, 128, 122))     # пятно грунта
        Entity(parent=self.hood, model=hm.build(), double_sided=True)

        # моторный отсек
        self.bay = Entity(parent=b)
        Entity(parent=self.bay, model="cube", color=color.rgb(90, 92, 95), position=(-0.05, 0.55, Z(3.35)), scale=(0.42, 0.42, 0.55))
        Entity(parent=self.bay, model="cube", color=color.rgb(20, 20, 20), position=(-0.05, 0.79, Z(3.35)), scale=(0.34, 0.06, 0.5))
        self.bay_parts = {
            "air_filter": Entity(parent=self.bay, model="cube", color=color.rgb(40, 40, 42), position=(0.05, 0.86, Z(3.3)), scale=(0.34, 0.07, 0.34)),
            "carb": Entity(parent=self.bay, model="cube", color=color.rgb(160, 150, 120), position=(0.12, 0.72, Z(3.3)), scale=(0.12, 0.1, 0.12)),
            "battery": Entity(parent=self.bay, model="cube", color=color.rgb(25, 25, 25), position=(0.52, 0.62, Z(3.62)), scale=(0.22, 0.2, 0.28)),
            "radiator": Entity(parent=self.bay, model="cube", color=color.rgb(150, 90, 50), position=(0, 0.58, Z(3.88)), scale=(0.9, 0.38, 0.04)),
            "alternator": Entity(parent=self.bay, model="cube", color=color.rgb(170, 170, 170), position=(-0.36, 0.5, Z(3.6)), scale=(0.14, 0.14, 0.16)),
            "distributor": Entity(parent=self.bay, model="cube", color=color.rgb(30, 30, 30), position=(-0.2, 0.8, Z(3.1)), scale=(0.07, 0.12, 0.07)),
            "belt": Entity(parent=self.bay, model="cube", color=color.rgb(15, 15, 15), position=(-0.2, 0.46, Z(3.66)), scale=(0.25, 0.03, 0.02)),
        }
        Entity(parent=self.bay_parts["battery"], model="cube", color=color.red, position=(0.3, 0.55, 0.3), scale=(0.15, 0.1, 0.1))
        Entity(parent=self.bay_parts["battery"], model="cube", color=color.blue, position=(-0.3, 0.55, 0.3), scale=(0.15, 0.1, 0.1))

        # стёкла
        glass_entity(b, [(-0.74, 0.88, Z(2.98)), (0.74, 0.88, Z(2.98)), (0.72, 1.39, Z(2.52)), (-0.72, 1.39, Z(2.52))])
        glass_entity(b, [(-0.70, 0.94, Z(0.07)), (0.70, 0.94, Z(0.07)), (0.70, 1.37, Z(0.1)), (-0.70, 1.37, Z(0.1))])

        # фары, фонари (отдельно — меняют яркость)
        self.headlamps = []
        for x in (-0.62, 0.62):
            Entity(parent=b, model="cube", color=color.rgb(*CHROME), position=(x, 0.64, Z(4.015)), scale=(0.24, 0.24, 0.02))
            lamp = Entity(parent=b, model="sphere", color=color.rgb(200, 200, 185), position=(x, 0.64, Z(4.02)),
                          scale=(0.19, 0.19, 0.05))
            self.headlamps.append(lamp)
        self.taillights = []
        for x in (-0.66, 0.66):
            tl = Entity(parent=b, model="cube", color=color.rgb(120, 20, 20), position=(x, 0.66, Z(-0.005)), scale=(0.18, 0.22, 0.02))
            self.taillights.append(tl)
        # номера
        self.plates = []
        for z, rot in ((Z(4.12), 180), (Z(-0.1), 0)):
            pl = Entity(parent=b, model="cube", color=color.rgb(240, 240, 240), position=(0, 0.52 if z > 0 else 0.62, z), scale=(0.52, 0.11, 0.01))
            Text(self.car.plate, parent=pl, scale=(1 / 0.52 * 0.9, 1 / 0.11 * 0.9), origin=(0, 0), color=color.black,
                 position=(0, 0, -0.6 if rot == 0 else 0.6), rotation_y=rot)
            self.plates.append(pl)


    def _build_ae86(self, b):
        """Toyota Sprinter Trueno AE86 (1985), «панда»: белый верх, чёрный низ."""
        Z = self.Z
        W_, K_ = (238, 238, 232), (32, 32, 34)
        GLS = (40, 50, 60)
        mb = MeshBuilder()
        for sx in self.car.spec["axles"]:
            for side in (-1, 1):
                mb.box(side * 0.30, 0.26, Z(sx - 0.42), side * 0.58, 0.74, Z(sx + 0.42), (24, 22, 20))
        mb.box(-0.70, 0.26, Z(3.10), 0.70, 0.40, Z(4.10), (30, 28, 26))
        mb.box(-0.72, 0.30, Z(0.3), 0.72, 0.36, Z(3.05), (38, 38, 40))
        mb.box(-0.70, 0.30, Z(0.10), 0.70, 0.62, Z(0.45), (40, 40, 42))          # пол багажника
        # нос: чёрный бампер + белая панель со щелью решётки
        mb.box(-0.82, 0.33, Z(4.00), 0.82, 0.52, Z(4.25), K_)
        mb.box(-0.80, 0.52, Z(4.05), 0.80, 0.71, Z(4.19), W_)
        mb.box(-0.55, 0.56, Z(4.19), 0.55, 0.62, Z(4.20), (15, 15, 15))
        for x in (-0.62, 0.62):
            mb.box(x - 0.1, 0.44, Z(4.24), x + 0.1, 0.49, Z(4.26), (230, 140, 30))   # поворотники в бампере
        # корма: чёрный бампер, белая панель, сплошная полоса фонарей
        mb.box(-0.82, 0.33, Z(-0.06), 0.82, 0.50, Z(0.12), K_)
        mb.box(-0.80, 0.50, Z(0.0), 0.80, 0.87, Z(0.08), W_)
        mb.box(-0.30, 0.62, Z(-0.01), 0.30, 0.80, Z(0.0), (20, 20, 20))            # место под номер
        # крыша, стойки
        mb.box(-0.74, 1.29, Z(1.45), 0.74, 1.35, Z(2.50), W_, top=(245, 245, 240))
        mb.box(-0.80, 0.87, Z(1.94), -0.74, 1.30, Z(2.0), K_)
        mb.box(0.74, 0.87, Z(1.94), 0.80, 1.30, Z(2.0), K_)
        for x in (-0.77, 0.77):
            d = 0.035
            p0, p1 = (0.87, Z(3.08)), (1.30, Z(2.55))
            mb.poly([(x - d, p0[0], p0[1]), (x + d, p0[0], p0[1]), (x + d, p1[0], p1[1]), (x - d, p1[0], p1[1])], K_, (0, 0.5, 0.5))
            mb.poly([(x - d, p0[0], p0[1] - 0.06), (x + d, p0[0], p0[1] - 0.06), (x + d, p1[0], p1[1] - 0.06),
                     (x - d, p1[0], p1[1] - 0.06)], K_, (0, -0.5, -0.5))
            # задние стойки вдоль стекла люка
            q0, q1 = (0.88, Z(0.45)), (1.30, Z(1.45))
            mb.poly([(x - d, q0[0], q0[1]), (x + d, q0[0], q0[1]), (x + d, q1[0], q1[1]), (x - d, q1[0], q1[1])], W_, (0, 0.5, -0.5))
        # зеркало, выхлоп
        mb.box(-0.93, 0.93, Z(2.90), -0.80, 1.0, Z(2.96), K_)
        mb.box(0.35, 0.18, Z(-0.12), 0.41, 0.24, Z(0.5), (90, 80, 70))
        # салон: торпедо, ковши, заднее сиденье
        mb.box(-0.72, 0.66, Z(2.75), 0.72, 0.88, Z(3.08), (28, 28, 30), top=(24, 24, 26))
        mb.box(-0.56, 0.84, Z(2.75), -0.16, 0.98, Z(2.85), (20, 20, 22))            # щиток приборов
        mb.box(-0.12, 0.70, Z(2.72), 0.12, 0.84, Z(2.78), (35, 35, 38))             # магнитола
        seat, trim = (60, 60, 66), (140, 30, 30)
        for x0 in (-0.62, 0.12):
            mb.box(x0, 0.36, Z(1.72), x0 + 0.50, 0.50, Z(2.25), seat)
            mb.box(x0, 0.50, Z(1.64), x0 + 0.50, 1.10, Z(1.74), seat)
            mb.box(x0 - 0.02, 0.50, Z(1.66), x0 + 0.04, 0.95, Z(1.90), seat)         # боковая поддержка
            mb.box(x0 + 0.46, 0.50, Z(1.66), x0 + 0.52, 0.95, Z(1.90), seat)
            mb.box(x0 + 0.1, 1.10, Z(1.66), x0 + 0.40, 1.24, Z(1.72), seat)
            mb.box(x0 + 0.05, 0.505, Z(1.742), x0 + 0.45, 0.515, Z(2.2), trim)       # красная вставка
        mb.box(-0.64, 0.36, Z(0.80), 0.64, 0.50, Z(1.30), seat)
        mb.box(-0.64, 0.50, Z(0.72), 0.64, 0.95, Z(0.82), seat)
        for x in (-0.73, 0.69):
            mb.box(x, 0.36, Z(0.5), x + 0.04, 0.86, Z(3.0), (45, 45, 48))
        mb.box(-0.72, 1.28, Z(1.5), 0.72, 1.29, Z(2.52), (150, 150, 150))           # потолок
        mb.box(-0.09, 1.20, Z(2.58), 0.09, 1.25, Z(2.60), (25, 25, 25))             # салонное зеркало
        mb.box(-0.02, 0.36, Z(2.35), 0.02, 0.70, Z(2.39), (25, 25, 25))             # рычаг КПП (5 ступ.)
        mb.box(-0.035, 0.68, Z(2.33), 0.035, 0.75, Z(2.40), (20, 20, 20))
        self.shell = Entity(parent=b, model=mb.build(), double_sided=True)

        # руль (трёхспицевый)
        self.wheel_pivot = Entity(parent=b, position=(-0.36, 0.88, Z(2.72)), rotation_x=-24)
        ring_entity(self.wheel_pivot, 0.18, 0.03, color.rgb(18, 18, 18))
        self.steer_spokes = Entity(parent=self.wheel_pivot)
        for a in (0, 180, 270):
            Entity(parent=self.steer_spokes, model="cube", color=color.rgb(30, 30, 30), rotation_z=a,
                   position=(math.cos(math.radians(a)) * 0.085, math.sin(math.radians(a)) * 0.085, 0),
                   scale=(0.17, 0.03, 0.02))
        Entity(parent=self.steer_spokes, model="cube", color=color.rgb(170, 20, 20), scale=(0.06, 0.06, 0.03))

        # капот (с наклоном к носу)
        self.hood_rest = 9.0
        self.hood = Entity(parent=b, position=(0, 0.87, Z(3.08)))
        hm = MeshBuilder()
        hm.box(-0.80, -0.05, 0.0, 0.80, 0.0, Z(4.05) - Z(3.08) - 0.32, W_, top=(242, 242, 236))
        Entity(parent=self.hood, model=hm.build(), double_sided=True)

        # поднимающиеся фары: крышка на шарнире + фара под ней
        self.headlamps = []
        for x in (-0.60, 0.60):
            pivot = Entity(parent=self.hood, position=(x, 0.0, 0.66))
            Entity(parent=pivot, model="cube", color=color.rgb(*W_), position=(0, -0.02, 0.15), scale=(0.34, 0.035, 0.30))
            self.popups.append(pivot)
            lamp = Entity(parent=pivot, model="cube", color=color.rgb(200, 200, 190), position=(0, -0.13, 0.30),
                          scale=(0.28, 0.20, 0.03))
            self.headlamps.append(lamp)

        # моторный отсек: 4A-GE
        self.bay = Entity(parent=b)
        Entity(parent=self.bay, model="cube", color=color.rgb(95, 97, 100), position=(0, 0.55, Z(3.55)), scale=(0.46, 0.40, 0.52))
        Entity(parent=self.bay, model="cube", color=color.rgb(200, 200, 205), position=(0, 0.78, Z(3.55)), scale=(0.40, 0.07, 0.48))
        Entity(parent=self.bay, model="cube", color=color.rgb(190, 30, 30), position=(0, 0.82, Z(3.55)), scale=(0.18, 0.012, 0.3))
        self.bay_parts = {
            "air_filter": Entity(parent=self.bay, model="cube", color=color.rgb(30, 30, 32), position=(-0.45, 0.70, Z(3.45)), scale=(0.25, 0.14, 0.35)),
            "carb": Entity(parent=self.bay, model="cube", color=color.rgb(150, 150, 150), position=(0.22, 0.70, Z(3.5)), scale=(0.1, 0.1, 0.4)),
            "battery": Entity(parent=self.bay, model="cube", color=color.rgb(25, 25, 25), position=(0.52, 0.60, Z(3.9)), scale=(0.22, 0.2, 0.26)),
            "radiator": Entity(parent=self.bay, model="cube", color=color.rgb(60, 60, 62), position=(0, 0.55, Z(4.02)), scale=(0.9, 0.32, 0.04)),
            "alternator": Entity(parent=self.bay, model="cube", color=color.rgb(170, 170, 170), position=(0.3, 0.45, Z(3.8)), scale=(0.14, 0.14, 0.16)),
            "distributor": Entity(parent=self.bay, model="cube", color=color.rgb(30, 30, 30), position=(-0.1, 0.72, Z(3.25)), scale=(0.08, 0.1, 0.08)),
            "belt": Entity(parent=self.bay, model="cube", color=color.rgb(20, 20, 20), position=(-0.26, 0.58, Z(3.84)), scale=(0.06, 0.36, 0.1)),
        }
        Entity(parent=self.bay_parts["battery"], model="cube", color=color.red, position=(0.3, 0.55, 0.3), scale=(0.15, 0.1, 0.1))
        Entity(parent=self.bay_parts["battery"], model="cube", color=color.blue, position=(-0.3, 0.55, 0.3), scale=(0.15, 0.1, 0.1))

        # стёкла: лобовое и покатое стекло люка
        glass_entity(b, [(-0.74, 0.87, Z(3.08)), (0.74, 0.87, Z(3.08)), (0.72, 1.30, Z(2.55)), (-0.72, 1.30, Z(2.55))], GLS)
        glass_entity(b, [(-0.72, 0.88, Z(0.45)), (0.72, 0.88, Z(0.45)), (0.70, 1.30, Z(1.45)), (-0.70, 1.30, Z(1.45))], GLS)

        # фонари: широкая полоса по всей корме
        self.taillights = []
        for x0, x1 in ((-0.79, -0.31), (0.31, 0.79)):
            tl = Entity(parent=b, model="cube", color=color.rgb(120, 20, 20), position=((x0 + x1) / 2, 0.71, Z(-0.005)),
                        scale=(x1 - x0, 0.17, 0.02))
            self.taillights.append(tl)
        # номера
        self.plates = []
        for z, y, rot in ((Z(4.26), 0.41, 180), (Z(-0.02), 0.71, 0)):
            pl = Entity(parent=b, model="cube", color=color.rgb(240, 240, 240), position=(0, y, z), scale=(0.52, 0.11, 0.01))
            Text(self.car.plate, parent=pl, scale=(1 / 0.52 * 0.9, 1 / 0.11 * 0.9), origin=(0, 0), color=color.black,
                 position=(0, 0, -0.6 if rot == 0 else 0.6), rotation_y=rot)
            self.plates.append(pl)

    # ------------------------------------------------------------------ состояние
    def refresh_rust(self, force=False):
        car = self.car
        key = tuple(int(v // 4) for v in car.rust.values()) + (int(car.dirt * 6), int(car.fade * 6),
                                                                 int(car.c("glass") * 4), tuple(car.dents))
        if key == self._rust_key and not force:
            return
        self._rust_key = key
        self.side_r.texture = textures3d.car_side(self.car, "r")
        self.side_l.texture = textures3d.car_side(self.car, "l")

    def set_hood(self, open_):
        self.hood.rotation_x = -55 if open_ else self.hood_rest
        self.bay.enabled = open_

    def update(self, dt, inp, night):
        car = self.car
        self.t += dt
        self.root.position = Vec3(car.x, 0, -car.y)
        self.root.rotation_y = 90 + math.degrees(car.angle)
        # крен и клевки
        lat = car.speed * car.ang_vel
        soft = 1.6 - 0.8 * car.c("shocks")
        self.body.rotation_z = max(-4, min(4, lat * 0.35 * soft))
        acc = inp.get("throttle", 0) * (1 if car.running and car.gear else 0) - inp.get("brake", 0) * (1 if abs(car.speed) > 0.5 else 0)
        self.body.rotation_x += ((-acc * 1.4 * soft) - self.body.rotation_x) * min(1, dt * 4)
        y = 0.0
        if car.shake > 0.05:
            y += math.sin(self.t * 23) * car.shake * 0.025
        if car.running:
            y += math.sin(self.t * max(10, car.rpm / 60)) * 0.004 * (2 - car.c("engine"))
        flats = car.flat_tires()
        self.body.y = y - 0.04 * len(flats)
        # колёса
        self.spin += car.speed / self.wr * dt
        for slot, (pivot, spin, bricks) in self.wheels.items():
            present = car.has(slot)
            pivot.enabled = present
            bricks.enabled = not present
            if not present:
                continue
            spin.rotation_x = math.degrees(self.spin)
            flat = slot in flats
            pivot.y = self.wr - 0.07 if flat else self.wr
            spin.scale_y = 0.78 if flat else 1.0
            if slot in ("tire_fl", "tire_fr"):
                max_steer = 33 / (1 + abs(car.speed) / 14)
                pivot.rotation_y = car.steer * max_steer
        self.wheel_pivot.rotation_z = 0
        self.steer_spokes.rotation_z = -car.steer * 120
        # свет
        lit = car.lights_ok
        for t in self.plate_texts:
            if t.text != car.plate:
                t.text = car.plate
        for lamp in self.headlamps:
            lamp.enabled = car.has("lights")
        k = 0.4 + 0.6 * car.c("lights") if lit else 0
        for lamp in self.headlamps:
            if lit:
                lamp.color = color.rgb(255, 250, 220)
                lamp.setLightOff()
            else:
                lamp.color = color.rgb(190, 190, 176)
                lamp.clearLight()
        # поднимающиеся фары AE86: открыты, когда включён свет
        for pu in self.popups:
            target = -78 if car.lights else 0
            pu.rotation_x += (target - pu.rotation_x) * min(1, dt * 6)
        for bm in self.beams:
            bm.enabled = lit and night > 0.15
            bm.color = color.rgba(255, 240, 200, int(140 * k))
        braking = inp.get("brake", 0) > 0.1 and car.battery_charge > 2
        for tl in self.taillights:
            if braking or lit:
                tl.color = color.rgb(255, 40, 30) if braking else color.rgb(200, 30, 25)
                tl.setLightOff()
            else:
                tl.color = color.rgb(120, 20, 20)
                tl.clearLight()
        for pl in self.plates:
            pl.enabled = car.registered
        for name, ent in self.bay_parts.items():
            ent.enabled = car.has(name)
        self.refresh_rust()
        # дым
        if car.running:
            fx, fy = car.forward()
            back = car.length / 2 + 0.1
            ex = car.x - fx * back + fy * 0.38
            ey = car.y - fy * back - fx * 0.38
            rich = car.choke or car.temp < 40 or car.c("plugs") < 0.4
            blue = car.c("engine") < 0.35
            rate = 6 + car.rpm / 400 * (0.3 + inp.get("throttle", 0))
            if rich:
                col = (60, 60, 62)
            elif blue:
                col = (140, 150, 175)
            else:
                col = (200, 200, 205)
            dens = 0.55 if rich or blue else 0.25
            if car.temp < 50:
                dens += 0.2   # пар из холодной трубы
            k = 1 - 0.8 * night
            col = tuple(int(c * k) for c in col)
            self.smoke.emit(dt, rate, (ex, 0.25, -ey), col, dens * (1 - 0.5 * night), (-fx * 0.6, 0.35, fy * 0.6))
        self.smoke.update(dt)


class Smoke:
    def __init__(self, n=48):
        self.pool = []
        for _ in range(n):
            e = Entity(model="quad", texture=textures3d.glow(), billboard=True, enabled=False)
            e.setTransparency(TransparencyAttrib.MAlpha)
            e.setDepthWrite(False)
            e.setBin("transparent", 30)
            e.setLightOff()
            self.pool.append([e, 0.0, Vec3(0, 0, 0), 0.0, (0, 0, 0)])
        self.acc = 0.0
        self.i = 0

    def emit(self, dt, rate, pos, col, dens, vel):
        self.acc += rate * dt
        while self.acc >= 1:
            self.acc -= 1
            p = self.pool[self.i]
            self.i = (self.i + 1) % len(self.pool)
            e = p[0]
            e.enabled = True
            e.position = Vec3(*pos)
            e.scale = 0.25
            p[1] = 1.6
            p[2] = Vec3(vel[0] + random.uniform(-0.2, 0.2), vel[1], vel[2] + random.uniform(-0.2, 0.2))
            p[3] = dens
            p[4] = col

    def update(self, dt):
        for p in self.pool:
            e = p[0]
            if not e.enabled:
                continue
            p[1] -= dt
            if p[1] <= 0:
                e.enabled = False
                continue
            e.position += p[2] * dt
            e.scale = 0.25 + (1.6 - p[1]) * 0.9
            a = p[3] * (p[1] / 1.6)
            e.color = color.rgba(*p[4], int(a * 255))


# ====================================================================== трафик


class AICar3D:
    def __init__(self, ai):
        self.ai = ai
        self.root = Entity()
        c = ai.color
        mb = MeshBuilder()
        police = ai.police
        body = (235, 235, 235) if police else c
        lower = (40, 110, 70) if police else c
        mb.box(-0.84, 0.28, -2.05, 0.84, 0.62, 2.05, lower)
        mb.box(-0.84, 0.62, -2.05, 0.84, 0.92, 2.05, body)
        mb.box(-0.78, 0.92, -1.75, 0.78, 1.38, 0.55, body)                   # кабина
        mb.box(-0.79, 0.97, -1.6, 0.79, 1.32, 0.45, (40, 52, 62))           # стёкла вокруг
        mb.box(-0.86, 0.3, 2.05, 0.86, 0.5, 2.15, (30, 30, 30))            # пластиковые бамперы
        mb.box(-0.86, 0.3, -2.15, 0.86, 0.5, -2.05, (30, 30, 30))
        for x in (-0.6, 0.6):
            mb.box(x - 0.2, 0.62, 2.05, x + 0.2, 0.75, 2.07, (235, 235, 210))
            mb.box(x - 0.2, 0.62, -2.07, x + 0.2, 0.78, -2.05, (170, 25, 25))
        if police:
            mb.box(-0.5, 1.38, -0.4, 0.5, 1.42, 0.2, (240, 240, 240))
        Entity(parent=self.root, model=mb.build(), double_sided=True)
        self.siren = None
        if police:
            self.siren = Entity(parent=self.root, model="cube", position=(0, 1.5, -0.1), scale=(0.7, 0.12, 0.22),
                                color=color.rgb(40, 70, 160))
            t = Text("POLIZEI", parent=self.root, position=(0.86, 0.75, 0), rotation_y=-90, scale=6, origin=(0, 0),
                     color=color.rgb(30, 90, 60))
            t2 = Text("POLIZEI", parent=self.root, position=(-0.86, 0.75, 0), rotation_y=90, scale=6, origin=(0, 0),
                      color=color.rgb(30, 90, 60))
        self.wheels = []
        for x in (-0.76, 0.76):
            for z in (-1.3, 1.3):
                self.wheels.append(Entity(parent=self.root, model=wheel_mesh(0.3, 0.18, seg=10, rim=(150, 150, 150)),
                                          position=(x, 0.3, z), double_sided=True))
        self.spin = 0.0

    def update(self, dt, t):
        ai = self.ai
        self.root.position = Vec3(ai.x, 0, -ai.y)
        self.root.rotation_y = 90 + math.degrees(ai.angle)
        self.spin += ai.speed / 0.3 * dt
        for w in self.wheels:
            w.rotation_x = math.degrees(self.spin)
        if self.siren is not None:
            on = ai.siren > 0 and int(t * 6) % 2 == 0
            self.siren.color = color.rgb(90, 150, 255) if on else color.rgb(40, 70, 160)
            if on:
                self.siren.setLightOff()
            else:
                self.siren.clearLight()


# ====================================================================== брошенные машины
class Wreck3D:
    """Брошенная машина у дороги: выцветшая краска, ржавчина, мутные/битые стёкла, спущенные колёса."""

    def __init__(self, w):
        import random as _r
        from state import WRECK_MODELS
        rng = _r.Random(w["seed"])
        self.id = w["id"]
        self.root = Entity()
        L, W = w["len"], w["wid"]
        hl, hw = L / 2, W / 2
        base = WRECK_MODELS[w["model"]][5]
        fade = tuple(int(c * 0.75 + 45) for c in base)
        rust = w["rust"]
        mb = MeshBuilder()
        sink = 0.08 if rng.random() < 0.5 else 0.0          # спущенные колёса — машина «села»
        y0 = 0.26 - sink
        mb.box(-hw, y0, -hl, hw, 0.84 - sink, hl, fade)
        roof_back, roof_front = -hl * 0.55, hl * 0.18
        if w["model"] in ("golf", "trabant"):
            roof_back = -hl * 0.85                            # хэтчбеки — крыша почти до конца
        mb.box(-hw + 0.08, 0.84 - sink, roof_back, hw - 0.08, 1.34 - sink, roof_front, fade,
               top=tuple(max(0, c - 15) for c in fade))
        glass = (60, 70, 72) if rng.random() < 0.6 else (95, 105, 100)
        for side in (-1, 1):
            mb.box(side * (hw - 0.05), 0.9 - sink, roof_back + 0.15, side * (hw - 0.035), 1.28 - sink, roof_front - 0.1, glass)
        mb.box(-hw + 0.15, 0.9 - sink, roof_front + 0.01, hw - 0.15, 1.28 - sink, roof_front + 0.025, glass)
        mb.box(-hw + 0.2, 0.9 - sink, roof_back - 0.025, hw - 0.2, 1.26 - sink, roof_back - 0.01, glass)
        mb.box(-hw - 0.03, 0.30 - sink, hl, hw + 0.03, 0.42 - sink, hl + 0.08, (70, 70, 70))    # бамперы
        mb.box(-hw - 0.03, 0.30 - sink, -hl - 0.08, hw + 0.03, 0.42 - sink, -hl, (70, 70, 70))
        for x in (-hw + 0.25, hw - 0.25):
            mb.box(x - 0.13, 0.55 - sink, hl, x + 0.13, 0.7 - sink, hl + 0.02, (150, 150, 140))
            mb.box(x - 0.13, 0.55 - sink, -hl - 0.02, x + 0.13, 0.7 - sink, -hl, (110, 30, 25))
        # ржавчина: пятна по бортам, аркам и порогам
        rcols = [(135, 66, 28), (105, 48, 22), (80, 40, 20)]
        for _ in range(int(10 + 30 * rust)):
            side = rng.choice((-1, 1))
            z = rng.uniform(-hl + 0.1, hl - 0.1)
            y = (rng.uniform(0.34, 0.62) if rng.random() < 0.75 else rng.uniform(0.62, 0.78)) - sink
            s_ = rng.uniform(0.03, 0.09) * (0.7 + rust)
            x = side * (hw + 0.005)
            mb.box(x - 0.004, y - s_, z - s_ * 1.4, x + 0.004, y + s_, z + s_ * 1.4, rng.choice(rcols))
        for _ in range(int(8 + 25 * rust)):                    # на капоте и крыше
            z = rng.uniform(-hl + 0.2, hl - 0.2)
            x = rng.uniform(-hw + 0.1, hw - 0.1)
            s_ = rng.uniform(0.05, 0.14)
            top = 1.34 - sink if roof_back < z < roof_front else 0.84 - sink
            mb.box(x - s_, top, z - s_, x + s_, top + 0.006, z + s_, rng.choice(rcols))
        Entity(parent=self.root, model=mb.build(), double_sided=True)
        # колёса (некоторых нет)
        for x in (-hw + 0.1, hw - 0.1):
            for z in (-hl + 0.75, hl - 0.75):
                if rng.random() < 0.18:
                    continue
                e = Entity(parent=self.root, model=wheel_mesh(0.28, 0.16, seg=10, rim=(95, 90, 85)),
                           position=(x, 0.28 - sink * 0.7, z), double_sided=True)
                e.scale_y = 0.85 if sink else 1.0

    def update(self, w):
        self.root.position = Vec3(w["x"], 0, -w["y"])
        self.root.rotation_y = 90 + math.degrees(w["angle"])


class Rope3D:
    """Буксировочный трос — тонкая жёлтая полоса между машинами."""

    def __init__(self):
        self.e = Entity(model="cube", color=color.rgb(230, 190, 40), enabled=False)

    def set(self, a, b):
        if a is None:
            self.e.enabled = False
            return
        ax, ay = a
        bx, by = b
        mid = Vec3((ax + bx) / 2, 0.45, -(ay + by) / 2)
        d = math.hypot(bx - ax, by - ay)
        self.e.enabled = True
        self.e.position = mid
        self.e.rotation = Vec3(0, math.degrees(math.atan2(bx - ax, -(by - ay))), 0)
        self.e.scale = (0.035, 0.035, max(0.1, d))
