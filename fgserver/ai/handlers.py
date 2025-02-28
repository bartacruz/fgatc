'''
Created on 29 abr. 2020

@author: julio
'''
from fgserver.ai.models import WayPoint
from fgserver.ai.common import PlaneInfo, PlaneRequest
from django.contrib.gis.geos.point import Point
from fgserver.models import Runway, Comm, get_runway
from fgserver.ai.dijkstra import dj_waypoints, get_next_on_runway,\
    get_runway_exit, taxi_path, taxi_path2
from fgserver import units
from fgserver.helper import move, normdeg, Position, normalize, say_char,\
    get_heading_to, get_distance
from random import randint
from fgserver.messages import alias

import logging
from fgserver.ai.actions import TuneInAction, ReadyTaxiAction, ReadBackAction,\
    RequestInboundAction, HoldingShortAction, ReadyTakeoffAction, LeavingAction,\
    ReportCircuitAction, RequestParkAction, ClearedRunwayAction,\
    CrossRunwayAction

llogger = logging.getLogger(__name__)



class Copilot():
    
    MAX_REQUEST_TIME = 2
    
    def __init__(self,plane):
        self.plane = plane
        self.aircraft = plane.aircraft
        self.freq = None
        self.next_freq = None
        self.controller = None
        self.icao = None
        self.order = None
        
        self.request = None
        self.requests = []
        
        self.message = None
        self.messages = []
        
        self.action = None
        self.actions = []
        
        self.circuits_helper = {
                PlaneInfo.CIRCUIT_CROSSWIND: alias.CIRCUIT_CROSSWIND,
                PlaneInfo.CIRCUIT_DOWNWIND: alias.CIRCUIT_DOWNWIND,
                PlaneInfo.CIRCUIT_BASE: alias.CIRCUIT_BASE,
                PlaneInfo.CIRCUIT_FINAL: alias.CIRCUIT_FINAL,
                PlaneInfo.CIRCUIT_STRAIGHT: alias.CIRCUIT_STRAIGHT,
        }
    
    
    def get_atis(self):
        cycle = self.airport().metar.last().cycle
        return say_char(chr(ord('a')+cycle))
         
    def update_aircraft(self,status):
        if len(self.actions) and (not self.action or self.action.is_done()):
            self.action = self.actions.pop(0)
            llogger.debug("{%s-CP}(%s) Loaded action: %s" % (self.aircraft, self.plane.state, self.action))
            
        if self.action and self.action.is_ready() and not self.action.is_done():
            llogger.debug("{%s-CP}(%s) Executing action: %s" % (self.aircraft, self.plane.state, self.action))
            self.action.execute()
        
        if len(self.requests):
            self.request =  self.requests.pop(0)
            llogger.debug("{%s-CP}(%s) Sending queued request: %s" % (self.aircraft, self.plane.state, self.request))
        if self.request:
            status.request = self.request.get_request()
        
        if len(self.messages):
            self.message =  self.messages.pop(0)
            llogger.debug("{%s-CP}(%s) Sending queued message: %s" % (self.aircraft, self.plane.state, self.message))
        if self.message:
            status.message = self.message
        
        if self.order:
            status.order = self.order.oid
        if self.freq:
            status.freq = int(str(self.freq).replace(".",""))
        
        return status
    
    def already_requested(self,req):
        return (self.request and self.request.req == req) or len(list(filter(lambda x: x.req == req, self.requests))) > 0
    
    def process_order(self,order):
        if order and self.order and order.oid == self.order.oid:
            return
        llogger.debug("{%s-CP}(%s) process_order: %s" % (self.aircraft, self.plane.state, order))
        #llogger.debug("{%s-CP}(%s) clearances in:%s" % (self.aircraft, self.plane.state, self.plane.clearances))
        self.order = order
        clearances = self.plane.clearances
        if order.ord==alias.TUNE_OK:
            self.icao = order.apt
            self.controller = order.atc
        elif order.ord==alias.TUNE_TO:
            freq = order.freq.replace('.','')
            self.actions.append(ReadBackAction(self, order))
            self.actions.append(TuneInAction(self, freq))
        elif order.ord==alias.STARTUP:
            self.actions.append(ReadBackAction(self, order))
            clearances.start = True
            llogger.debug("{%s-CP}(%s) starting plane" % (self.aircraft, self.plane.state))
            self.plane.start()
        elif order.ord==alias.TAXI_TO:
            self.actions.append(ReadBackAction(self, order))
            clearances.taxi = True
            clearances.runway = order.rwy
            clearances.short = order.short is not None
            clearances.lineup = order.lnup is not None
            self.runway = get_runway(self.icao,order.rwy)
            self.plane.dynamics.wait(30) # 30 seconds to start moving
            if order.freq:
                self.actions.append(TuneInAction(self,order.freq.replace(".",'')))
            if self.plane.is_taxiing():
                llogger.debug("{%s-CP}(%s) already taxiing, continue" % (self.aircraft, self.plane.state))
                pass
            elif self.plane.is_holding():
                llogger.debug("{%s-CP}(%s) resume taxiing" % (self.aircraft, self.plane.state))
                self.plane.taxi()
            else:
                llogger.debug("{%s-CP}(%s) starting taxi run" % (self.aircraft, self.plane.state))
                self.plane.pushback()
        elif order.ord == alias.WAIT:
            self.actions.append(ReadBackAction(self, order))
            clearances.cross = False
            clearances.take_off = False
        elif order.ord==alias.CLEAR_CROSS_RUNWAY:
            self.actions.append(ReadBackAction(self, order))
            clearances.cross = True
            llogger.debug("{%s-CP}(%s) crossing runway" % (self.aircraft, self.plane.state))
            self.plane.cross()
            
        elif order.ord==alias.LINEUP:
            self.actions.append(ReadBackAction(self, order))
            clearances.lineup = True
            clearances.take_off = False
            clearances.short = False
            llogger.debug("{%s-CP}(%s) lining up" % (self.aircraft, self.plane.state))
            self.plane.dynamics.wait(30) # wait 30 seconds to start moving
            self.plane.depart()
        elif order.ord==alias.CLEAR_TK:
            self.actions.append(ReadBackAction(self, order))
            clearances.take_off = True
            clearances.short = False
            self.plane.dynamics.wait(30)
            llogger.debug("{%s-CP}(%s) taking off" % (self.aircraft, self.plane.state))
            self.plane.depart()
        elif order.ord==alias.JOIN_CIRCUIT:
            self.actions.append(ReadBackAction(self, order))
            clearances.join = True
            clearances.runway = order.rwy
            clearances.report = order.cirw
            llogger.debug("{%s-CP}(%s) joining circuit" % (self.aircraft, self.plane.state))
            if order.freq:
                self.actions.append(TuneInAction(self,order.freq.replace(".",'')))
            self.plane.approach()
        elif order.ord==alias.CIRCUIT_STRAIGHT:
            self.actions.append(ReadBackAction(self, order))
            clearances.straight = True
            clearances.runway = order.rwy
            clearances.report = order.cirw
            llogger.debug("{%s-CP}(%s) joining straight" % (self.aircraft, self.plane.state))
            self.plane.approach()
        
        elif order.ord==alias.REPORT_CIRCUIT:
            self.actions.append(ReadBackAction(self, order))
            clearances.report = order.cirw
        elif order.ord==alias.CLEAR_LAND:
            self.actions.append(ReadBackAction(self, order))
            clearances.land = True
            llogger.debug("{%s-CP}(%s) landing" % (self.aircraft, self.plane.state))
            self.plane.land()
        elif order.ord==alias.GO_AROUND:
            self.actions.append(ReadBackAction(self, order))
            clearances.land = False
            llogger.debug("{%s-CP}(%s) going around" % (self.aircraft, self.plane.state))
            if order.freq:
                self.actions.append(TuneInAction(self,order.freq.replace(".",'')))
            self.plane.land()
        elif order.ord==alias.TAXI_PARK:
            llogger.debug("{%s-CP}(%s) taxi to parking %s (%s)" % (self.aircraft, self.plane.state, order.parkn,order.park))
            self.actions.append(ReadBackAction(self, order))
            clearances.parking = order.park
            clearances.taxi = True
            self.plane.park()
            self.plane.dynamics.wait(30)
            
            print("{%s-CP}(%s) park called %s (%s)" % (self.aircraft, self.plane.state, self.plane.state,clearances.parking))
        #llogger.debug("{%s-CP}(%s) clearances out:%s" % (self.aircraft, self.plane.state, self.plane.clearances))
        
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
        
        if self.plane.is_stopped():
            llogger.debug("{%s-CP} Stopped! resetting flightplan" % self.aircraft)
            self.plane.flightplan.reset()
            self.actions.clear()
            self.action = None
            self.messages.clear()
            self.message=None
            self.requests.clear()
            self.request=None
            self.order = None
            self.freq = None
            self.next_freq = None
            self.controller = None
            
        if self.plane.is_rejoining():
            llogger.debug("{%s-CP} Plane is rejoining, finding waypoint" % self.aircraft)
            wp = self.plane.flightplan.waypoints().filter(status=PlaneInfo.APPROACHING).last()
            self.plane.clearances.report=alias.CIRCUIT_CROSSWIND
            self.plane.flightplan.reroute(wp)
            llogger.debug("{%s-CP} Waypoint found. Setting course to %s" % (self.aircraft,wp))
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
            clearances.start = False
            clearances.taxi = False
            clearances.parking = False
            clearances.take_off = False
            clearances.short = False
            clearances.lineup = False
            llogger.debug("clearances: %s" % clearances)
        elif self.plane.is_climbing():
            clearances.runway = False
        elif self.plane.is_landing():
            clearances.join = False
            clearances.straight = False
        elif self.plane.is_rolling():
            clearances.land=False
            #clearances.parking=True # TODO: request parking
        elif self.plane.is_stopped():
            print("CLEARING CLEARANCES")
            for i in clearances.__dict__:
                setattr(clearances, i, False)
            print("CLEARED", str(clearances))
#             clearances.parking=False
#             clearances.runway=False
            
    def check_request(self):
        llogger.debug("{%s-CP} check_request. self.freq=%s, clearances=%s" %  (self.aircraft,self.freq, self.plane.clearances,))
        
        clearances = self.plane.clearances

        if self.plane.is_starting() and not clearances.taxi:
            print("{%s-CP} check_request: queing ReadyTaxiAction" % self.aircraft)
            comm = self.get_comm_by_type(self.airport(),Comm.GND)
            self.actions.append(TuneInAction(self,comm.frequency)) # Make sure we are tunned right
            self.actions.append( ReadyTaxiAction(self) )
        elif self.plane.is_holding() and not clearances.lineup and not clearances.cross:
            print("{%s-CP} check_request: queing RequestCrossAction" % self.aircraft)
            # TODO: detect wich runway we got in front
            self.actions.append( CrossRunwayAction(self,clearances.runway) )
        elif self.plane.is_taxiing() and clearances.cross:
            print("{%s-CP} check_request: queing ClearedRunway" % self.aircraft)
            # TODO: detect wich runway we got in front
            clearances.cross = False
            self.actions.append( ClearedRunwayAction(self,clearances.runway) )
        elif self.plane.is_short() and clearances.taxi and not clearances.take_off and not self.already_requested(alias.HOLDING_SHORT):
            print("{%s-CP} check_request: queing HoldingShortAction" % self.aircraft)
            self.actions.append( HoldingShortAction(self,clearances.runway) )
        elif self.plane.is_linedup() and not clearances.take_off and not self.already_requested(alias.READY_TAKEOFF):
            print("{%s-CP} check_request: queing ReadyTakeoffAction" % self.aircraft)
            self.actions.append( ReadyTakeoffAction(self,clearances.runway) )
        elif self.plane.is_climbing() and not self.request.req == alias.LEAVING:
            self.actions.append( LeavingAction(self,clearances.runway) )
        elif self.plane.is_approaching() and not (clearances.join or clearances.land) and not self.already_requested(alias.INBOUND_APPROACH):
            print("{%s-CP} check_request: queing inbound approach action" % self.aircraft)
            comm = self.get_comm_by_type(self.airport(),Comm.APP)
            self.actions.append(TuneInAction(self,comm.frequency)) # Make sure we are tunned right
            self.actions.append(RequestInboundAction(self)) 
        elif self.plane.is_on_circuit() and clearances.report:
            circ = self.circuits_helper[self.plane.flightplan.waypoint().status]
            if clearances.report and clearances.report == circ:
                print("{%s-CP} check_request: queing report circuit action for %s" % (self.aircraft, circ))
                comm = self.get_comm_by_type(self.airport(),Comm.TWR)
                self.actions.append(TuneInAction(self,comm.frequency)) # Make sure we are tunned right
                self.actions.append(ReportCircuitAction(self, circ, clearances.runway)) 
                clearances.report = None
        elif self.plane.is_short() and not clearances.taxi:
            print("{%s-CP} check_request: short after rolling" % self.aircraft)
            comm = self.get_comm_by_type(self.airport(),Comm.TWR)
            self.actions.append(TuneInAction(self,comm.frequency)) # Make sure we are tunned right
            self.actions.append(ClearedRunwayAction(self,clearances.runway))
        
    
class FlightPlanManager():
    
    def __init__(self,plane,flightplan):
        self.plane = plane
        self.flightplan = flightplan
        self.airport = flightplan.airport
        self.reset()
        
    def reset(self):
        self._waypoint = 0
        # TODO: free handler from FlightPlan.
        self.flightplan.init()
        self.handler = self.flightplan.get_handler()
        self.landing_generated = False
        self.depart_generated = False
        self.rolling_generated = False
        self.parking_generated = False
#         self.reached(self.waypoint())
        llogger.debug("{%s-FP} waypoint: %s %s" % (self.plane.aircraft,self._waypoint,self.waypoint() ) )
        
    def reached(self,waypoint):
        self._waypoint += 1
        llogger.info("{%s-FP} Next wp: %s" % (self.plane.aircraft,self.waypoint() ) )
        
    def waypoints(self):
        return self.flightplan.waypoints
    
    def reroute(self,waypoint):
        wp_index = list(self.waypoints().all().order_by('id')).index(waypoint)
        self._waypoint = wp_index
        llogger.info("{%s-FP} Rerouting to %s: %s" % (self.plane.aircraft, wp_index,self.waypoint()))
    
    def generate_waypoints(self):
        llogger.debug("{%s-FP} generating wpts" % self.plane.aircraft)
        clearances = self.plane.clearances
        position = self.plane.dynamics.position
        if self.plane.is_starting():
            print("{%s-FP} generating waypoints to runway %s. wp=%s" % (self.plane.aircraft, clearances.runway, self._waypoint))
            runway = self.airport.runways.get(name=clearances.runway)
            self.handler.generate_taxi_waypoints(position,runway)
            self.reached(self.waypoint())
            self.plane.dynamics.set_waypoint(self.waypoint(),self.next_waypoint())    
            print(self._waypoint,self.waypoints().all().order_by("id"))
        elif self.plane.is_linedup() and not self.depart_generated:
            print("{%s-FP} generating circuit waypoints" % self.plane.aircraft)
            self.depart_generated=True
            runway = self.airport.runways.get(name=clearances.runway)
            self.handler.generate_circuit_waypoints(runway)
        elif self.plane.is_cruising() and self._waypoint > 3:
            # RESET FLIGHTPLAN??
            pass
        elif self.plane.is_approaching() and clearances.join and not self.landing_generated:
            print("{%s-FP} generating circuit landing waypoints" % self.plane.aircraft)
            self.landing_generated=True
            runway = self.airport.runways.get(name=clearances.runway)
            self.handler.generate_landing_waypoints(runway)
        elif self.plane.is_approaching() and clearances.straight and not self.landing_generated:
            print("{%s-FP} generating straight landing waypoints" % self.plane.aircraft)
            # TODO: Por ahora generamos los normales.
            clearances.join=True
            self.landing_generated=True
            runway = self.airport.runways.get(name=clearances.runway)
            self.handler.generate_landing_waypoints(runway)
        elif self.plane.is_rolling() and not self.rolling_generated:
            print("{%s-FP} generating roling waypoints" % self.plane.aircraft)
            runway = self.airport.runways.get(name=clearances.runway)
            self.handler.generate_rolling_waypoints(position,runway)
            self.rolling_generated = True
        elif clearances.parking and not self.parking_generated:
            print("{%s-FP} generating parking waypoints" % self.plane.aircraft)
            parking = self.airport.startups.get(pk=clearances.parking)
            nwp = self.waypoints().count() 
            self.handler.generate_parking_waypoints(position,parking.get_position())
            self.parking_generated = True
            self._waypoint = nwp
            self.plane.dynamics.set_waypoint(self.waypoint(),self.next_waypoint())
           
    def waypoint(self):
        if self.flightplan.waypoints.all().count() <= self._waypoint:
            self._waypoint=self.flightplan.waypoints.all().count()-1
            print("{%s-FP} reset waypoint to %s" % (self.plane.aircraft, self._waypoint))
            
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
        if start_l:
            position= start_l.get_position()
            self.create_waypoint(position, start_l.name, WayPoint.PARKING, PlaneInfo.STOPPED)
            self.create_waypoint(position, start_l.name, WayPoint.PUSHBACK, PlaneInfo.PUSHBACK)
        else:
            position = self.airport.get_position()
            bearing = get_heading_to(position,self.airport.active_runway().get_position())
            dist = get_distance(position, self.airport.active_runway().get_position())
            position = move(position,bearing,dist/5,position.z)
            self.create_waypoint(position, "1", WayPoint.PARKING, PlaneInfo.STOPPED)
            self.create_waypoint(position, "1", WayPoint.PUSHBACK, PlaneInfo.PUSHBACK)

    def generate_rolling_waypoints(self,position,runway):
        path = get_runway_exit(runway, position, runway.bearing)
        
        for node in path:
            position=Position(node.point.y,node.point.x, self.apalt)
            wp = self.create_waypoint(position, "On runway %s" % runway.name, WayPoint.RWY, PlaneInfo.ROLLING)
        # last wp is outside the runway. must hold.
        wp.status = PlaneInfo.SHORT
        wp.type = WayPoint.HOLD
        wp.save()
    
    @property
    def apalt(self):
        return float(self.airport.altitude*units.FT)+1
    
    def generate_parking_waypoints(self, position, park):
        path = taxi_path(self.airport,position, park)
        for node in path:
            position=Position(node.point.y,node.point.x, self.apalt)
            self.create_waypoint(position, "Taxi %s" % node.id, WayPoint.TAXI, PlaneInfo.TAXIING)
        # Last wp is the parking itself. Stop.
        self.create_waypoint(park, "Parking", WayPoint.PARKING, PlaneInfo.STOPPED)
                
    def generate_taxi_waypoints(self, pos1, pos2, heading = None):
        # TODO: Change when geodjango is completly implemented
        p1 = pos1.to_point()
        if heading:
            # TODO: Calculate shortest p1 on similar heading
            pass
        if isinstance(pos2, Runway):
            rwystart = move(pos2.position(), normalize(pos2.bearing-180), pos2.length/2,pos2.position().z)
            lineup = move(rwystart, pos2.bearing, 50,self.apalt)
            p2 = rwystart.to_point()
            p2r=True
        else:
            p2 = pos2.to_point()
            p2r = False
        taxi = taxi_path(self.airport,p1, p2, end_on_rwy=p2r)
        
        last_short = None
        last_taxi = None
        if len(taxi):
            for way in taxi:
                taxinode = self.airport.taxinodes.filter(name=way.id).first()
                p = Position.from_point(way.point, self.apalt)
                on_runway = self.airport.on_runway(way.point)
                if taxinode:
                    if taxinode.short:
                        wp = self.create_waypoint(p, "Short %s" % way.id, WayPoint.HOLD, PlaneInfo.SHORT)
                        if last_short:
                            last_short.status=PlaneInfo.CROSS
                            last_short.save()
                        last_short=wp
                    elif on_runway:
                        wp = self.create_waypoint(p, "rwy %s" % way.id, WayPoint.RWY, PlaneInfo.TAXIING)
                    else:
                        wp = self.create_waypoint(p, "Taxi %s" % way.id, WayPoint.TAXI, PlaneInfo.TAXIING)
                        last_taxi=wp
                elif on_runway:
                    wp = self.create_waypoint(p, "Rwy %s" % way.id, WayPoint.RWY, PlaneInfo.TAXIING)
                else:
                    wp = self.create_waypoint(p, "Taxi %s" % way.id, WayPoint.TAXI, PlaneInfo.TAXIING)
                    last_taxi = wp
                
        if isinstance(pos2, Runway):
            if not last_short and last_taxi:
                # Create artificial short location with last not-on-runway node
                last_taxi.name = "Hold Short"
                last_taxi.status = PlaneInfo.SHORT
                last_taxi.type = WayPoint.HOLD
                last_taxi.save()
            self.create_waypoint(lineup, "Lineup  %s"% pos2.name, WayPoint.RWY, PlaneInfo.LINED_UP)
            position = move(lineup,pos2.bearing,50,self.apalt)
            self.create_waypoint(position, "Departure hack  %s"% pos2.name, WayPoint.RWY, PlaneInfo.DEPARTING)

    def generate_circuit_waypoints(self, runway):
        radius = self.circuit.radius
        altitude = self.circuit.altitude
        rwystart = move(runway.position(), normdeg(runway.bearing-180), runway.length/2,self.apalt)
        linedup = self.circuit.waypoints.filter(status = PlaneInfo.LINED_UP).last()
        straight=runway.bearing
        if linedup:
            print("{%s-CH} using startup waypoint %s" % (self.aircraft, linedup,) )
            position = move(linedup.get_position(),straight,50,linedup.get_position().z)
        else:
            position = move(rwystart,straight,100,self.apalt)
        self.create_waypoint(position, "Roll start %s" % runway.name, WayPoint.RWY, PlaneInfo.DEPARTING) # Set to start roll
        position = move(position,straight,300,self.apalt)
        self.create_waypoint(position, "Rotate1 %s" % runway.name, WayPoint.RWY, PlaneInfo.DEPARTING)
        position = move(position,straight,350,self.apalt+10)
        self.create_waypoint(position, "Rotate2 %s" % runway.name, WayPoint.RWY, PlaneInfo.DEPARTING)
        position = move(position,straight,500,self.apalt+30)
        self.create_waypoint(position, "Climbing %s" % runway.name, WayPoint.RWY, PlaneInfo.CLIMBING)
        #self.create_waypoint(position, "Departure %s"%runway.name, WayPoint.RWY, PlaneInfo.CLIMBING)
        position = move(position,straight,radius,self.apalt+altitude)
        self.create_waypoint(position, "Cruising", WayPoint.POINT, PlaneInfo.CRUISING)
        position = move(position,normdeg(straight+40),radius*0.7,self.apalt+altitude)
        self.create_waypoint(position, "Cruising 2", WayPoint.POINT, PlaneInfo.CRUISING)
        position = move(position,normdeg(straight+80),radius*0.6,self.apalt+altitude)
        self.create_waypoint(position, "Cruising 3", WayPoint.POINT, PlaneInfo.CRUISING)
        position = move(position,normdeg(straight+120),radius*0.6,self.apalt+altitude)
        self.create_waypoint(position, "Cruising 4", WayPoint.POINT, PlaneInfo.CRUISING)
        position = move(position,normdeg(straight+150),radius*0.6,self.apalt+altitude)
        self.create_waypoint(position, "Cruising 5", WayPoint.POINT, PlaneInfo.CRUISING)
        position = move(position,normdeg(straight+190),radius*0.6,self.apalt+altitude)
        self.create_waypoint(position, "Cruising 5", WayPoint.POINT, PlaneInfo.APPROACHING)
        position = move(position,normdeg(straight+230),radius*0.6,self.apalt+altitude)
        self.create_waypoint(position, "Cruising 6", WayPoint.POINT, PlaneInfo.APPROACHING)

    def generate_landing_waypoints(self,runway):
        radius = self.circuit.radius
        altitude = self.circuit.altitude
        straight=runway.bearing
        reverse= normdeg(straight-180)
        left = normdeg(straight-90)
        right = normdeg(straight+90)
        rwystart = move(runway.position(), reverse, runway.length/2,self.apalt)
        rwyend = move(runway.position(), straight, runway.length/2,self.apalt)
        position = move(rwyend,right,radius/5,self.apalt+altitude)
        self.create_waypoint(position, "Crosswind %s"%runway.name, WayPoint.CIRCUIT, PlaneInfo.CIRCUIT_CROSSWIND)
        position = move(rwyend,left,radius,self.apalt+altitude)
        self.create_waypoint(position, "Downwind %s"%runway.name, WayPoint.CIRCUIT, PlaneInfo.CIRCUIT_DOWNWIND)
        position = move(position,reverse,radius*1.2+runway.length,self.apalt+altitude)
        self.create_waypoint(position, "Base %s"%runway.name, WayPoint.CIRCUIT, PlaneInfo.CIRCUIT_BASE)
        position = move(position,right,radius,self.apalt+500*units.FT)
        self.create_waypoint(position, "Final 1 %s"%runway.name, WayPoint.CIRCUIT, PlaneInfo.CIRCUIT_FINAL)
        position = move(position,straight,radius/3,self.apalt+350*units.FT)
        self.create_waypoint(position, "Final 2 %s"%runway.name, WayPoint.CIRCUIT, PlaneInfo.LANDING)
        position = move(position,straight,radius/3,self.apalt+250*units.FT)
        self.create_waypoint(position, "Final 3 %s"%runway.name, WayPoint.CIRCUIT, PlaneInfo.LANDING)
        position = move(rwystart,reverse,30,self.apalt+15)
        self.create_waypoint(position, "Flare 1 %s"%runway.name, WayPoint.CIRCUIT, PlaneInfo.LANDING)
        position = move(position,straight,100,self.apalt+10)
        self.create_waypoint(position, "Flare 2 %s"%runway.name, WayPoint.CIRCUIT, PlaneInfo.LANDING)
        position = move(position,straight,100,self.apalt+5)
        self.create_waypoint(position, "Flare 3 %s"%runway.name, WayPoint.CIRCUIT, PlaneInfo.LANDING)
        position = move(position,straight,100,self.apalt)
        self.create_waypoint(position, "Touchdown %s"%runway.name, WayPoint.RWY, PlaneInfo.TOUCHDOWN)
        position = move(position,straight,180,self.apalt)
        self.create_waypoint(position, "Landing Roll End%s" % runway.name, WayPoint.RWY, PlaneInfo.ROLLING)
        # TODO: Create parking
        
    def create_waypoint(self,position, name, atype, status):
        try:
            name = name[:20] # truncate to avoid overflowing the field.
            return self.circuit.create_waypoint(position,name,atype,status)
        except:
            llogger.exception("Al intentar con %s" % name)

