# -*- encoding: utf-8 -*-
'''
Created on Apr 16, 2015

@author: bartacruz
'''
from django.contrib import admin
from django.contrib.admin.options import ModelAdmin, TabularInline
from fgserver.models import Airport, Runway, Aircraft

admin.autodiscover()

class RunwayInline(TabularInline):
    model=Runway
    extra=0
    
class AirportAdmin(ModelAdmin):
    search_fields = ['icao','name']
    list_display=('icao','name','lat','lon')
    inlines = [RunwayInline,]

class RunwayAdmin(ModelAdmin):
    search_fields = ['airport__icao','airport__name']
    list_display=('airport','name','bearing')

class AircraftAdmin(ModelAdmin):
    list_display=('callsign','lat','lon','altitude','last_request','last_order','state')

admin.site.register(Airport, AirportAdmin)
admin.site.register(Runway,RunwayAdmin)
admin.site.register(Aircraft,AircraftAdmin)