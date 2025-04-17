'''
Created on 29 abr. 2020

@author: julio
'''

from random import randint

from fgserver import units
from fgserver.ai.actions import TuneInAction, ReadyTaxiAction, ReadBackAction,\
    RequestInboundAction, HoldingShortAction, ReadyTakeoffAction, LeavingAction,\
    ReportCircuitAction, RequestParkAction, ClearedRunwayAction,\
    CrossRunwayAction
from fgserver.ai.common import PlaneInfo, PlaneRequest
from fgserver.map.consumers import AircraftConsumer
from fgserver.ai.dijkstra import dj_waypoints, get_next_on_runway,\
    get_runway_exit, taxi_path, taxi_path2
from fgserver.ai.models import WayPoint
from fgserver.helper import move, normdeg, Position, normalize, say_char,\
    get_heading_to, get_distance, angle_diff
from fgserver.messages import alias
from fgserver.models import Runway, Comm, get_runway

import logging

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
            self.plane.dynamics.wait(20) # wait 20 seconds to start moving
            self.plane.depart()
        elif order.ord==alias.CLEAR_TK:
            self.actions.append(ReadBackAction(self, order))
            clearances.take_off = True
            clearances.short = False
            self.plane.dynamics.wait(20)
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
            clearances.join = True
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
            
            llogger.debug("{%s-CP}(%s) park called %s (%s)" % (self.aircraft, self.plane.state, self.plane.state,clearances.parking))
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
            self.plane.manager.reset()
            self.plane.reset()
            
        if self.plane.is_rejoining():
            llogger.debug("{%s-CP} Plane is rejoining, finding waypoint" % self.aircraft)
            wp = self.plane.flightplan.waypoints.filter(status=PlaneInfo.APPROACHING).last()
            self.plane.clearances.report=alias.CIRCUIT_CROSSWIND
            self.plane.manager.reroute(wp)
            llogger.debug("{%s-CP} Waypoint found. Setting course to %s" % (self.aircraft,wp))
            self.plane.dynamics.set_waypoint(self.plane.flightplan.waypoint(),self.plane.flightplan.next_waypoint())
            self.plane.approach()            
        
    @staticmethod
    def get_FGfreq(frequency):
        sf = str(frequency)
        return "%s.%s" % (sf[:3],sf[3:])
    
    def airport(self):
        if self.plane.state in self.plane.departing_states: 
            return self.plane.manager.flightplan.departure
        else:
            return self.plane.manager.flightplan.arrival
    
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
            clearances.take_off = False
            clearances.runway = False
        elif self.plane.is_landing():
            clearances.join = False
            clearances.straight = False
        elif self.plane.is_rolling():
            clearances.land=False
            #clearances.parking=True # TODO: request parking
        elif self.plane.is_stopped():
            for i in clearances.__dict__:
                setattr(clearances, i, False)
            
    def check_request(self):
        llogger.debug("{%s-CP} check_request. self.freq=%s, clearances=%s" %  (self.aircraft,self.freq, self.plane.clearances,))
        
        clearances = self.plane.clearances

        if self.plane.is_starting() and not clearances.taxi:
            llogger.debug("{%s-CP} check_request: queing ReadyTaxiAction" % self.aircraft)
            comm = self.get_comm_by_type(self.airport(),Comm.GND)
            self.actions.append(TuneInAction(self,comm.frequency)) # Make sure we are tunned right
            self.actions.append( ReadyTaxiAction(self) )
        elif self.plane.is_holding() and not clearances.lineup and not clearances.cross:
            llogger.debug("{%s-CP} check_request: queing RequestCrossAction" % self.aircraft)
            # TODO: detect wich runway we got in front
            self.actions.append( CrossRunwayAction(self,clearances.runway) )
        elif self.plane.is_taxiing() and clearances.cross:
            llogger.debug("{%s-CP} check_request: queing ClearedRunway" % self.aircraft)
            # TODO: detect wich runway we got in front
            clearances.cross = False
            self.actions.append( ClearedRunwayAction(self,clearances.runway) )
        elif self.plane.is_short() and clearances.taxi and not clearances.take_off and not self.already_requested(alias.HOLDING_SHORT):
            llogger.debug("{%s-CP} check_request: queing HoldingShortAction" % self.aircraft)
            self.actions.append( HoldingShortAction(self,clearances.runway) )
        elif self.plane.is_linedup() and not clearances.take_off and not self.already_requested(alias.READY_TAKEOFF):
            llogger.debug("{%s-CP} check_request: queing ReadyTakeoffAction" % self.aircraft)
            self.actions.append( ReadyTakeoffAction(self,clearances.runway) )
        elif self.plane.is_climbing() and not self.request.req == alias.LEAVING:
            self.actions.append( LeavingAction(self,clearances.runway) )
        elif self.plane.is_approaching() and not (clearances.join or clearances.land) and not self.already_requested(alias.INBOUND_APPROACH):

            llogger.debug("{%s-CP} check_request: queing inbound approach action" % self.aircraft)
            comm = self.get_comm_by_type(self.airport(),Comm.APP)
            self.actions.append(TuneInAction(self,comm.frequency)) # Make sure we are tunned right
            self.actions.append(RequestInboundAction(self)) 
        elif self.plane.is_on_circuit() and clearances.report:
            circ = self.circuits_helper[self.plane.manager.waypoint().status]
            if clearances.report and clearances.report == circ:
                llogger.debug("{%s-CP} check_request: queing report circuit action for %s" % (self.aircraft, circ))
                comm = self.get_comm_by_type(self.airport(),Comm.TWR)
                self.actions.append(TuneInAction(self,comm.frequency)) # Make sure we are tunned right
                self.actions.append(ReportCircuitAction(self, circ, clearances.runway)) 
                clearances.report = None
        elif self.plane.is_short() and not clearances.taxi:
            llogger.debug("{%s-CP} check_request: short after rolling" % self.aircraft)
            comm = self.get_comm_by_type(self.plane.manager.flightplan.arrival, Comm.TWR)
            self.actions.append(TuneInAction(self,comm.frequency, comm)) # Make sure we are tunned right
            self.actions.append(ClearedRunwayAction(self,clearances.runway))
        
    
class FlightPlanManager():
    
    def __init__(self,plane,flightplan):
        self.plane = plane
        self.flightplan = flightplan
        # self.airport = flightplan.airport
        self.reset()
        
    def reset(self):
        self._waypoint = 0
        # TODO: free handler from FlightPlan.
        self.plane.aircraft.state=2
        self.plane.aircraft.save()
        self.handler = self.flightplan.get_handler()
        self.handler.reset()
        self.landing_generated = False
        self.depart_generated = False
        self.climb_generated = False
        self.cruise_generated = False
        self.rolling_generated = False
        self.parking_generated = False
        
#         self.reached(self.waypoint())
        llogger.debug("{%s-FP} waypoint: %s %s" % (self.plane.aircraft,self._waypoint,self.waypoint() ) )
        
    def reached(self,waypoint):
        if self.flightplan.waypoints.all().count() <= self._waypoint:
            llogger.debug("{%s-FP} end of the line. %s" % (self.plane.aircraft, self._waypoint))
            return
        self._waypoint += 1
        llogger.info("{%s-FP} Next wp: %s" % (self.plane.aircraft,self.waypoint() ) )
        
    def waypoints(self):
        return self.flightplan.waypoints
    
    def reroute(self,waypoint):
        wp_index = list(self.waypoints().all().order_by('id')).index(waypoint)
        self._waypoint = wp_index
        llogger.info("{%s-FP} Rerouting to %s: %s" % (self.plane.aircraft, wp_index,self.waypoint()))
    
    def generate_waypoints(self):
        llogger.debug("{%s-FP} generating wpts. state=%s" % (self.plane.aircraft, self.plane.state))
        clearances = self.plane.clearances
        position = self.plane.dynamics.position
        if self.plane.is_starting():
            llogger.debug("{%s-FP} generating waypoints to runway %s. wp=%s" % (self.plane.aircraft, clearances.runway, self._waypoint))
            runway = self.flightplan.departure.runways.get(name=clearances.runway)
            self.handler.generate_taxi_waypoints(position,runway)
            self.reached(self.waypoint())
            self.plane.dynamics.set_waypoint(self.waypoint(),self.next_waypoint())    
            
        elif self.plane.is_linedup() and not self.depart_generated:
            llogger.debug("{%s-FP} generating depart waypoints" % self.plane.aircraft)
            self.depart_generated=True
            runway = self.flightplan.departure.runways.get(name=clearances.runway)
            self.handler.generate_depart_waypoints(runway)
        elif self.plane.is_departing() and not self.climb_generated:
            llogger.debug("{%s-FP} generating climb waypoints" % self.plane.aircraft)
            self.climb_generated=True
            runway = self.flightplan.departure.runways.get(name=clearances.runway)
            self.handler.generate_climb_waypoints(runway)
        elif self.plane.is_climbing() and not self.cruise_generated:
            llogger.debug("{%s-FP} generating cruise waypoints" % self.plane.aircraft)
            self.cruise_generated=True
            self.handler.generate_cruise_waypoints()
        elif self.plane.is_cruising() and self._waypoint > 3:
            # RESET FLIGHTPLAN??
            pass
        elif self.plane.is_approaching() and clearances.join and not self.landing_generated:
            llogger.debug("{%s-FP} generating circuit landing waypoints" % self.plane.aircraft)
            self.landing_generated=True
            runway = self.flightplan.arrival.runways.get(name=clearances.runway)
            self.handler.generate_landing_waypoints(runway, clearances)
        elif self.plane.is_rolling() and not self.rolling_generated:
            llogger.debug("{%s-FP} generating roling waypoints" % self.plane.aircraft)
            runway = self.flightplan.arrival.runways.get(name=clearances.runway)
            self.handler.generate_rolling_waypoints(position,runway)
            self.rolling_generated = True
        elif clearances.parking and not self.parking_generated:
            llogger.debug("{%s-FP} generating parking waypoints" % self.plane.aircraft)

            parking = self.flightplan.arrival.startups.get(pk=clearances.parking)
            nwp = self.waypoints().count() 
            self.handler.generate_parking_waypoints(position,parking.get_position())
            self.parking_generated = True
            self._waypoint = nwp
            self.plane.dynamics.set_waypoint(self.waypoint(),self.next_waypoint())
        AircraftConsumer.publish_plan(self.flightplan)

    def waypoint(self):
        count = self.flightplan.waypoints.all().count()
        if count == 0:
            return None
        if count <= self._waypoint:
            self._waypoint=self.flightplan.waypoints.all().count()-1
            llogger.debug("{%s-FP} reset waypoint to %s" % (self.plane.aircraft, self._waypoint))
            
        return self.flightplan.waypoints.all().order_by('id')[self._waypoint]
        
    def next_waypoint(self):
        if self.flightplan.waypoints.all().count() > self._waypoint + 1:
            return self.flightplan.waypoints.all().order_by('id')[self._waypoint+1]
        return None


class CircuitHandler():
    
    def __init__(self,flightplan):
        self.flightplan = flightplan
        self.airport = flightplan.departure
        self.aircraft = flightplan.aircraft
        self.reset()
    
    def reset(self):
        self.flightplan.waypoints.all().delete()
        self.generate_start_waypoints()
        self.status=None
        self.radius = 2*units.NM
        AircraftConsumer.publish_plan(self.flightplan)
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
            position.z = self.departure_apalt
            self.create_waypoint(position, start_l.name, WayPoint.PARKING, PlaneInfo.STOPPED)
            self.create_waypoint(position, start_l.name, WayPoint.PUSHBACK, PlaneInfo.PUSHBACK)
        else:
            position = self.airport.get_position()
            bearing = get_heading_to(position,self.airport.active_runway().get_position())
            dist = get_distance(position, self.airport.active_runway().get_position())
            position = move(position,bearing,dist/5,self.departure_apalt)
            self.create_waypoint(position, "1", WayPoint.PARKING, PlaneInfo.STOPPED)
            self.create_waypoint(position, "1", WayPoint.PUSHBACK, PlaneInfo.PUSHBACK)

    def generate_rolling_waypoints(self,position,runway):
        path = get_runway_exit(runway, position, runway.bearing)
        if not len(path):
            position = move(position,runway.bearing,runway.width*5,self.arrival_apalt)
            self.create_waypoint(position, "On runway %s" % runway.name, WayPoint.RWY, PlaneInfo.ROLLING)
            position = move(position,normalize(runway.bearing+45),runway.width*2,self.arrival_apalt)
            self.create_waypoint(position, "Aside of runway %s" % runway.name, WayPoint.HOLD, PlaneInfo.SHORT)
            return
        for node in path:
            position=Position(node.point.y,node.point.x, self.arrival_apalt)
            wp = self.create_waypoint(position, "On runway %s" % runway.name, WayPoint.RWY, PlaneInfo.ROLLING)
        # last wp is outside the runway. must hold.
        wp.status = PlaneInfo.SHORT
        wp.type = WayPoint.HOLD
        wp.save()
    
    @property
    def apalt(self):
        return float(self.airport.altitude*units.FT)
    
    @property
    def departure_apalt(self):
        return float(self.flightplan.departure.altitude*units.FT)
    @property
    def arrival_apalt(self):
        return float(self.flightplan.arrival.altitude*units.FT)
    
    def generate_parking_waypoints(self, position, park):
        path = taxi_path(self.flightplan.arrival,position, park)
        for node in path:
            position=Position(node.point.y,node.point.x, self.arrival_apalt)
            self.create_waypoint(position, "Taxi %s" % node.id, WayPoint.TAXI, PlaneInfo.TAXIING)
        
        # Last wp is the parking itself. Stop.
        park.z = self.arrival_apalt
        self.create_waypoint(park, "Parking", WayPoint.PARKING, PlaneInfo.STOPPED)
                
    def generate_taxi_waypoints(self, pos1, pos2, heading = None):
        # TODO: Change when geodjango is completly implemented
        p1 = pos1.to_point()
        if heading:
            # TODO: Calculate shortest p1 on similar heading
            pass
        if isinstance(pos2, Runway):
            rwystart = move(pos2.position(), normalize(pos2.bearing-180), pos2.length/2,pos2.position().z)
            lineup = move(rwystart, pos2.bearing, 50,self.departure_apalt)
            p2 = rwystart.to_point()
            p2r=True
        else:
            rwystart = pos2
            p2 = pos2.to_point()
            p2r = False
        taxi = taxi_path(self.airport,p1, p2, end_on_rwy=p2r)
        position = None
        last_short = None
        last_taxi = None
        if len(taxi):
            for way in taxi:
                taxinode = self.airport.taxinodes.filter(name=way.id).first()
                position = Position.from_point(way.point, self.departure_apalt)
                on_runway = self.airport.on_runway(way.point)
                if taxinode:
                    if taxinode.short:
                        wp = self.create_waypoint(position, "Short %s" % way.id, WayPoint.HOLD, PlaneInfo.SHORT)
                        if last_short:
                            last_short.status=PlaneInfo.TAXIING
                            last_short.type=WayPoint.TAXI
                            last_short.save()
                        last_short=wp
                    elif on_runway:
                        wp = self.create_waypoint(position, "rwy %s" % way.id, WayPoint.RWY, PlaneInfo.TAXIING)
                    else:
                        wp = self.create_waypoint(position, "Taxi %s" % way.id, WayPoint.TAXI, PlaneInfo.TAXIING)
                        last_taxi=wp
                elif on_runway:
                    wp = self.create_waypoint(position, "Rwy %s" % way.id, WayPoint.RWY, PlaneInfo.TAXIING)
                else:
                    wp = self.create_waypoint(position, "Taxi %s" % way.id, WayPoint.TAXI, PlaneInfo.TAXIING)
                    last_taxi = wp
                
        else:
            # Create artificial path between start and lineup
            llogger.debug("No taxi nodes found. Create artificial path between start and lineup")
            heading = get_heading_to(p1,p2)
            distance = get_distance(p1,p2)
            position = move(pos1,heading,10*units.M,pos1.z)
            self.create_waypoint(position, "Taxi 1", WayPoint.TAXI, PlaneInfo.TAXIING)
            position = move(position,heading,distance/2,self.departure_apalt)
            self.create_waypoint(position, "Taxi 2", WayPoint.TAXI, PlaneInfo.TAXIING)
            position = move(rwystart,normalize(heading+180),50*units.M,p2.z)
            last_short = self.create_waypoint(position, "Short of rwy", WayPoint.HOLD, PlaneInfo.SHORT)
            position = move(rwystart, pos2.bearing, 20,self.departure_apalt)
            self.create_waypoint(position, "Taxi 3", WayPoint.TAXI, PlaneInfo.TAXIING)

        if isinstance(pos2, Runway):
            
            if not last_short and last_taxi:
                # Create artificial short location with last not-on-runway node
                last_taxi.name = "Hold Short"
                last_taxi.status = PlaneInfo.SHORT
                last_taxi.type = WayPoint.HOLD
                last_taxi.save()
            self.create_waypoint(lineup, "Lineup  %s"% pos2.name, WayPoint.RWY, PlaneInfo.LINED_UP)
            # HACK: add a departure wpt ahead to properly align the plane with the rwy before departing
            # position = move(lineup,pos2.bearing,10,self.departure_apalt)
            # self.create_waypoint(position, "Departure hack  %s"% pos2.name, WayPoint.RWY, PlaneInfo.DEPARTING)
    
    def generate_depart_waypoints(self, runway):
        
        rwystart = move(runway.position(), normdeg(runway.bearing-180), runway.length/2,self.departure_apalt)
        rwyend = move(runway.position(), runway.bearing, runway.length/2,self.departure_apalt)
        linedup = self.flightplan.waypoints.filter(status = PlaneInfo.LINED_UP).last()
        straight=float(runway.bearing)
        # departure_state = self.flightplan.fdm.get_props("departing")
        # rotate_time= departure_state.speed*units.KNOTS / departure_state.acceleration
        # rotate_distance = 0.5*departure_state.acceleration*rotate_time*rotate_time
        
        rotate_distance= self.flightplan.fdm.takeoff_distance * 1.1 # give some wiggle room

        llogger.debug("{%s-CH} rotate distance=%d" % (self.aircraft, rotate_distance))
        if linedup:
            llogger.debug("{%s-CH} using startup waypoint %s" % (self.aircraft, linedup,) )
            position = move(linedup.get_position(),straight,20,linedup.get_position().z)
        else:
            position = move(rwystart,straight,50,self.departure_apalt)
        self.create_waypoint(position, "Roll start %s" % runway.name, WayPoint.RWY, PlaneInfo.DEPARTING) # Set to start roll
        position = move(position,straight,rotate_distance,self.departure_apalt)
        self.create_waypoint(position, "Rotate1 %s" % runway.name, WayPoint.RWY, PlaneInfo.DEPARTING)
        lift_distance = min(rotate_distance, get_distance(position,rwyend)) /3
        position = move(position,straight,lift_distance,self.departure_apalt+5)
        self.create_waypoint(position, "Rotate2 %s" % runway.name, WayPoint.RWY, PlaneInfo.DEPARTING)
        position = move(rwyend,straight,5,self.apalt+30)
        self.create_waypoint(position, "Departing %s" % runway.name, WayPoint.RWY, PlaneInfo.DEPARTING)
        

    def generate_climb_waypoints(self, runway):
        altitude = self.flightplan.altitude
        position = self.flightplan.waypoints.last().get_position()
        straight = runway.bearing
        # get speeds from fdm
        props = self.flightplan.fdm.get_props('climbing')
        speed = props.speed*units.KNOTS
        vertical_speed=props.vertical_speed*units.FPM

        position = move(position,straight,200*units.M,position.z)
        self.create_waypoint(position, "Climbing 1", WayPoint.RWY, PlaneInfo.CLIMBING)
        t_alt = position.z
        # distance = t_alt * speed / vertical_speed
        while t_alt < altitude:
            step = 1000*units.M
            t_alt = position.z + (step/speed) * vertical_speed
            t_alt = min(t_alt,altitude)
            position = move(position,straight,step*1.2, t_alt)
            self.create_waypoint(position, "Climb %d" % (t_alt/units.FT), WayPoint.POINT, PlaneInfo.CLIMBING)
        position = move(position,straight,1000*units.M, altitude)
        self.create_waypoint(position, "Climb finished", WayPoint.POINT, PlaneInfo.CLIMBING)
        

    def generate_cruise_waypoints(self):
        radius = self.radius
        altitude = self.flightplan.altitude
        straight = self.flightplan.aircraft.heading
        position = self.flightplan.waypoints.last().get_position()
        mult = 1 if randint(0,10) >= 5 else -1
        position = move(position,normdeg(straight),radius,self.apalt+altitude)
        self.create_waypoint(position, "Cruising 1", WayPoint.POINT, PlaneInfo.CRUISING)
        position = move(position,normdeg(straight+40*mult),radius*0.7,self.apalt+altitude)
        self.create_waypoint(position, "Cruising 2", WayPoint.POINT, PlaneInfo.CRUISING)
        position = move(position,normdeg(straight+80*mult),radius*0.6,self.apalt+altitude)
        self.create_waypoint(position, "Cruising 3", WayPoint.POINT, PlaneInfo.CRUISING)
        position = move(position,normdeg(straight+120*mult),radius*0.6,self.apalt+altitude)
        self.create_waypoint(position, "Cruising 4", WayPoint.POINT, PlaneInfo.CRUISING)
        position = move(position,normdeg(straight+150*mult),radius*0.6,self.apalt+altitude)
        self.create_waypoint(position, "Cruising 5", WayPoint.POINT, PlaneInfo.CRUISING)
        position = move(position,normdeg(straight+190*mult),radius*0.6,self.apalt+altitude)
        self.create_waypoint(position, "Approaching 1", WayPoint.POINT, PlaneInfo.APPROACHING)
        position = move(position,normdeg(straight+230*mult),radius*0.6,self.apalt+altitude)
        self.create_waypoint(position, "Approaching 2", WayPoint.POINT, PlaneInfo.APPROACHING)
    
    def get_approach_distance(self):
        ''' 
        returns the distance needed to get from cruise altitude to circuit altitude
        '''
        # get props from fdm
        state_props = self.flightplan.fdm.get_props("approaching")
        speed = state_props.speed * units.KNOTS
        vertical_speed= state_props.vertical_speed * units.FPM
        altitude = self.flightplan.altitude
        circuit_altitude = self.arrival_apalt + 1000*units.FT
        delta_alt = altitude - circuit_altitude
        distance_needed = delta_alt * speed / vertical_speed
        return distance_needed

    def get_join_circuit_position(self,runway,clearances):
        # TODO: get this from join clearance
        radius = self.radius
        straight=runway.bearing
        reverse= normdeg(straight-180)
        left = normdeg(straight-90)
        right = normdeg(straight+90)
        rwystart = move(runway.position(), reverse, runway.length/2,self.arrival_apalt)
        rwyend = move(runway.position(), straight, runway.length/2,self.arrival_apalt)
        circuit_height = self.arrival_apalt + 1000*units.FT
        if clearances.straight:
            join_position = move(rwystart,reverse,radius*2,circuit_height)
        elif clearances.report == "crosswind":
            join_position = move(rwyend,right,radius/5,circuit_height)
        else:
            join_position = move(rwyend,left,radius,circuit_height)
        return join_position

    def create_approach_waypoints(self,runway,clearances):
        position = self.flightplan.waypoints.last().get_position()
        join_position = self.get_join_circuit_position(runway, clearances)
        bearing_to_join = get_heading_to(position,join_position)
        distance_to_join = get_distance(position,join_position)

        # get props from fdm
        state_props = self.flightplan.fdm.get_props("approaching")
        speed = state_props.speed * units.KNOTS
        vertical_speed= state_props.vertical_speed * units.FPM
        t_alt = position.z
        
        distance_needed = self.get_approach_distance()
        llogger.debug("approach waypoints: t_alt=%d, join_position.z=%d, distance_to_join=%d, distance_needed=%d" % (t_alt, join_position.z, distance_to_join,  distance_needed ))
        if distance_needed > distance_to_join:
            #make a 360 descent
            llogger.debug("{%s-CH} needed a 360! distance_to_join=%d, distance_needed=%d)" % (self.aircraft, distance_to_join, distance_needed))
        wp = None
        while t_alt > join_position.z:
            step = 1000*units.M
            t_alt = position.z - (step/speed) * vertical_speed
            t_alt = max(t_alt, join_position.z)
            position = move(position,bearing_to_join, step, t_alt)
            wp = self.create_waypoint(position, "Approach %d ft" % (t_alt / units.FT), WayPoint.POINT, PlaneInfo.APPROACHING)
        return wp
        
    
    def generate_landing_waypoints(self,runway,clearances):
        self.create_approach_waypoints(runway,clearances)
        radius = self.radius
        altitude = self.flightplan.altitude
        # TODO: get this from join clearance
        circuit_altitude = self.arrival_apalt + 1000*units.FT
        straight=runway.bearing
        reverse= normdeg(straight-180)
        left = normdeg(straight-90)
        right = normdeg(straight+90)
        rwystart = move(runway.position(), reverse, runway.length/2,self.arrival_apalt)
        rwyend = move(runway.position(), straight, runway.length/2,self.arrival_apalt)
        position = self.get_join_circuit_position(runway, clearances)
        
        if clearances.straight:
            #position = move(rwystart,reverse,radius*2,altitude)
            self.create_waypoint(position, "Straight 1 %s"%runway.name, WayPoint.CIRCUIT, PlaneInfo.CIRCUIT_STRAIGHT)
            position = move(rwystart,reverse,radius*1.5, circuit_altitude)
            self.create_waypoint(position, "Straight 2 %s"%runway.name, WayPoint.CIRCUIT, PlaneInfo.CIRCUIT_STRAIGHT)
            position = move(position,straight,radius, self.arrival_apalt+700*units.FT)
            self.create_waypoint(position, "Final 1 %s"%runway.name, WayPoint.CIRCUIT, PlaneInfo.CIRCUIT_FINAL)
        else:
            if clearances.report == "crosswind":
                self.create_waypoint(position, "Crosswind %s"%runway.name, WayPoint.CIRCUIT, PlaneInfo.CIRCUIT_CROSSWIND)
            position = move(rwyend,left, radius, circuit_altitude)
            self.create_waypoint(position, "Downwind %s" % runway.name, WayPoint.CIRCUIT, PlaneInfo.CIRCUIT_DOWNWIND)
            position = move(position,reverse, radius*1.2+runway.length, circuit_altitude)
            self.create_waypoint(position, "Base %s"%runway.name, WayPoint.CIRCUIT, PlaneInfo.CIRCUIT_BASE)
            position = move(position,right, radius, self.arrival_apalt+700*units.FT)
            self.create_waypoint(position, "Final 1 %s"%runway.name, WayPoint.CIRCUIT, PlaneInfo.CIRCUIT_FINAL)

        landing_distance = self.flightplan.fdm.landing_distance
        final_distance = get_distance(position,rwystart)
        delta_alt = position.z -self.arrival_apalt
        position = move(position,straight,final_distance*0.33,position.z-delta_alt*0.33)
        self.create_waypoint(position, "Final 2 %s"%runway.name, WayPoint.CIRCUIT, PlaneInfo.LANDING)
        position = move(position,straight,final_distance*0.33,position.z-delta_alt*0.33)
        self.create_waypoint(position, "Final 3 %s"%runway.name, WayPoint.CIRCUIT, PlaneInfo.LANDING)
        position = move(position,straight,final_distance*0.33,self.arrival_apalt+10*units.FT)
        self.create_waypoint(position, "Final 4 %s"%runway.name, WayPoint.CIRCUIT, PlaneInfo.LANDING)

        position = move(position, straight, landing_distance*0.1, self.arrival_apalt+10*units.FT)
        self.create_waypoint(position, "Flare 1 %s"%runway.name, WayPoint.CIRCUIT, PlaneInfo.LANDING)
        position = move(position,straight, landing_distance*0.1, self.arrival_apalt+5*units.FT)
        self.create_waypoint(position, "Flare 2 %s" % runway.name, WayPoint.RWY, PlaneInfo.LANDING)
        position = move(position,straight,landing_distance*0.1,self.arrival_apalt)
        self.create_waypoint(position, "Touchdown %s" % runway.name, WayPoint.RWY, PlaneInfo.TOUCHDOWN)
        position = move(position,straight,landing_distance*0.1,self.arrival_apalt)
        self.create_waypoint(position, "Landing Roll start %s" % runway.name, WayPoint.RWY, PlaneInfo.ROLLING)
        position = move(position,straight,landing_distance*0.6,self.arrival_apalt)
        self.create_waypoint(position, "Landing Roll end %s" % runway.name, WayPoint.RWY, PlaneInfo.ROLLING)

        
    def create_waypoint(self,position, name, atype, status):
        try:
            name = name[:20] # truncate to avoid overflowing the field.
            return self.flightplan.create_waypoint(position,name,atype,status)
        except:
            llogger.exception("Al intentar con %s" % name)

class TripHandler(CircuitHandler):

    def generate_climb_waypoints(self, runway):
        altitude = self.flightplan.altitude
        position = self.flightplan.waypoints.last().get_position()
        ap_altitude = self.flightplan.departure.altitude
        straight = float(runway.bearing)
        position = move(position,straight,200*units.M,position.z)

        self.create_waypoint(position, "Climbing 1", WayPoint.RWY, PlaneInfo.CLIMBING)
        # get props from fdm
        climbing_state = self.flightplan.fdm.get_props("climbing")
        speed = climbing_state.speed * units.KNOTS
        vertical_speed= climbing_state.vertical_speed * units.FPM
        t_alt = position.z
        # distance = t_alt * speed / vertical_speed
        wps = 0
        min_target = min(ap_altitude+1000*units.FT,altitude)
        step = ( min_target- position.z) /3
        while wps < 20 and position.z < min_target:
            #t_alt = position.z + (step/speed) * vertical_speed
            distance = step * speed / vertical_speed
            t_alt = min(min_target,position.z + step+10*units.FT)
            position = move(position,straight,distance, t_alt)
            self.create_waypoint(position, "Climb %d" % (t_alt/units.FT), WayPoint.POINT, PlaneInfo.CLIMBING)
            wps += 1
        
        position_to = self.flightplan.arrival.get_position()
        course = straight
        while position.z < altitude:
            bearing = get_heading_to(position,position_to)
            diff = normdeg(course - bearing)
            bank_sense = 1
            if diff != 0:
                bank_sense = int(diff/abs(diff))*-1
            delta = min(15,abs(diff))
            course = normalize(course+(delta*bank_sense))
            distance =1000*units.M
            t = distance/speed
            t_alt = position.z + t * vertical_speed
            t_alt = min(t_alt,altitude)
            position = move(position,course,distance,t_alt)
            self.create_waypoint(position, "Climb %d" % (t_alt/units.FT), WayPoint.POINT, PlaneInfo.CLIMBING)
            wps +=1
            
        position = move(position,course,1000*units.M, altitude)
        self.create_waypoint(position, "Climb finished", WayPoint.POINT, PlaneInfo.CLIMBING)

    def generate_cruise_waypoints(self):
        
        altitude = self.flightplan.altitude
        p1, p2 = list(self.flightplan.waypoints.order_by("id"))[-2:]
        position = p2.get_position()
        position_to = self.flightplan.arrival.get_position()
        bearing = get_heading_to(position,position_to)
        course = get_heading_to(p1.get_position(), position)
        turns = 0
        diff = normdeg(course - bearing)
        if abs(diff) <= 40:
            position = move(position,normdeg(course),500,altitude)    
            self.create_waypoint(position, "Cruising Start", WayPoint.POINT, PlaneInfo.CRUISING)

        else: 
            while abs(diff) > 40:
                # TODO: use fdm speed and turn rate
                turns = turns +1
                bank_sense = int(diff/abs(diff)*-1)
                course = normalize(course+(20*bank_sense))
                position = move(position,course, 0.5*units.NM, altitude)
                self.create_waypoint(position, "Cruising turn %d" % turns, WayPoint.POINT, PlaneInfo.CRUISING)
                bearing = get_heading_to(position,position_to)
                diff = normdeg(course - bearing)
        approach_distance = self.get_approach_distance()
        position = move(position_to,normdeg(bearing-180),approach_distance*2,altitude)
        self.create_waypoint(position, "Cruising Long", WayPoint.POINT, PlaneInfo.CRUISING)
        position = move(position,normdeg(bearing),approach_distance/4,altitude)
        self.create_waypoint(position, "Approaching 1", WayPoint.POINT, PlaneInfo.APPROACHING)
        position = move(position,normdeg(bearing),approach_distance/4,altitude)
        self.create_waypoint(position, "Approaching 2", WayPoint.POINT, PlaneInfo.APPROACHING)