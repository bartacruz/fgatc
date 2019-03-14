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
from fgserver.models import Aircraft
from asgiref.sync import async_to_sync

class Updater():
    thread = None
    
    @classmethod
    @setInterval(5)
    def update(cls):
        if not cls.thread:
            cls.thread=uuid4().hex
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
        
        
    