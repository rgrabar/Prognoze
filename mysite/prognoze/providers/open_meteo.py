"""Open-Meteo - besplatan, bez kljuca, bez registracije.

Jedan endpoint, ali `models=` bira koji numericki model racuna prognozu.
Ovdje se odjednom trazi sest modela iz cetiri razlicita centra - a bas je
to poanta usrednjavanja: vise neovisnih misljenja umjesto jednog.

**Sve ide u jednom HTTP zahtjevu.** Prije je svaki model bio zaseban poziv,
pa je jedno ucitavanje stranice znacilo sest zahtjeva prema Open-Meteou uz
jos tri (geokodiranje, zona, zrak). To je pocelo vracati 429 i nasumicno
gubiti po jedan izvor. `models=a,b,c` vraca sve u jednom odgovoru, s
kljucevima kojima je naziv modela nastavak: `temperature_2m_ukmo_seamless`.

Jedna posljedica: uz vise modela `current` **nije** razdvojen po modelu -
vrati se samo jedan blok. Zato se trenutno stanje svakog modela racuna iz
njegovog satnog niza (`interpolate`), isto kao kod 7Timera.

Dokumentacija: https://open-meteo.com/en/docs
"""

from datetime import datetime, timezone

from ..conditions import from_wmo
from .base import (
    HourPoint,
    Provider,
    ProviderForecast,
    interpolate,
    parse_iso_utc,
    to_float,
)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

HOURLY_FIELDS = (
    "weather_code,temperature_2m,relative_humidity_2m,"
    "wind_speed_10m,wind_direction_10m,precipitation_probability,"
    "precipitation,uv_index"
)
DAILY_FIELDS = "sunrise,sunset"

# UV i izlazak sunca uzimaju se samo od ovog modela. Open-Meteo UV racuna
# iz istog izvora bez obzira na model (gfs vrati identicne brojke), pa bi
# inace jedan te isti podatak glasao vise puta.
UV_MODEL = "best_match"


class Model:
    """Jedan model u zajednickom zahtjevu."""

    def __init__(self, name, label, key, precip_prob=True):
        self.name = name
        self.label = label
        # Oznaka modela kod Open-Meteoa; ujedno nastavak na nazive polja.
        self.key = key
        self.precip_prob = precip_prob


MODELS = [
    Model("open_meteo", "Open-Meteo (best match)", "best_match"),
    Model("open_meteo_gfs", "NOAA GFS (Open-Meteo)", "gfs_seamless"),
    Model(
        "open_meteo_arpege",
        "Meteo-France ARPEGE (Open-Meteo)",
        "meteofrance_seamless",
    ),
    Model("open_meteo_ecmwf", "ECMWF IFS (Open-Meteo)", "ecmwf_ifs025"),
    Model("open_meteo_ukmo", "UK Met Office (Open-Meteo)", "ukmo_seamless"),
    # GEM ne glasa o vjerojatnosti oborine. Njegova brojka nije ista
    # velicina kao kod ostalih: za vedar dan u Rijeci javljao je 71%
    # vjerojatnosti kise, a istovremeno 0.0 mm oborine, kod 0 (vedro) i 8%
    # naoblake. Vjerojatno je racunata iz rasapa ansambla, pa mjeri "ima li
    # ikakvog traga" umjesto stvarne sanse za kisu. Uprosjecena s ostalima
    # dizala je 2% na 19%.
    Model(
        "open_meteo_gem",
        "Environment Canada GEM (Open-Meteo)",
        "gem_seamless",
        precip_prob=False,
    ),
]

# Namjerno izostavljeni modeli:
#
#   icon_seamless   - za Rijeku vraca doslovno iste brojke kao best_match
#                     (provjereno: 24 od 24 sata identicno), pa bi DWD u
#                     prosjeku vrijedio dvostruko.
#   metno_seamless  - MET Norway vec zovemo izravno, u met_no.py.
#   ecmwf_ifs04     - stara oznaka; odgovara sa 200, ali su sve vrijednosti
#                     null.


class OpenMeteoProvider(Provider):
    """Dohvaca sve modele odjednom i vraca po jednu prognozu za svaki."""

    name = "open_meteo_group"
    label = "Open-Meteo"
    attribution = "open-meteo.com (CC BY 4.0)"

    def empty_result(self, error):
        """Kad zajednicki zahtjev padne, padaju svi modeli - ali svaki se i
        dalje mora pojaviti u popisu izvora, kao nedostupan."""
        return [
            ProviderForecast(name=m.name, label=m.label, error=error)
            for m in MODELS
        ]

    def fetch(self, location):
        payload = self.get_json(
            FORECAST_URL,
            params={
                "latitude": location.latitude,
                "longitude": location.longitude,
                "hourly": HOURLY_FIELDS,
                "daily": DAILY_FIELDS,
                "models": ",".join(m.key for m in MODELS),
                # Trazimo UTC pa se satnice svih izvora poklapaju bez pogadanja.
                "timezone": "UTC",
                # Lokalna ponoc pada u jucerasnji UTC dan (Rijeka je +1/+2),
                # pa bez `past_days` prvi sati danasnje trake ostanu prazni.
                "past_days": 1,
                # Danas plus cetiri dana za prognozu sa strane, i jos jedan
                # da zadnji dan bude cijeli i nakon pomaka zone.
                "forecast_days": 6,
            },
        )

        hourly = payload.get("hourly") or {}
        daily = payload.get("daily") or {}
        times = [parse_iso_utc(t) for t in (hourly.get("time") or [])]
        now = datetime.now(timezone.utc)

        return [
            self._one_model(model, hourly, daily, times, now)
            for model in MODELS
        ]

    def _one_model(self, model, hourly, daily, times, now):
        def series(field):
            return hourly.get("{0}_{1}".format(field, model.key)) or []

        temps = series("temperature_2m")
        codes = series("weather_code")
        winds = series("wind_speed_10m")
        directions = series("wind_direction_10m")
        humidities = series("relative_humidity_2m")
        probs = series("precipitation_probability") if model.precip_prob else []
        # Kolicina (mm) je pouzdana i kod GEM-a - on je za vedar dan javljao
        # 71% *vjerojatnosti*, ali 0.0 mm. Zato mm uzimamo od svih.
        amounts = series("precipitation")
        uvs = series("uv_index") if model.key == UV_MODEL else []

        def at(values, index):
            return values[index] if index < len(values) else None

        forecast = ProviderForecast(name=model.name, label=model.label)

        for index, moment in enumerate(times):
            if moment is None:
                continue
            forecast.hours.append(
                HourPoint(
                    time=moment,
                    temp_c=to_float(at(temps, index)),
                    condition=from_wmo(at(codes, index)),
                    precip_prob=to_float(at(probs, index)),
                    precip_mm=to_float(at(amounts, index)),
                    wind_kph=to_float(at(winds, index)),
                    wind_dir_deg=to_float(at(directions, index)),
                    humidity=to_float(at(humidities, index)),
                    uv=to_float(at(uvs, index)),
                )
            )

        # Uz vise modela Open-Meteo ne vraca `current` po modelu, pa se
        # trenutno stanje racuna iz satnog niza samog modela.
        current = interpolate(forecast.hours, now)
        if current is not None:
            forecast.temp_c = current.temp_c
            forecast.condition = current.condition
            forecast.wind_kph = current.wind_kph
            forecast.wind_dir_deg = current.wind_dir_deg
            forecast.humidity = current.humidity
            forecast.precip_prob = current.precip_prob
            forecast.precip_mm = current.precip_mm
            forecast.uv = current.uv

        if model.key == UV_MODEL:
            sunrises = daily.get("sunrise_{0}".format(model.key)) or []
            sunsets = daily.get("sunset_{0}".format(model.key)) or []
            for sunrise, sunset in zip(sunrises, sunsets):
                rise = parse_iso_utc(sunrise)
                set_ = parse_iso_utc(sunset)
                if rise and set_:
                    forecast.sun_times.append((rise, set_))

        return forecast


def build():
    return [OpenMeteoProvider()]
