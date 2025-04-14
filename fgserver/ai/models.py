'''
Created on Apr 24, 2015

@author: bartacruz
'''
from fgserver.helper import Position, get_distance, move, normdeg,\
    elevate, get_heading_to, angle_diff, short_callsign, say_number
from fgserver import units
from django.db.models.base import Model
from django.db.models.fields.related import ForeignKey, ManyToManyField
from django.db.models.fields import CharField, FloatField, IntegerField,\
    BooleanField
from fgserver.models import Airport, Aircraft, Order, Cache, StartupLocation
from fgserver.ai.common import PlaneInfo
from fgserver.messages import alias
from random import randint
import threading
from django.db import models
import re
from django.utils import timezone
from django.conf import settings
from django.utils.module_loading import import_string
import logging
from .dijkstra import dj_waypoints
from django.contrib.gis.geos.point import Point
import time
from django.contrib.gis.db.models.fields import PointField, LineStringField
from django.db.models.deletion import CASCADE

llogger = logging.getLogger(__name__)


class FDM(Model):
    name = CharField(max_length=25)
    
    def __str__(self):
        return str(self.name)
    
    def get_props(self,state):
        return self.states.filter(state=state).first()

class FDMState(Model):
    fdm = ForeignKey(FDM,related_name="states", on_delete=models.CASCADE)
    state =CharField(max_length=16, choices=PlaneInfo.CHOICES_STATE)
    speed=IntegerField(help_text='in Knots')
    vertical_speed=IntegerField(help_text='in Feets per minute')
    turn_rate=IntegerField(help_text='Degrees/second')
    acceleration=FloatField(help_text="in m/s2", default=0)

def __str__(self):
        return str(self.state)

class FlightPlan(Model):
    name = CharField(max_length=8)
    description = CharField(max_length=255,null=True,blank=True)
    aircraft=ForeignKey(Aircraft, on_delete=models.CASCADE, related_name="plans")
    fdm = ForeignKey(FDM, related_name='flightplans', on_delete=models.SET_NULL, null=True, blank=True)
    handler =  CharField(max_length=255, choices=(lambda: getattr(settings,'FGATC_AI_HANDLERS',[]))() )
    enabled = BooleanField(default=False)
    departure=ForeignKey(Airport, on_delete=models.CASCADE, related_name='departures', null=True, blank=True)
    arrival=ForeignKey(Airport, on_delete=models.CASCADE, related_name='arrivals', null=True, blank=True)
    altitude=FloatField(default=1000*units.FT)
    altitude.description="Altitude (in meters)"

    def get_handler(self):
        if not hasattr(self, '_handler'):
            handler_class=import_string(self.handler)
            self._handler = handler_class(self)
        return self._handler
         
    def update(self,time):
        self.get_handler().update(time)
    
    def init(self):
        self.get_handler().init()

    def __unicode__(self):
        return self.name
    
    def __str__(self):
        return str(self.name)
    
    def log(self,*argv):
        msg = "[FP %s]" % self.name
        for arg in argv:
            msg += " %s" % arg
        llogger.info(msg)
    
    def debug(self,*argv):
        msg = "[FP %s]" % self.name
        for arg in argv:
            msg += " %s" % arg
        llogger.info(msg)
    
    def create_waypoint(self,position,name,atype,status):
        wp = WayPoint(flightplan = self,name=name,type=atype,status=status)
        wp.set_position(position)
        wp.save()
        return wp

class WayPoint(Model):
    POINT=0
    AIRPORT=1
    NAV=2
    FIX=3
    TAXI=4
    RWY=5
    PARKING=6
    PUSHBACK=7
    CIRCUIT=8
    HOLD=9
    TYPE_CHOICES=((POINT,'Point'),(AIRPORT,'Airport'),(NAV,'Nav'),(FIX,'Fix'),(TAXI,'Taxi'),(RWY,'Runway'),(PARKING,'Parking'),(PUSHBACK,'Pushback'),(CIRCUIT,'Circuit'),(HOLD,'Hold'),)

    ''' Common fields to all waypoints'''
    flightplan = ForeignKey(FlightPlan, on_delete=models.CASCADE, related_name="waypoints")
    name = CharField(max_length=20)
    description = CharField(max_length=255,null=True,blank=True)
    lat = FloatField(default=0)
    lon = FloatField(default=0)
    altitude = FloatField(default=0)
    type = IntegerField(choices=TYPE_CHOICES,blank=True, null=True )
    status = IntegerField(choices=PlaneInfo.CHOICES,blank=True, null=True )
    status.description="Status of the aircraft AFTER reaching this waypoint"
    order =  IntegerField(default=0)
    
    def set_position(self,position):
        self.altitude=position.z
        self.lat = position.x
        self.lon = position.y
    
    def get_position(self):
        return Position(self.lat,self.lon,self.altitude)
    
    def __unicode__(self):
        return "%s - %s: (%s,%s) @ %s" %(self.flightplan.name, self.name, WayPoint.TYPE_CHOICES[self.type][1],PlaneInfo.CHOICES[self.status][1],self.get_position().get_array())
#        return "%s - %s: (%s,%s) @ %s" %(self.flightplan.name, self.name, self.type,self.status,self.get_position().get_array())
    def __str__(self):
        return str(self.__unicode__())

class TaxiNode(Model):
    name = models.CharField(max_length=30) #OSM id
    airport = ForeignKey(Airport, related_name='taxinodes', on_delete=CASCADE)
    point = PointField()
    short = BooleanField(default=False)
    on_runway = BooleanField(default=False)
    adjacents = ManyToManyField("self")
    
    def adjacent_to(self,node):
        if node:
            self.adjacents.add(node)
    
    def __unicode__(self):
        return self.name
    
    def __str__(self):
        return str(self.__unicode__())
    
class TaxiWay(Model):
    name = models.CharField(max_length=30)
    airport = ForeignKey(Airport, related_name='taxiways', on_delete=CASCADE)
    nodes = ManyToManyField(TaxiNode)
    parking = BooleanField(default=False)
    
    def __unicode__(self):
        return self.name
    
    def __str__(self):
        return str(self.__unicode__())

