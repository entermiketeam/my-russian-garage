"""Работа с машиной: детали, жидкости, зарядка, сварка кузова. Вид сбоку."""
import pygame
import engine as _eng

import ui
from config import WIDTH, HEIGHT, WHITE, GREY, YELLOW, GREEN, RED, ORANGE
from scenes_menu import Scene, DialogScene, InventoryScene, info
from items import SLOTS, PANELS, ITEMS, item_name
from world import GARAGE, point_in
from car import TANK, OIL_CAP, COOLANT_CAP
from i18n import T


class CarWorkScene(Scene):
    time_flows = True

    def __init__(self, game):
        super().__init__(game)
        self.menu = ui.ListMenu()
        self.stack = ["root"]
        self.slot = None
        self.panel = None
        self.refresh()

    @property
    def car(self):
        return self.game.car

    def in_garage(self):
        return point_in(GARAGE, self.car.x, self.car.y)

    # --------------------------------------------------------------- меню
    def refresh(self):
        g, car = self.game, self.car
        mode = self.stack[-1]
        items = []
        if mode == "root":
            items = [
                (T("Детали (снять / поставить)"), "parts", True),
                (T("Жидкости (масло, антифриз, бензин...)"), "fluids", True),
                (T("Кузов и ржавчина (сварка, покраска)"), "body", True),
                ((T("Зарядить аккумулятор"), T("3 ч, в гараже")), "charge", True),
                (T("Закрыть капот"), "exit", True),
            ]
            self.menu.title = T("ВАЗ 2102 — работа с машиной")
        elif mode == "parts":
            for s, (name, pid, mins) in SLOTS.items():
                p = car.parts.get(s)
                right = T("НЕТ") if p is None else f"{p['cond']:.0f}%"
                items.append(((name, right), ("slot", s), True))
            items.append((T("← Назад"), "back", True))
            self.menu.title = T("Детали")
        elif mode == "slot":
            s = self.slot
            name, pid, mins = SLOTS[s]
            p = car.parts.get(s)
            if p is not None:
                items.append(((T("Снять: {item_name} ({cond:.0f}%)", item_name=item_name(p['id']), cond=p['cond']), T("{mins} мин", mins=mins)), ("remove", s), True))
            else:
                cands = sorted([e for e in g.p.inventory if e["id"] == pid], key=lambda e: -e["cond"])
                for e in cands:
                    items.append(((T("Поставить: {item_name} ({cond:.0f}%)", item_name=item_name(pid), cond=e['cond']), T("{mins} мин", mins=mins)),
                                  ("install", e), True))
                if not cands:
                    items.append((T("Нет детали «{item_name}» в инвентаре", item_name=item_name(pid)), None, False))
            items.append((T("← Назад"), "back", True))
            self.menu.title = name
        elif mode == "fluids":
            items = [
                ((T("Долить масло 15W-40 (канистр: {count})", count=g.count('oil')), T("10 мин")), "oil_add", True),
                ((T("Слить старое масло"), T("20 мин")), "oil_drain", True),
                ((T("Долить антифриз (канистр: {count})", count=g.count('coolant')), T("10 мин")), "cool_add", True),
                ((T("Долить тормозную жидкость ({count})", count=g.count('brake_fl')), T("15 мин")), "brake_add", True),
                ((T("Залить бензин из канистры ({count})", count=g.count('fuel_can')), T("5 мин")), "fuel_add", True),
                (T("← Назад"), "back", True),
            ]
            self.menu.title = T("Жидкости")
        elif mode == "body":
            for p, name in PANELS.items():
                v = car.rust[p]
                tag = T(" (покрашено)") if car.painted[p] else ""
                items.append(((name + tag, f"{v:.0f}%"), ("panel", p), True))
            items.append((T("← Назад"), "back", True))
            self.menu.title = T("Кузов — ржавчина")
        elif mode == "panel":
            p = self.panel
            big = p in ("floor", "sill_l", "sill_r")
            need = 2 if big else 1
            items = [
                ((T("Вырезать гниль и вварить металл ({need} лист.)", need=need), T("2 ч")), "weld", True),
                ((T("Обработать преобразователем ржавчины"), T("20 мин")), "conv", True),
                ((T("Загрунтовать и покрасить"), T("40 мин")), "paint", True),
                (T("← Назад"), "back", True),
            ]
            self.menu.title = T("{0}: {1:.0f}% ржавчины", PANELS[p], car.rust[p])
        self.menu.set_items(items)

    def go(self, mode):
        self.stack.append(mode)
        self.menu.index = 0
        self.refresh()

    def back(self):
        if len(self.stack) > 1:
            self.stack.pop()
            self.menu.index = 0
            self.refresh()
        else:
            self.game.pop()

    # --------------------------------------------------------------- действия
    def need_off(self):
        if self.car.running:
            self.game.notify(T("Сначала заглушите двигатель."), RED)
            return False
        return True

    def work(self, minutes, sound="tool"):
        self.game.sound.play(sound, 0.6)
        g = self.game
        step = 10
        left = minutes
        while left > 0:
            g.advance(min(step, left), working=True)
            left -= step

    def handle(self, ev):
        g, car = self.game, self.car
        if ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                self.back()
                return
            if ev.key in (pygame.K_TAB, pygame.K_i):
                g.push(InventoryScene(g))
                return
        sel = self.menu.handle(ev)
        if sel is None:
            return
        if sel == "back":
            self.back()
            return
        if sel == "exit":
            g.pop()
            return
        if sel in ("parts", "fluids", "body"):
            self.go(sel)
            return
        if isinstance(sel, tuple) and sel[0] == "slot":
            self.slot = sel[1]
            self.go("slot")
            return
        if isinstance(sel, tuple) and sel[0] == "panel":
            self.panel = sel[1]
            self.go("panel")
            return

        if sel == "charge":
            if not self.in_garage():
                g.notify(T("Зарядка — только в гараже (нужна розетка)."), RED)
            elif not g.has("charger"):
                g.notify(T("Нужно зарядное устройство (магазин «Восток»)."), RED)
            elif not car.has("battery"):
                g.notify(T("Аккумулятор не установлен."), RED)
            else:
                g.advance(180)
                car.battery_charge = 100.0 * (0.3 + 0.7 * car.c("battery"))
                g.notify(T("Аккумулятор заряжен: {battery_charge:.0f}% (зависит от износа АКБ).", battery_charge=car.battery_charge), GREEN)
        elif isinstance(sel, tuple) and sel[0] == "remove":
            s = sel[1]
            if not self.need_off():
                return
            if not g.has("toolbox"):
                g.notify(T("Нужен набор ключей."), RED)
                return
            part = car.parts[s]
            self.work(SLOTS[s][2])
            car.parts[s] = None
            entry = {"id": part["id"], "cond": round(float(part["cond"]), 1)}
            if s == "engine":
                car.oil = 0.0
                entry["sub"] = _eng.remove_whole(car)      # внутренности двигателя едут вместе с ним
            g.p.inventory.append(entry)
            g.notify(T("Снято: {item_name} ({cond:.0f}%)", item_name=item_name(part['id']), cond=part['cond']), GREEN)
            self.back()
        elif isinstance(sel, tuple) and sel[0] == "install":
            e = sel[1]
            s = self.slot
            if not self.need_off():
                return
            if not g.has("toolbox"):
                g.notify(T("Нужен набор ключей."), RED)
                return
            g.take_item(e["id"], e)
            self.work(SLOTS[s][2])
            car.parts[s] = {"id": e["id"], "cond": e["cond"]}
            if s == "engine":
                _eng.install_whole(car, e)
            if s == "battery":
                car.battery_charge = 60.0 if e["cond"] > 95 else 20.0
            g.notify(T("Установлено: {item_name}", item_name=item_name(e['id'])), GREEN)
            if s == "engine":
                g.notify(T("Не забудьте залить масло в новый двигатель!"), YELLOW)
            self.back()
        elif sel == "oil_add":
            if not g.has("oil"):
                g.notify(T("Нет масла. Купите в магазине «Восток» или на заправке."), RED)
            elif car.oil >= OIL_CAP - 0.1:
                g.notify(T("Масла и так по верхней метке."), YELLOW)
            else:
                g.take_item("oil")
                fresh = min(4.0, OIL_CAP + 0.25 - car.oil)
                total = car.oil + fresh
                car.oil_quality = (car.oil * car.oil_quality + fresh * 100) / total
                car.oil = min(OIL_CAP + 0.25, total)
                self.work(10)
                g.notify(T("Масло: {oil:.2f} л, качество {oil_quality:.0f}%.", oil=car.oil, oil_quality=car.oil_quality), GREEN)
        elif sel == "oil_drain":
            if not self.need_off():
                return
            self.work(20)
            car.oil = 0.0
            car.oil_quality = 100.0
            g.notify(T("Старое масло слито (чёрное, как нефть). Залейте новое!"), YELLOW)
        elif sel == "cool_add":
            if not g.has("coolant"):
                g.notify(T("Нет антифриза."), RED)
            elif car.coolant >= COOLANT_CAP - 0.1:
                g.notify(T("Антифриза достаточно."), YELLOW)
            else:
                g.take_item("coolant")
                car.coolant = min(COOLANT_CAP, car.coolant + 5)
                self.work(10)
                g.notify(T("Антифриз: {coolant:.1f} л.", coolant=car.coolant), GREEN)
                if car.c("radiator") < 0.25:
                    g.notify(T("Радиатор течёт — антифриз будет уходить."), ORANGE)
        elif sel == "brake_add":
            if not g.has("brake_fl"):
                g.notify(T("Нет тормозной жидкости."), RED)
            else:
                g.take_item("brake_fl")
                car.brake_fluid = 100.0
                self.work(15)
                g.notify(T("Тормозная жидкость заменена, тормоза прокачаны."), GREEN)
        elif sel == "fuel_add":
            if not g.has("fuel_can"):
                g.notify(T("Нет канистры с бензином."), RED)
            elif car.fuel > TANK - 1:
                g.notify(T("Бак полон."), YELLOW)
            else:
                g.take_item("fuel_can")
                car.fuel = min(TANK, car.fuel + 10)
                self.work(5)
                g.notify(T("В баке {fuel:.1f} л.", fuel=car.fuel), GREEN)
        elif sel in ("weld", "conv", "paint"):
            self.body_work(sel)
        self.refresh()

    def body_work(self, what):
        g, car = self.game, self.car
        p = self.panel
        if what == "weld":
            need = 2 if p in ("floor", "sill_l", "sill_r") else 1
            if not self.in_garage():
                g.notify(T("Сварка — только в гараже."), RED)
            elif not g.has("welder"):
                g.notify(T("Нужен сварочный аппарат (магазин «Восток», 320 ₽)."), RED)
            elif g.count("metal") < need:
                g.notify(T("Нужно листов металла: {need}.", need=need), RED)
            elif car.rust[p] < 15:
                g.notify(T("Здесь варить нечего — только поверхностная ржавчина."), YELLOW)
            else:
                for _ in range(need):
                    g.take_item("metal")
                self.work(120, "weld")
                car.rust[p] = 6.0
                car.painted[p] = False
                car._sprite_key = None
                g.p.hygiene = max(0, g.p.hygiene - 15)
                g.notify(T("{0}: гниль вырезана, вварена заплатка. Покрасьте, иначе снова заржавеет!", PANELS[p]), GREEN)
        elif what == "conv":
            if not g.has("rust_conv"):
                g.notify(T("Нет преобразователя ржавчины."), RED)
            elif car.rust[p] > 55:
                g.notify(T("Тут уже дыры — поможет только сварка."), ORANGE)
            else:
                g.take_item("rust_conv")
                self.work(20)
                car.rust[p] = max(0.0, car.rust[p] - 12)
                car._sprite_key = None
                g.notify(T("{0}: ржавчина обработана.", PANELS[p]), GREEN)
        elif what == "paint":
            if not g.has("paint"):
                g.notify(T("Нет грунта и краски."), RED)
            elif car.rust[p] > 20:
                g.notify(T("Красить по ржавчине бессмысленно — сначала сварка/преобразователь."), ORANGE)
            else:
                g.take_item("paint")
                self.work(40)
                car.painted[p] = True
                g.notify(T("{0}: покрашено. Теперь ржавеет в 4 раза медленнее.", PANELS[p]), GREEN)

    # --------------------------------------------------------------- отрисовка
    def draw(self, surf):
        g, car = self.game, self.car
        garage = self.in_garage()
        if garage:
            surf.fill((70, 66, 60))
            for y in range(0, 480, 24):
                off = 0 if (y // 24) % 2 == 0 else 30
                for x in range(-30 + off, 720, 60):
                    pygame.draw.rect(surf, (82, 76, 68), (x, y, 58, 22))
            # полка с банками и стенд с ключами
            pygame.draw.rect(surf, (90, 60, 40), (40, 110, 240, 10))
            for i, c in enumerate([(200, 170, 40), (40, 90, 160), (160, 40, 40), (60, 120, 60), (200, 200, 200)]):
                pygame.draw.rect(surf, c, (50 + i * 45, 72, 30, 38))
            pygame.draw.rect(surf, (120, 100, 70), (400, 40, 260, 110))
            for i in range(9):
                pygame.draw.line(surf, (180, 180, 185), (420 + i * 27, 60), (420 + i * 27, 60 + 30 + (i % 3) * 12), 4)
            pygame.draw.rect(surf, (230, 230, 200), (200, 8, 300, 8))  # лампа дневного света
            if g.has("welder"):
                pygame.draw.rect(surf, (40, 90, 150), (20, 380, 70, 70))
                ui.text(surf, T("Сварка"), (24, 400), 12)
            if g.has("charger"):
                pygame.draw.rect(surf, (200, 150, 30), (620, 400, 60, 40))
        else:
            sky = (140, 165, 190) if g.darkness() < 0.3 else (25, 30, 45)
            surf.fill(sky)
            pygame.draw.rect(surf, (90, 110, 70), (0, 330, 720, 160))
        pygame.draw.rect(surf, (48, 48, 50), (0, 470, 720, HEIGHT - 470))
        car.draw_side(surf, 55, 470, 150)

        # информация
        ui.panel(surf, (10, 490, 700, 222), 225)
        tuv = T("действует") if car.tuv_until >= g.day else T("нет")
        rows = [
            (T("Бензин"), T("{fuel:.1f} / {TANK:.0f} л", fuel=car.fuel, TANK=TANK), car.fuel / TANK * 100),
            (T("Масло"), T("{oil:.2f} / {OIL_CAP} л, кач. {oil_quality:.0f}%", oil=car.oil, OIL_CAP=OIL_CAP, oil_quality=car.oil_quality), car.oil / OIL_CAP * 100),
            (T("Антифриз"), T("{coolant:.1f} / {COOLANT_CAP} л", coolant=car.coolant, COOLANT_CAP=COOLANT_CAP), car.coolant / COOLANT_CAP * 100),
            (T("Торм. жидкость"), f"{car.brake_fluid:.0f}%", car.brake_fluid),
            (T("Заряд АКБ"), f"{car.battery_charge:.0f}%", car.battery_charge),
        ]
        y = 500
        for name, val, pct in rows:
            ui.text(surf, name, (24, y), 15)
            ui.bar(surf, 150, y + 2, 150, 14, pct)
            ui.text(surf, val, (312, y), 15, GREY)
            y += 24
        ui.text(surf, T("Пробег: {odometer:.0f} км   Темп.: {temp:.0f}°C", odometer=car.odometer, temp=car.temp), (24, y + 4), 15)
        ui.text(surf, T("Техосмотр: {tuv}   Номера: {0}   "
                      "{1}", T('есть') if car.registered else T('нет'), T('В гараже') if garage else T('На улице (сварка и зарядка недоступны)'), tuv=tuv),
                (24, y + 28), 15, GREEN if garage else ORANGE)
        ui.text(surf, T("Макс. ржавчина: {max_rust:.0f}%", max_rust=car.max_rust()), (24, y + 52), 15,
                RED if car.max_rust() > 45 else WHITE)

        # правое меню
        ui.panel(surf, (722, 10, 548, 700), 235)
        self.menu.draw(surf, 742, 22, 510, rows=22, size=16)
        if self.stack[-1] == "parts":
            cur = self.menu.current()
            if isinstance(cur, tuple):
                p = car.parts.get(cur[1])
                if p is not None:
                    ui.bar(surf, 742, 668, 500, 10, p["cond"])
        ui.text(surf, T("Enter — выбрать, Esc — назад, Tab — инвентарь"), (742, 686), 14, GREY)
        # компактный HUD поверх
        ui.panel(surf, (8, 8, 300, 30), 200)
        ui.text(surf, f"{g.time_str()}   {g.p.money:.2f} ₽", (16, 12), 16, WHITE)
