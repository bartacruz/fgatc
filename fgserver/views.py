'''
Created on 14 mar. 2019

@author: julio
'''
from fgserver import settings
from django.shortcuts import render, redirect, render_to_response
from django.http.response import HttpResponseServerError, HttpResponse
from fgserver.models import Airport
import logging
from django.contrib.auth import authenticate, login, logout
from django.urls.base import reverse

llogger = logging.getLogger(__name__)

def home(request):
    template = getattr(settings,'FGATC_HOME_TEMPLATE','home.html')
    return render(request,template)
 
def activate_airport(request,icao,active=True, single=False):
    try:
        if single:
            Airport.objects.all().update(active=False)
        airport= Airport.objects.get(icao=icao)
        airport.active = active
        airport.save()
        response ="Airport %s activated: %s\n" % (icao, active,)
        if active:
            for comm in airport.comms.all():
                response = "%s%s %s\n" % (response,comm.frequency,comm.identifier)
        return HttpResponse(response)
    except Airport.DoesNotExist:
        return HttpResponseServerError("Airport %s does not exists\n" % icao)
    except:
        llogger.exception("Activating airport %s" % icao)
        return HttpResponseServerError("Error activating airport %s\n" % icao)

def clear(request):
    try:
        Airport.objects.all().update(active=False)
        return HttpResponse("Airports deactivated")
    except:
        return HttpResponseServerError("Error deactivating airports")

def fgatc_login(request):
    username = ''
    password = ''
    if request.POST:
        username = request.POST.get('username').strip().lower()
        password = request.POST.get('password')
        user = authenticate(username=username, password=password)
        if user is not None:
            if user.is_active:
                
                next_url = request.META['HTTP_REFERER'] or '/'
                login(request, user)
                return redirect(next_url)
    
    return redirect(reverse('home'))
        
def fgatc_logout(request):
    logout(request)
    return redirect('/')    

