import requests 
r = requests.get('https://api.open-meteo.com/v1/forecast?latitude=45.32154636314539&longitude=14.473822849484131&current=temperature_2m')
print(r.json())


print(requests.get('http://api.weatherapi.com/v1/current.json?key=f66550f548914444b74191312241101&q=45.32154636314539, 14.473822849484131&aqi=no').json())