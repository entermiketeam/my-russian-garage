"""Особые места: подземные гаражи, заброшенные парковки, площадка «Gebrauchtwagen Weber», ряды свалки.

Только данные и раскладка (без графики). Подземные уровни лежат в отдельной «внутренней» области
координат (x >= INTERIOR_X): туда и обратно попадают через въезды-порталы — машиной или пешком.
"""
import math
import random

INTERIOR_X = 2400.0

# ---------------------------------------------------------------- въезды в подземные гаражи (на поверхности)
TG_ENTRANCES = [
    dict(id="tg1", name="Подземный гараж у Рыночной площади", rect=(700, 316, 9, 14)),
    dict(id="tg2", name="Подземный гараж у вокзала", rect=(440, 115, 9, 14)),
]
# ---------------------------------------------------------------- уровни (во внутренней области)
TG_LEVELS = [
    dict(id="tg1_1", tg="tg1", no=-1, rect=(2500, 40, 84, 56), style="modern"),
    dict(id="tg1_2", tg="tg1", no=-2, rect=(2500, 140, 84, 56), style="modern_low"),
    dict(id="tg2_1", tg="tg2", no=-1, rect=(2640, 40, 96, 64), style="old"),
    dict(id="tg2_2", tg="tg2", no=-2, rect=(2640, 140, 72, 60), style="bunker"),
]
# ---------------------------------------------------------------- заброшенные парковки
PARKINGS = [
    dict(id="p1", name="Парковка бывшего магазина «Консум»", rect=(560, 718, 64, 40), door="n", style="market"),
    dict(id="p2", name="Парковка у трассы L 342", rect=(1660, 318, 96, 28), door="n", style="gravel"),
    dict(id="p3", name="Задний двор транспортной фирмы Мюллера", rect=(826, 496, 72, 42), door="w", style="yard"),
]
# ---------------------------------------------------------------- площадка купли-продажи
DEALER_LOT = (1545, 314, 54, 36)
DEALER_SELL = (1583, 316, 15, 32)        # сюда ставят машину, которую хотят продать
DEALER_SPOTS = [(1549.5 + i * 3.4, row, -math.pi / 2) for row in (324.0, 340.0) for i in range(8)]
# ---------------------------------------------------------------- ряды машин на свалке
JUNK_SPOTS = ([(420.0 + i * 3.3, 362.0, (-1) ** i * math.pi / 2) for i in range(8)] +
              [(388.0 + i * 3.3, 405.0, (-1) ** i * math.pi / 2) for i in range(18)] +
              [(388.0 + i * 3.3, 418.0, (-1) ** (i + 1) * math.pi / 2) for i in range(18)])


def reserved_rects():
    """Что зарезервировать до генерации домов (с запасом под подъезды)."""
    out = []
    for e in TG_ENTRANCES:
        x, y, w, h = e["rect"]
        out.append((x - 3, y - 4, w + 6, h + 6))
    for p in PARKINGS:
        out.append(p["rect"])
        out.append(driveway(p))
    out.append(DEALER_LOT)
    return out


def driveway(p):
    x, y, w, h = p["rect"]
    if p["door"] == "n":
        return (x + w / 2 - 6, y - 8, 12, 8)
    if p["door"] == "s":
        return (x + w / 2 - 6, y + h, 12, 8)
    if p["door"] == "w":
        return (x - 14, y + h / 2 - 5, 14, 10)
    return (x + w, y + h / 2 - 5, 14, 10)


class Places:
    def __init__(self, world):
        self.world = world
        self.interior_solids = []
        self.portals = []
        self.levels = []
        self.entrances = []
        self.parkings = []
        self.loot_spots = []          # (x, y, место) — где лежат детали
        self.gaps = []                # подъезды: здесь нет снежных валов
        self._build_entrances()
        for L in TG_LEVELS:
            self.levels.append(self._build_level(L))
        self._link_portals()
        for P in PARKINGS:
            self.parkings.append(self._build_parking(P))
        self.gaps.append(DEALER_LOT)

    # ============================================================ въезды
    def _build_entrances(self):
        for e in TG_ENTRANCES:
            x, y, w, h = e["rect"]
            walls = [(x, y, 0.4, h), (x + w - 0.4, y, 0.4, h), (x, y + h - 0.4, w, 0.4)]
            ent = dict(e, walls=walls, trigger=(x + 0.6, y + 8.0, w - 1.2, 5.3),
                       exit=(x + w / 2, y + 2.6, -math.pi / 2), door_pt=(x + w / 2, y - 1.5))
            self.world.solids += walls
            self.entrances.append(ent)
            self.gaps.append((x - 1, y - 6, w + 2, 8))

    # ============================================================ подземный уровень
    def _build_level(self, L):
        rng = random.Random(L["id"])
        x0, y0, w, h = L["rect"]
        t = 0.5
        solids = [(x0 - t, y0 - t, w + 2 * t, t), (x0 - t, y0 + h, w + 2 * t, t),
                  (x0 - t, y0, t, h), (x0 + w, y0, t, h)]
        style = L["style"]
        angled = style in ("old", "bunker")
        # полосы: места у северной стены / проезд A / двойной ряд / проезд B / двойной ряд / проезд C / места / комнаты
        bands = dict(n_bays=(y0, y0 + 5), aisleA=(y0 + 5, y0 + 11), dbl1=(y0 + 11, y0 + 21), aisleB=(y0 + 21, y0 + 27),
                     dbl2=(y0 + 27, y0 + 37), aisleC=(y0 + 37, y0 + 43), s_bays=(y0 + 43, y0 + 48), rooms=(y0 + 48, y0 + h))
        pillars = []
        for py in (y0 + 16, y0 + 32):
            k = 1
            while x0 + 6 + k * 8 < x0 + w - 6:
                px = x0 + 6 + k * 8
                pillars.append((px - 0.3, py - 0.3, 0.6, 0.6))
                k += 1
        solids += pillars
        # парковочные места
        bays = []
        bw = 2.5
        n = int((w - 14) // bw)
        for i in range(n):
            bx = x0 + 7 + i * bw + bw / 2
            skew = (0.45 if (i % 2 == 0) else 0.35) if angled else 0.0
            bays.append((bx, y0 + 2.6, -math.pi / 2 + skew, "n"))
            bays.append((bx, y0 + 13.6, math.pi / 2 - skew, "d1n"))
            bays.append((bx, y0 + 18.4, -math.pi / 2 + skew, "d1s"))
            bays.append((bx, y0 + 29.6, math.pi / 2 - skew, "d2n"))
            bays.append((bx, y0 + 34.4, -math.pi / 2 + skew, "d2s"))
            bays.append((bx, y0 + 45.4, math.pi / 2 - skew, "s"))
        # не ставить машины вплотную к колоннам
        bays = [b for b in bays if all(not (abs(b[0] - (p[0] + 0.3)) < 1.5 and abs(b[1] - (p[1] + 0.3)) < 3.0)
                                       for p in pillars)]
        # помещения вдоль южной стены
        rooms = []
        ry0, ry1 = bands["rooms"]
        kinds = {"modern": ["Treppenhaus", "Technikraum", "Kellerabteile", "Waschbox"],
                 "modern_low": ["Treppenhaus", "Kellerabteile", "Lager", "Technikraum"],
                 "old": ["Treppenhaus", "Kellerabteile", "Lager", "Eingestürzt", "Technikraum"],
                 "bunker": ["Treppenhaus", "Schutzraum", "Kellerabteile", "Eingestürzt"]}[style]
        rx = x0
        widths = []
        rem = w
        for i, kname in enumerate(kinds):
            rw = rem / (len(kinds) - i) + rng.uniform(-3, 3) if i < len(kinds) - 1 else rem
            widths.append(max(10.0, rw))
            rem -= widths[-1]
        rx = x0
        for kname, rw in zip(kinds, widths):
            rw = min(rw, x0 + w - rx)
            door_x = rx + rw * rng.uniform(0.3, 0.7)
            # стена с проёмом 1.6 м
            solids.append((rx, ry0, max(0.1, door_x - 0.8 - rx), 0.3))
            solids.append((door_x + 0.8, ry0, max(0.1, rx + rw - door_x - 0.8), 0.3))
            if rx + rw < x0 + w - 0.1:
                solids.append((rx + rw - 0.15, ry0, 0.3, ry1 - ry0))
            room = dict(kind=kname, rect=(rx, ry0, rw, ry1 - ry0), door=(door_x, ry0))
            inner = (rx + 0.6, ry0 + 0.8, rw - 1.2, ry1 - ry0 - 1.4)
            if kname == "Kellerabteile":
                # клетки из сетки — в каждой может лежать деталь
                cw = 2.6
                cn = int(inner[2] // cw)
                for c in range(cn):
                    cx = inner[0] + c * cw
                    solids.append((cx, inner[1] + inner[3] - 3.0, 0.08, 3.0))       # перегородка-сетка
                    if rng.random() < 0.45:
                        self.loot_spots.append((cx + cw / 2, inner[1] + inner[3] - 1.3, L["id"]))
                room["cages"] = (inner[0], inner[1] + inner[3] - 3.0, cn * cw, 3.0, cn)
            elif kname == "Lager":
                for _ in range(2):
                    self.loot_spots.append((rng.uniform(inner[0] + 1, inner[0] + inner[2] - 1),
                                            rng.uniform(inner[1] + 1, inner[1] + inner[3] - 1), L["id"]))
                racks = (inner[0], inner[1] + inner[3] - 0.8, inner[2], 0.6)
                solids.append(racks)
                room["racks"] = racks
            elif kname == "Technikraum":
                cab = (inner[0] + 0.2, inner[1], inner[2] - 0.4, 0.7)
                solids.append(cab)
                room["cabinets"] = cab
            elif kname == "Eingestürzt":
                # обрушение: куча обломков перекрывает часть комнаты и заходит в проезд
                rub = (inner[0] + 1, inner[1] - 2.5, inner[2] - 2, inner[3] + 1.5)
                solids.append(rub)
                room["rubble"] = rub
            elif kname == "Schutzraum":
                room["bunker_door"] = (door_x, ry0)
            rooms.append(room)
            rx += rw
        # лампы вдоль проездов, некоторые разбиты или мигают
        lamps = []
        for band in ("aisleA", "aisleB", "aisleC"):
            yy = (bands[band][0] + bands[band][1]) / 2
            lx = x0 + 4
            while lx < x0 + w - 3:
                r = rng.random()
                state = "ok" if r < 0.55 else ("flicker" if r < 0.75 else "broken")
                if style == "bunker" and r < 0.3:
                    state = "broken"
                lamps.append((lx, yy, state))
                lx += 6.0
        # лужи (на нижних уровнях больше), мусор
        puddles = []
        for _ in range(4 if L["no"] == -1 else 9):
            puddles.append((rng.uniform(x0 + 5, x0 + w - 8), rng.uniform(y0 + 6, y0 + 46), rng.uniform(1.5, 5), rng.uniform(1, 3)))
        junk = []
        for _ in range(18):
            junk.append((rng.uniform(x0 + 1, x0 + w - 1), rng.uniform(y0 + 1, y0 + 47), rng.choice(["paper", "box", "can", "tire", "bottle"])))
        self.interior_solids += solids
        lvl = dict(L, bands=bands, pillars=pillars, bays=bays, rooms=rooms, lamps=lamps, puddles=puddles, junk=junk,
                   name=next(e["name"] for e in TG_ENTRANCES if e["id"] == L["tg"]))
        return lvl

    def _link_portals(self):
        by = {L["id"]: L for L in self.levels}
        for e in self.entrances:
            l1 = by[e["id"] + "_1"]
            l2 = by[e["id"] + "_2"]
            x0, y0, w, h = l1["rect"]
            X0, Y0, W, H = l2["rect"]
            # поверхность -> уровень -1 (въезд), обратно — в западном конце проезда A
            self.portals.append(dict(trigger=e["trigger"], dir=(0, 1), to=(x0 + 10, y0 + 8, 0.0), label=e["name"] + ": −1"))
            self.portals.append(dict(trigger=(x0 + 0.1, y0 + 5.2, 4.0, 5.6), dir=(-1, 0), to=e["exit"], label="Выезд"))
            # −1 <-> −2: пандусы в восточных концах проездов
            self.portals.append(dict(trigger=(x0 + w - 4.1, y0 + 37.2, 4.0, 5.6), dir=(1, 0),
                                     to=(X0 + W - 10, Y0 + 8, math.pi), label="Уровень −2"))
            self.portals.append(dict(trigger=(X0 + W - 4.1, Y0 + 5.2, 4.0, 5.6), dir=(1, 0),
                                     to=(x0 + w - 10, y0 + 40, math.pi), label="Уровень −1"))
            l1["ramps"] = [("up", (x0, y0 + 5, 4.5, 6)), ("down", (x0 + w - 4.5, y0 + 37, 4.5, 6))]
            l2["ramps"] = [("up", (X0 + W - 4.5, Y0 + 5, 4.5, 6))]

    # ============================================================ парковки
    def _build_parking(self, P):
        rng = random.Random(P["id"] + "park")
        x, y, w, h = P["rect"]
        style = P["style"]
        props = []      # (kind, x, y, angle, w, d, h, color)
        solids = []
        bays = []
        if style == "market":
            # два ряда мест лицом друг к другу, проезд посередине, киоск-руина, тележки, фонари
            for i in range(int((w - 8) // 2.6)):
                bx = x + 4 + i * 2.6 + 1.3
                bays.append((bx, y + 5, -math.pi / 2))
                bays.append((bx, y + h - 5, math.pi / 2))
            kx, ky = x + w - 12, y + h / 2 - 4
            for r in [(kx, ky, 8, 0.3), (kx, ky + 7.7, 8, 0.3), (kx + 7.7, ky, 0.3, 8)]:
                solids.append(r)
                props.append(("wall", r[0], r[1], 0, r[2], r[3], rng.uniform(1.2, 2.6), (170, 160, 140)))
            props.append(("sign", x + 3, y + 1, 0, 3.0, 0.2, 4.5, (200, 60, 40)))
            for i in range(9):
                props.append(("cart", x + 10 + rng.uniform(-3, 20), y + h / 2 + rng.uniform(-3, 3), rng.uniform(0, 6.28),
                              0.6, 0.9, 1.0, (140, 130, 120)))
            for lx in (x + 8, x + 30, x + 50):
                tilt = rng.choice([0, 0, 18, 70])
                props.append(("lamp", lx, y + h / 2, tilt, 0.15, 0.15, 6.0, (80, 80, 85)))
            props.append(("container", x + 2, y + h - 6, 0, 2.2, 1.5, 1.4, (60, 100, 60)))
            solids.append((x + 2, y + h - 6, 2.2, 1.5))
            props.append(("barrier", x + w / 2 - 5, y - 0.5, 0, 5.0, 0.15, 1.0, (220, 30, 30)))
        elif style == "gravel":
            # косые места вдоль задней стороны, остановка-руина, вагончик, шины, бочки
            for i in range(int((w - 10) // 3.0)):
                bays.append((x + 6 + i * 3.0, y + h - 5, math.pi / 2 - 0.5))
            props.append(("caravan", x + w - 14, y + 4, 0.1, 6.0, 2.3, 2.5, (220, 215, 195)))
            solids.append((x + w - 14, y + 4, 6.0, 2.3))
            props.append(("shelter", x + 6, y + 1.5, 0, 4.0, 1.5, 2.4, (120, 140, 150)))
            for i in range(5):
                props.append(("tires", x + rng.uniform(15, w - 18), y + rng.uniform(2, 8), 0, 0.7, 0.7, rng.uniform(0.4, 1.2),
                              (25, 25, 25)))
            for i in range(6):
                props.append(("drum", x + rng.uniform(20, w - 10), y + rng.uniform(2, h - 10), 0, 0.6, 0.6, 0.9,
                              rng.choice([(40, 70, 120), (150, 40, 30), (70, 90, 60)])))
            for fx in range(int(x), int(x + w), 3):
                if rng.random() < 0.7:
                    props.append(("fence", fx, y + h - 0.2, rng.uniform(-8, 8), 2.8, 0.05, 1.6, (110, 110, 105)))
        else:  # yard — двор экспедиции: прицепы, рампа, контейнеры, поддоны, погрузчик
            for i in range(int((h - 6) // 2.8)):
                bays.append((x + 5, y + 3 + i * 2.8 + 1.4, 0.0))
            props.append(("trailer", x + 22, y + 4, 0, 13.0, 2.5, 3.6, (180, 180, 185)))
            solids.append((x + 22, y + 4, 13.0, 2.5))
            props.append(("trailer", x + 26, y + 14, 0.05, 13.0, 2.5, 3.6, (60, 90, 140)))
            solids.append((x + 26, y + 14, 13.0, 2.5))
            props.append(("container", x + w - 8, y + h - 10, 0, 2.4, 6.0, 2.6, (160, 80, 40)))
            solids.append((x + w - 8, y + h - 10, 2.4, 6.0))
            props.append(("ramp", x + w - 3, y + 2, 0, 3.0, 12.0, 1.2, (120, 120, 118)))
            solids.append((x + w - 3, y + 2, 3.0, 12.0))
            for i in range(10):
                props.append(("pallets", x + rng.uniform(15, w - 6), y + rng.uniform(24, h - 3), rng.uniform(0, 1.5),
                              1.2, 0.8, rng.uniform(0.15, 1.0), (150, 120, 80)))
            props.append(("forklift", x + 40, y + h - 6, 0.7, 2.2, 1.1, 2.1, (230, 170, 30)))
            solids.append((x + 39, y + h - 7, 2.4, 2.0))
            for i in range(4):
                props.append(("drum", x + rng.uniform(12, 20), y + rng.uniform(24, h - 3), 0, 0.6, 0.6, 0.9, (40, 70, 120)))
        # трещины, сорняки, мусор — у всех, но в разном количестве
        for _ in range({"market": 40, "gravel": 25, "yard": 30}[style]):
            props.append(("weed", x + rng.uniform(0, w), y + rng.uniform(0, h), 0, rng.uniform(0.3, 1.2), 0.3,
                          rng.uniform(0.2, 0.6), (80, 95, 55)))
        for _ in range({"market": 20, "gravel": 6, "yard": 12}[style]):
            props.append(("crack", x + rng.uniform(1, w - 1), y + rng.uniform(1, h - 1), rng.uniform(0, 3.14),
                          rng.uniform(1.5, 5), 0.08, 0.0, (40, 40, 40)))
        # детали на земле
        spots = []
        for _ in range({"market": 6, "gravel": 5, "yard": 8}[style]):
            for _try in range(20):
                px, py = x + rng.uniform(2, w - 2), y + rng.uniform(2, h - 2)
                if not any(px >= s[0] - 1 and px <= s[0] + s[2] + 1 and py >= s[1] - 1 and py <= s[1] + s[3] + 1
                           for s in solids):
                    spots.append((px, py, P["id"]))
                    break
        self.loot_spots += spots
        self.world.solids += solids
        self.gaps.append(driveway(P))
        return dict(P, props=props, bays=bays, solids=solids)

    # ============================================================ запросы
    def level_at(self, x, y):
        if x < INTERIOR_X:
            return None
        for L in self.levels:
            lx, ly, lw, lh = L["rect"]
            if lx - 1 <= x <= lx + lw + 1 and ly - 1 <= y <= ly + lh + 1:
                return L
        return None

    def parking_at(self, x, y):
        for P in self.parkings:
            px, py, pw, ph = P["rect"]
            if px <= x <= px + pw and py <= y <= py + ph:
                return P
        return None

    def portal_for(self, x, y, vx, vy):
        """Портал, в который входит точка, движущаяся в направлении (vx, vy)."""
        for pt in self.portals:
            tx, ty, tw, th = pt["trigger"]
            if tx <= x <= tx + tw and ty <= y <= ty + th:
                dx, dy = pt["dir"]
                if vx * dx + vy * dy > 0.2:
                    return pt
        return None
