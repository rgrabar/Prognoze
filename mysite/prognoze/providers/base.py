"""Zajednicki oblik podataka za sve izvore prognoze.

Svaki izvor vraca `ProviderForecast`. Sva polja su neobavezna - ako neki API
ne daje vlaznost ili vjerojatnost kise, to polje ostane None i usrednjavanje
ga jednostavno preskoci umjesto da cijela stranica pukne.

Sva vremena su timezone-aware i u UTC-u. To je namjerno: izvori se razlikuju
(Open-Meteo vraca lokalno vrijeme, met.no UTC, wttr.in lokalno bez oznake),
pa se satnice slazu samo ako se sve svede na istu os.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

import requests

from ..conditions import Condition

# Nijedan API ne smije drzati stranicu zauvijek.
HTTP_TIMEOUT = 6


@dataclass
class HourPoint:
    """Jedan sat prognoze, s jednog izvora."""

    time: datetime  # aware, UTC
    temp_c: Optional[float] = None
    condition: Optional[Condition] = None
    precip_prob: Optional[float] = None
    wind_kph: Optional[float] = None
    wind_dir_deg: Optional[float] = None
    humidity: Optional[float] = None
    uv: Optional[float] = None


@dataclass
class ProviderForecast:
    """Rezultat jednog izvora."""

    name: str
    label: str
    temp_c: Optional[float] = None
    wind_kph: Optional[float] = None
    wind_dir_deg: Optional[float] = None
    humidity: Optional[float] = None
    condition: Optional[Condition] = None
    precip_prob: Optional[float] = None
    uv: Optional[float] = None
    hours: List[HourPoint] = field(default_factory=list)
    # Parovi (izlazak, zalazak) u UTC-u - za odabir sunca ili mjeseca.
    sun_times: List[Tuple[datetime, datetime]] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def ok(self):
        return self.error is None


class Provider:
    """Bazni izvor. Nasljednici implementiraju `fetch`."""

    name = ""
    label = ""
    attribution = ""
    # True ako izvor treba kljuc; takvi se preskacu ako kljuc nije postavljen.
    requires_key = False

    def available(self):
        return True

    def fetch(self, location):
        raise NotImplementedError

    def secrets(self):
        """Vrijednosti koje se ne smiju pojaviti u dnevniku ni na stranici.

        Kljucevi putuju u URL-u - kod WeatherAPIja kao parametar, kod nekih
        drugih i u samoj putanji. Kad zahtjev pukne, poruka greske sadrzi
        cijeli URL, a ta poruka zavrsi u dnevniku. Izvori s kljucem ovdje
        vracaju svoj kljuc da ga se prije toga izbrise.
        """
        return []

    # -- pomocnici ---------------------------------------------------------

    def get_json(self, url, params=None, headers=None):
        response = requests.get(
            url, params=params, headers=headers, timeout=HTTP_TIMEOUT
        )
        response.raise_for_status()
        return response.json()

    def empty(self, error):
        return ProviderForecast(name=self.name, label=self.label, error=error)

    def empty_result(self, error):
        """Sto vratiti kad `fetch` pukne.

        Izvori koji vracaju vise prognoza odjednom (npr. Open-Meteo sa
        svojih sest modela) ovo nadjacaju popisom, da svaki model ostane
        vidljiv u popisu izvora umjesto da ih svih sest nestane.
        """
        return self.empty(error)


def parse_iso_utc(value, utc_offset_seconds=0):
    """ISO vrijeme -> aware datetime u UTC-u.

    Podnosi i "Z" na kraju (Python 3.8 `fromisoformat` to ne zna sam) i
    vrijeme bez oznake zone, koje se tada tumaci kao lokalno pa pomice za
    `utc_offset_seconds`.
    """
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone(timedelta(seconds=utc_offset_seconds))
        )
    return parsed.astimezone(timezone.utc)


def nearest_point(hours, moment):
    """Termin najblizi zadanom trenutku, ili None ako niza nema."""
    if not hours:
        return None
    return min(hours, key=lambda h: abs(h.time - moment))


def interpolate(hours, now):
    """Stanje "sada" iz satnog ili tro-satnog niza.

    Uzimanje najblizeg termina zna promasiti i do sat i pol, a navecer se
    temperatura u tom razmaku spusti za par stupnjeva. Zato se brojevi
    linearno interpoliraju izmedu termina prije i poslije.

    Ne interpolira se sve: stanje neba nije broj, a smjer vjetra se ne
    smije usrednjavati linearno (izmedu 350 i 10 stupnjeva nije 180). Oboje
    se uzima iz blizeg termina.
    """
    if not hours:
        return None

    ordered = sorted(hours, key=lambda h: h.time)
    before = [h for h in ordered if h.time <= now]
    after = [h for h in ordered if h.time > now]

    if not before or not after:
        return nearest_point(ordered, now)

    start, end = before[-1], after[0]
    span = (end.time - start.time).total_seconds()
    if span <= 0:
        return start

    ratio = (now - start.time).total_seconds() / span
    blizi = start if ratio < 0.5 else end

    def blend(first, second):
        if first is None or second is None:
            return first if second is None else second
        return first + (second - first) * ratio

    return HourPoint(
        time=now,
        temp_c=blend(start.temp_c, end.temp_c),
        condition=blizi.condition,
        precip_prob=blend(start.precip_prob, end.precip_prob),
        wind_kph=blend(start.wind_kph, end.wind_kph),
        wind_dir_deg=blizi.wind_dir_deg,
        humidity=blend(start.humidity, end.humidity),
        uv=blend(start.uv, end.uv),
    )


def to_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def ms_to_kph(value):
    number = to_float(value)
    return None if number is None else number * 3.6
