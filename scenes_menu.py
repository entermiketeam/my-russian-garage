"""Меню, диалоги, магазины, инвентарь."""
import os
import random

import pygame

import ui
from config import WIDTH, HEIGHT, WHITE, GREY, YELLOW, RED, GREEN, ORANGE, SAVE_FILE, font
from items import ITEMS, item_name, SLOTS


class Scene:
    time_flows = False
    overlay = False

    def __init__(self, game):
        self.game = game

    def handle(self, ev):
        pass

    def update(self, dt):
        pass

    def draw(self, surf):
        pass


# ============================================================ диалог
class DialogScene(Scene):
    """Окно с текстом и вариантами. options: [(label, callback|None, enabled)]."""
    overlay = True
    time_flows = False

    def __init__(self, game, title, lines, options=None, width=720):
        super().__init__(game)
        self.title = title
        self.lines = lines if isinstance(lines, list) else [lines]
        opts = list(options or [])
        opts.append(("Закрыть", None, True))
        self.menu = ui.ListMenu(opts)
        self.width = width

    def handle(self, ev):
        if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_ESCAPE, pygame.K_TAB):
            self.game.pop()
            return
        cb = self.menu.handle(ev)
        if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_RETURN, pygame.K_e, pygame.K_SPACE):
            it = self.menu.items[self.menu.index]
            if len(it) > 2 and not it[2]:
                return
            if cb is None:
                self.game.pop()
            else:
                self.game.pop()
                cb()

    def draw(self, surf):
        wrapped = []
        for l in self.lines:
            if l == "":
                wrapped.append("")
            else:
                wrapped += ui.wrap(l, 18, self.width - 50)
        h = 90 + len(wrapped) * 24 + len(self.menu.items) * 27
        h = min(h, HEIGHT - 40)
        r = pygame.Rect(0, 0, self.width, h)
        r.center = (WIDTH // 2, HEIGHT // 2)
        dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 110))
        surf.blit(dim, (0, 0))
        ui.panel(surf, r, 240)
        ui.text(surf, self.title, (r.x + 24, r.y + 18), 24, YELLOW, bold=True)
        y = r.y + 58
        for l in wrapped:
            ui.text(surf, l, (r.x + 24, y), 18)
            y += 24
        self.menu.draw(surf, r.x + 30, y + 10, self.width - 60, rows=12, size=18)


def info(game, title, lines):
    game.push(DialogScene(game, title, lines))


# ============================================================ магазин
class ShopScene(Scene):
    overlay = False
    time_flows = True

    def __init__(self, game, title, item_ids, mode="buy", stock=None, subtitle=""):
        super().__init__(game)
        self.title = title
        self.subtitle = subtitle
        self.item_ids = item_ids
        self.mode = mode          # buy / used / sell
        self.stock = stock        # для б/у: список {"id","cond","price"}
        self.menu = ui.ListMenu()
        self.refresh()

    def refresh(self):
        g = self.game
        items = []
        if self.mode == "buy":
            for iid in self.item_ids:
                it = ITEMS[iid]
                have = g.count(iid)
                label = (f"{it['name']}" + (f"  (есть {have})" if have else ""), f"{it['price']:.2f} DM")
                items.append((label, ("buy", iid), True))
        elif self.mode == "used":
            for e in self.stock:
                label = (f"{item_name(e['id'])} — б/у, {e['cond']:.0f}%", f"{e['price']:.2f} DM")
                items.append((label, ("used", e), True))
            if not self.stock:
                items.append(("Сегодня ничего нет. Приходите завтра.", None, False))
        else:
            for e in g.p.inventory:
                it = ITEMS.get(e["id"], {})
                if it.get("kind") not in ("part", "tool"):
                    continue
                price = self.sell_price(e)
                label = (f"{it['name']} ({e['cond']:.0f}%)", f"{price:.2f} DM")
                items.append((label, ("sell", e), True))
            if not items:
                items.append(("Нечего продавать (только детали и инструменты).", None, False))
        self.menu.set_items(items)

    def sell_price(self, e):
        from actions import sell_price
        return sell_price(e)

    def handle(self, ev):
        if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_ESCAPE, pygame.K_TAB, pygame.K_q):
            self.game.pop()
            return
        sel = self.menu.handle(ev)
        if not sel:
            return
        g = self.game
        kind, data = sel
        if kind == "buy":
            it = ITEMS[data]
            if g.pay(it["price"]):
                g.add_item(data)
                g.notify(f"Куплено: {it['name']}", GREEN)
        elif kind == "used":
            if data in self.stock and g.pay(data["price"]):
                g.add_item(data["id"], data["cond"])
                self.stock.remove(data)
                g.notify(f"Куплено б/у: {item_name(data['id'])}", GREEN)
        elif kind == "sell":
            if data in g.p.inventory:
                price = self.sell_price(data)
                g.take_item(data["id"], data)
                g.earn(price, "(продажа)")
        self.refresh()

    def draw(self, surf):
        surf.fill((28, 30, 34))
        # полки
        for i in range(6):
            pygame.draw.rect(surf, (60, 50, 40), (40, 120 + i * 90, 480, 10))
            rr = random.Random(i + len(self.title))
            for k in range(9):
                c = (rr.randint(60, 220), rr.randint(60, 200), rr.randint(40, 180))
                h = rr.randint(30, 70)
                pygame.draw.rect(surf, c, (50 + k * 52, 120 + i * 90 - h, 40, h))
        ui.panel(surf, (560, 30, 690, 660), 235)
        ui.text(surf, self.title, (585, 45), 26, YELLOW, bold=True)
        if self.subtitle:
            ui.text(surf, self.subtitle, (585, 80), 15, GREY)
        ui.text(surf, f"Деньги: {self.game.p.money:.2f} DM", (1230, 48), 18, GREEN, right=True)
        self.menu.draw(surf, 590, 110, 640, rows=19, size=17)
        ui.text(surf, "W/S — выбор, Enter — купить/продать, Esc — выйти", (585, 660), 14, GREY)
        cur = self.menu.current()
        if cur and cur[0] == "buy" and ITEMS[cur[1]].get("note"):
            ui.text(surf, ITEMS[cur[1]]["note"], (40, 660), 15, ORANGE)
        if cur and cur[0] == "buy":
            iid = cur[1]
            it = ITEMS[iid]
            slots = [SLOTS[s][0] for s in SLOTS if SLOTS[s][1] == iid]
            if slots:
                ui.text(surf, "Ставится: " + ", ".join(slots), (40, 630), 15, WHITE)


# ============================================================ инвентарь
class InventoryScene(Scene):
    overlay = True
    time_flows = True

    def __init__(self, game, only_food=False, title="Инвентарь"):
        super().__init__(game)
        self.only_food = only_food
        self.title = title
        self.menu = ui.ListMenu()
        self.refresh()

    def refresh(self):
        g = self.game
        groups = {}
        for e in g.p.inventory:
            it = ITEMS.get(e["id"], {})
            if self.only_food and it.get("kind") not in ("food", "drink"):
                continue
            key = e["id"] if it.get("kind") != "part" else (e["id"], round(e["cond"]))
            groups.setdefault(key, []).append(e)
        items = []
        order = {"food": 0, "drink": 1, "fluid": 2, "material": 3, "part": 4, "tool": 5}
        for key, es in sorted(groups.items(), key=lambda kv: (order.get(ITEMS[kv[1][0]["id"]]["kind"], 9), str(kv[0]))):
            e = es[0]
            it = ITEMS[e["id"]]
            name = it["name"]
            if it["kind"] == "part":
                name += f"  [{e['cond']:.0f}%]"
            usable = it["kind"] in ("food", "drink")
            hint = "съесть/выпить" if usable else it["kind"].replace("part", "деталь").replace(
                "tool", "инструмент").replace("fluid", "жидкость").replace("material", "материал")
            items.append(((f"{name}  x{len(es)}", hint), e, usable))
        if not items:
            items.append(("Пусто", None, False))
        self.menu.set_items(items)

    def handle(self, ev):
        if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_ESCAPE, pygame.K_TAB, pygame.K_i):
            self.game.pop()
            return
        e = self.menu.handle(ev)
        if e:
            self.game.take_item(e["id"], e)
            self.game.consume(e["id"])
            self.refresh()

    def draw(self, surf):
        r = pygame.Rect(WIDTH // 2 - 380, 60, 760, 600)
        ui.panel(surf, r, 240)
        ui.text(surf, self.title, (r.x + 20, r.y + 16), 24, YELLOW, bold=True)
        p = self.game.p
        ui.text(surf, f"{p.money:.2f} DM", (r.right - 20, r.y + 18), 20, GREEN, right=True)
        self.menu.draw(surf, r.x + 26, r.y + 64, r.w - 50, rows=17, size=17)
        ui.text(surf, "Enter — использовать, Tab/Esc — закрыть", (r.x + 20, r.bottom - 28), 14, GREY)


# ============================================================ титул / пауза / конец
CONTROLS = [
    "ПЕШКОМ: WASD — идти, Shift — бежать, E — действие, F — сесть в машину,",
    "        Tab — инвентарь, M — карта, Esc — пауза.",
    "ЗА РУЛЁМ: W — газ, S — тормоз, A/D — руль, Пробел — сцепление (держать),",
    "        Shift / Ctrl — передача вверх/вниз (или 1-4, R — задняя, N — нейтраль),",
    "        I (держать) — стартер / заглушить, C — подсос, L — фары, H — гудок,",
    "        F — выйти, E — действие (заправка, TÜV, доставка).",
    "У машины: E — открыть капот / работа с машиной (снять/поставить детали, жидкости, сварка).",
    "",
    "СОВЕТЫ: холодный двигатель заводится только с подсосом (C). Трогайтесь с 1-й передачи.",
    "Если остановились на передаче — выжмите сцепление, иначе заглохнете.",
    "Свечи, аккумулятор и масло — первое, что нужно машине. Зарядка АКБ — только в гараже.",
    "Чтобы ездить легально: TÜV (техосмотр) → Zulassungsstelle в Rathaus (номера).",
    "Магазины закрыты в воскресенье и по вечерам (Ladenschlussgesetz!). Тankstelle — 24 ч.",
]

INTRO = [
    "Октябрь 1998 года. Нижняя Саксония, городок Kleinbruck.",
    "Полгода назад вы переехали в Германию. У вас есть однокомнатная квартира на Lindenstraße 7, "
    "немного марок и наследство от дяди Вити — ВАЗ 2102 «Жигули» 1979 года.",
    "Машина шесть лет простояла в гараже за домом. Пороги сгнили, арки в дырах, "
    "аккумулятор мёртв, резина спущена, а масло похоже на гуталин.",
    "Задача: оживить «двойку», пройти TÜV, поставить на учёт — и не умереть с голоду, "
    "пока копишь на детали. Работа есть на складе (Lager) и в пиццерии (доставка).",
    "",
    "Квартира ваша собственная — платить за жильё не нужно. На старте у вас 3000 DM.",
]


class TitleScene(Scene):
    def __init__(self, game):
        super().__init__(game)
        self.menu = ui.ListMenu()
        self.refresh()

    def refresh(self):
        has_save = os.path.exists(SAVE_FILE)
        self.menu.set_items([
            ("Новая игра", "new", True),
            ("Продолжить", "load", has_save),
            ("Управление", "help", True),
            ("Выход", "quit", True),
        ])

    def handle(self, ev):
        sel = self.menu.handle(ev)
        g = self.game
        if sel == "new":
            g.new_state()
            from scene_apartment import ApartmentScene
            from scene_street import StreetScene
            g.replace(StreetScene(g))
            g.push(ApartmentScene(g))
            g.push(DialogScene(g, "Добро пожаловать в Kleinbruck", INTRO, width=820))
        elif sel == "load":
            if g.load():
                from scene_street import StreetScene
                g.replace(StreetScene(g))
        elif sel == "help":
            g.push(DialogScene(g, "Управление", CONTROLS, width=1000))
        elif sel == "quit":
            g.running = False

    def draw(self, surf):
        surf.fill((18, 20, 26))
        # фон: машина сбоку
        pygame.draw.rect(surf, (48, 48, 50), (0, 520, WIDTH, 200))
        self.game.car.draw_side(surf, 560, 560, 150)
        ui.text(surf, "MEIN GARAGEN-SOMMER", (60, 60), 54, (230, 200, 90), bold=True)
        ui.text(surf, "ВАЗ 2102 · Германия · 1998", (64, 128), 26, WHITE)
        ui.text(surf, "аналог My Winter Car — ржавая «двойка», квартира, работа, TÜV", (64, 164), 17, GREY)
        self.menu.draw(surf, 70, 240, 360, size=24)


class PauseScene(Scene):
    overlay = True

    def __init__(self, game):
        super().__init__(game)
        self.menu = ui.ListMenu([
            ("Продолжить", "back", True),
            ("Сохранить игру", "save", True),
            ("Загрузить игру", "load", os.path.exists(SAVE_FILE)),
            ("Управление", "help", True),
            ("Выйти в главное меню", "title", True),
        ], title="Пауза")

    def handle(self, ev):
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            self.game.pop()
            return
        sel = self.menu.handle(ev)
        g = self.game
        if sel == "back":
            g.pop()
        elif sel == "save":
            g.save()
            g.pop()
        elif sel == "load":
            if g.load():
                from scene_street import StreetScene
                g.replace(StreetScene(g))
        elif sel == "help":
            g.push(DialogScene(g, "Управление", CONTROLS, width=1000))
        elif sel == "title":
            g.sound.silence()
            g.replace(TitleScene(g))

    def draw(self, surf):
        dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 150))
        surf.blit(dim, (0, 0))
        ui.panel(surf, (WIDTH // 2 - 200, 180, 400, 320), 240)
        self.menu.draw(surf, WIDTH // 2 - 170, 200, 340, size=22)


class GameOverScene(Scene):
    is_game_over = True

    def __init__(self, game, reason):
        super().__init__(game)
        self.reason = reason

    def handle(self, ev):
        if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_RETURN, pygame.K_ESCAPE):
            self.game.new_state()
            self.game.replace(TitleScene(self.game))

    def draw(self, surf):
        surf.fill((12, 8, 8))
        ui.text(surf, "ИГРА ОКОНЧЕНА", (WIDTH // 2, 200), 48, RED, bold=True, center=True)
        y = 290
        for line in self.reason.split("\n"):
            ui.text(surf, line, (WIDTH // 2, y), 22, WHITE, center=True)
            y += 34
        ui.text(surf, "Enter — в главное меню", (WIDTH // 2, 560), 18, GREY, center=True)
