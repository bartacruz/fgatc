# -*- encoding: utf-8 -*-
'''
Created on Apr 16, 2015

@author: bartacruz
'''
from django.contrib import admin
from django.contrib.admin.options import ModelAdmin, TabularInline
from .models import  FlightPlan, WayPoint , FDM, FDMState
# from ajax_select.helpers import make_ajax_form
# from ajax_select.admin import AjaxSelectAdmin

admin.autodiscover()

def activate(modeladmin, request, queryset):
    queryset.update(enabled=True)
activate.short_description = "Activate selected"
def deactivate(modeladmin,request,queryset):
    queryset.update(enabled=False)

class WaypointInline(TabularInline):
    model=WayPoint
    extra=0

class FDMStateInline(TabularInline):
    model=FDMState
    extra=0
class FlightPlanAdmin(ModelAdmin):
    search_fields = ['name']
    list_display=('name','aircraft', 'departure','arrival','description','enabled')
    inlines = [WaypointInline]
    actions = [activate, deactivate]

class FDMAdmin(ModelAdmin):
    list_display=('name',)
    inlines = [FDMStateInline]

admin.site.register(FDM, FDMAdmin)
admin.site.register(FlightPlan, FlightPlanAdmin)
