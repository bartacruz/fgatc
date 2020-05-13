'''
Created on 7 may. 2020

@author: julio
'''

from transitions import Machine
from fgserver.messages import alias
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
    
    states = ['stopped','pushback','taxiing','short','linedup','departing','climbing','cruising','approaching','on_circuit','rejoining','landing', 'rolling']
    
    
    def __init__(self, aircraft, dynamic_manager):
        #self.circuit = circuit
        self.aircraft = aircraft
        self.order = None
        self.started = False
        self.clearances = Clearances()  
    
        
        self.machine = Machine(model=self,states=StatePlane.states,initial='stopped',before_state_change=['entering_state_changed'], after_state_change=['state_changed'])
        self.machine.add_transition('stop', '*', 'stopped')
        self.machine.add_transition('start', 'stopped', 'pushback', conditions=[lambda: self.clearances.start])
        self.machine.add_transition('taxi', 'pushback', 'taxiing', conditions=[lambda: self.clearances.taxi], before=['generate_waypoints'])

        self.machine.add_transition('taxi', 'short', 'taxiing', conditions=[lambda: self.clearances.cross], after=[]) # remove clearance
        self.machine.add_transition('taxi', 'short', 'taxiing', conditions=[lambda: self.clearances.lineup])
        self.machine.add_transition('taxi', 'short', 'taxiing', conditions=[lambda: self.clearances.take_off])
        self.machine.add_transition('taxi', 'rolling', 'taxiing', conditions=[lambda: self.clearances.parking])
        
        self.machine.add_transition('hold', 'taxiing', 'short', conditions=[lambda: self.clearances.short])
        self.machine.add_transition('hold', 'taxiing', 'taxiing', conditions=[lambda: not self.clearances.short])
        
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
        status = self.copilot.update_aircraft(status)
        return status
    
    def entering_state_changed(self):
        print(self.aircraft,"entering state %s" % self.state)
        
    def state_changed(self):
        print(self.aircraft,"state changed to %s" % self.state)
        self.dynamics.check()
        self.copilot.state_changed()
        
    def __str__(self):
        return self.aircraft.callsign
    
    def check_request(self):
        self.copilot.check_request()
    
        
    def reached(self,waypoint):
        llogger.debug("{%s}(%s) reached waypoint %s | %s" % (self.aircraft, self.state, waypoint.status, waypoint))
        llogger.debug("{%s}(%s) clearances: %s " % (self.aircraft, self.state, self.clearances))
        if waypoint.status == PlaneInfo.PUSHBACK:
            self.start()
        if waypoint.status == PlaneInfo.SHORT:
            self.hold()
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
            self.taxi()
        elif waypoint.status == PlaneInfo.STOPPED:
            self.stop()

        
        self.flightplan.reached(waypoint)
        self.dynamics.set_waypoint(self.flightplan.waypoint(),self.flightplan.next_waypoint())
        
    def generate_waypoints(self):
        self.flightplan.generate_waypoints()
        
    
