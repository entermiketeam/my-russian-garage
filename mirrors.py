"""Рабочие зеркала заднего вида у машины, в которой сидит игрок.

У каждой машины два зеркала: салонное (над лобовым стеклом) и наружное водительское. Их стекло — плоскость
в car3d_extra (Extras._build_mirror_glass). Здесь — две камеры в том же мире: они стоят у зеркал, смотрят
назад и рисуют в небольшие текстуры; текстура на стекле отражена по горизонтали, как в настоящем зеркале.
Работают, только пока игрок в салоне (вид из кабины) — иначе выключены и ничего не стоят.
"""
from panda3d.core import Camera, PerspectiveLens, Texture, Vec3
from i18n import T

SPEC = {"inner": dict(size=(256, 80), fov=(34, 11), yaw=180.0),       # широкое узкое салонное
        "side": dict(size=(160, 108), fov=(26, 18), yaw=184.0),        # левое: назад и чуть наружу от кузова
        "side_r": dict(size=(160, 108), fov=(22, 15), yaw=184.0)}      # правое (дальше от глаз — поле уже)
MIRROR_FAR = 120.0         # дальше в зеркале всё равно не разглядеть — не рисуем (экономия)


class Mirrors:
    def __init__(self, app):
        self.app = app
        self.ok = False
        self.views = {}
        self.active = None
        try:
            for name, sp in SPEC.items():
                buf = app.win.makeTextureBuffer("mirror_" + name, *sp["size"])
                if buf is None:
                    raise RuntimeError(T("нет внеэкранного буфера"))
                buf.setSort(-25)
                buf.setClearColorActive(True)
                tex = buf.getTexture()
                tex.setWrapU(Texture.WMRepeat)              # u → −u (отражение) остаётся в пределах кадра
                tex.setWrapV(Texture.WMClamp)
                lens = PerspectiveLens()
                lens.setFov(*sp["fov"])
                lens.setNearFar(0.05, MIRROR_FAR)
                cam = Camera("mirror_cam_" + name, lens)
                cnp = app.render.attachNewNode(cam)
                dr = buf.makeDisplayRegion()
                dr.setCamera(cnp)
                buf.setActive(False)
                self.views[name] = {"buf": buf, "tex": tex, "cam": cnp, "glass": None}
            self.ok = True
        except Exception as ex:
            print(T("Зеркала без отражения:"), ex)

    def update(self, c3, active, sky=(140, 178, 222)):
        """c3 — Car3D машины игрока (или None); active — игрок сидит в салоне и смотрит из кабины."""
        if not self.ok:
            return
        glass = getattr(c3, "mirror_glass", None) if (c3 is not None and active) else None
        on = bool(glass)
        # за кадр перерисовывается не больше одного зеркала: салонное — через кадр, боковые — каждое 4-й
        # (при 60 FPS это 30 и 15 раз в секунду — глазу хватает, а мир рисуется не 3 лишних раза, а один)
        self._frame = getattr(self, "_frame", 0) + 1
        slot = {"inner": (0, 2), "side": (1, 4), "side_r": (3, 4)}
        for name, v in self.views.items():
            g = glass.get(name) if glass else None
            want = g is not None
            ph, per = slot.get(name, (0, 1))
            live = want and self._frame % per == ph % per
            if v["buf"].isActive() != live:
                v["buf"].setActive(live)
            if not want:
                if v["glass"] is not None:                   # вышли из машины: стекло снова просто стекло
                    try:
                        v["glass"].clearTexture()
                        v["glass"].texture_scale = (1, 1)
                    except Exception:
                        pass
                v["glass"] = None
                continue
            if v["glass"] is not g:                          # новая машина / пересобранная модель
                v["glass"] = g
                v["cam"].reparentTo(g.parent)
                v["cam"].setPos(g.getPos() + Vec3(0, 0, -0.03))          # чуть ближе к водителю, за стеклом
                v["cam"].setHpr(0, 0, 0)
                v["cam"].setH(360 - SPEC[name]["yaw"] if g.x <= 0 else SPEC[name]["yaw"])     # наружу от кузова
                g.setTexture(v["tex"], 1)
                g.texture_scale = (-1, 1)                    # зеркально, как в настоящем зеркале
                g.setLightOff()
            v["buf"].setClearColor((sky[0] / 255, sky[1] / 255, sky[2] / 255, 1))
        self.active = on
