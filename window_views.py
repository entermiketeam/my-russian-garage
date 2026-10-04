"""Настоящий вид из окон квартиры (2-й этаж дома Lindenstraße 7).

Как устроено (без копий мира):
  * интерьер квартиры стоит в 3D вне карты (apartment3d.AX/AZ), а город, машины и трафик — на своих местах;
  * квартира «вписана» в дом: северная стена — северный фасад (улица), восточная — восточный, южная — южный
    (балконы), пол — на высоте второго этажа (3 м);
  * для каждой стороны дома есть камера в том же мире: она стоит там, где были бы ваши глаза, если бы квартира
    была внутри дома, и смотрит туда же, куда вы. Объектив — тот же, что у основной камеры;
  * стекло окна показывает кадр этой камеры в экранных координатах (проективная текстура от основной камеры),
    поэтому вид меняется правильно при любом положении и повороте головы — это именно окно, а не картинка;
  * стену дома перед камерой отрезает плоскость отсечения по фасаду;
  * камера рисует, только когда её окно в кадре, в уменьшенное разрешение.
"""
import math
import random

import numpy as np
from PIL import Image
from panda3d.core import (Camera, NodePath, PlaneNode, Plane, Vec3, Point3, ClipPlaneAttrib, RenderState,
                          TextureStage, TexGenAttrib, Texture, TransparencyAttrib)
from ursina import Entity, color, camera

from world import BUILDINGS
from i18n import T

FLOOR_H = 3.0            # пол второго этажа (1. OG)
import graphics  # noqa: E402

RES = graphics.get("window_res")   # разрешение вида из окна относительно экрана (на «Высоком» 0.8)
CLIP_OUT = 0.25          # насколько за фасадом начинается «улица» (подоконные отливы, декор окон — отрезаны)


def _sheen_tex():
    """Блик на стекле: мягкая диагональная полоса."""
    w, h = 256, 256
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    d = (x * 0.8 + y) / (w * 1.8)
    a = np.exp(-((d - 0.35) / 0.07) ** 2) * 0.9 + np.exp(-((d - 0.55) / 0.03) ** 2) * 0.5
    a += 0.12 * (1 - y / h)                       # сверху стекло отражает светлее (небо / потолок)
    img = np.zeros((h, w, 4), np.uint8)
    img[..., :3] = 255
    img[..., 3] = np.clip(a * 255, 0, 255).astype(np.uint8)
    return _ptex(img)


def _ptex(img):
    from ursina import Texture as UTex
    t = UTex(Image.fromarray(img, "RGBA"))
    t.filtering = "mipmap"
    return t


def _precip_tex(kind):
    rng = random.Random(7 if kind == "rain" else 11)
    w, h = 128, 128
    img = np.zeros((h, w, 4), np.uint8)
    img[..., :3] = 235
    for _ in range(70 if kind == "rain" else 110):
        x, y = rng.randrange(w), rng.randrange(h)
        if kind == "rain":                         # капли и стекающие дорожки
            L = rng.randint(4, 16)
            for k in range(L):
                img[(y + k) % h, x, 3] = max(img[(y + k) % h, x, 3], 150 - k * 6)
        else:                                      # хлопья
            r = rng.choice((1, 1, 2))
            img[max(0, y - r):y + r, max(0, x - r):x + r, 3] = 220
    return _ptex(img)


class WindowViews:
    def __init__(self, app, apt):
        self.app = app
        self.apt = apt
        self.ok = False
        self.groups = []
        self.t = 0.0
        if not graphics.get("window_views"):       # низкая графика: стёкла цвета неба вместо настоящего вида
            return
        try:
            self._build()
            self.ok = True
        except Exception as ex:                      # нет поддержки off-screen буферов — остаются цветные стёкла
            print(T("Вид из окон недоступен:"), ex)

    # ------------------------------------------------------------------ сборка
    def _build(self):
        from apartment3d import AX, AZ, W, H
        bx0, by0, bw, bh = BUILDINGS["apartment"][:4]
        east = bx0 + bw
        south = by0 + bh
        bx = east - W / 100.0                            # квартира — в северо-восточном углу этажа
        d_n = Vec3(bx - AX, FLOOR_H, -AZ - by0)          # север и восток: северная стена = фасад на улицу
        d_s = Vec3(bx - AX, FLOOR_H, -AZ - (south - H / 100.0))    # юг: южная стена = фасад с балконами
        render = self.app.render
        wins = self.apt.windows
        spec = [("n", d_n, Plane(Vec3(0, 0, 1), Point3(0, 0, -(by0 - CLIP_OUT))), wins[0:2]),
                ("s", d_s, Plane(Vec3(0, 0, -1), Point3(0, 0, -(south + CLIP_OUT))), wins[2:3]),
                ("e", d_n, Plane(Vec3(1, 0, 0), Point3(east + CLIP_OUT, 0, 0)), wins[3:4])]
        sx = max(64, int(self.app.win.getXSize() * RES))
        sy = max(36, int(self.app.win.getYSize() * RES))
        sheen = _sheen_tex()
        self.rain_tex, self.snow_tex = _precip_tex("rain"), _precip_tex("snow")
        for name, d, plane, ents in spec:
            buf = self.app.win.makeTextureBuffer("aptview_" + name, sx, sy)
            if buf is None:
                raise RuntimeError(T("makeTextureBuffer вернул None"))
            buf.setSort(-30)
            buf.setClearColorActive(True)
            buf.setClearColor((0.55, 0.65, 0.8, 1))
            tex = buf.getTexture()
            tex.setWrapU(Texture.WMClamp)
            tex.setWrapV(Texture.WMClamp)
            cam = Camera("aptcam_" + name)
            cam.setLens(self._lens())                    # копия объектива основной камеры (см. _sync_lens)
            cnp = render.attachNewNode(cam)
            pn = render.attachNewNode(PlaneNode("aptclip_" + name, plane))
            cam.setInitialState(RenderState.make(ClipPlaneAttrib.make().addOnPlane(pn)))
            dr = buf.makeDisplayRegion()
            dr.setCamera(cnp)
            ts = TextureStage("aptview_" + name)
            ts.setMode(TextureStage.MModulate)
            glass = []
            for e in ents:
                e.position = e.position + e.back * 0.012   # стекло — перед рамой (иначе грани в одной плоскости)
                e.color = color.rgb(238, 242, 246)       # стекло чуть холодит цвет
                e.setTexture(ts, tex)
                e.setTexGen(ts, TexGenAttrib.MWorldPosition)
                e.setTexProjector(ts, render, self.app.cam)
                e.setLightOff()
                # блик и осадки на стекле — тонкие слои в комнату от стекла
                fwd = e.back * 0.006
                sh = Entity(model="quad", parent=e.parent, position=e.position + fwd, rotation=e.rotation,
                            scale=e.scale, texture=sheen, color=color.rgba(255, 255, 255, 40))
                from city3d import additive
                additive(sh)
                pr = Entity(model="quad", parent=e.parent, position=e.position + fwd * 0.5, rotation=e.rotation,
                            scale=e.scale, texture=self.rain_tex, color=color.rgba(220, 225, 235, 0))
                pr.setTransparency(TransparencyAttrib.MAlpha)
                pr.setDepthWrite(False)
                pr.setLightOff()
                pr.texture_scale = (e.scale_x / 0.9, e.scale_y / 0.9)
                glass.append((e, sh, pr))
            self.groups.append({"name": name, "d": d, "buf": buf, "cam": cnp, "glass": glass, "active": True})
        self.set_active(False)

    def _lens(self):
        if getattr(self, "lens", None) is None:
            self.lens = camera.lens.makeCopy()
        return self.lens

    def _sync_lens(self):
        """Тот же угол и пропорции, что у основной камеры, но своя дальняя граница: основная камера в квартире
        рисует только квартиру (город за стенами ей не нужен), а камеры окон — улицу до горизонта."""
        from config import VIEW_DIST
        main_lens = camera.lens
        self.lens.setFilmSize(main_lens.getFilmSize())
        self.lens.setFov(main_lens.getFov())
        self.lens.setNearFar(main_lens.getNear(), VIEW_DIST + 60)

    # ------------------------------------------------------------------ работа
    def set_active(self, on):
        for gr in self.groups:
            want = on and gr.get("in_view", True)
            if gr["active"] != want:
                gr["active"] = want
                gr["buf"].setActive(want)
        self._on = on

    def _in_view(self, gr):
        cam = self.app.cam
        lens_node = cam.node()
        for e, _, _ in gr["glass"]:
            for dx, dy in ((0, 0), (-0.5, -0.5), (0.5, -0.5), (-0.5, 0.5), (0.5, 0.5)):
                p = cam.getRelativePoint(e, Point3(dx, dy, 0))
                if lens_node.isInView(p):
                    return True
        return False

    def update(self, dt, inside, sky, darkness, weather):
        """Каждый кадр, пока игрок в квартире: камеры — вслед за глазами, рисуют только видимые окна."""
        if not self.ok:
            return
        if not inside:
            if self._on:
                self.set_active(False)
            return
        self.t += dt
        self._sync_lens()
        cam = self.app.cam
        pos, quat = cam.getPos(self.app.render), cam.getQuat(self.app.render)
        clear = (sky[0] / 255, sky[1] / 255, sky[2] / 255, 1)
        for gr in self.groups:
            gr["in_view"] = self._in_view(gr)
            gr["cam"].setPos(self.app.render, pos + gr["d"])
            gr["cam"].setQuat(self.app.render, quat)
            gr["buf"].setClearColor(clear)
        self.set_active(True)
        # блики: днём еле заметные, ночью стекло сильнее отражает комнату с лампами
        sheen_a = int(22 + 26 * darkness)
        prec = weather if weather in ("rain", "sleet", "snow") else None
        tex = self.snow_tex if prec == "snow" else self.rain_tex
        for gr in self.groups:
            for e, sh, pr in gr["glass"]:
                sh.color = color.rgba(255, 255, 255, sheen_a)
                pr.enabled = prec is not None
                if prec:
                    if pr.texture is not tex:
                        pr.texture = tex
                    speed = 0.08 if prec == "snow" else 0.35
                    drift = math.sin(self.t * 0.4) * 0.05 if prec == "snow" else 0.0
                    pr.texture_offset = (drift, (self.t * speed) % 1.0)
                    pr.color = color.rgba(230, 235, 245, 200 if prec == "snow" else 150)
