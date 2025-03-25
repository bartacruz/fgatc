import sys
import django
django.setup()
from fgserver.models import Airport
from urllib import request
import requests
import xml.etree.ElementTree as E
base_url = 'https://api.met.no/weatherapi/locationforecast/2.0/complete?lat={:.2f}&lon={:.2f}&altitude={:d}'
from datetime import datetime
def get_metar(icao):
    tree = E.parse('{}.xml'.format(icao))
    root = tree.getroot()
    print("root:",root)
    print(child.find("time"))
#     for child in root.iter("time"):
#         data = child.attrib
#         print(data)
#         f = """"
#         <location altitude="72" latitude="-38.48" longitude="-58.81">
#         <temperature id="TTT" unit="celsius" value="25.1"></temperature>
#         <windDirection id="dd" deg="332.4" name="NW"></windDirection>
#         <windSpeed id="ff" mps="5.2" beaufort="3" name="Lett bris"></windSpeed>
#         <humidity unit="percent" value="65.8"></humidity>
#         <pressure id="pr" unit="hPa" value="1017.3"></pressure>
#         <cloudiness id="NN" percent="0.0"></cloudiness>
#         <fog id="FOG" percent="0.0"></fog>
#         <lowClouds id="LOW" percent="0.0"></lowClouds>
#         <mediumClouds id="MEDIUM" percent="0.0"></mediumClouds>
#         <highClouds id="HIGH" percent="0.0"></highClouds>
#         <dewpointTemperature id="TD" unit="celsius" value="18.1"></dewpointTemperature>
#       </location>
# """     
#         loc = child.find("location")
#         for i in loc:
#              print(i)
#         data["temp"] = loc.find("temperature").attrib #value
#         data["wind_dir"] = loc.find("windDirection").attrib #deg
#         data["wind_speed"] = loc.find("windSpeed").attrib #mps*1.95
#         data["pressure"] = loc.find("pressure").attrib #value*0.02953
#         print(data)
def get_clouds(details):
    def label(val):
        ret = "CLR"
        if val > 70:
            ret="OVC"
        elif val > 50:
            ret="BKN"
        elif val > 10:
            ret = "SCT"
        return ret
    cf = details["cloud_area_fraction"]
    if cf < 15:
        return "CLR"
    clouds = ""
    cl = details["cloud_area_fraction_low"]
    cm = details["cloud_area_fraction_medium"]
    ch = details["cloud_area_fraction_high"]
    if ch > 10:
        clouds = "{}200".format(label(ch))
    if cm > 10 or  cl < 10:
        clouds = "{}100 {}".format(label(cm), clouds)
    if cl >= 10 or cm >= 10:
        clouds = "{}030 {}".format(label(cl),clouds)

    return clouds

def encode_metar(icao):
    airport = Airport.objects.get(icao=icao)
    url = base_url.format(airport.lat,airport.lon,airport.altitude)        
    print(url);
    data = {}
    headers = {'User-Agent': 'FG Metar Encoder v1 (bartacruz@gmail.com)'}
    response = requests.get(url, headers=headers)
    #print(response.content)
    data = response.json()
    timeserie = data["properties"]["timeseries"][0]
    print(timeserie)
    d = datetime.strptime(timeserie["time"],"%Y-%m-%dT%H:%M:%SZ")
    details = (timeserie["data"]["instant"]["details"])
    wd = int(details["wind_from_direction"]/10)*10
    ws = details["wind_speed"] *1.95
    temp = details["air_temperature"]
    dew = details["dew_point_temperature"]
    press = details["air_pressure_at_sea_level"]
    
    clouds = get_clouds(details)

    metar = 'METAR {:s} {:02.0f}{:02.0f}{:02.0f}Z {:03.0f}{:02.0f}KT 9999 {} {:02.0f}/{:02.0f} Q{:.0f}'.format(icao,d.day,d.hour,d.minute, wd,ws,clouds,temp,dew,press)
    print(metar)
    return metar;
    

if __name__ == '__main__':
    encode_metar(sys.argv[1])
    #get_metar(sys.argv[1])
