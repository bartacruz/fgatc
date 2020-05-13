'''
Created on Apr 24, 2015

@author: bartacruz
'''
from fgserver.helper import Position, get_distance, move, normdeg,\
    elevate, get_heading_to, angle_diff, short_callsign, say_number
from fgserver import units
from django.db.models.base import Model
from django.db.models.fields.related import ForeignKey
from django.db.models.fields import CharField, FloatField, IntegerField,\
    BooleanField
from fgserver.models import Airport, Aircraft, Order, Cache, StartupLocation
from fgserver.ai.planes import AIPlane, PlaneInfo
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

llogger = logging.getLogger(__name__)

class FlightPlan(Model):
    name = CharField(max_length=8)
    description = CharField(max_length=255,null=True,blank=True)
    aircraft=ForeignKey(Aircraft, on_delete=models.CASCADE, related_name="plans")
    handler =  CharField(max_length=255, choices=(lambda: getattr(settings,'FGATC_AI_HANDLERS',[]))() )
    enabled = BooleanField(default=False)
        
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
    
    
class Circuit(FlightPlan):
    ''' A standard left-circuit over an airfield ''' 
    airport=ForeignKey(Airport, on_delete=models.CASCADE, related_name='circuits')
    radius = FloatField(default=2*units.NM)
    radius.description="Radius of the circuit (in meters)"
    altitude=FloatField(default=1000*units.FT)
    altitude.description="Altitude of the circuit (in meters)"   
    
    def init(self):
        self._waypoint=0
        self._time=0
        #self._waiting=randint(30,180)
        #self._waiting=randint(5,60)
        self._waiting=10
        self._last_order=None
        self.aircraft.state=2
        self.runway = None
        self.waypoints.all().delete()
        #self._handler=None
        if hasattr(self, '_handler'):
            print("REMOVING HANDLER",self._handler)
            delattr(self,'_handler')
        self.get_handler()
        #self.generate_waypoints()
        self.aiplane = AIPlane(self)
        self.aiplane.position = self.waypoint().get_position()
        self.aiplane.update_aircraft()
        self.aircraft.save()
        self.aircraft.status.save()
        self.debug(self.name,": init called")
    
    def _wait(self,seconds):
        self.debug("Waiting %s seconds" % seconds)
        self._waiting = seconds
        
    def started(self):
        return hasattr(self, '_time')
    
    def end(self):
        self.log("End of circuit %s" % self.name)
        self.init()

    def last_order(self):
        return self.aircraft.orders.filter(confirmed=True).last()
    
    def create_waypoint(self,position,name,atype,status):
        wp = WayPoint(flightplan = self,name=name,type=atype,status=status)
        wp.set_position(position)
        wp.save()
        return wp

    def get_startup_location(self):     
        s1 = self.airport.startups.filter(aircraft = self.aircraft).first()
        if not s1:
            s1 = self.airport.startups.filter(active=True,aircraft=None).order_by("?").first()
        if s1:
            s1.aircraft=self.aircraft
            s1.save()
        return s1

    def waypoint(self):
        if self.waypoints.all().count() <= self._waypoint:
            self._waypoint=0
        return self.waypoints.all().order_by('id')[self._waypoint]
        
    
    def next_waypoint(self):
        if self.waypoints.all().count() > self._waypoint + 1:
            return self.waypoints.all().order_by('id')[self._waypoint+1]
        return None
    
    def update(self,time):
        #if self.aircraft.state < 1:
        #    return

        dt = time-self._time
        plane = self.aiplane
        if not plane:
            self.log("ERROR: aiplane is null!")
            return
        
        if self._waiting or plane.state in [PlaneInfo.STOPPED, PlaneInfo.LINED_UP, PlaneInfo.HOLD, PlaneInfo.SHORT]:
            # dont move
            self._waiting= max(0,self._waiting-dt)
            self._time=time
            status = plane.update_aircraft()
            status.date = timezone.now()
            status.save()
            self.debug("WAITING on %s: %s" % (plane.get_state_label(),self._waiting,))
            return
        wp = self.waypoint()
        if not wp:
            self.log("ERROR: No waypoint set. %s" % self._waypoint)
            return
        course = plane.heading_to(wp.get_position())
        dist = plane.speed * dt
        dist_to=get_distance(plane.position, wp.get_position())
        #self.log("course: %s, dist:%s, dist_to:%s" % (course,dist,dist_to))
        seconds_before=0
        nang=0
        if self.waypoints.count()-1 > self._waypoint and not plane.on_ground():
            ncourse = get_heading_to(wp.get_position(), self.next_waypoint().get_position())
            nang = angle_diff(course, ncourse) 
            seconds_before = nang/plane.turn_rate+2
        turn_dist = dist_to - dist*seconds_before/(dt*2)
        #self.debug("sec before",seconds_before,'turn_dist',turn_dist)
        step = False
        if dist >= abs(turn_dist):
            self.debug("Reached waypoint %s" % wp)
            self.debug(nang,seconds_before,dist,dist_to,turn_dist)
            
            dist = min(dist,dist_to)
            #plane.course = course
            step = True
        plane.move(course,dist,dt)
        if step:
            plane.set_state(wp.status)
            if wp.type == WayPoint.HOLD:
                self._wait(5)
            self._waypoint += 1
            self.debug("Next wp:",self._waypoint,self.waypoint())
            if self.waypoint():
                plane.waypoint = self.waypoint()
                plane.target_altitude=self.waypoint().get_position().z
                self.debug("Next course: ",course,plane.course,plane.target_course,plane.next_course(0.1))
#                self.debug("target altitude %sm" % plane.target_altitude)
#                self.debug("heading",plane.course,plane.heading_to(wp.get_position()))
            else:
                self.circuit.end()
        self._time = time
        
        try:
            status = plane.update_aircraft()
            status.date = timezone.now()
            status.save()
            #self.debug("status saved",status.id, status.freq, status.order)
        except:
            llogger.exception("Updating plane status")
    
    def process_order(self,instance):
        if not instance or instance == self._last_order:
            return
        try:
            order = instance.get(Order.PARAM_ORDER,None)
            short = instance.get(Order.PARAM_SHORT,False) or False
            self._last_order = instance
            self.aiplane.last_order = instance
            self.readback(instance)
            if order == alias.TUNE_OK:
                if self.aiplane.state == PlaneInfo.STOPPED:
                    self.aiplane.set_state(PlaneInfo.PUSHBACK)
                else:
                    self.aiplane.check_request()
            elif order == alias.TUNE_TO:
                freq = instance.get(Order.PARAM_FREQUENCY,None).replace('.','')
                self.debug("retunning radio to %s" % freq)
                comm = self.airport.comms.filter(frequency=freq).first()
                self.aiplane.comm=comm
                req = "req=tunein;freq=%s" % comm.get_FGfreq()
                threading.Thread(target=self.aiplane.send_request,args=(req,'',)).start()
            elif order in [alias.TAXI_TO, alias.LINEUP]:
                rwy = instance.get(Order.PARAM_RUNWAY, None)
                if not self.runway or self.runway.name != rwy or short:
                    ''' the ATC refered us to a different runway. Obey '''
                    self.debug("Generating waypoints for ATC's assigned runway %s (short=%s) " % (rwy,short,))
                    self.runway = self.airport.runways.get(name=rwy)
                    self._handler.generate_taxi_waypoints(self.aiplane.position,self.runway,short)
                    self.aiplane.waypoint = self.waypoint()
                    self.debug("Setting aiplane waypoint to %s " % self.aiplane.waypoint)
                    
                self.aiplane.set_state(PlaneInfo.TAXIING)
                self._wait(10)
            elif order == alias.CLEAR_TK:
                self._handler.generate_circuit_waypoints(self.runway)
                if self.aiplane.state == PlaneInfo.SHORT:
                    self.aiplane.set_state(PlaneInfo.LINING_UP)
                else:
                    self.aiplane.set_state(PlaneInfo.DEPARTING)
                self._wait(10)
            elif order in [alias.CIRCUIT_STRAIGHT, alias.JOIN_CIRCUIT]:
                rwy = instance.get(Order.PARAM_RUNWAY, None)
                if not self.runway or self.runway.name != rwy:
                    self.debug("Generating waypoints for ATC's assigned runway approach %s " % rwy)
                    self.runway = self.airport.runways.get(name=rwy)
                self._handler.generate_landing_waypoints(self.runway)
            elif order == alias.TAXI_PARK:
                if instance.get(Order.PARAM_PARKING,False):
                    try:
                        startup = StartupLocation.objects.get(pk=instance.get(Order.PARAM_PARKING))
                        self._handler.generate_taxi_waypoints(self.aiplane.position,startup.get_position())
                    except StartupLocation.DoesNotExist:
                        startup = self.airport.startups.all().order_by("?").first()
                        if startup:
                            self._handler.generate_taxi_waypoints(self.aiplane.position,startup.get_position())
                            
                self._wait(10)
                self.aiplane.set_state(PlaneInfo.TAXIING)
                
            else:
                self.log("Circuit",self.aircraft.callsign,', order ignored', instance)
        except:
            llogger.exception("Processing order %s" % order)
                
    def readback(self,order):
        templates={
           alias.CLEAR_LAND:"clear to land runway {rwy}{qnh}",
           alias.CLEAR_TOUCHNGO:"clear touch and go{onum} runway {rwy}{qnh}",
           alias.CLEAR_TK : "cleared for take off runway {rwy}",
           alias.GO_AROUND : "going around, report on {cirw}",
           alias.JOIN_CIRCUIT:"{cirw} for {rwy} at {alt}{qnh}",
           alias.CIRCUIT_STRAIGHT:"straight for {rwy}, report on {cirw}{qnh}",
           alias.LINEUP : "line up on {rwy}{hld}",
           alias.REPORT_CIRCUIT: 'report on {cirw}',
           alias.STARTUP: "start up approved{qnh}",
           alias.TAXI_TO: "taxi to {rwy}{via}{hld}{short}{lineup}",
           alias.WAIT: "we wait", 
           alias.SWITCHING_OFF: "Good day",
           alias.TAXI_PARK: "parking {park}",
        }
        msg = templates.get(order.get(Order.PARAM_ORDER))
        if not msg:
            llogger.info("No readback for %s" % order.get(Order.PARAM_ORDER))
            return
        msg = re.sub(r'{cs}',short_callsign(self.aircraft.callsign),msg)
        msg = re.sub(r'{icao}',order.get(Order.PARAM_AIRPORT),msg)
        msg = re.sub(r'{comm}',self.aiplane.comm.identifier,msg)
        msg = re.sub(r'{rwy}',say_number(order.get(Order.PARAM_RUNWAY,'')),msg)
        msg = re.sub(r'{alt}',str(order.get(Order.PARAM_ALTITUDE,'')),msg)
        msg = re.sub(r'{cirt}',order.get(Order.PARAM_CIRCUIT_TYPE,''),msg)
        msg = re.sub(r'{cirw}',order.get(Order.PARAM_CIRCUIT_WP,''),msg)
        msg = re.sub(r'{num}',str(order.get(Order.PARAM_NUMBER,'')),msg)
        msg = re.sub(r'{freq}',str(order.get(Order.PARAM_FREQUENCY,'')),msg)
        msg = re.sub(r'{conn}',str(order.get(Order.PARAM_CONTROLLER,'')),msg)
        msg = re.sub(r'{park}',str(order.get(Order.PARAM_PARKING,'')),msg)
        if order.get(Order.PARAM_NUMBER, False):
            msg = re.sub(r'{onum}',', number %s' % order.get(Order.PARAM_NUMBER),msg)
        if order.get(Order.PARAM_LINEUP):
            msg = re.sub(r'{lineup}',' and line up',msg)
        if order.get(Order.PARAM_HOLD):
            msg = re.sub(r'{hld}',' and hold',msg)
        if order.get(Order.PARAM_SHORT):
            msg = re.sub(r'{short}',' short',msg)
        if order.get(Order.PARAM_PARKING):
            try:
                startup = StartupLocation.objects.get(pk=order.get(Order.PARAM_PARKING))
                msg = re.sub(r'{park}',startup.name.replace("_"," "),msg)
            except StartupLocation.DoesNotExist:
                pass
        if order.get(Order.PARAM_QNH):
            msg = re.sub(r'{qnh}','. QNH %s' % say_number(order.get(Order.PARAM_QNH)),msg)

        # Clean up tags not replaced
        msg = re.sub(r'{\w+}','',msg)
        msg += ", %s" % short_callsign(self.aircraft.callsign)
        req = "req=roger;laor=%s" % order.get(Order.PARAM_ORDER)
        llogger.debug("readback: %s | %s" % (req,msg,))        
        threading.Thread(target=self.send_delayed_request,args=(req,msg,10,)).start()
    
    def send_delayed_request(self,req,msg,delay=5):
        time.sleep(delay)
        self.aiplane.send_request(req,msg)
        
class Circuits(Cache):            
    
    @classmethod
    def load(cls, instance_id):
        try:
            circuit = Circuit.objects.get(pk=instance_id)
            cls.set(instance_id,circuit)
            return circuit
        except:
            return None

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
            
class CircuitWaypoint(WayPoint):
    CIRCUIT_STRAIGHT=0
    CIRCUIT_CROSSWIND=1
    CIRCUIT_DOWNWIND=2
    CIRCUIT_BASE=3
    CIRCUIT_FINAL=4
    CIRCUIT_CHOICES=(
        (CIRCUIT_STRAIGHT,'Straight'),
        (CIRCUIT_CROSSWIND,'Crosswind'),
        (CIRCUIT_DOWNWIND,'Downwind'),
        (CIRCUIT_BASE,'Base'),
        (CIRCUIT_FINAL,'Final'),
    )

    circuit_type = IntegerField(choices=CIRCUIT_CHOICES,blank=True, null=True )

