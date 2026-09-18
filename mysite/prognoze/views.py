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

    # Sto preglednik pamti: zadnji grad koji je covjek sam trazio, i je li
    # tocna lokacija ukljucena ili iskljucena. Oboje zivi u istom kolacicu.
    cookie = request.COOKIES.get(geocode.COOKIE_NAME)
    remembered = geocode.from_cookie(cookie)
    gps = geocode.gps_from_cookie(cookie)
    # Veza "Iskljuci tocnu lokaciju". Vrijedi vec za ovaj zahtjev, ne tek
    # od kolacica koji ce se sad zapisati - inace bi se bas ova stranica
    # jos jednom sama dohvatila.
    turn_off = request.GET.get("tocno") == "ne"
    if turn_off:
        gps = geocode.GPS_OFF

    location = geocode.resolve(
        query=query,
        latitude=request.GET.get("lat"),
        longitude=request.GET.get("lon"),
        # Ime i zona stizu samo kad je grad odabran iz prijedloga.
        name=request.GET.get("name"),
        tz=request.GET.get("tz"),
        remembered=remembered,
        ip=client_ip(request),
    )
    precise = location.source == geocode.BY_PRECISE

    # Smije li se lokacija dohvatiti sama od sebe (uz vec dano dopustenje)?
    # Da ako je covjek ukljucio tocnu lokaciju; ne ako ju je iskljucio;
    # inace samo kad nema niceg boljeg - zapamcen grad je bolji, covjek ga
    # je sam izabrao, pa ga GPS ne smije pregaziti bez pitanja.
    auto_locate = (
        (gps == geocode.GPS_ON and location.source == geocode.BY_REMEMBERED)
        or (
            gps != geocode.GPS_OFF
            and location.source in (geocode.BY_IP, geocode.BY_DEFAULT)
        )
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
            # Nazivi dijelova dana za zaglavlje popisa na uskom zaslonu.
            "dijelovi_dana": aggregate.DAY_PARTS,
            # Prekidac za tocnu lokaciju je uvijek tu: dok je ukljucena,
            # veza koja je gasi; inace gumb koji je pali - i kad je grad
            # upisan, da se uvijek moze vratiti na "gdje jesam".
            "tocno_ukljuceno": precise,
            "moze_tocnije": not precise,
            "auto_lokacija": auto_locate,
            # Je li ju covjek sam ukljucio? Onda se trazi odmah, i uz
            # pitanje preglednika ako ga on postavlja svaki put (Safari na
            # iPhoneu) - to je pristao kad ju je ukljucio. Ne na stranici
            # upisanog grada: tamo je upravo rekao da hoce taj grad.
            "tocno_zeljeno": gps == geocode.GPS_ON and auto_locate,
            # Ako bas nijedan izvor nije prosao, reci to umjesto praznih polja.
            "nema_podataka": data.used_sources == 0,
        },
    )

    # Sto se pamti za sljedeci put - zadnji izricit izbor pobjeduje:
    #  - upisan ili odabran grad se pamti, a tocna lokacija time gasi;
    #  - ukljucena tocna lokacija se pamti kao zelja, ne kao koordinate:
    #    "gdje jesam" se mijenja, pa se svaki put dohvaca iznova. Grad
    #    ispod ostaje, da se ima kamo vratiti kad se iskljuci;
    #  - iskljucena se pamti isto tako, inace bi se sljedeci posjet opet
    #    sam dohvatio i ne bi se dala iskljuciti.
    if location.source == geocode.BY_QUERY:
        remember = geocode.to_cookie(location)
    elif precise:
        remember = geocode.to_cookie(remembered, gps=geocode.GPS_ON)
    elif turn_off:
        remember = geocode.to_cookie(remembered, gps=geocode.GPS_OFF)
    else:
        remember = None

    if remember is not None:
        response.set_cookie(
            geocode.COOKIE_NAME,
            remember,
            max_age=geocode.COOKIE_MAX_AGE,
            samesite="Lax",
            httponly=True,
        )

    return response
