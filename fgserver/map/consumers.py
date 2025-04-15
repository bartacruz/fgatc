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
from fgserver.ai.models import FlightPlan
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
        message = {'type': 'update_consumer','data':{}}
        channel_layer = get_channel_layer()
        #llogger.debug("Updater: sending %s" % message)
        async_to_sync(channel_layer.group_send)("aircrafts",message)
        
        
class AircraftConsumer(JsonWebsocketConsumer):
    groups = ["aircrafts"]
    def connect(self):
        self.accept()
        self.dirty = True
        if not Updater.thread:
            Updater.update()
        llogger.debug("Connect to %s. thread=%s" % (self,Updater.thread))
    
    def disconnect(self, code):
        llogger.debug("Disconnect from %s. thread=%s" % (self,Updater.thread))
        WebsocketConsumer.disconnect(self, code)
    
    def update_consumer(self,event):
        self.update_aircrafts()
        # Update airports only if consumer changed location or options
        if self.dirty:
            self.update_airports()
            self.update_flightplans()
            self.dirty = False
        
    def update_aircrafts(self):
        least = timezone.now() - timedelta(seconds=10)    
        aircrafts = Aircraft.objects.filter(status__date__gte=least)
        if not aircrafts.count(): 
            return
        event = {'type': 'aircrafts_update', 'Model':'Aircraft','data':json.loads(serialize('json',aircrafts)) }
        self.send_json(event,)

    def update_airports(self):
        airports = Airport.objects.filter(lat__gte=self.bounds[1], lon__gte=self.bounds[0], lat__lte=self.bounds[3],lon__lte=self.bounds[2])
        if not self.show_airports:
            airports = airports.filter(active=True)

        print("airports",airports)
        message = {'type': 'airports_update', 'Model':'Airport','data':json.loads(serialize('json',airports))}
        self.send_json(message,)

    def aircrafts_update(self,event):
        self.send_json(event,)
    
    def update_flightplans(self):
        aircrafts = Aircraft.objects.filter(lat__gte=self.bounds[1], lon__gte=self.bounds[0], lat__lte=self.bounds[3],lon__lte=self.bounds[2])
        for a in aircrafts:
            plan= a.plans.filter(enabled=True).first()
            if plan:
                wps = plan.waypoints.all().order_by('id')
                ser = {'callsign': plan.aircraft.callsign,
                    'wps': json.loads(serialize('json',wps))
                    }
                self.update_flightplan(ser)

    def update_flightplan(self,event):
        data = event.get('data',event)
        message = {'type': 'flightplan_update', 'Model':'FlightPlan','data':data}
        self.send_json(message,)

    def receive_json(self, content):
        llogger.debug("Receive from %s. thread=%s, data=%s" % (self,Updater.thread,content))
        self.lon = content.get('lon')
        self.lat = content.get('lat')
        self.zoom = content.get("zoom")
        self.bounds = content.get("bounds").split(",")
        self.show_airports = content.get('show_airports',False)
        self.dirty = True # new coords, need update.
            

    @staticmethod
    def publish_plan(plan):
        wps = plan.waypoints.all().order_by('id')
        # d = json.loads(serialize('json',wps ))
        ser = {'callsign': plan.aircraft.callsign,
               'wps': json.loads(serialize('json',wps))
               }
        
        message = {'type': 'update_flightplan','data':ser}
        
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)("aircrafts",message)   
