# -*- encoding: utf-8 -*-
'''
Created on Apr 16, 2015

@author: bartacruz
'''
from django.contrib import admin
from django.contrib.admin.options import ModelAdmin, TabularInline
from fgserver.atc.models import Controller, ATC, Tag
from django.contrib.admin.decorators import register

admin.autodiscover()

class ControllerInline(TabularInline):
    model=Controller
    extra=0

class TagInline(TabularInline):
    model=Tag
    extra=0

@register(ATC)
class ATCAdmin(ModelAdmin):
    search_fields = ['airport__name']
    list_display=('airport','airport_name')
    inlines = [ControllerInline]

@register(Controller)
class ControllerAdmin(ModelAdmin):
    search_fields = ['atc__airport__name']
    list_display=('atc','name')

@register(Tag)
class TagAdmin(ModelAdmin):
    search_fields = ['airport__name']
    list_display=('airport','aircraft')




