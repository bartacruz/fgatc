# -*- encoding: utf-8 -*-
'''
Created on Apr 22, 2015

@author: bartacruz
'''
from django.shortcuts import render_to_response
from fgserver.models import Airport, Aircraft
from django.template.context import RequestContext
from fgserver.helper import Position, get_distance
import json
from django.http.response import HttpResponse
from django.core.serializers import serialize
from fgserver.ai.models import WayPoint

def map_view(request):
    icao=request.REQUEST.get('icao','SABE')
    airport = Airport.objects.get(icao=icao)
    return render_to_response('map/map.html',
                    {'title': 'Map','airport': airport},
                    context_instance=RequestContext(request))

def aircrafts(request):
    lat = float(request.REQUEST.get('lat'))
    lon = float(request.REQUEST.get('lon'))
    zoom = request.REQUEST.get('zoom',1)
    center = Position(lat,lon,0)
    aircrafts = Aircraft.objects.filter(state__gte=1)
    acfts = []
    for aircraft in aircrafts:
        dist = get_distance(center, aircraft.get_position())
        #print "map: dist=",dist,aircraft
        acfts.append(aircraft)
        #callsigns.append({"callsign":aircraft.callsign, "lat": float(aircraft.lat),"lon":float(aircraft.lon)})
    d = json.loads(serialize('json',acfts ))
    #print d    
    return HttpResponse(json.dumps({'aircrafts': d,}), mimetype='application/javascript;charset=utf-8"')

def flightplan(request):
    callsign = request.REQUEST.get('callsign')
    wps = WayPoint.objects.filter(flightplan__aircraft__callsign=callsign)
    d = json.loads(serialize('json',wps ))
    print callsign, d    
    return HttpResponse(json.dumps({'waypoints': d}), mimetype='application/javascript;charset=utf-8"')

    

