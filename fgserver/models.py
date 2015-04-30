# -*- encoding: utf-8 -*-
'''
Created on Apr 15, 2015

@author: bartacruz
'''
from django.db.models.base import Model
from django.db.models.fields import CharField, DecimalField, IntegerField,\
    DateTimeField, BooleanField, FloatField
from django.db.models.fields.related import ForeignKey
from fgserver.settings import METAR_URL, METAR_UPDATE
from fgserver.helper import normdeg, fetch_metar, Position
from __builtin__ import abs
from datetime import datetime
from django.dispatch.dispatcher import receiver
from django.db.models.signals import post_save
from random import randint
from time import sleep
from django.utils import timezone


class Airport(Model):
    icao=CharField(max_length=4, db_index=True)
    name=CharField(max_length=255)
    lat=DecimalField(default=0,max_digits=10,decimal_places=6)
    lon=DecimalField(default=0,max_digits=10,decimal_places=6)
    altitude=IntegerField(default=0)
    metar = None
    has_metar = True
    
    def get_position(self):
        return Position(float(self.lat),float(self.lon),float(self.altitude))
    def __unicode__(self):
        return self.icao
    
    def active_runway(self):
        if self.get_metar():
            wind_from = 270
            wind_speed = self.metar.wind_speed
            if wind_speed and self.metar.wind_dir:
                wind_from=self.metar.wind_dir.value()
            vmax = -1
            rwy = None
            for curr in self.runways.all():
                deviation = abs(normdeg(wind_from - float(curr.bearing))) + 1e-20;
                v = (0.01 * float(curr.length) + 0.01 * float(curr.width)) / deviation;
                if v > vmax:
                    vmax = v
                    rwy = curr
            rwy.altitude = self.altitude
            print "selected runway: ",rwy
            return rwy
        else:
            rwy = self.runways.all().first()
            rwy.altitude = self.altitude
            print "default runway: ",rwy
            return rwy
    def check_metar(self):
        try:
            diff = datetime.now() - self.metar.time
            if diff.total_seconds > METAR_UPDATE:
                self.metar = fetch_metar(self.icao)
                self.has_metar = self.metar != None
        except:
            pass
            
    def get_metar(self):
        if self.has_metar: 
            if not self.metar:
                self.metar = fetch_metar(self.icao)
                self.has_metar = self.metar != None
            else:
                self.check_metar()
        return self.metar
        

class Runway(Model):
    airport=ForeignKey(Airport,related_name='runways')
    name=CharField(max_length=3)
    bearing=DecimalField(default=0,max_digits=5,decimal_places=2)
    width= IntegerField(default=0)
    length= IntegerField(default=0)
    lat=DecimalField(default=0,max_digits=10,decimal_places=6)
    lon=DecimalField(default=0,max_digits=10,decimal_places=6)
    altitude =0
        
    def position(self):
        ''' alias'''
        return self.get_position()
        
    def get_position(self):
        return Position(float(self.lat),float(self.lon),self.altitude)
    
    def __unicode__(self):
        return self.name
    
class Aircraft(Model):
    callsign = CharField(max_length=8)
    freq = CharField(max_length=10,blank=True,null=True)
    lat=DecimalField(default=0,max_digits=10,decimal_places=6)
    lon=DecimalField(default=0,max_digits=10,decimal_places=6)
    altitude=IntegerField(default=0)
    model = CharField(max_length=96,blank=True,null=True)
    state = IntegerField(default=0)
    last_request=CharField(max_length=60,blank=True,null=True)
    last_order=CharField(max_length=60,blank=True,null=True)
    ip=CharField(max_length=15,blank=True,null=True)
    port=CharField(max_length=5,blank=True,null=True)
    heading=FloatField(default=0)
    
    def get_addr(self):
        return (self.ip,int(self.port))
    def get_request(self):
        if self.last_request:
            return type('new_dict', (object,),{p.split('=')[0]:p.split('=')[1] for p in self.last_request.split(';')})
        return None

    def get_position(self):
        return Position(float(self.lat), float(self.lon), float(self.altitude))
    
    def __unicode__(self):
        return self.callsign

class Request(Model):
    date = DateTimeField()
    sender = ForeignKey(Aircraft, related_name='requests')
    request = CharField(max_length=255)
    
    def get_request(self):
        if self.request:
            return type('new_dict', (object,),{p.split('=')[0]:p.split('=')[1] for p in self.request.split(';')})
        return None
    
class Order(Model):
    date = DateTimeField()
    receiver = ForeignKey(Aircraft, related_name='orders')
    sender = ForeignKey(Airport, related_name='orders')
    order = CharField(max_length=255)
    message = CharField(max_length=255)
    confirmed = BooleanField(default=False)

    PARAM_ORDER='ord'
    PARAM_RUNWAY='rwy'
    PARAM_PARKING='park'
    PARAM_AIRPORT='apt'
    PARAM_CIRCUIT_WP='cirw'
    PARAM_CIRCUIT_TYPE='cirt'
    PARAM_LINEUP='lnup'
    PARAM_NUMBER='number'
    PARAM_HOLD='hld'
    PARAM_SHORT='short'
    PARAM_REPEAT='repeat'
    PARAM_ALTITUDE='alt'
    PARAM_LEG='leg'
    PARAM_ATIS='atis'
    PARAM_RECEIVER='to'
    
    def add_param(self,key,val):
        self._order[key]=val

    def get_param(self,key,default=None):
        return self._order.get(key,default)
  
    def get_instruction(self):
        return self.get_param(Order.PARAM_ORDER)
    
    def get_order(self):
        ret = {}
        for (k, v) in self._order.items():
            if type(v) == unicode:
                v = str(v)
            ret[k]=v
        return str(ret)

    def short(self):
        return self.get_param(Order.PARAM_SHORT, 0)
    
    def hold(self):
        return self.get_param(Order.PARAM_HOLD, 0)
    
    def __init__(self, *args, **kwargs):
        super(Order, self).__init__(*args, **kwargs)
        try:
            self._order = eval(self.order)
        except:
            self._order = {} 
        
    def save(self, *args, **kwargs):
        self.order=str(self._order)
        super(Order, self).save(*args, **kwargs)
            
    def __unicode__(self):
        return "%s: to %s = %s" %( self.id,self.receiver,self.order)

