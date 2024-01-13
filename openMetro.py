import requests 
r = requests.get('https://api.open-meteo.com/v1/forecast?latitude=45.32154636314539&longitude=14.473822849484131&current=temperature_2m')
print(r.json())


print(requests.get('http://api.weatherapi.com/v1/current.json?key=43ad9cc8b1ae40f08e6191643241301&q=45.32154636314539, 14.473822849484131&aqi=no').json())


# air visual but it's garbage
#74ae249c-ff7c-49ea-9842-52c1d8558889
#print(requests.get('http://api.airvisual.com/v2/city?city=Los%20Angeles&state=California&country=USA&key=74ae249c-ff7c-49ea-9842-52c1d8558889').json())


#print(requests.get('https://api.tomorrow.io/v4/weather/forecast?location=45.32154636314539,14.473822849484131&apikey=DVKXawhTxQZ65SrIa6LgGngTTEnQqLIh').json())

