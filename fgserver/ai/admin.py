# -*- encoding: utf-8 -*-
'''
Created on Apr 16, 2015

@author: bartacruz
'''
from django.contrib import admin
from django.contrib.admin.options import ModelAdmin, TabularInline
from fgserver.ai.models import Circuit, WayPoint, FlightPlan
from ajax_select.helpers import make_ajax_form
from ajax_select.admin import AjaxSelectAdmin

admin.autodiscover()

def activate(modeladmin, request, queryset):
    queryset.update(enabled=True)
activate.short_description = "Activate selected"
def deactivate(modeladmin,request,queryset):
    queryset.update(enabled=False)

class WaypointInline(TabularInline):
    model=WayPoint
    extra=0

class CircuitInline(TabularInline):
    model=Circuit
    extra=0

class FlightPlanAdmin(ModelAdmin):
    search_fields = ['name']
    list_display=('name','description', 'aircraft','enabled')
    inlines = [WaypointInline]
    actions = [activate, deactivate]
    
class CircuitAdmin(AjaxSelectAdmin):
    list_display=('name','airport','description','radius','altitude','enabled')
    search_fields = ['name','airport__icao','airport__name']
    inlines = [WaypointInline]
    actions = [activate, deactivate]
    
    form = make_ajax_form(Circuit, {
        'airport': 'airports'
        })

admin.site.register(FlightPlan, FlightPlanAdmin)
admin.site.register(Circuit, CircuitAdmin)