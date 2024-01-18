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

    if str(weatherCode) == "0":
        slikicaVrime = "sun.png"
    elif str(weatherCode) == "1" or str(weatherCode) == "2" or str(weatherCode) == "3":
        slikicaVrime = "cloud.png"
    elif str(weatherCode) == "45" or str(weatherCode) == "48":
        slikicaVrime = "magla.png"
    elif str(weatherCode) == "51" or str(weatherCode) == "52" or str(weatherCode) == "53":
        slikicaVrime = "rain.png"
    elif str(weatherCode) == "56" or str(weatherCode) == "57":
        slikicaVrime = "snow.png"
    elif str(weatherCode) == "61" or str(weatherCode) == "63" or str(weatherCode) == "65":
        slikicaVrime = "rain.png"
    elif str(weatherCode) == "66" or str(weatherCode) == "67":
        slikicaVrime = "rain.png"
    elif str(weatherCode) == "71" or str(weatherCode) == "73" or str(weatherCode) == "75" or str(weatherCode) == "77":
        slikicaVrime = "pahulja.png"
    elif str(weatherCode) == "80" or str(weatherCode) == "81" or str(weatherCode) == "82":
        slikicaVrime = "rain.png"
    elif str(weatherCode) == "85" or str(weatherCode) == "86":
        slikicaVrime = "pahulja.png"
    elif str(weatherCode) == "95" or str(weatherCode) == "96" or str(weatherCode) == "99":
        slikicaVrime = "thunder.png"
    #return HttpResponse("Hello, world. You're at the polls index." + str(kanta)) 
    return render(request, 'prognoza.html', {'current': current, 'max':max_, 'min':min_, 'wind_speed':wind_speed, 'kisa':kisa, 'slika':slikicaVrime, 'sviKodovi':sviKodovi})