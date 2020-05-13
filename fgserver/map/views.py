# -*- encoding: utf-8 -*-
'''
Created on Apr 22, 2015

@author: bartacruz
'''
from django.shortcuts import render
from fgserver.models import Airport, Aircraft, Runway
import json
from django.http.response import HttpResponse, JsonResponse
from django.core.serializers import serialize
from fgserver.ai.models import WayPoint
from fgserver.helper import move, normalize
from django.conf import settings

def map_view(request):
    icao=request.GET.get('icao',getattr(settings,'FGATC_MAP_DEFAULT_ICAO','SABE'))
    airport = Airport.objects.get(icao=icao)
    context = {'title': 'Map','airport': airport}
    return render(request,'map/map.html',context)

def aircrafts(request):
    aircrafts = Aircraft.objects.filter(state__gte=1)
    acfts = []
    for aircraft in aircrafts:
        acfts.append(aircraft)
    d = json.loads(serialize('json',acfts ))
    return HttpResponse(json.dumps({'aircrafts': d,}), content_type='application/json;charset=utf-8"')

def flightplan(request):
    callsign = request.GET.get('callsign')
    wps = WayPoint.objects.filter(flightplan__aircraft__callsign=callsign).order_by('id')
    d = json.loads(serialize('json',wps ))
    return JsonResponse({'waypoints': d})

def runway(request):
    icao = request.GET.get("icao")
    runway = Runway.objects.filter(airport__icao=icao).first()
    bounds = runway._boundaries
    bounds_p = [[i[1],i[0]] for i in list(bounds[0])]
    rwystart = move(runway.position(), normalize(runway.bearing-180), runway.length/2,runway.position().z)
    print("on runway",runway.on_runway(rwystart))
    return JsonResponse({'boundaries': bounds_p, 'start': rwystart.get_array()})
    
        

