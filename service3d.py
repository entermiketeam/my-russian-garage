"""3D автосервиса «Kfz-Werkstatt Schmidt»: цех с воротами, подъёмники, верстак, шины, вывеска, парковка, механики."""
import math

from ursina import Entity, Text, color, Vec3

from mesh3d import MeshBuilder
from world import SERVICE_LOT, SERVICE_HALL, SERVICE_BAYS, SERVICE_DOORS, SERVICE_PARK, SERVICE_DOOR_PT
from streaming import mesh_group

H = 4.2                      # высота цеха


class _FakePed:
    """Фигурка механика в синем комбинезоне (та же модель, что у пешеходов)."""

    def __init__(self, i, x, y):
        self.i = 100 + i
        self.x, self.y, self.angle = x, y, 0.0
        self.speed = 0.0
        self.phase = 0.0
        self.down = 0.0
        self.looks = ((40, 70, 140), (40, 70, 140), (225, 185, 155), (90, 60, 30), 1.0)


class Service3D:
    def __init__(self, world):
        self.world = world
        mb = MeshBuilder()
        lx, ly, lw, lh = SERVICE_LOT
        mb.flat2d(lx, ly, lw, lh, 0.035, (96, 96, 98))                     # асфальт участка
        hx, hy, hw, hh = SERVICE_HALL
        mb.flat2d(hx, hy, hw, hh, 0.045, (150, 150, 145))                  # бетонный пол цеха
        wall = (205, 200, 185)
        for (wx, wy, ww, whh) in world.service_walls[:-1]:
            mb.box2d(wx, wy, ww, whh, 0, H, wall)
        # перемычки над воротами
        east = hx + hw
        for a, b in SERVICE_DOORS:
            mb.box2d(east, a, 0.3, b - a, 3.4, H, wall)
            mb.box2d(east + 0.02, a, 0.05, b - a, 3.25, 3.4, (230, 190, 40))          # жёлто-чёрная полоса
        # крыша (плоская, с парапетом)
        mb.box2d(hx - 0.4, hy - 0.4, hw + 0.8, hh + 0.8, H, H + 0.25, (90, 90, 95))
        # стойка приёмки, окно конторы
        ox, oy, ow, oh = SERVICE_HALL[0], SERVICE_HALL[1], 6.0, 2.8
        mb.box2d(ox, oy + oh, ow, 0.25, 0, 1.1, (120, 90, 60))
        mb.box2d(ox + 0.5, oy + 0.3, 1.2, 0.8, 0, 0.75, (90, 70, 50))                 # стол
        mb.box2d(ox + 0.6, oy + 0.4, 0.5, 0.4, 0.75, 1.05, (40, 40, 45))              # касса / телефон
        # ячейки: разметка, подъёмники (две стойки и лапы), яма
        for (bx, by, bw, bh) in SERVICE_BAYS:
            for fx, fy, fw, fh in ((bx, by, bw, 0.12), (bx, by + bh - 0.12, bw, 0.12)):
                mb.flat2d(fx, fy, fw, fh, 0.05, (230, 190, 40))
            for py in (by + 0.5, by + bh - 0.7):
                mb.box2d(bx + bw * 0.45, py, 0.3, 0.3, 0, 2.6, (40, 90, 160))           # стойки подъёмника
                mb.box2d(bx + bw * 0.45 - 1.0, py + (0.3 if py < by + 1 else -0.35), 2.3, 0.06, 0.05, 0.12, (60, 60, 60))
        # верстак, шкафы с инструментом, стеллаж с шинами, компрессор, бочки
        mb.box2d(hx + 0.2, hy + hh - 1.0, 5.5, 0.8, 0, 0.9, (110, 80, 50))
        for k in range(4):
            mb.box2d(hx + 6.2 + k * 1.1, hy + hh - 0.7, 1.0, 0.5, 0, 1.6, [(170, 30, 30), (40, 70, 140), (170, 30, 30), (60, 60, 60)][k])
        mb.box2d(hx + 0.2, hy + 3.4, 0.8, 5.5, 0, 2.2, (90, 70, 50))                   # стеллаж
        for k in range(6):
            mb.cylinder(hx + 0.6, 0.35 + (k % 3) * 0.7, -(hy + 4.2 + (k // 3) * 2.5), 0.32, 0.2, (25, 25, 25), seg=10)
        mb.box2d(hx + 0.3, hy + 12.5, 0.8, 0.8, 0, 1.0, (200, 40, 40))                 # компрессор
        for k in range(3):
            mb.cylinder(hx + 0.5 + k * 0.7, 0, -(hy + hh - 2.0), 0.3, 0.9, (40, 80, 50), seg=10)   # бочки с маслом
        # парковка: разметка мест
        for x, y, a in SERVICE_PARK:
            mb.flat2d(x - 2.6, y - 1.25, 0.1, 2.5, 0.05, (235, 235, 235))
            mb.flat2d(x + 2.5, y - 1.25, 0.1, 2.5, 0.05, (235, 235, 235))
        # вывеска на столбе у дороги
        mb.box2d(lx + lw - 1.0, ly + 1.0, 0.25, 0.25, 0, 5.0, (70, 70, 75))
        self.static = mesh_group(mb, "service", double_sided=True)
        sx, sy = lx + lw - 0.9, ly + 1.1
        self.sign = Entity(model="cube", position=(sx, 5.4, -sy), scale=(0.2, 1.3, 4.2), color=color.rgb(30, 60, 130))
        for side in (-1, 1):
            Text("Автосервис\nШмидта", parent=self.sign, position=(side * 0.6, 0.1, 0), rotation_y=-90 * side,
                 scale=(1 / 0.2 * 0.9, 1 / 1.3 * 0.9), origin=(0, 0), color=color.rgb(250, 250, 240))
        Text("ОБСЛУЖИВАНИЕ · РЕМОНТ · ПОДГОТОВКА К ТЕХОСМОТРУ", position=(east + 0.35, 3.75, -(hy + hh / 2)), rotation_y=-90,
             scale=6, origin=(0, 0), color=color.rgb(30, 60, 130))
        # механики
        from traffic3d import Ped3D
        self.mech = []
        for i, (x, y) in enumerate(((hx + 3.0, hy + 3.5), (hx + 6.0, hy + hh - 2.2))):
            fp = _FakePed(i, x, y)
            self.mech.append((fp, Ped3D(fp), (x, y)))
        self.t = 0.0

    def set_visible(self, v):
        self.static.enabled = v
        self.sign.enabled = v
        for fp, pv, home in self.mech:
            pv.root.enabled = v

    def update(self, dt, game):
        """Механики ходят вокруг машин в ремонте (капот открыт), иначе — у верстака."""
        self.t += dt
        working = [(k, c) for k, c in game.cars.items() if getattr(c, "service", None)]
        for i, (fp, pv, home) in enumerate(self.mech):
            if i < len(working):
                k, c = working[i]
                a = self.t * 0.35 + i * math.pi
                tx = c.x + math.cos(a) * 2.8
                ty = c.y + math.sin(a) * 1.8
                c3 = game.car3ds.get(k)
                if c3 is not None and not getattr(c3, "_svc_hood", False):
                    c3.set_hood(True)
                    c3._svc_hood = True
            else:
                tx, ty = home
            dx, dy = tx - fp.x, ty - fp.y
            d = math.hypot(dx, dy)
            if d > 0.2:
                sp = min(1.2, d * 2)
                fp.x += dx / d * sp * dt
                fp.y += dy / d * sp * dt
                fp.angle = math.atan2(dy, dx)
                fp.speed = sp
                fp.phase += sp * dt * 2.2
            else:
                fp.speed = 0.0
            pv.update(False)
