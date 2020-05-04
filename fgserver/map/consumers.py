'''
Created on 14 mar. 2019

@author: julio
'''
from channels.generic.websocket import WebsocketConsumer, JsonWebsocketConsumer
from fgserver import llogger, setInterval
from uuid import uuid4
from channels.layers import get_channel_layer
import json
from django.core.serializers import serialize
from fgserver.models import Aircraft, AircraftStatus, Airport
from asgiref.sync import async_to_sync
from fgserver.helper import Quaternion, Vector3D, get_heading, cart2geod
from datetime import timedelta
from django.utils import timezone

class Updater():
    thread = None
    
    @classmethod
    @setInterval(5)
    def update(cls):
        if not cls.thread:
            cls.thread=uuid4().hex
            
        least = timezone.now() - timedelta(seconds=10)    
        Aircraft.objects.all().update(state=0)
        statuses = AircraftStatus.objects.filter(date__gte=least)
        for status in statuses:
            position = cart2geod(status.position)
            status.aircraft.lat = position[0]
            status.aircraft.lon = position[1]
            status.aircraft.altitude = position[2]
            status.aircraft.heading = round(get_heading(status.position, status.orientation),2)
            status.aircraft.state=1
            status.aircraft.updated = timezone.now()
            status.aircraft.save()
        for airport in Airport.objects.filter(active=True):
            try:
                aircraft = Aircraft.objects.get(callsign=airport.icao)
                aircraft.state = 1;
                aircraft.save();
            except:
                pass

        aircrafts = Aircraft.objects.filter(state__gte=1)
        if not aircrafts.count():
            return
        acfts = []
        for aircraft in aircrafts:
            acfts.append(aircraft)    
        message = {'type': 'aircrafts_update', 'Model':'Aircraft','data':json.loads(serialize('json',acfts))}
        channel_layer = get_channel_layer()
        llogger.debug("Updater: sending %s" % message)
        async_to_sync(channel_layer.group_send)("aircrafts",message)
        
        
class AircraftConsumer(JsonWebsocketConsumer):
    thread = None
    groups = ["aircrafts"]
    def connect(self):
        self.accept()
        if not Updater.thread:
            Updater.update()
        llogger.debug("Connect to %s. thread=%s" % (self,self.thread))
    
    def disconnect(self, code):
        llogger.debug("Disconnect from %s. thread=%s" % (self,self.thread))
        WebsocketConsumer.disconnect(self, code)
        
    def aircrafts_update(self,event):
        self.send_json(event,)

    def receive_json(self, content):
        llogger.debug("Receive from %s. thread=%s, data=%s" % (self,self.thread,content))
        
        
    