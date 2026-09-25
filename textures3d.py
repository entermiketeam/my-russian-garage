"""Процедурные текстуры (PIL + numpy) и текстуры бортов машины из 2D-рисунка."""
import numpy as np
import pygame
from PIL import Image
from ursina import Texture

_cache = {}


def _tex(img, filtering="mipmap"):
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    t = Texture(img)
    t.filtering = filtering
    return t


def _noise(size, seed, octaves=4):
    rng = np.random.default_rng(seed)
    out = np.zeros((size, size))
    amp = 1.0
    tot = 0.0
    for o in range(octaves):
        n = 2 ** (o + 2)
        small = rng.random((n, n))
        img = Image.fromarray((small * 255).astype(np.uint8)).resize((size, size), Image.BICUBIC)
        out += np.asarray(img, dtype=float) / 255 * amp
        tot += amp
        amp *= 0.5
    out /= tot
    return out


def detail():
    """Серый шум для земли/асфальта/травы (умножается на цвет вершин)."""
    if "detail" not in _cache:
        n = _noise(256, 1)
        fine = np.random.default_rng(2).random((256, 256))
        v = 0.78 + 0.22 * n + 0.08 * (fine - 0.5)
        a = np.clip(v * 255, 0, 255).astype(np.uint8)
        _cache["detail"] = _tex(Image.fromarray(a).convert("RGB"))
    return _cache["detail"]


def glow():
    """Круглое мягкое пятно света (для фонарей и фар на асфальте)."""
    if "glow" not in _cache:
        s = 128
        y, x = np.mgrid[0:s, 0:s]
        d = np.sqrt((x - s / 2 + 0.5) ** 2 + (y - s / 2 + 0.5) ** 2) / (s / 2)
        a = np.clip(1 - d, 0, 1) ** 1.6
        img = np.zeros((s, s, 4), dtype=np.uint8)
        img[..., :3] = 255
        img[..., 3] = (a * 255).astype(np.uint8)
        _cache["glow"] = _tex(Image.fromarray(img, "RGBA"), "bilinear")
    return _cache["glow"]


def beam():
    """Пятно фары: вытянутый конус, яркий у основания."""
    if "beam" not in _cache:
        w, h = 128, 256
        y, x = np.mgrid[0:h, 0:w]
        t = 1 - y / h                   # 0 у дальнего конца, 1 у фары
        spread = 0.15 + 0.85 * (1 - t)
        dx = np.abs((x - w / 2) / (w / 2)) / spread
        a = np.clip(1 - dx, 0, 1) ** 1.3 * np.clip(t * 1.6, 0, 1) ** 0.7
        img = np.zeros((h, w, 4), dtype=np.uint8)
        img[..., :3] = 255
        img[..., 3] = (a * 255).astype(np.uint8)
        _cache["beam"] = _tex(Image.fromarray(img, "RGBA"), "bilinear")
    return _cache["beam"]


def surface_to_texture(surf):
    data = pygame.image.tostring(surf, "RGBA")
    img = Image.frombytes("RGBA", surf.get_size(), data)
    return _tex(img)


SIDE_W, SIDE_H = 512, 256
SIDE_PPM = 115.0          # пикселей на метр в текстуре борта (4.45 м — хватает и на AE86)
SIDE_X0 = 0.15            # метров слева от заднего края кузова


def car_side(car, side):
    """Текстура борта ВАЗ 2102. Правый борт — перед справа, левый — зеркально (перед слева)."""
    surf = pygame.Surface((SIDE_W, SIDE_H), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))
    car.draw_side(surf, SIDE_X0 * SIDE_PPM, SIDE_H - 2, SIDE_PPM, texture=True, side=side)
    if side == "l":
        surf = pygame.transform.flip(surf, True, False)
    return surface_to_texture(surf)


def map_texture(world, buildings, roads, k=0.5):
    """Карта местности для экрана карты."""
    import pygame as pg
    from world import MAP_W, MAP_H
    m = pg.Surface((int(MAP_W * k), int(MAP_H * k)))
    m.fill((60, 90, 50))
    for r in roads:
        col = (230, 200, 90) if r[4] == "autobahn" else ((215, 215, 215) if r[4] == "town" else (175, 175, 175))
        pg.draw.rect(m, col, (r[0] * k, r[1] * k, max(2, r[2] * k), max(2, r[3] * k)))
    for h in world.houses:
        pg.draw.rect(m, (150, 110, 90), (h[0] * k, h[1] * k, h[2] * k, h[3] * k))
    for b in buildings.values():
        pg.draw.rect(m, (80, 140, 220), (b[0] * k, b[1] * k, b[2] * k, b[3] * k))
    return surface_to_texture(m), m.get_size()
