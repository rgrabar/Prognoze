"""Odredivanje mjesta.

Redoslijed je od najpouzdanijeg prema najgrubljem:

  1. `?q=Split`      - covjek je sam upisao, to uvijek pobjeduje;
  2. `?lat=&lon=`    - tocna lokacija iz preglednika, uz dopustenje;
  3. IP adresa       - automatski, bez pitanja, ali samo priblizno;
  4. Rijeka          - ako nista od navedenog ne uspije.

Sve usluge su besplatne i bez kljuca.
"""

import ipaddress
import logging
import os
from dataclasses import dataclass

import requests
from django.core.cache import cache

logger = logging.getLogger(__name__)

SEARCH_URL = "https://geocoding-api.open-meteo.com/v1/search"
OFFSET_URL = "https://api.open-meteo.com/v1/forecast"
IP_LOOKUP_URL = "https://ipwho.is/"
REVERSE_URL = "https://api.bigdatacloud.net/data/reverse-geocode-client"

HTTP_TIMEOUT = 6
LOCATION_CACHE_SECONDS = 24 * 3600
IP_CACHE_SECONDS = 6 * 3600

# Kako je mjesto odredeno - prikazuje se na stranici.
BY_QUERY = "upisano"
BY_PRECISE = "tocna lokacija"
BY_IP = "prema IP adresi"
BY_DEFAULT = "zadano"


@dataclass
class Location:
    name: str
    country: str
    latitude: float
    longitude: float
    # Pomak lokalnog vremena mjesta u odnosu na UTC. Treba izvorima koji
    # vracaju lokalno vrijeme bez oznake zone (wttr.in, WeatherAPI).
    utc_offset_seconds: int = 0
    source: str = BY_DEFAULT

    @property
    def title(self):
        return "{0}, {1}".format(self.name, self.country) if self.country else self.name


# Iste koordinate koje su i prije bile u kodu.
DEFAULT_LOCATION = Location(
    name="Rijeka",
    country="Hrvatska",
    latitude=45.32154636314539,
    longitude=14.473822849484131,
)


def utc_offset_for(latitude, longitude):
    """Pomak zone mjesta, u sekundama. Open-Meteo ga vrati uz `timezone=auto`."""
    key = "prognoze:offset:{0:.3f}:{1:.3f}".format(latitude, longitude)
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        response = requests.get(
            OFFSET_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m",
                "timezone": "auto",
            },
            timeout=HTTP_TIMEOUT,
        )
        response.raise_for_status()
        offset = int(response.json().get("utc_offset_seconds") or 0)
    except Exception as error:
        logger.warning("Ne mogu dohvatiti vremensku zonu: %s", error)
        return 0

    cache.set(key, offset, LOCATION_CACHE_SECONDS)
    return offset


def search(query):
    """Nadi mjesto po imenu. Vraca Location ili None."""
    key = "prognoze:geo:{0}".format(query.strip().lower())
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        response = requests.get(
            SEARCH_URL,
            params={
                "name": query,
                "count": 1,
                "language": "hr",
                "format": "json",
            },
            timeout=HTTP_TIMEOUT,
        )
        response.raise_for_status()
        results = response.json().get("results") or []
    except Exception as error:
        logger.warning("Trazenje mjesta nije uspjelo: %s", error)
        return None

    if not results:
        return None

    hit = results[0]
    location = Location(
        name=hit.get("name") or query,
        country=hit.get("country") or "",
        latitude=float(hit["latitude"]),
        longitude=float(hit["longitude"]),
    )
    cache.set(key, location, LOCATION_CACHE_SECONDS)
    return location


def is_public_ip(ip):
    """Lokalne adrese nema smisla slati na provjeru - u razvoju je klijent
    uvijek 127.0.0.1, a usluga na to vraca "Reserved range"."""
    if not ip:
        return False
    try:
        address = ipaddress.ip_address(ip.strip())
    except ValueError:
        return False
    return not (
        address.is_private
        or address.is_loopback
        or address.is_reserved
        or address.is_link_local
        or address.is_multicast
    )


def ip_lookup_enabled():
    """Trazenje po IP-u se moze ugasiti s PROGNOZE_IP_LOOKUP=0."""
    return os.environ.get("PROGNOZE_IP_LOOKUP", "1") != "0"


def from_ip(ip):
    """Priblizno mjesto iz IP adrese. Vraca Location ili None.

    Ovo salje posjetiteljevu IP adresu vanjskoj usluzi (ipwho.is). Zato se
    radi samo za javne adrese, rezultat se pamti nekoliko sati, a cijela se
    stvar da ugasiti varijablom okoline.
    """
    if not ip_lookup_enabled() or not is_public_ip(ip):
        return None

    key = "prognoze:ip:{0}".format(ip)
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        response = requests.get(
            IP_LOOKUP_URL + ip, timeout=HTTP_TIMEOUT
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as error:
        logger.warning("Trazenje po IP-u nije uspjelo: %s", error)
        return None

    if not payload.get("success"):
        logger.info(
            "IP %s nije lociran: %s", ip, payload.get("message", "bez razloga")
        )
        return None

    try:
        location = Location(
            name=payload.get("city") or payload.get("region") or "Nepoznato",
            country=payload.get("country") or "",
            latitude=float(payload["latitude"]),
            longitude=float(payload["longitude"]),
            source=BY_IP,
        )
    except (KeyError, TypeError, ValueError):
        return None

    cache.set(key, location, IP_CACHE_SECONDS)
    return location


def reverse(latitude, longitude):
    """Koordinate -> ime mjesta. Koristi se za tocnu lokaciju iz preglednika."""
    key = "prognoze:rev:{0:.3f}:{1:.3f}".format(latitude, longitude)
    cached = cache.get(key)
    if cached is not None:
        return cached

    name, country = "Moja lokacija", ""
    try:
        response = requests.get(
            REVERSE_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "localityLanguage": "hr",
            },
            timeout=HTTP_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        name = (
            payload.get("city")
            or payload.get("locality")
            or payload.get("principalSubdivision")
            or name
        )
        country = payload.get("countryName") or ""
    except Exception as error:
        # Ime je samo ukras - koordinate su vec tocne, prognoza radi i bez njega.
        logger.warning("Obrnuto geokodiranje nije uspjelo: %s", error)

    location = Location(
        name=name,
        country=country,
        latitude=latitude,
        longitude=longitude,
        source=BY_PRECISE,
    )
    cache.set(key, location, LOCATION_CACHE_SECONDS)
    return location


def _coordinates(latitude, longitude):
    """Provjeri da su koordinate brojevi i unutar granica Zemlje."""
    try:
        lat, lon = float(latitude), float(longitude)
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return lat, lon


def default_location():
    return Location(
        name=DEFAULT_LOCATION.name,
        country=DEFAULT_LOCATION.country,
        latitude=DEFAULT_LOCATION.latitude,
        longitude=DEFAULT_LOCATION.longitude,
        source=BY_DEFAULT,
    )


def resolve(query=None, latitude=None, longitude=None, ip=None):
    """Odredi mjesto po redoslijedu iz zaglavlja modula."""
    location = None

    if query and query.strip():
        location = search(query)
        if location is not None:
            location.source = BY_QUERY

    if location is None:
        point = _coordinates(latitude, longitude)
        if point is not None:
            location = reverse(point[0], point[1])

    if location is None and ip:
        location = from_ip(ip)

    if location is None:
        location = default_location()

    location.utc_offset_seconds = utc_offset_for(
        location.latitude, location.longitude
    )
    return location
