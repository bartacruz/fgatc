import django
if __name__ == '__main__':
    django.setup()

import time
import pprint
from django.utils import timezone
from django.db.models import Count
from OSMPythonTools.overpass import Overpass, overpassQueryBuilder
import requests
import json
from django.contrib.gis.geos.point import Point
from fgserver.models import Airport, Aircraft
from fgserver.ai.models import TaxiWay, TaxiNode

def find_airport(icao):

    overpass = Overpass()
    result = overpass.query('nwr["icao"="%s"]; out body;' % icao)
    element = result.elements()[0]
    print("ID",element.id(), element.areaId())
    query = overpassQueryBuilder(area=element.areaId(),elementType="way,node", selector='"aeroway"="taxiway"',out="body")
    ways = overpass.query(query)
    for element in ways.elements():
        print(element.id(),element.tags(), element.nodes())

def fetch_taxiways(icao):
    airport = Airport.objects.get(icao=icao)
    overpass_url = "http://overpass-api.de/api/interpreter"

    overpass_query = """
[out:json][timeout:25];
area["icao"="%s"]->.apt;
(
  way(area.apt)["aeroway"="taxiway"];
  way(area.apt)["aeroway"="parking_position"];
  nwr(area.apt)["aeroway"="holding_position"];
  way(area.apt)["aeroway"="runway"];
);
out geom;
""" % icao

    print(overpass_query)
    response = requests.get(overpass_url, 
                        params={'data': overpass_query})
    data = response.json()
    return data
def save_taxiways(icao,data):
    with open('../data/%s.json' % icao, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_taxiways(icao):
    with open('../data/%s.json' % icao, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data

def get_taxiways(icao, data=None):
    airport = Airport.objects.get(icao=icao)
    data = data or fetch_taxiways(icao)

    nodes = {}
    ways = {}
    hold = []
    airport.taxi_ways.all().delete()
    airport.taxinodes.all().delete()
    for element in data['elements']:
        if element.get("type") == "node":
            print("found node", element)
            if element.get('tags').get('aeroway') == 'holding_position':
                hold.append(element.get("id"))
            continue
        way_name = element.get('tags').get('ref',element.get('id'))
        taxiway = ways.get(way_name)
        if not taxiway:
            taxiway = airport.taxi_ways.create(name=way_name, parking = element.get('tags').get('aeroway')=='parking_position')
            ways[way_name]=taxiway

        i=0
        parent=None

        while i < len(element['nodes']):
            node_id = element['nodes'][i]
            node = nodes.get(node_id)
            if not node:
                name = element['nodes'][i]
                geom = element['geometry'][i]
                point = Point(geom.get('lon'),geom.get('lat'))
                on_rwy = airport.on_runway(point)
                short = name in hold
                node = taxiway.nodes.create(airport=airport, name=name, point=point, on_runway=on_rwy, short=short)
                nodes[node_id]=node
            else:
                taxiway.nodes.add(node)
            
            node.adjacent_to(parent)
            parent = node
            i+=1
    # for h in hold:
    #     print("setting hold to ",nodes.get(h).name, nodes.get(h).point)
    #     nodes.get(h).short=True


    #show_nodes(icao,airport)
    print("hold", hold)
    print("Airport shorts",[i.name for i in airport.taxinodes.filter(short=True)])
    print("Airport runway",[i.name for i in airport.taxinodes.filter(on_runway=True)])
    print("holds", [i.name for i in nodes.values() if i.short])
    print("rwy", [i.name for i in nodes.values() if i.on_runway])
    
    
        
def show_intersections(icao, airport=None):
    airport = airport or Airport.objects.get(icao=icao)
    for node in airport.taxinodes.annotate(adjacent_count=Count('adjacents')).filter(adjacent_count__gte=3):
        print(node.name,[i.name for i in node.taxiway_set.all()],[i.name for i in node.adjacents.all()], node.point)

def show_nodes(icao,airport=None):
    airport = airport or Airport.objects.get(icao=icao)
    print("nodes")
    for node in airport.taxinodes.all():
        print(node.name,node.on_runway, node.short, [i.name for i in node.taxiway_set.all()],[i.name for i in node.adjacents.all()], node.point)
    print("ways")
    for way in airport.taxi_ways.all().order_by('name'):
        print(way.name, way.parking, [i.name for i in way.nodes.all()])

def check_on_runway(icao):
    airport = Airport.objects.get(icao=icao)
    for node in airport.taxinodes.all():
        node.on_runway = airport.on_runway(node.point)
        print(node.name,node.on_runway, node.point)
def t2():
    airport = Airport.objects.get(icao="SAAR")
    node = TaxiNode.objects.get(name="286498942")
    rwy = airport.runways.first()
    print("rwy",rwy._boundaries)
    print("node",node.name,node.on_runway, node.point)
    print("is?",rwy.on_runway(node.point))

def test_path(icao,plane):
    airport = Airport.objects.get(icao=icao)
    aircraft = Aircraft.objects.get(name=plane)



if __name__ == '__main__':
    #show_nodes("SAAR")
    #show_intersections("SAAR")
    # data = fetch_taxiways("SAAR")
    # save_taxiways("SAAR", data)
    data = load_taxiways("SAAR")
    get_taxiways("SAAR", data)
    # check_on_runway("SAAR")
    
