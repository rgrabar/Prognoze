# Prognoze

Uzme prognozu s vise izvora, usrednji ih i prikaze kao jednu.
Zadano mjesto je Rijeka, ali radi za bilo koji grad (`?q=Split`).

## Izvori

Devet od jedanaest izvora ne trazi nikakav kljuc ni registraciju:

| Izvor | Kljuc | Centar / napomena |
|---|---|---|
| Open-Meteo (best match) | ne | za Europu je to DWD ICON |
| NOAA GFS (preko Open-Meteo) | ne | SAD |
| Meteo-France ARPEGE (preko Open-Meteo) | ne | Francuska |
| ECMWF IFS (preko Open-Meteo) | ne | Europa, oznaka `ecmwf_ifs025` |
| UK Met Office (preko Open-Meteo) | ne | Britanija; nema vjerojatnost kise |
| Environment Canada GEM (preko Open-Meteo) | ne | Kanada |
| MET Norway | ne | trazi posten `User-Agent` |
| wttr.in | ne | korak od 3 sata |
| 7Timer! | ne | korak od 3 sata, GFS |
| Tomorrow.io | da | vlastiti model i sateliti |
| WeatherAPI.com | da | preskace se ako kljuc nije postavljen |

Dakle sest neovisnih centara: DWD, NOAA, Meteo-France, ECMWF, UKMO i CMC.

**GEM ne glasa o vjerojatnosti oborine.** Za vedar rujanski dan u Rijeci
javljao je 71% vjerojatnosti kise, a istovremeno 0.0 mm oborine, kod 0
(vedro) i 8% naoblake - dakle sam sebi proturjecan. Vjerojatno je racunata
iz rasapa ansambla, pa mjeri "ima li ikakvog traga" umjesto stvarne sanse
za kisu. Uprosjecena s ostalima dizala je 2% na 19%. Temperatura, stanje i
vjetar su mu u redu, pa o tome i dalje glasa.

To je isti obrazac kao kod met.no-ovog UV-a za vedro nebo i kod americkog
AQI-ja: **broj koji se zove isto, a mjeri nesto drugo, ne smije u prosjek.**

Open-Meteo nudi jos modela, ali tri su namjerno izostavljena:

* `icon_seamless` - za Rijeku vraca **doslovno iste brojke** kao
  `best_match` (provjereno, 24 od 24 sata), pa bi DWD glasao dvaput;
* `metno_seamless` - MET Norway se vec zove izravno;
* `ecmwf_ifs04` - stara oznaka, odgovara sa 200 ali su sve vrijednosti
  `null`; izgledala bi kao da radi, a ne bi donijela nista.

Ako neki izvor padne ili mu istekne kljuc, prosjek se racuna iz preostalih.

### Zasto NASA POWER nije unutra

Isproban pa izbacen, iz dva razloga:

* **Nije prognoza.** To je MERRA-2 reanaliza, dakle obrada vec izmjerenog
  stanja, i kasni. Na upit do danasnjeg datuma zadnji stvarni podatak bio
  je od prije tri dana, ostatak je stigao kao `-999`.
* **Mreza mu je pregruba za Rijeku.** POWER vrati i nadmorsku visinu
  celije koju je upotrijebio: za Rijeku **666 m**, iako je grad na moru -
  celija je puna Gorskog kotara. Zato mu je rujanska normala 14 C umjesto
  stvarnih ~20 C. (Za Split, celija na 212 m, pogodi 20.6 C.)

### Sto je vazno kod dodavanja izvora

Isproban je i Pirate Weather pa izbacen: racuna iz NOAA GFS-a, dakle iz
istog modela kao vec postojeci "NOAA GFS (Open-Meteo)". Njihova je obrada
drugacija pa brojke nisu iste, ali to nije novo misljenje - samo bi dalo
GFS-u dvostruku tezinu u prosjeku. Kod usrednjavanja je vazno **koliko je
izvora neovisno**, a ne koliko ih ima.

Ista logika stoji iza toga sto Open-Meteo UV daje samo jednom (vidi nize)
i sto met.no ne glasa o UV-u.

### Tomorrow.io

Jedini izvor s kljucem koji **vrti vlastiti model** i ima vlastite
satelite, pa nije jos jedno pakiranje GFS-a ili ECMWF-a.

Zamka: `windSpeed` je uz `units=metric` u **m/s**, ne km/h. Bez pretvorbe
bi vjetar od 12 km/h u prosjek usao kao 3.4 km/h.

Koristi se samo `forecast`, a trenutno stanje se racuna iz satnog niza -
dakle jedan zahtjev umjesto dva, jer besplatni plan dopusta 25 na sat.

### Kljucevi nikad ne zavrsavaju u dnevniku

Kljucevi putuju u URL-u, pa ih poruka greske sadrzi cim zahtjev pukne - a
ta poruka ide u dnevnik. Izvor s kljucem zato u `secrets()` vrati svoj
kljuc, a `providers.scrub()` ga prije biljezenja zamijeni sa `***`.

### Dvije zamke kod 7Timera

* `wind10m.speed` **nije km/h** nego razred 1-8. Razred 3 je oko 20 km/h,
  ne 3 km/h - bez pretvorbe bi prosjek vjetra bio besmislen.
* `rh2m` stize kao tekst (`"73%"`), a u drugom njihovom proizvodu kao
  indeks -4..4, pa se prihvaca samo ako ispadne smislen postotak.

Niz je 3-satni, pa se trenutno stanje interpolira izmedu dva termina -
uzimanje najblizeg promasi i do sat i pol, sto navecer vrijedi par
stupnjeva.

## Pokretanje

```bash
pip install -r requirements.txt
cd mysite
python manage.py runserver
```

Stranica je na http://127.0.0.1:8000/prognoze/

Provjera izvora iz terminala, bez servera:

```bash
python openMetro.py Rijeka
```

Testovi:

```bash
cd mysite
python manage.py test prognoze
```

## Odredivanje mjesta

Mjesto se odreduje samo, redom od najpouzdanijeg prema najgrubljem:

| # | Nacin | Kad se koristi | Tocnost |
|---|---|---|---|
| 1 | `?q=Split` | covjek je sam upisao | tocno |
| 2 | `?lat=&lon=` | tocna lokacija iz preglednika, uz dopustenje | vrlo tocno |
| 3 | IP adresa | automatski, bez pitanja | otprilike grad |
| 4 | Rijeka | ako nista od navedenog ne uspije | - |

Na stranici uvijek pise koji je nacin upotrijebljen.

**Prijedlozi dok se tipka.** Trazilica nudi gradove iz istog Open-Meteo
geocodinga, ali zvanog izravno iz preglednika - tako ne trosi kvotu
posluzitelja. Njihova trazilica vraca i smece (zracne luke, mjesta bez
stanovnika: za "split" i "Split Rock" i "Splitlog"), pa se rezultati
prosijavaju na naseljena mjesta sa stanovnicima i preslaguju: prvo ona
koja pocinju upisanim slovima, zatim po broju stanovnika. Bez toga se za
"rij" Rijeka nije ni pojavila medu prvih pet.

Odabir salje **koordinate i ime** (`?lat=&lon=&name=`), a ne `?q=`. Tako
se dobije bas ono mjesto koje je covjek odabrao - `?q=London` uvijek vodi
u Englesku, dok odabir iz popisa moze biti i London u Ontariju. Ime se
salje sa sobom pa nema potrebe za obrnutim geokodiranjem.

**Preglednik ne pitamo sami od sebe.** Ako je dopustenje vec dano, lokacija
se dohvati i stranica se osvjezi bez pitanja. Ako nije, pojavi se gumb
"Tocna lokacija" pa neka covjek odluci. Ako je odbijeno, gumba nema.

**IP se salje vanjskoj usluzi.** Za korak 3 posjetiteljeva IP adresa ide na
`ipinfo.io` (besplatno, bez kljuca). Lokalne adrese se preskacu, pa u
razvoju ovaj korak nikad ne radi - klijent je `127.0.0.1` i odmah se pada
na Rijeku. Cijeli se korak gasi s `PROGNOZE_IP_LOOKUP=0`.

Iza proxyja se cita `X-Forwarded-For`. Taj se header da krivotvoriti, pa mu
vjeruj samo ako je proxy tvoj; ovdje najgore sto se dogodi je krivi grad.

## Varijable okoline

Sve su neobavezne - bez ijedne radi u razvoju, sa sest besplatnih izvora.

| Varijabla | Cemu sluzi |
|---|---|
| `WEATHERAPI_KEY` | kljuc za WeatherAPI.com; bez njega se taj izvor preskace |
| `TOMORROW_KEY` | kljuc za Tomorrow.io; bez njega se taj izvor preskace |
| `MET_NO_USER_AGENT` | kontakt za met.no, npr. `Prognoze/1.0 (ja@primjer.hr)` |
| `PROGNOZE_IP_LOOKUP` | `0` gasi odredivanje mjesta po IP adresi |
| `PROGNOZE_DISABLED_SOURCES` | izvori koje ne treba zvati, odvojeni zarezom (npr. `wttr,seven_timer`) |
| `DJANGO_SECRET_KEY` | obavezno postaviti izvan razvoja |
| `DJANGO_DEBUG` | `0` gasi debug |
| `DJANGO_ALLOWED_HOSTS` | popis domena odvojen zarezom |

## Hosting na PythonAnywhereu (besplatni plan)

Besplatni plan pusta prema van samo na popis dopustenih domena
(https://www.pythonanywhere.com/whitelist/). Od svega sto ovaj projekt
zove, **cetiri domene nisu na njemu**, pa su zamijenjene ili se gase:

| Sto | Domena | Rjesenje |
|---|---|---|
| mjesto po IP-u | `ipwho.is` | zamijenjeno s `ipinfo.io` (na popisu, bez kljuca, daje i zonu) |
| ime za GPS koordinate | `api.bigdatacloud.net` | zamijenjeno s `nominatim.openstreetmap.org` (na popisu) |
| izvor prognoze | `wttr.in` | nema zamjene - iskljuci ga |
| izvor prognoze | `www.7timer.info` | nema zamjene - iskljuci ga |

Sve ostalo (Open-Meteo sa svim poddomenama, met.no, Tomorrow.io,
WeatherAPI) je na popisu. Bez ta dva izvora ostaje ih **devet**.

Postavke za PythonAnywhere:

```
DJANGO_DEBUG=0
DJANGO_SECRET_KEY=<dugacak nasumican niz>
DJANGO_ALLOWED_HOSTS=<korisnik>.pythonanywhere.com
PROGNOZE_DISABLED_SOURCES=wttr,seven_timer
WEATHERAPI_KEY=...
TOMORROW_KEY=...
```

PythonAnywhere ne prenosi varijable iz kartice Web u aplikaciju sam od
sebe - najjednostavnije ih je postaviti na vrhu WSGI datoteke
(`os.environ["DJANGO_DEBUG"] = "0"` itd.), prije nego se Django ucita.

Staticne datoteke: uz `DEBUG=0` Django ih ne posluzuje. Pokreni

```bash
python manage.py collectstatic
```

pa u kartici Web pod "Static files" mapiraj URL `/static/` na mapu
`.../mysite/staticfiles`.

Jos dvije stvari koje na PythonAnywhereu rade *bolje* nego lokalno:
stranica je na HTTPS-u, pa gumb "Tocna lokacija" (geolokacija u
pregledniku) ondje radi; i posjetitelji dolaze s javnim IP adresama preko
`X-Forwarded-For`, pa mjesto po IP-u ondje stvarno pogada grad.

## Kako radi usrednjavanje

Brojevi (temperatura, vjetar, vlaga, vjerojatnost kise) idu na obican
prosjek, uz preskakanje izvora koji to polje ne daju.

Stanje neba se ne moze zbrajati - Open-Meteo koristi WMO kodove, WeatherAPI
i wttr.in svoje brojeve, met.no tekst. Svi se prvo prevode u zajednicki
`Condition` (`prognoze/conditions.py`), pa se glasa: pobjeduje ono sto je
najvise izvora reklo, a kod neodlucenog ozbiljnije stanje.

Smjer vjetra ide vektorski, jer je obican prosjek 350 i 10 stupnjeva jug,
a tocan odgovor je sjever.

Vremena su svugdje svedena na UTC prije usporedivanja, jer izvori vracaju
razlicite zone - inace se satnice ne poklapaju.

Odgovori se spremaju u cache 10 minuta i dohvacaju paralelno.

### Brzina ucitavanja

Novi grad znaci upit prema desetak usluga. Izmjereno na stranici:

| | trajanje |
|---|---|
| upisan grad (`?q=`) | ~1.9 s |
| odabran iz prijedloga | ~1.4 s |
| ponovni posjet (iz cachea) | ~0.01 s |

Prije je oboje trajalo oko 2.7 s. Razlika je u tome sto se **pomak
vremenske zone vise ne trazi preko mreze**: geocoding, ipinfo.io i
prijedlozi u pregledniku svi vec vrate naziv zone (`Europe/Zagreb`), pa ga
`offset_from_timezone` pretvori u pomak preko `zoneinfo`. Taj je upit bio
cistih 430 ms cekanja, i to serijski, prije nego bi ijedan izvor krenuo.
`utc_offset_for` je ostao samo kao rezerva.

Ostatak je cekanje na najsporiji izvor, sto se paralelizmom vise ne da
skratiti - zato traka na vrhu pokazuje da se nesto dogada.

### Svih sest Open-Meteo modela u jednom zahtjevu

`models=a,b,c` vraca sve modele u jednom odgovoru, s oznakom modela kao
nastavkom na naziv polja (`temperature_2m_ukmo_seamless`). Prije je svaki
model bio zaseban poziv, pa je jedno ucitavanje stranice znacilo **11**
HTTP zahtjeva; sada ih je **6**, od cega samo 2 prema Open-Meteou. Uz sest
modela to je pocelo vracati 429 i nasumicno gubiti po jedan izvor.

Jedna posljedica: uz vise modela Open-Meteo **ne razdvaja `current` po
modelu** - vrati samo jedan blok. Zato se trenutno stanje svakog modela
racuna iz njegovog satnog niza, interpolacijom izmedu dva termina (isto
kao kod 7Timera). Brojke se zato razlikuju za koju desetinku od onoga sto
je `current` prije davao.

Ako zajednicki zahtjev padne, padnu svi modeli odjednom - ali se svaki i
dalje pojavi u popisu izvora kao nedostupan, umjesto da ih sest nestane.

## Traka po satima

Traka je pomicni prozor oko sadasnjeg trenutka: **8 sati unatrag i 16
unaprijed**, a ne kalendarski dan od ponoci - navecer bi taj dan bio
uglavnom proslost. Prosli sati stoje blijedi, sadasnji je uokviren, a gdje
prozor prijede ponoc povuce se crta.

Sirina prozora je u `PAST_HOURS` i `FUTURE_HOURS` (`aggregate.py`).

Ispod trake (i ispod UV grafa) stoji redak s opisom sata. Na racunalu se
puni prelaskom misem, na mobitelu dodirom - jer dodir nema "hover", pa se
`title` ondje nikad ne bi vidio. Bez ikakvog dodira pise trenutni sat.
Odabir dodirom ostaje, a kad mis ode s trake redak se vraca na trenutni sat.

`title` namjerno ostaje u HTML-u: ako JavaScript ne radi, na racunalu se
opis i dalje vidi kao obicni oblacic.

### Sutra po satima

Ispod danasnje trake stoji i sutrasnja - svih 24 sata - ali **sklopljena**
dok je se ne otvori, da ne udvostruci visinu stranice onima koje zanima
samo danas. Sklapanje radi preko `<details>`, dakle bez JavaScripta, i u
sazetku pise stanje i raspon temperature pa se vidi i zatvorena.

Podaci za nju se ionako racunaju za popis dana sa strane - samo se vise ne
bacaju. Ne kosta nijedan dodatni zahtjev.

Obje trake dijele isti predlozak (`_traka.html`), pa se opis sata na dodir
i sve ostalo ponasa jednako. Sutra nema "trenutnog" ni "proslog" sata.

`min` i `max` se i dalje racunaju za **danasnji kalendarski dan**, zasebno
od prozora - inace bi "najvisa danas" znacila nesto drugo nego sto pise.

## UV graf

Stupci po satima za **danasnji kalendarski dan** (ne za pomicni prozor -
UV je krivulja jednog dana, s vrhuncem oko podneva). Boje su sluzbeni
razredi WHO-a, i to je jedino mjesto gdje boja nesto znaci: u traci po
satima znacenje nosi slikica.

| UV | Razred | Boja |
|---|---|---|
| 0-2 | nizak | zelena |
| 3-5 | umjeren | zuta |
| 6-7 | visok | narancasta |
| 8-10 | vrlo visok | crvena |
| 11+ | ekstreman | ljubicasta |

Razred se odreduje po zaokruzenoj vrijednosti, kako je i uobicajeno - zato
UV 5.6 vec pise "visok", a 5.2 jos "umjeren".

Graf pokriva samo dio dana u kojem UV moze biti veci od nule - nocu je
svugdje nula pa bi pola grafa bila ravna crta. Raspon se vadi iz samih
podataka (prvi i zadnji sat s UV-om, plus sat rezerve sa svake strane), pa
se sam prilagodi godisnjem dobu i zemljopisnoj sirini umjesto da bude
zalijepljen na 06-21. Bez UV podataka pada na `UV_WINDOW_FALLBACK`.

Ljestvica grafa ide do najveceg UV-a toga dana, ali nikad ispod
`UV_MIN_SCALE` (3) - inace bi zimski dan s UV 1 izgledao kao ljetni.

Graf je krivulja, a ne stupci. Boja se zato ne moze mijenjati po satu, pa
ispuna ima okomiti gradijent po istim razredima: sto krivulja vise ide, to
prolazi kroz jaci razred. Preko grafa lezi prozirna mreza od 24 polja, samo
zato da svaki sat ima svoj opis pri prelasku misem.

Desno od grafa stoje izlazak i zalazak sunca te trajanje dana. Taj se
podatak ionako vec dohvaca (za odabir sunca ili mjeseca u traci), a uz UV
ide prirodno - krivulja pocinje na izlasku i zavrsava na zalasku.

Trenutni UV stoji i kao broj u gornjoj kartici, uz naziv razreda.

## Kakvoca zraka

Ispod UV-a u gornjoj kartici stoji europski indeks kakvoce zraka (EEA),
iz Open-Meteo Air Quality APIja - besplatno i bez kljuca. Prelaskom misem
pisu i koncentracije PM2.5 i PM10.

Ovdje se **nista ne usrednjava**: od besplatnih izvora bez kljuca ovaj
jedini daje indeks. WeatherAPI daje americki US AQI, ali to je druga
ljestvica pa bi mijesanje bilo besmisleno - isto kao sto met.no-ov UV za
vedro nebo nije isto sto i obicni UV.

| AQI | Razred |
|---|---|
| 0-20 | dobra |
| 20-40 | zadovoljavajuca |
| 40-60 | umjerena |
| 60-80 | losa |
| 80-100 | vrlo losa |
| 100+ | izuzetno losa |

### Sati za suncanje

Ispod grafa pise u kojim je satima UV izmedu `TAN_MIN_UV` (3) i
`TAN_MAX_UV` (6): ispod 3 koza tamni vrlo sporo, iznad 6 opekline dolaze
brzo. Na jakom ljetnom danu to samo od sebe izbaci podne i ostavi jutro i
kasno poslijepodne.

I ovdje se gleda zaokruzena vrijednost. Bez toga se razmak lomi na
komadice kad UV oscilira oko granice - u Quitu je zbog popodnevnih oblaka
ispadalo "09:00-10:00, 13:00-14:00 i 15:00-16:00" jer je jedan sat imao
2.9 umjesto 3.0.

UV daju samo neki izvori:

* **Open-Meteo** - da, ali se trazi samo od `best_match` modela. Open-Meteo
  UV racuna iz istog izvora bez obzira na model, pa `gfs_seamless` vrati
  doslovno iste brojke; da i on glasa, Open-Meteo bi u prosjeku UV-a
  vrijedio dvostruko. `meteofrance_seamless` UV uopce nema.
* **wttr.in** - da, u koracima od 3 sata.
* **WeatherAPI.com** - da, ako je kljuc postavljen.
* **MET Norway** - ima samo `ultraviolet_index_clear_sky`, dakle UV *za
  vedro nebo*. To je druga velicina i pod oblacima je previsoka, pa se
  namjerno ne mijesa u prosjek.
* **7Timer!** - nema UV.

## Sljedeci dani

Desno od UV grafa stoji kratka prognoza za `FORECAST_DAYS` (4) dana: jedna
slikica po danu, uz najvisu i najnizu temperaturu. **Danas nije medu njima**
- vec stoji u gornjoj kartici i u traci po satima, pa bi se samo ponavljao.
Danasnji se sati i dalje racunaju, jer o njima ovise UV graf i min/max.

Slikica pokazuje **ono sto je za taj dan najvaznije**, a ne ono cega je
najvise:

* **Oborina pobjeduje cim se pojavi u ijednom satu**, i to najjaca. Kisa
  je vijest makar padala jedan sat, dok vedrina koja traje ostatak dana
  nije. Grmljavina nadjacava kisu, kisa rosulju.
* **Ako oborine nema**, dan opisuje stanje neba kojeg je najvise. Jedan
  oblacan sat ne cini dan oblacnim - za razliku od kise, naoblaka je
  stanje, a ne dogadaj. Iz istog razloga ni magla nije dogadaj.

Popis stanja koja se broje kao dogadaj je u `PRECIPITATION`
(`aggregate.py`).

Zadnji dani imaju manje izvora: Open-Meteo trazi 6 dana, Tomorrow.io daje
5, met.no i 7Timer jos vise, ali wttr.in i WeatherAPI stanu na 3. Prosjek
preskace one kojih nema, kao i svugdje.

## Milimetri oborine

Uz vjerojatnost kise, opis sata nosi i **kolicinu u mm** (samo kad je ima
- "0.0 mm" na svakom vedrom satu bio bi sum), a dan sa strane zbroj za
cijeli dan. To je usporedivi broj za "koliko jako": 6 mm u satu je pljusak,
0.2 mm rosulja.

Izvori to daju svaki malo drugacije, pa se svodi na mm po satu:

* **wttr.in** daje kolicinu za tro-satni korak - dijeli se s tri, inace
  bi u prosjeku trostruko nadglasao satne izvore;
* **Tomorrow.io** kisu, snijeg i susnjezicu daje odvojeno; snijeg i
  susnjezica ulaze kao tekuci ekvivalent (`...Lwe`), ne kao visina;
* **GEM** ovdje glasa, iako mu je vjerojatnost iskljucena - mm su mu bili
  tocni (0.0 za vedar dan) dok je vjerojatnost bila 71%;
* **7Timer** daje samo razred 0-9, pa ne glasa.

## Slikice

Traka koristi iste slikice iz `static/`, a ne obojane kvadratice.
Sat poslije zalaska sunca dobiva nocnu inacicu (`moon.png`).

Stanja i njihove slikice su u `CONDITION_ICONS` (`conditions.py`). Trenutno
neka stanja dijele istu slikicu jer je nemamo zasebnu:

| Nedostaje | Zasto bi pomoglo |
|---|---|
| `moon_small_cloud.png` | nocna inacica za "pretezno vedro" (sad dijeli `cloud_moon.png` s "djelomicno oblacno") |

### Ikona na pocetnom zaslonu

Za "dodaj na pocetni zaslon" obicni favicon nije dovoljan, pa uz
`umbrella.png` (kartica preglednika) postoje jos tri slike napravljene iz
njega, kvadratne i s bijelom podlogom:

| Datoteka | Za koga | Zasto bas takva |
|---|---|---|
| `apple-touch-icon.png` (180 px) | iOS | iOS ispod prozirnih piksela stavi **crno** - zato bez alfe |
| `icon-192.png`, `icon-512.png` | Android, preko `manifest.json` | Android bez manifesta ne nudi "instaliraj"; kod "maskable" reze u krug, pa kisobran stoji u sredini s rubom |

Podloga je bijela jer i sam `umbrella.png` ima bijelu, neprozirnu pozadinu
(ne prozirnu) - na plavoj bi se vidio bijeli pravokutnik. Ako se kisobran
promijeni, tri ikone treba ponovno generirati; test provjerava da postoje,
da su deklarirane velicine tocne i da iOS ikona nema alfu.

`tornado.png` postoji, ali se **ne koristi**: nijedan izvor ne javlja
tornado. Open-Meteo koristi skraceni skup WMO kodova bez njega, WeatherAPI
i Tomorrow.io ga nemaju u svojim kodovima, met.no i 7Timer takoder. Stanje
za njega bi bilo mrtav kod dok se ne pojavi izvor koji ga daje.

Jacina kise (rosulja, slaba, jaka) se ne razdvaja u zasebna stanja - to
kaze broj milimetara u opisu sata. Vise stanja bi razlomilo glasanje na
sitnije skupine, a sliku ne bi ucinilo jasnijom.

Stanja bez sunca na slikici - kisa, snijeg, susnjezica, magla, oblak,
grmljavina - izgledaju isto danju i nocu, pa im nocna inacica ne treba.

Nova slikica se ubacuje tako da se doda u `CONDITION_ICONS` (ili
`NIGHT_ICONS` za nocnu inacicu) - nista drugo se ne dira.

## Struktura

```
mysite/prognoze/
    conditions.py       prijevod kodova svih APIja u zajednicki rjecnik
    geocode.py          trazenje mjesta i vremenske zone
    aggregate.py        usrednjavanje i glasanje
    providers/          jedan modul po izvoru
    views.py            tanak pogled
```

Novi izvor koji glasa = novi modul u `providers/` s `fetch(location)` koji
vrati `ProviderForecast`, plus red u `all_providers()`. Sva polja smiju
biti `None`; usrednjavanje preskace ono cega nema.
