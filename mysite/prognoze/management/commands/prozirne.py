"""Napravi prozirne inacice slikica, za tamnu temu.

Slikice su crtane na cistoj bijeloj podlozi, bez prozirnosti. Na svijetloj
stranici se to ne vidi, ali na tamnoj svaka postane bijeli kvadratic. Zato
uz svaku stoji i inacica bez pozadine, u `static/prozirno/`.

Izvorne slikice se ne diraju - iz njih se samo cita.

Pozadina se mice poplavom s ruba, a ne "izbaci sve bijelo": bjelina unutar
crteza (trbuh oblaka) je zatvorena obrisom, pa je poplava ne dosegne i
ostaje. Rub se omeksa po tome koliko je pixel blizu bijeloj, inace crtez
ostane nazubljen.

Zatim se **posvjetljuje pretamno mastilo**. Ove slikice idu samo na tamnu
temu, a na njoj se crni obrisi (kisobran, strelice vjetra) i tamnoplave
kapi gube - kap `#023e94` ima prema plocici omjer 1.1:1, sto znaci da je
prakticki nema. Dize se samo ono ispod praga, i to po svjetlini: ton i
zasicenost ostaju, pa kap ostane plava a oblak siv. Svjetliji dijelovi
(trbuh oblaka, plavo platno kisobrana) se ne diraju.

Pokretanje (treba Pillow, koji nije nuzan za rad stranice):

    python manage.py prozirne

Nove se slikice tako dodaju samo u `static/`, pa se pokrene naredba.
"""

import colorsys
from collections import deque

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

# Od koliko se pixel broji kao pozadina, i do koliko se rub omeksava.
BIJELA = 250
RUB = 200

# Mastilo tamnije od PRAG_SVJETLINE dize se na POD_SVJETLINE (0 = crno,
# 1 = bijelo). Prag je ispod svjetline oblaka (0.50) i plavog platna
# kisobrana (0.59), pa njih ostavlja na miru.
PRAG_SVJETLINE = 0.42
POD_SVJETLINE = 0.72

MAPA = "prozirno"

# Ikone pocetnog zaslona ostaju neprozirne: iOS prozirnost ne podrzava i
# podmece crno, pa bi ikona na zaslonu postala crni kvadrat.
PRESKOCI = {"apple-touch-icon.png", "icon-192.png", "icon-512.png"}


def bez_pozadine(image):
    """Kopija slike s uklonjenom bijelom pozadinom."""
    image = image.convert("RGBA")
    w, h = image.size
    px = image.load()

    pozadina = bytearray(w * h)
    red = deque()
    for x in range(w):
        red.append((x, 0))
        red.append((x, h - 1))
    for y in range(h):
        red.append((0, y))
        red.append((w - 1, y))

    while red:
        x, y = red.popleft()
        if x < 0 or y < 0 or x >= w or y >= h or pozadina[y * w + x]:
            continue
        r, g, b, _a = px[x, y]
        if min(r, g, b) < BIJELA:
            continue
        pozadina[y * w + x] = 1
        red.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))

    raspon = float(BIJELA - RUB)
    for y in range(h):
        for x in range(w):
            if pozadina[y * w + x]:
                px[x, y] = (255, 255, 255, 0)
                continue
            uz_rub = any(
                0 <= x + dx < w and 0 <= y + dy < h
                and pozadina[(y + dy) * w + x + dx]
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            )
            if not uz_rub:
                continue
            r, g, b, a = px[x, y]
            najtamniji = min(r, g, b)
            if najtamniji <= RUB:
                continue
            udio = (BIJELA - najtamniji) / raspon
            px[x, y] = (r, g, b, int(round(a * max(0.0, min(1.0, udio)))))

    return image


def posvijetli_mastilo(image):
    """Dize pretamno mastilo, da se vidi na tamnoj podlozi.

    Mijenja se samo svjetlina, i samo onima ispod praga - ton i zasicenost
    ostaju, pa kisa ostane plava a strelica siva. Prozirni se pixeli
    preskacu: njih se ionako ne vidi.
    """
    w, h = image.size
    px = image.load()

    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if not a:
                continue
            ton, svjetlina, zasicenost = colorsys.rgb_to_hls(
                r / 255.0, g / 255.0, b / 255.0
            )
            if svjetlina >= PRAG_SVJETLINE:
                continue
            r, g, b = colorsys.hls_to_rgb(ton, POD_SVJETLINE, zasicenost)
            px[x, y] = (
                int(round(r * 255)), int(round(g * 255)), int(round(b * 255)), a
            )

    return image


class Command(BaseCommand):
    help = "Napravi prozirne inacice slikica u static/prozirno/"

    def handle(self, *args, **options):
        try:
            from PIL import Image
        except ImportError:
            raise CommandError(
                "Treba Pillow: python -m pip install Pillow. "
                "Stranica ga ne treba za rad, samo ova naredba."
            )

        izvor = settings.STATICFILES_DIRS[0]
        odrediste = izvor / MAPA
        odrediste.mkdir(exist_ok=True)

        napravljeno = 0
        for put in sorted(izvor.glob("*.png")):
            if put.name in PRESKOCI:
                continue
            slikica = posvijetli_mastilo(bez_pozadine(Image.open(put)))
            slikica.save(odrediste / put.name)
            napravljeno += 1
            self.stdout.write("  {0}".format(put.name))

        self.stdout.write(
            self.style.SUCCESS("Gotovo: {0} slikica u {1}/".format(napravljeno, MAPA))
        )
