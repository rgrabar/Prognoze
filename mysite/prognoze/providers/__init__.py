"""Registar izvora i paralelno dohvacanje.

Sest izvora jedan za drugim znaci sest cekanja - zato idu u thread pool.
Svaki se sprema u cache 10 minuta (prognoza se ionako ne mijenja svake
sekunde), i svaki je zamotan u try/except: ako jedan API padne ili mu
istekne kljuc, prosjek se izracuna iz preostalih umjesto da stranica pukne.
"""

import logging
from concurrent.futures import ThreadPoolExecutor

from django.core.cache import cache

from . import met_no, open_meteo, seven_timer, tomorrow, weather_api, wttr
from .base import HourPoint, Provider, ProviderForecast  # noqa: F401

logger = logging.getLogger(__name__)

CACHE_SECONDS = 600


def all_providers():
    providers = []
    providers.extend(open_meteo.build())
    providers.extend(met_no.build())
    providers.extend(wttr.build())
    providers.extend(seven_timer.build())
    providers.extend(tomorrow.build())
    providers.extend(weather_api.build())
    return providers


def _cache_key(provider, location):
    return "prognoze:{0}:{1:.4f}:{2:.4f}".format(
        provider.name, location.latitude, location.longitude
    )


def scrub(text, secrets):
    """Izbaci kljuceve iz poruke greske prije nego zavrsi u dnevniku."""
    ocisceno = str(text)
    for tajna in secrets:
        if tajna:
            ocisceno = ocisceno.replace(tajna, "***")
    return ocisceno


def _fetch_one(provider, location):
    """Rezultat jednog izvora. Moze biti jedna prognoza ili popis njih."""
    key = _cache_key(provider, location)
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        forecast = provider.fetch(location)
    except Exception as error:  # namjerno siroko: jedan izvor ne rusi ostale
        poruka = scrub(error, provider.secrets())
        logger.warning("Izvor %s nije uspio: %s", provider.name, poruka)
        return provider.empty_result(poruka)

    cache.set(key, forecast, CACHE_SECONDS)
    return forecast


def collect(location):
    """Dohvati sve dostupne izvore paralelno. Vraca listu ProviderForecast."""
    providers = [p for p in all_providers() if p.available()]
    if not providers:
        return []

    with ThreadPoolExecutor(max_workers=len(providers)) as pool:
        rezultati = pool.map(lambda p: _fetch_one(p, location), providers)

    # Open-Meteo vraca sest prognoza iz jednog zahtjeva, ostali po jednu.
    forecasts = []
    for rezultat in rezultati:
        if isinstance(rezultat, list):
            forecasts.extend(rezultat)
        else:
            forecasts.append(rezultat)
    return forecasts
