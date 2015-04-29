'''
Created on Apr 24, 2015

@author: bartacruz
'''
from fgserver.helper import Position, get_distance, move, normdeg, Quaternion,\
    elevate
from fgserver import units
from __builtin__ import min
from django.db.models.base import Model
from django.db.models.fields.related import ForeignKey
from django.db.models.fields import CharField, FloatField, IntegerField
from fgserver.models import Airport, Aircraft, Order
from fgserver.ai import AIPlane, PlaneInfo
from django.db.models.signals import post_save
from django.dispatch.dispatcher import receiver

class FlightPlan(Model):
    name = CharField(max_length=8)
    description = CharField(max_length=255,null=True,blank=True)
    aircraft=ForeignKey(Aircraft, related_name="plans")

    def update(self,time):
        pass
    
    def init(self):
        pass
    
class Circuit(FlightPlan):
    ''' A standard left-circuit over an airfield ''' 
    airport=ForeignKey(Airport, related_name='circuits')
    radius = FloatField(default=2*units.NM)
    radius.description="Radius of the circuit (in meters)"
    altitude=FloatField(default=1000*units.FT)
    altitude.description="Altitude of the circuit (in meters)"    
    
    aiplane = None
    _waypoint=0
    _time=0
    def init(self):
        self.waypoints.all().delete()
        self.aircraft.state=2
        self.generate_waypoints()
        self.aiplane = AIPlane(self)
        
    def end(self):
        print "END OF CIRCUIT %s" % self.name
    
    def create_waypoint(self,position,name,atype,status):
        wp = WayPoint(flightplan = self,name=name,type=atype,status=status)
        wp.set_position(position)
        wp.save()
        return wp
         
    def generate_waypoints(self):
        runway = self.airport.active_runway()
        straight = runway.bearing
        reverse= normdeg(straight-180)
        left = normdeg(straight-90)
        right = normdeg(straight+90)
        apalt=float(self.airport.altitude*units.FT+2)
        print "runway length", runway.length,runway.length/2
        rwystart = move(runway.position(), reverse, runway.length*units.FT/2,apalt)
        rwyend = move(runway.position(), straight, runway.length*units.FT/2,apalt)
        position = move(rwystart,left,runway.width*units.FT,apalt)
        self.create_waypoint(position, "FParking %s"%runway.name, WayPoint.PARKING, PlaneInfo.STOPPED)
        position = move(rwystart,straight,30*units.FT,apalt)
        self.create_waypoint(position, "Hold %s"%runway.name, WayPoint.HOLD, PlaneInfo.STOPPED)
        position = move(rwystart,straight,runway.length*units.FT*0.75,apalt)
        self.create_waypoint(position, "Rotate %s"%runway.name, WayPoint.RWY, PlaneInfo.DEPARTING)
        # get to 10 meters altitude after exit the runway, then start climbing
        position = elevate(rwyend,apalt+10)
        self.create_waypoint(position, "Departure %s"%runway.name, WayPoint.RWY, PlaneInfo.CLIMBING)
        position = move(position,straight,self.radius,apalt+self.altitude)
        self.create_waypoint(position, "Cruising", WayPoint.POINT, PlaneInfo.CRUISING)
        position = move(position,normdeg(straight+40),self.radius*0.8,apalt+self.altitude)
        self.create_waypoint(position, "Cruising 2", WayPoint.POINT, PlaneInfo.CRUISING)
        position = move(position,normdeg(straight+80),self.radius*0.8,apalt+self.altitude)
        self.create_waypoint(position, "Cruising 3", WayPoint.POINT, PlaneInfo.CRUISING)
        position = move(position,normdeg(straight+120),self.radius*0.8,apalt+self.altitude)
        self.create_waypoint(position, "Cruising 4", WayPoint.POINT, PlaneInfo.CRUISING)
        position = move(position,normdeg(straight+150),self.radius*0.5,apalt+self.altitude)
        self.create_waypoint(position, "Cruising 5", WayPoint.POINT, PlaneInfo.CRUISING)
        position = move(position,normdeg(straight+190),self.radius*0.5,apalt+self.altitude)
        self.create_waypoint(position, "Cruising 5", WayPoint.POINT, PlaneInfo.CRUISING)
        position = move(position,normdeg(straight+230),self.radius*0.5,apalt+self.altitude)
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
    
    def waypoint(self):
        if self.waypoints.all().count() > self._waypoint:
            return self.waypoints.all().order_by('id')[self._waypoint]
        return None
    
    def update(self,time):
        #if self.aircraft.state < 1:
        #    return
        dt = time-self._time
        plane = self.aiplane
        if not plane:
            print "ERROR: aiplane is null!"
            return
#         if self._waiting:
#             self._waiting -=dt
#             if self._waiting < 0:
#                 self._waiting=0
#             return plane.get_pos_message()
        wp = self.waypoint()
        if not wp:
            print "ERROR: No waypoint set."
            return plane.get_pos_message()
        course = plane.heading_to(wp.get_position())
        dist = plane.speed * dt
        dist_to=get_distance(plane.position, wp.get_position())
        #print "course: %s, dist:%s, dist_to:%s" % (course,dist,dist_to)
        seconds_before=0
        if self.waypoints.count()-1 > self._waypoint:
            seconds_before = 60/plane.turn_rate
        turn_dist = dist_to - dist*seconds_before*dt
        step = False
        if dist >= turn_dist:
            print "reached waypoint %s" % wp
            dist = min(dist,dist_to)
            plane.course = course
            step = True
        plane.move(course,dist,dt)
        if step:
            plane.set_state(wp.status)
            self._waypoint += 1
            print "Next wp:",self._waypoint,self.waypoint()
            if self.waypoint():
                plane.waypoint = self.waypoint()
                plane.target_altitude=self.waypoint().get_position().z
                 
                print "target altitude %sm" % plane.target_altitude
                print "heading",plane.course,plane.heading_to(wp.get_position())
            else:
                self.circuit.end()
        self._time = time
        plane.update_aircraft()
        return plane.get_pos_message()

    def process_order(self,instance):
        print self.name,"procesando orden",instance
        if instance.receiver == self.aircraft:
            order = instance._order
            if order[Order.PARAM_ORDER] == 'tuneok':
                self.aiplane.set_state(PlaneInfo.PUSHBACK)
            if order[Order.PARAM_ORDER] == 'taxito':
                self.aiplane.set_state(PlaneInfo.TAXIING)
            if order[Order.PARAM_ORDER] == 'cleartk':
                self.aiplane.set_state(PlaneInfo.DEPARTING)

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
    flightplan = ForeignKey(FlightPlan, related_name="waypoints")
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

