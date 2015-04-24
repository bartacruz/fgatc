# -*- encoding: utf-8 -*-
'''
Created on Apr 19, 2015

@author: bartacruz
'''
from fgserver.helper import Position, get_distance, get_heading_to, Vector3D,\
    move, normdeg, Quaternion, geod2cart, normalize
from fgserver.messages import PosMsg, PROP_CHAT
from fgserver import units
from __builtin__ import round, min
from fgserver.units import FT
from fgserver.models import Aircraft, Request
from django.utils import timezone

class PlaneInfo():
    STOPPED = 1
    PUSHBACK = 2
    TAXIING = 3
    DEPARTING = 4
    TURNING = 5
    CLIMBING = 6
    CRUISING = 7
    APPROACHING = 8
    LANDING = 9
    TOUCHDOWN = 10
    CIRCUIT=11
    
    status=0
    position=None
    position=None
    waypoint = None
    callsign = None
    
    speed=0
    heading=0
    roll=0
    pitch=0
    vertical_speed=0
    
    def on_ground(self):
        return self.status in [PlaneInfo.STOPPED,PlaneInfo.TAXIING,PlaneInfo.DEPARTING]

class WayPoint():
    position=None
    name=None
    type=0
    status = 0
    POINT=0
    AIRPORT=1
    NAV=2
    FIX=3
    TAXI=4
    RWY=5
    PARKING=6
    PUSHBACK=7
 
    CIRCUIT_STRAIGHT=10
    CIRCUIT_CROSSWIND=11
    CIRCUIT_DOWNWIND=12
    CIRCUIT_BASE=13
    CIRCUIT_FINAL=14
       
    def __init__(self,position=None,wtype=0,name=None, status=PlaneInfo.STOPPED):
        self.position=position
        self.name=name
        self.type=wtype
        self.status = status # status that is set to the plane when WayPoint is reached
         
    def route_from(self,position):
        distance = get_distance(position,self.position)
        heading = get_heading_to(position,self.position)
        alt = self.position.alt - position.alt
        return Vector3D(distance,heading,alt)

    def __str__(self):
        return "WP %s, type:%s, pos= %s" %(self.name,self.type,self.position)
    def __unicode__(self):
        return "WP %s, type:%s, pos= %s" %(self.name,self.type,self.position)

class AIPlane():
    DEFAULT_MODEL="Aircraft/c310/Models/c310-dpm.xml"
    aircraft=None
    airport = None
    model=DEFAULT_MODEL
    state = PlaneInfo.STOPPED
    position=None
    orientation=None
    waypoint = None
    course=0
    speed=0 #in M/s
    linear_velocity=None
    vertical_speed=0
    turn_rate=0
    bank_sense=0
    message=""
    target_course=0
    target_vertical_speed=0
    target_altitude=0
    
    def callsign(self):
        return self.aircraft.callsign
    
    def __init__(self,callsign):
        self.model = self.DEFAULT_MODEL
        self.state = PlaneInfo.STOPPED
        self.position = Position()
        self.orientation = Position()
        self.linear_velocity = Position()
        self.aircraft,created = Aircraft.objects.get_or_create(callsign=callsign)
        self.aircraft.ip = None
        self.aircraft.state=1
        self.aircraft.save()
        
    def set_state(self,state):
        if state <=0:
            return
        if self.state != state:
            print "State changed from %s to %s" % (self.state, state)
        self.state=state
        if state == PlaneInfo.STOPPED:
            self.speed=0
            self.vertical_speed=0
            self.turn_rate=1
            self.target_vertical_speed=1
        elif state == PlaneInfo.TAXIING:
            self.turn_rate = 40
            self.speed = 20*units.KNOTS
            self.target_vertical_speed=1
        elif state == PlaneInfo.DEPARTING:
            self.speed = 70*units.KNOTS
            self.target_vertical_speed=100*units.FPM
        elif state == PlaneInfo.CLIMBING:
            knots = self.speed/units.KNOTS
            self.turn_rate = 49000/(knots*knots)
            self.speed = 100*units.KNOTS
            self.target_vertical_speed=900*units.FPM
        elif state == PlaneInfo.CRUISING:
            knots = self.speed/units.KNOTS
            self.turn_rate = 49000/(knots*knots)
            self.speed = 140*units.KNOTS
            self.target_vertical_speed=200*units.FPM
        elif state == PlaneInfo.APPROACHING:
            knots = self.speed/units.KNOTS
            self.turn_rate = 19000/(knots*knots)
            self.speed = 80*units.KNOTS
            self.target_vertical_speed=700*units.FPM
        elif state == PlaneInfo.LANDING:
            knots = self.speed/units.KNOTS
            self.turn_rate = 19000/(knots*knots)
            self.speed = 70*units.KNOTS
            self.target_vertical_speed=300*units.FPM
        elif state == PlaneInfo.TOUCHDOWN:
            self.turn_rate=1
            self.speed=40*units.KNOTS
        
        self.check_request()
        
    def check_request(self):
        print "check_request",self.airport,self.waypoint.type
        if not self.airport:
            return
        if self.waypoint.type == WayPoint.CIRCUIT_DOWNWIND:
            req = "req=downwind;apt=%s" % self.airport.icao
            request = Request(sender=self.aircraft,date=timezone.now(),request=req)
            self.message="%s Tower, %s, Dowwnind for runway %s" % (self.airport.name, self.callsign(),self.airport.active_runway())
            print req,self.message
            request.save()
        elif self.waypoint.type == WayPoint.TAXI:
            req = "req=readytko;apt=%s" % self.airport.icao
            request = Request(sender=self.aircraft,date=timezone.now(),request=req)
            self.message="%s Tower, %s, ready for takeoff" % (self.airport.name, self.callsign())
            print req,self.message
            request.save()
        elif self.waypoint.type == WayPoint.PARKING:
            req = "req=tunein;apt=%s" % self.airport.icao
            request = Request(sender=self.aircraft,date=timezone.now(),request=req)
            self.message=""
            print req,self.message
            request.save()

    def move(self,course,distance,dt):
        self.target_course=course
        newcourse = self.next_course(dt)
        newalt = self.next_altitude(dt)
        newpos = move(self.position, newcourse, distance, newalt)
        p1=self.position.to_cart()
        p = newpos.to_cart()
        dif =  p.substract(p1)
        #asspeed = dif.get_length()/dt
        vs = Position.fromV3D(dif.scale(1/dt))
        q1 = Quaternion.fromLatLon(newpos.x, newpos.y)
        coursediff=abs(newcourse - course)
        roll = 0
        if not self.state in [PlaneInfo.TAXIING,PlaneInfo.PUSHBACK] and coursediff >= 0.01:
            roll = (self.turn_rate*self.bank_sense)/dt
        q2 = Quaternion.fromYawPitchRoll(newcourse, 0, roll)
        
        self.position = newpos
        self.orientation =  Position.fromV3D(q1.multiply(q2).normalize().get_angle_axis())
        self.linear_velocity = vs
        self.course=newcourse
        
        
    def next_altitude(self,dt):
        if self.speed == 0 or abs(self.position.z - self.target_altitude) <= 0.1:
            return self.target_altitude
        multi=1
        diff = self.target_altitude - self.position.z
        if diff < 0:
            multi = -1
        vsdiff = self.target_vertical_speed -self.vertical_speed
        vsdiffa = abs(vsdiff)
        if vsdiff !=0:
            if self.vertical_speed==0:
                self.vertical_speed=0.5
            vsmult = round(vsdiff / abs(vsdiff))
            self.vertical_speed += vsmult * min((self.vertical_speed*self.vertical_speed)/vsdiffa, vsdiffa)
        
        vs = multi * min(self.vertical_speed*dt,abs(diff))
        na= self.position.z+vs;
        return na

    def next_course(self,dt):
        hdiff = abs(self.course - self.target_course)
        if self.speed == 0 or hdiff < 0.01:
            return self.target_course
        if hdiff > 180:
            hdiff = abs(hdiff-360)
        sumc = self.course +hdiff
        if sumc > 360:
            sumc -= 360
        self.bank_sense=1.0
        if abs(sumc - self.target_course) > 0.0001:
            self.bank_sense = -1.0
        nc =normdeg(self.course + self.bank_sense*min(hdiff, self.turn_rate*dt))
        return nc
    
    def heading_to(self,to):
        return get_heading_to(self.position, to)
    def on_ground(self):
        return self.state in [PlaneInfo.STOPPED,PlaneInfo.TAXIING,PlaneInfo.DEPARTING]

    
    def _fill_properties(self,pos):
        props = pos.properties
        props.set_prop(302,self.speed*50)
        props.set_prop(312,self.speed*50)
        if self.on_ground():
            props.set_prop(1004,1)
            props.set_prop(201,1)
            props.set_prop(211,1)
            props.set_prop(221,1)
        else:
            props.set_prop(1004,0)
            props.set_prop(201,0)
            props.set_prop(211,0)
            props.set_prop(221,0)
        if self.message:
            props.set_prop(PROP_CHAT,self.message)
        
    def get_pos_message(self):
        pos = PosMsg()
        pos.header.callsign=self.callsign()
        pos.model = self.model
        pos.angular_vel=Position(0,0,0).get_array()
        pos.angular_accel=Position(0,0,0).get_array()
        pos.linear_accel=Position(0,0,0).get_array()
        pos.linear_vel=self.linear_velocity.get_array()
        pos.orientation=self.orientation.get_array()
        pos.position=self.position.get_array_cart()
        self._fill_properties(pos)
        return pos
        
class Circuit():
    time=0
    aircraft=None
    airport=None
    waypoints=[]
    _waypoint=0
    RADIUS=2*units.NM
    ALTITUDE=1000*units.FT
    FINAL = 500*units.FT
    _waiting=0

    def __init__(self,airport, callsign):
        self.aircraft=AIPlane(callsign)
        self.airport=airport
        self.aircraft.airport = airport
        
    def reset(self):
        self.waypoints=[]
        self.calculateCircuit()
        self._waypoint=0
        for wp in self.waypoints:
            print "wp: %s" % wp
        
        rwy = self.airport.active_runway()
        #print "reset: rwy: %s" % rwy.position().get_array()
        
        #pos = move(rwy.position(),normalize(rwy.bearing),rwy.length / 2, rwy.altitude+1.8)
        self.aircraft.position=self.waypoint().position
        q1 = Quaternion.fromLatLon(rwy.lat, rwy.lon)
        q2 = Quaternion.fromYawPitchRoll(rwy.bearing, 0, 0)
        orient =q1.multiply(q2).normalize().get_angle_axis()
        self.aircraft.orientation=Position.fromV3D(orient)
        self.aircraft.waypoint = self.waypoint()
        self._waiting=30
        self.aircraft.set_state(PlaneInfo.TAXIING)
        print "reset: %s, %s" %( self.aircraft.position.get_array() ,self.aircraft.orientation.get_array())
    
    def get_pos_message(self):
        return self.aircraft.get_pos_message()

    def waypoint(self):
        if len(self.waypoints) > self._waypoint:
            return self.waypoints[self._waypoint]
        return None
    
    def update(self,time):
        #if self.aircraft.state < 1:
        #    return
        dt = time-self.time
        if self._waiting:
            self._waiting -=dt
            if self._waiting < 0:
                self._waiting=0
            return
        wp = self.waypoint()
        if not wp:
            return
        plane = self.aircraft
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
                self.reset()
        self.time = time
        
    def calculateCircuit(self):
        runway = self.airport.active_runway()
        thead = runway.bearing
        oheading= normdeg(thead+180)
        theading = normdeg(thead-90)
        apalt=float(self.airport.altitude)
        rwycenter = move(runway.position(), thead, 0,apalt)
        rwystart = move(runway.position(), oheading, runway.length/2-10,apalt)
        rwyhld = move(rwystart, thead, 50, apalt)
        landstart = move(rwystart, thead, 0, apalt+20*units.FT)
        rotate = move(rwystart, thead, min(900,runway.length*0.8), apalt+15)
        landend = move(rotate, thead, 0, apalt)
        rwyend = move(rwystart, thead, runway.length, apalt+10)
        apt_exit = move(rwyend, thead, 50, apalt+40)
        
        cruise = move(rwyend, thead, Circuit.RADIUS, apalt +Circuit.ALTITUDE*2)
        dnwind = move(rwyend, theading, Circuit.RADIUS, apalt + Circuit.ALTITUDE)
        base = move(dnwind, oheading,runway.length+ Circuit.RADIUS, apalt +Circuit.ALTITUDE*0.8)
        finl = move(rwystart, oheading,Circuit.RADIUS, apalt + Circuit.FINAL)
        prefinl = move(finl,theading,0.3*units.NM,apalt + Circuit.FINAL+50*units.FT)
        postfinl = move(finl,thead,0.3*units.NM,apalt + Circuit.FINAL-50*units.FT)
        finl2 = move(rwystart, oheading,0.7*units.NM, apalt + 150*units.FT)
        sl= None # Startup location
        #self.waypoints.append(WayPoint(rwystart,WayPoint.PARKING,"%s Parking" % runway.name,PlaneInfo.TAXIING))
        park = WayPoint(rwystart,WayPoint.TAXI,"Start %s" % runway.name,PlaneInfo.TAXIING)
        self.waypoints.append(park)
        hold = WayPoint(rwyhld,WayPoint.RWY,"%s Hold" % runway.name,PlaneInfo.DEPARTING)
        self.waypoints.append(hold)
        self.waypoints.append(WayPoint(rwycenter,WayPoint.RWY,"%s Center" % runway.name,PlaneInfo.DEPARTING))
        self.waypoints.append(WayPoint(rotate,WayPoint.RWY,"%s Rotate" % runway.name,PlaneInfo.CLIMBING))
        self.waypoints.append(WayPoint(apt_exit,WayPoint.RWY,"%s APT exit" % runway.name,PlaneInfo.CLIMBING))
        self.waypoints.append(WayPoint(cruise,WayPoint.POINT,"%s Cruise" % runway.name,PlaneInfo.CRUISING))
        self.waypoints.append(WayPoint(dnwind,WayPoint.CIRCUIT_DOWNWIND,"%s Downwind" % runway.name,PlaneInfo.APPROACHING))
        self.waypoints.append(WayPoint(base,WayPoint.CIRCUIT_BASE,"%s Base" % runway.name,PlaneInfo.APPROACHING))
        self.waypoints.append(WayPoint(prefinl,WayPoint.CIRCUIT_FINAL,"%s PreFinal" % runway.name,PlaneInfo.LANDING))
        self.waypoints.append(WayPoint(postfinl,WayPoint.CIRCUIT_FINAL,"%s PostFinal" % runway.name,PlaneInfo.LANDING))
        self.waypoints.append(WayPoint(finl2,WayPoint.CIRCUIT_FINAL,"%s Final 2" % runway.name,PlaneInfo.LANDING))
        self.waypoints.append(WayPoint(landstart,WayPoint.RWY,"%s Land start" % runway.name,PlaneInfo.TOUCHDOWN))
        self.waypoints.append(WayPoint(landend,WayPoint.RWY,"%s landend" % runway.name,PlaneInfo.TAXIING))
        
        
