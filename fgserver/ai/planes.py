'''
Created on 24 de abr. de 2017

@author: julio
'''
from fgserver.helper import Position, get_heading_to_360, short_callsign,\
    move, normdeg, Quaternion, normalize, say_number
    
from fgserver.messages import PosMsg, PROP_CHAT, PROP_OID, alias, PROP_FREQ,\
    sim_time
from fgserver.models import Order, Comm, AircraftStatus
from random import randint
import fgserver
from fgserver.ai.common import PlaneInfo, ReceivedOrder
from fgserver import units
from django.contrib.gis.geos.point import Point
from fgserver import messages
from fgserver.server.server import FGServer
import logging
from django.conf import settings
from django.utils import timezone
from .consumers import StatePlaneConsumer

llogger = logging.getLogger(__name__)

class StatePlaneClient(FGServer):
    
    def __init__(self, plane, delay=0.2, port=None):
        self.plane=plane
        plane.clearances.start = True
        plane.dynamics.wait(randint(5,60))
        self._last_save=timezone.now()
        FGServer.__init__(self, delay=delay, port=port)
        self.server_to = settings.FGATC_AI_SERVER
        #plane.start()
        plane.update(sim_time())
        
    def get_position_message(self):
        status = self.plane.update(sim_time())
        pos = status.get_position_message()
        status.save()
        if (status.date - self._last_save).seconds > 1:
            self.plane.aircraft.save()
            self._last_save = status.date
            StatePlaneConsumer.publish_plane(self.plane) # publish to map!
        return pos

    def after_init(self):
        llogger.debug('Starting client loop')
        self.plane.start()
        while True:
            try:
                pos = self.server.incoming.get(True,.1)
                # TODO: Process requests also (for non controlled airports/UNICOM)
                #llogger.debug('processing order %s' % pos.get_order())
                if not pos or not pos.get_order():
                    continue
                
                freq = pos.get_value(messages.PROP_FREQ) or ''
                freq = int(freq.replace('.','')) 
                if not freq or freq not in  [self.plane.copilot.freq, self.plane.copilot.next_freq]:
                    #llogger.debug("Ignoring %s [%s %s]: %s" % (freq,self.plane.copilot.freq, self.plane.copilot.next_freq, pos.get_order()))
                    continue
                try:
                    order = ReceivedOrder.from_string(pos.get_order())
                    #llogger.debug("Order received %s" % order)
                except:
                    llogger.exception('Evaluating order %s' % pos.get_order())
                    continue
                if order.to ==self.plane.aircraft.callsign:
                    self.plane.process_order(order)
            except:
                pass

class CircuitClient(FGServer):
    
    def __init__(self, circuit, delay=0.2):
        self.circuit=circuit
        self.circuit.init()
        FGServer.__init__(self, delay=delay)
        self.server_to = settings.FGATC_AI_SERVER
        
    def get_position_message(self):
        self.circuit.update(sim_time())
        pos = self.circuit.aircraft.status.get_position_message()
        #print(pos)
        return pos

    def after_init(self):
        llogger.debug('Starting client loop')
        while True:
            try:
                pos = self.server.incoming.get(True,.1)
                # TODO: Process requests also (for non controlled airports/UNICOM)
                #llogger.debug('processing order %s' % pos.get_order())
                if not pos or not pos.get_order():
                    continue
                
                
                freq = pos.get_value(messages.PROP_FREQ) or ''
                freq = int(freq.replace('.','')) 
                if not freq or freq != self.circuit.aircraft.status.freq:
                    #llogger.debug('Ignoring message not in my freq. %s != %s' % (freq,self.circuit.aircraft.status.freq,))
                    #llogger.debug('%s != %s' % (type(freq),type(self.circuit.aircraft.status.freq),))
                    continue
                
                try:
                    order = eval(pos.get_order())
                except:
                    llogger.exception('Evaluating order %s' % pos.get_order())
                    continue
                if order[Order.PARAM_RECEIVER]==self.circuit.aircraft.callsign:
                    self.circuit.process_order(order)
            except:
                pass


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
    comm=None
    request = None
        
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
        self.comm=self.airport().comms.filter(type=Comm.TWR).first()
            
        self.log("created")
        
    def log(self,*argv):
        fgserver.info("AI %s" % self.callsign(),*argv)

    def set_state(self,state,changed=False):
        if state <=0:
            return
        if self.state != state:
            self.log("State changed from %s to %s" % (PlaneInfo.CHOICES[self.state][1],PlaneInfo.CHOICES[state][1]))
            changed = True
            old_state=self.state
        self.state=state
        laor = getattr(self.circuit,'_last_order',None)
        if state == PlaneInfo.LINED_UP and laor.get(Order.PARAM_ORDER) == alias.CLEAR_TK:
            # Special case: we are lined up, waypoint says HOLD,  but we're already clear for take off
            llogger.debug("Lined up and cleartk. Setting state to DEPARTING")
            self.set_state(PlaneInfo.DEPARTING)
        if state in [PlaneInfo.STOPPED, PlaneInfo.HOLD, PlaneInfo.PUSHBACK]\
                or (state==PlaneInfo.SHORT and laor and laor.get(Order.PARAM_SHORT,False))\
                or (state==PlaneInfo.LINED_UP and laor and laor.get(Order.PARAM_LINEUP,False)):
            self.speed=0
            self.vertical_speed=0
            self.turn_rate=1
            self.target_vertical_speed=1 
        elif state == PlaneInfo.TAXIING or (state==PlaneInfo.SHORT and not laor.get(Order.PARAM_SHORT,False) ) or state == PlaneInfo.LINING_UP:
            self.turn_rate = 160
            self.speed = 20*units.KNOTS
            self.target_vertical_speed=1
        elif state == PlaneInfo.DEPARTING or state==PlaneInfo.LINED_UP:
            self.turn_rate = 3
            self.speed = 70*units.KNOTS
            self.target_vertical_speed=150*units.FPM
        elif state == PlaneInfo.CLIMBING:
            self.turn_rate = 5
            self.speed = 100*units.KNOTS
            self.target_vertical_speed=900*units.FPM
        elif state == PlaneInfo.CRUISING:
            self.turn_rate = 5
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
        #self.log("turn_rate",self.turn_rate,"speed",self.speed,"target_vs",self.target_vertical_speed)
        
        if state == PlaneInfo.DEPARTING or state==PlaneInfo.LINED_UP:
            self.course = float(self.airport().active_runway().bearing)
                
        if changed:
            self.check_request(old_state)
    
    def airport(self):
        return self.circuit.airport

    def aircraft(self):
        return self.circuit.aircraft
    
    def say_runway(self,runway=None):
        ''' returns the numbers of the runway designation. i.e. "one niner right" for 19R'''
        if not runway:
            runway = self.airport().active_runway()
        return say_number(runway.name)
    
    def get_state_label(self,state=None):
        state = state or self.state
        return PlaneInfo.CHOICES[state][1]
        
    def send_request(self,req,msg):
        self.message=msg
        req = "%s;freq=%s;mid=%s" % (req,self.comm.get_FGfreq(),randint(1000,9999))
        self.log("Sending request",req,msg)
        self.aircraft().status.request = req
        self.request = req

    def check_request(self,old_state=None):
        self.log("check_request",self.waypoint.type, self.state)
        from fgserver.ai.models import WayPoint
        if not self.airport():
            return
        callsign = short_callsign(self.callsign())
        laor = getattr(self.circuit,'_last_order',None)
        self.log("laor=%s" % laor)
        if self.state == PlaneInfo.CIRCUIT_CROSSWIND:
            req = "req=crosswind;apt=%s" % self.airport().icao
            msg="%s, %s, Crosswind for runway %s" % (self.comm.identifier, callsign,self.say_runway())
            self.send_request(req,msg)
        elif self.state == PlaneInfo.APPROACHING:
            req = "req=inbound;apt=%s" % self.airport().icao
            msg="%s, %s, for inbound approach" % (self.comm.identifier, callsign)
            self.send_request(req,msg)
        elif self.state == PlaneInfo.CIRCUIT_DOWNWIND:
            req = "req=downwind;apt=%s" % self.airport().icao
            msg="%s, %s, Downwind for runway %s" % (self.comm.identifier, callsign,self.say_runway())
            self.send_request(req,msg)
        elif self.state == PlaneInfo.CIRCUIT_BASE:
            req = "req=base;apt=%s" % self.airport().icao
            msg="%s, %s, Turning base for runway %s" % (self.comm.identifier, callsign,self.say_runway())
            self.send_request(req,msg)
        elif self.state == PlaneInfo.CIRCUIT_FINAL:
            req = "req=final;apt=%s" % self.airport().icao
            msg="%s, %s, Final for runway %s" % (self.comm.identifier, callsign,self.say_runway())
            self.send_request(req,msg)    
        elif self.state == PlaneInfo.HOLD and old_state == PlaneInfo.TOUCHDOWN:
            req = "req=clearrw;apt=%s" % self.airport().icao
            msg="%s, %s, landed on runway %s" % (self.comm.identifier, callsign,self.say_runway())
            self.send_request(req,msg)    
        elif self.state == PlaneInfo.PUSHBACK:
            req = "req=readytaxi;apt=%s" % self.airport().icao
            msg="%s, %s, ready to taxi" % (self.comm.identifier, callsign)
            self.send_request(req,msg)
        elif self.state == PlaneInfo.LINED_UP and laor.get(Order.PARAM_LINEUP,False):
            req = "req=readytko;apt=%s" % self.airport().icao
            msg="%s, %s, ready for takeoff" % (self.comm.identifier, callsign)
            self.send_request(req,msg)
        elif self.state == PlaneInfo.SHORT and (laor.get(Order.PARAM_SHORT,False) or laor.get(Order.PARAM_ORDER,None)==alias.TUNE_OK):
            req = "req=holdingshort;apt=%s" % self.airport().icao
            msg="%s, %s, holding short of runway %s" % (self.comm.identifier, callsign,self.say_runway())
            self.send_request(req,msg)
        elif self.state== PlaneInfo.STOPPED and self.waypoint.type == WayPoint.PARKING:
            ground = self.airport().comms.filter(type = Comm.GND).first()
            if ground:
                self.comm=ground
            req = "req=tunein"
            self.send_request(req,'',)
        elif self.state== PlaneInfo.CLIMBING:
            req = "req=leaving;apt=%s" % self.airport().icao
            self.send_request(req,"%s, %s, leaving airfield" % (self.comm.identifier, callsign))
        else:
            self.log("ignoring change of state:",self.state,laor.get(Order.PARAM_SHORT,False),laor.get(Order.PARAM_ORDER,None))

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
        if not self.on_ground() and coursediff >= 0.01:
            roll = (self.turn_rate*self.bank_sense)*2
            #self.log("tr",self.turn_rate,"roll",roll,"bank",self.bank_sense)
        q2 = Quaternion.fromYawPitchRoll(newcourse, 0, roll)
        
        self.position = newpos
        self.orientation =  Position.fromV3D(q1.multiply(q2).normalize().get_angle_axis())
        self.linear_velocity = vs
        self.course=newcourse
        
        
    def next_altitude(self,dt):
        if self.on_ground():
            return self.airport().altitude*units.FT
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
        diff = normdeg(self.course - self.target_course)
        hdiff = abs(diff)
        if self.speed == 0 or hdiff < 0.01:
            return self.target_course
        
        self.bank_sense=1.0
        if diff > 0.01:
            self.bank_sense = -1.0
        nc =normalize(self.course + self.bank_sense*min(hdiff, self.turn_rate*dt))
        return nc
    
    def heading_to(self,to):
        return get_heading_to_360(self.position, to)
        
    
    def on_ground(self):
        return self.state in [PlaneInfo.STOPPED,PlaneInfo.TAXIING,PlaneInfo.DEPARTING,PlaneInfo.LINED_UP,PlaneInfo.SHORT, PlaneInfo.TOUCHDOWN]

    
    def _fill_properties(self,pos):
        props = pos.properties
        props.set_prop(302,self.speed*50)
        props.set_prop(312,self.speed*50)
        if self.comm:
            props.set_prop(PROP_FREQ,str(self.comm.get_FGfreq()))
        if self.circuit._last_order:
            props.set_prop(PROP_OID,str(self.circuit._last_order.get(Order.PARAM_OID)))
        if self.on_ground() or self.state == PlaneInfo.LANDING:
            #props.set_prop(1004,1)
            props.set_prop(201,1)
            props.set_prop(211,1)
            props.set_prop(221,1)
        else:
            #props.set_prop(1004,0)
            props.set_prop(201,0)
            props.set_prop(211,0)
            props.set_prop(221,0)
        if self.message:
            props.set_prop(PROP_CHAT,self.message)
        
    def get_pos_message(self):
        raise DeprecationWarning("Llamado a get_message")
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
        try:
            status = a.status
        except:
            status = AircraftStatus(aircraft=a)
        status.position= Point(self.position.get_array_cart())
        status.orientation = Point(self.orientation.get_array())
        status.linear_vel = Point(self.linear_velocity.get_array_cart())
        status.angular_vel = Point([0,0,0])
        status.linear_accel = Point([0,0,0])
        status.angular_accel = Point([0,0,0])
        status.state=self.state
        if self.request:
            status.request = self.request
        if self.circuit._last_order:
            status.order = self.circuit._last_order.get(Order.PARAM_OID)
        status.freq = self.comm.frequency
        status.message = self.message
        status.on_ground = self.on_ground()
        return status
        #print "upd",a.lat,a.lon,a.altitude,a.heading
        
        

