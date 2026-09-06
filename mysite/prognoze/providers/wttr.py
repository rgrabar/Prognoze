"""wttr.in - besplatno, bez kljuca, bez registracije.

Vraca podatke u koracima od 3 sata i u lokalnom vremenu bez oznake zone,
pa se vrijeme pomice pomocu `location.utc_offset_seconds`.

https://github.com/chubin/wttr.in
"""

from datetime import datetime, timedelta, timezone

from ..conditions import from_wwo
from .base import HourPoint, Provider, ProviderForecast, to_float

BASE_URL = "https://wttr.in/{lat},{lon}"


class WttrProvider(Provider):
    name = "wttr"
    label = "wttr.in"
    attribution = "wttr.in"

    def fetch(self, location):
        url = BASE_URL.format(lat=location.latitude, lon=location.longitude)
        payload = self.get_json(
            url,
            params={"format": "j1"},
            headers={"User-Agent": "Prognoze/1.0"},
        )

        forecast = ProviderForecast(name=self.name, label=self.label)

        current_list = payload.get("current_condition") or []
        if current_list:
            current = current_list[0]
            forecast.temp_c = to_float(current.get("temp_C"))
            forecast.wind_kph = to_float(current.get("windspeedKmph"))
            forecast.wind_dir_deg = to_float(current.get("winddirDegree"))
            forecast.humidity = to_float(current.get("humidity"))
            forecast.condition = from_wwo(current.get("weatherCode"))
            forecast.uv = to_float(current.get("uvIndex"))

        local_zone = timezone(timedelta(seconds=location.utc_offset_seconds))

        for day in payload.get("weather") or []:
            try:
                date = datetime.strptime(day.get("date", ""), "%Y-%m-%d").date()
            except ValueError:
                continue

            for slot in day.get("hourly") or []:
                # "0", "300", "1500" -> 0, 3, 15
                try:
                    hour = int(slot.get("time", "0")) // 100
                except (TypeError, ValueError):
                    continue

                moment = datetime(
                    date.year, date.month, date.day, hour, tzinfo=local_zone
                ).astimezone(timezone.utc)

                forecast.hours.append(
                    HourPoint(
                        time=moment,
                        temp_c=to_float(slot.get("tempC")),
                        condition=from_wwo(slot.get("weatherCode")),
                        precip_prob=to_float(slot.get("chanceofrain")),
                        wind_kph=to_float(slot.get("windspeedKmph")),
                        humidity=to_float(slot.get("humidity")),
                        uv=to_float(slot.get("uvIndex")),
                    )
                )

        return forecast


def build():
    return [WttrProvider()]
