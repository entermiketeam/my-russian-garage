"""3D-квартира на Lindenstraße 7. Планировка — как в 2D (сантиметры), стоит вне карты."""
import math

from ursina import Entity, Text, color, scene
from panda3d.core import AmbientLight, DirectionalLight, LightAttrib

from mesh3d import MeshBuilder
from city3d import additive
import textures3d
from i18n import T

AX, AZ = -700.0, 700.0   # положение квартиры в 3D-мире
WALL_H = 2.6
W, H = 1100, 590

WALLS = [
    (0, 0, W, 12), (0, H - 12, W, 12), (0, 0, 12, H), (W - 12, 0, 12, H),
    (560, 0, 12, 160), (560, 260, 12, 40),
    (560, 300, 340, 12), (990, 300, 110, 12),
    (780, 300, 12, 120), (780, 500, 12, 90),
    (560, 300, 12, 60), (560, 440, 12, 150),
]

# key, подпись, прямоугольник (см), твёрдый
OBJECTS = [
    ("door", T("Выйти на улицу"), (12, 560, 80, 30), False),
    ("mail", T("Почта и счета"), (100, 555, 45, 25), True),
    ("keyhook", T("Ключница (запасные ключи)"), (12, 470, 14, 45), False),
    ("sofa", T("Диван (посидеть 1 ч)"), (40, 20, 220, 85), True),
    ("tv", T("Телевизор"), (380, 20, 110, 50), True),
    ("table", T("Стол (дела, счета)"), (230, 250, 150, 90), True),
    ("phone", T("Телефон"), (400, 530, 60, 45), True),
    ("shelf", T("Книжная полка"), (14, 200, 40, 180), True),
    ("fridge", T("Холодильник «Bosch»"), (1010, 14, 76, 70), True),
    ("stove", T("Плита"), (900, 14, 90, 60), True),
    ("sink", T("Раковина (кран)"), (800, 14, 90, 60), True),
    ("ktable", T("Кухонный стол"), (700, 160, 110, 80), True),
    ("bed", T("Кровать"), (950, 420, 136, 160), True),
    ("wardrobe", T("Шкаф"), (810, 312, 120, 50), True),
    ("calendar", T("Календарь"), (1070, 330, 16, 40), True),
    ("shower", T("Душ"), (574, 505, 95, 73), True),
    ("toilet", T("Туалет"), (705, 520, 55, 58), True),
    ("mirror", T("Зеркало и умывальник"), (590, 312, 70, 40), True),
]


def P(x, y, h=0.0):
    """Сантиметры квартиры -> 3D."""
    return (AX + x / 100.0, h, AZ - y / 100.0)


def box_cm(mb, x, y, w, d, h0, h1, col, **kw):
    x0, y0, z0 = P(x, y + d, h0)
    x1, y1, z1 = P(x + w, y, h1)
    mb.box(x0, y0, z0, x1, y1, z1, col, **kw)


class Apartment3D:
    def __init__(self):
        before = set(scene.children)
        self._build()
        # всё, что построили, — под один корень со своим светом (улица освещается отдельно)
        self.root = Entity()
        for e in list(scene.children):
            if e not in before and e is not self.root and isinstance(e, Entity):
                e.world_parent = self.root
        self.amb = AmbientLight("apt_amb")
        self.sun = DirectionalLight("apt_window_light")
        self.amb_np = self.root.attachNewNode(self.amb)
        self.sun_np = self.root.attachNewNode(self.sun)
        self.sun_np.setHpr(160, -35, 0)                  # свет из окон: с севера и чуть сверху
        self.root.setAttrib(LightAttrib.makeAllOff().addOnLight(self.amb_np).addOnLight(self.sun_np))
        self.views_ok = False

    def _build(self):
        mb = MeshBuilder()
        # полы
        floor = MeshBuilder(uv_tile=1.0)
        for (x, y, w, h), col in (((0, 0, 560, H), (138, 96, 62)), ((560, 0, 540, 300), (205, 200, 188)),
                                   ((560, 300, 220, H - 300), (170, 200, 208)), ((780, 300, 320, H - 300), (140, 128, 150))):
            x0, _, z0 = P(x, y + h)
            x1, _, z1 = P(x + w, y)
            floor.poly([(x0, 0.0, z0), (x1, 0.0, z0), (x1, 0.0, z1), (x0, 0.0, z1)], col, (0, 1, 0))
        # паркет: полоски
        for yy in range(0, H, 18):
            x0, _, z = P(0, yy)
            floor.poly([(x0, 0.003, z), (AX + 5.6, 0.003, z), (AX + 5.6, 0.003, z - 0.01), (x0, 0.003, z - 0.01)],
                       (110, 76, 50), (0, 1, 0))
        # ковёр
        box_cm(mb, 120, 150, 300, 200, 0.0, 0.012, (140, 40, 40))
        box_cm(mb, 135, 165, 270, 170, 0.012, 0.016, (170, 130, 60))
        box_cm(mb, 145, 175, 250, 150, 0.016, 0.02, (140, 40, 40))
        box_cm(mb, 200, 215, 140, 70, 0.02, 0.024, (70, 35, 70))
        # потолок
        x0, _, z0 = P(0, H)
        x1, _, z1 = P(W, 0)
        mb.poly([(x0, WALL_H, z0), (x1, WALL_H, z0), (x1, WALL_H, z1), (x0, WALL_H, z1)], (235, 232, 222), (0, -1, 0))
        # стены (с плинтусом)
        for (x, y, w, h) in WALLS:
            box_cm(mb, x, y, w, h, 0, WALL_H, (226, 220, 200))
            box_cm(mb, x - 1, y - 1, w + 2, h + 2, 0, 0.08, (120, 90, 60))
        # дверные коробки над проёмами
        for (x, y, w, h) in ((560, 160, 12, 100), (900, 300, 90, 12), (780, 420, 12, 80), (560, 360, 12, 80)):
            box_cm(mb, x, y, w, h, 2.1, WALL_H, (226, 220, 200))
        self._furniture(mb)
        self.static = Entity(model=mb.build(), double_sided=True)
        self.floor = Entity(model=floor.build(), texture=textures3d.detail(), double_sided=True)
        # окна (цвет неба меняется)
        self.windows = []
        for (x, y, w, face) in ((150, 12, 120, "n"), (700, 12, 90, "n"), (330, H - 12, 120, "s")):
            cx = x + w / 2
            px, _, pz = P(cx, y + (0.5 if face == "n" else -0.5))
            e = Entity(model="quad", position=(px, 1.55, pz), scale=(w / 100, 1.3),
                       rotation_y=0 if face == "n" else 180, color=color.rgb(160, 190, 230))
            e.setLightOff()
            fr = Entity(model="cube", position=(px, 1.55, pz + (0.01 if face == "n" else -0.01)),
                        scale=(w / 100 + 0.12, 1.42, 0.02), color=color.rgb(240, 240, 235))
            Entity(model="cube", position=(px, 0.88, pz - (0.08 if face == "n" else -0.08)), scale=(w / 100 + 0.3, 0.05, 0.2),
                   color=color.rgb(240, 240, 235))   # подоконник
            Entity(model="cube", position=(px, 1.55, pz - (0.005 if face == "n" else -0.005)), scale=(0.04, 1.3, 0.01),
                   color=color.rgb(240, 240, 235))
            self.windows.append(e)
        px, _, pz = P(W - 12.5, 490)
        e = Entity(model="quad", position=(px, 1.55, pz), rotation_y=90, scale=(1.0, 1.3), color=color.rgb(160, 190, 230))
        e.setLightOff()
        self.windows.append(e)
        # люстры
        for (x, y) in ((280, 280), (830, 150), (940, 450), (670, 420)):
            px, _, pz = P(x, y)
            Entity(model="cube", position=(px, WALL_H - 0.25, pz), scale=(0.02, 0.5, 0.02), color=color.dark_gray)
            lamp = Entity(model="sphere", position=(px, WALL_H - 0.55, pz), scale=0.3, color=color.rgb(255, 235, 190))
            lamp.setLightOff()
        # ТВ-экран (светится, когда смотрите)
        px, _, pz = P(435, 70.5)
        self.tv_screen = Entity(model="quad", position=(px, 0.84, pz), scale=(0.6, 0.42), rotation_y=180,
                                color=color.rgb(40, 48, 56))
        self.tv_screen.setLightOff()
        # календарь с датой
        px, _, pz = P(W - 12.5, 350)
        self.calendar = Text("", position=(px - 0.02, 1.5, pz), rotation_y=90, scale=4, origin=(0, 0),
                             color=color.rgb(20, 20, 20), background=True)
        self.calendar.background.color = color.rgb(245, 240, 225)
        # пятна дневного света на полу у окон
        self.light_patches = []
        for w_ in self.windows:
            fwd = w_.back
            p = Entity(model="quad", position=(w_.x + fwd.x * 0.9, 0.03, w_.z + fwd.z * 0.9), rotation_x=90,
                       rotation_y=w_.rotation_y, scale=(w_.scale_x * 1.1, 1.4), color=color.rgba(255, 245, 220, 0))
            additive(p)
            self.light_patches.append(p)
        self.root_entities = [self.static, self.floor, self.tv_screen, self.calendar] + self.windows

    def _furniture(self, mb):
        b = lambda *a, **k: box_cm(mb, *a, **k)
        # входная дверь (на южной стене)
        b(15, 575, 85, 3, 0, 2.05, (110, 75, 45))
        b(85, 573, 6, 2, 1.0, 1.05, (200, 190, 150))
        b(12, 540, 80, 30, 0, 0.012, (90, 70, 50))                         # коврик
        # ключница на стене у входа: дощечка с крючками
        b(12, 470, 3, 45, 1.35, 1.62, (120, 85, 55))
        for k in range(4):
            b(15, 475 + k * 10, 3, 2, 1.45, 1.48, (190, 190, 195))
            b(15, 475 + k * 10, 2, 3, 1.33, 1.45, (170, 150, 60))               # ключ на крючке
        # тумба и письма
        b(100, 555, 45, 25, 0, 0.5, (120, 90, 60))
        b(108, 560, 25, 15, 0.5, 0.52, (240, 235, 220))
        # диван
        b(40, 20, 220, 85, 0, 0.42, (95, 62, 50))
        b(40, 20, 220, 22, 0.42, 0.9, (90, 58, 48))
        b(40, 20, 22, 85, 0.42, 0.62, (90, 58, 48))
        b(238, 20, 22, 85, 0.42, 0.62, (90, 58, 48))
        # телевизор на тумбе (кинескоп!)
        b(380, 20, 110, 50, 0, 0.5, (70, 50, 38))
        b(400, 22, 70, 48, 0.5, 1.02, (28, 28, 30))
        # стол со стульями
        b(230, 250, 150, 90, 0.72, 0.76, (130, 92, 58))
        for lx, ly in ((234, 254), (372, 254), (234, 332), (372, 332)):
            b(lx, ly, 5, 5, 0, 0.72, (110, 78, 50))
        b(250, 270, 40, 28, 0.76, 0.765, (240, 240, 230))                 # бумаги
        for cx, cy in ((290, 345), (290, 205)):
            b(cx, cy, 40, 40, 0.42, 0.46, (120, 85, 55))
            b(cx, cy + (36 if cy > 250 else 0), 40, 4, 0.46, 0.95, (120, 85, 55))
        # телефон
        b(400, 530, 60, 45, 0, 0.7, (110, 80, 55))
        b(415, 540, 28, 22, 0.7, 0.8, (190, 40, 30))
        # полка с книгами
        b(14, 200, 40, 180, 0, 2.0, (110, 80, 55))
        for shelf in range(5):
            for k in range(10):
                col = ((k * 53) % 150 + 60, (k * 31 + shelf * 40) % 120 + 50, (k * 17 + shelf * 70) % 100 + 40)
                b(54, 205 + k * 17, 2, 14, 0.15 + shelf * 0.38, 0.45 + shelf * 0.38, col)
        # кухня
        b(1010, 14, 76, 70, 0, 1.8, (232, 232, 230))
        b(1010, 82, 76, 2, 1.1, 1.12, (160, 160, 160))
        b(900, 14, 90, 60, 0, 0.9, (80, 80, 84), top=(40, 40, 42))
        for cx in (915, 950):
            for cy in (22, 44):
                b(cx, cy, 22, 18, 0.9, 0.915, (20, 20, 20))
        b(800, 14, 90, 60, 0, 0.9, (230, 228, 220))
        b(815, 22, 60, 40, 0.86, 0.905, (150, 160, 170))
        b(842, 14, 6, 12, 0.9, 1.2, (190, 190, 195))
        b(700, 160, 110, 80, 0.72, 0.76, (200, 60, 60))                   # клеёнка
        for lx, ly in ((704, 164), (802, 164), (704, 232), (802, 232)):
            b(lx, ly, 4, 4, 0, 0.72, (150, 110, 70))
        b(740, 240, 36, 36, 0.42, 0.46, (150, 110, 70))
        b(740, 272, 36, 4, 0.46, 0.9, (150, 110, 70))
        # спальня
        b(950, 420, 136, 160, 0, 0.42, (100, 75, 55))
        b(955, 425, 126, 150, 0.42, 0.58, (235, 235, 235))
        b(965, 430, 106, 36, 0.58, 0.7, (245, 245, 245))
        b(952, 480, 132, 98, 0.58, 0.64, (90, 100, 140))
        b(950, 575, 136, 8, 0.42, 0.9, (100, 75, 55))
        b(810, 312, 120, 50, 0, 2.1, (105, 78, 52))
        b(868, 362, 3, 2, 0.9, 1.3, (60, 50, 40))
        # ванная
        b(574, 505, 95, 73, 0, 0.1, (220, 225, 230))
        for (x, y, w, d) in ((574, 505, 95, 2), (667, 505, 2, 73)):
            b(x, y, w, d, 0.1, 2.0, (170, 205, 225))
        b(610, 570, 10, 6, 1.8, 1.95, (190, 190, 195))
        b(705, 540, 50, 38, 0, 0.42, (245, 245, 245))
        b(705, 570, 50, 8, 0.42, 0.85, (245, 245, 245))
        b(595, 312, 60, 40, 0.8, 0.88, (245, 245, 245))
        b(590, 312, 70, 2, 1.15, 1.75, (190, 215, 235))                    # зеркало

    def set_visible(self, v):
        self.root.enabled = v
        self.calendar.enabled = v

    def update_env(self, darkness, rain, date_text, watching_tv=False, t=0.0, dim=1.0):
        """Свет в квартире: днём — из окон (зависит от погоды), вечером и ночью — лампы."""
        k = 1 - darkness
        day = k * dim
        lamp = min(1.0, darkness * 1.6)                  # вечером включают свет
        a = 0.32 + 0.3 * day + 0.3 * lamp
        self.amb.setColor((a * (1.0 if lamp > day else 0.93), a * 0.97, a * (0.86 if lamp > day else 1.0), 1))
        self.sun.setColor((0.55 * day, 0.56 * day, 0.6 * day, 1))
        for p in self.light_patches:
            p.color = color.rgba(255, 245, 220, int(70 * day))
        if not self.views_ok:                            # запасной вариант: стекло цвета неба
            c = (int(60 + 110 * k), int(70 + 130 * k), int(100 + 140 * k))
            if rain:
                c = tuple(int(v * 0.75) for v in c)
            for w in self.windows:
                w.color = color.rgb(*c)
        self.calendar.text = date_text
        if watching_tv:
            f = 0.6 + 0.4 * math.sin(t * 7) * math.sin(t * 3.1)
            self.tv_screen.color = color.rgb(int(90 * f), int(120 * f), int(170 * f))
        else:
            self.tv_screen.color = color.rgb(40, 48, 56)
