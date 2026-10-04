"""Простые элементы интерфейса: текст, панели, полоски, меню, уведомления."""
import pygame
from config import font, WHITE, GREY, YELLOW, PANEL, RED, GREEN, ORANGE, WIDTH, HEIGHT
import fonts

_fb_fonts = {}


def render(s, size, color, bold=False):
    """Строка в картинку; символы, которых нет в основном шрифте (₽, ⚠...), — запасным шрифтом."""
    parts = fonts.runs(s)
    if len(parts) == 1 and parts[0][1] is None:
        return font(size, bold).render(s, True, color)
    imgs = []
    for txt, fp in parts:
        if fp is None:
            f = font(size, bold)
        else:
            f = _fb_fonts.get((fp, size))
            if f is None:
                f = _fb_fonts[(fp, size)] = pygame.font.Font(fp, size)
        imgs.append(f.render(txt, True, color))
    w, h = sum(i.get_width() for i in imgs), max(i.get_height() for i in imgs)
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    x = 0
    for i in imgs:
        out.blit(i, (x, (h - i.get_height()) // 2))
        x += i.get_width()
    return out


def text(surf, s, pos, size=18, color=WHITE, bold=False, center=False, right=False, shadow=True):
    img = render(str(s), size, color, bold)
    r = img.get_rect()
    if center:
        r.center = pos
    elif right:
        r.topright = pos
    else:
        r.topleft = pos
    if shadow:
        sh = render(str(s), size, (0, 0, 0), bold)
        surf.blit(sh, (r.x + 1, r.y + 1))
    surf.blit(img, r)
    return r


def wrap(s, size, width):
    f = font(size)
    words = s.split(" ")
    lines, cur = [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if f.size(t)[0] > width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines


def panel(surf, rect, alpha=215, border=(70, 70, 75)):
    r = pygame.Rect(rect)
    s = pygame.Surface(r.size, pygame.SRCALPHA)
    s.fill((*PANEL, alpha))
    surf.blit(s, r.topleft)
    pygame.draw.rect(surf, border, r, 1)
    return r


def bar(surf, x, y, w, h, value, maxv=100, color=None, label=None):
    v = max(0.0, min(1.0, value / maxv))
    if color is None:
        color = GREEN if v > 0.5 else (ORANGE if v > 0.25 else RED)
    pygame.draw.rect(surf, (40, 40, 44), (x, y, w, h))
    pygame.draw.rect(surf, color, (x, y, int(w * v), h))
    pygame.draw.rect(surf, (90, 90, 95), (x, y, w, h), 1)
    if label:
        text(surf, label, (x + 4, y + h // 2 - 8), 13)


def cond_color(c):
    if c >= 70:
        return GREEN
    if c >= 40:
        return YELLOW
    if c >= 15:
        return ORANGE
    return RED


class Notifier:
    """Всплывающие сообщения в левом нижнем углу."""

    def __init__(self):
        self.items = []  # [text, time_left, color]

    def push(self, s, color=WHITE, t=5.0):
        self.items.append([s, t, color])
        self.items = self.items[-7:]

    def update(self, dt):
        for it in self.items:
            it[1] -= dt
        self.items = [i for i in self.items if i[1] > 0]

    def draw(self, surf):
        y = HEIGHT - 40
        for s, t, c in reversed(self.items):
            a = min(1.0, t)
            col = tuple(int(ch * a) for ch in c)
            text(surf, s, (16, y), 17, col)
            y -= 24


class ListMenu:
    """Вертикальное меню со стрелками/WS и Enter."""

    def __init__(self, items=None, title=""):
        self.items = items or []  # список (label, payload, enabled)
        self.index = 0
        self.title = title
        self.scroll = 0

    def set_items(self, items):
        self.items = items
        if self.index >= len(items):
            self.index = max(0, len(items) - 1)

    def handle(self, ev):
        """Возвращает payload выбранного пункта при Enter, иначе None."""
        if ev.type != pygame.KEYDOWN or not self.items:
            return None
        if ev.key in (pygame.K_UP, pygame.K_w):
            self.index = (self.index - 1) % len(self.items)
        elif ev.key in (pygame.K_DOWN, pygame.K_s):
            self.index = (self.index + 1) % len(self.items)
        elif ev.key in (pygame.K_RETURN, pygame.K_e, pygame.K_SPACE):
            it = self.items[self.index]
            if len(it) < 3 or it[2]:
                return it[1]
        return None

    def current(self):
        if not self.items:
            return None
        return self.items[self.index][1]

    def draw(self, surf, x, y, w, rows=14, size=17):
        if self.title:
            text(surf, self.title, (x, y), 22, YELLOW, bold=True)
            y += 34
        if self.index < self.scroll:
            self.scroll = self.index
        if self.index >= self.scroll + rows:
            self.scroll = self.index - rows + 1
        vis = self.items[self.scroll:self.scroll + rows]
        for i, it in enumerate(vis):
            idx = i + self.scroll
            enabled = len(it) < 3 or it[2]
            sel = idx == self.index
            if sel:
                pygame.draw.rect(surf, (60, 60, 30), (x - 6, y - 2, w, size + 8))
            col = (YELLOW if sel else WHITE) if enabled else GREY
            label = it[0]
            if isinstance(label, (list, tuple)):
                # (левая часть, правая часть)
                text(surf, label[0], (x, y), size, col)
                text(surf, label[1], (x + w - 16, y), size, col, right=True)
            else:
                text(surf, label, (x, y), size, col)
            y += size + 10
        if len(self.items) > rows:
            text(surf, f"{self.index + 1}/{len(self.items)}", (x + w - 16, y), 13, GREY, right=True)
