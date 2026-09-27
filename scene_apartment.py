"""Квартира на Lindenstraße 7: 1-комнатная + кухня + ванная. Вид сверху."""
import math
import random

import pygame

import ui
from config import WIDTH, HEIGHT, WHITE, GREY, YELLOW, GREEN, RED, ORANGE
from scenes_menu import Scene, DialogScene, InventoryScene, PauseScene, info
from world import BUILDINGS, GARAGE

OX, OY = 90, 70  # смещение комнаты на экране
NEWS = [
    "Tagesschau: Герхард Шрёдер (SPD) выиграл выборы в Бундестаг. Конец эпохи Коля.",
    "Tagesschau: С 1 января 1999 года евро введут в безналичных расчётах. Марка пока остаётся.",
    "Sportschau: «Бавария» лидирует в Бундеслиге, «Кайзерслаутерн» — действующий чемпион.",
    "Wetter: в Нижней Саксонии дожди, ночью до +4 °C. Берегите машины от сырости.",
    "Werbung: «Opel Astra — ab 26.990 DM!» Вы смотрите на свои ржавые пороги и вздыхаете.",
    "Tagesschau: Цены на бензин выросли до 1,65 DM за литр. Автоклубы возмущены.",
    "Регион: В Kleinbruck полиция усилила контроль техосмотра старых автомобилей.",
    "Wer wird Millionär? Вы отвечаете на три вопроса и чувствуете себя умным.",
]


class Obj:
    def __init__(self, key, label, rect, color, solid=True):
        self.key = key
        self.label = label
        self.rect = pygame.Rect(rect)
        self.color = color
        self.solid = solid


class ApartmentScene(Scene):
    time_flows = True

    def __init__(self, game):
        super().__init__(game)
        self.px, self.py = 70.0, 520.0
        self.facing = 0.0
        W, H = 1100, 590
        t = 12
        # стены (координаты комнаты)
        self.walls = [
            (0, 0, W, t), (0, H - t, W, t), (0, 0, t, H), (W - t, 0, t, H),
            # кухня / гостиная (проём 160..260)
            (560, 0, t, 160), (560, 260, t, 40),
            # горизонтальная стена кухни (проём в спальню 900..990)
            (560, 300, 340, t), (990, 300, 110, t),
            # ванная / спальня (дверь 420..500)
            (780, 300, t, 120), (780, 500, t, 90),
            # вход в ванную из гостиной (проём 360..440)
            (560, 300, t, 60), (560, 440, t, 150),
        ]
        self.objs = [
            Obj("door", "Выйти на улицу", (12, 548, 70, 30), (110, 80, 50), solid=False),
            Obj("mail", "Почтовый ящик / письма", (100, 560, 40, 18), (160, 160, 60)),
            Obj("sofa", "Диван (посидеть 1 ч)", (40, 40, 220, 70), (90, 60, 50)),
            Obj("tv", "Телевизор", (380, 30, 110, 40), (30, 30, 34)),
            Obj("table", "Стол (дела, счета)", (230, 250, 150, 90), (140, 100, 60)),
            Obj("phone", "Телефон", (400, 520, 60, 40), (190, 50, 40)),
            Obj("shelf", "Книжная полка", (20, 200, 36, 180), (110, 80, 55)),
            Obj("fridge", "Холодильник «Bosch»", (1010, 20, 70, 70), (225, 225, 225)),
            Obj("stove", "Плита", (900, 20, 90, 60), (70, 70, 72)),
            Obj("sink", "Раковина (кран)", (800, 20, 80, 50), (190, 200, 210)),
            Obj("ktable", "Кухонный стол", (700, 160, 110, 80), (160, 120, 80)),
            Obj("bed", "Кровать", (960, 420, 120, 150), (120, 130, 170)),
            Obj("wardrobe", "Шкаф", (810, 320, 120, 45), (100, 75, 50)),
            Obj("calendar", "Календарь", (1060, 330, 24, 40), (230, 230, 200)),
            Obj("shower", "Душ", (580, 510, 90, 65), (160, 200, 220)),
            Obj("toilet", "Туалет", (700, 520, 50, 50), (235, 235, 235)),
            Obj("mirror", "Зеркало", (580, 320, 70, 22), (180, 210, 230)),
        ]
        self.near = None
        self.rng = random.Random(3)
        self.window_t = 0

    # --------------------------------------------------------------- движение
    def solid_rects(self):
        rs = [pygame.Rect(w) for w in self.walls]
        rs += [o.rect for o in self.objs if o.solid]
        return rs

    def move(self, dx, dy):
        r = 13
        for axis in (0, 1):
            nx = self.px + (dx if axis == 0 else 0)
            ny = self.py + (dy if axis == 1 else 0)
            box = pygame.Rect(nx - r, ny - r, 2 * r, 2 * r)
            if not any(box.colliderect(s) for s in self.solid_rects()):
                self.px, self.py = nx, ny

    def update(self, dt):
        k = pygame.key.get_pressed()
        dx = (k[pygame.K_d] or k[pygame.K_RIGHT]) - (k[pygame.K_a] or k[pygame.K_LEFT])
        dy = (k[pygame.K_s] or k[pygame.K_DOWN]) - (k[pygame.K_w] or k[pygame.K_UP])
        if dx or dy:
            l = math.hypot(dx, dy)
            sp = 190 * dt
            self.move(dx / l * sp, 0)
            self.move(0, dy / l * sp)
            self.facing = math.atan2(dy, dx)
        best, bd = None, 55
        for o in self.objs:
            cx = max(o.rect.left, min(self.px, o.rect.right))
            cy = max(o.rect.top, min(self.py, o.rect.bottom))
            d = math.hypot(self.px - cx, self.py - cy)
            if d < bd:
                best, bd = o, d
        self.near = best
        if self.game.pending_faint:
            self.game.pending_faint = False
            self.game.notify("Вы уснули прямо на полу...", RED)
            self.sleep(6 * 60)

    # --------------------------------------------------------------- действия
    def handle(self, ev):
        if ev.type != pygame.KEYDOWN:
            return
        g = self.game
        if ev.key == pygame.K_ESCAPE:
            g.push(PauseScene(g))
        elif ev.key in (pygame.K_TAB, pygame.K_i):
            g.push(InventoryScene(g))
        elif ev.key == pygame.K_e and self.near:
            self.act(self.near.key)

    def sleep(self, minutes):
        g = self.game
        step = 10
        left = minutes
        while left > 0 and not g.game_over:
            g.advance(min(step, left), sleeping=True)
            left -= step
        g.p.energy = min(100, g.p.energy)
        g.notify(f"Вы проснулись. {g.time_str()}", GREEN)

    def act(self, key):
        g = self.game
        p = g.p
        if key == "door":
            g.sound.play("door", 0.6)
            ax, ay = BUILDINGS["apartment"][7]
            p.x, p.y = ax, ay - 1.0
            p.in_car = False
            g.pop()
        elif key == "bed":
            if p.energy > 80:
                info(g, "Кровать", ["Спать пока не хочется."])
                return

            def until_morning():
                h = g.hour
                mins = ((7 - h) % 24) * 60
                self.sleep(max(30, mins))
                g.save()

            g.push(DialogScene(g, "Кровать", [f"Бодрость: {p.energy:.0f}%. Сон также сохраняет игру."], [
                ("Вздремнуть 1 час", lambda: self.sleep(60), True),
                ("Поспать 4 часа", lambda: self.sleep(240), True),
                ("Спать до 07:00 утра (и сохранить)", until_morning, True),
            ]))
        elif key == "fridge":
            g.push(InventoryScene(g, only_food=True, title="Холодильник (ваши продукты)"))
        elif key == "stove":
            if g.has("pizza_tk"):
                def cook():
                    g.take_item("pizza_tk")
                    g.advance(15)
                    g.add_item("pizza_hot")
                    g.notify("Пицца готова (горячая пицца в инвентаре).", GREEN)
                g.push(DialogScene(g, "Плита", ["Разогреть замороженную пиццу? (15 мин)"],
                                   [("Разогреть", cook, True)]))
            else:
                info(g, "Плита", ["Нечего готовить. Купите Tiefkühlpizza в Supermarkt."])
        elif key == "sink":
            p.thirst = min(100, p.thirst + 30)
            g.advance(2)
            g.notify("Вы попили воды из-под крана.", GREEN)
        elif key == "shower":
            g.advance(15)
            p.hygiene = 100
            p.energy = min(100, p.energy + 5)
            g.notify("Вы приняли душ. Свежесть!", GREEN)
        elif key == "toilet":
            g.advance(4)
            g.notify("Вы сходили в туалет. Бачок подтекает, как и ваш карбюратор.")
        elif key == "mirror":
            look = "бодрый" if p.energy > 60 else ("уставший" if p.energy > 25 else "как зомби")
            smell = "пахнете нормально" if p.hygiene > 50 else ("пахнете бензином и потом" if p.hygiene > 20 else "пахнете ужасно — на работу так нельзя")
            drunk = " Глаза красные — вы пьяны." if p.drunk > 25 else ""
            info(g, "Зеркало", [f"Вы выглядите {look} и {smell}.{drunk}", f"Здоровье: {p.health:.0f}%"])
        elif key == "tv":
            def watch():
                g.advance(60)
                info(g, "Fernsehen", [random.choice(NEWS)])
            g.push(DialogScene(g, "Телевизор", ["Посмотреть телевизор 1 час?"], [("Смотреть", watch, True)]))
        elif key == "sofa":
            g.advance(60)
            p.energy = min(100, p.energy + 4)
            g.notify("Вы посидели на диване и уставились в потолок.")
        elif key == "phone":
            self.phone()
        elif key in ("table", "calendar", "mail"):
            self.status()
        elif key == "shelf":
            info(g, "Книжная полка", [
                "«Руководство по ремонту ВАЗ-2101, -2102» (1982), зачитанное до дыр.",
                "Закладка на странице: «Порядок работы цилиндров 1-3-4-2. Зазор в контактах "
                "прерывателя 0,35-0,45 мм. Уровень масла — между метками щупа (3,75 л)».",
                "Рядом — немецко-русский словарь и сборник «Deutsch für Aussiedler».",
            ])
        elif key == "wardrobe":
            info(g, "Шкаф", ["Спортивный костюм Adidas, рабочая куртка, выходная рубашка. "
                             "Больше ничего полезного."])
        elif key == "ktable":
            info(g, "Кухонный стол", ["Клеёнка в клетку, пепельница и счёт за электричество (оплачен)."])

    def phone(self):
        g = self.game
        car = g.car

        def pizza():
            if g.pay(15):
                g.advance(35)
                g.add_item("pizza_hot")
                g.notify("Курьер привёз пиццу (15 DM).", GREEN)

        def tow():
            if g.pay(120):
                gx, gy, gw, gh = GARAGE
                car.x, car.y = gx + gw / 2, gy + gh / 2 + 0.5
                car.angle = -math.pi / 2
                car.speed = 0
                car.engine_off()
                g.advance(90)
                g.notify("Abschleppdienst Meier отбуксировал машину в ваш гараж (120 DM).", GREEN)

        def mama():
            g.advance(20)
            if g.day - g.last_mama >= 5:
                g.last_mama = g.day
                g.earn(60, "— мама перевела денег")
                info(g, "Звонок маме", ["«Сынок, ты там кушаешь? Я тебе 60 марок перевела. "
                                        "И продай ты эту ржавую машину, отец твой на ней ещё в Сочи ездил!»"])
            else:
                info(g, "Звонок маме", ["«Опять звонишь? Денег больше нет до следующей недели. "
                                        "Шапку надевай, октябрь на дворе!»"])

        g.push(DialogScene(g, "Телефон", ["Кому позвонить?"], [
            ("Pizza-Service — заказать пиццу (15 DM)", pizza, True),
            ("Abschleppdienst — эвакуировать машину к гаражу (120 DM)", tow, True),
            ("Позвонить маме в Омск", mama, True),
        ]))

    def status(self):
        g = self.game
        car = g.car
        days_rent = 7 - g.day % 7
        tuv = "нет" if car.tuv_until < g.day else f"до дня {car.tuv_until}"
        lines = [
            f"Деньги: {g.p.money:.2f} DM.  Квартира своя — за жильё платить не нужно.",
            f"Машина: TÜV — {tuv};  номера — {'есть' if car.registered else 'нет (ездить нельзя!)'}.",
            f"Пробег: {car.odometer:.0f} км.  Макс. ржавчина: {car.max_rust():.0f}%.",
            f"Сделано доставок: {g.stats['deliveries']},  смен на складе: {g.stats['shifts']}.",
            "",
            "План: 1) свечи + зарядить АКБ + масло + бензин;  2) шины и тормоза;",
            "3) сварка порогов/днища и покраска;  4) TÜV;  5) номера в Rathaus.",
        ]
        info(g, "Дела и счета", lines)

    # --------------------------------------------------------------- отрисовка
    def draw(self, surf):
        g = self.game
        surf.fill((16, 16, 18))
        W, H = 1100, 590
        # пол
        pygame.draw.rect(surf, (120, 88, 60), (OX, OY, 560, H))           # паркет
        for i in range(0, H, 18):
            pygame.draw.line(surf, (105, 76, 52), (OX, OY + i), (OX + 560, OY + i))
        pygame.draw.rect(surf, (200, 195, 180), (OX + 560, OY, 540, 300))  # кухня (плитка)
        for i in range(0, 540, 30):
            pygame.draw.line(surf, (180, 175, 160), (OX + 560 + i, OY), (OX + 560 + i, OY + 300))
        for i in range(0, 300, 30):
            pygame.draw.line(surf, (180, 175, 160), (OX + 560, OY + i), (OX + 1100, OY + i))
        pygame.draw.rect(surf, (170, 200, 205), (OX + 560, OY + 300, 220, 290))  # ванная
        pygame.draw.rect(surf, (140, 130, 150), (OX + 780, OY + 300, 320, 290))  # спальня (ковролин)
        # ковёр на стене... то есть на полу — советская классика
        pygame.draw.rect(surf, (140, 40, 40), (OX + 120, OY + 150, 300, 200))
        pygame.draw.rect(surf, (190, 150, 60), (OX + 130, OY + 160, 280, 180), 3)
        pygame.draw.rect(surf, (60, 30, 60), (OX + 190, OY + 210, 160, 80), 2)
        # предметы
        for o in self.objs:
            r = o.rect.move(OX, OY)
            pygame.draw.rect(surf, (0, 0, 0), r.move(3, 3))
            pygame.draw.rect(surf, o.color, r)
            pygame.draw.rect(surf, (40, 40, 40), r, 2)
            if o.key == "bed":
                pygame.draw.rect(surf, (235, 235, 235), (r.x + 8, r.y + 8, r.w - 16, 30))
                pygame.draw.rect(surf, (90, 100, 140), (r.x + 4, r.y + 50, r.w - 8, r.h - 54))
            elif o.key == "stove":
                for cx in (r.x + 22, r.x + 66):
                    for cy in (r.y + 16, r.y + 44):
                        pygame.draw.circle(surf, (30, 30, 30), (cx, cy), 11)
            elif o.key == "tv":
                pygame.draw.rect(surf, (60, 80, 100), r.inflate(-14, -12))
            elif o.key == "sofa":
                pygame.draw.rect(surf, (110, 75, 60), (r.x + 6, r.y + 6, r.w - 12, 24))
            elif o.key == "phone":
                pygame.draw.circle(surf, (240, 240, 240), r.center, 9, 2)
            elif o.key == "shelf":
                for yy in range(r.y + 8, r.bottom - 8, 22):
                    for xx in range(r.x + 4, r.right - 4, 6):
                        c = ((xx * 7) % 150 + 60, (yy * 3) % 120 + 50, (xx + yy) % 90 + 40)
                        pygame.draw.rect(surf, c, (xx, yy, 5, 16))
            elif o.key == "table":
                pygame.draw.rect(surf, (230, 230, 220), (r.x + 20, r.y + 20, 40, 28))
            elif o.key == "sink":
                pygame.draw.ellipse(surf, (150, 160, 170), r.inflate(-20, -16))
            elif o.key == "shower":
                pygame.draw.circle(surf, (120, 150, 170), r.center, 8)
        # окна (свет снаружи)
        dark = g.darkness()
        wc = (int(160 - 120 * dark), int(190 - 140 * dark), int(230 - 150 * dark))
        for wx, wy, ww, wh in ((OX + 150, OY - 4, 120, 8), (OX + 700, OY - 4, 90, 8), (OX + 1096, OY + 440, 8, 100),
                               (OX + 330, OY + H - 4, 120, 8)):
            pygame.draw.rect(surf, wc, (wx, wy, ww, wh))
        # стены
        for w in self.walls:
            pygame.draw.rect(surf, (225, 220, 205), pygame.Rect(w).move(OX, OY))
        # игрок
        x, y = OX + self.px, OY + self.py
        pygame.draw.circle(surf, (0, 0, 0), (int(x) + 3, int(y) + 3), 14)
        pygame.draw.circle(surf, (40, 60, 140), (int(x), int(y)), 14)   # «адидас»
        pygame.draw.circle(surf, (230, 190, 160), (int(x + math.cos(self.facing) * 4), int(y + math.sin(self.facing) * 4)), 8)
        # ночью в квартире горит лампа — лёгкое затемнение углов
        if dark > 0.2:
            s = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            s.fill((10, 10, 30, int(60 * dark)))
            surf.blit(s, (0, 0))
        # подсказка
        if self.near:
            ui.panel(surf, (WIDTH // 2 - 220, HEIGHT - 58, 440, 36), 220)
            ui.text(surf, f"E — {self.near.label}", (WIDTH // 2, HEIGHT - 40), 18, YELLOW, center=True)
        draw_hud(surf, g, "Квартира, Lindenstraße 7")


def draw_hud(surf, g, place=""):
    p = g.p
    ui.panel(surf, (8, 8, 380, 54), 200)
    wth = f"{g.weather_text()}, {g.ambient_temp():+.0f}°C" if hasattr(g, "weather_text") else g.weather
    ui.text(surf, g.time_str(), (18, 12), 20, WHITE, bold=True)
    ui.text(surf, f"{place}  ·  {wth}", (18, 38), 14, GREY)
    ui.panel(surf, (WIDTH - 500, 8, 492, 54), 200)
    col = GREEN if p.money >= 0 else RED
    ui.text(surf, f"{p.money:.2f} DM", (WIDTH - 395, 12), 22, col, bold=True, right=True)
    x0 = WIDTH - 385
    for i, (name, v) in enumerate((("Сытость", p.hunger), ("Жажда", p.thirst),
                                   ("Бодрость", p.energy), ("Гигиена", p.hygiene))):
        ui.bar(surf, x0 + (i % 2) * 188, 13 + (i // 2) * 23, 180, 18, v, label=name)
    extra = []
    if p.drunk > 10:
        extra.append((f"Опьянение {p.drunk:.0f}%", ORANGE))
    if p.health < 100:
        extra.append((f"Здоровье {p.health:.0f}%", RED if p.health < 50 else WHITE))
    if extra:
        s, c = extra[0] if len(extra) == 1 or g.t % 4 < 2 else extra[1]
        ui.text(surf, s, (WIDTH - 395, 42), 12, c, right=True)
