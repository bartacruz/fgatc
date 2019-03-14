# -*- encoding: utf-8 -*-
'''
Created on Apr 22, 2015

@author: bartacruz
'''
from django.urls.conf import path
from fgserver.tracker import views


urlpatterns = [
    path('callsign/',views.callsign, name="callsign"),
    
]
