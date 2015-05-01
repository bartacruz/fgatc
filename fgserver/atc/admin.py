# -*- encoding: utf-8 -*-
'''
Created on Apr 16, 2015

@author: bartacruz
'''
from django.contrib import admin
from django.contrib.admin.options import ModelAdmin, TabularInline
from fgserver.ai.models import Circuit, WayPoint, FlightPlan
from fgserver.atc.models import Controller, ATC, Tag

admin.autodiscover()

class ControllerInline(TabularInline):
    model=Controller
    extra=0

class TagInline(TabularInline):
    model=Tag
    extra=0

class ATCAdmin(ModelAdmin):
    search_fields = ['airport__name']
    list_display=('airport','airport_name')
    inlines = [ControllerInline,TagInline]

class ControllerAdmin(ModelAdmin):
    search_fields = ['atc__airport__name']
    list_display=('atc','name')

admin.site.register(ATC, ATCAdmin)
admin.site.register(Controller, ControllerAdmin)
