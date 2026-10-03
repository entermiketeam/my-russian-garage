"""Календарь и климат: 12 настоящих месяцев (Нижняя Саксония, конец 90-х).

Дата игры идёт по реальному календарю (state.date()): 31 декабря → 1 января следующего года и т. д.
От месяца зависят: температура, рассвет/закат, вероятности погоды (снег/дождь/ясно), снежный покров
на земле и дорогах, слякоть и зелень деревьев. Всё берётся отсюда — чтобы привязать к сезону что-то
новое, достаточно прочитать climate(month) или snow_level().
"""

MONTHS_RU = ["январь", "февраль", "март", "апрель", "май", "июнь",
             "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"]
MONTHS_GEN = ["января", "февраля", "марта", "апреля", "мая", "июня",
              "июля", "августа", "сентября", "октября", "ноября", "декабря"]
MONTHS_DE = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",          # (раньше — немецкие названия)
             "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
SEASON = {12: "winter", 1: "winter", 2: "winter", 3: "spring", 4: "spring", 5: "spring",
          6: "summer", 7: "summer", 8: "summer", 9: "autumn", 10: "autumn", 11: "autumn"}
SEASON_RU = {"winter": "зима", "spring": "весна", "summer": "лето", "autumn": "осень"}

# месяц: средняя t, суточный размах, рассвет, закат (ч, местное время), погода {вид: вес},
#        снег на земле (0..1), листва (0 голые ветки .. 1 полная)
CLIMATE = {
    1: dict(t=0.5, amp=4.0, rise=8.5, set=16.6, w={"clear": 0.22, "cloudy": 0.36, "snow": 0.27, "sleet": 0.15},
            snow=1.0, leaves=0.0),
    2: dict(t=1.0, amp=5.0, rise=7.8, set=17.4, w={"clear": 0.25, "cloudy": 0.35, "snow": 0.24, "sleet": 0.16},
            snow=0.9, leaves=0.0),
    3: dict(t=4.5, amp=7.0, rise=6.8, set=18.3, w={"clear": 0.3, "cloudy": 0.35, "rain": 0.2, "sleet": 0.1, "snow": 0.05},
            snow=0.3, leaves=0.1),
    4: dict(t=8.5, amp=9.0, rise=6.6, set=20.3, w={"clear": 0.38, "cloudy": 0.34, "rain": 0.26, "sleet": 0.02},
            snow=0.0, leaves=0.5),
    5: dict(t=13.0, amp=10.0, rise=5.5, set=21.2, w={"clear": 0.45, "cloudy": 0.3, "rain": 0.25},
            snow=0.0, leaves=1.0),
    6: dict(t=16.0, amp=10.0, rise=5.0, set=21.8, w={"clear": 0.45, "cloudy": 0.28, "rain": 0.27},
            snow=0.0, leaves=1.0),
    7: dict(t=17.8, amp=10.0, rise=5.3, set=21.7, w={"clear": 0.48, "cloudy": 0.26, "rain": 0.26},
            snow=0.0, leaves=1.0),
    8: dict(t=17.5, amp=10.0, rise=6.1, set=20.9, w={"clear": 0.48, "cloudy": 0.28, "rain": 0.24},
            snow=0.0, leaves=1.0),
    9: dict(t=14.0, amp=8.0, rise=7.0, set=19.7, w={"clear": 0.38, "cloudy": 0.34, "rain": 0.28},
            snow=0.0, leaves=0.85),
    10: dict(t=9.5, amp=6.0, rise=7.9, set=18.5, w={"clear": 0.28, "cloudy": 0.4, "rain": 0.32},
             snow=0.0, leaves=0.45),
    11: dict(t=5.0, amp=4.0, rise=7.8, set=16.6, w={"clear": 0.2, "cloudy": 0.42, "rain": 0.25, "sleet": 0.1, "snow": 0.03},
             snow=0.15, leaves=0.05),
    12: dict(t=1.5, amp=3.0, rise=8.4, set=16.1, w={"clear": 0.25, "cloudy": 0.35, "snow": 0.28, "sleet": 0.12},
             snow=1.0, leaves=0.0),
}


def climate(month):
    return CLIMATE[int(month)]


def month_name(month):
    return MONTHS_RU[int(month) - 1]


def season(month):
    return SEASON[int(month)]


def pick_weather(month, rng):
    w = climate(month)["w"]
    return rng.choices(list(w), list(w.values()))[0]


def valid_weather(month, weather):
    """Погода, возможная в этом месяце (снегопад в июле превращается в дождь и т. п.)."""
    w = climate(month)["w"]
    if weather in w:
        return weather
    if weather in ("snow", "sleet"):
        return "rain" if "rain" in w else "cloudy"
    if weather == "rain":
        return "sleet" if "sleet" in w else "cloudy"
    return "cloudy"


def temp(month, hour, day_frac=0.5):
    """Температура воздуха: плавно между соседними месяцами (день месяца day_frac 0..1)."""
    c = climate(month)
    nb = climate(month % 12 + 1) if day_frac >= 0.5 else climate((month - 2) % 12 + 1)
    k = abs(day_frac - 0.5)                         # к краю месяца — ближе к соседнему
    base = c["t"] * (1 - k) + nb["t"] * k
    amp = c["amp"] * (1 - k) + nb["amp"] * k
    import math
    return base + amp / 2 * math.sin(2 * math.pi * (hour - 9) / 24)


def darkness(month, hour):
    """0 — день, 0.8 — ночь; сумерки около часа вокруг рассвета и заката."""
    c = climate(month)
    rise, st = c["rise"], c["set"]
    if rise + 0.2 <= hour <= st - 0.2:
        return 0.0
    if rise - 0.8 < hour < rise + 0.2:
        return (rise + 0.2 - hour) * 0.8
    if st - 0.2 < hour < st + 0.8:
        return (hour - st + 0.2) * 0.8
    return 0.8
