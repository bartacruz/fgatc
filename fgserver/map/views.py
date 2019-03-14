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
    icao=request.GET.get('icao','SABE')
    airport = Airport.objects.get(icao=icao)
    return render_to_response('map/map.html',
                    {'title': 'Map','airport': airport})

def aircrafts(request):
    aircrafts = Aircraft.objects.filter(state__gte=1)
    acfts = []
    for aircraft in aircrafts:
        acfts.append(aircraft)
    d = json.loads(serialize('json',acfts ))
    return HttpResponse(json.dumps({'aircrafts': d,}), mimetype='application/javascript;charset=utf-8"')

def flightplan(request):
    callsign = request.GET.get('callsign')
    wps = WayPoint.objects.filter(flightplan__aircraft__callsign=callsign)
    d = json.loads(serialize('json',wps ))
    return HttpResponse(json.dumps({'waypoints': d}), mimetype='application/javascript;charset=utf-8"')

    

