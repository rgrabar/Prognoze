from django.http import HttpResponse, request
import requests
from django.shortcuts import render

# ne znan kako ovo lipje nacinit :(
weather_images = {
    0:  'sun.png',                               # Clear sky
    1:  'cloud_sun.png',                         # Mainly clear, partly cloudy, and overcast
    2:  'cloud_sun.png',                         # Mainly clear, partly cloudy, and overcast
    3:  'cloud.png',                         # Mainly clear, partly cloudy, and overcast
    45: 'magla.png',
    48: 'magla.png',
    51: 'rain.png',
    53: 'rain.png',
    55: 'rain.png',
    56: 'rain_snow.png',
    57: 'rain_snow.png',
    61: 'rain.png',
    63: 'rain.png',
    65: 'rain.png',
    66: 'rain_snow.png',
    67: 'rain_snow.png',
    71: 'pahulja.png',
    73: 'pahulja.png',
    75: 'pahulja.png',
    77: 'pahulja.png',
    80: 'rain.png',
    81: 'rain.png',
    82: 'rain.png',
    85: 'pahulja.png',
    86: 'pahulja.png',
    95: 'thunder.png',
    96: 'rain_thunder.png',
    99: 'rain_thunder.png',
}

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

    if int(weatherCode) in weather_images:
        slikicaVrime = weather_images[int(weatherCode)]

    return render(request, 'prognoza.html', {'current': current, 'max':max_, 'min':min_, 'wind_speed':wind_speed, 'kisa':kisa, 'slika':slikicaVrime, 'sviKodovi':sviKodovi})