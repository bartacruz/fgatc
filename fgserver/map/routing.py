'''
Created on 14 mar. 2019

@author: julio
'''

from . import consumers
from django.urls import path
from fgserver.ai import consumers as cc

websocket_urlpatterns = [
    path('aircrafts', consumers.AircraftConsumer.as_asgi()),
    path('stateplanes', cc.StatePlaneConsumer.as_asgi()),
]
