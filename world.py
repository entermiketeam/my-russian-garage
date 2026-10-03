"""Карта городка Kleinbruck (Нижняя Саксония, 1998). Все координаты в метрах."""
import math
import random
import pygame

from config import PPM, GRASS, ROAD, ROAD_LINE, SIDEWALK, WIDTH, HEIGHT, font
import places as _places
from places import INTERIOR_X, DEALER_LOT, PARKINGS, TG_ENTRANCES
from i18n import T, src

MAP_W, MAP_H = 1900, 1600

# (x, y, w, h, тип, название, ограничение км/ч или None)
ROADS = [
    (100, 300, 1210, 10, "town", T("Хауптштрассе"), 50),
    (1310, 300, 490, 10, "land", "L 342", 100),
    (300, 100, 10, 810, "town", T("Банхофштрассе"), 50),
    (300, 910, 10, 500, "land", "K 17", 80),
    (800, 100, 10, 810, "town", T("Индустриштрассе"), 50),
    (100, 700, 1210, 10, "town", T("Шульштрассе"), 50),
    (300, 100, 510, 10, "town", T("Ам-Вальд"), 30),
    (1300, 300, 10, 410, "town", T("Рингштрассе"), 50),
    (300, 1400, 1500, 10, "land", "K 17", 80),
    (1800, 0, 26, 1600, "autobahn", "A 7", None),
]

# Особые здания: id -> (x, y, w, h, название, цвет стен, цвет крыши, точка двери)
BUILDINGS = {
    "apartment": (318, 314, 44, 26, T("Жилой дом, Линденштрассе, 7"), (200, 190, 170), (150, 70, 55), (330, 312.5)),
    "imbiss": (255, 314, 38, 18, T("Дёнер-закусочная"), (210, 200, 150), (120, 60, 40), (274, 312.5)),
    "pizzeria": (316, 262, 40, 32, T("Пиццерия «У Луиджи»"), (220, 190, 150), (160, 60, 40), (336, 297)),
    "supermarkt": (400, 250, 70, 44, T("Супермаркет «Кауфгут»"), (190, 190, 195), (110, 110, 118), (435, 297)),
    "rathaus": (490, 244, 50, 50, T("Ратуша / регистрация машин"), (215, 200, 170), (130, 55, 45), (515, 297)),
    "autoteile": (560, 314, 40, 24, T("Запчасти «Восток»"), (170, 175, 160), (90, 95, 90), (580, 312.5)),
    "tanke": (690, 256, 30, 18, T("Заправка"), (220, 220, 220), (200, 40, 40), (705, 276)),
    "tuv": (840, 330, 50, 26, T("Техосмотр TÜV"), (200, 205, 215), (40, 80, 150), (865, 328)),
    "polizei": (1000, 250, 50, 44, T("Полицейский участок"), (205, 210, 200), (40, 110, 70), (1025, 297)),
    "lager": (825, 420, 110, 70, T("Склад транспортной фирмы Мюллера"), (160, 150, 130), (100, 100, 105), (821, 455)),
    "kirche": (150, 150, 30, 50, T("Церковь Святой Марии"), (190, 180, 160), (90, 90, 95), None),
    "bahnhof": (320, 60, 80, 36, T("Вокзал"), (180, 110, 90), (90, 60, 50), None),
    "schrott": (446, 347, 12, 6, T("Авторазборка Ковальского"), (120, 125, 110), (80, 80, 78), (452, 354.5)),
    "autohaus": (1110, 318, 56, 26, T("Автосалон Крюгера — Toyota"), (225, 225, 228), (170, 30, 30), (1138, 312.5)),
    "dealer": (1602, 318, 26, 14, T("Автоплощадка Вебера — покупка и продажа"), (235, 230, 215), (40, 90, 150), (1615, 316.0)),
}

AUTOHAUS_LOT = (1170, 316, 30, 26)   # площадка автосалона Toyota (декор)
PARKING2 = (377, 314, 7, 13)         # второе место у гаража (куда эвакуатор ставит вторую машину)

# Autoverwertung Kowalski — свалка/приём старых машин прямо за гаражом
JUNKYARD = (380, 344, 80, 88)        # территория за забором (расширена: ряды машин-доноров)
JUNK_LANE = (386, 310, 9, 35)        # проезд от Hauptstraße к воротам (между гаражом и домами)
SCRAP_DROP = (396, 378, 18, 16)      # площадка приёма лома у пресса
AE86_SPOT = (446.0, 390.0)           # тут стоит ржавая AE86
JUNK_FENCES = [(380, 344, 6, 0.3), (395, 344, 65, 0.3), (380, 344, 0.3, 88), (459.7, 344, 0.3, 88),
               (380, 431.7, 80, 0.3)]
# Заброшенные гаражи и сараи с забытыми машинами (места подбираются автоматически у дорог)
ABANDONED_NAMES = [
    (T("Заброшенный гараж деда Хайнца"), True),
    (T("Старый сарай фермера Мёллера"), False),
    (T("Бывшая автомастерская Брандта"), True),
    (T("Гараж у бывшего колхоза"), False),
    (T("Покосившийся гараж у дороги"), True),
    (T("Сарай за лесополосой"), False),
]
AG_W, AG_D = 7.2, 12.0      # ширина и глубина заброшенного гаража (м)

JUNK_PILES = [(381, 352, 3.5, 22), (381, 378, 3.5, 17), (452, 358, 6.5, 24), (452, 398, 6.5, 26),
              (381, 398, 3.2, 28), (416, 380, 6, 8)]

GARAGE_ZONE = pygame.Rect(0, 0, 0, 0)  # заполняется ниже (в «метрах»)
GARAGE = (366, 314, 9, 13)
GARAGE_WALLS = [(365, 314, 1, 14), (375, 314, 1, 14), (365, 327, 11, 1)]
PUMP_ZONE = (680, 278, 90, 18)
PUMPS = [(704, 285, 2, 4), (734, 285, 2, 4), (754, 285, 2, 4)]
TUV_YARD = (830, 314, 70, 15)

# Автосервис «Kfz-Werkstatt Schmidt» на Industriestraße (западная сторона): цех на 2 ячейки воротами к дороге,
# подъезд, парковка, офис. Ставится после генерации города (город не сдвигается, с участка убирается один дом).
SERVICE_LOT = (763, 450, 34, 28)
SERVICE_HALL = (766, 452, 17, 24)                    # цех: стены по периметру, ворота на восточной стене
SERVICE_BAYS = [(769, 455.5, 12.5, 7.5), (769, 465.0, 12.5, 7.5)]    # ремонтные ячейки внутри цеха
SERVICE_DOORS = [(456.5, 462.0), (466.0, 471.5)]    # проёмы ворот (по y) в восточной стене x = 783
SERVICE_PARK = [(789.0, 452.8, 0.0), (794.5, 452.8, 0.0), (789.0, 475.2, 0.0), (794.5, 475.2, 0.0)]
SERVICE_OFFICE = (766, 452, 17, 2.8)                # приёмка — северная часть цеха (за стойкой)
SERVICE_DOOR_PT = (785.5, 464.0)                    # где стоит мастер-приёмщик (у ворот, между ячейками)

BLITZER = [(600, 312, 50), (1550, 312, 100), (312, 1100, 80)]

AI_LOOPS = [
    [(305, 305), (805, 305), (805, 705), (305, 705)],
    [(305, 305), (1813, 305), (1813, 1405), (305, 1405)],
    [(305, 105), (805, 105), (805, 305), (305, 305)],
    [(805, 705), (1305, 705), (1305, 305), (805, 305)],
]
AI_COLORS = [(200, 200, 205), (40, 60, 120), (150, 20, 20), (30, 30, 30), (230, 210, 60),
             (60, 110, 60), (170, 170, 175), (110, 70, 40)]


def rect_overlap(a, b, margin=0.0):
    return (a[0] - margin < b[0] + b[2] and b[0] - margin < a[0] + a[2] and
            a[1] - margin < b[1] + b[3] and b[1] - margin < a[1] + a[3])


def point_in(r, x, y):
    return r[0] <= x <= r[0] + r[2] and r[1] <= y <= r[1] + r[3]


class AICar:
    def __init__(self, loop, idx, color, police=False, rng=None):
        self.loop = loop
        self.idx = (idx + 1) % len(loop)
        self.x, self.y = loop[idx]
        self.angle = 0.0
        self.speed = 0.0
        self.color = color
        self.police = police
        self.check_cd = 0.0
        self.siren = 0.0
        self.stuck = 0.0
        self.overtake = 0.0     # объезд препятствия (стоящая машина игрока и т.п.)

    def seg_offset(self, i):
        a = self.loop[i - 1]
        b = self.loop[i]
        dx, dy = b[0] - a[0], b[1] - a[1]
        d = math.hypot(dx, dy) or 1
        return -dy / d, dx / d  # правая сторона (правостороннее движение)

    def target(self):
        rx, ry = self.seg_offset(self.idx)
        wx, wy = self.loop[self.idx]
        ax = self.loop[self.idx - 1][0]
        off = 5.5 if abs(wx - 1813) < 1 and abs(ax - 1813) < 1 else 2.5
        if self.overtake > 0:
            off -= 4.5          # уходим на встречную полосу, чтобы объехать
        return wx + rx * off, wy + ry * off

    def update(self, dt, world, player_car, others):
        players = player_car if isinstance(player_car, (list, tuple)) else [player_car]
        self.overtake = max(0.0, self.overtake - dt)
        tx, ty = self.target()
        dx, dy = tx - self.x, ty - self.y
        dist = math.hypot(dx, dy)
        if dist < 6:
            self.idx = (self.idx + 1) % len(self.loop)
            return
        desired = math.atan2(dy, dx)
        da = (desired - self.angle + math.pi) % (2 * math.pi) - math.pi
        self.angle += max(-1.6 * dt, min(1.6 * dt, da * 3 * dt)) if self.speed > 1 else da * min(1, dt * 3)
        limit = world.speed_limit(self.x, self.y) or 36
        target_v = limit / 3.6 * 0.95
        if dist < 30:
            target_v = min(target_v, 7.0)
        # не врезаться в машину впереди
        fx, fy = math.cos(self.angle), math.sin(self.angle)
        blocked = False
        for o in others + list(players):
            if o is self:
                continue
            ox, oy = o.x - self.x, o.y - self.y
            if abs(ox) > 16 or abs(oy) > 16:
                continue
            ahead = ox * fx + oy * fy
            side = abs(-ox * fy + oy * fx)
            if 0 < ahead < 14 and side < 2.2:
                target_v = min(target_v, max(0, (ahead - 6) * 0.8))
                blocked = blocked or (o in players and abs(getattr(o, "speed", 0)) < 1.0)
        # стоим за неподвижной машиной игрока больше 4 с — объезжаем по встречке
        self.stuck = self.stuck + dt if blocked and self.speed < 1.0 else 0.0
        if self.stuck > 4.0:
            self.overtake = 7.0
            self.stuck = 0.0
        if self.overtake > 0:
            target_v = max(target_v, 4.0)
        if self.police and self.siren > 0:
            target_v = 0
        self.speed += max(-7 * dt, min(2.5 * dt, target_v - self.speed))
        self.x += fx * self.speed * dt
        self.y += fy * self.speed * dt

    def draw(self, surf, cam, t):
        L, W = 4.2 * PPM, 1.7 * PPM
        img = pygame.Surface((int(L), int(W)), pygame.SRCALPHA)
        pygame.draw.rect(img, self.color, (0, 0, int(L), int(W)), border_radius=4)
        pygame.draw.rect(img, (40, 50, 60), (int(L * 0.55), 2, int(L * 0.14), int(W) - 4))
        pygame.draw.rect(img, (40, 50, 60), (int(L * 0.12), 3, int(L * 0.1), int(W) - 6))
        if self.police:
            pygame.draw.rect(img, (240, 240, 240), (int(L * 0.25), 2, int(L * 0.3), int(W) - 4))
            on = int(t * 6) % 2 == 0 and self.siren > 0
            pygame.draw.rect(img, (60, 120, 255) if on else (30, 50, 120), (int(L * 0.38), 3, 4, int(W) - 6))
        pygame.draw.rect(img, (240, 240, 210), (int(L) - 3, 2, 3, 4))
        pygame.draw.rect(img, (240, 240, 210), (int(L) - 3, int(W) - 6, 3, 4))
        rot = pygame.transform.rotate(img, -math.degrees(self.angle))
        sx = (self.x - cam[0]) * PPM
        sy = (self.y - cam[1]) * PPM
        surf.blit(rot, rot.get_rect(center=(sx, sy)))


class World:
    def __init__(self):
        rng = random.Random(1998)
        self.solids = []  # прямоугольники (x, y, w, h)
        self.houses = []  # (x, y, w, h, wall, roof, door)
        for b in BUILDINGS.values():
            self.solids.append(b[:4])
        self.solids += GARAGE_WALLS + PUMPS + JUNK_FENCES + JUNK_PILES
        reserved = [b[:4] for b in BUILDINGS.values()] + [GARAGE, PUMP_ZONE, TUV_YARD,
                                                          (360, 310, 38, 36), AUTOHAUS_LOT, JUNKYARD]
        reserved += _places.reserved_rects()
        # декоративные дома вдоль городских дорог
        roofs = [(150, 70, 55), (130, 55, 45), (95, 90, 95), (160, 85, 60), (110, 60, 50)]
        walls = [(220, 210, 190), (200, 190, 170), (230, 225, 210), (190, 175, 160), (215, 205, 180)]
        for r in ROADS:
            x, y, w, h, kind = r[:5]
            if kind == "autobahn":
                continue
            horiz = w > h
            length = w if horiz else h
            pos = 8.0
            gap = 4.0 if kind == "town" else 30.0
            while pos < length - 12:
                hw = rng.uniform(10, 16)
                hd = rng.uniform(9, 14)
                for side in (-1, 1):
                    if kind != "town" and rng.random() < 0.7:
                        continue
                    if horiz:
                        hx = x + pos
                        hy = y - 4 - hd if side < 0 else y + h + 4
                        door = (hx + hw / 2, hy + hd + 1.5 if side < 0 else hy - 1.5)
                    else:
                        hy = y + pos
                        hx = x - 4 - hw if side < 0 else x + w + 4
                        door = (hx + hw + 1.5 if side < 0 else hx - 1.5, hy + hd / 2)
                    cand = (hx, hy, hw, hd)
                    if hx < 5 or hy < 5 or hx + hw > MAP_W - 5 or hy + hd > MAP_H - 5:
                        continue
                    if any(rect_overlap(cand, rr[:4], 3.5) for rr in ROADS):
                        continue
                    if any(rect_overlap(cand, rr, 3) for rr in reserved + [hh[:4] for hh in self.houses]):
                        continue
                    self.houses.append((hx, hy, hw, hd, rng.choice(walls), rng.choice(roofs), door))
                pos += hw + gap
        for hh in self.houses:
            self.solids.append(hh[:4])
        # заброшенные гаражи — до деревьев, чтобы деревья не выросли внутри
        self.abandoned = self._place_abandoned(reserved)
        for ag in self.abandoned:
            self.solids += ag["walls"]
            reserved.append((ag["rect"][0] - 2, ag["rect"][1] - 2, ag["rect"][2] + 4, ag["rect"][3] + 4))
            reserved.append(ag["apron"])
        self.reset_doors()
        # подземные гаражи (въезды), парковки, площадка Weber — до деревьев
        self.places = _places.Places(self)
        reserved += [e["rect"] for e in TG_ENTRANCES] + [pp["rect"] for pp in PARKINGS] + [DEALER_LOT]
        # деревья
        self.trees = []
        tries = 0
        while len(self.trees) < 900 and tries < 20000:
            tries += 1
            tx, ty = rng.uniform(0, MAP_W), rng.uniform(0, MAP_H)
            r = rng.uniform(1.5, 3.2)
            box = (tx - r, ty - r, 2 * r, 2 * r)
            if any(rect_overlap(box, rr[:4], 4) for rr in ROADS):
                continue
            if any(rect_overlap(box, s, 2) for s in self.solids + reserved):
                continue
            self.trees.append((tx, ty, r, rng.randint(0, 2)))
        # места у загородных дорог, где бросают старые машины
        self.nospawn = [pp["rect"] for pp in PARKINGS] + [DEALER_LOT, JUNKYARD] + [e["rect"] for e in TG_ENTRANCES] + \
            [ag["apron"] for ag in self.abandoned] + [ag["rect"] for ag in self.abandoned]
        self.wreck_spots = []
        for r in ROADS:
            x, y, w, h, kind = r[:5]
            if kind != "land":
                continue
            horiz = w > h
            length = w if horiz else h
            for pos in range(40, int(length) - 20, 70):
                for side in (-1, 1):
                    if horiz:
                        px, py = x + pos, (y - 7 if side < 0 else y + h + 7)
                    else:
                        px, py = (x - 7 if side < 0 else x + w + 7), y + pos
                    if px < 20 or py < 20 or px > MAP_W - 20 or py > MAP_H - 20:
                        continue
                    if any(rect_overlap((px - 3, py - 3, 6, 6), rr[:4], 1.5) for rr in ROADS):
                        continue
                    if any(rect_overlap((px - 3, py - 3, 6, 6), s_, 2) for s_ in self.solids):
                        continue
                    if any(math.hypot(px - tx, py - ty) < tr + 3.5 for tx, ty, tr, _ in self.trees):
                        continue
                    if any(rect_overlap((px - 3, py - 3, 6, 6), nz, 3) for nz in self.nospawn):
                        continue
                    self.wreck_spots.append((px, py, 0.0 if horiz else math.pi / 2))

        # места у домов в городе: во дворе, у стены, на обочине участка
        hr = random.Random(5150)
        self.house_spots = []
        for i, hh in enumerate(self.houses):
            if i % 4:
                continue
            hx, hy, hw, hhh = hh[:4]
            cands = [(hx - 5.5, hy + hhh / 2, math.pi / 2), (hx + hw + 5.5, hy + hhh / 2, math.pi / 2),
                     (hx + hw / 2, hy - 5.5, 0.0), (hx + hw / 2, hy + hhh + 5.5, 0.0)]
            hr.shuffle(cands)
            for px, py, a in cands:
                if px < 20 or py < 20 or px > MAP_W - 20 or py > MAP_H - 20:
                    continue
                if any(rect_overlap((px - 3, py - 3, 6, 6), rr[:4], 1.5) for rr in ROADS):
                    continue
                if any(rect_overlap((px - 3, py - 3, 6, 6), s_, 1.0) for s_ in self.solids):
                    continue
                if any(math.hypot(px - tx, py - ty) < tr + 3.5 for tx, ty, tr, _ in self.trees):
                    continue
                if any(rect_overlap((px - 3, py - 3, 6, 6), nz, 3) for nz in self.nospawn):
                    continue
                if any(rect_overlap((px - 3, py - 3, 6, 6), rr, 2) for rr in reserved):
                    continue
                self.house_spots.append((px, py, a))
                break
        self.road_spots = list(self.wreck_spots)
        self.wreck_spots += self.house_spots

        # пятна травы / поля
        self.fields = []
        for _ in range(60):
            fx, fy = rng.uniform(0, MAP_W), rng.uniform(0, MAP_H)
            fw, fh = rng.uniform(40, 160), rng.uniform(40, 160)
            col = rng.choice([(86, 118, 60), (100, 120, 62), (120, 110, 70), (70, 100, 52)])
            self.fields.append((fx, fy, fw, fh, col))
        # фонари
        self.lamps = []
        for r in ROADS:
            x, y, w, h, kind = r[:5]
            if kind != "town":
                continue
            if w > h:
                for px in range(int(x) + 10, int(x + w), 35):
                    self.lamps.append((px, y - 2))
            else:
                for py in range(int(y) + 10, int(y + h), 35):
                    self.lamps.append((x + w + 2, py))
        self.lamps += [(700, 287), (740, 287), (860, 320)]
        # пересечения (чтобы разметка не шла через перекрёсток)
        self.crossings = []
        for i, a in enumerate(ROADS):
            for b in ROADS[i + 1:]:
                if rect_overlap(a[:4], b[:4]):
                    x0 = max(a[0], b[0]); y0 = max(a[1], b[1])
                    x1 = min(a[0] + a[2], b[0] + b[2]); y1 = min(a[1] + a[3], b[1] + b[3])
                    self.crossings.append((x0, y0, x1 - x0, y1 - y0))
        self.delivery_points = [h[6] for h in self.houses]
        self._labels = {}
        # трафик
        self.ai = []
        for i in range(14):
            loop = AI_LOOPS[i % len(AI_LOOPS)]
            c = AICar(loop, rng.randrange(len(loop)), rng.choice(AI_COLORS))
            self.ai.append(c)
        self.police = AICar(AI_LOOPS[0], 2, (40, 110, 70), police=True)
        self.ai.append(self.police)
        self._spread_ai(rng)
        self._place_service()

    def _place_service(self):
        """Автосервис: убрать то, что стоит на участке (после генерации — остальной город не меняется), поставить стены."""
        lot = SERVICE_LOT

        def inside(x, y, pad=2.0):
            return lot[0] - pad <= x <= lot[0] + lot[2] + pad and lot[1] - pad <= y <= lot[1] + lot[3] + pad
        gone = [h for h in self.houses if rect_overlap(h[:4], lot, 2)]
        self.houses = [h for h in self.houses if h not in gone]
        self.solids = [s_ for s_ in self.solids if not any(s_ == g[:4] for g in gone)]
        self.trees = [t for t in self.trees if not inside(t[0], t[1], t[2] + 1)]
        for name in ("house_spots", "wreck_spots", "road_spots"):
            setattr(self, name, [sp for sp in getattr(self, name) if not inside(sp[0], sp[1], 4)])
        self.delivery_points = [h[6] for h in self.houses]
        hx, hy, hw, hh = SERVICE_HALL
        east = hx + hw
        walls = [(hx - 0.3, hy - 0.3, hw + 0.6, 0.3), (hx - 0.3, hy + hh, hw + 0.6, 0.3), (hx - 0.3, hy - 0.3, 0.3, hh + 0.6)]
        # восточная стена с двумя проёмами ворот
        ys = [hy - 0.3]
        for a, b in SERVICE_DOORS:
            ys += [a, b]
        ys.append(hy + hh + 0.3)
        for i in range(0, len(ys), 2):
            walls.append((east, ys[i], 0.3, ys[i + 1] - ys[i]))
        walls.append((hx, hy + SERVICE_OFFICE[3], 6.0, 0.25))      # стойка приёмки (низкая стенка)
        self.service_walls = walls
        self.solids += walls

    def _spread_ai(self, rng):
        for c in self.ai:
            a = c.loop[c.idx - 1]
            b = c.loop[c.idx]
            t = rng.random()
            c.x = a[0] + (b[0] - a[0]) * t
            c.y = a[1] + (b[1] - a[1]) * t
            c.angle = math.atan2(b[1] - a[1], b[0] - a[0])

    # -------------------------------------------------------------- заброшенные гаражи
    def _place_abandoned(self, reserved):
        """Ищет места у дорог (подальше от домов и друг от друга) и строит гаражи воротами к дороге."""
        rng = random.Random(77)
        cands = []
        for r in ROADS:
            x, y, w, h, kind = r[:5]
            if kind == "autobahn" or src(r[5]) == "Ам-Вальд":
                continue
            horiz = w > h
            length = w if horiz else h
            for pos in range(30, int(length) - 30, 25):
                for side in (-1, 1):
                    if horiz:
                        gx = x + pos
                        if side < 0:
                            rect, door = (gx, y - 8 - AG_D, AG_W, AG_D), "s"
                        else:
                            rect, door = (gx, y + h + 8, AG_W, AG_D), "n"
                    else:
                        gy = y + pos
                        if side < 0:
                            rect, door = (x - 8 - AG_D, gy, AG_D, AG_W), "e"
                        else:
                            rect, door = (x + w + 8, gy, AG_D, AG_W), "w"
                    cands.append((rect, door, r[5]))
        rng.shuffle(cands)
        chosen = []
        blockers = [hh[:4] for hh in self.houses] + list(self.solids) + list(reserved)
        for rect, door, road in cands:
            gx, gy, gw, gh = rect
            if gx < 15 or gy < 15 or gx + gw > MAP_W - 15 or gy + gh > MAP_H - 15:
                continue
            if any(rect_overlap(rect, rr[:4], 4) for rr in ROADS):
                continue
            if any(rect_overlap(rect, b, 5) for b in blockers):
                continue
            cx, cy = gx + gw / 2, gy + gh / 2
            if any(math.hypot(cx - c["cx"], cy - c["cy"]) < 220 for c in chosen):
                continue
            if math.hypot(cx - 370, cy - 320) < 150:      # не у самого дома
                continue
            chosen.append({"rect": rect, "door": door, "road": road, "cx": cx, "cy": cy})
            if len(chosen) >= len(ABANDONED_NAMES):
                break
        out = []
        for i, c in enumerate(chosen):
            name, locked = ABANDONED_NAMES[i]
            out.append(self._make_abandoned(f"a{i + 1}", name, locked, c["rect"], c["door"], c["road"]))
        return out

    @staticmethod
    def _make_abandoned(gid, name, locked, rect, door, road):
        gx, gy, gw, gh = rect
        t = 0.3
        # стены: две боковые, задняя; ворота — на стороне door
        if door in ("n", "s"):
            side_walls = [(gx, gy, t, gh), (gx + gw - t, gy, t, gh)]
            if door == "n":
                back = (gx, gy + gh - t, gw, t)
                door_rect = (gx + t, gy, gw - 2 * t, t)
                dp = (gx + gw / 2, gy - 1.6)
                shelf = (gx + 0.5, gy + gh - 1.0, gw - 1.0, 0.6)
                shelf_pt = (gx + gw / 2, gy + gh - 1.9)
                angle = -math.pi / 2
                apron = (gx - 1, gy - 8, gw + 2, 8)
            else:
                back = (gx, gy, gw, t)
                door_rect = (gx + t, gy + gh - t, gw - 2 * t, t)
                dp = (gx + gw / 2, gy + gh + 1.6)
                shelf = (gx + 0.5, gy + 0.4, gw - 1.0, 0.6)
                shelf_pt = (gx + gw / 2, gy + 1.9)
                angle = math.pi / 2
                apron = (gx - 1, gy + gh, gw + 2, 8)
            walls = side_walls + [back]
        else:
            side_walls = [(gx, gy, gw, t), (gx, gy + gh - t, gw, t)]
            if door == "w":
                back = (gx + gw - t, gy, t, gh)
                door_rect = (gx, gy + t, t, gh - 2 * t)
                dp = (gx - 1.6, gy + gh / 2)
                shelf = (gx + gw - 1.0, gy + 0.5, 0.6, gh - 1.0)
                shelf_pt = (gx + gw - 1.9, gy + gh / 2)
                angle = math.pi
                apron = (gx - 8, gy - 1, 8, gh + 2)
            else:
                back = (gx, gy, t, gh)
                door_rect = (gx + gw - t, gy + t, t, gh - 2 * t)
                dp = (gx + gw + 1.6, gy + gh / 2)
                shelf = (gx + 0.4, gy + 0.5, 0.6, gh - 1.0)
                shelf_pt = (gx + 1.9, gy + gh / 2)
                angle = 0.0
                apron = (gx + gw, gy - 1, 8, gh + 2)
            walls = side_walls + [back]
        return {"id": gid, "name": name, "locked": locked, "rect": rect, "door": door, "road": road,
                "walls": walls + [shelf], "door_rect": door_rect, "door_pt": dp, "shelf_pt": shelf_pt,
                "shelf": shelf, "car_spot": (gx + gw / 2, gy + gh / 2), "car_angle": angle, "apron": apron}

    def reset_doors(self):
        """Все ворота закрыты (новая игра)."""
        for ag in self.abandoned:
            if ag["door_rect"] not in self.solids:
                self.solids.append(ag["door_rect"])

    def open_door(self, gid):
        for ag in self.abandoned:
            if ag["id"] == gid and ag["door_rect"] in self.solids:
                self.solids.remove(ag["door_rect"])

    def abandoned_by_id(self, gid):
        for ag in self.abandoned:
            if ag["id"] == gid:
                return ag
        return None

    def abandoned_at(self, x, y):
        for ag in self.abandoned:
            if point_in(ag["rect"], x, y):
                return ag
        return None

    # -------------------------------------------------------------- запросы
    def road_at(self, x, y):
        for r in ROADS:
            if point_in(r, x, y):
                return r
        return None

    def speed_limit(self, x, y):
        r = self.road_at(x, y)
        return r[6] if r else 30

    def on_road(self, x, y):
        return self.road_at(x, y) is not None

    _GRID = 16.0

    def _solid_grid(self):
        """Сетка препятствий 16 м (пересобирается, если список препятствий поменялся — ворота гаражей и т.п.)."""
        key = (len(self.solids), id(self.solids[-1]) if self.solids else 0, len(self.trees))
        if getattr(self, "_grid_key", None) == key:
            return self._grid_s, self._grid_t
        G = self._GRID
        gs, gt = {}, {}
        for i, s_ in enumerate(self.solids):
            for gx in range(int(s_[0] // G), int((s_[0] + s_[2]) // G) + 1):
                for gy in range(int(s_[1] // G), int((s_[1] + s_[3]) // G) + 1):
                    gs.setdefault((gx, gy), []).append(i)
        for i, (tx, ty, tr, _) in enumerate(self.trees):
            gt.setdefault((int(tx // G), int(ty // G)), []).append(i)
        self._grid_s, self._grid_t, self._grid_key = gs, gt, key
        return gs, gt

    def collide_circle(self, x, y, rad):
        """Возвращает вектор выталкивания (nx, ny, глубина) или None."""
        if x >= INTERIOR_X - 50:
            return self._collide_interior(x, y, rad)
        gs, gt = self._solid_grid()
        G = self._GRID
        cells = [(gx, gy) for gx in range(int((x - rad - 4) // G), int((x + rad + 4) // G) + 1)
                 for gy in range(int((y - rad - 4) // G), int((y + rad + 4) // G) + 1)]
        idx = sorted({i for cell in cells for i in gs.get(cell, ())})
        solids = self.solids
        for s in (solids[i] for i in idx):
            if x + rad < s[0] or x - rad > s[0] + s[2] or y + rad < s[1] or y - rad > s[1] + s[3]:
                continue
            cx = min(max(x, s[0]), s[0] + s[2])
            cy = min(max(y, s[1]), s[1] + s[3])
            dx, dy = x - cx, y - cy
            d = math.hypot(dx, dy)
            if d < rad:
                along = s[3] if abs(dx) > abs(dy) else s[2]       # ширина препятствия поперёк удара
                self.last_hit = ("pole" if min(s[2], s[3]) < 0.8 else "wall", along)
                if d < 1e-6:        # центр внутри препятствия — выталкиваем к ближайшему краю
                    edges = [(x - s[0], -1.0, 0.0), (s[0] + s[2] - x, 1.0, 0.0),
                             (y - s[1], 0.0, -1.0), (s[1] + s[3] - y, 0.0, 1.0)]
                    e_ = min(edges)
                    return (e_[1], e_[2], e_[0] + rad)
                return (dx / d, dy / d, rad - d)
        tidx = sorted({i for cell in cells for i in gt.get(cell, ())})
        trees = self.trees
        for tx, ty, tr, _ in (trees[i] for i in tidx):
            if abs(x - tx) > rad + tr or abs(y - ty) > rad + tr:
                continue
            dx, dy = x - tx, y - ty
            d = math.hypot(dx, dy)
            lim = rad + tr * 0.35
            if d < lim and d > 1e-6:
                self.last_hit = ("pole", tr * 0.7)                 # ствол дерева
                return (dx / d, dy / d, lim - d)
        if x - rad < 0:
            return (1, 0, rad - x)
        if y - rad < 0:
            return (0, 1, rad - y)
        if x + rad > MAP_W:
            return (-1, 0, x + rad - MAP_W)
        if y + rad > MAP_H:
            return (0, -1, y + rad - MAP_H)
        return None

    last_hit = ("wall", 3.0)

    def _collide_interior(self, x, y, rad):
        for s_ in self.places.interior_solids:
            if x + rad < s_[0] or x - rad > s_[0] + s_[2] or y + rad < s_[1] or y - rad > s_[1] + s_[3]:
                continue
            cx = min(max(x, s_[0]), s_[0] + s_[2])
            cy = min(max(y, s_[1]), s_[1] + s_[3])
            dx, dy = x - cx, y - cy
            d = math.hypot(dx, dy)
            if d < rad:
                if d < 1e-6:
                    return (0.0, -1.0, rad)
                return (dx / d, dy / d, rad - d)
        return None

    def level_at(self, x, y):
        return self.places.level_at(x, y)

    def zone_of(self, x, y):
        if point_in(GARAGE, x, y):
            return "garage"
        if point_in(PARKING2, x, y):
            return "parking"
        if point_in(SCRAP_DROP, x, y):
            return "scrap_drop"
        if point_in(PUMP_ZONE, x, y):
            return "pumps"
        if point_in(TUV_YARD, x, y):
            return "tuv_yard"
        return None

    def update_ai(self, dt, player_car, center=None, radius=None):
        """player_car — машина игрока или список всех машин игрока (их трафик объезжает).
        center/radius — трафик дальше radius от игрока стоит на паузе (его всё равно не видно)."""
        for c in self.ai:
            if center is not None and radius and abs(c.x - center[0]) + abs(c.y - center[1]) > radius:
                continue
            c.update(dt, self, player_car, self.ai)

    # -------------------------------------------------------------- отрисовка
    def label(self, s, size=14, color=(20, 20, 20)):
        key = (s, size, color)
        if key not in self._labels:
            self._labels[key] = font(size, True).render(s, True, color)
        return self._labels[key]

    def draw(self, surf, cam, night=0.0):
        cx, cy = cam
        vw, vh = WIDTH / PPM, HEIGHT / PPM
        view = (cx - 5, cy - 5, vw + 10, vh + 10)

        def R(r):
            return pygame.Rect(int((r[0] - cx) * PPM), int((r[1] - cy) * PPM),
                               int(math.ceil(r[2] * PPM)), int(math.ceil(r[3] * PPM)))

        surf.fill(GRASS)
        for f in self.fields:
            if rect_overlap(f[:4], view):
                pygame.draw.rect(surf, f[4], R(f[:4]))
        # тротуары
        for r in ROADS:
            if r[4] == "town" and rect_overlap(r[:4], view, 3):
                pygame.draw.rect(surf, SIDEWALK, R((r[0] - 2.5, r[1] - 2.5, r[2] + 5, r[3] + 5)))
        # дворы
        for z, col in ((PUMP_ZONE, (85, 85, 90)), (TUV_YARD, (95, 95, 100)), (GARAGE, (70, 70, 72)),
                       ((356, 310, 24, 4), (80, 80, 82))):
            if rect_overlap(z, view):
                pygame.draw.rect(surf, col, R(z))
        # асфальт
        for r in ROADS:
            if rect_overlap(r[:4], view):
                pygame.draw.rect(surf, ROAD if r[4] != "land" else (66, 66, 68), R(r[:4]))
        # разметка
        for r in ROADS:
            if not rect_overlap(r[:4], view):
                continue
            x, y, w, h, kind = r[:5]
            horiz = w > h
            if kind == "autobahn":
                mid = x + w / 2
                pygame.draw.rect(surf, (120, 120, 120), R((mid - 0.6, y, 1.2, h)))
                for lx in (x + 6.5, x + w - 6.5):
                    for yy in range(int(max(y, cy - 10)), int(min(y + h, cy + vh + 10)), 12):
                        pygame.draw.rect(surf, ROAD_LINE, R((lx - 0.1, yy, 0.2, 6)))
                for lx in (x + 0.8, x + w - 0.8):
                    pygame.draw.rect(surf, ROAD_LINE, R((lx - 0.1, y, 0.2, h)))
                continue
            if horiz:
                mid = y + h / 2
                start, end = int(max(x, cx - 10)), int(min(x + w, cx + vw + 10))
                for xx in range(start - start % 6, end, 6):
                    pygame.draw.rect(surf, ROAD_LINE, R((xx, mid - 0.08, 3, 0.16)))
            else:
                mid = x + w / 2
                start, end = int(max(y, cy - 10)), int(min(y + h, cy + vh + 10))
                for yy in range(start - start % 6, end, 6):
                    pygame.draw.rect(surf, ROAD_LINE, R((mid - 0.08, yy, 0.16, 3)))
        for c in self.crossings:
            if rect_overlap(c, view):
                pygame.draw.rect(surf, ROAD, R(c))
        # колонки
        for p in PUMPS:
            if rect_overlap(p, view):
                pygame.draw.rect(surf, (200, 40, 40), R(p))
        # блитцеры
        for bx, by, lim in BLITZER:
            if point_in(view, bx, by):
                pygame.draw.rect(surf, (230, 230, 230), R((bx - 0.4, by - 0.4, 0.8, 1.2)))
                pygame.draw.circle(surf, (30, 30, 30), R((bx, by, 0, 0)).topleft, 2)
        # дома
        for hh in self.houses:
            if rect_overlap(hh[:4], view):
                self._draw_house(surf, R(hh[:4]), hh[4], hh[5])
        for bid, b in BUILDINGS.items():
            if rect_overlap(b[:4], view):
                rr = R(b[:4])
                self._draw_house(surf, rr, b[5], b[6], flat=bid in ("supermarkt", "lager", "tuv", "tanke", "autoteile"))
                lab = self.label(b[4], 14, (250, 245, 230))
                bg = pygame.Rect(0, 0, lab.get_width() + 8, lab.get_height() + 4)
                bg.center = rr.center
                pygame.draw.rect(surf, (20, 20, 20), bg)
                surf.blit(lab, lab.get_rect(center=rr.center))
                if b[7]:
                    d = R((b[7][0], b[7][1], 0, 0)).topleft
                    pygame.draw.circle(surf, (240, 200, 60), d, 5, 2)
        # заброшенные гаражи
        for ag in self.abandoned:
            if rect_overlap(ag["rect"], view):
                pygame.draw.rect(surf, (85, 80, 75), R(ag["rect"]))
                for w in ag["walls"]:
                    pygame.draw.rect(surf, (120, 100, 85), R(w))
                if ag["door_rect"] in self.solids:
                    pygame.draw.rect(surf, (140, 70, 40), R(ag["door_rect"]))
        # гараж
        for w in GARAGE_WALLS:
            if rect_overlap(w, view):
                pygame.draw.rect(surf, (140, 130, 120), R(w))
        if rect_overlap(GARAGE, view):
            lab = self.label(T("Гараж"), 13, (250, 230, 120))
            surf.blit(lab, R((GARAGE[0] + 1, GARAGE[1] + GARAGE[3] - 2.2, 0, 0)).topleft)
        # навес заправки
        if rect_overlap(PUMP_ZONE, view):
            can = pygame.Surface(R(PUMP_ZONE).size, pygame.SRCALPHA)
            can.fill((230, 230, 230, 60))
            surf.blit(can, R(PUMP_ZONE).topleft)

    def draw_trees(self, surf, cam):
        cx, cy = cam
        vw, vh = WIDTH / PPM, HEIGHT / PPM
        cols = [(40, 80, 40), (52, 92, 45), (35, 70, 38)]
        for tx, ty, r, k in self.trees:
            if cx - 5 < tx < cx + vw + 5 and cy - 5 < ty < cy + vh + 5:
                p = (int((tx - cx) * PPM), int((ty - cy) * PPM))
                pygame.draw.circle(surf, (30, 45, 28), (p[0] + 4, p[1] + 4), int(r * PPM))
                pygame.draw.circle(surf, cols[k], p, int(r * PPM))
                pygame.draw.circle(surf, tuple(min(255, c + 18) for c in cols[k]),
                                   (p[0] - int(r * 2), p[1] - int(r * 2)), int(r * PPM * 0.5))

    def _draw_house(self, surf, rr, wall, roof, flat=False):
        pygame.draw.rect(surf, (30, 30, 30), rr.move(4, 4))
        pygame.draw.rect(surf, wall, rr)
        inner = rr.inflate(-4, -4)
        pygame.draw.rect(surf, roof, inner)
        if not flat:
            if rr.w > rr.h:
                pygame.draw.line(surf, tuple(max(0, c - 35) for c in roof), (inner.left, inner.centery), (inner.right, inner.centery), 2)
            else:
                pygame.draw.line(surf, tuple(max(0, c - 35) for c in roof), (inner.centerx, inner.top), (inner.centerx, inner.bottom), 2)
        else:
            pygame.draw.rect(surf, tuple(max(0, c - 20) for c in roof), inner, 3)
