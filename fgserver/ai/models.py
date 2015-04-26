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
from fgserver.models import Airport, Aircraft
from fgserver.ai import AIPlane, PlaneInfo

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
        reverse= normdeg(straight+180)
        left = normdeg(straight-90)
        right = normdeg(straight+90)
        apalt=float(self.airport.altitude)
        rwystart = move(runway.position(), reverse, runway.length/2,apalt)
        rwyend = move(runway.position(), straight, runway.length/2,apalt)
        position = move(rwystart,left,30*units.FT,apalt)
        self.create_waypoint(position, "Parking %s"%runway.name, WayPoint.PARKING, PlaneInfo.STOPPED)
        position = move(rwystart,straight,30*units.FT,apalt)
        self.create_waypoint(position, "Hold %s"%runway.name, WayPoint.RWY, PlaneInfo.DEPARTING)
        position = move(rwystart,straight,runway.length*0.75,apalt)
        self.create_waypoint(position, "Rotate %s"%runway.name, WayPoint.RWY, PlaneInfo.DEPARTING)
        # get to 10 meters altitude after exit the runway, then start climbing
        position = elevate(rwyend,apalt+10)
        self.create_waypoint(position, "Departure %s"%runway.name, WayPoint.RWY, PlaneInfo.CLIMBING)
        position = move(position,straight,self.radius,apalt+self.altitude)
        self.create_waypoint(position, "Cruising", WayPoint.POINT, PlaneInfo.CRUISING)
        position = move(rwyend,right,self.radius,apalt+self.altitude+1000*units.FT)
        self.create_waypoint(position, "Crosswind %s"%runway.name, WayPoint.CIRCUIT, PlaneInfo.CIRCUIT)
        position = move(position,left,self.radius*2,apalt+self.altitude)
        self.create_waypoint(position, "Downwind %s"%runway.name, WayPoint.CIRCUIT, PlaneInfo.CIRCUIT)
        position = move(position,reverse,self.radius,apalt+self.altitude)
        self.create_waypoint(position, "Base %s"%runway.name, WayPoint.CIRCUIT, PlaneInfo.CIRCUIT)
        position = move(position,right,self.radius,apalt+500*units.FT)
        self.create_waypoint(position, "Final %s"%runway.name, WayPoint.CIRCUIT, PlaneInfo.LANDING)
        position = move(rwystart,reverse,30,apalt+15)
        self.create_waypoint(position, "Flare %s"%runway.name, WayPoint.CIRCUIT, PlaneInfo.LANDING)
        position = move(rwystart,straight,20,apalt)
        self.create_waypoint(position, "Touchdown %s"%runway.name, WayPoint.RWY, PlaneInfo.TOUCHDOWN)
        self.create_waypoint(runway.position(), "Taxi %s"%runway.name, WayPoint.RWY, PlaneInfo.TAXIING)        
        position = move(rwyend,left,30*units.FT,apalt)
        self.create_waypoint(position, "Taxi 2 %s"%runway.name, WayPoint.TAXI, PlaneInfo.TAXIING)
        position = move(rwystart,left,30*units.FT,apalt)
        self.create_waypoint(position, "Parking %s"%runway.name, WayPoint.PARKING, PlaneInfo.STOPPED)
    
    def waypoint(self):
        return self.waypoints.all()[self._waypoint]
    
    def update(self,time):
        #if self.aircraft.state < 1:
        #    return
        dt = time-self.time
        if self._waiting:
            self._waiting -=dt
            if self._waiting < 0:
                self._waiting=0
            return self.aircraft
        wp = self.waypoint()
        plane = self.aiplane
        if not wp:
            return plane.get_pos_message()
        course = plane.heading_to(wp.position)
        dist = plane.speed * dt
        dist_to=get_distance(plane.position, wp.position)
        #print "course: %s, dist:%s, dist_to:%s" % (course,dist,dist_to)
        seconds_before=0
        if len(self.waypoints)-1 > self._waypoint:
            seconds_before = 60/plane.turn_rate
        turn_dist = dist_to - dist*seconds_before*dt
        step = False
        if dist > turn_dist:
            print "reached waypoint %s" % wp
            dist = min(dist,dist_to)
            plane.course = course
            step = True
        plane.move(course,dist,dt)
        if step:
            plane.set_state(wp.status)
            self._waypoint += 1
            if self.waypoint():
                plane.waypoint = self.waypoint()
                plane.target_altitude=self.waypoint().position.z
                 
                print "target altitude %sm" % plane.target_altitude
            else:
                self.circuit.end()
        self.time = time
        plane.update_aircraft()
        return plane.get_pos_message()
        
# class CircuitOld():
#     airport=ForeignKey(Airport)
#     radius = FloatField(default=2*units.NM)
#     radius.description="Radius of the circuit (in meters)"
#     altitude=FloatField(default=1000*units.FT)
#     altitude.description="Altitude of the circuit (in meters)"
#     time=0
#     waypoints=[]
#     _waypoint=0
#     FINAL = 500*units.FT
#     _waiting=0
# 
#     def reset(self):
#         self.aircraft=AIPlane(self.name)
#         self.aircraft.airport = self.airport
#         self.waypoints=[]
#         self.calculateCircuit()
#         self._waypoint=0
#         for wp in self.waypoints:
#             print "wp: %s" % wp
#         
#         rwy = self.airport.active_runway()
#         #print "reset: rwy: %s" % rwy.position().get_array()
#         
#         #pos = move(rwy.position(),normalize(rwy.bearing),rwy.length / 2, rwy.altitude+1.8)
#         self.aircraft.position=self.waypoint().position
#         q1 = Quaternion.fromLatLon(rwy.lat, rwy.lon)
#         q2 = Quaternion.fromYawPitchRoll(rwy.bearing, 0, 0)
#         orient =q1.multiply(q2).normalize().get_angle_axis()
#         self.aircraft.orientation=Position.fromV3D(orient)
#         self.aircraft.waypoint = self.waypoint()
#         self._waiting=30
#         self.aircraft.set_state(PlaneInfo.TAXIING)
#         print "reset: %s, %s" %( self.aircraft.position.get_array() ,self.aircraft.orientation.get_array())
#     
#     def get_pos_message(self):
#         return self.aircraft.get_pos_message()
# 
#     def waypoint(self):
#         ''' Gets the current waypoint'''
#         if len(self.waypoints) > self._waypoint:
#             return self.waypoints[self._waypoint]
#         return None
#     
#     def update(self,time):
#         #if self.aircraft.state < 1:
#         #    return
#         dt = time-self.time
#         if self._waiting:
#             self._waiting -=dt
#             if self._waiting < 0:
#                 self._waiting=0
#             return
#         wp = self.waypoint()
#         if not wp:
#             return
#         plane = self.aircraft
#         course = plane.heading_to(wp.position)
#         dist = plane.speed * dt
#         dist_to=get_distance(plane.position, wp.position)
#         #print "course: %s, dist:%s, dist_to:%s" % (course,dist,dist_to)
#         seconds_before=0
#         if len(self.waypoints)-1 > self._waypoint:
#             seconds_before = 60/plane.turn_rate
#         turn_dist = dist_to - dist*seconds_before*dt
#         step = False
#         if dist > turn_dist:
#             print "reached waypoint %s" % wp
#             dist = min(dist,dist_to)
#             plane.course = course
#             step = True
#         plane.move(course,dist,dt)
#         if step:
#             plane.set_state(wp.status)
#             self._waypoint += 1
#             if self.waypoint():
#                 plane.waypoint = self.waypoint()
#                 plane.target_altitude=self.waypoint().position.z
#                 
#                 print "target altitude %sm" % plane.target_altitude
#             else:
#                 self.reset()
#         self.time = time
#         
#     def calculateCircuit(self):
#         runway = self.airport.active_runway()
#         thead = runway.bearing
#         oheading= normdeg(thead+180)
#         theading = normdeg(thead-90)
#         apalt=float(self.airport.altitude)
#         rwycenter = move(runway.position(), thead, 0,apalt)
#         rwystart = move(runway.position(), oheading, runway.length/2-10,apalt)
#         rwyhld = move(rwystart, thead, 50, apalt)
#         landstart = move(rwystart, thead, 0, apalt+20*units.FT)
#         rotate = move(rwystart, thead, min(900,runway.length*0.8), apalt+15)
#         landend = move(rotate, thead, 0, apalt)
#         rwyend = move(rwystart, thead, runway.length, apalt+10)
#         apt_exit = move(rwyend, thead, 50, apalt+40)
#         
#         cruise = move(rwyend, thead, self.radius, apalt +self.altitude*2)
#         dnwind = move(rwyend, theading, self.radius, apalt + self.altitude)
#         base = move(dnwind, oheading,runway.length+ self.radius, apalt +self.altitude*0.8)
#         finl = move(rwystart, oheading,self.radius, apalt + Circuit.FINAL)
#         prefinl = move(finl,theading,0.3*units.NM,apalt + Circuit.FINAL+50*units.FT)
#         postfinl = move(finl,thead,0.3*units.NM,apalt + Circuit.FINAL-50*units.FT)
#         finl2 = move(rwystart, oheading,0.7*units.NM, apalt + 150*units.FT)
#         sl= None # Startup location
#         #self.waypoints.append(WayPoint(rwystart,WayPoint.PARKING,"%s Parking" % runway.name,PlaneInfo.TAXIING))
#         park = WayPoint(rwystart,WayPoint.TAXI,"Start %s" % runway.name,PlaneInfo.TAXIING)
#         self.waypoints.append(park)
#         hold = WayPoint(rwyhld,WayPoint.RWY,"%s Hold" % runway.name,PlaneInfo.DEPARTING)
#         self.waypoints.append(hold)
#         self.waypoints.append(WayPoint(rwycenter,WayPoint.RWY,"%s Center" % runway.name,PlaneInfo.DEPARTING))
#         self.waypoints.append(WayPoint(rotate,WayPoint.RWY,"%s Rotate" % runway.name,PlaneInfo.CLIMBING))
#         self.waypoints.append(WayPoint(apt_exit,WayPoint.RWY,"%s APT exit" % runway.name,PlaneInfo.CLIMBING))
#         self.waypoints.append(WayPoint(cruise,WayPoint.POINT,"%s Cruise" % runway.name,PlaneInfo.CRUISING))
#         self.waypoints.append(WayPoint(dnwind,WayPoint.CIRCUIT_DOWNWIND,"%s Downwind" % runway.name,PlaneInfo.APPROACHING))
#         self.waypoints.append(WayPoint(base,WayPoint.CIRCUIT_BASE,"%s Base" % runway.name,PlaneInfo.APPROACHING))
#         self.waypoints.append(WayPoint(prefinl,WayPoint.CIRCUIT_FINAL,"%s PreFinal" % runway.name,PlaneInfo.LANDING))
#         self.waypoints.append(WayPoint(postfinl,WayPoint.CIRCUIT_FINAL,"%s PostFinal" % runway.name,PlaneInfo.LANDING))
#         self.waypoints.append(WayPoint(finl2,WayPoint.CIRCUIT_FINAL,"%s Final 2" % runway.name,PlaneInfo.LANDING))
#         self.waypoints.append(WayPoint(landstart,WayPoint.RWY,"%s Land start" % runway.name,PlaneInfo.TOUCHDOWN))
#         self.waypoints.append(WayPoint(landend,WayPoint.RWY,"%s landend" % runway.name,PlaneInfo.TAXIING))

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
    TYPE_CHOICES=((POINT,'Point'),(AIRPORT,'Airport'),(NAV,'Nav'),(FIX,'Fix'),(TAXI,'Taxi'),(RWY,'Runway'),(PARKING,'Parking'),(PUSHBACK,'Pushback'),(CIRCUIT,'Circtui'),)

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

