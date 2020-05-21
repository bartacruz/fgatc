'''
Created on 7 may. 2020

@author: julio
'''

from transitions import Machine
from fgserver.messages import alias, sim_time
import time
from fgserver.ai.handlers import Copilot, FlightPlanManager
from fgserver.ai.common import PlaneInfo
import logging

llogger = logging.getLogger(__name__)

class Clearances():
    start=False
    taxi = False
    cross = False
    lineup = False
    take_off = False
    join = False
    land = False
    touch_and_go=False
    short = False
    runway = False
    report = False
    parking = False
    straight = False
    
    def __init__(self):
        self.start=False
        self.taxi = False
        self.cross = False
        self.lineup = False
        self.take_off = False
        self.join = False
        self.land = False
        self.touch_and_go=False
        self.short = False
        self.runway = False
        self.report = False
        self.parking = False
        self.straight = False


    def __str__(self):
        return str(self.__dict__)
    
class StatePlane(object):
    
    states = ['stopped','starting','pushback','taxiing','holding','short','linedup','departing','climbing','cruising','approaching','on_circuit','rejoining','landing', 'rolling', 'crossing']
    
    
    def __init__(self, aircraft, dynamic_manager, init_delay=0):
        #self.circuit = circuit
        self.aircraft = aircraft
        self.order = None
        self.started = False
        self.init_delay = init_delay
        self.stopped_time=sim_time()
        
        self.clearances = Clearances()  
    
        
        self.machine = Machine(model=self,states=StatePlane.states,initial='stopped',before_state_change=['entering_state_changed'], after_state_change=['state_changed'])
        self.machine.add_transition('stop', '*', 'stopped')
        self.machine.add_transition('start', 'stopped', 'starting', conditions=[lambda: self.clearances.start])
        self.machine.add_transition('pushback', ['stopped','starting'], 'pushback', conditions=[lambda: self.clearances.start], before=['generate_waypoints'])
        self.machine.add_transition('pushback', 'pushback', 'pushback', conditions=[lambda: self.clearances.taxi])
        
        self.machine.add_transition('taxi', ['pushback', 'holding'], 'taxiing', conditions=[lambda: self.clearances.taxi])
        self.machine.add_transition('taxi', 'short', 'taxiing', conditions=[lambda: self.clearances.cross], after=[]) # remove clearance
        
        self.machine.add_transition('taxi', 'short', 'taxiing', conditions=[lambda: self.clearances.lineup])
        self.machine.add_transition('taxi', 'short', 'taxiing', conditions=[lambda: self.clearances.take_off])
        
        self.machine.add_transition('hold', 'taxiing', 'short', conditions=[lambda: self.clearances.short or not self.clearances.taxi])
        self.machine.add_transition('hold', 'taxiing', 'taxiing', conditions=[lambda: not self.clearances.short])
        self.machine.add_transition('hold', 'rolling', 'short', conditions=[lambda: not self.clearances.parking])
        self.machine.add_transition('hold', 'rolling', 'taxiing', conditions=[lambda: self.clearances.parking])
        
        self.machine.add_transition('cross', 'taxiing', 'holding', conditions=[lambda: not self.clearances.cross])
        self.machine.add_transition('cross', 'holding', 'crossing', conditions=[lambda: self.clearances.cross])
        self.machine.add_transition('cross', 'crossing', 'taxiing', conditions=[lambda: self.clearances.cross])
        
        
        self.machine.add_transition('depart', 'linedup', 'departing', conditions=[lambda: self.clearances.take_off ],after=['generate_waypoints','depart'])
        self.machine.add_transition('depart', 'short', 'taxiing', conditions=[lambda: self.clearances.lineup or self.clearances.take_off])
        self.machine.add_transition('depart', '*', 'linedup', conditions=[lambda: not self.flightplan.depart_generated],after=['generate_waypoints','depart'])
        self.machine.add_transition('depart', '*', 'linedup', conditions=[lambda: not self.clearances.take_off])
        
        
        self.machine.add_transition('climb', 'departing', 'climbing')
        
        self.machine.add_transition('cruise', '*', 'cruising')
        
        self.machine.add_transition('approach', ['approaching','cruising'], 'approaching', conditions=[lambda: self.clearances.join],after=['generate_waypoints'])
        self.machine.add_transition('approach', ['approaching','cruising'], 'approaching')
        self.machine.add_transition('approach', ['rejoining'], 'approaching')
        
        self.machine.add_transition('join', ['approaching', 'on_circuit'], 'on_circuit', conditions=[lambda: self.clearances.join or self.clearances.land])
        
        self.machine.add_transition('land', 'on_circuit', 'landing', conditions=[lambda: self.clearances.land],after=['generate_waypoints'])
        self.machine.add_transition('land', 'on_circuit', 'rejoining', conditions=[lambda: not self.clearances.land])
        
        self.machine.add_transition('roll', 'landing', 'rolling',after=['generate_waypoints'] )
        self.machine.add_transition('park', 'short', 'taxiing', before=['generate_waypoints'] )
        
        
        
        self.dynamics = dynamic_manager(self)
        
        self.flightplan = FlightPlanManager(self,aircraft.plans.first().circuit)
        
        self.copilot = Copilot(self)
        
        # HACK
        self.dynamics.position = self.flightplan.waypoint().get_position()
        self.dynamics.set_waypoint(self.flightplan.waypoint(),self.flightplan.next_waypoint())
        
        
        
    def process_order(self,order):
        #print("%s process_order: %s" % (self.aircraft.callsign,order,))
        #llogger.debug("{%s} order=%s" % (self.aircraft,order,))
        self.copilot.process_order(order)
    
            
    def update(self,time):
        self.dynamics.update(time)
        status = self.dynamics.update_aircraft()
        
        if self.is_stopped() and self.init_delay != None:
            if sim_time() - self.stopped_time > self.init_delay:
                llogger.debug("{%s}(%s) starting! %s > %s " % (self.aircraft, self.state, sim_time() - self.stopped_time, self.init_delay))
                self.flightplan._waypoint = 0
                self.clearances.start = True
                print("START BEFORE WP",self.flightplan._waypoint)
                self.start()
                print("START AFTER  WP",self.flightplan._waypoint)
            else:
                #llogger.debug("{%s}(%s) WAITING on stopped %s > %s " % (self.aircraft, self.state, sim_time() - self.stopped_time, self.init_delay))
                return status
        
        status = self.copilot.update_aircraft(status)
        
        return status
    
    def entering_state_changed(self):
        print(self.aircraft,"entering state %s" % self.state)
        
    def state_changed(self):
        print(self.aircraft,"state changed to %s" % self.state)
        self.dynamics.check()
        self.copilot.state_changed()
#           
        
    def __str__(self):
        return self.aircraft.callsign
    
    def check_request(self):
        self.copilot.check_request()
    
        
    def reached(self,waypoint):
        llogger.debug("{%s}(%s) reached waypoint %s | %s" % (self.aircraft, self.state, waypoint.status, waypoint))
        llogger.debug("{%s}(%s) clearances: %s " % (self.aircraft, self.state, self.clearances))
        if waypoint.status == PlaneInfo.STOPPED:
            print("STOPPING")
            self.stopped_time = sim_time()
            self.stop()
        elif waypoint.status == PlaneInfo.TAXIING and self.is_pushback():
            self.taxi()
        elif waypoint.status == PlaneInfo.SHORT:
            self.hold()
        elif waypoint.status == PlaneInfo.CROSS:
            self.cross()
        elif waypoint.status == PlaneInfo.LINED_UP:
            self.state = 'linedup'
            self.depart()
        elif waypoint.status == PlaneInfo.CLIMBING:
            self.climb()
        elif waypoint.status == PlaneInfo.CRUISING:
            self.cruise()
        elif waypoint.status == PlaneInfo.APPROACHING:
            self.approach()
        elif waypoint.status in PlaneInfo.CIRCUITS:
            self.join()
        elif waypoint.status == PlaneInfo.TOUCHDOWN:
            self.roll()
        elif self.is_rolling() and waypoint.status == PlaneInfo.HOLD:
            self.hold()
        
        
        self.flightplan.reached(waypoint)
        self.dynamics.set_waypoint(self.flightplan.waypoint(),self.flightplan.next_waypoint())
        
    def generate_waypoints(self):
        try:
            self.flightplan.generate_waypoints()
        except:
            llogger.exception("Generating waypoints")
        
    
