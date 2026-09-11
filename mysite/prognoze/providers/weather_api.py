"""WeatherAPI.com - besplatan plan, ali trazi kljuc.

Kljuc ide u varijablu okoline WEATHERAPI_KEY. Ako nije postavljena, izvor se
tiho preskace i prosjek se racuna iz ostalih (koji ne trebaju kljuc).
"""

import os
from datetime import datetime, timedelta, timezone

from ..conditions import from_weather_api
from .base import HourPoint, Provider, ProviderForecast, to_float

FORECAST_URL = "http://api.weatherapi.com/v1/forecast.json"


class WeatherApiProvider(Provider):
    name = "weather_api"
    label = "WeatherAPI.com"
    attribution = "WeatherAPI.com"
    requires_key = True

    def api_key(self):
        return os.environ.get("WEATHERAPI_KEY", "").strip()

    def available(self):
        return bool(self.api_key())

    def secrets(self):
        # Kljuc ide kao parametar u URL-u, pa bi bez ovoga zavrsio u
        # dnevniku cim zahtjev pukne.
        key = self.api_key()
        return [key] if key else []

    def fetch(self, location):
        payload = self.get_json(
            FORECAST_URL,
            params={
                "key": self.api_key(),
                "q": "{0},{1}".format(location.latitude, location.longitude),
                # Besplatni plan daje najvise 3 dana.
                "days": 3,
                "aqi": "no",
                "alerts": "no",
            },
        )

        forecast = ProviderForecast(name=self.name, label=self.label)

        current = payload.get("current") or {}
        if current:
            forecast.temp_c = to_float(current.get("temp_c"))
            forecast.wind_kph = to_float(current.get("wind_kph"))
            forecast.wind_dir_deg = to_float(current.get("wind_degree"))
            forecast.humidity = to_float(current.get("humidity"))
            forecast.condition = from_weather_api(
                (current.get("condition") or {}).get("code")
            )
            forecast.uv = to_float(current.get("uv"))
            forecast.precip_mm = to_float(current.get("precip_mm"))

        # WeatherAPI vraca lokalno vrijeme mjesta, bez oznake zone.
        local_zone = timezone(timedelta(seconds=location.utc_offset_seconds))

        days = (payload.get("forecast") or {}).get("forecastday") or []
        for day in days:
            for slot in day.get("hour") or []:
                try:
                    naive = datetime.strptime(
                        slot.get("time", ""), "%Y-%m-%d %H:%M"
                    )
                except ValueError:
                    continue

                moment = naive.replace(tzinfo=local_zone).astimezone(
                    timezone.utc
                )

                forecast.hours.append(
                    HourPoint(
                        time=moment,
                        temp_c=to_float(slot.get("temp_c")),
                        condition=from_weather_api(
                            (slot.get("condition") or {}).get("code")
                        ),
                        precip_prob=to_float(slot.get("chance_of_rain")),
                        precip_mm=to_float(slot.get("precip_mm")),
                        wind_kph=to_float(slot.get("wind_kph")),
                        humidity=to_float(slot.get("humidity")),
                        uv=to_float(slot.get("uv")),
                    )
                )

        return forecast


def build():
    return [WeatherApiProvider()]
