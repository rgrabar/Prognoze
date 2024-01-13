from django.http import HttpResponse, request
import requests
from django.shortcuts import render

def op(request):
    r = requests.get('https://api.open-meteo.com/v1/forecast?latitude=52.52&longitude=13.41&current=temperature_2m,wind_speed_10m&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m&forecast_days=1')
    print(r.json())
    kanta = r.json()
    current = r.json()['current']['temperature_2m']
    min_ = min(kanta['hourly']['temperature_2m']) 
    max_ = max(kanta['hourly']['temperature_2m']) 
    #return HttpResponse("Hello, world. You're at the polls index." + str(kanta)) 
    return render(request, 'prognoza.html', {'current': current, 'max':max_, 'min':min_})