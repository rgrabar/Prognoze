"""Brza provjera izvora iz terminala, bez pokretanja servera.

    python openMetro.py
    python openMetro.py Split

Korisno kad zelis vidjeti koji izvor odgovara, a koji je pao, i koliko se
medusobno razilaze - bez otvaranja preglednika.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "mysite"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")

import django  # noqa: E402

django.setup()

from prognoze import aggregate, geocode, providers  # noqa: E402


def main():
    query = " ".join(sys.argv[1:])
    location = geocode.resolve(query)
    forecasts = providers.collect(location)
    data = aggregate.build(location, forecasts)

    print("{0}  ({1:.4f}, {2:.4f})".format(
        data.location.title, location.latitude, location.longitude
    ))
    print("lokalno vrijeme: {0}".format(data.local_time_label))
    print("")

    for source in data.sources:
        if source.ok:
            print("  [ok]  {0:<36} {1} C  {2}".format(
                source.label,
                source.temp_c if source.temp_c is not None else "?",
                source.condition_label,
            ))
        else:
            print("  [--]  {0:<36} {1}".format(source.label, source.error))

    print("")
    print("prosjek {0} izvora:".format(data.used_sources))
    print("  temperatura : {0} C  (min {1} / max {2})".format(
        data.temp_c, data.min_c, data.max_c
    ))
    print("  vjetar      : {0} km/h iz {1}".format(
        data.wind_kph, data.wind_dir or "?"
    ))
    print("  kisa        : {0}%".format(data.precip_prob))
    print("  vlaga       : {0}%".format(data.humidity))
    print("  stanje      : {0}  ({1})".format(data.condition_label, data.icon))
    if data.spread_c:
        print("  razilazenje : {0} C".format(data.spread_c))


if __name__ == "__main__":
    main()
