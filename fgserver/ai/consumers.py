'''
Created on 16 may. 2020

@author: julio
'''
import logging

from asgiref.sync import async_to_sync
from channels.generic.websocket import JsonWebsocketConsumer, WebsocketConsumer
from channels.layers import get_channel_layer

from fgserver import units

llogger = logging.getLogger(__name__)

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
               'request': str(plane.copilot.request),
               'message': plane.copilot.message,
               }
        message = {'type': 'plane_update', 'Model':'StatePlane','data':ser}
    
        channel_layer = get_channel_layer()
        #llogger.debug("Updater: sending %s" % message)
        async_to_sync(channel_layer.group_send)("stateplanes",message)
