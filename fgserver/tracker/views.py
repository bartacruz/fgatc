'''
Created on 30 de abr. de 2017

@author: julio
'''
from django.shortcuts import render_to_response
from django.template.context import RequestContext

def callsign(request):
    callsign=request.GET.get('callsign',None)
    return render_to_response('tracker/callsign.html',
                    {'title': 'Callsign %s' % callsign,'callsign':callsign},
                    context_instance=RequestContext(request))

