"""Общие настройки игры «My Russian Garage»."""
import os

import pygame

import fonts

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

# Шрифты — в fonts.py: основной Arial, недостающие символы (₽, ⚠, ✓) — запасным шрифтом.


_font_cache = {}


def font(size, bold=False):
    key = (size, bold)
    if key not in _font_cache:
        path = fonts.main_font_path()
        bold_path = path and path.replace("Arial.ttf", "Arial Bold.ttf").replace("arial.ttf", "arialbd.ttf")
        if bold and bold_path and os.path.exists(bold_path):
            path, bold = bold_path, False
        f = pygame.font.Font(path, size) if path else pygame.font.Font(None, size + 6)
        if bold:
            f.set_bold(True)
        _font_cache[key] = f
    return _font_cache[key]

# ---------------------------------------------------------------- дальность прорисовки (3D)
# Карта существует целиком, но рисуется и обсчитывается только область вокруг игрока.
# Эти числа можно смело менять: больше — дальше видно, но тяжелее для компьютера.
# Значения зависят от уровня графики (graphics.py, меню «Графика»); на «Высоком» — 320 / 140 / 450, как раньше.
import graphics as _gfx  # noqa: E402
VIEW_DIST = _gfx.get("view_dist")          # м: дальше этого город, снег и вывески выключаются (туман скрывает границу)
CHUNK = 100                                # м: размер квадрата, на которые нарезана карта
CAR_VIEW_DIST = _gfx.get("car_view_dist")  # м: ближе этого у машин-находок подробная 3D-модель
CAR_PROXY_DIST = _gfx.get("car_proxy_dist")  # м: дальше подробной модели — простой силуэт (0 — нет)
SIM_DIST = _gfx.get("sim_dist")            # м: дальше этого трафик стоит на паузе (игрок его всё равно не видит)
