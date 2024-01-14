from django.http import HttpResponse, request
import requests
from django.shortcuts import render

def op(request):
    dude =  s = (
    "https://api.open-meteo.com/v1/forecast?latitude=52.52&longitude=13.41&"
    "current=temperature_2m,wind_speed_10m,wind_direction_10m&"
    "hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation_probability"
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
    kisa = kanta['hourly']['precipitation_probability'][now.hour    ]
    #return HttpResponse("Hello, world. You're at the polls index." + str(kanta)) 
    return render(request, 'prognoza.html', {'current': current, 'max':max_, 'min':min_, 'wind_speed':wind_speed, 'kisa':kisa})