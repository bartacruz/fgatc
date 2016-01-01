# -*- encoding: utf-8 -*-
'''
Created on Apr 16, 2015

@author: bartacruz
'''
from django.contrib import admin
from django.contrib.admin.options import ModelAdmin, TabularInline
from fgserver.ai.models import Circuit, WayPoint, FlightPlan

admin.autodiscover()

class WaypointInline(TabularInline):
    model=WayPoint
    extra=0

class CircuitInline(TabularInline):
    model=Circuit
    extra=0

class FlightPlanAdmin(ModelAdmin):
    search_fields = ['name']
    list_display=('name','description')
    inlines = [WaypointInline]

class CircuitAdmin(ModelAdmin):
    list_display=('name','airport','description','radius','altitude','enabled')
    search_fields = ['name','airport__icao','airport__name']
    inlines = [WaypointInline]

admin.site.register(FlightPlan, FlightPlanAdmin)
admin.site.register(Circuit, CircuitAdmin)