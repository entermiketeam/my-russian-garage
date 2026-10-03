"""Общие настройки игры «My Russian Garage»."""
import os

import pygame

WIDTH, HEIGHT = 1280, 720
FPS = 60
TITLE = "My Russian Garage"

# 1 реальная секунда = 1 игровая минута (сутки ≈ 24 минуты)
GAME_MIN_PER_SEC = 1.0

# Масштаб мира: пикселей на метр
PPM = 11

SAVE_FILE = "savegame.json"

# Цвета
BLACK = (0, 0, 0)
WHITE = (240, 240, 235)
GREY = (120, 120, 120)
DARK = (25, 25, 28)
PANEL = (20, 22, 26)
YELLOW = (240, 200, 60)
RED = (210, 60, 50)
GREEN = (90, 190, 90)
ORANGE = (230, 140, 40)
BLUE = (80, 140, 220)
RUST = (130, 62, 28)
RUST_DARK = (85, 38, 18)

GRASS = (74, 110, 58)
ROAD = (58, 58, 62)
ROAD_LINE = (220, 220, 210)
SIDEWALK = (150, 148, 140)

CURRENCY = "₽"           # валюта игры — рубли; все суммы в коде и сохранениях — просто числа в рублях

# Шрифты интерфейса по порядку: берётся первый, в котором есть и кириллица, и знак рубля
# (в старых Arial знака ₽ нет — вместо него рисовался бы пустой квадрат).
UI_FONTS = (
    "/System/Library/Fonts/Supplemental/PTSans.ttc",        # macOS: PT Sans (ParaType)
    "/System/Library/Fonts/HelveticaNeue.ttc",              # macOS
    "C:/Windows/Fonts/arial.ttf",                           # Windows (Arial с ₽ — с обновлений 2014 г.)
    "C:/Windows/Fonts/segoeui.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",      # Linux
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",         # запасные: без ₽, но с кириллицей
    "/Library/Fonts/Arial.ttf",
)


def has_glyphs(path, chars=CURRENCY + "Жж"):
    """Есть ли в шрифте настоящие глифы (а не «пустой квадрат» .notdef)."""
    try:
        if not pygame.font.get_init():
            pygame.font.init()
        f = pygame.font.Font(path, 24)
        missing = pygame.image.tostring(f.render("\uffff", True, (255, 255, 255)), "RGB")
        return all(pygame.image.tostring(f.render(ch, True, (255, 255, 255)), "RGB") != missing for ch in chars)
    except Exception:
        return False


_ui_font = []


def ui_font_path():
    """Путь к шрифту интерфейса (для 3D — Text.default_font, для 2D — pygame)."""
    if not _ui_font:
        existing = [p for p in UI_FONTS if os.path.exists(p)]
        _ui_font.append(next((p for p in existing if has_glyphs(p)), existing[0] if existing else None))
    return _ui_font[0]


_font_cache = {}


def font(size, bold=False):
    key = (size, bold)
    if key not in _font_cache:
        path = ui_font_path()
        f = pygame.font.Font(path, size) if path else pygame.font.Font(None, size + 6)
        if bold:
            f.set_bold(True)
        _font_cache[key] = f
    return _font_cache[key]

# ---------------------------------------------------------------- дальность прорисовки (3D)
# Карта существует целиком, но рисуется и обсчитывается только область вокруг игрока.
# Эти числа можно смело менять: больше — дальше видно, но тяжелее для компьютера.
VIEW_DIST = 320          # м: дальше этого город, снег и вывески выключаются (туман скрывает границу)
CHUNK = 100              # м: размер квадрата, на которые нарезана карта
CAR_VIEW_DIST = 140      # м: ближе этого у машин-находок подробная 3D-модель
SIM_DIST = 450           # м: дальше этого трафик стоит на паузе (игрок его всё равно не видит)
