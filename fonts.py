"""Шрифты интерфейса с подстановкой недостающих символов.

Основной шрифт — Arial (как было изначально): в нём есть кириллица, стрелки ← → ↑ ↓, ▲, «…».
Но в нём нет знака рубля ₽ и некоторых значков (⚠ ✓ ✗ ↳). Ни Panda3D, ни pygame не умеют сами брать символ
из другого шрифта, поэтому:
  * 3D (Ursina/Panda3D): такие символы оборачиваются в свойства текста Panda3D «\\1fbN\\1символ\\2» —
    этот кусочек рисуется запасным шрифтом, остальной текст — основным;
  * 2D (pygame): строка рисуется кусками разными шрифтами (ui.text).
"""
import os

import pygame

MAIN_FONTS = (
    "/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf",            # macOS
    "C:/Windows/Fonts/arial.ttf",                                                            # Windows
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",                                       # Linux
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
)
FALLBACK_FONTS = (
    "/System/Library/Fonts/Supplemental/PTSans.ttc", "/System/Library/Fonts/HelveticaNeue.ttc",
    "/System/Library/Fonts/SFNS.ttf", "/System/Library/Fonts/Apple Symbols.ttf", "/System/Library/Fonts/Menlo.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/seguisym.ttf", "C:/Windows/Fonts/arialuni.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/noto/NotoSansSymbols-Regular.ttf",
)
# символы, которые могут понадобиться из запасного шрифта (остальное есть в любом основном)
SPECIAL = "₽⚠✓✗↳←→↑↓▲•…–—«»·°×≈−∞"

_has = {}


def has_glyph(path, ch):
    key = (path, ch)
    if key not in _has:
        try:
            if not pygame.font.get_init():
                pygame.font.init()
            f = pygame.font.Font(path, 24)
            missing = pygame.image.tostring(f.render("\uffff", True, (255, 255, 255)), "RGB")
            _has[key] = pygame.image.tostring(f.render(ch, True, (255, 255, 255)), "RGB") != missing
        except Exception:
            _has[key] = False
    return _has[key]


_main = []


def main_font_path():
    if not _main:
        existing = [p for p in MAIN_FONTS if os.path.exists(p)]
        _main.append(next((p for p in existing if has_glyph(p, "Ж")), existing[0] if existing else None))
    return _main[0]


_fb = {}


def fallback_map():
    """{символ: путь к шрифту} — для символов, которых нет в основном шрифте."""
    if not _fb:
        main = main_font_path()
        fbs = [p for p in FALLBACK_FONTS if os.path.exists(p)]
        for ch in SPECIAL:
            if main and has_glyph(main, ch):
                continue
            p = next((p for p in fbs if has_glyph(p, ch)), None)
            if p:
                _fb[ch] = p
        _fb.setdefault("", None)          # отметка «уже посчитано»
    return {k: v for k, v in _fb.items() if k}


# ---------------------------------------------------------------------- 3D: Panda3D / Ursina
_wrap_tbl = {}


def install_ursina():
    """Основной шрифт + свойства Panda3D для запасных символов + обёртка текста в Ursina."""
    from ursina import Text
    from panda3d.core import TextProperties, TextPropertiesManager
    from ursina.text import Text as UText
    main = main_font_path()
    if main:
        Text.default_font = main
    fb = fallback_map()
    if not fb:
        return
    from direct.showbase.Loader import Loader
    from panda3d.core import TextNode
    import builtins
    loader = getattr(builtins, "loader", None) or Loader(None)
    mgr = TextPropertiesManager.getGlobalPtr()
    names = {}
    for ch, path in fb.items():
        if path not in names:
            font = loader.loadFont(path)
            font.setPixelsPerUnit(Text.default_resolution)
            tp = TextProperties()
            tp.setFont(font)
            nm = f"mrgfb{len(names)}"
            mgr.setProperties(nm, tp)
            names[path] = (nm, font)
        nm, font = names[path]
        _wrap_tbl[ord(ch)] = f"\1{nm}\1{ch}\2"
        tn = TextNode("mrgfb_measure")
        tn.setFont(font)
        _fb_nodes[ch] = tn
    orig = UText.create_text_section

    def create_text_section(self, text, tag="", x=0, y=0):
        return orig(self, wrap(text), tag, x, y)

    UText.create_text_section = create_text_section
    # текст, ширина и выравнивание — по настоящим символам (а не по служебным меткам Panda3D)
    text_prop = UText.text
    UText.text = property(lambda self: unwrap(text_prop.fget(self)), text_prop.fset)

    def width(self):
        if not hasattr(self, "text"):
            return 0
        tn = TextNode("temp")
        tn.setFont(self._font)
        return max((measure(line, tn) for line in self.text.split("\n")), default=0) * self.scale_x * self.size

    UText.width = property(width)

    def align(self):
        value = self.origin
        main = self.text_nodes[0].node()
        linewidths = [measure(line, main) for line in self.lines]
        for tn in self.text_nodes:
            linenumber = abs(int(tn.getY() / self.size / self.line_height))
            tn.setX(tn.getX() - (linewidths[linenumber] / 2 * self.size * tn.getScale()[0] / self.size))
            tn.setX(tn.getX() - (linewidths[linenumber] / 2 * value[0] * 2 * self.size) * tn.getScale()[0] / self.size)
            halfheight = len(linewidths) * self.line_height / 2
            tn.setY(tn.getY() + (halfheight * self.size))
            tn.setY(tn.getY() - (halfheight * value[1] * 2 * self.size))

    UText.align = align


_fb_nodes = {}
_CTRL = None


def unwrap(s):
    """Убрать служебные метки свойств Panda3D (\\1имя\\1 ... \\2)."""
    global _CTRL
    if "\1" not in s:
        return s
    if _CTRL is None:
        import re
        _CTRL = re.compile("\x01[^\x01]*\x01|\x02")
    return _CTRL.sub("", s)


def measure(s, main_node):
    """Ширина строки в единицах TextNode: обычные символы — основным шрифтом, подставленные — своим."""
    s = unwrap(s)
    if not _fb_nodes or not any(c in _fb_nodes for c in s):
        return main_node.calcWidth(s)
    w, seg = 0.0, ""
    for c in s:
        n = _fb_nodes.get(c)
        if n is None:
            seg += c
            continue
        if seg:
            w += main_node.calcWidth(seg)
            seg = ""
        w += n.calcWidth(c)
    if seg:
        w += main_node.calcWidth(seg)
    return w


def wrap(s):
    """Строка для Panda3D: недостающие символы — запасным шрифтом."""
    return s.translate(_wrap_tbl) if _wrap_tbl else s


# ---------------------------------------------------------------------- 2D: pygame
def runs(s):
    """Разбить строку на куски [(текст, путь_шрифта или None — основной)]."""
    fb = fallback_map()
    if not fb or not any(c in fb for c in s):
        return [(s, None)]
    out, cur, cur_f = [], "", None
    for c in s:
        f = fb.get(c)
        if f != cur_f and cur:
            out.append((cur, cur_f))
            cur = ""
        cur_f = f
        cur += c
    if cur:
        out.append((cur, cur_f))
    return out
