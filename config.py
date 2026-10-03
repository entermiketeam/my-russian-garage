"""Общие настройки игры «Mein Garagen-Sommer: ВАЗ 2102»."""
import pygame

WIDTH, HEIGHT = 1280, 720
FPS = 60
TITLE = "Mein Garagen-Sommer — ВАЗ 2102 в Германии"

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

_font_cache = {}


def font(size, bold=False):
    key = (size, bold)
    if key not in _font_cache:
        f = None
        for name in ("arial", "helvetica", "dejavusans", "liberationsans"):
            path = pygame.font.match_font(name, bold=bold)
            if path:
                f = pygame.font.Font(path, size)
                break
        if f is None:
            f = pygame.font.Font(None, size + 6)
        _font_cache[key] = f
    return _font_cache[key]

# ---------------------------------------------------------------- дальность прорисовки (3D)
# Карта существует целиком, но рисуется и обсчитывается только область вокруг игрока.
# Эти числа можно смело менять: больше — дальше видно, но тяжелее для компьютера.
VIEW_DIST = 320          # м: дальше этого город, снег и вывески выключаются (туман скрывает границу)
CHUNK = 100              # м: размер квадрата, на которые нарезана карта
CAR_VIEW_DIST = 140      # м: ближе этого у машин-находок подробная 3D-модель
SIM_DIST = 450           # м: дальше этого трафик стоит на паузе (игрок его всё равно не видит)
