"""Уровни графики: «Сверхнизкий», «Низкий», «Средний», «Высокий».

Уровень выбирается в главном меню (кнопка «Графика»), хранится в settings.json и применяется при запуске игры
(модели, текстуры и сетки строятся один раз — поэтому после смены уровня игра перезапускается сама).
Для проверки без меню: переменная окружения MRG_GRAPHICS=ultra_low|low|medium|high.

Физика, управление, ремонт и все механики от уровня НЕ зависят — меняется только то, что рисуется:
дальность, детализация моделей вдали, разрешение текстур, количество частиц и «дорогие» эффекты
(зеркала с отражением, настоящий вид из окон).

Как добавить параметр: впишите его во все четыре пресета ниже и читайте как graphics.get("имя").
"""
import json
import os

from i18n import T

LEVELS = ("ultra_low", "low", "medium", "high")
DEFAULT = "medium"

# Что значат поля:
#   view_dist        дальность прорисовки города, снега, вывесок (м); дальше — туман
#   car_view_dist    до какой дальности у машин полная модель (м)
#   car_proxy_dist   дальше полной модели — простой силуэт машины (м, 0 — не рисовать)
#   sim_dist         дальше этого трафик стоит на паузе (игрок его не видит)
#   traffic_near     машины трафика ближе этого — полная модель, дальше — лёгкая коробка (м)
#   traffic_far_k    лёгкие машины трафика видны до view_dist * k
#   ped_dist         пешеходы видны ближе этого (м)
#   mirrors          настоящие отражения в зеркалах заднего вида; mirror_res — множитель разрешения
#   window_views     настоящий вид из окон квартиры; window_res — доля разрешения экрана
#   tex_scale        множитель разрешения процедурных текстур (борта машин, снег, шум земли)
#   seg_k            множитель числа сегментов у круглых деталей (колёса, деревья, фонари)
#   snow_step        шаг (м) снежных валов вдоль дорог и сугробов у стен (больше — проще)
#   snow_extras      снег на деревьях, слякоть с колеями
#   precip           капель/снежинок на экране
#   smoke            частиц выхлопа на машину
#   glow             ореолы фонарей и пятна света фар на асфальте
#   window_size      размер окна (меньше — легче видеокарте)
PRESETS = {
    "ultra_low": dict(view_dist=150, car_view_dist=40, car_proxy_dist=120, sim_dist=260, traffic_near=0,
                      traffic_far_k=0.9, ped_dist=45, mirrors=False, mirror_res=0.5, window_views=False,
                      window_res=0.4, tex_scale=0.25, seg_k=0.5, snow_step=4.0, snow_extras=False, precip=25,
                      smoke=6, glow=False, window_size=(960, 540)),
    "low": dict(view_dist=210, car_view_dist=60, car_proxy_dist=170, sim_dist=330, traffic_near=40,
                traffic_far_k=1.0, ped_dist=65, mirrors=True, mirror_res=0.6, window_views=False, window_res=0.5,
                tex_scale=0.5, seg_k=0.65, snow_step=3.0, snow_extras=False, precip=50, smoke=12, glow=True,
                window_size=(1280, 720)),
    "medium": dict(view_dist=270, car_view_dist=95, car_proxy_dist=230, sim_dist=400, traffic_near=65,
                   traffic_far_k=1.2, ped_dist=90, mirrors=True, mirror_res=1.0, window_views=True, window_res=0.6,
                   tex_scale=0.75, seg_k=0.8, snow_step=2.4, snow_extras=True, precip=90, smoke=24, glow=True,
                   window_size=(1280, 720)),
    "high": dict(view_dist=320, car_view_dist=140, car_proxy_dist=0, sim_dist=450, traffic_near=95,
                 traffic_far_k=1.3, ped_dist=110, mirrors=True, mirror_res=1.0, window_views=True, window_res=0.8,
                 tex_scale=1.0, seg_k=1.0, snow_step=1.8, snow_extras=True, precip=140, smoke=48, glow=True,
                 window_size=(1280, 720)),
}

ROOT = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(ROOT, "settings.json")


def _read():
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _pick():
    lvl = os.environ.get("MRG_GRAPHICS") or _read().get("graphics", DEFAULT)
    return lvl if lvl in PRESETS else DEFAULT


LEVEL = _pick()                    # уровень этого запуска (меняется только перезапуском)
_P = PRESETS[LEVEL]


def get(name):
    return _P[name]


def seg(n, minimum=4):
    """Число сегментов круглой детали с учётом уровня."""
    return max(minimum, int(round(n * _P["seg_k"])))


def tex(n, minimum=16):
    """Размер процедурной текстуры с учётом уровня (степень двойки не обязательна)."""
    return max(minimum, int(n * _P["tex_scale"]))


def names():
    return {"ultra_low": T("Сверхнизкая"), "low": T("Низкая"), "medium": T("Средняя"), "high": T("Высокая")}


def descriptions():
    return {"ultra_low": T("для очень слабых компьютеров: простые модели, маленькие текстуры, близкая дальность"),
            "low": T("для слабых ноутбуков: упрощённые модели вдали, без вида из окон"),
            "medium": T("баланс: полная детализация вблизи, упрощение вдали"),
            "high": T("максимальная детализация и дальность (как было раньше)")}


def saved_level():
    lvl = _read().get("graphics", DEFAULT)
    return lvl if lvl in PRESETS else DEFAULT


def save_level(lvl):
    d = _read()
    d["graphics"] = lvl
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
    except OSError as e:
        print(f"[graphics] не удалось сохранить настройки: {e}")
