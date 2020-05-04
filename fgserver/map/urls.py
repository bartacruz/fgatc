# -*- encoding: utf-8 -*-
'''
Created on Apr 22, 2015

@author: bartacruz
'''
from django.urls.conf import path
from fgserver.map import views
urlpatterns = [
    
    path('', views.map_view, name='map_view'),
    path('aircrafts/', views.aircrafts, name='aircrafts'),
    path('flightplan/', views.flightplan, name='flightplan'),
]
