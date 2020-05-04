# -*- encoding: utf-8 -*-
'''
Created on Apr 22, 2015

@author: bartacruz
'''
from django.shortcuts import render
from fgserver.models import Airport, Aircraft
import json
from django.http.response import HttpResponse, JsonResponse
from django.core.serializers import serialize
from fgserver.ai.models import WayPoint

def map_view(request):
    icao=request.GET.get('icao','SABE')
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

    

