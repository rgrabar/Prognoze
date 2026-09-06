"""Usrednjavanje vise prognoza u jednu.

Brojevi (temperatura, vjetar, vlaga, vjerojatnost kise) idu na obicni
prosjek. Stanje neba ne moze - ono se glasa: pobjeduje ono koje je najvise
izvora prijavilo, a ako je neodluceno, uzima se ozbiljnije (radije najavi
grmljavinu koje nema nego obrnuto).

Smjer vjetra se isto ne smije zbrajati kao obican broj: prosjek 350 i 10
stupnjeva je 180 (jug), a tocan odgovor je 0 (sjever). Zato ide vektorski.
"""

import math
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from .conditions import Condition, icon_for, label_for, wind_direction

# Traka po satima: koliko unatrag, koliko unaprijed. Zbroj je sirina trake.
PAST_HOURS = 8
FUTURE_HOURS = 16

# Ljestvica UV indeksa po WHO-u: granica, naziv, boja.
UV_BANDS = [
    (2.5, "nizak", "#3ea72d"),
    (5.5, "umjeren", "#d9b800"),
    (7.5, "visok", "#f18b00"),
    (10.5, "vrlo visok", "#e53210"),
    (float("inf"), "ekstreman", "#9b4dca"),
]

# Da graf ne izgleda prazno u zimu, ljestvica ide barem do ovoga.
UV_MIN_SCALE = 3.0

# Raspon UV-a za "najbolje sate za suncanje". Ispod 3 koza tamni jako
# sporo, iznad 6 opekline dolaze brzo - pa ostaje sredina. Na jakom
# ljetnom danu to samo od sebe izbaci podne i ostavi jutro i kasno
# poslijepodne, sto se poklapa s uobicajenim savjetom.
TAN_MIN_UV = 3.0
TAN_MAX_UV = 6.0

# Graf pokriva samo sate u kojima UV moze biti razlicit od nule. Ako
# podataka nema, uzme se ovaj raspon.
UV_WINDOW_FALLBACK = (6, 21)

# Koliko dana ima kratka prognoza sa strane. Danas nije medu njima - stoji
# vec u gornjoj kartici i u traci po satima, pa bi se samo ponavljao.
FORECAST_DAYS = 4

# Stanja koja se broje kao dogadaj: dovoljan je jedan sat da obiljeze dan.
# Naoblaka nije medu njima - jedan oblacan sat ne cini dan oblacnim, dok
# jedan sat kise itekako znaci da ce padati.
PRECIPITATION = {
    Condition.DRIZZLE,
    Condition.RAIN,
    Condition.SLEET,
    Condition.SNOW,
    Condition.THUNDER,
    Condition.THUNDER_HAIL,
}

# Kratice dana u tjednu, po `datetime.weekday()` (ponedjeljak = 0).
WEEKDAYS = ["pon", "uto", "sri", "cet", "pet", "sub", "ned"]


def day_condition(hours):
    """Jedno stanje koje najbolje opisuje cijeli dan.

    Oborina pobjeduje cim se pojavi u ijednom satu, i to najjaca - kisa je
    vijest, makar padala sat vremena, dok vedrina koja traje ostatak dana
    nije. Ako oborine nema, dan opisuje ono stanje neba kojeg je najvise.
    """
    conditions = [h.condition for h in hours if h.condition is not None]
    if not conditions:
        return None

    oborine = [c for c in conditions if c in PRECIPITATION]
    if oborine:
        return max(oborine, key=lambda c: c.severity)

    counts = Counter(conditions)
    top = max(counts.values())
    tied = [c for c, n in counts.items() if n == top]
    return max(tied, key=lambda c: c.severity)


def uv_band(value):
    """UV vrijednost -> (naziv, boja)."""
    if value is None:
        return ("nepoznato", "#c9c9cf")
    for granica, naziv, boja in UV_BANDS:
        if value <= granica:
            return (naziv, boja)
    return UV_BANDS[-1][1:]


def mean(values):
    """Prosjek uz preskakanje None. Vraca None ako nema nicega."""
    numbers = [v for v in values if v is not None]
    if not numbers:
        return None
    return sum(numbers) / len(numbers)


def rounded(value, digits=1):
    if value is None:
        return None
    # Postotke prikazujemo bez decimale ("70%", ne "70.0%").
    if digits == 0:
        return int(round(value))
    return round(value, digits)


def vote(conditions):
    """Vecina odlucuje.

    Kod neodlucenog rezultata pobjeduje ozbiljnije stanje - bolje najaviti
    grmljavinu koje nema nego obrnuto.

    Iznimka je kad se svi izvori razidu i svaki kaze nesto drugo (svi imaju
    po jedan glas). Tada "najozbiljnije" znaci da jedan jedini model koji
    vidi rosulju oboji cijeli sat kisom, pa se uzima sredina po ozbiljnosti
    - reprezentativnija je i traka po satima ne poskakuje.
    """
    votes = [c for c in conditions if c is not None]
    if not votes:
        return None

    counts = Counter(votes)
    top = max(counts.values())
    tied = sorted(
        (c for c, n in counts.items() if n == top),
        key=lambda c: c.severity,
    )

    if top == 1 and len(tied) > 2:
        # Potpuni razlaz: sredina umjesto krajnosti.
        return tied[len(tied) // 2]

    return tied[-1]


def mean_direction(degrees):
    """Kruzni prosjek smjera vjetra."""
    values = [d for d in degrees if d is not None]
    if not values:
        return None
    x = sum(math.cos(math.radians(d)) for d in values)
    y = sum(math.sin(math.radians(d)) for d in values)
    if abs(x) < 1e-9 and abs(y) < 1e-9:
        # Smjerovi se ponistili (npr. tocno suprotni) - nema smislenog prosjeka.
        return None
    return math.degrees(math.atan2(y, x)) % 360


@dataclass
class AggregatedHour:
    hour: int
    label: str
    temp_c: Optional[float] = None
    precip_prob: Optional[float] = None
    condition: Optional[Condition] = None
    uv: Optional[float] = None
    sources: int = 0
    is_now: bool = False
    is_night: bool = False
    is_past: bool = False
    starts_day: bool = False
    # Visina stupca u UV grafu, u postotcima. Popuni se tek kad se zna
    # najveca vrijednost dana.
    uv_pct: float = 0.0

    @property
    def icon(self):
        return icon_for(self.condition, self.is_night)

    @property
    def uv_color(self):
        return uv_band(self.uv)[1]

    @property
    def uv_label(self):
        return uv_band(self.uv)[0]

    @property
    def uv_title(self):
        if self.uv is None:
            return "{0:02d}:00 | UV nepoznat".format(self.hour)
        return "{0:02d}:00 | UV {1} ({2})".format(
            self.hour, self.uv, self.uv_label
        )

    @property
    def condition_label(self):
        return label_for(self.condition)

    @property
    def title(self):
        parts = ["{0:02d}:00".format(self.hour), label_for(self.condition)]
        if self.temp_c is not None:
            parts.append("{0} C".format(round(self.temp_c, 1)))
        if self.precip_prob is not None:
            parts.append("kisa {0}%".format(round(self.precip_prob)))
        parts.append("{0} izvora".format(self.sources))
        return " | ".join(parts)


@dataclass
class DayForecast:
    """Jedan dan u kratkoj prognozi sa strane."""

    label: str
    condition: Optional[Condition] = None
    min_c: Optional[float] = None
    max_c: Optional[float] = None
    precip_hours: int = 0

    @property
    def icon(self):
        # Uvijek dnevna slikica - ovo je sazetak cijelog dana.
        return icon_for(self.condition)

    @property
    def condition_label(self):
        return label_for(self.condition)

    @property
    def title(self):
        parts = [self.label, self.condition_label]
        if self.min_c is not None and self.max_c is not None:
            parts.append("{0} do {1} C".format(self.min_c, self.max_c))
        if self.precip_hours:
            parts.append("oborina {0} h".format(self.precip_hours))
        return " | ".join(parts)


@dataclass
class SourceStatus:
    label: str
    ok: bool
    temp_c: Optional[float] = None
    condition_label: str = ""
    error: str = ""


@dataclass
class Aggregated:
    location: object
    local_now: datetime
    temp_c: Optional[float] = None
    min_c: Optional[float] = None
    max_c: Optional[float] = None
    wind_kph: Optional[float] = None
    wind_dir: Optional[str] = None
    humidity: Optional[float] = None
    precip_prob: Optional[float] = None
    condition: Optional[Condition] = None
    is_night: bool = False
    uv: Optional[float] = None
    sunrise: Optional[datetime] = None
    sunset: Optional[datetime] = None
    hours: List[AggregatedHour] = field(default_factory=list)
    # Cijeli lokalni kalendarski dan, 00:00-23:00. Iz njega idu min/max i
    # UV graf, koji je po naravi krivulja jednog dana.
    day_hours: List[AggregatedHour] = field(default_factory=list)
    days: List[DayForecast] = field(default_factory=list)
    sources: List[SourceStatus] = field(default_factory=list)
    spread_c: Optional[float] = None

    @property
    def uv_max(self):
        vrijednosti = [h.uv for h in self.day_hours if h.uv is not None]
        return max(vrijednosti) if vrijednosti else None

    @property
    def uv_peak_hour(self):
        vrhunac = None
        for hour in self.day_hours:
            if hour.uv is not None and (vrhunac is None or hour.uv > vrhunac.uv):
                vrhunac = hour
        return vrhunac

    @property
    def has_uv(self):
        return self.uv_max is not None

    @property
    def uv_max_label(self):
        return uv_band(self.uv_max)[0]

    @property
    def uv_max_color(self):
        return uv_band(self.uv_max)[1]

    @property
    def uv_label(self):
        return uv_band(self.uv)[0]

    @property
    def uv_color(self):
        return uv_band(self.uv)[1]

    # --- sunce ---

    @property
    def sunrise_label(self):
        return self.sunrise.strftime("%H:%M") if self.sunrise else ""

    @property
    def sunset_label(self):
        return self.sunset.strftime("%H:%M") if self.sunset else ""

    @property
    def day_length_label(self):
        if not (self.sunrise and self.sunset):
            return ""
        minutes = int((self.sunset - self.sunrise).total_seconds() // 60)
        return "{0} h {1} min".format(minutes // 60, minutes % 60)

    # --- UV krivulja ---

    @property
    def uv_scale(self):
        return max(self.uv_max or 0, UV_MIN_SCALE)

    @property
    def uv_hours(self):
        """Samo sati u kojima UV moze biti veci od nule.

        Nocu je UV svugdje nula, pa bi pola grafa bila ravna crta. Raspon
        se vadi iz samih podataka (prvi i zadnji sat s UV-om, plus sat sa
        svake strane), pa se sam prilagodi godisnjem dobu i zemljopisnoj
        sirini umjesto da bude zalijepljen na 06-21.
        """
        if not self.day_hours:
            return []

        aktivni = [i for i, h in enumerate(self.day_hours) if h.uv]
        if aktivni:
            prvi = max(0, min(aktivni) - 1)
            zadnji = min(len(self.day_hours) - 1, max(aktivni) + 1)
        else:
            prvi, zadnji = UV_WINDOW_FALLBACK

        return self.day_hours[prvi : zadnji + 1]

    @property
    def uv_view_width(self):
        """Sirina SVG koordinatnog sustava: 10 jedinica po satu."""
        return max((len(self.uv_hours) - 1) * 10, 10)

    @property
    def uv_line_points(self):
        """Tocke krivulje za SVG. Sat i ide na x = i*10; y je obrnut jer
        SVG racuna od vrha."""
        return " ".join(
            "{0},{1}".format(index * 10, round(100 - hour.uv_pct, 1))
            for index, hour in enumerate(self.uv_hours)
            if hour.uv is not None
        )

    @property
    def uv_area_points(self):
        """Iste tocke, ali zatvorene do dna - za ispunu ispod krivulje."""
        indexes = [
            i for i, h in enumerate(self.uv_hours) if h.uv is not None
        ]
        if not indexes:
            return ""
        return "{0},100 {1} {2},100".format(
            indexes[0] * 10, self.uv_line_points, indexes[-1] * 10
        )

    @property
    def uv_gradient_stops(self):
        """Okomiti gradijent ispune, obojen po razredima UV-a.

        Krivulja je jedna linija pa ne moze biti obojena po satu kao sto su
        bili stupci. Umjesto toga se boja ispuna po visini: sto krivulja
        vise ide, to prolazi kroz jaci razred.
        """
        scale = self.uv_scale
        stops = []
        previous = 0.0

        for granica, _naziv, boja in UV_BANDS:
            offset = 1.0 if granica == float("inf") else min(granica / scale, 1.0)
            stops.append((round(previous * 100, 1), boja))
            stops.append((round(offset * 100, 1), boja))
            previous = offset
            if offset >= 1.0:
                break

        return stops

    @property
    def tanning_windows(self):
        """Nizovi uzastopnih sati u kojima je UV izmedu TAN_MIN i TAN_MAX.

        Vraca popis parova (prvi sat, zadnji sat), oboje ukljucivo.
        """
        windows = []
        start = None

        for hour in self.day_hours:
            # Usporeduje se zaokruzeni UV, isto kao kod razreda gore. Inace
            # sat s 2.9 ispadne, a onaj do njega s 3.0 udje, pa se razmak
            # raspadne na komadice zbog jedne desetinke.
            pogodan = (
                hour.uv is not None
                and TAN_MIN_UV <= round(hour.uv) <= TAN_MAX_UV
            )
            if pogodan and start is None:
                start = hour.hour
            elif not pogodan and start is not None:
                windows.append((start, hour.hour - 1))
                start = None

        if start is not None:
            windows.append((start, self.day_hours[-1].hour))

        return windows

    @property
    def tanning_label(self):
        """Sati za suncanje kao tekst, npr. "09:00-12:00 i 16:00-18:00".

        Sat 9 pokriva razdoblje 09:00-10:00, pa kraj ide na zadnji sat + 1.
        """
        windows = self.tanning_windows
        if not windows:
            return ""

        rasponi = [
            "{0:02d}:00-{1:02d}:00".format(start, end + 1)
            for start, end in windows
        ]
        if len(rasponi) == 1:
            return rasponi[0]
        return "{0} i {1}".format(", ".join(rasponi[:-1]), rasponi[-1])

    @property
    def icon(self):
        return icon_for(self.condition, self.is_night)

    @property
    def condition_label(self):
        return label_for(self.condition)

    @property
    def used_sources(self):
        return sum(1 for s in self.sources if s.ok)

    @property
    def local_time_label(self):
        # Formatira se ovdje, a ne u predlosku: Djangov `date` filter bi
        # aware vrijeme pretvorio natrag u TIME_ZONE projekta (UTC).
        return self.local_now.strftime("%d.%m.%Y. %H:%M")


def _hourly_index(forecast):
    """Satnice jednog izvora, slozene po punom satu u UTC-u."""
    index = {}
    for point in forecast.hours:
        key = point.time.replace(minute=0, second=0, microsecond=0)
        index[key] = point
    return index


def _day_label(moment, offset):
    """Kratka oznaka dana: sutra, pa kratica dana u tjednu."""
    if offset == 1:
        return "sutra"
    return WEEKDAYS[moment.weekday()]


def _bucket(indexes, slot_utc, local_zone, current_hour_utc, sun_times):
    """Jedan sat trake: prosjek svih izvora koji taj sat pokrivaju."""
    points = [
        index[slot_utc] for index in indexes.values() if slot_utc in index
    ]
    slot_local = slot_utc.astimezone(local_zone)

    return AggregatedHour(
        hour=slot_local.hour,
        label="{0:02d}:00".format(slot_local.hour),
        temp_c=rounded(mean([p.temp_c for p in points])),
        precip_prob=rounded(mean([p.precip_prob for p in points]), 0),
        condition=vote([p.condition for p in points]),
        uv=rounded(mean([p.uv for p in points])),
        sources=len(points),
        is_now=slot_utc == current_hour_utc,
        is_night=_is_night(sun_times, slot_utc),
        is_past=slot_utc < current_hour_utc,
        # Ponoc dijeli prozor na dva dana - traka to treba pokazati.
        starts_day=slot_local.hour == 0,
    )


def _sun_times(forecasts):
    """Izlasci i zalasci sunca - daje ih samo jedan izvor, dovoljno je."""
    for forecast in forecasts:
        if forecast.sun_times:
            return forecast.sun_times
    return []


def _is_night(sun_times, moment):
    for sunrise, sunset in sun_times:
        if sunrise.date() == moment.date():
            return moment < sunrise or moment > sunset
    # Bez podatka o suncu radije ostavi dnevnu slikicu.
    return False


def build(location, forecasts, now_utc=None):
    """Spoji sve izvore u jedan rezultat za prikaz."""
    now_utc = now_utc or datetime.now(timezone.utc)
    local_zone = timezone(timedelta(seconds=location.utc_offset_seconds))
    local_now = now_utc.astimezone(local_zone)

    good = [f for f in forecasts if f.ok]
    indexes = {f.name: _hourly_index(f) for f in good}
    sun_times = _sun_times(good)

    current_hour_utc = now_utc.replace(minute=0, second=0, microsecond=0)

    # --- trenutno stanje ---
    temps = []
    for forecast in good:
        if forecast.temp_c is not None:
            temps.append(forecast.temp_c)

    # Neki izvori ne daju vjerojatnost kise "sada" - uzmi njihov trenutni sat.
    probabilities = []
    for forecast in good:
        value = forecast.precip_prob
        if value is None:
            point = indexes[forecast.name].get(current_hour_utc)
            value = point.precip_prob if point else None
        if value is not None:
            probabilities.append(value)

    result = Aggregated(
        location=location,
        local_now=local_now,
        temp_c=rounded(mean(temps)),
        wind_kph=rounded(mean([f.wind_kph for f in good])),
        humidity=rounded(mean([f.humidity for f in good]), 0),
        precip_prob=rounded(mean(probabilities), 0),
        condition=vote([f.condition for f in good]),
        is_night=_is_night(sun_times, now_utc),
        uv=rounded(mean([f.uv for f in good])),
    )
    result.wind_dir = wind_direction(
        mean_direction([f.wind_dir_deg for f in good])
    )
    if len(temps) > 1:
        result.spread_c = rounded(max(temps) - min(temps))

    # --- traka: pomicni prozor oko sadasnjeg trenutka ---
    # Cijeli dan od ponoci navecer je uglavnom proslost, pa nema smisla.
    window_start = current_hour_utc - timedelta(hours=PAST_HOURS)
    for step in range(PAST_HOURS + FUTURE_HOURS):
        slot_utc = window_start + timedelta(hours=step)
        result.hours.append(
            _bucket(indexes, slot_utc, local_zone, current_hour_utc, sun_times)
        )

    # --- kalendarski dani ---
    # Danasnji dan se racuna zasebno od trake gore, jer prozor prelazi u
    # sutra pa bi inace "najvisa danas" znacila nesto drugo nego sto pise.
    # Isti dan koristi i UV graf, a svih pet kratka prognoza sa strane.
    local_midnight = local_now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Dan 0 se racuna zbog UV grafa i min/max, ali se ne prikazuje medu
    # danima sa strane - danas vec pise gore.
    for day in range(FORECAST_DAYS + 1):
        pocetak = local_midnight + timedelta(days=day)
        hours = []
        for hour in range(24):
            slot_utc = (pocetak + timedelta(hours=hour)).astimezone(
                timezone.utc
            ).replace(minute=0, second=0, microsecond=0)
            hours.append(
                _bucket(
                    indexes, slot_utc, local_zone, current_hour_utc, sun_times
                )
            )

        if day == 0:
            result.day_hours = hours
            continue

        temps = [h.temp_c for h in hours if h.temp_c is not None]
        result.days.append(
            DayForecast(
                label=_day_label(pocetak, day),
                condition=day_condition(hours),
                min_c=rounded(min(temps)) if temps else None,
                max_c=rounded(max(temps)) if temps else None,
                precip_hours=sum(
                    1 for h in hours if h.condition in PRECIPITATION
                ),
            )
        )

    # Izlazak i zalazak sunca za danas, u lokalnom vremenu. Podatak se vec
    # dohvaca za odabir sunca/mjeseca, samo se dosad nije prikazivao.
    for sunrise, sunset in sun_times:
        if sunrise.astimezone(local_zone).date() == local_now.date():
            result.sunrise = sunrise.astimezone(local_zone)
            result.sunset = sunset.astimezone(local_zone)
            break

    day_temps = [h.temp_c for h in result.day_hours if h.temp_c is not None]
    if day_temps:
        result.min_c = rounded(min(day_temps))
        result.max_c = rounded(max(day_temps))

    # Visine stupaca u UV grafu. Ljestvica ide do najveceg dnevnog UV-a, ali
    # nikad ispod UV_MIN_SCALE - inace bi zimski dan bio ravna crta.
    uv_max = result.uv_max
    if uv_max is not None:
        scale = max(uv_max, UV_MIN_SCALE)
        for hour in result.day_hours:
            if hour.uv is not None:
                hour.uv_pct = round(hour.uv / scale * 100, 1)

    # --- tko je sto rekao ---
    for forecast in forecasts:
        result.sources.append(
            SourceStatus(
                label=forecast.label,
                ok=forecast.ok,
                temp_c=rounded(forecast.temp_c),
                condition_label=label_for(forecast.condition),
                error=forecast.error or "",
            )
        )

    return result
