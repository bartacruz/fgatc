# -*- encoding: utf-8 -*-
'''
Created on Apr 16, 2015

@author: julio
'''
from django.contrib import admin
from django.contrib.admin.options import ModelAdmin, TabularInline
from fgserver.models import Airport, Runway, Aircraft

admin.autodiscover()

class RunwayInline(TabularInline):
    model=Runway
    extra=0
    
class AirportAdmin(ModelAdmin):
    list_display=('icao','name','lat','lon')
    inlines = [RunwayInline,]

class RunwayAdmin(ModelAdmin):
    list_display=('airport','name','bearing')

class AircraftAdmin(ModelAdmin):
    list_display=('callsign','lat','lon','altitude','last_request','last_order','state')

admin.site.register(Airport, AirportAdmin)
admin.site.register(Runway,RunwayAdmin)
admin.site.register(Aircraft,AircraftAdmin)