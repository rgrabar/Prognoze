"""Kakvoca zraka preko Open-Meteo Air Quality APIja (besplatno, bez kljuca).

Za razliku od vremena, ovdje se nista ne usrednjava: od besplatnih izvora
bez kljuca ovaj jedini daje indeks. Mijesati ga s americkim US AQI-jem
(koji daje WeatherAPI) ne bi imalo smisla - to su dvije razlicite
ljestvice, kao sto met.no-ov UV za vedro nebo nije isto sto i obicni UV.

Koristi se europski indeks (EEA), jer je projekt hrvatski.

https://open-meteo.com/en/docs/air-quality-api
"""

import logging
from dataclasses import dataclass
from typing import Optional

import requests
from django.core.cache import cache

logger = logging.getLogger(__name__)

AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

HTTP_TIMEOUT = 6
CACHE_SECONDS = 600

# Europski indeks kakvoce zraka (EEA): granica, naziv, boja.
# Boje su iz sluzbene palete, malo potamnjene da se citaju na bijelom.
AQI_BANDS = [
    (20, "dobra", "#1a9e94"),
    (40, "zadovoljavajuca", "#2e9b7d"),
    (60, "umjerena", "#b09a00"),
    (80, "losa", "#e03131"),
    (100, "vrlo losa", "#960032"),
    (float("inf"), "izuzetno losa", "#7d2181"),
]


def aqi_band(value):
    """AQI -> (naziv, boja)."""
    if value is None:
        return ("nepoznato", "#c9c9cf")
    for granica, naziv, boja in AQI_BANDS:
        if value <= granica:
            return (naziv, boja)
    return AQI_BANDS[-1][1:]


@dataclass
class AirQuality:
    aqi: Optional[float] = None
    pm2_5: Optional[float] = None
    pm10: Optional[float] = None
    error: str = ""

    @property
    def ok(self):
        return not self.error and self.aqi is not None

    @property
    def label(self):
        return aqi_band(self.aqi)[0]

    @property
    def color(self):
        return aqi_band(self.aqi)[1]

    @property
    def title(self):
        parts = []
        if self.pm2_5 is not None:
            parts.append("PM2.5 {0}".format(self.pm2_5))
        if self.pm10 is not None:
            parts.append("PM10 {0}".format(self.pm10))
        if not parts:
            return "Europski indeks kakvoce zraka"
        return "Europski indeks kakvoce zraka | {0} µg/m³".format(
            " | ".join(parts)
        )


def _number(value):
    if value is None:
        return None
    try:
        return round(float(value), 1)
    except (TypeError, ValueError):
        return None


def quality_for(location):
    """Trenutna kakvoca zraka za mjesto. Nikad ne baca - vrati prazno."""
    key = "prognoze:zrak:{0:.3f}:{1:.3f}".format(
        location.latitude, location.longitude
    )
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        response = requests.get(
            AIR_URL,
            params={
                "latitude": location.latitude,
                "longitude": location.longitude,
                "current": "european_aqi,pm2_5,pm10",
                "timezone": "UTC",
            },
            timeout=HTTP_TIMEOUT,
        )
        response.raise_for_status()
        current = (response.json().get("current") or {})
    except Exception as error:
        logger.warning("Kakvoca zraka nije dohvacena: %s", error)
        return AirQuality(error=str(error))

    quality = AirQuality(
        aqi=_number(current.get("european_aqi")),
        pm2_5=_number(current.get("pm2_5")),
        pm10=_number(current.get("pm10")),
    )
    cache.set(key, quality, CACHE_SECONDS)
    return quality
