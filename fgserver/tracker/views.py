'''
Created on 30 de abr. de 2017

@author: julio
'''
from django.shortcuts import render
from fgserver.models import Aircraft

def home(request):
    callsigns = list(Aircraft.objects.all().values_list('callsign',flat=True))
    return render(request,'tracker/home.html', {'callsigns':callsigns})
    
def callsign(request,callsign=None):
    return render(request,'tracker/callsign.html',
                    {'title': 'Callsign %s' % callsign,'callsign':callsign})

