'''
Created on 14 mar. 2019

@author: julio
'''

from . import consumers
from django.conf.urls import url
from fgserver import ai

websocket_urlpatterns = [
    url(r'^aircrafts$', consumers.AircraftConsumer),
    url(r'^stateplanes$', ai.consumers.StatePlaneConsumer),
]
