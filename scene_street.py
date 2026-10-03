"""Улица: ходьба, вождение, здания, работа, полиция, освещение, HUD."""
import math
import random

import pygame

import ui
from config import (WIDTH, HEIGHT, PPM, WHITE, GREY, YELLOW, GREEN, RED, ORANGE, BLUE, font)
from scenes_menu import Scene, DialogScene, ShopScene, InventoryScene, PauseScene, info
from scene_apartment import ApartmentScene, draw_hud
from scene_garage import CarWorkScene
from world import (BUILDINGS, ROADS, BLITZER, PUMP_ZONE, TUV_YARD, GARAGE, MAP_W, MAP_H, point_in)
from items import ITEMS, SHOP_SUPERMARKT, SHOP_TEILE, SHOP_TANKE, SHOP_IMBISS, SLOTS, item_name
from car import GEAR_NAMES, TANK
from actions import sell_price, used_price
from i18n import T

FUEL_PRICE = 1.65  # ₽/л, осень 1998
PLATE = "KB-VZ 102"


def radial(radius, strength=255):
    s = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    for r in range(radius, 0, -2):
        a = int(strength * (1 - r / radius) ** 0.8)
        pygame.draw.circle(s, (0, 0, 0, a), (radius, radius), r)
    return s


def cone(length, spread, strength=235):
    s = pygame.Surface((length, spread * 2), pygame.SRCALPHA)
    steps = 24
    for i in range(steps, 0, -1):
        k = i / steps
        a = int(strength * (1 - k) ** 0.7)
        pts = [(0, spread - 6), (int(length * k), spread - int(spread * k)),
               (int(length * k), spread + int(spread * k)), (0, spread + 6)]
        pygame.draw.polygon(s, (0, 0, 0, a), pts)
    return s


class StreetScene(Scene):
    time_flows = True

    def __init__(self, game):
        super().__init__(game)
        self.cam = [0.0, 0.0]
        self.prompt = []
        self.action = None
        self.throttle = 0.0
        self.brake = 0.0
        self.show_map = False
        self.flash = 0.0
        self.walk_phase = 0.0
        self.lamp_light = radial(int(14 * PPM), 200)
        self.small_light = radial(int(4 * PPM), 160)
        self.head_cone = cone(int(38 * PPM), int(11 * PPM))
        self.dark = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.drops = [[random.uniform(0, WIDTH), random.uniform(0, HEIGHT)] for _ in range(260)]
        self._build_map()

    # ------------------------------------------------------------ карта
    def _build_map(self):
        k = 0.5
        m = pygame.Surface((int(MAP_W * k), int(MAP_H * k)))
        m.fill((60, 90, 50))
        for r in ROADS:
            col = (230, 200, 90) if r[4] == "autobahn" else ((200, 200, 200) if r[4] == "town" else (170, 170, 170))
            pygame.draw.rect(m, col, (r[0] * k, r[1] * k, max(2, r[2] * k), max(2, r[3] * k)))
        for h in self.game.world.houses:
            pygame.draw.rect(m, (150, 110, 90), (h[0] * k, h[1] * k, h[2] * k, h[3] * k))
        for bid, b in BUILDINGS.items():
            pygame.draw.rect(m, (80, 140, 220), (b[0] * k, b[1] * k, b[2] * k, b[3] * k))
        self.mapsurf = m
        sc = (HEIGHT - 60) / MAP_H
        self.bigmap = pygame.transform.smoothscale(m, (int(MAP_W * sc), int(MAP_H * sc)))
        self.bigmap_k = sc

    # ------------------------------------------------------------ ввод
    def handle(self, ev):
        g, p, car = self.game, self.game.p, self.game.car
        if ev.type == pygame.KEYUP and ev.key == pygame.K_i and p.in_car:
            car.stop_crank()
        if ev.type != pygame.KEYDOWN:
            return
        k = ev.key
        if k == pygame.K_ESCAPE:
            if self.show_map:
                self.show_map = False
            else:
                g.push(PauseScene(g))
            return
        if k == pygame.K_m:
            self.show_map = not self.show_map
        elif k == pygame.K_TAB:
            g.push(InventoryScene(g))
        elif k == pygame.K_e and self.action:
            self.action[1]()
        elif k == pygame.K_f:
            self.toggle_car()
        elif p.in_car:
            if k == pygame.K_i:
                if car.running:
                    car.engine_off(T("Двигатель заглушен."))
                else:
                    car.start_crank()
            elif k == pygame.K_c:
                car.choke = not car.choke
                g.notify(T("Подсос ") + (T("ВЫТЯНУТ") if car.choke else T("задвинут")))
            elif k == pygame.K_l:
                if car.has("lights") and car.c("lights") > 0.05:
                    car.lights = not car.lights
                else:
                    g.notify(T("Фары не работают."), RED)
            elif k == pygame.K_h:
                if car.battery_charge > 5:
                    g.sound.play("horn", 0.7)
            elif k in (pygame.K_LSHIFT, pygame.K_RSHIFT):
                self.shift(car.gear + 1 if car.gear < 4 else 4)
            elif k in (pygame.K_LCTRL, pygame.K_RCTRL):
                self.shift(car.gear - 1 if car.gear > -1 else -1)
            elif k in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                self.shift(k - pygame.K_0)
            elif k == pygame.K_r:
                self.shift(-1)
            elif k in (pygame.K_n, pygame.K_0):
                self.shift(0)

    def shift(self, gear):
        car = self.game.car
        if gear == car.gear:
            return
        if (gear == -1 and car.speed > 1.5) or (gear > 0 and car.speed < -1.5):
            self.game.notify(T("ХРУСТЬ! Сначала остановитесь."), RED)
            self.game.sound.play("grind", 0.7)
            return
        car.gear = gear

    def toggle_car(self):
        g, p, car = self.game, self.game.p, self.game.car
        if p.in_car:
            if abs(car.speed) > 1:
                g.notify(T("Сначала остановитесь."), RED)
                return
            car.stop_crank()
            if car.running:
                car.gear = 0
            fx, fy = car.forward()
            for side in (1, -1):
                nx, ny = car.x + fy * 1.5 * side, car.y - fx * 1.5 * side
                if not g.world.collide_circle(nx, ny, 0.35):
                    p.x, p.y = nx, ny
                    break
            else:
                p.x, p.y = car.x - fx * 3, car.y - fy * 3
            p.in_car = False
            g.sound.play("door", 0.6)
        elif self.near_car():
            p.in_car = True
            g.sound.play("door", 0.6)
            if not car.registered:
                g.notify(T("Внимание: машина без номеров и страховки. Не попадитесь полиции!"), ORANGE, 6)

    def near_car(self, dist=2.6):
        p, car = self.game.p, self.game.car
        return any(math.hypot(p.x - cx, p.y - cy) < dist for cx, cy, _ in car.body_circles())

    # ------------------------------------------------------------ обновление
    def update(self, dt):
        g, p, car = self.game, self.game.p, self.game.car
        keys = pygame.key.get_pressed()
        self.flash = max(0.0, self.flash - dt * 3)
        g.police_cd = max(0.0, g.police_cd - dt)

        if p.in_car:
            thr = 1.0 if (keys[pygame.K_w] or keys[pygame.K_UP]) else 0.0
            brk = 1.0 if (keys[pygame.K_s] or keys[pygame.K_DOWN]) else 0.0
            self.throttle += (thr - self.throttle) * min(1, dt * 5)
            self.brake += (brk - self.brake) * min(1, dt * 8)
            steer = ((keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT]))
            if p.drunk > 20:
                steer += math.sin(g.t * 1.3) * p.drunk / 180
            g.car_input = {"throttle": self.throttle, "brake": self.brake, "steer": steer,
                           "clutch": keys[pygame.K_SPACE]}
            if car.cranking and not keys[pygame.K_i]:
                car.stop_crank()
            p.x, p.y = car.x, car.y
            self.check_blitzer()
            self.check_police()
        else:
            g.car_input = {}
            dx = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
            dy = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])
            if dx or dy:
                run = keys[pygame.K_LSHIFT] and p.energy > 10
                sp = (4.2 if run else 1.5) * dt
                if run:
                    g.advance(dt * 0.5)
                l = math.hypot(dx, dy)
                for ax, ay in ((dx / l * sp, 0), (0, dy / l * sp)):
                    nx, ny = p.x + ax, p.y + ay
                    blocked = g.world.collide_circle(nx, ny, 0.35)
                    if not blocked:
                        blocked = any(math.hypot(nx - cx, ny - cy) < r + 0.3 for cx, cy, r in car.body_circles())
                    if not blocked:
                        p.x, p.y = nx, ny
                self.walk_phase += dt * (10 if run else 6)
            # сбили машиной
            for ai in g.world.ai:
                if ai.speed > 4 and math.hypot(ai.x - p.x, ai.y - p.y) < 1.5:
                    g.hospital(T("Вас сбила машина! Смотрите по сторонам."))
                    return
        g.traffic.update(dt, g, (car.x, car.y)) if hasattr(g, "traffic") else g.world.update_ai(dt, car)

        # потеря сознания от усталости
        if g.pending_faint:
            g.pending_faint = False
            if p.in_car and abs(car.speed) > 3:
                g.notify(T("Вы уснули за рулём!"), RED, 8)
                if car.impact(abs(car.speed)):
                    g.hospital(T("Авария: уснули за рулём."))
                    return
                car.speed = 0
            else:
                g.notify(T("Вы уснули прямо на улице..."), RED, 8)
            car.engine_off()
            for _ in range(36):
                g.advance(10, sleeping=True)
            if random.random() < 0.3 and p.money > 20:
                g.charge(min(p.money, random.uniform(10, 60)), T("Пока вы спали, у вас украли деньги"), RED, 8)

        # доставка: опоздание
        d = g.delivery
        if d and g.minutes > d["deadline"] + 60:
            g.notify(T("Заказ отменён — клиент не дождался. Пиццерия недовольна."), RED)
            g.delivery = None

        self.find_action()
        # камера
        tx, ty = (car.x, car.y) if p.in_car else (p.x, p.y)
        if p.in_car:
            fx, fy = car.forward()
            tx += fx * car.speed * 0.6
            ty += fy * car.speed * 0.6
        cx = tx - WIDTH / 2 / PPM
        cy = ty - HEIGHT / 2 / PPM
        self.cam[0] += (cx - self.cam[0]) * min(1, dt * 5)
        self.cam[1] += (cy - self.cam[1]) * min(1, dt * 5)
        g.sound.set_rain(1.0 if g.weather == "rain" else 0.0)

    # ------------------------------------------------------------ штрафы
    def check_blitzer(self):
        g, car = self.game, self.game.car
        for i, (bx, by, lim) in enumerate(BLITZER):
            if math.hypot(car.x - bx, car.y - by) < 9 and g.t > g.blitz_cd.get(i, 0):
                over = car.kmh() - lim
                if over > 5:
                    g.blitz_cd[i] = g.t + 15
                    fine = 20 if over <= 10 else (50 if over <= 20 else (100 if over <= 30 else 200))
                    self.flash = 1.0
                    g.sound.play("blitz", 0.8)
                    g.charge(fine, T("БЛИЦ! {kmh:.0f} км/ч при {lim}. Штраф", kmh=car.kmh(), lim=lim))

    def check_police(self):
        g, car, pol = self.game, self.game.car, self.game.world.police
        if g.police_cd > 0 or abs(car.speed) < 1:
            return
        if math.hypot(car.x - pol.x, car.y - pol.y) > 28:
            return
        reasons = []
        lim = g.world.speed_limit(car.x, car.y)
        if not car.registered:
            reasons.append((T("Езда без регистрации и страховки"), 250))
        elif car.tuv_until < g.day:
            reasons.append((T("Просроченный техосмотр"), 60))
        if g.p.drunk > 25:
            reasons.append((T("Вождение в нетрезвом виде"), 500))
        if lim and car.kmh() > lim + 20:
            reasons.append((T("Превышение скорости ({kmh:.0f} при {lim})", kmh=car.kmh(), lim=lim), 100))
        if car.c("lights") < 0.05 and g.darkness() > 0.4:
            reasons.append((T("Езда без света ночью"), 30))
        if car.c("exhaust") < 0.2:
            reasons.append((T("Слишком громкий выхлоп"), 40))
        if not reasons:
            return
        g.police_cd = 240
        pol.siren = 8.0
        car.speed = 0
        g.sound.play("police", 0.6)
        total = sum(r[1] for r in reasons)
        g.charge(total)
        lines = [T("«Плановая проверка! Права и документы на машину, пожалуйста.»"), ""]
        lines += [f"• {r[0]}: {r[1]} ₽" for r in reasons]
        lines += ["", T("Итого штраф: {total} ₽.", total=total),
                  T("Полицейский качает головой, глядя на ваши гнилые пороги.")]
        info(g, T("Полиция"), lines)

    # ------------------------------------------------------------ взаимодействия
    def find_action(self):
        g, p, car = self.game, self.game.p, self.game.car
        self.action = None
        acts = []
        d = g.delivery
        if d:
            if math.hypot(p.x - d["x"], p.y - d["y"]) < (9 if p.in_car else 4):
                acts.append((T("Отдать пиццу клиенту"), self.deliver))
        if p.in_car:
            if point_in(PUMP_ZONE, car.x, car.y):
                acts.append((T("Заправиться"), self.refuel))
            if point_in(TUV_YARD, car.x, car.y):
                acts.append((T("Пройти техосмотр"), self.tuv))
        else:
            for bid, b in BUILDINGS.items():
                door = b[7]
                if door and math.hypot(p.x - door[0], p.y - door[1]) < 3.0:
                    acts.append((T("Войти: {0}", b[4]), lambda bid=bid: self.enter(bid)))
                    break
            if self.near_car():
                acts.append((T("Открыть капот — работа с машиной"), lambda: g.push(CarWorkScene(g))))
                if point_in(PUMP_ZONE, car.x, car.y):
                    acts.append((T("Заправить машину"), self.refuel))
        if acts:
            self.action = acts[0]
        self.prompt = [a[0] for a in acts]

    def enter(self, bid):
        g = self.game
        name = BUILDINGS[bid][4]
        if bid == "apartment":
            g.sound.play("door", 0.6)
            g.push(ApartmentScene(g))
            return
        if not g.is_open(bid):
            info(g, name, [T("Закрыто."), T("Часы работы: {hours_str}", hours_str=g.hours_str(bid))])
            return
        if bid == "supermarkt":
            g.push(ShopScene(g, T("Супермаркет «Кауфгут»"), SHOP_SUPERMARKT, subtitle=T("Продукты и напитки")))
        elif bid == "autoteile":
            g.push(ShopScene(g, T("Запчасти «Восток»"), SHOP_TEILE,
                             subtitle=T("«Запчасти для Lada, Moskwitsch, Wolga. Привезём из Польши.»")))
        elif bid == "tanke":
            g.push(ShopScene(g, T("Заправка"), SHOP_TANKE, subtitle=T("Открыто круглосуточно")))
        elif bid == "imbiss":
            g.push(ShopScene(g, T("Дёнер-закусочная"), SHOP_IMBISS, subtitle=T("«Со всем и поострее?»")))
        elif bid == "pizzeria":
            self.pizzeria()
        elif bid == "rathaus":
            self.rathaus()
        elif bid == "tuv":
            self.tuv()
        elif bid == "lager":
            self.lager()
        elif bid == "schrott":
            self.schrott()

    # --- заправка
    def refuel(self):
        g, car = self.game, self.game.car
        if car.running:
            info(g, T("Заправка"), [T("«Мотор заглушите!» — кричит заправщик. Заглушите двигатель.")])
            return
        space = TANK - car.fuel

        def fill(l):
            l = min(l, TANK - car.fuel)
            if l <= 0.1:
                g.notify(T("Бак полон."))
                return
            afford = max(0.0, g.p.money) / FUEL_PRICE
            if afford < 1:
                g.notify(T("Денег не хватит даже на литр ({FUEL_PRICE:.2f} ₽).", FUEL_PRICE=FUEL_PRICE), RED)
                return
            if l > afford:
                l = int(afford * 10) / 10.0
                g.notify(T("Денег хватило только на {l:.1f} л.", l=l), YELLOW)
            cost = round(l * FUEL_PRICE, 2)
            if g.pay(cost):
                car.fuel = min(TANK, car.fuel + l)
                g.advance(5)
                g.notify(T("Заправлено {l:.1f} л за {cost:.2f} ₽.", l=l, cost=cost), GREEN)

        g.push(DialogScene(g, T("Заправка — бензин 91"), [
            T("В баке: {fuel:.1f} / {TANK:.0f} л. Цена: {FUEL_PRICE:.2f} ₽/л. У вас: {money:.2f} ₽.", fuel=car.fuel, TANK=TANK, FUEL_PRICE=FUEL_PRICE, money=g.p.money),
            T("Старый мотор 2101 рассчитан на А-76, но и немецкий 91-й переварит.")], [
            (T("10 литров ({0:.2f} ₽)", 10 * FUEL_PRICE), lambda: fill(10), True),
            (T("20 литров ({0:.2f} ₽)", 20 * FUEL_PRICE), lambda: fill(20), True),
            (T("Полный бак ({space:.1f} л = {0:.2f} ₽)", space * FUEL_PRICE, space=space), lambda: fill(space), True),
        ]))

    # --- TÜV
    def tuv(self):
        g, car = self.game, self.game.car
        if not g.is_open("tuv"):
            info(g, T("Техосмотр TÜV"), [T("Закрыто."), T("Часы работы: {hours_str}", hours_str=g.hours_str('tuv'))])
            return
        if not point_in(TUV_YARD, car.x, car.y):
            info(g, T("Техосмотр TÜV"), [T("«Добрый день. Для техосмотра пригоните машину во двор перед зданием.»"),
                                       T("Стоимость проверки: 95 ₽.")])
            return

        def check():
            if not g.pay(95):
                return
            g.advance(45)
            defects = car.tuv_defects()
            p, why = car._start_chance()
            if p <= 0 or car.battery_charge < 10:
                defects.insert(0, T("Автомобиль не заводится своим ходом"))
            if not defects:
                car.tuv_until = g.day + 730
                info(g, T("Техосмотр ПРОЙДЕН!"), [
                    T("Инспектор долго смотрит на «Жигули», потом на вас, потом снова на «Жигули»."),
                    T("«Ну что ж... Существенных дефектов нет.» Он клеит на номер свежую наклейку техосмотра."),
                    T("Техосмотр действует 2 года. Теперь — в ратушу за номерами.")])
            else:
                info(g, T("Техосмотр НЕ ПРОЙДЕН"), [T("Существенные дефекты:"), ""] +
                     [f"• {d}" for d in defects[:14]] + ["", T("Устраните и приезжайте снова.")])

        g.push(DialogScene(g, T("Техосмотр TÜV"), [
            T("Техосмотр для ВАЗ 2102, 1979 года выпуска."),
            T("Проверяют: коррозию, тормоза, шины, свет, выхлоп, амортизаторы, течи.")],
            [(T("Пройти проверку (95 ₽, 45 мин)"), check, True)]))

    # --- Rathaus
    def rathaus(self):
        g, car = self.game, self.game.car

        def register():
            if car.tuv_until < g.day:
                info(g, T("Регистрация машин"), [T("«Без действующего техосмотра регистрации не будет.» Сначала техосмотр.")])
                return
            if g.pay(145):
                g.advance(120)
                car.registered = True
                info(g, T("Регистрация машин"), [
                    T("Два часа в очереди, три формуляра — и номера ваши: {PLATE}.", PLATE=PLATE),
                    T("Страховка и налог (24 ₽) будут списываться еженедельно."),
                    T("Теперь можно ездить легально!")])

        opts = []
        if not car.registered:
            opts.append((T("Поставить машину на учёт (145 ₽: номера + страховка)"), register, True))
        g.push(DialogScene(g, T("Ратуша — регистрация машин"),
                           [T("«Номер сорок семь, пожалуйста...» Служащая госпожа Беккер смотрит поверх очков.")] +
                           ([T("Ваша машина зарегистрирована: {PLATE}.", PLATE=PLATE)] if car.registered else
                            [T("Для регистрации нужен действующий техосмотр.")]), opts))

    # --- склад
    def lager(self):
        g, p = self.game, self.game.p
        h = g.hour
        wd = g.weekday()

        def shift():
            if p.drunk > 15:
                info(g, T("Склад"), [T("Бригадир Вольф: «Да ты пьян! Марш домой!» — сегодня без работы.")])
                return
            if p.energy < 30:
                info(g, T("Склад"), [T("Вы слишком устали для смены (бодрость < 30).")])
                return
            for _ in range(48):
                g.advance(10, working=True)
                if g.game_over:
                    return
            pay = 104.0
            note = ""
            if p.hygiene < 20:
                pay = round(pay * 0.7, 2)
                note = T(" Бригадир ворчал, что от вас воняет (−30%).")
            g.stats["shifts"] += 1
            g.earn(pay, T("за смену на складе"))
            info(g, T("Склад"), [T("8 часов таскали коробки и водили погрузчик. Заработано {pay:.0f} ₽.{note}", pay=pay, note=note)])

        can = wd < 5 and 6 <= h < 9
        g.push(DialogScene(g, T("Склад транспортной фирмы Мюллера"), [
            T("Склад логистической компании. Платят 13 ₽ в час (8 часов = 104 ₽)."),
            T("Смену можно начать по будням с 06:00 до 09:00.")],
            [(T("Отработать смену (8 часов)"), shift, can)]))

    # --- пиццерия
    def pizzeria(self):
        g = self.game

        def take():
            pts = [pt for pt in g.world.delivery_points
                   if 250 < math.hypot(pt[0] - 336, pt[1] - 297) < 1200]
            x, y = random.choice(pts)
            dist = math.hypot(x - 336, y - 297)
            limit = dist / 8.0 + 60
            g.delivery = {"x": x, "y": y, "deadline": g.minutes + limit, "start": g.minutes,
                          "pay": round(10 + dist / 70, 2)}
            info(g, T("Пиццерия «У Луиджи»"), [
                T("Луиджи: «Вот! Пицца с салями. Быстро, быстро!»"),
                T("Адрес отмечен на карте (M). Расстояние ~{dist:.0f} м, время ~{limit:.0f} мин.", dist=dist, limit=limit),
                T("Оплата: {pay:.2f} ₽ + чаевые за скорость. Пешком не успеть!", pay=g.delivery['pay'])])

        def buy():
            if g.pay(9):
                g.add_item("pizza_hot")

        opts = [(T("Купить пиццу (9 ₽)"), buy, True)]
        if g.delivery:
            opts.insert(0, (T("Заказ уже на руках — отвезите его"), None, False))
        else:
            opts.insert(0, (T("Взять заказ на доставку"), take, True))
        g.push(DialogScene(g, T("Пиццерия «У Луиджи»"), [T("Луиджи ищет курьера со своей машиной. Платит за каждый заказ.")], opts))

    def deliver(self):
        g = self.game
        d = g.delivery
        late = g.minutes > d["deadline"]
        pay = round(d["pay"] * (0.5 if late else 1.0), 2)
        tip = 0.0
        if not late:
            left = d["deadline"] - g.minutes
            tip = round(min(8.0, left / 10), 2)
        g.delivery = None
        g.stats["deliveries"] += 1
        g.earn(pay + tip, T("за доставку") + (T(" (опоздали — половина)") if late else T(" (чаевые {tip:.2f})", tip=tip)))

    # --- свалка
    def schrott(self):
        g = self.game
        if g.schrott_day != g.day:
            g.schrott_day = g.day
            rng = random.Random(g.day * 31 + 7)
            pool = [v[1] for v in SLOTS.values()]
            g.schrott_stock = []
            for _ in range(rng.randint(4, 8)):
                pid = rng.choice(pool)
                cond = rng.uniform(20, 75)
                g.schrott_stock.append({"id": pid, "cond": round(cond, 1), "price": used_price(pid, cond)})
            if rng.random() < 0.4:
                g.schrott_stock.append({"id": "metal", "cond": 100, "price": 6.0})
        g.push(DialogScene(g, T("Авторазборка Ковальского"), [
            T("Пан Ковальский: «Лада? О, у меня стояла одна 2103, всё поснимали. Посмотри, может, что есть.»"),
            T("Ассортимент меняется каждый день.")], [
            (T("Купить б/у запчасти"), lambda: g.push(ShopScene(g, T("Свалка — б/у запчасти"), [], mode="used",
                                                           stock=g.schrott_stock,
                                                           subtitle=T("Всё как есть, без гарантии"))), True),
            (T("Продать старые детали"), lambda: g.push(ShopScene(g, T("Свалка — скупка"), [], mode="sell",
                                                             subtitle=T("Цена зависит от состояния"))), True),
        ]))

    # ------------------------------------------------------------ отрисовка
    def draw(self, surf):
        g, p, car, w = self.game, self.game.p, self.game.car, self.game.world
        cam = self.cam
        if p.drunk > 30:
            cam = (cam[0] + math.sin(g.t * 0.9) * p.drunk / 60, cam[1] + math.cos(g.t * 0.7) * p.drunk / 80)
        w.draw(surf, cam)
        if g.weather == "rain":
            wet = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            wet.fill((20, 30, 60, 40))
            surf.blit(wet, (0, 0))
        # цель доставки
        if g.delivery:
            d = g.delivery
            sx, sy = (d["x"] - cam[0]) * PPM, (d["y"] - cam[1]) * PPM
            r = 14 + 5 * math.sin(g.t * 5)
            pygame.draw.circle(surf, YELLOW, (int(sx), int(sy)), int(r), 3)
        for ai in w.ai:
            ai.draw(surf, cam, g.t)
            ai.siren = max(0.0, ai.siren - 1 / 60)
        car.draw_top(surf, cam, g.t)
        if not p.in_car:
            sx, sy = (p.x - cam[0]) * PPM, (p.y - cam[1]) * PPM
            bob = math.sin(self.walk_phase) * 1.5
            pygame.draw.circle(surf, (0, 0, 0), (int(sx) + 2, int(sy) + 2), 6)
            pygame.draw.circle(surf, (40, 60, 140), (int(sx), int(sy + bob)), 6)
            pygame.draw.circle(surf, (230, 190, 160), (int(sx), int(sy + bob)), 3)
        w.draw_trees(surf, cam)
        self.draw_night(surf, cam)
        if g.weather == "rain":
            for dr in self.drops:
                dr[0] -= 2
                dr[1] += 14
                if dr[1] > HEIGHT:
                    dr[0], dr[1] = random.uniform(0, WIDTH + 100), -10
                pygame.draw.line(surf, (160, 170, 200), (dr[0], dr[1]), (dr[0] - 2, dr[1] + 8), 1)
        if self.flash > 0:
            fl = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            fl.fill((255, 255, 255, int(200 * self.flash)))
            surf.blit(fl, (0, 0))
        place = T("За рулём ВАЗ 2102") if p.in_car else T("Кляйнбрук")
        rd = w.road_at(p.x, p.y)
        if rd:
            place = rd[5]
        draw_hud(surf, g, place)
        self.draw_minimap(surf)
        if p.in_car:
            self.draw_dash(surf)
        if self.prompt:
            y = HEIGHT - (170 if p.in_car else 60)
            ui.panel(surf, (WIDTH // 2 - 260, y - 6, 520, 12 + 24 * len(self.prompt[:2])), 210)
            ui.text(surf, f"E — {self.prompt[0]}", (WIDTH // 2, y + 6), 18, YELLOW, center=True)
            if not p.in_car and self.near_car():
                ui.text(surf, T("F — сесть за руль"), (WIDTH // 2, y + 30), 16, WHITE, center=True)
        elif not p.in_car and self.near_car():
            ui.panel(surf, (WIDTH // 2 - 200, HEIGHT - 66, 400, 36), 210)
            ui.text(surf, T("F — сесть за руль"), (WIDTH // 2, HEIGHT - 48), 18, YELLOW, center=True)
        if g.delivery:
            d = g.delivery
            left = d["deadline"] - g.minutes
            col = GREEN if left > 15 else (ORANGE if left > 0 else RED)
            ui.panel(surf, (WIDTH // 2 - 170, 8, 340, 30), 210)
            ui.text(surf, T("Доставка пиццы: {0:.0f} мин  ·  {hypot:.0f} м", max(0, left), hypot=math.hypot(d['x'] - p.x, d['y'] - p.y)),
                    (WIDTH // 2, 23), 16, col, center=True)
        if self.show_map:
            self.draw_bigmap(surf)

    def draw_night(self, surf, cam):
        g, car = self.game, self.game.car
        dk = g.darkness()
        if g.weather == "rain":
            dk = max(dk, 0.15)
        if dk <= 0.01:
            return
        self.dark.fill((5, 8, 25, int(235 * dk)))
        vw, vh = WIDTH / PPM, HEIGHT / PPM
        lr = self.lamp_light.get_width() // 2
        if g.darkness() > 0.2:
            for lx, ly in g.world.lamps:
                if cam[0] - 20 < lx < cam[0] + vw + 20 and cam[1] - 20 < ly < cam[1] + vh + 20:
                    sx, sy = (lx - cam[0]) * PPM, (ly - cam[1]) * PPM
                    self.dark.blit(self.lamp_light, (sx - lr, sy - lr), special_flags=pygame.BLEND_RGBA_SUB)
            for h in g.world.houses[::3]:
                if cam[0] - 20 < h[0] < cam[0] + vw + 20 and cam[1] - 20 < h[1] < cam[1] + vh + 20:
                    sx, sy = (h[6][0] - cam[0]) * PPM, (h[6][1] - cam[1]) * PPM
                    r = self.small_light.get_width() // 2
                    self.dark.blit(self.small_light, (sx - r, sy - r), special_flags=pygame.BLEND_RGBA_SUB)
        if car.lights and car.battery_charge > 2 and car.c("lights") > 0.05:
            fx, fy = car.forward()
            rot = pygame.transform.rotate(self.head_cone, -math.degrees(car.angle))
            k = 0.4 + 0.6 * car.c("lights")
            cxp = (car.x + fx * 2.0 - cam[0]) * PPM + fx * self.head_cone.get_width() / 2
            cyp = (car.y + fy * 2.0 - cam[1]) * PPM + fy * self.head_cone.get_width() / 2
            if k < 0.99:
                rot.fill((255, 255, 255, int(255 * k)), special_flags=pygame.BLEND_RGBA_MULT)
            self.dark.blit(rot, rot.get_rect(center=(cxp, cyp)), special_flags=pygame.BLEND_RGBA_SUB)
        surf.blit(self.dark, (0, 0))

    def draw_minimap(self, surf):
        g, p = self.game, self.game.p
        size = 200
        x0, y0 = WIDTH - 210, 70
        k = 0.5
        area = pygame.Rect(int(p.x * k - size / 2), int(p.y * k - size / 2), size, size)
        mm = pygame.Surface((size, size))
        mm.fill((40, 60, 35))
        mm.blit(self.mapsurf, (0, 0), area)
        pygame.draw.circle(mm, RED if p.in_car else WHITE, (size // 2, size // 2), 4)
        car = g.car
        if not p.in_car:
            cx, cy = car.x * k - area.x, car.y * k - area.y
            if 0 <= cx < size and 0 <= cy < size:
                pygame.draw.circle(mm, (230, 200, 60), (int(cx), int(cy)), 4)
        if g.delivery:
            d = g.delivery
            dx, dy = d["x"] * k - area.x, d["y"] * k - area.y
            if 0 <= dx < size and 0 <= dy < size:
                pygame.draw.circle(mm, YELLOW, (int(dx), int(dy)), 5, 2)
            else:
                a = math.atan2(dy - size / 2, dx - size / 2)
                pygame.draw.circle(mm, YELLOW, (int(size / 2 + math.cos(a) * 90), int(size / 2 + math.sin(a) * 90)), 5)
        surf.blit(mm, (x0, y0))
        pygame.draw.rect(surf, (90, 90, 95), (x0, y0, size, size), 1)
        ui.text(surf, T("M — карта"), (x0 + 4, y0 + size + 2), 13, GREY)

    def draw_bigmap(self, surf):
        g = self.game
        dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 200))
        surf.blit(dim, (0, 0))
        bm = self.bigmap
        ox = (WIDTH - bm.get_width()) // 2
        oy = 30
        surf.blit(bm, (ox, oy))
        k = self.bigmap_k
        for bid, b in BUILDINGS.items():
            ui.text(surf, b[4], (ox + (b[0] + b[2] / 2) * k, oy + b[1] * k - 12), 11, WHITE, center=True)
        for r in ROADS:
            if r[2] > 300 or r[3] > 300:
                ui.text(surf, r[5], (ox + (r[0] + r[2] / 2) * k, oy + (r[1] + r[3] / 2) * k), 11, (250, 240, 150), center=True)
        pygame.draw.circle(surf, RED, (int(ox + g.p.x * k), int(oy + g.p.y * k)), 5)
        pygame.draw.circle(surf, (230, 200, 60), (int(ox + g.car.x * k), int(oy + g.car.y * k)), 4, 2)
        if g.delivery:
            pygame.draw.circle(surf, YELLOW, (int(ox + g.delivery["x"] * k), int(oy + g.delivery["y"] * k)), 7, 2)
        ui.text(surf, T("Кляйнбрук (Нижняя Саксония)  ·  красная точка — вы, жёлтый круг — машина  ·  M/Esc — закрыть"),
                (WIDTH // 2, HEIGHT - 20), 14, WHITE, center=True)

    def draw_dash(self, surf):
        g, car = self.game, self.game.car
        r = pygame.Rect(WIDTH // 2 - 330, HEIGHT - 112, 660, 104)
        ui.panel(surf, r, 230)
        # спидометр
        ui.text(surf, f"{car.kmh():3.0f}", (r.x + 70, r.y + 12), 44, WHITE, bold=True, center=False)
        ui.text(surf, T("км/ч"), (r.x + 150, r.y + 34), 14, GREY)
        ui.text(surf, T("{odometer:09.1f} км", odometer=car.odometer), (r.x + 22, r.y + 74), 13, GREY)
        # тахометр
        rx = r.x + 210
        ui.text(surf, T("об/мин {rpm:4.0f}", rpm=car.rpm), (rx, r.y + 10), 14, WHITE)
        pygame.draw.rect(surf, (40, 40, 44), (rx, r.y + 32, 200, 14))
        fr = min(1, car.rpm / 7000)
        pygame.draw.rect(surf, RED if car.rpm > 5600 else GREEN, (rx, r.y + 32, int(200 * fr), 14))
        pygame.draw.line(surf, RED, (rx + 160, r.y + 30), (rx + 160, r.y + 48), 2)
        # передача
        ui.text(surf, GEAR_NAMES[car.gear], (rx + 230, r.y + 8), 48, YELLOW, bold=True)
        # топливо и температура
        ui.text(surf, T("Бензин"), (rx, r.y + 54), 13, GREY)
        ui.bar(surf, rx + 55, r.y + 56, 90, 10, car.fuel, TANK)
        ui.text(surf, f"{car.temp:.0f}°C", (rx + 150, r.y + 52), 14, RED if car.temp > 105 else WHITE)
        ui.text(surf, T("АКБ"), (rx, r.y + 74), 13, GREY)
        ui.bar(surf, rx + 55, r.y + 76, 90, 10, car.battery_charge)
        # лампы
        lx = r.x + 490
        lamps = [
            (T("МАСЛО"), car.oil < 1.3 and (car.running or car.cranking), RED),
            (T("ЗАРЯД"), not car.running and car.battery_charge > 5 or car.c("belt") < 0.05, RED),
            (T("ПОДСОС"), car.choke, ORANGE),
            (T("ФАРЫ"), car.lights, BLUE),
            (T("СЦЕПЛ."), pygame.key.get_pressed()[pygame.K_SPACE], GREY),
        ]
        for i, (name, on, col) in enumerate(lamps):
            yy = r.y + 8 + i * 19
            pygame.draw.circle(surf, col if on else (45, 45, 48), (lx, yy + 8), 6)
            ui.text(surf, name, (lx + 12, yy), 13, WHITE if on else GREY)
        # знак ограничения
        lim = g.world.speed_limit(car.x, car.y)
        cx, cy = r.right + 40, r.y + 50
        pygame.draw.circle(surf, WHITE, (cx, cy), 28)
        if lim:
            pygame.draw.circle(surf, RED, (cx, cy), 28, 5)
            ui.text(surf, str(lim), (cx, cy), 20, (10, 10, 10), bold=True, center=True, shadow=False)
        else:
            pygame.draw.line(surf, (30, 30, 30), (cx - 18, cy + 18), (cx + 18, cy - 18), 3)
        if not car.running:
            ui.text(surf, T("I (держать) — стартер") + (T("   C — подсос") if car.temp < 45 and not car.choke else ""),
                    (r.x + 10, r.y - 24), 15, YELLOW)
