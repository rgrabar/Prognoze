"""7Timer! - besplatno, bez kljuca, bez registracije.

Dvije zamke, obje rijesene u `conditions.py`:

  * brzina vjetra nije km/h nego razred 1-8, pa se pretvara;
  * vlaga stize kao tekst ("73%"), ne kao broj.

Vremena: `init` je pocetak u UTC-u ("2026090212"), a svaki `timepoint` je
broj sati od tog trenutka. Korak je 3 sata.

http://www.7timer.info/doc.php
"""

from datetime import datetime, timedelta, timezone

from ..conditions import compass_to_degrees, from_7timer, seven_timer_wind_kph
from .base import (
    HourPoint,
    Provider,
    ProviderForecast,
    interpolate,
    to_float,
)

FORECAST_URL = "http://www.7timer.info/bin/api.pl"


def parse_humidity(value):
    """rh2m dolazi kao "73%". Prihvati samo smislen postotak."""
    if value is None:
        return None
    number = to_float(str(value).replace("%", "").strip())
    if number is None or not 0 <= number <= 100:
        return None
    return number


def parse_init(value):
    """"2026090212" -> datetime u UTC-u."""
    try:
        return datetime.strptime(str(value), "%Y%m%d%H").replace(
            tzinfo=timezone.utc
        )
    except (TypeError, ValueError):
        return None


class SevenTimerProvider(Provider):
    name = "seven_timer"
    label = "7Timer!"
    attribution = "7Timer! / NOAA GFS"

    def fetch(self, location):
        payload = self.get_json(
            FORECAST_URL,
            params={
                "lat": round(location.latitude, 4),
                "lon": round(location.longitude, 4),
                "product": "civil",
                "output": "json",
            },
        )

        forecast = ProviderForecast(name=self.name, label=self.label)

        start = parse_init(payload.get("init"))
        if start is None:
            return self.empty("neispravan 'init' u odgovoru")

        for entry in payload.get("dataseries") or []:
            offset = to_float(entry.get("timepoint"))
            if offset is None:
                continue

            wind = entry.get("wind10m") or {}
            forecast.hours.append(
                HourPoint(
                    time=start + timedelta(hours=offset),
                    temp_c=to_float(entry.get("temp2m")),
                    condition=from_7timer(entry.get("weather")),
                    # 7Timer ne daje vjerojatnost oborine, samo razred kolicine.
                    precip_prob=None,
                    wind_kph=seven_timer_wind_kph(wind.get("speed")),
                    wind_dir_deg=compass_to_degrees(wind.get("direction")),
                    humidity=parse_humidity(entry.get("rh2m")),
                )
            )

        # Nema zasebnog "trenutno" - izracunaj ga iz niza. Smjer vjetra
        # `interpolate` uzima iz blizeg termina, ne prosjekom.
        current = interpolate(forecast.hours, datetime.now(timezone.utc))
        if current is not None:
            forecast.temp_c = current.temp_c
            forecast.condition = current.condition
            forecast.wind_kph = current.wind_kph
            forecast.wind_dir_deg = current.wind_dir_deg
            forecast.humidity = current.humidity

        return forecast


def build():
    return [SevenTimerProvider()]
