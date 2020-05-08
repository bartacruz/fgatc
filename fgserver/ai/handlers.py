'''
Created on 29 abr. 2020

@author: julio
'''
from fgserver.ai.models import WayPoint
from fgserver.ai.common import PlaneInfo, PlaneRequest
from django.contrib.gis.geos.point import Point
from fgserver.models import Runway, StartupLocation, Comm, get_runway
from fgserver.ai.dijkstra import dj_waypoints
from fgserver import units, get_controller
from fgserver.helper import move, normdeg, Position, say_number, short_callsign
from random import randrange, randint
import logging
from fgserver.messages import alias
import re
import threading
import time

llogger = logging.getLogger(__name__)


class Copilot():
    def __init__(self,plane):
        self.plane = plane
        self.aircraft = plane.aircraft
        self.freq = None
        self.next_freq = None
        self.controller = None
        self.icao = None
        
    def process_order(self,order):
        llogger.debug("process_order: %s" % order)
        self.order = order
        clearances = self.plane.clearances
        if order.ord==alias.TUNE_OK:
            self.freq = order.freq
            self.next_freq=None
            self.icao = order.apt
            self.controller = order.atc
            self.check_request()
        elif order.ord==alias.TUNE_TO:
            self.freq = None
            self.next_freq = order.freq
            self.readback(order)
            self.check_request()
        elif order.ord==alias.STARTUP:
            self.readback(order)
            clearances.start = True
            self.plane.start()
        elif order.ord==alias.TAXI_TO:
            self.readback(order)
            clearances.taxi = True
            clearances.runway = order.rwy
            clearances.short = order.short
            clearances.lineup = order.lnup
            self.runway = get_runway(self.icao,order.rwy)
            self.plane.dynamics.wait(5)
            self.plane.taxi()
        elif order.ord==alias.CLEAR_CROSS:
            self.readback(order)
            clearances.cross = True
            self.plane.taxi()
            # Clearance expires when we move
            clearances.cross = False
        elif order.ord==alias.LINEUP:
            self.readback(order)
            clearances.lineup = True
            self.plane.depart()
        elif order.ord==alias.CLEAR_TK:
            self.readback(order)
            clearances.take_off = True
            self.plane.dynamics.wait(5)
            self.plane.depart()
        elif order.ord==alias.JOIN_CIRCUIT:
            self.readback(order)
            clearances.join = True
            clearances.runway = order.rwy
            clearances.report = order.cirw
            self.plane.approach()
        elif order.ord==alias.REPORT_CIRCUIT:
            self.readback(order)
            clearances.report = order.cirw
        elif order.ord==alias.CLEAR_LAND:
            self.readback(order)
            clearances.land = True
            self.plane.land()
        elif order.ord==alias.GO_AROUND:
            self.readback(order)
            clearances.land = False
            self.plane.land()
    
    def new_request(self,what):
        return PlaneRequest(req=what, freq=self.get_FGfreq(self.freq), mid = randint(1000,9999) )
    
    def get_comm_by_freq(self,airport,freq):
        return airport.comms.filter(frequency=freq).first()
    
    def get_comm_by_type(self,airport,comm_type):
        comm = airport.comms.filter(type=comm_type).first()
        if not comm:
            comm = airport.comms.filter(type=Comm.TWR).first()
        return comm
    
    def state_changed(self):
        self.check_clearances()
        self.check_request()
        if self.plane.is_rejoining():
            llogger.debug("Plane is rejoining, finding waypoint")
            wp = self.plane.flightplan.waypoints().filter(status=PlaneInfo.APPROACHING).last()
            self.plane.clearances.report=alias.CIRCUIT_CROSSWIND
            self.plane.flightplan.reroute(wp)
            llogger.debug("Waypoint found. Setting course")
            self.plane.dynamics.set_waypoint(self.plane.flightplan.waypoint(),self.plane.flightplan.next_waypoint())
            self.plane.approach()            
        
    @staticmethod
    def get_FGfreq(frequency):
        sf = str(frequency)
        return "%s.%s" % (sf[:3],sf[3:])
    
    def airport(self):
        return self.plane.flightplan.airport
    
    def check_clearances(self):
        clearances = self.plane.clearances
        if self.plane.is_departing():
            clearances.take_off = False
            clearances.short = False
            clearances.lineup = False
            llogger.debug("clearances: %s" % clearances)
        elif self.plane.is_climbing():
            clearances.runway = False
        elif self.plane.is_landing():
            clearances.join = False
        elif self.plane.is_rolling():
            clearances.land=False
            clearances.parking=True # TODO: request parking
            
    def check_request(self):
        print("check_request. self.freq=%s" % self.freq)
        clearances = self.plane.clearances
        req = None
        if not self.freq:
            req = self.new_request('tunein')
            if self.next_freq:
                comm =self.get_comm_by_freq(self.airport(),self.next_freq)
            elif self.plane.state in ['stopped','pushback','taxiing']:
                comm = self.get_comm_by_type(self.airport(),Comm.GND)
            req.freq=comm.get_FGfreq()
            
        elif self.plane.is_pushback() and not clearances.taxi:
            print("check_request: requesting taxi clearance")
            req = self.new_request('readytaxi')
        elif self.plane.is_short() and not clearances.take_off and not self.request.req == 'holdingshort':
            print("check_request: requesting holding short")
            req = self.new_request('holdingshort')
            req.rwy = clearances.runway
        elif self.plane.is_linedup() and not clearances.take_off and not self.request.req == 'readytko':
            print("check_request: requesting ready to take off")
            req = self.new_request('readytko')
            req.rwy = clearances.runway
        elif self.plane.is_approaching() and not (clearances.join or clearances.land) and not self.request.req == alias.INBOUND_APPROACH:
            comm = self.get_comm_by_type(self.airport(),Comm.APP)
            if self.freq and self.freq == comm.get_FGfreq():
                print("check_request: requesting inbound approach")
                req = self.new_request(alias.INBOUND_APPROACH)
                req.icao = self.icao
            elif not self.request.req == alias.TUNE_IN:
                print("check_request: re-tunning to approach controller %s != %s" % (self.freq, comm.frequency))
                self.freq=None
                self.next_freq=comm.frequency
                return self.check_request()
        elif self.plane.is_on_circuit() and clearances.report:
            print("check_request: reporting circuit")
            req = self.new_request(clearances.report)
            req.rwy = clearances.runway
        if req:
            self.request = req
        
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
        msg = templates.get(order.ord)
        if not msg:
            llogger.info("No readback for %s" % order.ord)
            return
        msg = re.sub(r'{cs}',short_callsign(self.aircraft.callsign),msg)
        msg = re.sub(r'{icao}',order.apt,msg)
        msg = re.sub(r'{comm}',self.controller,msg)
        msg = re.sub(r'{rwy}',say_number(order.rwy),msg)
        msg = re.sub(r'{alt}',str(order.alt or ''),msg)
        msg = re.sub(r'{cirt}',order.cirt or '',msg)
        msg = re.sub(r'{cirw}',order.cirw or '',msg)
        msg = re.sub(r'{num}',str(order.number or ''),msg)
        msg = re.sub(r'{freq}',str(order.freq or ''),msg)
        msg = re.sub(r'{conn}',str(order.atc or ''),msg)
        msg = re.sub(r'{park}',str(order.park or ''),msg)
        if order.number:
            msg = re.sub(r'{onum}',', number %s' % order.number,msg)
        if order.lnup:
            msg = re.sub(r'{lineup}',' and line up',msg)
        if order.hld:
            msg = re.sub(r'{hld}',' and hold',msg)
        if order.short:
            msg = re.sub(r'{short}',' short',msg)
        if order.park:
            try:
                startup = StartupLocation.objects.get(pk=order.park)
                msg = re.sub(r'{park}',startup.name.replace("_"," "),msg)
            except StartupLocation.DoesNotExist:
                pass
        if order.qnh:
            msg = re.sub(r'{qnh}','. QNH %s' % say_number(order.qnh),msg)

        # Clean up tags not replaced
        msg = re.sub(r'{\w+}','',msg)
        msg += ", %s" % short_callsign(self.aircraft.callsign)
        req = "req=roger;laor=%s" % order.ord
        llogger.debug("readback: %s | %s" % (req,msg,))        
        threading.Thread(target=self.send_delayed_request,args=(req,msg,10,)).start()
    
    def send_delayed_request(self,req,msg,delay=5):
        #time.sleep(delay)
        #self.request = req        
        #dummy
        llogger.debug("readback: %s | %s" % (req,msg,))
    
    
    
    
class FlightPlanManager():
    
    def __init__(self,plane,flightplan):
        self.plane = plane
        self.flightplan = flightplan
        self.airport = flightplan.airport
        self._waypoint = 0
        # TODO: free handler from FlightPlan.
        self.flightplan.init()
        self.handler = self.flightplan.get_handler()
        self.landing_generated = False
        
    def reached(self,waypoint):
        self._waypoint += 1

    def waypoints(self):
        return self.flightplan.waypoints
    
    def reroute(self,waypoint):
        wp_index = list(self.waypoints().all().order_by('id')).index(waypoint)
        self._waypoint = wp_index
        llogger.info("Rerouting to %s: %s" % (wp_index,self.waypoint()))
    
    def generate_waypoints(self,*args,**kwargs):
        print("generating wpts", args, kwargs)
        clearances = self.plane.clearances
        position = self.plane.dynamics.position
        if self.plane.is_pushback():
            print("generating waypoints to runway")
            runway = self.airport.runways.get(name=clearances.runway)
            self.handler.generate_taxi_waypoints(position,runway,clearances.short)
            self.plane.reached(self.waypoint())    
        elif self.plane.is_linedup() or clearances.take_off:
            print("generating circuit waypoints")
            runway = self.airport.runways.get(name=clearances.runway)
            self.handler.generate_circuit_waypoints(runway)
        elif self.plane.is_approaching() and clearances.runway and not self.landing_generated:
            print("generating landing waypoints")
            self.landing_generated=True
            runway = self.airport.runways.get(name=clearances.runway)
            self.handler.generate_landing_waypoints(runway)
        elif self.plane.is_rolling():
            print("generating parking waypoints")
            parking = self.waypoints().all().order_by("id").first()
            self.handler.generate_taxi_waypoints(position,parking.get_position())
            
    def waypoint(self):
        if self.flightplan.waypoints.all().count() <= self._waypoint:
            self._waypoint=0
        return self.flightplan.waypoints.all().order_by('id')[self._waypoint]
        
    
    def next_waypoint(self):
        if self.flightplan.waypoints.all().count() > self._waypoint + 1:
            return self.flightplan.waypoints.all().order_by('id')[self._waypoint+1]
        return None

        
class CircuitHandler():
    
    def __init__(self,circuit):
        self.circuit = circuit
        self.airport = circuit.airport
        self.aircraft = circuit.aircraft
        self.generate_start_waypoints()
        self.status=None
    
    def waypoint_reached(self,wp):
        self.status=wp.status
        
    def get_startup_location(self):     
        s1 = self.airport.startups.filter(aircraft = self.aircraft).first()
        if not s1:
            s1 = self.airport.startups.filter(active=True,aircraft=None).order_by("?").first()
        if s1:
            s1.aircraft=self.aircraft
            s1.save()
        return s1
    
    def generate_start_waypoints(self):
        start_l = self.get_startup_location()
        position= start_l.get_position()
        self.create_waypoint(position, start_l.name, WayPoint.PARKING, PlaneInfo.STOPPED)
        self.create_waypoint(position, start_l.name, WayPoint.PUSHBACK, PlaneInfo.TAXIING)
    
    def generate_taxi_waypoints(self, pos1, pos2, short=False):
        # TODO: Change when geodjango is completly implemented
        apalt=float(self.airport.altitude*units.FT+2)
        p1 = Point((pos1.y,pos1.x))
        if isinstance(pos2, Runway):
            rwystart = move(pos2.position(), normdeg(pos2.bearing-180), pos2.length/2,apalt)
            p2 = Point((rwystart.y,rwystart.x))
        else:
            p2 = Point((pos2.y,pos2.x))
        taxi = dj_waypoints(self.airport.icao,p1, p2)
        if len(taxi) > 2:
            for way in taxi[:-2]:
                p=Position(way.point.y,way.point.x, apalt)
                self.create_waypoint(p, "Taxi %s" % way.id, WayPoint.TAXI, PlaneInfo.TAXIING)
            position=Position(taxi[-2].point.y, taxi[-2].point.x, apalt)
            if short:
                self.create_waypoint(position, "Hold Short", WayPoint.HOLD, PlaneInfo.SHORT)
            else:
                self.create_waypoint(position, "Hold Short", WayPoint.TAXI, PlaneInfo.TAXIING)
                
            position=Position(taxi[-1].point.y, taxi[-1].point.x, apalt)
            if isinstance(pos2, Runway):
#                 self.create_waypoint(position, "Ramping for %s" % pos2.name, WayPoint.TAXI, PlaneInfo.TAXIING)
#                 position = move(rwystart,pos2.bearing,10,apalt)
                self.create_waypoint(position, "Lineup %s"% pos2.name, WayPoint.HOLD, PlaneInfo.LINED_UP)
                position = move(position,pos2.bearing,30,position.z)
                self.create_waypoint(position, "Departure hack  %s"% pos2.name, WayPoint.RWY, PlaneInfo.DEPARTING)
            else:
                self.create_waypoint(position, "Taxi step ", WayPoint.TAXI, PlaneInfo.TAXIING)

    def generate_circuit_waypoints(self, runway):
        llogger.debug("Generating departure and circuit waypoints")
        radius = self.circuit.radius
        apalt=float(runway.airport.altitude*units.FT+2)
        altitude = self.circuit.altitude
        rwystart = move(runway.position(), normdeg(runway.bearing-180), runway.length/2,apalt)
        
        straight=runway.bearing
        position = move(rwystart,straight,80,apalt)
        self.create_waypoint(position, "Roll start %s" % runway.name, WayPoint.RWY, PlaneInfo.DEPARTING) # Set to start roll
        position = move(rwystart,straight,300,apalt)
        self.create_waypoint(position, "Rotate1 %s" % runway.name, WayPoint.RWY, PlaneInfo.DEPARTING)
        position = move(position,straight,350,apalt+3)
        self.create_waypoint(position, "Rotate2 %s" % runway.name, WayPoint.RWY, PlaneInfo.DEPARTING)
        # get to 20 meters altitude after exit the runway, then start climbing
#         position = move(rwystart,straight,int(runway.length*0.9),apalt+20)
#         self.create_waypoint(position, "Departure %s" % runway.name, WayPoint.RWY, PlaneInfo.DEPARTING)
        # get to 20 meters altitude after exit the runway, then start climbing
        position = move(position,straight,750,apalt+10)
        self.create_waypoint(position, "Climbing %s" % runway.name, WayPoint.RWY, PlaneInfo.CLIMBING)
        #self.create_waypoint(position, "Departure %s"%runway.name, WayPoint.RWY, PlaneInfo.CLIMBING)
        position = move(position,straight,radius,apalt+altitude)
        self.create_waypoint(position, "Cruising", WayPoint.POINT, PlaneInfo.CRUISING)
        position = move(position,normdeg(straight+40),radius*0.7,apalt+altitude)
        self.create_waypoint(position, "Cruising 2", WayPoint.POINT, PlaneInfo.CRUISING)
        position = move(position,normdeg(straight+80),radius*0.6,apalt+altitude)
        self.create_waypoint(position, "Cruising 3", WayPoint.POINT, PlaneInfo.CRUISING)
        position = move(position,normdeg(straight+120),radius*0.6,apalt+altitude)
        self.create_waypoint(position, "Cruising 4", WayPoint.POINT, PlaneInfo.CRUISING)
        position = move(position,normdeg(straight+150),radius*0.6,apalt+altitude)
        self.create_waypoint(position, "Cruising 5", WayPoint.POINT, PlaneInfo.CRUISING)
        position = move(position,normdeg(straight+190),radius*0.6,apalt+altitude)
        self.create_waypoint(position, "Cruising 5", WayPoint.POINT, PlaneInfo.APPROACHING)
        position = move(position,normdeg(straight+230),radius*0.6,apalt+altitude)
        self.create_waypoint(position, "Cruising 6", WayPoint.POINT, PlaneInfo.APPROACHING)

    def generate_landing_waypoints(self,runway):
        radius = self.circuit.radius
        altitude = self.circuit.altitude
        apalt=float(runway.airport.altitude*units.FT+2)
        straight=runway.bearing
        reverse= normdeg(straight-180)
        left = normdeg(straight-90)
        right = normdeg(straight+90)
        rwystart = move(runway.position(), reverse, runway.length/2,apalt)
        rwyend = move(runway.position(), straight, runway.length/2,apalt)
        position = move(rwyend,right,radius/5,apalt+altitude+1000*units.FT)
        self.create_waypoint(position, "Crosswind %s"%runway.name, WayPoint.CIRCUIT, PlaneInfo.CIRCUIT_CROSSWIND)
        position = move(rwyend,left,radius,apalt+altitude)
        self.create_waypoint(position, "Downwind %s"%runway.name, WayPoint.CIRCUIT, PlaneInfo.CIRCUIT_DOWNWIND)
        position = move(position,reverse,radius*2+runway.length,apalt+altitude)
        self.create_waypoint(position, "Base %s"%runway.name, WayPoint.CIRCUIT, PlaneInfo.CIRCUIT_BASE)
        position = move(position,right,radius,apalt+500*units.FT)
        self.create_waypoint(position, "Final %s"%runway.name, WayPoint.CIRCUIT, PlaneInfo.CIRCUIT_FINAL)
        position = move(rwystart,reverse,30,apalt+15)
        self.create_waypoint(position, "Flare 1 %s"%runway.name, WayPoint.CIRCUIT, PlaneInfo.LANDING)
        position = move(position,straight,100,apalt+10)
        self.create_waypoint(position, "Flare 2 %s"%runway.name, WayPoint.CIRCUIT, PlaneInfo.LANDING)
        position = move(position,straight,100,apalt+5)
        self.create_waypoint(position, "Flare 3 %s"%runway.name, WayPoint.CIRCUIT, PlaneInfo.LANDING)
        position = move(position,straight,100,apalt)
        self.create_waypoint(position, "Touchdown %s"%runway.name, WayPoint.RWY, PlaneInfo.TOUCHDOWN)
        position = move(position,straight,180,apalt)
        self.create_waypoint(position, "Landing Roll %s" % runway.name, WayPoint.RWY, PlaneInfo.HOLD)
        # TODO: Create parking
        
    def create_waypoint(self,position, name, atype, status):
        self.circuit.create_waypoint(position,name,atype,status)

