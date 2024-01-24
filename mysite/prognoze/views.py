from django.http import HttpResponse, request
import requests
from django.shortcuts import render

def op(request):
    dude =  s = (
    "https://api.open-meteo.com/v1/forecast?latitude=45.32154636314539&longitude=14.473822849484131&"
    "current=weather_code,temperature_2m,wind_speed_10m,wind_direction_10m&"
    "hourly=weather_code,temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation_probability"
    "&forecast_days=1"
    )

    import datetime
    now = datetime.datetime.now()
    #print(now.year, now.month, now.day, now.hour, now.minute, now.second)

    r = requests.get(dude)
    print(r.json())
    kanta = r.json()
    current = r.json()['current']['temperature_2m']
    wind_speed = r.json()['current']['wind_speed_10m']
    min_ = min(kanta['hourly']['temperature_2m']) 
    max_ = max(kanta['hourly']['temperature_2m']) 
    kisa = kanta['hourly']['precipitation_probability'][now.hour]

    
    weatherCode = r.json()['current']['weather_code']
    sviKodovi = r.json()['hourly']['weather_code']

    slikicaVrime = "neznamovrime.png"

    #todo: ma neki enum ili nec ca ni ovako umufljeno
    if int(weatherCode) == 0:
        slikicaVrime = "sun.png"
    elif int(weatherCode) <= 3:
        slikicaVrime = "cloud_sun.png"
    elif int(weatherCode) <= 48:
        slikicaVrime = "magla.png"
    elif int(weatherCode) <= 53:
        slikicaVrime = "rain.png"
    elif int(weatherCode) <= 57:
        slikicaVrime = "rain_snow.png"
    elif int(weatherCode) <= 65:
        slikicaVrime = "rain.png"
    elif int(weatherCode) <= 67:
        slikicaVrime = "rain_snow.png"
    elif int(weatherCode) <= 77:
        slikicaVrime = "pahulja.png"
    elif int(weatherCode) <= 82:
        slikicaVrime = "rain.png"
    elif int(weatherCode) <= 86:
        slikicaVrime = "pahulja.png"
    elif int(weatherCode) <= 99:
        slikicaVrime = "rain_thunder.png"
    #return HttpResponse("Hello, world. You're at the polls index." + str(kanta)) 
    return render(request, 'prognoza.html', {'current': current, 'max':max_, 'min':min_, 'wind_speed':wind_speed, 'kisa':kisa, 'slika':slikicaVrime, 'sviKodovi':sviKodovi})