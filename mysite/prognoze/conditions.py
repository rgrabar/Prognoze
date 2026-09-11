"""Jedan zajednicki rjecnik vremenskih stanja.

Svaki API govori svojim jezikom: Open-Meteo koristi WMO kodove, WeatherAPI
i wttr.in svoje brojeve, MET Norway tekstualne simbole. Ne mozes usrednjiti
broj 3 (WMO: oblacno) i broj 1000 (WeatherAPI: vedro) - zato se sve prvo
prevodi ovdje u `Condition`, pa se tek onda glasa.
"""

from enum import Enum


class Condition(Enum):
    """Kanonsko stanje. Vrijednost = ozbiljnost (za neodluceno glasanje)."""

    CLEAR = 0
    MAINLY_CLEAR = 1
    PARTLY_CLOUDY = 2
    OVERCAST = 3
    FOG = 4
    DRIZZLE = 5
    RAIN = 6
    SLEET = 7
    SNOW = 8
    THUNDER = 9
    THUNDER_HAIL = 10

    @property
    def severity(self):
        return self.value


# Slikice iz static/ za dnevne sate.
CONDITION_ICONS = {
    Condition.CLEAR: "sun.png",
    # Veliko sunce s malim oblakom nasuprot oblaku sa suncem - tako se
    # "pretezno vedro" i "djelomicno oblacno" vise ne cine isto.
    Condition.MAINLY_CLEAR: "sun_small_cloud.png",
    Condition.PARTLY_CLOUDY: "cloud_sun.png",
    Condition.OVERCAST: "cloud.png",
    Condition.FOG: "magla.png",
    Condition.DRIZZLE: "drizzle.png",
    Condition.RAIN: "rain.png",
    Condition.SLEET: "rain_snow.png",
    Condition.SNOW: "pahulja.png",
    Condition.THUNDER: "thunder.png",
    Condition.THUNDER_HAIL: "rain_thunder.png",
}

UNKNOWN_ICON = "neznamovrime.png"

# Nocne inacice - samo za stanja u kojima se vidi sunce. Kisa, snijeg,
# susnjezica, magla, oblak i grmljavina izgledaju isto danju i nocu, pa im
# zamjena ne treba.
NIGHT_ICONS = {
    Condition.CLEAR: "moon.png",
    Condition.MAINLY_CLEAR: "cloud_moon.png",
    Condition.PARTLY_CLOUDY: "cloud_moon.png",
}

CONDITION_LABELS = {
    Condition.CLEAR: "vedro",
    Condition.MAINLY_CLEAR: "pretezno vedro",
    Condition.PARTLY_CLOUDY: "djelomicno oblacno",
    Condition.OVERCAST: "oblacno",
    Condition.FOG: "magla",
    Condition.DRIZZLE: "rosulja",
    Condition.RAIN: "kisa",
    Condition.SLEET: "susnjezica",
    Condition.SNOW: "snijeg",
    Condition.THUNDER: "grmljavina",
    Condition.THUNDER_HAIL: "grmljavina s tucom",
}

def icon_for(condition, is_night=False):
    """Naziv datoteke slikice za stanje."""
    if condition is None:
        return UNKNOWN_ICON
    if is_night and condition in NIGHT_ICONS:
        return NIGHT_ICONS[condition]
    return CONDITION_ICONS.get(condition, UNKNOWN_ICON)


def label_for(condition):
    if condition is None:
        return "nepoznato"
    return CONDITION_LABELS.get(condition, "nepoznato")


# --- Open-Meteo / WMO -------------------------------------------------------

WMO = {
    0: Condition.CLEAR,
    1: Condition.MAINLY_CLEAR,
    2: Condition.PARTLY_CLOUDY,
    3: Condition.OVERCAST,
    45: Condition.FOG,
    48: Condition.FOG,
    51: Condition.DRIZZLE,
    53: Condition.DRIZZLE,
    55: Condition.DRIZZLE,
    56: Condition.SLEET,
    57: Condition.SLEET,
    61: Condition.RAIN,
    63: Condition.RAIN,
    65: Condition.RAIN,
    66: Condition.SLEET,
    67: Condition.SLEET,
    71: Condition.SNOW,
    73: Condition.SNOW,
    75: Condition.SNOW,
    77: Condition.SNOW,
    80: Condition.RAIN,
    81: Condition.RAIN,
    82: Condition.RAIN,
    85: Condition.SNOW,
    86: Condition.SNOW,
    95: Condition.THUNDER,
    96: Condition.THUNDER_HAIL,
    99: Condition.THUNDER_HAIL,
}


def from_wmo(code):
    try:
        return WMO.get(int(code))
    except (TypeError, ValueError):
        return None


# --- WeatherAPI.com ---------------------------------------------------------

WEATHER_API = {
    1000: Condition.CLEAR,
    1003: Condition.PARTLY_CLOUDY,
    1006: Condition.OVERCAST,
    1009: Condition.OVERCAST,
    1030: Condition.FOG,
    1063: Condition.RAIN,
    1066: Condition.SNOW,
    1069: Condition.SLEET,
    1072: Condition.SLEET,
    1087: Condition.THUNDER,
    1114: Condition.SNOW,
    1117: Condition.SNOW,
    1135: Condition.FOG,
    1147: Condition.FOG,
    1150: Condition.DRIZZLE,
    1153: Condition.DRIZZLE,
    1168: Condition.SLEET,
    1171: Condition.SLEET,
    1180: Condition.RAIN,
    1183: Condition.RAIN,
    1186: Condition.RAIN,
    1189: Condition.RAIN,
    1192: Condition.RAIN,
    1195: Condition.RAIN,
    1198: Condition.SLEET,
    1201: Condition.SLEET,
    1204: Condition.SLEET,
    1207: Condition.SLEET,
    1210: Condition.SNOW,
    1213: Condition.SNOW,
    1216: Condition.SNOW,
    1219: Condition.SNOW,
    1222: Condition.SNOW,
    1225: Condition.SNOW,
    1237: Condition.SLEET,
    1240: Condition.RAIN,
    1243: Condition.RAIN,
    1246: Condition.RAIN,
    1249: Condition.SLEET,
    1252: Condition.SLEET,
    1255: Condition.SNOW,
    1258: Condition.SNOW,
    1261: Condition.SLEET,
    1264: Condition.SLEET,
    1273: Condition.THUNDER,
    1276: Condition.THUNDER,
    1279: Condition.THUNDER,
    1282: Condition.THUNDER,
}


def from_weather_api(code):
    try:
        return WEATHER_API.get(int(code))
    except (TypeError, ValueError):
        return None


# --- wttr.in / World Weather Online ----------------------------------------

WWO = {
    113: Condition.CLEAR,
    116: Condition.PARTLY_CLOUDY,
    119: Condition.OVERCAST,
    122: Condition.OVERCAST,
    143: Condition.FOG,
    176: Condition.RAIN,
    179: Condition.SNOW,
    182: Condition.SLEET,
    185: Condition.SLEET,
    200: Condition.THUNDER,
    227: Condition.SNOW,
    230: Condition.SNOW,
    248: Condition.FOG,
    260: Condition.FOG,
    263: Condition.DRIZZLE,
    266: Condition.DRIZZLE,
    281: Condition.SLEET,
    284: Condition.SLEET,
    293: Condition.RAIN,
    296: Condition.RAIN,
    299: Condition.RAIN,
    302: Condition.RAIN,
    305: Condition.RAIN,
    308: Condition.RAIN,
    311: Condition.SLEET,
    314: Condition.SLEET,
    317: Condition.SLEET,
    320: Condition.SLEET,
    323: Condition.SNOW,
    326: Condition.SNOW,
    329: Condition.SNOW,
    332: Condition.SNOW,
    335: Condition.SNOW,
    338: Condition.SNOW,
    350: Condition.SLEET,
    353: Condition.RAIN,
    356: Condition.RAIN,
    359: Condition.RAIN,
    362: Condition.SLEET,
    365: Condition.SLEET,
    368: Condition.SNOW,
    371: Condition.SNOW,
    374: Condition.SLEET,
    377: Condition.SLEET,
    386: Condition.THUNDER,
    389: Condition.THUNDER,
    392: Condition.THUNDER,
    395: Condition.THUNDER,
}


def from_wwo(code):
    try:
        return WWO.get(int(code))
    except (TypeError, ValueError):
        return None


# --- MET Norway -------------------------------------------------------------

# met.no vraca tekst tipa "lightrainshowers_day" ili "heavysleetandthunder".
# Redoslijed je bitan: "rainandthunder" sadrzi i "rain" i "thunder", a
# grmljavina je ono sto zapravo opisuje taj sat.
_MET_NO_RULES = [
    ("thunder", Condition.THUNDER),
    ("sleet", Condition.SLEET),
    ("snow", Condition.SNOW),
    ("rain", Condition.RAIN),
    ("drizzle", Condition.DRIZZLE),
    ("fog", Condition.FOG),
    ("partlycloudy", Condition.PARTLY_CLOUDY),
    ("cloudy", Condition.OVERCAST),
    ("fair", Condition.MAINLY_CLEAR),
    ("clearsky", Condition.CLEAR),
]


def from_met_no(symbol_code):
    if not symbol_code:
        return None
    key = str(symbol_code).lower()
    for suffix in ("_day", "_night", "_polartwilight"):
        if key.endswith(suffix):
            key = key[: -len(suffix)]
            break
    for needle, condition in _MET_NO_RULES:
        if needle in key:
            return condition
    return None


# --- 7Timer! ----------------------------------------------------------------

# 7Timer vraca tekst tipa "pcloudyday", "tsrainnight", "lightrainday".
#
# Ovdje se gleda pocetak imena, a ne sadrzi li ga - za razliku od met.no,
# koji imena spaja ("rainandthunder"). Kod 7Timera bi traženje podniza bilo
# krivo: "lightsnow" sadrzi "ts" (ligh-TS-now) pa bi snijeg ispao
# grmljavina. Svako njihovo ime pocinje onim sto stvarno znaci.
#
# Redoslijed je i dalje bitan: "tsrain" pocinje s "ts", "rainsnow" s
# "rain", a "lightrain" je rosulja, ne kisa.
_SEVEN_TIMER_RULES = [
    ("tsrain", Condition.THUNDER),
    ("ts", Condition.THUNDER),
    ("rainsnow", Condition.SLEET),
    ("lightrain", Condition.DRIZZLE),
    ("oshower", Condition.RAIN),
    ("ishower", Condition.RAIN),
    ("rain", Condition.RAIN),
    ("lightsnow", Condition.SNOW),
    ("snow", Condition.SNOW),
    ("fog", Condition.FOG),
    # "humid" je kod njih sumaglica/velika vlaga - najblize magli.
    ("humid", Condition.FOG),
    ("pcloudy", Condition.MAINLY_CLEAR),
    ("mcloudy", Condition.PARTLY_CLOUDY),
    ("cloudy", Condition.OVERCAST),
    ("clear", Condition.CLEAR),
]


def from_7timer(weather):
    if not weather:
        return None
    key = str(weather).lower()
    for suffix in ("day", "night"):
        if key.endswith(suffix):
            key = key[: -len(suffix)]
            break
    for prefix, condition in _SEVEN_TIMER_RULES:
        if key.startswith(prefix):
            return condition
    return None


# 7Timer ne daje brzinu vjetra u km/h nego razred 1-8. Bez pretvorbe bi
# razred 3 usao u prosjek kao "3 km/h", a to je zapravo oko 20 km/h.
# Vrijednosti su sredine razreda iz njihove dokumentacije, u m/s.
_SEVEN_TIMER_WIND_MS = {
    1: 0.15,   # < 0.3 m/s, tiho
    2: 1.85,   # 0.3 - 3.4
    3: 5.70,   # 3.4 - 8.0
    4: 9.40,   # 8.0 - 10.8
    5: 14.00,  # 10.8 - 17.2
    6: 20.85,  # 17.2 - 24.5
    7: 28.55,  # 24.5 - 32.6
    8: 35.00,  # > 32.6
}


def seven_timer_wind_kph(level):
    """Razred vjetra 1-8 -> priblizna brzina u km/h."""
    try:
        speed = _SEVEN_TIMER_WIND_MS.get(int(level))
    except (TypeError, ValueError):
        return None
    return None if speed is None else speed * 3.6


# --- Tomorrow.io ------------------------------------------------------------

TOMORROW = {
    1000: Condition.CLEAR,
    1100: Condition.MAINLY_CLEAR,
    1101: Condition.PARTLY_CLOUDY,
    # Kod njih je ljestvica naoblake u pet stupnjeva, kod nas u cetiri, pa
    # "mostly cloudy" i "cloudy" zavrsavaju zajedno.
    1102: Condition.OVERCAST,
    1001: Condition.OVERCAST,
    2000: Condition.FOG,
    2100: Condition.FOG,
    4000: Condition.DRIZZLE,
    4001: Condition.RAIN,
    4200: Condition.RAIN,
    4201: Condition.RAIN,
    5000: Condition.SNOW,
    5001: Condition.SNOW,
    5100: Condition.SNOW,
    5101: Condition.SNOW,
    6000: Condition.SLEET,
    6001: Condition.SLEET,
    6200: Condition.SLEET,
    6201: Condition.SLEET,
    7000: Condition.SLEET,
    7101: Condition.SLEET,
    7102: Condition.SLEET,
    8000: Condition.THUNDER,
}


def from_tomorrow(code):
    try:
        return TOMORROW.get(int(code))
    except (TypeError, ValueError):
        return None


# --- Smjer vjetra -----------------------------------------------------------

# Samo 8 strana svijeta, jer tocno toliko slikica imamo u static/.
_COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def wind_direction(degrees):
    """Stupnjevi (odakle vjetar puse) -> ime slikice bez .png, ili None."""
    if degrees is None:
        return None
    try:
        deg = float(degrees) % 360
    except (TypeError, ValueError):
        return None
    index = int((deg + 22.5) // 45) % 8
    return _COMPASS[index]


_COMPASS_DEGREES = {name: i * 45 for i, name in enumerate(_COMPASS)}


def compass_to_degrees(name):
    """"NE" -> 45. 7Timer salje stranu svijeta kao tekst, a "VR" znaci
    promjenjiv vjetar, sto nema smisla usrednjavati."""
    if not name:
        return None
    return _COMPASS_DEGREES.get(str(name).strip().upper())
