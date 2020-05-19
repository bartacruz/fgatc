# -*- encoding: utf-8 -*-
'''
Created on Apr 15, 2015

@author: bartacruz
'''
from threading import Thread

from django.db.models.base import Model
from django.db.models.fields import CharField, DecimalField, IntegerField, \
    DateTimeField, BooleanField, FloatField
from django.db.models.fields.related import ForeignKey, OneToOneField
from django.dispatch.dispatcher import receiver
from django.utils import timezone

from fgserver import llogger, debug, units, get_closest_metar
from fgserver.helper import normdeg, Position, get_distance, move, normalize,\
    point_inside_polygon, cart2geod, Quaternion, Vector3D, GEOID
from fgserver.settings import METAR_UPDATE
from django.db.models.signals import post_save
from metar.Metar import Metar
from math import sqrt, atan
from django.db import models
from django.contrib.gis.db.models.fields import PointField
from builtins import staticmethod
from fgserver.messages import PosMsg, PROP_FREQ, PROP_OID, PROP_CHAT,\
    PROP_REQUEST, sim_time
from fgserver.ai.common import PlaneInfo
from django.contrib.gis.geos.point import Point
from django.contrib.gis.geos.linestring import LinearRing
from django.contrib.gis.geos.polygon import Polygon



class Cache(object):
    ''' Implements a class-based basic cache. '''
    _store = None
    _map = None

    @classmethod
    def check(cls):
        #print "%s check: %s" % (cls,cls._store)
        if cls._store==None:
            cls._store={}
            cls._map = {}
            cls.load_all()

    @classmethod
    def clean(cls):
        cls._store={}
        cls._map = {}
    
    @classmethod
    def map(cls,map_id,instance_id,):
        cls.check()
        cls._map[map_id]=instance_id

    @classmethod
    def is_mapped(cls,map_id):
        cls.check()
        return map_id in cls._map

    @classmethod
    def get_mapped(cls,map_id):
        cls.check()
        return cls.get(cls._map.get(map_id,None))
    
    @classmethod
    def load(cls,instance_id):
        return None

    @classmethod
    def load_all(cls):
        return None

    @classmethod
    def get(cls,instance_id,force=False):
        cls.check()
        if not instance_id:
            return None
        if not force and cls._store.get(instance_id):
#            llogger.debug("%s get: obteniendo %s|%s" % (cls,instance_id,force))
            return cls._store.get(instance_id)
        return cls.load(instance_id)

    @classmethod
    def has(cls,instance_id):
        cls.check()
        return instance_id in cls._store

    @classmethod
    def keys(cls):
        cls.check()
        return cls._store.keys()

    @classmethod
    def values(cls):
        cls.check()
        return cls._store.values()
    
    @classmethod
    def set(cls,instance_id,value):
        cls.check()
#       llogger.debug("%s set: seteando %s : %s" % (cls,instance_id,value))
        cls._store[instance_id]=value

    @classmethod
    def remove(cls,instance_id):
        cls.check()
        return cls._store.pop(instance_id,None)
    

class Airport(Model):
    icao=CharField(max_length=4, db_index=True)
    name=CharField(max_length=255)
    lat=DecimalField(default=0,max_digits=10,decimal_places=6)
    lon=DecimalField(default=0,max_digits=10,decimal_places=6)
    #location = PointField(verbose_name="Airport location", null=True, blank=True)
    altitude=IntegerField(default=0)
    active = BooleanField(default=False)
    
    def get_position(self):
        return Position(float(self.lat),float(self.lon),float(self.altitude))
    
    def __unicode__(self):
        return self.icao
    
    def __str__(self):
        return str(self.icao)
    
    def on_runway(self,pos):
        for runway in self.runways.all():
            if runway.on_runway(pos): return True
        return False
            
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

class Airports(Cache):
    @classmethod
    def load(cls, instance_id):
        try:
            instance = Airport.objects.get(pk=instance_id)
            cls.set(instance_id,instance)
            return instance
        except Airport.DoesNotExist:
            return None
            

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
    airport=ForeignKey(Airport,on_delete=models.CASCADE,related_name='runways')
    name=CharField(max_length=3)
    bearing=DecimalField(default=0,max_digits=5,decimal_places=2)
    width= IntegerField(default=0)
    length= IntegerField(default=0)
    lat=DecimalField(default=0,max_digits=10,decimal_places=6)
    lon=DecimalField(default=0,max_digits=10,decimal_places=6)
    #location = PointField(verbose_name="Runway location", null=True, blank=True)
    altitude =0
        
    def __init__(self, *args, **kwargs):
        Model.__init__(self, *args, **kwargs)
        try:
            self._calculate_boundaries()
        except:
            llogger.exception("Error calculating boundaries for %s " % self)
    
    def data(self):
        return "%s@%s %s-%s @%s [%s,%s]" % (self.name,self.airport,self.lat, self.lon,self.altitude,self.bearing,self.length,)
    
    def _calculate_boundaries(self):
        w2= self.width/2
        # add 5mft for runway start/end miscalculation"
        l2= self.length/2+5
        bearing = float(self.bearing)
        pos = self.get_position()
        cat = sqrt(w2 * w2+l2*l2)
        alpha = atan(w2/l2)*units.RAD
        #self.log(l2,w2,cat,alpha)
        angles = []
        angles.append(normalize(bearing + alpha)) # front right
        angles.append(normalize(bearing - alpha))
        angles.append(normalize(bearing + alpha -180 ))
        angles.append(normalize(bearing - alpha -180 ))
        #self.log("self angles", angles)
        points=[]
        for angle in angles:
            lon,lat,raz = GEOID.fwd(pos.y,pos.x,angle,cat)
            points.append(Point(lon,lat))
        points.append(points[0]) # lose the ring
        
        self._boundaries=Polygon(points)
                
    def on_runway(self,pos):
        if isinstance(pos, Point):
            return self._boundaries.contains(pos)
        point = Point(pos.y,pos.x) 
        return self._boundaries.contains(point)
    
    def position(self):
        ''' alias'''
        return self.get_position()
        
    def get_position(self):
        return Position(float(self.lat),float(self.lon),self.altitude)
    
    def __unicode__(self):
        return self.name

def get_runway(icao,name):
    try:
        return Runway.objects.get(name=name, airport__icao=icao)
    except Runway.DoesNotExist:
        return None

class Runways(Cache):
    @classmethod
    def load(cls, instance_id):
        try:
            instance = Runway.objects.get(pk=instance_id)
            cls.set(instance_id,instance)
            cls.map(instance.airport_id, instance_id)
            return instance
        except Airport.DoesNotExist:
            return None  

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
    airport = ForeignKey(Airport, on_delete=models.CASCADE, related_name="comms")
    type = IntegerField(choices=TYPES)
    frequency = IntegerField()
    frequency.help_text="Frequency in MhZ * 100 (eg. 12345 for 123.45 Mhz)"
    name = CharField(max_length=255)
    identifier=CharField(max_length=60)
    identifier.help_text="The name used in ATC communications"
    
    def get_FGfreq(self):
        sf = str(self.frequency)
        return "%s.%s" % (sf[:3],sf[3:])
    
    def __str__(self):
        return self.__unicode__()
    
    def __unicode__(self):
        return "%s@%s" %(self.name, self.frequency)

class MetarObservation(Model):
    airport = ForeignKey(Airport, on_delete=models.CASCADE, related_name='metar')
    date = DateTimeField()
    cycle = IntegerField()
    observation = CharField(max_length=255)
    
class Aircraft(Model):
    callsign = CharField(max_length=8)
    freq = CharField(max_length=10,blank=True,null=True)
    lat=DecimalField(default=0,max_digits=10,decimal_places=6)
    lon=DecimalField(default=0,max_digits=10,decimal_places=6)
    #location = PointField(verbose_name="Aircraft location", null=True, blank=True)
    altitude=IntegerField(default=0)
    model = CharField(max_length=96,blank=True,null=True)
    state = IntegerField(default=0)
    last_request=CharField(max_length=60,blank=True,null=True)
    last_order=CharField(max_length=60,blank=True,null=True)
    ip=CharField(max_length=15,blank=True,null=True)
    port=CharField(max_length=5,blank=True,null=True)
    heading=FloatField(default=0)
    updated = DateTimeField(blank=True,null=True)
    
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
    
    def __str__(self):
        return str(self.__unicode__())

    def update_position(self,position=None):
        '''
        Updates aircraft's lat,lon,alt and heading from a PosMsg
        '''
        position = position or self.posmsg.position
        geod = cart2geod(position)
        #print("updating position of %s" % self, position, geod)
        self.lat=geod[0]
        self.lon=geod[1]
        self.altitude=geod[2]
        
        qor = Quaternion.fromAngleAxis(Vector3D.from_array(self.posmsg.orientation))
        h10r = Quaternion.fromLatLon(self.lat, self.lon).conjugate().multiply(qor)
        eul = h10r.getEuler().scale(units.RAD)
        self.heading= eul.z
        self.updated = timezone.now()

class Aircrafts(Cache):
    @classmethod
    def load(cls, instance_id):
        try:
            instance = Aircraft.objects.get(callsign=instance_id)
            try: 
                status = instance.status
            except:
                llogger.info("Creating new AircraftStatus for %s" % instance)
                status = AircraftStatus(aircraft=instance)
                status.save()
            cls.set(instance_id,instance)
            return instance
        except Aircraft.DoesNotExist:
            return None

class AircraftStatus(Model):
    aircraft = OneToOneField(to=Aircraft, related_name='status', verbose_name='Aircraft status', on_delete=models.CASCADE)
    date = DateTimeField(blank=True,null=True)
    position = PointField(dim=3,verbose_name="Position", default=Point(0,0,0)) # lon,lat,alt
    orientation = PointField(dim=3,verbose_name="Orientation", default=Point(0,0,0))
    linear_vel = PointField(dim=3,verbose_name="Linear velocity", default=Point(0,0,0))
    angular_vel = PointField(dim=3,verbose_name="Angular velocity", default=Point(0,0,0))
    linear_accel = PointField(dim=3,verbose_name="Linear acceleration", default=Point(0,0,0))
    angular_accel = PointField(dim=3,verbose_name="Angular acceleration", default=Point(0,0,0))
    request=CharField(max_length=255,blank=True,null=True)
    order=CharField(max_length=255,blank=True,null=True)
    on_ground = BooleanField(default=False)
    freq = IntegerField(default=0,blank=True,null=True)
    message = CharField(max_length=255,blank=True,null=True)
    state = IntegerField(default=0)
    
    @staticmethod
    def _p2a(p):
        return (p.x,p.y,p.z)
    
    def get_fg_freq(self): 
        if not self.freq:
            return None       
        sf = str(self.freq)
        return "%s.%s" % (sf[:3],sf[3:])
    
    def set_fg_freq(self,value):
        if not value:
            self.freq = None
        else:
            self.freq = value.replace(".","")
        
    def update_from_position(self,pos):
        self.model = pos.model
        self.date = timezone.now() # TODO: take it from time?
        self.position = Point(pos.position)
        self.orientation = Point(pos.orientation)
        self.linear_accel = Point(pos.linear_accel)
        self.linear_vel = Point(pos.linear_vel)
        self.angular_vel = Point(pos.angular_vel)
        self.angular_accel = Point(pos.angular_accel)
        
        # Properties
        
        self.set_fg_freq(pos.properties.get_value(PROP_FREQ)) or ""
        self.order = pos.properties.get_value(PROP_OID) or ""
        self.request = pos.properties.get_value(PROP_REQUEST) or ""
        self.message = pos.properties.get_value(PROP_CHAT) or ""
        
    def get_position_message(self):
        pos = PosMsg()
        pos.header.callsign=self.aircraft.callsign
        pos.model = self.aircraft.model
        pos.time = sim_time()
        pos.lag = 0.5
        pos.position=self._p2a(self.position)
        pos.orientation=self._p2a(self.orientation)
        pos.angular_vel=self._p2a(self.angular_vel)
        pos.angular_accel=self._p2a(self.angular_accel)
        pos.linear_vel=self._p2a(self.linear_vel)
        pos.linear_accel=self._p2a(self.linear_accel)
        
        props = pos.properties
        props.set_prop(PROP_FREQ,self.get_fg_freq())
        #print(self.freq,self.get_fg_freq(),pos.get_value(PROP_FREQ))
        # HACK
        props.set_prop(302,self.linear_vel.x*50) # engine 0 rpms
        props.set_prop(312,self.linear_vel.x*50) # engine 1 rpms
        
        if self.order:
            props.set_prop(PROP_OID,str(self.order))
        if self.request:
            #llogger.debug("request=%s" % self.request)
            props.set_prop(PROP_REQUEST,self.request)
        # Landing gears
        if self.on_ground or self.state == PlaneInfo.LANDING:
            #props.set_prop(1004,1)
            props.set_prop(201,1)
            props.set_prop(211,1)
            props.set_prop(221,1)
        else:
            #props.set_prop(1004,0)
            props.set_prop(201,0)
            props.set_prop(211,0)
            props.set_prop(221,0)
        props.set_prop(PROP_CHAT,self.message)
#         print("Returning pos %s" % pos )
        return pos
        
    
class Request(Model):
    date = DateTimeField()
    sender = ForeignKey(Aircraft, on_delete=models.CASCADE, related_name='requests')
    receiver = ForeignKey(Comm, on_delete=models.CASCADE, related_name='requests', null=True,blank=True)
    request = CharField(max_length=255)
    received = BooleanField(default=False) # by Server
    processed = BooleanField(default=False) # by ATC or Server
    
    
    def get_param(self,param):
        r = self.get_request();
        return r.__dict__.get(param,None)
    
    def get_request(self):
        if self.request:
            return type('new_dict', (object,),{p.split('=')[0]:p.split('=')[1] for p in self.request.split(';')})
        return None

    def __unicode__(self):
        return "%s: from %s = %s" %( self.id,self.sender,self.request)
    
    def __str__(self):
        return str(self.__unicode__())

class Order(Model):
    date = DateTimeField()
    receiver = ForeignKey(Aircraft, on_delete=models.CASCADE, related_name='orders')
    sender = ForeignKey(Comm, on_delete=models.CASCADE, related_name='orders')
    order = CharField(max_length=255)
    message = CharField(max_length=255)
    sent_date = DateTimeField(null=True, blank=True)
    expired = BooleanField(default=False) # by Server
    received = BooleanField(default=False) # by aircraft radio
    acked = BooleanField(default=False) # by pilot
    lost = BooleanField(default=False) # never received or acked
    
    PARAM_ORDER='ord'
    PARAM_OID='oid'
    PARAM_FREQUENCY='freq'
    PARAM_RUNWAY='rwy'
    PARAM_PARKING='park'
    PARAM_PARKING_NAME='parkn'
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
            ret[k]=str(v)
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
    
    def __str__(self):
        return str(self.__unicode__())
    
class StartupLocation(Model):
    airport = ForeignKey(Airport,on_delete=models.CASCADE, related_name="startups")
    name = CharField(max_length=60)
    lat = DecimalField(default=0,max_digits=10,decimal_places=6)
    lon = DecimalField(default=0,max_digits=10,decimal_places=6)
    #location = PointField(verbose_name="Location", null=True, blank=True)
    altitude = IntegerField(default=0)
    heading = FloatField(default=0)
    aircraft=ForeignKey(Aircraft,on_delete=models.CASCADE, blank=True,null=True, related_name='startup_location')
    active = BooleanField(default=True)

    def get_position(self):
        return Position(float(self.lat), float(self.lon), float(self.altitude))
    def __str__(self):
        return self.__unicode__()
    def __unicode__(self):
        return "%s@%s" %( self.name,self.airport)
  
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


