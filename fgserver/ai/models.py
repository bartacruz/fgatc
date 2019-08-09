'''
Created on Apr 24, 2015

@author: bartacruz
'''
from fgserver.helper import Position, get_distance, move, normdeg,\
    elevate, get_heading_to, angle_diff, short_callsign, say_number
from fgserver import units, llogger, messages
from django.db.models.base import Model
from django.db.models.fields.related import ForeignKey
from django.db.models.fields import CharField, FloatField, IntegerField,\
    BooleanField
from fgserver.models import Airport, Aircraft, Order, Cache
from fgserver.ai.planes import AIPlane, PlaneInfo
from fgserver.messages import alias
from random import randint
import threading
from django.db import models
import re

class FlightPlan(Model):
    name = CharField(max_length=8)
    description = CharField(max_length=255,null=True,blank=True)
    aircraft=ForeignKey(Aircraft, on_delete=models.CASCADE, related_name="plans")

    
    def update(self,time):
        pass
    
    def init(self):
        pass

    def __unicode__(self):
        return self.name
    
    def __str__(self):
        return str(self.name)
    
    def log(self,*argv):
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
    enabled = BooleanField(default=False)
            
    def init(self):
        self._waypoint=0
        self._time=0
        self._waiting=randint(60,180)
        self.aircraft.state=2
        self.runway = None
        self.generate_waypoints()
        self.aiplane = AIPlane(self)
        self.aiplane.update_aircraft()
        self.aircraft.save()
        self.log(self.name,": init called")
    
    def end(self):
        self.log("END OF CIRCUIT %s" % self.name)
        self._waypoint=0
        self.aiplane = AIPlane(self)
        self._waiting=randint(90,270)

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
            s1 = self.airport.startups.filter(active=True,aircraft=None).first()
        if s1:
            s1.aircraft=self.aircraft
            s1.save()
        return s1

    def generate_waypoints(self):
        self.waypoints.all().delete()
        if not self.runway:
            self.runway = self.airport.active_runway()
        runway = self.runway
        straight = runway.bearing
        reverse= normdeg(straight-180)
        left = normdeg(straight-90)
        right = normdeg(straight+90)
        apalt=float(self.airport.altitude*units.FT+2)
        self.log("runway length", runway.length,runway.length/2)
        rwystart = move(runway.position(), reverse, runway.length*units.FT/2,apalt)
        rwyend = move(runway.position(), straight, runway.length*units.FT/2,apalt)
        s1 = self.get_startup_location()
        if s1:
            position = s1.get_position()
            self.log("STARTUP LOCATION=%s" % s1)
        else:
            position = move(rwystart,left,runway.width*units.FT,apalt)
        self.create_waypoint(position, "FParking %s"%runway.name, WayPoint.PARKING, PlaneInfo.STOPPED)
        position = move(rwystart,left,runway.width*units.FT*0.8,apalt)
        self.create_waypoint(position, "Short %s"%runway.name, WayPoint.HOLD, PlaneInfo.SHORT)
        position = move(rwystart,straight,30*units.FT,apalt)
        self.create_waypoint(position, "Hold %s"%runway.name, WayPoint.HOLD, PlaneInfo.LINED_UP)
        position = move(rwystart,straight,runway.length*units.FT*0.75,apalt)
        self.create_waypoint(position, "Rotate %s"%runway.name, WayPoint.RWY, PlaneInfo.DEPARTING)
        # get to 10 meters altitude after exit the runway, then start climbing
        position = elevate(rwyend,apalt+10)
        self.create_waypoint(position, "Departure %s"%runway.name, WayPoint.RWY, PlaneInfo.CLIMBING)
        position = move(position,straight,self.radius,apalt+self.altitude)
        self.create_waypoint(position, "Cruising", WayPoint.POINT, PlaneInfo.CRUISING)
        position = move(position,normdeg(straight+40),self.radius*0.7,apalt+self.altitude)
        self.create_waypoint(position, "Cruising 2", WayPoint.POINT, PlaneInfo.CRUISING)
        position = move(position,normdeg(straight+80),self.radius*0.6,apalt+self.altitude)
        self.create_waypoint(position, "Cruising 3", WayPoint.POINT, PlaneInfo.CRUISING)
        position = move(position,normdeg(straight+120),self.radius*0.6,apalt+self.altitude)
        self.create_waypoint(position, "Cruising 4", WayPoint.POINT, PlaneInfo.CRUISING)
        position = move(position,normdeg(straight+150),self.radius*0.6,apalt+self.altitude)
        self.create_waypoint(position, "Cruising 5", WayPoint.POINT, PlaneInfo.CRUISING)
        position = move(position,normdeg(straight+190),self.radius*0.6,apalt+self.altitude)
        self.create_waypoint(position, "Cruising 5", WayPoint.POINT, PlaneInfo.CRUISING)
        position = move(position,normdeg(straight+230),self.radius*0.6,apalt+self.altitude)
        self.create_waypoint(position, "Cruising 6", WayPoint.POINT, PlaneInfo.CRUISING)
        position = move(rwyend,right,self.radius,apalt+self.altitude+1000*units.FT)
        self.create_waypoint(position, "Crosswind %s"%runway.name, WayPoint.CIRCUIT, PlaneInfo.CIRCUIT_CROSSWIND)
        position = move(position,left,self.radius*2,apalt+self.altitude)
        self.create_waypoint(position, "Downwind %s"%runway.name, WayPoint.CIRCUIT, PlaneInfo.CIRCUIT_DOWNWIND)
        position = move(position,reverse,self.radius+runway.length*units.FT,apalt+self.altitude)
        self.create_waypoint(position, "Base %s"%runway.name, WayPoint.CIRCUIT, PlaneInfo.CIRCUIT_BASE)
        position = move(position,right,self.radius,apalt+500*units.FT)
        self.create_waypoint(position, "Final %s"%runway.name, WayPoint.CIRCUIT, PlaneInfo.CIRCUIT_FINAL)
        position = move(rwystart,reverse,30,apalt+15)
        self.create_waypoint(position, "Flare %s"%runway.name, WayPoint.CIRCUIT, PlaneInfo.LANDING)
        position = move(rwystart,straight,20,apalt)
        self.create_waypoint(position, "Touchdown %s"%runway.name, WayPoint.RWY, PlaneInfo.TOUCHDOWN)
        self.create_waypoint(runway.position(), "Taxi %s"%runway.name, WayPoint.TAXI, PlaneInfo.TAXIING)        
        position = move(rwyend,left,30*units.FT,apalt)
        self.create_waypoint(position, "Taxi 2 %s"%runway.name, WayPoint.TAXI, PlaneInfo.TAXIING)
        position = move(rwystart,left,30*units.FT,apalt)
        self.create_waypoint(position, "Parking %s"%runway.name, WayPoint.PARKING, PlaneInfo.STOPPED)
        self.log("waypoints created")

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
        
        if self._waiting:
            self._waiting= max(0,self._waiting-dt)
            self._time=time
            return plane.get_pos_message()
        wp = self.waypoint()
        if not wp:
            self.log("ERROR: No waypoint set. %s" % self._waypoint)
            return plane.get_pos_message()
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
        #self.log("sec before",seconds_before,'turn_dist',turn_dist)
        step = False
        if dist >= abs(turn_dist):
            self.log("reached waypoint %s" % wp)
            self.log(nang,seconds_before,dist,dist_to,turn_dist)
            
            dist = min(dist,dist_to)
            #plane.course = course
            step = True
        plane.move(course,dist,dt)
        if step:
            plane.set_state(wp.status)
            if wp.type == WayPoint.HOLD:
                self._waiting=5
            self._waypoint += 1
            self.log("Next wp:",self._waypoint,self.waypoint())
            if self.waypoint():
                plane.waypoint = self.waypoint()
                plane.target_altitude=self.waypoint().get_position().z
                self.log("NEXT COURSE",course,plane.course,plane.target_course,plane.next_course(0.1))
#                self.log("target altitude %sm" % plane.target_altitude)
#                self.log("heading",plane.course,plane.heading_to(wp.get_position()))
            else:
                self.circuit.end()
        self._time = time
        plane.update_aircraft()
        return plane.get_pos_message()

    def process_order(self,instance):
        self.log(self.name,"procesando orden",instance)
        if not instance.receiver == self.aircraft or not instance.confirmed:
            llogger.warn("order is not for me or not confirmed! %s != %s or %s" % (instance.receiver, self.aircraft, instance.confirmed))
            return
        
        order = instance.get_param(Order.PARAM_ORDER)
        self._last_order = instance
        self.aiplane.last_order = instance
        self.readback(instance)
        if order == alias.TUNE_OK:
            if self.aiplane.state == PlaneInfo.STOPPED:
                self.aiplane.set_state(PlaneInfo.PUSHBACK)
            else:
                self.aiplane.check_request()
        elif order == alias.TUNE_TO:
            freq = instance.get_param(Order.PARAM_FREQUENCY).replace('.','')
            self.log("retunning radio to %s" % freq)
            comm = self.airport.comms.filter(frequency=freq).first()
            self.aiplane.comm=comm
            req = "req=tunein;freq=%s" % comm.get_FGfreq()
            threading.Thread(target=self.aiplane.send_request,args=(req,'',)).start()
        elif order in [alias.TAXI_TO, alias.LINEUP]:
            rwy = instance.get_param(Order.PARAM_RUNWAY)
            if not self.runway or self.runway.name != rwy:
                ''' the ATC refered us to a different runway. Obey '''
                self.log("regenerating flight plan for ATC's assigned runway %s " % rwy)
                self.runway = self.airport.runways.get(name=rwy)
                self.generate_waypoints()
                self.aiplane.waypoint = self.waypoint()
                self.log("Setting aiplane waypoint to %s " % self.aiplane.waypoint)
                
            self.aiplane.set_state(PlaneInfo.TAXIING)
            self._waiting=10
        elif order == alias.CLEAR_TK:
            if self.aiplane.state == PlaneInfo.SHORT:
                self.aiplane.set_state(PlaneInfo.LINING_UP)
            else:
                self.aiplane.set_state(PlaneInfo.DEPARTING)
            self._waiting=15

        else:
            self.log("Circuit",self.aircraft.callsign,', order ignored', instance)
    
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
           alias.SWITCHING_OFF: "switching off",
           alias.TAXI_PARK: "parking {park}"
        }
        msg = templates.get(order.get_instruction())
        if not msg:
            llogger.info("No readback for %s" % order.get_instruction())
            return
        msg = re.sub(r'{cs}',short_callsign(order.receiver.callsign),msg)
        msg = re.sub(r'{icao}',order.sender.airport.icao,msg)
        msg = re.sub(r'{comm}',order.sender.identifier,msg)
        msg = re.sub(r'{rwy}',say_number(order.get_param(Order.PARAM_RUNWAY,'')),msg)
        msg = re.sub(r'{alt}',str(order.get_param(Order.PARAM_ALTITUDE,'')),msg)
        msg = re.sub(r'{cirt}',order.get_param(Order.PARAM_CIRCUIT_TYPE,''),msg)
        msg = re.sub(r'{cirw}',order.get_param(Order.PARAM_CIRCUIT_WP,''),msg)
        msg = re.sub(r'{num}',str(order.get_param(Order.PARAM_NUMBER,'')),msg)
        msg = re.sub(r'{freq}',str(order.get_param(Order.PARAM_FREQUENCY,'')),msg)
        msg = re.sub(r'{conn}',str(order.get_param(Order.PARAM_CONTROLLER,'')),msg)
        msg = re.sub(r'{park}',str(order.get_param(Order.PARAM_PARKING,'')),msg)
        if order.get_param(Order.PARAM_NUMBER):
            msg = re.sub(r'{onum}',', number %s' % order.get_param(Order.PARAM_NUMBER),msg)
        if order.get_param(Order.PARAM_LINEUP):
            msg = re.sub(r'{lineup}',' and line up',msg)
        if order.get_param(Order.PARAM_HOLD):
            msg = re.sub(r'{hld}',' and hold',msg)
        if order.get_param(Order.PARAM_SHORT):
            msg = re.sub(r'{short}',' short',msg)
        
        if order.get_param(Order.PARAM_QNH):
            msg = re.sub(r'{qnh}','. QNH %s' % say_number(order.get_param(Order.PARAM_QNH)),msg)

        # Clean up tags not replaced
        msg = re.sub(r'{\w+}','',msg)
        msg += ", %s" % short_callsign(order.receiver.callsign)
        req = "req=roger;laor=%s" % order.get_instruction()
        llogger.debug("readback: %s | %s" % (req,msg,))        
        threading.Thread(target=self.aiplane.send_request,args=(req,msg,)).start()
           
class Circuits(Cache):            
    pass

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

