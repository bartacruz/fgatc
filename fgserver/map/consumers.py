'''
Created on 14 mar. 2019

@author: julio
'''
from channels.generic.websocket import WebsocketConsumer, JsonWebsocketConsumer
from fgserver import llogger, setInterval, units
from uuid import uuid4
from channels.layers import get_channel_layer
import json
from django.core.serializers import serialize
from fgserver.models import Aircraft, Airport
from asgiref.sync import async_to_sync
from datetime import timedelta
from django.utils import timezone

class Updater():
    thread = None
    
    @classmethod
    @setInterval(2)
    def update(cls):
        if not cls.thread:
            cls.thread=uuid4().hex
            
        least = timezone.now() - timedelta(seconds=10)    
        aircrafts = Aircraft.objects.filter(status__date__gte=least)
        airports = Airport.objects.filter(active=True)
        if not aircrafts.count() and not airports.count():
            return
        acfts = []
        for aircraft in aircrafts:
            acfts.append(aircraft)    
        message = {'type': 'aircrafts_update', 'Model':'Aircraft','data':json.loads(serialize('json',acfts)),'airports':json.loads(serialize('json',airports))}
        channel_layer = get_channel_layer()
        #llogger.debug("Updater: sending %s" % message)
        async_to_sync(channel_layer.group_send)("aircrafts",message)
        
        
class AircraftConsumer(JsonWebsocketConsumer):
    groups = ["aircrafts"]
    def connect(self):
        self.accept()
        if not Updater.thread:
            Updater.update()
        llogger.debug("Connect to %s. thread=%s" % (self,Updater.thread))
    
    def disconnect(self, code):
        llogger.debug("Disconnect from %s. thread=%s" % (self,Updater.thread))
        WebsocketConsumer.disconnect(self, code)
        
    def aircrafts_update(self,event):
        self.send_json(event,)

    def receive_json(self, content):
        llogger.debug("Receive from %s. thread=%s, data=%s" % (self,Updater.thread,content))
        

class StatePlaneConsumer(JsonWebsocketConsumer):
    groups = ["stateplanes"]

    def connect(self):
        self.accept()
        llogger.debug("Connect to %s" % self)
    
    def disconnect(self, code):
        llogger.debug("Disconnect from %s: %s" % (self,code))
        WebsocketConsumer.disconnect(self, code)
        
    def plane_update(self,event):
        self.send_json(event,)

    def receive_json(self, content):
        llogger.debug("Receive from %s. data=%s" % (self, content))
        
    @staticmethod
    def publish_plane(plane):
        ser = {'callsign': plane.aircraft.callsign,
               'state' : plane.state, 
               'position': plane.aircraft.get_position().get_array(),
               'altitude': plane.aircraft.altitude,
               'speed': plane.dynamics.props.speed/units.KNOTS,
               'vertical_speed': plane.dynamics.props.vertical_speed,
               'turn_rate': plane.dynamics.actual_turn_rate,
               'course': plane.dynamics.course,
               'pitch': 0,
               'roll': plane.dynamics.roll,
               'waypoint_name': plane.dynamics.waypoint.name if plane.dynamics.waypoint else None,
               'waypoint_heading': plane.dynamics.target_course if plane.dynamics.waypoint else None,
               'waypoint_distance': plane.dynamics.waypoint_distance if plane.dynamics.waypoint else None,
               'clearances': plane.clearances.__dict__,
               }
        message = {'type': 'plane_update', 'Model':'StatePlane','data':ser}
    
        channel_layer = get_channel_layer()
        #llogger.debug("Updater: sending %s" % message)
        async_to_sync(channel_layer.group_send)("stateplanes",message)

