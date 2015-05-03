from fgserver.helper import Position, get_distance, get_heading_to, Vector3D,\
    move, normdeg, Quaternion, geod2cart, normalize
from fgserver.messages import PosMsg, PROP_CHAT, alias
from fgserver import units
from __builtin__ import round, min
from fgserver.units import FT
from fgserver.models import Aircraft, Request, Airport, Order
from django.utils import timezone
from datetime import timedelta
from random import randint
import fgserver

class PlaneInfo():
    

    DEFAULT_MODEL="Aircraft/c310/Models/c310-dpm.xml"

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
    CIRCUIT_CROSSWIND=11
    CIRCUIT_DOWNWIND=12
    CIRCUIT_BASE=13
    CIRCUIT_FINAL=14
    CIRCUIT_STRAIGHT=15
    SHORT=16
    LINED_UP=17
    
    TUNNED=18
    
    CHOICES = (
        (0,'None'),               
        (STOPPED,'Stopped'),
        (PUSHBACK,'Pushback'),
        (TAXIING,'Taxiing'),
        (DEPARTING,'Departing'),
        (TURNING,'Turning'),
        (CLIMBING,'Climbing'),
        (CRUISING,'Cruising'),
        (APPROACHING,'Approaching'),
        (LANDING,'Landing'),
        (TOUCHDOWN,'Touchdown'),
        (CIRCUIT_CROSSWIND,'Crosswind'),
        (CIRCUIT_DOWNWIND,'Downwind'),
        (CIRCUIT_BASE,'Base'),
        (CIRCUIT_FINAL,'Final'),
        (CIRCUIT_STRAIGHT,'Straight'),
        (SHORT,'Short of runway'),
        (LINED_UP,'Lined up'),
        (TUNNED,'Tunned'),
    )
    CHOICES_STR = (
        ('0','None'),               
        (str(STOPPED),'Stopped'),
        (str(PUSHBACK),'Pushback'),
        (str(TAXIING),'Taxiing'),
        (str(DEPARTING),'Departing'),
        (str(TURNING),'Turning'),
        (str(CLIMBING),'Climbing'),
        (str(CRUISING),'Cruising'),
        (str(APPROACHING),'Approaching'),
        (str(LANDING),'Landing'),
        (str(TOUCHDOWN),'Touchdown'),
        (str(CIRCUIT_CROSSWIND),'Crosswind'),
        (str(CIRCUIT_DOWNWIND),'Downwind'),
        (str(CIRCUIT_BASE),'Base'),
        (str(CIRCUIT_FINAL),'Final'),
        (str(CIRCUIT_STRAIGHT),'Straight'),
        (str(SHORT),'Short of runway'),
        (str(LINED_UP),'Lined up'),
        (str(TUNNED),'Tunned'),
    )
         
class AIPlane():
    circuit = None
    state = 0
    position=None
    orientation=None
    waypoint = None
    course=0
    speed=0 #in M/s
    linear_velocity=None
    vertical_speed=0
    turn_rate=1
    bank_sense=0
    message=""
    target_course=0
    target_vertical_speed=0
    target_altitude=0
    
    def callsign(self):
        return self.circuit.aircraft.callsign
    
    def __init__(self,circuit):
        self.circuit = circuit
        self.waypoint = self.circuit.waypoint()
        self.position = self.waypoint.get_position()
        self.orientation = Position()
        self.linear_velocity = Position()
        #self.set_state(self.waypoint.status)
        #self.update_aircraft()
        self.log("created")
        
    def log(self,*argv):
        fgserver.info("AI %s" % self.callsign(),*argv)

    def set_state(self,state):
        if state <=0:
            return
        changed = False
        if self.state != state:
            self.log("State changed from %s to %s" % (PlaneInfo.CHOICES[self.state][1],PlaneInfo.CHOICES[state][1]))
            changed = True
        self.state=state
        laor = getattr(self.circuit,'_last_order',None)
        if laor:
            self.log(laor,laor.short(),laor.hold())
        if state in [PlaneInfo.STOPPED, PlaneInfo.PUSHBACK]\
                or (state==PlaneInfo.SHORT and laor and laor.short())\
                or (state==PlaneInfo.LINED_UP and laor and laor.get_param(Order.PARAM_LINEUP)):
            self.speed=0
            self.vertical_speed=0
            self.turn_rate=1
            self.target_vertical_speed=1
        elif state == PlaneInfo.TAXIING or (state==PlaneInfo.SHORT and not laor.short()):
            self.turn_rate = 10
            self.speed = 20*units.KNOTS
            self.target_vertical_speed=1
        elif state == PlaneInfo.DEPARTING or (state==PlaneInfo.LINED_UP and laor.hold()):
            self.turn_rate = 3
            self.speed = 70*units.KNOTS
            self.target_vertical_speed=100*units.FPM
        elif state == PlaneInfo.CLIMBING:
            self.turn_rate = 3
            self.speed = 100*units.KNOTS
            self.target_vertical_speed=900*units.FPM
        elif state == PlaneInfo.CRUISING:
            self.turn_rate = 3
            self.speed = 140*units.KNOTS
            self.target_vertical_speed=200*units.FPM
        elif state == PlaneInfo.LANDING:
            knots = self.speed/units.KNOTS
            self.turn_rate = 1.5
            self.speed = 70*units.KNOTS
            self.target_vertical_speed=300*units.FPM
        elif state == PlaneInfo.TOUCHDOWN:
            self.turn_rate=1.5
            self.speed=40*units.KNOTS
        else:
            self.turn_rate = 3
            self.speed = 80*units.KNOTS
            self.target_vertical_speed=400*units.FPM
        self.log("turn_rate",self.turn_rate,"speed",self.speed,"target_vs",self.target_vertical_speed)
        if changed:
            self.check_request()
    
    def airport(self):
        return self.circuit.airport

    def aircraft(self):
        return self.circuit.aircraft
    
    def send_request(self,req,msg):
        self.message=msg
        date=timezone.now()
        request = Request(sender=self.aircraft(),date=date,request=req)
        self.log("Sending request",request)
        request.save()

    def check_request(self):
        self.log("check_request",self.waypoint.type)
        from fgserver.ai.models import WayPoint
        if not self.airport():
            return
        laor = getattr(self.circuit,'_last_order',None)
        if self.state == PlaneInfo.CIRCUIT_CROSSWIND:
            req = "req=crosswind;apt=%s" % self.airport().icao
            msg="%s Tower, %s, Crosswind for runway %s" % (self.airport().name, self.callsign(),self.airport().active_runway())
            self.send_request(req,msg)
        elif self.state == PlaneInfo.CIRCUIT_DOWNWIND:
            req = "req=downwind;apt=%s" % self.airport().icao
            msg="%s Tower, %s, Downwind for runway %s" % (self.airport().name, self.callsign(),self.airport().active_runway())
            self.send_request(req,msg)
        elif self.state == PlaneInfo.CIRCUIT_BASE:
            req = "req=base;apt=%s" % self.airport().icao
            msg="%s Tower, %s, Turning base for runway %s" % (self.airport().name, self.callsign(),self.airport().active_runway())
            self.send_request(req,msg)
        elif self.state == PlaneInfo.CIRCUIT_FINAL:
            req = "req=final;apt=%s" % self.airport().icao
            msg="%s Tower, %s, Final for runway %s" % (self.airport().name, self.callsign(),self.airport().active_runway())
            self.send_request(req,msg)    
        elif self.state == PlaneInfo.PUSHBACK:
            req = "req=readytaxi;apt=%s" % self.airport().icao
            msg="%s Tower, %s, ready to taxi" % (self.airport().name, self.callsign())
            self.send_request(req,msg)
        elif self.state == PlaneInfo.LINED_UP and laor.get_param(Order.PARAM_LINEUP):
            req = "req=readytko;apt=%s" % self.airport().icao
            msg="%s Tower, %s, ready for takeoff" % (self.airport().name, self.callsign())
            self.send_request(req,msg)
        elif self.state == PlaneInfo.SHORT and laor.short():
            req = "req=holdingshort;apt=%s" % self.airport().icao
            msg="%s Tower, %s, holding short of runway %s" % (self.airport().name, self.callsign(),self.airport().active_runway())
            self.send_request(req,msg)
        elif self.state== PlaneInfo.STOPPED and self.waypoint.type == WayPoint.PARKING:
            req = "req=tunein;apt=%s" % self.airport().icao
            self.send_request(req,'')

        elif self.state== PlaneInfo.CLIMBING:
            req = "req=leaving;apt=%s" % self.airport().icao
            self.send_request(req,"%s Tower, %s, leaving airfield" % (self.airport().name, self.callsign()))

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
        if not self.state in [PlaneInfo.TAXIING,PlaneInfo.PUSHBACK, PlaneInfo.DEPARTING] and coursediff >= 0.01:
            roll = (self.turn_rate*self.bank_sense)*10
            #self.log("tr",self.turn_rate,"roll",roll,"bank",self.bank_sense)
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
        return self.state in [PlaneInfo.STOPPED,PlaneInfo.TAXIING,PlaneInfo.DEPARTING,PlaneInfo.LINED_UP,PlaneInfo.SHORT, PlaneInfo.TOUCHDOWN]

    
    def _fill_properties(self,pos):
        props = pos.properties
        props.set_prop(302,self.speed*50)
        props.set_prop(312,self.speed*50)
        if self.on_ground() or self.state == PlaneInfo.LANDING:
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
        pos.model = self.aircraft().model
        pos.angular_vel=Position(0,0,0).get_array()
        pos.angular_accel=Position(0,0,0).get_array()
        pos.linear_accel=Position(0,0,0).get_array()
        pos.linear_vel=self.linear_velocity.get_array()
        pos.orientation=self.orientation.get_array()
        pos.position=self.position.get_array_cart()
        self._fill_properties(pos)
        return pos
        
    def update_aircraft(self):
        a = self.aircraft()
        a.lat = self.position.x
        a.lon = self.position.y
        a.altitude = self.position.z
        a.heading= self.course
        #print "upd",a.lat,a.lon,a.altitude,a.heading
        
        
