"""Testovi za dijelove koji ne diraju mrezu.

Prijevod kodova i usrednjavanje su cista logika, pa se daju testirati bez
ijednog HTTP poziva - a bas tu se najlakse potkrade greska.
"""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase

from . import aggregate, air, providers, views
from .conditions import (
    CONDITION_ICONS,
    NIGHT_ICONS,
    UNKNOWN_ICON,
    Condition,
    _COMPASS,
    compass_to_degrees,
    from_7timer,
    from_met_no,
    from_tomorrow,
    from_weather_api,
    from_wmo,
    from_wwo,
    icon_for,
    seven_timer_wind_kph,
    wind_direction,
)
from . import geocode
from .geocode import Location, is_public_ip, _coordinates
from .providers import open_meteo, tomorrow, weather_api, wttr
from .providers.base import (
    HourPoint,
    ProviderForecast,
    interpolate,
    parse_iso_utc,
)
from .providers.seven_timer import parse_humidity, parse_init


class ConditionMappingTests(SimpleTestCase):
    def test_isto_vrijeme_iz_razlicitih_apija_daje_isto_stanje(self):
        # Umjerena kisa: WMO 63, WeatherAPI 1189, WWO 302, met.no i 7Timer.
        self.assertEqual(from_wmo(63), Condition.RAIN)
        self.assertEqual(from_weather_api(1189), Condition.RAIN)
        self.assertEqual(from_wwo(302), Condition.RAIN)
        self.assertEqual(from_met_no("rain"), Condition.RAIN)
        self.assertEqual(from_7timer("rainday"), Condition.RAIN)

    def test_vedro_iz_razlicitih_apija(self):
        self.assertEqual(from_wmo(0), Condition.CLEAR)
        self.assertEqual(from_weather_api(1000), Condition.CLEAR)
        self.assertEqual(from_wwo(113), Condition.CLEAR)
        self.assertEqual(from_met_no("clearsky_day"), Condition.CLEAR)
        self.assertEqual(from_7timer("clearnight"), Condition.CLEAR)

    def test_met_no_grmljavina_pobjeduje_kisu_u_imenu(self):
        # "rainandthunder" sadrzi i "rain" - mora ispasti grmljavina.
        self.assertEqual(from_met_no("rainandthunder"), Condition.THUNDER)
        self.assertEqual(
            from_met_no("heavysleetandthunder_night"), Condition.THUNDER
        )

    def test_nepoznat_kod_daje_none(self):
        self.assertIsNone(from_wmo(1234))
        self.assertIsNone(from_wmo(None))
        self.assertIsNone(from_weather_api("bezveze"))
        self.assertIsNone(from_met_no(""))

    def test_slikice_ostaju_postojece_datoteke(self):
        self.assertEqual(icon_for(Condition.RAIN), "rain.png")
        self.assertEqual(icon_for(Condition.SNOW), "pahulja.png")
        self.assertEqual(icon_for(None), "neznamovrime.png")

    def test_rosulja_i_kisa_imaju_razlicite_slikice(self):
        # Dva razlicita glasa - od kad postoji drizzle.png vise ne dijele
        # istu sliku.
        self.assertEqual(icon_for(Condition.DRIZZLE), "drizzle.png")
        self.assertNotEqual(
            icon_for(Condition.DRIZZLE), icon_for(Condition.RAIN)
        )

    def test_stanja_sa_suncem_imaju_nocnu_inacicu(self):
        self.assertEqual(icon_for(Condition.CLEAR), "sun.png")
        self.assertEqual(icon_for(Condition.CLEAR, is_night=True), "moon.png")

        self.assertEqual(
            icon_for(Condition.MAINLY_CLEAR), "sun_small_cloud.png"
        )
        self.assertEqual(
            icon_for(Condition.MAINLY_CLEAR, is_night=True), "cloud_moon.png"
        )

        self.assertEqual(icon_for(Condition.PARTLY_CLOUDY), "cloud_sun.png")
        self.assertEqual(
            icon_for(Condition.PARTLY_CLOUDY, is_night=True), "cloud_moon.png"
        )

    def test_stanja_bez_sunca_izgledaju_isto_nocu(self):
        for condition in (
            Condition.OVERCAST,
            Condition.FOG,
            Condition.RAIN,
            Condition.SLEET,
            Condition.SNOW,
            Condition.THUNDER,
            Condition.THUNDER_HAIL,
        ):
            self.assertEqual(
                icon_for(condition),
                icon_for(condition, is_night=True),
                "{0} ne bi trebalo mijenjati slikicu nocu".format(condition),
            )

    def test_pretezno_vedro_i_djelomicno_oblacno_se_razlikuju(self):
        # Dva razlicita glasa ne smiju izgledati isto - bar danju.
        self.assertNotEqual(
            icon_for(Condition.MAINLY_CLEAR),
            icon_for(Condition.PARTLY_CLOUDY),
        )

    def test_svaka_navedena_slikica_stvarno_postoji(self):
        # Tipfeler u imenu datoteke inace se vidi tek kao prazan kvadratic
        # na stranici.
        staticni = Path(settings.STATICFILES_DIRS[0])
        imena = set(CONDITION_ICONS.values()) | set(NIGHT_ICONS.values())
        imena.add(UNKNOWN_ICON)
        # Strane svijeta za vjetar.
        imena.update("{0}.png".format(s) for s in _COMPASS)

        for ime in sorted(imena):
            with self.subTest(slikica=ime):
                self.assertTrue(
                    (staticni / ime).is_file(),
                    "nedostaje static/{0}".format(ime),
                )

    def test_svako_stanje_ima_slikicu(self):
        for condition in Condition:
            self.assertIn(condition, CONDITION_ICONS)


class SevenTimerTests(SimpleTestCase):
    def test_oblacnost_ide_po_stupnjevima(self):
        self.assertEqual(from_7timer("clearday"), Condition.CLEAR)
        self.assertEqual(from_7timer("pcloudyday"), Condition.MAINLY_CLEAR)
        self.assertEqual(from_7timer("mcloudynight"), Condition.PARTLY_CLOUDY)
        self.assertEqual(from_7timer("cloudynight"), Condition.OVERCAST)

    def test_preklapajuca_imena_idu_na_tocno_stanje(self):
        # "tsrain" sadrzi "rain", "rainsnow" sadrzi i "rain" i "snow",
        # a "lightrain" je rosulja - redoslijed pravila mora to razlikovati.
        self.assertEqual(from_7timer("tsrainday"), Condition.THUNDER)
        self.assertEqual(from_7timer("tsday"), Condition.THUNDER)
        self.assertEqual(from_7timer("rainsnowday"), Condition.SLEET)
        self.assertEqual(from_7timer("lightrainday"), Condition.DRIZZLE)
        self.assertEqual(from_7timer("rainday"), Condition.RAIN)
        self.assertEqual(from_7timer("lightsnownight"), Condition.SNOW)

    def test_pljuskovi_i_sumaglica(self):
        self.assertEqual(from_7timer("oshowerday"), Condition.RAIN)
        self.assertEqual(from_7timer("ishowerday"), Condition.RAIN)
        self.assertEqual(from_7timer("humidnight"), Condition.FOG)

    def test_razred_vjetra_nije_kilometri_na_sat(self):
        # Razred 3 je oko 3.4-8.0 m/s, dakle ~20 km/h, a ne 3 km/h.
        self.assertAlmostEqual(seven_timer_wind_kph(2), 6.66, places=2)
        self.assertAlmostEqual(seven_timer_wind_kph(3), 20.52, places=2)
        self.assertGreater(seven_timer_wind_kph(8), 100)
        self.assertIsNone(seven_timer_wind_kph(None))
        self.assertIsNone(seven_timer_wind_kph(99))

    def test_vlaga_dolazi_kao_tekst(self):
        self.assertEqual(parse_humidity("73%"), 73.0)
        self.assertEqual(parse_humidity("0%"), 0.0)
        self.assertIsNone(parse_humidity(None))
        # U drugom proizvodu rh2m je indeks -4..4, a ne postotak.
        self.assertIsNone(parse_humidity(-4))
        self.assertIsNone(parse_humidity("nesto"))

    def test_init_se_cita_kao_utc(self):
        moment = parse_init("2026090212")
        self.assertEqual(moment.year, 2026)
        self.assertEqual(moment.month, 9)
        self.assertEqual(moment.day, 2)
        self.assertEqual(moment.hour, 12)
        self.assertEqual(moment.tzinfo, timezone.utc)
        self.assertIsNone(parse_init("smece"))

    def test_interpolacija_pogada_sredinu_izmedu_termina(self):
        # Korak je 3 sata; u 19:00 smo dvije trecine puta od 18:00 do 21:00.
        hours = [
            HourPoint(
                time=datetime(2026, 9, 2, 18, tzinfo=timezone.utc),
                temp_c=27.0,
                condition=Condition.CLEAR,
                wind_kph=10.0,
            ),
            HourPoint(
                time=datetime(2026, 9, 2, 21, tzinfo=timezone.utc),
                temp_c=21.0,
                condition=Condition.OVERCAST,
                wind_kph=16.0,
            ),
        ]
        now = datetime(2026, 9, 2, 20, tzinfo=timezone.utc)
        current = interpolate(hours, now)

        self.assertAlmostEqual(current.temp_c, 23.0, places=6)
        self.assertAlmostEqual(current.wind_kph, 14.0, places=6)
        # Blizi je termin u 21:00, pa stanje neba dolazi odande.
        self.assertEqual(current.condition, Condition.OVERCAST)

    def test_interpolacija_izvan_niza_uzima_najblizi(self):
        hours = [
            HourPoint(
                time=datetime(2026, 9, 2, 18, tzinfo=timezone.utc),
                temp_c=27.0,
            ),
            HourPoint(
                time=datetime(2026, 9, 2, 21, tzinfo=timezone.utc),
                temp_c=21.0,
            ),
        ]
        # Prije pocetka niza nema sto interpolirati.
        current = interpolate(
            hours, datetime(2026, 9, 2, 10, tzinfo=timezone.utc)
        )
        self.assertEqual(current.temp_c, 27.0)
        self.assertIsNone(
            interpolate([], datetime(2026, 9, 2, 10, tzinfo=timezone.utc))
        )

    def test_strana_svijeta_iz_teksta(self):
        self.assertEqual(compass_to_degrees("N"), 0)
        self.assertEqual(compass_to_degrees("ne"), 45)
        self.assertEqual(compass_to_degrees("SW"), 225)
        # "VR" znaci promjenjiv vjetar - nema smisla u prosjeku.
        self.assertIsNone(compass_to_degrees("VR"))
        self.assertIsNone(compass_to_degrees(None))


class CssVersionTests(SimpleTestCase):
    def test_verzija_je_vrijeme_izmjene_datoteke(self):
        # Broj koji se mijenja s datotekom - da preglednik ne sluzi stari CSS.
        self.assertGreater(views.css_version(), 0)

    def test_bez_datoteke_ne_puca(self):
        with mock.patch("os.path.getmtime", side_effect=OSError):
            self.assertEqual(views.css_version(), 0)


class ClientIpTests(SimpleTestCase):
    def test_uzima_prvi_iz_x_forwarded_for(self):
        request = RequestFactory().get(
            "/prognoze/",
            HTTP_X_FORWARDED_FOR="203.0.113.7, 70.41.3.18, 150.172.238.178",
        )
        self.assertEqual(views.client_ip(request), "203.0.113.7")

    def test_bez_proxyja_uzima_remote_addr(self):
        request = RequestFactory().get("/prognoze/", REMOTE_ADDR="203.0.113.9")
        self.assertEqual(views.client_ip(request), "203.0.113.9")


class PublicIpTests(SimpleTestCase):
    def test_javne_adrese_prolaze(self):
        self.assertTrue(is_public_ip("8.8.8.8"))
        self.assertTrue(is_public_ip("2001:4860:4860::8888"))

    def test_dokumentacijske_adrese_ne_prolaze(self):
        # Python 3.12 je raspone iz dokumentacije (203.0.113.0/24 i slicne)
        # svrstao medu privatne. To nam odgovara - to nisu stvarni posjetitelji.
        self.assertFalse(is_public_ip("203.0.113.7"))
        self.assertFalse(is_public_ip("192.0.2.1"))

    def test_lokalne_adrese_se_preskacu(self):
        # U razvoju je klijent uvijek 127.0.0.1 - nema smisla slati usluzi.
        self.assertFalse(is_public_ip("127.0.0.1"))
        self.assertFalse(is_public_ip("192.168.1.5"))
        self.assertFalse(is_public_ip("10.0.0.3"))
        self.assertFalse(is_public_ip("172.16.0.1"))
        self.assertFalse(is_public_ip("::1"))
        self.assertFalse(is_public_ip("169.254.1.1"))

    def test_smece_ne_rusi_nego_vraca_false(self):
        self.assertFalse(is_public_ip(""))
        self.assertFalse(is_public_ip(None))
        self.assertFalse(is_public_ip("nije-ip"))
        self.assertFalse(is_public_ip("999.999.999.999"))


class ChosenCityTests(SimpleTestCase):
    """Grad odabran iz prijedloga stize kao koordinate + ime."""

    def test_ime_iz_prijedloga_se_koristi_bez_novog_upita(self):
        with mock.patch.object(geocode, "reverse") as obrnuto, \
                mock.patch.object(geocode, "utc_offset_for", return_value=0):
            location = geocode.resolve(
                latitude="43.5081", longitude="16.4402", name="Split"
            )

        self.assertEqual(location.name, "Split")
        self.assertEqual(location.latitude, 43.5081)
        self.assertEqual(location.source, geocode.BY_QUERY)
        # Ime vec znamo, pa se obrnuto geokodiranje preskace.
        obrnuto.assert_not_called()

    def test_bez_imena_se_i_dalje_pita_za_njega(self):
        with mock.patch.object(geocode, "reverse") as obrnuto, \
                mock.patch.object(geocode, "utc_offset_for", return_value=0):
            obrnuto.return_value = Location(
                "Negdje", "HR", 43.5081, 16.4402, source=geocode.BY_PRECISE
            )
            geocode.resolve(latitude="43.5081", longitude="16.4402")

        obrnuto.assert_called_once()

    def test_predugo_ime_se_krati(self):
        with mock.patch.object(geocode, "utc_offset_for", return_value=0):
            location = geocode.resolve(
                latitude="45.32", longitude="14.47", name="x" * 500
            )
        self.assertEqual(len(location.name), 80)


class TimezoneOffsetTests(SimpleTestCase):
    """Pomak zone iz naziva - brzi put, bez mreznog upita."""

    def test_naziv_zone_daje_pomak(self):
        # Hrvatska je zimi +1, ljeti +2; oba su valjana.
        self.assertIn(
            geocode.offset_from_timezone("Europe/Zagreb"), (3600, 7200)
        )
        self.assertEqual(geocode.offset_from_timezone("UTC"), 0)

    def test_nepoznata_ili_prazna_zona_daje_none(self):
        self.assertIsNone(geocode.offset_from_timezone(""))
        self.assertIsNone(geocode.offset_from_timezone(None))
        self.assertIsNone(geocode.offset_from_timezone("Nije/Zona"))

    def test_poznata_zona_preskace_mrezni_upit(self):
        with mock.patch.object(geocode, "utc_offset_for") as preko_mreze:
            location = geocode.resolve(
                latitude="43.5081",
                longitude="16.4402",
                name="Split",
                tz="Europe/Zagreb",
            )

        self.assertIn(location.utc_offset_seconds, (3600, 7200))
        preko_mreze.assert_not_called()

    def test_bez_zone_se_pita_preko_mreze(self):
        # Obrnuto geokodiranje ne vraca zonu, pa pomak mora doci s mreze.
        with mock.patch.object(
            geocode, "utc_offset_for", return_value=7200
        ) as preko_mreze, mock.patch.object(
            geocode, "reverse",
            return_value=Location("Negdje", "", 43.5, 16.4),
        ):
            geocode.resolve(latitude="43.5", longitude="16.4")

        preko_mreze.assert_called_once()

    def test_zadano_mjesto_ima_zonu(self):
        # Rijeka je zadana, pa ni ona ne treba mrezni upit.
        with mock.patch.object(geocode, "utc_offset_for") as preko_mreze:
            location = geocode.resolve()

        self.assertEqual(location.name, "Rijeka")
        self.assertIn(location.utc_offset_seconds, (3600, 7200))
        preko_mreze.assert_not_called()


class IpinfoParseTests(SimpleTestCase):
    """ipinfo.io - koordinate stizu kao jedan tekst, drzava kao oznaka."""

    def test_razdvaja_koordinate_iz_teksta(self):
        location = geocode.parse_ipinfo({
            "city": "Karlovac", "region": "Karlovac", "country": "HR",
            "loc": "45.4917,15.5500", "timezone": "Europe/Zagreb",
        })
        self.assertEqual(location.name, "Karlovac")
        self.assertEqual(location.latitude, 45.4917)
        self.assertEqual(location.longitude, 15.55)
        self.assertEqual(location.timezone, "Europe/Zagreb")
        self.assertEqual(location.source, geocode.BY_IP)

    def test_bez_koordinata_ili_smece_daje_none(self):
        self.assertIsNone(geocode.parse_ipinfo({"city": "X"}))
        self.assertIsNone(geocode.parse_ipinfo({"loc": "nije,broj"}))
        self.assertIsNone(geocode.parse_ipinfo({"loc": "45.0"}))
        self.assertIsNone(geocode.parse_ipinfo(None))
        # "bogon" znaci privatnu/rezerviranu adresu.
        self.assertIsNone(geocode.parse_ipinfo({"bogon": True}))

    def test_neuspjeh_se_pamti_da_se_ne_ponavlja(self):
        # Blokirana ili pala usluga ne smije se zvati na svaki zahtjev.
        cache.clear()
        with mock.patch.object(
            geocode.requests, "get", side_effect=OSError("blokirano")
        ) as poziv:
            self.assertIsNone(geocode.from_ip("8.8.8.8"))
            self.assertIsNone(geocode.from_ip("8.8.8.8"))
        self.assertEqual(poziv.call_count, 1)
        cache.clear()


class NominatimParseTests(SimpleTestCase):
    """Nominatim naselje javlja pod razlicitim kljucevima."""

    def test_grad(self):
        ime, drzava = geocode.parse_nominatim(
            {"address": {"city": "Split", "country": "Hrvatska"}}
        )
        self.assertEqual((ime, drzava), ("Split", "Hrvatska"))

    def test_manje_mjesto_pod_town_ili_village(self):
        self.assertEqual(
            geocode.parse_nominatim({"address": {"town": "Krk"}})[0], "Krk"
        )
        self.assertEqual(
            geocode.parse_nominatim({"address": {"village": "Lubenice"}})[0],
            "Lubenice",
        )

    def test_grad_ima_prednost_pred_manjim(self):
        ime, _ = geocode.parse_nominatim(
            {"address": {"village": "X", "city": "Rijeka"}}
        )
        self.assertEqual(ime, "Rijeka")

    def test_prazno_daje_prazno(self):
        self.assertEqual(geocode.parse_nominatim({}), ("", ""))
        self.assertEqual(geocode.parse_nominatim(None), ("", ""))


class DisabledSourcesTests(SimpleTestCase):
    def test_iskljuceni_izvori_se_ne_pojavljuju(self):
        with mock.patch.dict(
            os.environ, {"PROGNOZE_DISABLED_SOURCES": "wttr, seven_timer"}
        ):
            imena = {p.name for p in providers.all_providers()}
        self.assertNotIn("wttr", imena)
        self.assertNotIn("seven_timer", imena)
        # Ostali ostaju.
        self.assertIn("met_no", imena)
        self.assertIn("open_meteo_group", imena)

    def test_bez_varijable_su_svi_tu(self):
        with mock.patch.dict(os.environ, {"PROGNOZE_DISABLED_SOURCES": ""}):
            imena = {p.name for p in providers.all_providers()}
        self.assertIn("wttr", imena)
        self.assertIn("seven_timer", imena)


class CoordinateTests(SimpleTestCase):
    def test_ispravne_koordinate(self):
        self.assertEqual(_coordinates("45.32", "14.47"), (45.32, 14.47))
        self.assertEqual(_coordinates(0, 0), (0.0, 0.0))

    def test_izvan_granica_ili_smece(self):
        self.assertIsNone(_coordinates("91", "14"))
        self.assertIsNone(_coordinates("45", "181"))
        self.assertIsNone(_coordinates("negdje", "tamo"))
        self.assertIsNone(_coordinates(None, None))


class OpenMeteoGroupTests(SimpleTestCase):
    """Sest modela iz jednog zahtjeva."""

    def _payload(self):
        """Odgovor u obliku u kojem ga Open-Meteo vraca uz `models=`:
        nazivi polja imaju oznaku modela kao nastavak."""
        vremena = [
            "2026-09-05T{0:02d}:00".format(sat) for sat in range(4)
        ]
        hourly = {"time": vremena}
        for model in open_meteo.MODELS:
            k = model.key
            hourly["temperature_2m_" + k] = [20.0, 21.0, 22.0, 23.0]
            hourly["weather_code_" + k] = [0, 0, 3, 3]
            hourly["wind_speed_10m_" + k] = [10.0, 11.0, 12.0, 13.0]
            hourly["wind_direction_10m_" + k] = [90, 90, 180, 180]
            hourly["relative_humidity_2m_" + k] = [50, 51, 52, 53]
            hourly["precipitation_probability_" + k] = [5, 6, 7, 8]
            hourly["uv_index_" + k] = [1.0, 2.0, 3.0, 4.0]
        daily = {
            "time": ["2026-09-05"],
            "sunrise_best_match": ["2026-09-05T04:30"],
            "sunset_best_match": ["2026-09-05T17:45"],
        }
        return {"hourly": hourly, "daily": daily}

    def _fetch(self):
        provider = open_meteo.OpenMeteoProvider()
        with mock.patch.object(
            provider, "get_json", return_value=self._payload()
        ):
            return provider.fetch(Location("Rijeka", "HR", 45.32, 14.47))

    def test_jedan_zahtjev_daje_prognozu_po_modelu(self):
        forecasts = self._fetch()

        self.assertEqual(len(forecasts), len(open_meteo.MODELS))
        self.assertEqual(
            [f.name for f in forecasts], [m.name for m in open_meteo.MODELS]
        )
        for forecast in forecasts:
            with self.subTest(izvor=forecast.name):
                self.assertTrue(forecast.ok)
                self.assertEqual(len(forecast.hours), 4)

    def test_salje_se_tocno_jedan_zahtjev(self):
        provider = open_meteo.OpenMeteoProvider()
        with mock.patch.object(
            provider, "get_json", return_value=self._payload()
        ) as poziv:
            provider.fetch(Location("Rijeka", "HR", 45.32, 14.47))

        self.assertEqual(poziv.call_count, 1)
        modeli = poziv.call_args.kwargs["params"]["models"].split(",")
        self.assertEqual(modeli, [m.key for m in open_meteo.MODELS])

    def test_gem_ne_glasa_o_vjerojatnosti_oborine(self):
        # GEM je za vedar dan javljao 71% kise uz 0.0 mm i kod "vedro".
        forecasts = {f.name: f for f in self._fetch()}
        gem = forecasts["open_meteo_gem"]
        drugi = forecasts["open_meteo_gfs"]

        self.assertTrue(all(h.precip_prob is None for h in gem.hours))
        self.assertIsNone(gem.precip_prob)
        # Ostali je i dalje daju.
        self.assertEqual(drugi.hours[0].precip_prob, 5.0)
        # Ali ostalo od GEM-a se koristi.
        self.assertEqual(gem.hours[0].temp_c, 20.0)

    def test_uv_i_sunce_dolaze_samo_od_jednog_modela(self):
        # Open-Meteo UV racuna iz istog izvora bez obzira na model.
        forecasts = {f.name: f for f in self._fetch()}

        glavni = forecasts["open_meteo"]
        self.assertEqual(glavni.hours[0].uv, 1.0)
        self.assertTrue(glavni.sun_times)

        for ime, forecast in forecasts.items():
            if ime == "open_meteo":
                continue
            with self.subTest(izvor=ime):
                self.assertTrue(all(h.uv is None for h in forecast.hours))
                self.assertEqual(forecast.sun_times, [])

    def test_pad_zahtjeva_ostavlja_sve_modele_vidljivima(self):
        provider = open_meteo.OpenMeteoProvider()
        pali = provider.empty_result("429 Too Many Requests")

        self.assertEqual(len(pali), len(open_meteo.MODELS))
        for forecast in pali:
            with self.subTest(izvor=forecast.name):
                self.assertFalse(forecast.ok)
                self.assertIn("429", forecast.error)

    def test_nema_dvostrukih_ni_izbacenih_modela(self):
        kljucevi = [m.key for m in open_meteo.MODELS]
        self.assertEqual(len(kljucevi), len(set(kljucevi)))
        # icon_seamless je isto sto i best_match; metno se zove izravno;
        # ecmwf_ifs04 vraca same null vrijednosti.
        self.assertNotIn("icon_seamless", kljucevi)
        self.assertNotIn("metno_seamless", kljucevi)
        self.assertNotIn("ecmwf_ifs04", kljucevi)


class PrecipitationAmountTests(SimpleTestCase):
    """Milimetri oborine - svaki izvor ih daje malo drugacije."""

    def test_wttr_trosatnu_kolicinu_dijeli_na_sat(self):
        # 3.0 mm u tri sata je 1.0 mm po satu, inace bi wttr u prosjeku
        # trostruko nadglasao satne izvore.
        self.assertEqual(wttr._per_hour("3.0"), 1.0)
        self.assertEqual(wttr._per_hour(0), 0.0)
        self.assertIsNone(wttr._per_hour(None))
        self.assertIsNone(wttr._per_hour("puno"))

    def test_tomorrow_zbraja_kisu_snijeg_i_susnjezicu(self):
        # Snijeg i susnjezica ulaze kao tekuci ekvivalent (Lwe), ne kao
        # visina snijega - samo je to usporedivo s kisom.
        vrijednosti = {
            "rainAccumulation": 1.0,
            "snowAccumulationLwe": 0.5,
            "sleetAccumulationLwe": 0.25,
            "snowAccumulation": 99.0,
        }
        self.assertEqual(tomorrow.total_precip_mm(vrijednosti), 1.75)

    def test_tomorrow_bez_podataka_daje_none(self):
        self.assertIsNone(tomorrow.total_precip_mm({}))
        self.assertEqual(tomorrow.total_precip_mm({"rainAccumulation": 0}), 0.0)

    def test_sat_pokazuje_mm_samo_kad_ih_ima(self):
        suh = aggregate.AggregatedHour(hour=10, label="", precip_mm=0.0)
        self.assertNotIn("mm", suh.title)

        mokar = aggregate.AggregatedHour(hour=10, label="", precip_mm=1.2)
        self.assertIn("1.2 mm", mokar.title)

    def test_dan_zbraja_satne_milimetre(self):
        dan = aggregate.DayForecast(
            label="sutra", precip_hours=3, precip_mm=4.5
        )
        self.assertIn("oborina 3 h, 4.5 mm", dan.title)

        suh = aggregate.DayForecast(label="sutra", precip_hours=0)
        self.assertNotIn("oborina", suh.title)


class TomorrowTests(SimpleTestCase):
    def test_stanja_iz_njihovih_kodova(self):
        self.assertEqual(from_tomorrow(1000), Condition.CLEAR)
        self.assertEqual(from_tomorrow(1100), Condition.MAINLY_CLEAR)
        self.assertEqual(from_tomorrow(1101), Condition.PARTLY_CLOUDY)
        self.assertEqual(from_tomorrow(1001), Condition.OVERCAST)
        self.assertEqual(from_tomorrow(4000), Condition.DRIZZLE)
        self.assertEqual(from_tomorrow(4001), Condition.RAIN)
        self.assertEqual(from_tomorrow(5101), Condition.SNOW)
        self.assertEqual(from_tomorrow(6001), Condition.SLEET)
        self.assertEqual(from_tomorrow(8000), Condition.THUNDER)
        self.assertIsNone(from_tomorrow(None))
        self.assertIsNone(from_tomorrow(1234))

    def test_vjetar_se_pretvara_iz_ms_u_kmh(self):
        payload = {
            "timelines": {
                "hourly": [
                    {
                        "time": "2026-09-06T09:00:00Z",
                        "values": {
                            "temperature": 28.6,
                            "weatherCode": 1000,
                            "precipitationProbability": 0,
                            # 3.4 m/s je oko 12 km/h, ne 3.4 km/h.
                            "windSpeed": 3.4,
                            "windDirection": 61,
                            "humidity": 30,
                            "uvIndex": 5,
                        },
                    }
                ]
            }
        }
        provider = tomorrow.TomorrowProvider()
        with mock.patch.object(provider, "get_json", return_value=payload):
            forecast = provider.fetch(Location("Rijeka", "HR", 45.32, 14.47))

        sat = forecast.hours[0]
        self.assertAlmostEqual(sat.wind_kph, 12.24, places=2)
        self.assertEqual(sat.temp_c, 28.6)
        self.assertEqual(sat.condition, Condition.CLEAR)
        self.assertEqual(sat.uv, 5.0)
        self.assertEqual(sat.humidity, 30.0)

    def test_kljuc_je_prijavljen_kao_tajna(self):
        provider = tomorrow.TomorrowProvider()
        with mock.patch.dict(
            os.environ, {"TOMORROW_KEY": "tajni123"}, clear=False
        ):
            self.assertEqual(provider.secrets(), ["tajni123"])
            self.assertTrue(provider.available())
        with mock.patch.dict(os.environ, {"TOMORROW_KEY": ""}, clear=False):
            self.assertEqual(provider.secrets(), [])
            self.assertFalse(provider.available())


class SecretScrubbingTests(SimpleTestCase):
    def test_kljuc_se_brise_iz_poruke(self):
        # WeatherAPI salje kljuc kao parametar, pa ga poruka greske sadrzi.
        poruka = (
            "401 Client Error for url: http://api.weatherapi.com/v1/"
            "forecast.json?key=tajni123&q=45.3,14.4"
        )
        ocisceno = providers.scrub(poruka, ["tajni123"])

        self.assertNotIn("tajni123", ocisceno)
        self.assertIn("***", ocisceno)
        self.assertIn("401", ocisceno)

    def test_bez_kljuca_poruka_ostaje_ista(self):
        self.assertEqual(providers.scrub("timeout", []), "timeout")
        self.assertEqual(providers.scrub("timeout", [""]), "timeout")

    def test_izvor_s_kljucem_ga_prijavljuje(self):
        provider = weather_api.WeatherApiProvider()
        with mock.patch.dict(
            os.environ, {"WEATHERAPI_KEY": "tajni123"}, clear=False
        ):
            self.assertEqual(provider.secrets(), ["tajni123"])
        with mock.patch.dict(os.environ, {"WEATHERAPI_KEY": ""}, clear=False):
            self.assertEqual(provider.secrets(), [])

    def test_izvori_bez_kljuca_nemaju_tajni(self):
        for provider in providers.all_providers():
            if provider.requires_key:
                continue
            with self.subTest(izvor=provider.name):
                self.assertEqual(provider.secrets(), [])


class WindDirectionTests(SimpleTestCase):
    def test_stupnjevi_u_stranu_svijeta(self):
        self.assertEqual(wind_direction(0), "N")
        self.assertEqual(wind_direction(90), "E")
        self.assertEqual(wind_direction(180), "S")
        self.assertEqual(wind_direction(270), "W")
        self.assertEqual(wind_direction(45), "NE")

    def test_rubovi_i_smece(self):
        self.assertEqual(wind_direction(359), "N")
        self.assertEqual(wind_direction(370), "N")
        self.assertIsNone(wind_direction(None))
        self.assertIsNone(wind_direction("sjever"))

    def test_kruzni_prosjek_ne_zavrsi_na_jugu(self):
        # Obicni prosjek 350 i 10 je 180 (jug), a tocno je 0 (sjever).
        self.assertAlmostEqual(
            aggregate.mean_direction([350, 10]) % 360, 0, places=6
        )
        self.assertEqual(
            wind_direction(aggregate.mean_direction([350, 10])), "N"
        )


class VoteTests(SimpleTestCase):
    def test_vecina_pobjeduje(self):
        result = aggregate.vote(
            [Condition.RAIN, Condition.RAIN, Condition.CLEAR]
        )
        self.assertEqual(result, Condition.RAIN)

    def test_neodluceno_ide_na_ozbiljnije(self):
        result = aggregate.vote([Condition.CLEAR, Condition.THUNDER])
        self.assertEqual(result, Condition.THUNDER)

    def test_dva_na_dva_ide_na_ozbiljnije(self):
        result = aggregate.vote(
            [
                Condition.CLEAR,
                Condition.CLEAR,
                Condition.THUNDER,
                Condition.THUNDER,
            ]
        )
        self.assertEqual(result, Condition.THUNDER)

    def test_potpuni_razlaz_uzima_sredinu(self):
        # Tri izvora, tri razlicita odgovora: jedan model koji vidi rosulju
        # ne smije cijeli sat obojati kisom.
        result = aggregate.vote(
            [Condition.CLEAR, Condition.OVERCAST, Condition.DRIZZLE]
        )
        self.assertEqual(result, Condition.OVERCAST)

    def test_dva_razlicita_odgovora_i_dalje_idu_na_ozbiljnije(self):
        # Kod samo dva izvora nema "sredine", pa ostaje opreznija procjena.
        result = aggregate.vote([Condition.CLEAR, Condition.RAIN])
        self.assertEqual(result, Condition.RAIN)

    def test_none_se_preskace(self):
        self.assertEqual(
            aggregate.vote([None, Condition.FOG, None]), Condition.FOG
        )
        self.assertIsNone(aggregate.vote([None, None]))
        self.assertIsNone(aggregate.vote([]))


class DayConditionTests(SimpleTestCase):
    """Koje stanje najbolje opisuje cijeli dan."""

    def _hours(self, *conditions):
        return [
            aggregate.AggregatedHour(hour=i, label="", condition=c)
            for i, c in enumerate(conditions)
        ]

    def test_jedan_sat_kise_pobjeduje_cijeli_vedar_dan(self):
        # Ovo je bila izricita zelja: kisa je vijest i kad traje sat.
        hours = self._hours(*([Condition.CLEAR] * 23 + [Condition.RAIN]))
        self.assertEqual(aggregate.day_condition(hours), Condition.RAIN)

    def test_od_vise_oborina_pobjeduje_najjaca(self):
        hours = self._hours(
            Condition.DRIZZLE, Condition.RAIN, Condition.THUNDER,
            *([Condition.CLEAR] * 10)
        )
        self.assertEqual(aggregate.day_condition(hours), Condition.THUNDER)

    def test_jedan_oblacan_sat_ne_cini_dan_oblacnim(self):
        # Za razliku od kise, naoblaka nije dogadaj nego stanje - odlucuje
        # ono cega je najvise.
        hours = self._hours(*([Condition.CLEAR] * 20 + [Condition.OVERCAST]))
        self.assertEqual(aggregate.day_condition(hours), Condition.CLEAR)

    def test_bez_oborine_odlucuje_vecina(self):
        hours = self._hours(
            *([Condition.OVERCAST] * 14 + [Condition.CLEAR] * 6)
        )
        self.assertEqual(aggregate.day_condition(hours), Condition.OVERCAST)

    def test_magla_nije_dogadaj(self):
        # Magla je stanje neba, pa se za nju gleda kolicina, ne pojava.
        hours = self._hours(*([Condition.CLEAR] * 20 + [Condition.FOG]))
        self.assertEqual(aggregate.day_condition(hours), Condition.CLEAR)

    def test_prazan_dan_nema_stanje(self):
        self.assertIsNone(aggregate.day_condition([]))
        self.assertIsNone(aggregate.day_condition(self._hours(None, None)))


class UvBandTests(SimpleTestCase):
    def test_razredi_po_who(self):
        self.assertEqual(aggregate.uv_band(0)[0], "nizak")
        self.assertEqual(aggregate.uv_band(2)[0], "nizak")
        self.assertEqual(aggregate.uv_band(3)[0], "umjeren")
        self.assertEqual(aggregate.uv_band(5)[0], "umjeren")
        self.assertEqual(aggregate.uv_band(6)[0], "visok")
        self.assertEqual(aggregate.uv_band(7)[0], "visok")
        self.assertEqual(aggregate.uv_band(8)[0], "vrlo visok")
        self.assertEqual(aggregate.uv_band(10)[0], "vrlo visok")
        self.assertEqual(aggregate.uv_band(11)[0], "ekstreman")
        self.assertEqual(aggregate.uv_band(15)[0], "ekstreman")

    def test_bez_vrijednosti(self):
        self.assertEqual(aggregate.uv_band(None)[0], "nepoznato")

    def test_svaki_razred_ima_boju(self):
        for vrijednost in (0, 3, 6, 8, 11, None):
            self.assertTrue(aggregate.uv_band(vrijednost)[1].startswith("#"))


class AqiBandTests(SimpleTestCase):
    def test_europski_razredi(self):
        self.assertEqual(air.aqi_band(0)[0], "dobra")
        self.assertEqual(air.aqi_band(20)[0], "dobra")
        self.assertEqual(air.aqi_band(21)[0], "zadovoljavajuca")
        self.assertEqual(air.aqi_band(40)[0], "zadovoljavajuca")
        self.assertEqual(air.aqi_band(50)[0], "umjerena")
        self.assertEqual(air.aqi_band(70)[0], "losa")
        self.assertEqual(air.aqi_band(90)[0], "vrlo losa")
        self.assertEqual(air.aqi_band(140)[0], "izuzetno losa")

    def test_bez_vrijednosti(self):
        self.assertEqual(air.aqi_band(None)[0], "nepoznato")
        self.assertFalse(air.AirQuality().ok)
        self.assertFalse(air.AirQuality(error="timeout").ok)
        self.assertTrue(air.AirQuality(aqi=15).ok)

    def test_opis_navodi_cestice(self):
        quality = air.AirQuality(aqi=15, pm2_5=4.2, pm10=9.0)
        self.assertIn("PM2.5 4.2", quality.title)
        self.assertIn("PM10 9.0", quality.title)


class MeanTests(SimpleTestCase):
    def test_preskace_none(self):
        self.assertEqual(aggregate.mean([10, None, 20]), 15)

    def test_prazno_daje_none(self):
        self.assertIsNone(aggregate.mean([]))
        self.assertIsNone(aggregate.mean([None, None]))


class ParseIsoTests(SimpleTestCase):
    def test_z_sufiks(self):
        moment = parse_iso_utc("2026-09-02T14:00:00Z")
        self.assertEqual(moment.hour, 14)
        self.assertEqual(moment.tzinfo, timezone.utc)

    def test_bez_zone_koristi_pomak(self):
        # 14:00 lokalno uz +2h je 12:00 UTC.
        moment = parse_iso_utc("2026-09-02T14:00", utc_offset_seconds=7200)
        self.assertEqual(moment.hour, 12)

    def test_smece_daje_none(self):
        self.assertIsNone(parse_iso_utc("nije vrijeme"))
        self.assertIsNone(parse_iso_utc(None))


class AggregateBuildTests(SimpleTestCase):
    def setUp(self):
        self.location = Location(
            name="Rijeka",
            country="Hrvatska",
            latitude=45.32,
            longitude=14.47,
            utc_offset_seconds=7200,
        )
        self.now = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)

    def _forecast(self, name, temp, condition, wind, direction, uv=None):
        forecast = ProviderForecast(
            name=name,
            label=name,
            temp_c=temp,
            wind_kph=wind,
            wind_dir_deg=direction,
            condition=condition,
            precip_prob=20,
        )
        midnight = datetime(2026, 9, 1, 22, 0, tzinfo=timezone.utc)
        for hour in range(24):
            forecast.hours.append(
                HourPoint(
                    time=midnight + timedelta(hours=hour),
                    temp_c=temp + hour * 0.1,
                    condition=condition,
                    precip_prob=20,
                    # Gruba krivulja: vrhunac u podne, nula nocu.
                    uv=None if uv is None else max(0.0, uv - abs(12 - hour)),
                )
            )
        return forecast

    def test_usrednjava_brojeve_i_glasa_stanje(self):
        forecasts = [
            self._forecast("a", 20.0, Condition.RAIN, 10.0, 0),
            self._forecast("b", 22.0, Condition.RAIN, 20.0, 20),
            self._forecast("c", 24.0, Condition.CLEAR, 30.0, 340),
        ]
        result = aggregate.build(self.location, forecasts, now_utc=self.now)

        self.assertEqual(result.temp_c, 22.0)
        self.assertEqual(result.wind_kph, 20.0)
        self.assertEqual(result.condition, Condition.RAIN)
        self.assertEqual(result.used_sources, 3)
        self.assertEqual(result.spread_c, 4.0)
        self.assertEqual(result.wind_dir, "N")

    def test_pali_izvor_ne_rusi_prosjek(self):
        forecasts = [
            self._forecast("a", 20.0, Condition.RAIN, 10.0, 0),
            ProviderForecast(name="b", label="b", error="timeout"),
        ]
        result = aggregate.build(self.location, forecasts, now_utc=self.now)

        self.assertEqual(result.temp_c, 20.0)
        self.assertEqual(result.used_sources, 1)
        self.assertEqual(len(result.sources), 2)
        self.assertFalse(result.sources[1].ok)

    def test_bez_ijednog_izvora_ne_puca(self):
        result = aggregate.build(self.location, [], now_utc=self.now)

        self.assertIsNone(result.temp_c)
        self.assertIsNone(result.min_c)
        self.assertEqual(result.used_sources, 0)
        self.assertEqual(len(result.hours), 24)

    def test_traka_je_prozor_oko_sadasnjeg_trenutka(self):
        forecasts = [self._forecast("a", 20.0, Condition.CLEAR, 10.0, 0)]
        result = aggregate.build(self.location, forecasts, now_utc=self.now)

        self.assertEqual(len(result.hours), 24)

        # Sadasnji sat je deveti po redu: osam ih je prije njega.
        sada = [h for h in result.hours if h.is_now]
        self.assertEqual(len(sada), 1)
        self.assertEqual(result.hours.index(sada[0]), 8)

        # 12:00 UTC uz pomak +2h je 14:00 lokalno.
        self.assertEqual(sada[0].hour, 14)
        # Prozor ide od 06:00 do 05:00 sljedeceg dana, lokalno.
        self.assertEqual(result.hours[0].hour, 6)
        self.assertEqual(result.hours[-1].hour, 5)

    def test_prosli_sati_su_oznaceni(self):
        forecasts = [self._forecast("a", 20.0, Condition.CLEAR, 10.0, 0)]
        result = aggregate.build(self.location, forecasts, now_utc=self.now)

        self.assertEqual(sum(1 for h in result.hours if h.is_past), 8)
        self.assertFalse(result.hours[8].is_past)
        self.assertFalse(result.hours[9].is_past)

    def test_ponoc_u_prozoru_je_oznacena(self):
        forecasts = [self._forecast("a", 20.0, Condition.CLEAR, 10.0, 0)]
        result = aggregate.build(self.location, forecasts, now_utc=self.now)

        pocetak_dana = [h for h in result.hours if h.starts_day]
        self.assertEqual(len(pocetak_dana), 1)
        self.assertEqual(pocetak_dana[0].hour, 0)

    def test_svaki_sat_dobije_slikicu_prema_dobu_dana(self):
        # Sunce izlazi u 04:00 i zalazi u 18:00 UTC.
        forecast = self._forecast("a", 20.0, Condition.CLEAR, 10.0, 0)
        forecast.sun_times = [
            (
                datetime(2026, 9, 2, 4, tzinfo=timezone.utc),
                datetime(2026, 9, 2, 18, tzinfo=timezone.utc),
            )
        ]
        result = aggregate.build(self.location, [forecast], now_utc=self.now)

        # Prozor pocinje u 06:00 lokalno = 04:00 UTC, dakle poslije izlaska.
        jutro = result.hours[0]
        self.assertEqual(jutro.hour, 6)
        self.assertFalse(jutro.is_night)
        self.assertEqual(jutro.icon, "sun.png")

        # Lokalno 22:00 je 20:00 UTC - poslije zalaska, dakle mjesec.
        navecer = [h for h in result.hours if h.hour == 22][0]
        self.assertTrue(navecer.is_night)
        self.assertEqual(navecer.icon, "moon.png")

    def test_sat_bez_izvora_nema_slikicu_nego_prazninu(self):
        result = aggregate.build(self.location, [], now_utc=self.now)
        prazan = result.hours[0]

        self.assertEqual(prazan.sources, 0)
        self.assertIsNone(prazan.condition)
        self.assertEqual(prazan.icon, "neznamovrime.png")

    def test_izvor_bez_vjerojatnosti_kise_ne_kvari_prosjek(self):
        # 7Timer ne daje vjerojatnost oborine; smije nedostajati, ali mora
        # i dalje glasati o temperaturi i stanju neba.
        bez_kise = self._forecast("7timer", 30.0, Condition.CLEAR, 20.0, 90)
        bez_kise.precip_prob = None
        for point in bez_kise.hours:
            point.precip_prob = None

        forecasts = [
            self._forecast("a", 20.0, Condition.CLEAR, 10.0, 90),
            bez_kise,
        ]
        result = aggregate.build(self.location, forecasts, now_utc=self.now)

        self.assertEqual(result.temp_c, 25.0)
        # Prosjek kise racuna se samo iz izvora koji je daju.
        self.assertEqual(result.precip_prob, 20)
        self.assertEqual(result.used_sources, 2)

    def test_uv_graf_pokriva_kalendarski_dan(self):
        forecasts = [self._forecast("a", 20.0, Condition.CLEAR, 10.0, 0, uv=8)]
        result = aggregate.build(self.location, forecasts, now_utc=self.now)

        self.assertTrue(result.has_uv)
        self.assertEqual(len(result.day_hours), 24)
        # Graf je kalendarski dan, ne pomicni prozor.
        self.assertEqual(result.day_hours[0].hour, 0)
        self.assertEqual(result.day_hours[23].hour, 23)

        self.assertEqual(result.uv_max, 8.0)
        self.assertEqual(result.uv_peak_hour.hour, 12)
        self.assertEqual(result.uv_max_label, "vrlo visok")

    def test_visine_stupaca_su_u_odnosu_na_dnevni_maksimum(self):
        forecasts = [self._forecast("a", 20.0, Condition.CLEAR, 10.0, 0, uv=8)]
        result = aggregate.build(self.location, forecasts, now_utc=self.now)

        vrhunac = result.uv_peak_hour
        self.assertEqual(vrhunac.uv_pct, 100.0)
        # Sat s pola UV-a ima pola stupca.
        polovica = [h for h in result.day_hours if h.uv == 4.0][0]
        self.assertEqual(polovica.uv_pct, 50.0)
        # Noc je na nuli.
        self.assertEqual(result.day_hours[0].uv, 0.0)
        self.assertEqual(result.day_hours[0].uv_pct, 0.0)

    def test_slab_uv_ne_razvuce_graf_do_vrha(self):
        # Zimski dan s UV 1 ne smije izgledati kao ljetni s UV 10.
        forecasts = [self._forecast("a", 5.0, Condition.CLEAR, 10.0, 0, uv=1)]
        result = aggregate.build(self.location, forecasts, now_utc=self.now)

        self.assertEqual(result.uv_max, 1.0)
        # Ljestvica ide do UV_MIN_SCALE (3), pa je vrhunac na trecini.
        self.assertAlmostEqual(result.uv_peak_hour.uv_pct, 33.3, places=1)

    def test_suncanje_izbjegava_podne_kad_je_uv_jak(self):
        # Vrhunac 10 znaci da je oko podneva iznad TAN_MAX, pa ostanu dva
        # razmaka - jutro i poslijepodne.
        forecasts = [self._forecast("a", 25.0, Condition.CLEAR, 10.0, 0, uv=10)]
        result = aggregate.build(self.location, forecasts, now_utc=self.now)

        self.assertEqual(len(result.tanning_windows), 2)
        prvi, drugi = result.tanning_windows
        # UV je 10 - |12 - sat|: u 8h je 6 (jos moze), u 9h vec 7 (previse).
        self.assertEqual(prvi, (5, 8))
        self.assertEqual(drugi, (16, 19))
        self.assertEqual(result.tanning_label, "05:00-09:00 i 16:00-20:00")

    def test_suncanje_je_jedan_raspon_kad_je_uv_umjeren(self):
        # Vrhunac 6 nikad ne prijede TAN_MAX, pa je razmak jedan i neprekinut.
        forecasts = [self._forecast("a", 20.0, Condition.CLEAR, 10.0, 0, uv=6)]
        result = aggregate.build(self.location, forecasts, now_utc=self.now)

        self.assertEqual(len(result.tanning_windows), 1)
        self.assertEqual(result.tanning_windows[0], (9, 15))
        self.assertEqual(result.tanning_label, "09:00-16:00")

    def test_granica_gleda_zaokruzeni_uv(self):
        # 2.9 i 3.0 su isti sat po WHO ljestvici, pa ne smiju razdvojiti
        # razmak. Prije je 2.9 ispadao i razmak se lomio na komadice.
        forecast = self._forecast("a", 25.0, Condition.CLEAR, 10.0, 0, uv=6)
        for point in forecast.hours:
            point.uv = 2.9
        result = aggregate.build(self.location, [forecast], now_utc=self.now)

        self.assertEqual(len(result.tanning_windows), 1)
        self.assertEqual(result.tanning_windows[0], (0, 23))

    def test_slab_uv_nema_sati_za_suncanje(self):
        forecasts = [self._forecast("a", 5.0, Condition.CLEAR, 10.0, 0, uv=2)]
        result = aggregate.build(self.location, forecasts, now_utc=self.now)

        self.assertEqual(result.tanning_windows, [])
        self.assertEqual(result.tanning_label, "")

    def test_bez_uv_podataka_nema_ni_sati_za_suncanje(self):
        forecasts = [self._forecast("a", 20.0, Condition.CLEAR, 10.0, 0)]
        result = aggregate.build(self.location, forecasts, now_utc=self.now)

        self.assertEqual(result.tanning_windows, [])
        self.assertEqual(result.tanning_label, "")

    def test_krivulja_ima_tocku_po_satu(self):
        forecasts = [self._forecast("a", 25.0, Condition.CLEAR, 10.0, 0, uv=8)]
        result = aggregate.build(self.location, forecasts, now_utc=self.now)

        tocke = result.uv_line_points.split()
        # Graf pokriva samo dnevne sate (4h-20h), ne cijela 24.
        self.assertEqual(len(tocke), len(result.uv_hours))
        self.assertTrue(tocke[0].startswith("0,"))
        self.assertTrue(
            tocke[-1].startswith("{0},".format(result.uv_view_width))
        )
        # Vrhunac je u 12h, dakle osmi prikazani sat, i na vrhu grafa
        # (y = 0, jer SVG racuna od vrha).
        self.assertEqual(tocke[12 - result.uv_hours[0].hour], "80,0.0")

    def test_ispuna_je_zatvorena_do_dna(self):
        forecasts = [self._forecast("a", 25.0, Condition.CLEAR, 10.0, 0, uv=8)]
        result = aggregate.build(self.location, forecasts, now_utc=self.now)

        area = result.uv_area_points.split()
        self.assertEqual(area[0], "0,100")
        self.assertEqual(
            area[-1], "{0},100".format(result.uv_view_width)
        )

    def test_gradijent_prati_ljestvicu(self):
        forecasts = [self._forecast("a", 25.0, Condition.CLEAR, 10.0, 0, uv=8)]
        result = aggregate.build(self.location, forecasts, now_utc=self.now)

        stops = result.uv_gradient_stops
        self.assertTrue(stops)
        # Pomaci rastu i staju na 100%.
        pomaci = [o for o, _ in stops]
        self.assertEqual(pomaci, sorted(pomaci))
        self.assertEqual(pomaci[-1], 100.0)
        # Ljestvica je 8, pa granica "nizak/umjeren" (2.5) pada na 31.25%.
        self.assertAlmostEqual(pomaci[1], 31.25, delta=0.1)

    def test_bez_uv_podataka_nema_krivulje(self):
        forecasts = [self._forecast("a", 20.0, Condition.CLEAR, 10.0, 0)]
        result = aggregate.build(self.location, forecasts, now_utc=self.now)

        self.assertEqual(result.uv_line_points, "")
        self.assertEqual(result.uv_area_points, "")

    def test_izlazak_i_zalazak_sunca(self):
        forecast = self._forecast("a", 25.0, Condition.CLEAR, 10.0, 0, uv=8)
        forecast.sun_times = [
            (
                datetime(2026, 9, 2, 4, 30, tzinfo=timezone.utc),
                datetime(2026, 9, 2, 17, 45, tzinfo=timezone.utc),
            )
        ]
        result = aggregate.build(self.location, [forecast], now_utc=self.now)

        # Pomak je +2h, pa 04:30 UTC znaci 06:30 lokalno.
        self.assertEqual(result.sunrise_label, "06:30")
        self.assertEqual(result.sunset_label, "19:45")
        self.assertEqual(result.day_length_label, "13 h 15 min")

    def test_bez_podatka_o_suncu_nema_oznaka(self):
        forecasts = [self._forecast("a", 20.0, Condition.CLEAR, 10.0, 0)]
        result = aggregate.build(self.location, forecasts, now_utc=self.now)

        self.assertEqual(result.sunrise_label, "")
        self.assertEqual(result.day_length_label, "")

    def test_trenutni_uv_ima_razred_i_boju(self):
        forecast = self._forecast("a", 25.0, Condition.CLEAR, 10.0, 0, uv=8)
        forecast.uv = 7.0
        result = aggregate.build(self.location, [forecast], now_utc=self.now)

        self.assertEqual(result.uv, 7.0)
        self.assertEqual(result.uv_label, "visok")
        self.assertTrue(result.uv_color.startswith("#"))

    def test_uv_graf_izostavlja_nocne_sate(self):
        # UV je nocu svugdje nula; graf pokriva samo dio dana oko podneva.
        forecasts = [self._forecast("a", 25.0, Condition.CLEAR, 10.0, 0, uv=8)]
        result = aggregate.build(self.location, forecasts, now_utc=self.now)

        sati = [h.hour for h in result.uv_hours]
        self.assertLess(len(sati), 24)
        # UV = 8 - |12 - sat| je nula u 4h i u 20h, a prvi/zadnji sat s
        # UV-om su 5 i 19; graf im doda po sat rezerve sa svake strane.
        self.assertEqual(sati[0], 4)
        self.assertEqual(sati[-1], 20)
        # Sirina SVG-a prati broj prikazanih sati.
        self.assertEqual(result.uv_view_width, (len(sati) - 1) * 10)

    def test_bez_uv_podataka_prozor_pada_na_zadani(self):
        forecasts = [self._forecast("a", 20.0, Condition.CLEAR, 10.0, 0)]
        result = aggregate.build(self.location, forecasts, now_utc=self.now)

        sati = [h.hour for h in result.uv_hours]
        self.assertEqual(sati[0], aggregate.UV_WINDOW_FALLBACK[0])
        self.assertEqual(sati[-1], aggregate.UV_WINDOW_FALLBACK[1])

    def test_bez_uv_podataka_grafa_nema(self):
        forecasts = [self._forecast("a", 20.0, Condition.CLEAR, 10.0, 0)]
        result = aggregate.build(self.location, forecasts, now_utc=self.now)

        self.assertFalse(result.has_uv)
        self.assertIsNone(result.uv_max)
        self.assertIsNone(result.uv_peak_hour)
        self.assertEqual(result.day_hours[12].uv_pct, 0.0)

    def test_dani_sa_strane_pocinju_od_sutra(self):
        # Danas vec stoji u gornjoj kartici, pa se ne ponavlja sa strane.
        forecasts = [self._forecast("a", 20.0, Condition.CLEAR, 10.0, 0)]
        result = aggregate.build(self.location, forecasts, now_utc=self.now)

        self.assertEqual(len(result.days), aggregate.FORECAST_DAYS)
        self.assertEqual(result.days[0].label, "sutra")
        self.assertNotIn("danas", [dan.label for dan in result.days])
        # Ostali nose kraticu dana u tjednu.
        for dan in result.days[1:]:
            self.assertIn(dan.label, aggregate.WEEKDAYS)

    def test_danasnji_sati_se_i_dalje_racunaju(self):
        # Dan 0 se preskace u popisu, ali UV graf i min/max i dalje ovise
        # o njegovim satima.
        forecasts = [self._forecast("a", 20.0, Condition.CLEAR, 10.0, 0)]
        result = aggregate.build(self.location, forecasts, now_utc=self.now)

        self.assertEqual(len(result.day_hours), 24)
        self.assertEqual(result.min_c, 20.0)
        self.assertEqual(result.max_c, 22.3)

    def test_sutra_ima_svih_24_sata(self):
        forecast = self._forecast("a", 20.0, Condition.CLEAR, 10.0, 0)
        # Prosiri niz da pokrije i sutra (2026-09-03 lokalno).
        zadnji = forecast.hours[-1].time
        for i in range(1, 25):
            forecast.hours.append(
                HourPoint(
                    time=zadnji + timedelta(hours=i),
                    temp_c=15.0,
                    condition=Condition.RAIN,
                )
            )
        result = aggregate.build(self.location, [forecast], now_utc=self.now)

        sutra = result.tomorrow_hours
        self.assertEqual(len(sutra), 24)
        self.assertEqual([h.hour for h in sutra], list(range(24)))
        # Sutra nijedan sat nije "sada" ni "proslo".
        self.assertFalse(any(h.is_now for h in sutra))
        self.assertFalse(any(h.is_past for h in sutra))
        self.assertTrue(all(h.condition == Condition.RAIN for h in sutra))

    def test_sutra_bez_podataka_je_prazno(self):
        # Izvor pokriva samo danas.
        forecasts = [self._forecast("a", 20.0, Condition.CLEAR, 10.0, 0)]
        result = aggregate.build(self.location, forecasts, now_utc=self.now)

        self.assertEqual(result.tomorrow_hours, [])
        self.assertEqual(aggregate.build(self.location, [], now_utc=self.now).tomorrow_hours, [])

    def test_dan_bez_podataka_ostaje_prazan(self):
        # Izvor pokriva samo danas, pa preostali dani nemaju sto pokazati.
        forecasts = [self._forecast("a", 20.0, Condition.CLEAR, 10.0, 0)]
        result = aggregate.build(self.location, forecasts, now_utc=self.now)

        zadnji = result.days[-1]
        self.assertIsNone(zadnji.condition)
        self.assertIsNone(zadnji.max_c)
        self.assertEqual(zadnji.icon, "neznamovrime.png")

    def test_min_max_dolaze_iz_danasnjih_sati(self):
        forecasts = [self._forecast("a", 20.0, Condition.CLEAR, 10.0, 0)]
        result = aggregate.build(self.location, forecasts, now_utc=self.now)

        self.assertEqual(result.min_c, 20.0)
        self.assertEqual(result.max_c, 22.3)
