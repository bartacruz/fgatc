'''
Created on Apr 22, 2015

@author: bartacruz
'''
from django.shortcuts import render_to_response
from fgserver.models import Airport
from django.template.context import RequestContext

def map_view(request):
    icao=request.REQUEST.get('icao','SABE')
    airport = Airport.objects.get(icao=icao)
    return render_to_response('map/map.html',
                    {'title': 'Map','airport': airport},
                    context_instance=RequestContext(request))
