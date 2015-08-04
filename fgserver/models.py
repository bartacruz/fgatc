# -*- encoding: utf-8 -*-
'''
Created on Apr 15, 2015

@author: bartacruz
'''
from __builtin__ import abs
from threading import Thread

from django.db.models.base import Model
from django.db.models.fields import CharField, DecimalField, IntegerField, \
    DateTimeField, BooleanField, FloatField
from django.db.models.fields.related import ForeignKey
from django.dispatch.dispatcher import receiver
from django.utils import timezone

from fgserver import llogger, debug, units, get_closest_metar
from fgserver.helper import normdeg, Position, get_distance, move
from fgserver.settings import METAR_UPDATE
from django.db.models.signals import post_save
from metar.Metar import Metar


class Airport(Model):
    icao=CharField(max_length=4, db_index=True)
    name=CharField(max_length=255)
    lat=DecimalField(default=0,max_digits=10,decimal_places=6)
    lon=DecimalField(default=0,max_digits=10,decimal_places=6)
    altitude=IntegerField(default=0)
    
    
    def get_position(self):
        return Position(float(self.lat),float(self.lon),float(self.altitude))
    def __unicode__(self):
        return self.icao
    
    def active_runway(self):
        metar = self.metar.last()
        if metar:
            obs = Metar(metar.observation)
            wind_from = 270
            wind_speed = obs.wind_speed
            if wind_speed and obs.wind_dir:
                wind_from=obs.wind_dir.value()
            vmax = -1
            rwy = None
            for curr in self.runways.all():
                deviation = abs(normdeg(wind_from - float(curr.bearing))) + 1e-20;
                v = (0.01 * float(curr.length) + 0.01 * float(curr.width)) / deviation;
                if v > vmax:
                    vmax = v
                    rwy = curr
            rwy.altitude = self.altitude
            debug(self.icao,"selected runway: ",rwy)
            return rwy
        else:
            rwy = self.runways.all().first()
            rwy.altitude = self.altitude
            debug(self.icao,"default runway: ",rwy)
            return rwy


def airportsWithinRange(pos,max_range, unit=units.NM):
    ne = move(pos, 45, max_range*unit, 0)
    sw = move(pos, 225, max_range*unit, 0)
    apts = Airport.objects.filter(lat__gte=sw.x, lon__gte=sw.y, lat__lte=ne.x,lon__lte=ne.y)
    within = [None]*max_range
    for apt in apts:
        apt_pos=apt.get_position()
        d =get_distance(pos, apt_pos, unit)
        within.insert(int(d),apt)
    within = [item for item in within if item] # sorting vodoo
    return within


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

class Comm(Model):
    
    # Radio types according to apt.dat v1000
    RECORDED = 50 #AWOS, ASOS or ATIS
    UNICOM = 51 # Unicom (US), CTAF (US), Radio (UK)
    CLD = 52 #  Clearance Delivery
    GND = 53 # Ground
    TWR = 54 # Tower
    APP = 55 # Approach
    DEP = 56 # Departure
    TYPES = (
        (RECORDED,'AWOS, ASOS or ATIS'),
        (UNICOM, 'Unicom'),
        (CLD, 'Clearance Delivery'),
        (GND,'Ground Control'),
        (TWR, 'Tower'),
        (APP, 'Approach'),
        (DEP, 'Departure'),
    )
    airport = ForeignKey(Airport, related_name="comms")
    type = IntegerField(choices=TYPES)
    frequency = IntegerField()
    frequency.help_text="Frequency in MhZ * 100 (eg. 12345 for 123.45 Mhz)"
    name = CharField(max_length=255)
    identifier=CharField(max_length=60)
    identifier.help_text="The name used in ATC communications"
    
    def get_FGfreq(self):
        sf = str(self.frequency)
        return "%s.%s" % (sf[:3],sf[3:])
    
    def __unicode__(self):
        return "%s@%s" %(self.name, self.frequency)

class MetarObservation(Model):
    airport = ForeignKey(Airport,related_name='metar')
    date = DateTimeField()
    cycle = IntegerField()
    observation = CharField(max_length=255)
    
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
    receiver = ForeignKey(Comm, related_name='requests', null=True,blank=True)
    request = CharField(max_length=255)
    
    def get_request(self):
        if self.request:
            return type('new_dict', (object,),{p.split('=')[0]:p.split('=')[1] for p in self.request.split(';')})
        return None

    def __unicode__(self):
        return "%s: from %s = %s" %( self.id,self.sender,self.request)

class Order(Model):
    date = DateTimeField()
    receiver = ForeignKey(Aircraft, related_name='orders')
    sender = ForeignKey(Comm, related_name='orders')
    order = CharField(max_length=255)
    message = CharField(max_length=255)
    confirmed = BooleanField(default=False) # by ATC
    received = BooleanField(default=False) # by aircraft radio
    acked = BooleanField(default=False) # by pilot
    
    PARAM_ORDER='ord'
    PARAM_FREQUENCY='freq'
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
    PARAM_QNH='qnh'
    PARAM_LEG='leg'
    PARAM_ATIS='atis'
    PARAM_RECEIVER='to'
    PARAM_CONTROLLER='atc'
    
    
    def add_param(self,key,val):
        self._order[key]=val

    def get_param(self,key,default=None):
        return self._order.get(key,default)
  
    def get_instruction(self):
        return self.get_param(Order.PARAM_ORDER)
    
    def get_order(self):
        self.add_param('oid', self.id)
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

class MetarUpdater(Thread):
    apt = None
    
    def __init__(self,apt):
        self.apt = apt
        super(MetarUpdater,self).__init__()
    
    def run(self):
        obs = get_closest_metar(self.apt)
        if obs:
            try:
                metar= MetarObservation.objects.get(airport=self.apt)
                llogger.debug("Updating METAR for %s with %s" % (self.apt,obs))
            except:
                metar = MetarObservation(airport=self.apt)
                llogger.debug("Creating METAR for %s with %s" % (self.apt,obs))
            metar.observation = obs.code
            metar.date=timezone.now()
            metar.cycle = obs.cycle
            metar.save()
            
 
@receiver(post_save,sender=Order)
def check_metar(sender, instance, **kwargs):
    try:
        metar = MetarObservation.objects.get(airport = instance.sender.airport)
        diff = timezone.now() - metar.date
        if diff.total_seconds() <= METAR_UPDATE:
            return
    except:
        llogger.error("Error getting MetarObservation for %s" % instance.sender.airport)
    llogger.debug("Getting metar for %s" % instance.sender.airport)
    t = MetarUpdater(instance.sender.airport)
    t.start()


