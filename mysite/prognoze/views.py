"""Prikaz usrednjene prognoze.

Pogled je namjerno tanak: odredi mjesto, pokupi izvore, usrednji, renderaj.
Sva logika je u `geocode`, `providers`, `aggregate` i `air`.
"""

import os
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.shortcuts import render

from . import aggregate, air, geocode, providers


def css_version():
    """Vrijeme zadnje izmjene stilova, kao broj.

    Ide u URL stilova (`prognoza.css?v=...`), pa preglednik nakon svake
    izmjene povuce novu datoteku umjesto da sluzi staru iz svog cachea.
    Bez toga se izmjena izgleda na mobitelu zna ne vidjeti danima.
    """
    try:
        return int(os.path.getmtime(settings.STATICFILES_DIRS[0] / "prognoza.css"))
    except (OSError, IndexError):
        return 0


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
        # Ime i zona stizu samo kad je grad odabran iz prijedloga.
        name=request.GET.get("name"),
        tz=request.GET.get("tz"),
        # Zadnje mjesto koje je covjek sam trazio, ako ga preglednik pamti.
        remembered=geocode.from_cookie(request.COOKIES.get(geocode.COOKIE_NAME)),
        ip=client_ip(request),
    )

    # Zrak je zaseban API, pa ide usporedo s prognozom umjesto da ceka red.
    with ThreadPoolExecutor(max_workers=2) as pool:
        forecasts_task = pool.submit(providers.collect, location)
        air_task = pool.submit(air.quality_for, location)
        forecasts = forecasts_task.result()
        quality = air_task.result()

    data = aggregate.build(location, forecasts)

    response = render(
        request,
        "prognoza.html",
        {
            "query": query,
            "prognoza": data,
            "zrak": quality,
            "css_v": css_version(),
            # Granice raspona za suncanje - da tekst i kod ne razilaze.
            "tan_min": aggregate.TAN_MIN_UV,
            "tan_max": aggregate.TAN_MAX_UV,
            # Gumb za tocnu lokaciju se nudi kad mjesto nije upisano ni
            # dobiveno iz koordinata - dakle i kad je zapamceno.
            "moze_tocnije": location.source in (
                geocode.BY_IP, geocode.BY_DEFAULT, geocode.BY_REMEMBERED
            ),
            # Ali se lokacija sama od sebe dohvaca (uz vec dano dopustenje)
            # samo kad nema niceg boljeg. Zapamceno mjesto je bolje: covjek
            # ga je sam izabrao, pa ga GPS ne smije pregaziti bez pitanja.
            "auto_lokacija": location.source in (
                geocode.BY_IP, geocode.BY_DEFAULT
            ),
            # Ako bas nijedan izvor nije prosao, reci to umjesto praznih polja.
            "nema_podataka": data.used_sources == 0,
        },
    )

    # Sto se pamti za sljedeci put:
    #  - upisan ili odabran grad se pamti - to je izricita zelja;
    #  - tocna lokacija iz preglednika brise zapamceno: covjek je rekao
    #    "gdje jesam", a to se mijenja, pa se ne smije prikovati.
    if location.source == geocode.BY_QUERY:
        response.set_cookie(
            geocode.COOKIE_NAME,
            geocode.to_cookie(location),
            max_age=geocode.COOKIE_MAX_AGE,
            samesite="Lax",
            httponly=True,
        )
    elif location.source == geocode.BY_PRECISE:
        response.delete_cookie(geocode.COOKIE_NAME, samesite="Lax")

    return response
