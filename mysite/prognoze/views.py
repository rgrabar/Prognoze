from django.http import HttpResponse, request
import requests
from django.shortcuts import render
import json
# ne znan kako ovo lipje nacinit :(
weather_images = {
    0:  'sun.png',                               # Clear sky
    1:  'cloud_sun.png',                         # Mainly clear
    2:  'cloud_sun.png',                         # partly cloudy
    3:  'cloud.png',                             # overcast
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

    weather_api_r = requests.get("http://api.weatherapi.com/v1/forecast.json?key=43ad9cc8b1ae40f08e6191643241301&q=45.32154636314539,14.473822849484131&days=1&aqi=no&alerts=no").json()
    #print(weather_api_r)
    current_temp_weather_api = weather_api_r['current']['temp_c']
    current_wind_weather_api = weather_api_r['current']['wind_kph']
    current_code_weather_api = weather_api_r['current']['condition']['code']
    #print("!!!!!!!!! ", current_code_weather_api)

    garbo = weather_api_r['forecast']

    print(garbo['forecastday'][0]['hour'][0]['time'])





    open_metro_link = (
    "https://api.open-meteo.com/v1/forecast?latitude=45.32154636314539&longitude=14.473822849484131&"
    "current=weather_code,temperature_2m,wind_speed_10m,wind_direction_10m&"
    "hourly=weather_code,temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation_probability"
    "&forecast_days=1"
    )

    import datetime
    now = datetime.datetime.now()
    #print(now.year, now.month, now.day, now.hour, now.minute, now.second)

    open_metro_r = requests.get(open_metro_link).json()
    current = open_metro_r['current']['temperature_2m']
    wind_speed = open_metro_r['current']['wind_speed_10m']
    weatherCode = open_metro_r['current']['weather_code']

    sviKodovi = open_metro_r['hourly']['weather_code']
    min_ = min(open_metro_r['hourly']['temperature_2m']) 
    max_ = max(open_metro_r['hourly']['temperature_2m']) 
    kisa = open_metro_r['hourly']['precipitation_probability'][now.hour]

    slikicaVrime = "neznamovrime.png"

    if int(weatherCode) in weather_images:
        slikicaVrime = weather_images[int(weatherCode)]

    return render(request, 'prognoza.html', {'current': current, 'max':max_, 'min':min_, 'wind_speed':wind_speed, 'kisa':kisa, 'slika':slikicaVrime, 'sviKodovi':sviKodovi})