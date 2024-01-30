from django.http import HttpResponse, request
import requests
from django.shortcuts import render
import json
# ne znan kako ovo lipje nacinit :(
weather_images = {
    0:  'sun.png',                               # Clear sky
    1:  'cloud_sun.png',                         # Mainly clear
    2:  'cloud_sun.png',                         # Partly cloudy
    3:  'cloud.png',                             # Overcast
    45: 'magla.png',                             # Fog
    48: 'magla.png',                             # Depositing rime fog
    51: 'rain.png',                              # Light drizzle
    53: 'rain.png',                              # Moderate drizzle
    55: 'rain.png',                              # Dense drizzle
    56: 'rain_snow.png',                         # Light freezing drizzle
    57: 'rain_snow.png',                         # Dense freezing drizzle
    61: 'rain.png',                              # Slight rain
    63: 'rain.png',                              # Moderate rain
    65: 'rain.png',                              # Heavy rain
    66: 'rain_snow.png',                         # Light freezing rain
    67: 'rain_snow.png',                         # Heavy freezing rain
    71: 'pahulja.png',                           # Slight snow fall
    73: 'pahulja.png',                           # Moderate snow fall
    75: 'pahulja.png',                           # Heavy snow fall
    77: 'pahulja.png',                           # Snow grains
    80: 'rain.png',                              # Slight rain shower
    81: 'rain.png',                              # Moderate rain shower
    82: 'rain.png',                              # Violent rain shower
    85: 'pahulja.png',                           # Slight snow shower
    86: 'pahulja.png',                           # Heavy snow shower
    95: 'thunder.png',                           # Thunderstorm slight/moderate
    96: 'rain_thunder.png',                      # Thunderstorm with slight hail 
    99: 'rain_thunder.png',                      # Thunderstorm with heavy hail
}

def op(request):

    import datetime
    now = datetime.datetime.now()

    weather_api_r = requests.get("http://api.weatherapi.com/v1/forecast.json?key=43ad9cc8b1ae40f08e6191643241301&q=45.32154636314539,14.473822849484131&days=1&aqi=no&alerts=no").json()
    #print(weather_api_r)
    current_temp_weather_api = weather_api_r['current']['temp_c']
    current_wind_weather_api = weather_api_r['current']['wind_kph']
    current_code_weather_api = weather_api_r['current']['condition']['code']
    #print("!!!!!!!!! ", current_code_weather_api)

    garbo = weather_api_r['forecast']

    #print(garbo['forecastday'][0]['hour'][0]['condition']['code'])

    all_codes_weather_api = []

    min_weather_api = float('inf')
    max_weather_api = float('-inf')

    for x in garbo['forecastday'][0]['hour']:
        all_codes_weather_api.append(x['condition']['code'])
        min_weather_api = min(min_weather_api, x['temp_c'])
        max_weather_api = max(max_weather_api, x['temp_c'])

    kisa_weather_api = weather_api_r['forecast']['forecastday'][0]['hour'][now.hour]['chance_of_rain']

    #print(kisa_weather_api)
    #print(min_weather_api)
    #print(max_weather_api)



    open_metro_link = (
    "https://api.open-meteo.com/v1/forecast?latitude=45.32154636314539&longitude=14.473822849484131&"
    "current=weather_code,temperature_2m,wind_speed_10m,wind_direction_10m&"
    "hourly=weather_code,temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation_probability"
    "&forecast_days=1"
    )

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