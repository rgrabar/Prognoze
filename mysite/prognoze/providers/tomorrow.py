"""Tomorrow.io - besplatan plan, ali trazi kljuc.

Kljuc ide u varijablu okoline TOMORROW_KEY. Ako nije postavljena, izvor se
tiho preskace, kao i WeatherAPI.

Za razliku od vecine ostalih, Tomorrow.io vrti **vlastiti model** i ima
vlastite satelite, pa nije jos jedno pakiranje GFS-a ili ECMWF-a.

Dvije stvari na koje treba paziti:

  * `windSpeed` je uz `units=metric` u **m/s**, ne km/h. Bez pretvorbe bi
    vjetar od 12 km/h u prosjek usao kao 3.4 km/h.
  * kljuc putuje kao parametar u URL-u, pa se iz poruke greske brise
    (vidi `secrets`).

Koristi se samo `forecast`; trenutno stanje se racuna iz satnog niza, pa
je to jedan zahtjev umjesto dva - besplatni plan dopusta 25 na sat.

https://docs.tomorrow.io/reference/weather-forecast
"""

import os
from datetime import datetime, timezone

from ..conditions import from_tomorrow
from .base import (
    HourPoint,
    Provider,
    ProviderForecast,
    interpolate,
    ms_to_kph,
    parse_iso_utc,
    to_float,
)

FORECAST_URL = "https://api.tomorrow.io/v4/weather/forecast"


class TomorrowProvider(Provider):
    name = "tomorrow"
    label = "Tomorrow.io"
    attribution = "Tomorrow.io"
    requires_key = True

    def api_key(self):
        return os.environ.get("TOMORROW_KEY", "").strip()

    def available(self):
        return bool(self.api_key())

    def secrets(self):
        key = self.api_key()
        return [key] if key else []

    def fetch(self, location):
        payload = self.get_json(
            FORECAST_URL,
            params={
                "location": "{0},{1}".format(
                    location.latitude, location.longitude
                ),
                "timesteps": "1h",
                "units": "metric",
                "apikey": self.api_key(),
            },
        )

        forecast = ProviderForecast(name=self.name, label=self.label)

        hourly = ((payload.get("timelines") or {}).get("hourly")) or []
        for slot in hourly:
            moment = parse_iso_utc(slot.get("time"))
            if moment is None:
                continue

            values = slot.get("values") or {}
            forecast.hours.append(
                HourPoint(
                    time=moment,
                    temp_c=to_float(values.get("temperature")),
                    condition=from_tomorrow(values.get("weatherCode")),
                    precip_prob=to_float(
                        values.get("precipitationProbability")
                    ),
                    # metric znaci m/s, a mi svugdje racunamo u km/h.
                    wind_kph=ms_to_kph(values.get("windSpeed")),
                    wind_dir_deg=to_float(values.get("windDirection")),
                    humidity=to_float(values.get("humidity")),
                    uv=to_float(values.get("uvIndex")),
                )
            )

        current = interpolate(forecast.hours, datetime.now(timezone.utc))
        if current is not None:
            forecast.temp_c = current.temp_c
            forecast.condition = current.condition
            forecast.precip_prob = current.precip_prob
            forecast.wind_kph = current.wind_kph
            forecast.wind_dir_deg = current.wind_dir_deg
            forecast.humidity = current.humidity
            forecast.uv = current.uv

        return forecast


def build():
    return [TomorrowProvider()]
