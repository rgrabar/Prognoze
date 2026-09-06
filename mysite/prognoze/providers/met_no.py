"""MET Norway (Norveski meteoroloski institut) - besplatno, bez kljuca.

Trazi samo posten `User-Agent` s kontaktom i da se koordinate zaokruze na
najvise 4 decimale (inace im rusis cache i blokiraju te).

Uvjeti: https://api.met.no/doc/TermsOfService
Podaci: MET Norway, licenca CC BY 4.0 / NLOD.
"""

import os

from ..conditions import from_met_no
from .base import (
    HourPoint,
    Provider,
    ProviderForecast,
    ms_to_kph,
    parse_iso_utc,
    to_float,
)

FORECAST_URL = "https://api.met.no/weatherapi/locationforecast/2.0/complete"

DEFAULT_USER_AGENT = (
    "Prognoze/1.0 (osobni projekt; postavi MET_NO_USER_AGENT za kontakt)"
)


class MetNoProvider(Provider):
    name = "met_no"
    label = "MET Norway"
    attribution = "MET Norway (CC BY 4.0)"

    def user_agent(self):
        return os.environ.get("MET_NO_USER_AGENT", DEFAULT_USER_AGENT)

    def fetch(self, location):
        payload = self.get_json(
            FORECAST_URL,
            # met.no trazi najvise 4 decimale.
            params={
                "lat": round(location.latitude, 4),
                "lon": round(location.longitude, 4),
            },
            headers={"User-Agent": self.user_agent()},
        )

        series = (payload.get("properties") or {}).get("timeseries") or []
        forecast = ProviderForecast(name=self.name, label=self.label)

        for entry in series:
            moment = parse_iso_utc(entry.get("time"))
            if moment is None:
                continue

            data = entry.get("data") or {}
            instant = ((data.get("instant") or {}).get("details")) or {}
            next_hour = data.get("next_1_hours") or {}
            summary = next_hour.get("summary") or {}
            details = next_hour.get("details") or {}

            forecast.hours.append(
                HourPoint(
                    time=moment,
                    temp_c=to_float(instant.get("air_temperature")),
                    condition=from_met_no(summary.get("symbol_code")),
                    precip_prob=to_float(
                        details.get("probability_of_precipitation")
                    ),
                    # met.no daje m/s, mi svugdje racunamo u km/h.
                    wind_kph=ms_to_kph(instant.get("wind_speed")),
                    humidity=to_float(instant.get("relative_humidity")),
                )
            )

        if series:
            first = series[0].get("data") or {}
            instant = ((first.get("instant") or {}).get("details")) or {}
            summary = ((first.get("next_1_hours") or {}).get("summary")) or {}
            details = ((first.get("next_1_hours") or {}).get("details")) or {}

            forecast.temp_c = to_float(instant.get("air_temperature"))
            forecast.wind_kph = ms_to_kph(instant.get("wind_speed"))
            forecast.wind_dir_deg = to_float(instant.get("wind_from_direction"))
            forecast.humidity = to_float(instant.get("relative_humidity"))
            forecast.condition = from_met_no(summary.get("symbol_code"))
            forecast.precip_prob = to_float(
                details.get("probability_of_precipitation")
            )

        return forecast


def build():
    return [MetNoProvider()]
