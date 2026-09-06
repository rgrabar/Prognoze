"""Prikaz usrednjene prognoze.

Pogled je namjerno tanak: odredi mjesto, pokupi izvore, usrednji, renderaj.
Sva logika je u `geocode`, `providers`, `aggregate` i `air`.
"""

from concurrent.futures import ThreadPoolExecutor

from django.shortcuts import render

from . import aggregate, air, geocode, providers


def client_ip(request):
    """IP posjetitelja.

    Iza proxyja stvarna adresa dolazi u X-Forwarded-For, kao popis u kojem
    je prva stavka klijent. Taj se header da krivotvoriti, pa mu se smije
    vjerovati samo ako je proxy tvoj i sam ga postavlja; ovdje sluzi za
    priblizno mjesto, gdje kriva pretpostavka znaci samo krivi grad.
    """
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def op(request):
    query = request.GET.get("q", "")

    location = geocode.resolve(
        query=query,
        latitude=request.GET.get("lat"),
        longitude=request.GET.get("lon"),
        ip=client_ip(request),
    )

    # Zrak je zaseban API, pa ide usporedo s prognozom umjesto da ceka red.
    with ThreadPoolExecutor(max_workers=2) as pool:
        forecasts_task = pool.submit(providers.collect, location)
        air_task = pool.submit(air.quality_for, location)
        forecasts = forecasts_task.result()
        quality = air_task.result()

    data = aggregate.build(location, forecasts)

    return render(
        request,
        "prognoza.html",
        {
            "query": query,
            "prognoza": data,
            "zrak": quality,
            # Granice raspona za suncanje - da tekst i kod ne razilaze.
            "tan_min": aggregate.TAN_MIN_UV,
            "tan_max": aggregate.TAN_MAX_UV,
            # Preglednik nudi tocnu lokaciju samo ako mjesto nije vec
            # izricito upisano ili dobiveno iz koordinata.
            "moze_tocnije": location.source in (geocode.BY_IP, geocode.BY_DEFAULT),
            # Ako bas nijedan izvor nije prosao, reci to umjesto praznih polja.
            "nema_podataka": data.used_sources == 0,
        },
    )
