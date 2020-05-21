'''
Created on 17 may. 2020

@author: julio
'''

from fgserver.models import Comm, StartupLocation
from fgserver.messages import alias, sim_time
import re
from fgserver.helper import short_callsign, say_number
import logging

llogger = logging.getLogger(__name__)
class Action():
    issued = None # a Datetime
    
    
    def __init__(self,handler):
        self.handler = handler
        self.issued = sim_time()
        self.done = False
        self._delay=2 # Default delay before executing
    
    def new_request(self,req_type):
        return self.handler.new_request(req_type)
    
    def send_request(self,request,with_message=False):
        self.handler.requests.append(request)
        if with_message:
            self.send_message(request)
    
    @property
    def waiting(self):
        return self._delay and sim_time() - self.issued < self._delay
        
    def is_ready(self):
        return not self.done and not self.waiting
    
    def execute(self):
        pass
    
    
    def is_done(self):
        return self.done

    def send_message(self,request):
        templates={
           alias.STARTUP:"{atis}request startup clearance",
           alias.TAXI_READY:"{atis}ready to taxi",
           alias.HOLDING_SHORT : "holding short of runway {rwy}",
           alias.CROSS_RUNWAY : "requests cross runway {rwy}",
           alias.READY_TAKEOFF : "ready for take-off, runway {rwy}",
           alias.LEAVING : "leaving airfield",
           alias.INBOUND_APPROACH : "{atis}for inbound approach",
           alias.CIRCUIT_CROSSWIND: '{cirw} for runway {rwy}',
           alias.CIRCUIT_DOWNWIND: '{cirw} for runway {rwy}',
           alias.CIRCUIT_BASE: '{cirw} for runway {rwy}',
           alias.CIRCUIT_FINAL: '{cirw} for runway {rwy}',
           alias.CIRCUIT_STRAIGHT: '{cirw} for runway {rwy}',
           alias.CLEAR_RUNWAY: 'clear of runway {rwy}',
        }
        msg = templates.get(request.req,None)
        if not msg:
            llogger.debug("{%s-CP} No message for %s" % (self.handler.aircraft, request.req, ))
            return
        msg = "%s,%s, %s" % (self.handler.controller, short_callsign(self.handler.aircraft.callsign), msg)
        msg = re.sub(r'{atis}','with %s, ' % self.handler.get_atis(),msg)
        msg = re.sub(r'{cs}',short_callsign(self.handler.aircraft.callsign),msg)
        msg = re.sub(r'{comm}',self.handler.controller,msg)
        msg = re.sub(r'{rwy}',say_number(request.rwy),msg)
        msg = re.sub(r'{alt}',str(request.alt or ''),msg)
        msg = re.sub(r'{cirw}',request.cirw or '',msg)
            
        self.handler.messages.append(msg)






class ReadBackAction(Action):
    
    
    def __init__(self, handler, order):
        Action.__init__(self, handler)
        self.order = order
        self._delay = 15
    
     
    def is_ready(self):
        return self.handler.controller and not self.waiting

    def execute(self):
        if not self.handler.controller:
            return
        templates={
           alias.CLEAR_LAND:"clear to land runway {rwy}{qnh}",
           alias.CLEAR_TOUCHNGO:"clear touch and go{onum} runway {rwy}{qnh}",
           alias.CLEAR_TK : "cleared for take off runway {rwy}",
           alias.CLEAR_CROSS_RUNWAY : "crossing runway {rwy}",
           alias.GO_AROUND : "going around, report on {cirw}",
           alias.JOIN_CIRCUIT:"{cirw} for {rwy} at {alt}{qnh}",
           alias.CIRCUIT_STRAIGHT:"straight for {rwy}, report on {cirw}{qnh}",
           alias.LINEUP : "line up on {rwy}{hld}",
           alias.REPORT_CIRCUIT: 'report on {cirw}',
           alias.STARTUP: "start up approved{qnh}",
           alias.TAXI_TO: "taxi to {rwy}{via}{hld}{short}{lineup}",
           alias.WAIT: "we wait", 
           alias.SWITCHING_OFF: "Good day",
           alias.TAXI_PARK: "taxi to {parkn}{way}{via}{hld}{short}",
        }
        msg = templates.get(self.order.ord)
        if not msg:
            llogger.debug("{%s} No readback for %s" % (self.handler.aircraft,self.order.ord))
            return
        msg = re.sub(r'{cs}',short_callsign(self.handler.aircraft.callsign),msg)
        msg = re.sub(r'{icao}',self.order.apt,msg)
        msg = re.sub(r'{comm}',self.handler.controller,msg)
        msg = re.sub(r'{rwy}',say_number(self.order.rwy),msg)
        msg = re.sub(r'{alt}',str(self.order.alt or ''),msg)
        msg = re.sub(r'{cirt}',self.order.cirt or '',msg)
        msg = re.sub(r'{cirw}',self.order.cirw or '',msg)
        msg = re.sub(r'{num}',str(self.order.number or ''),msg)
        msg = re.sub(r'{freq}',str(self.order.freq or ''),msg)
        msg = re.sub(r'{conn}',str(self.order.atc or ''),msg)
        msg = re.sub(r'{park}',str(self.order.park or ''),msg)
        msg = re.sub(r'{parkn}',str(self.order.parkn or ''),msg)
        if self.order.number:
            msg = re.sub(r'{onum}',', number %s' % self.order.number,msg)
        if self.order.lnup:
            msg = re.sub(r'{lineup}',' and line up',msg)
        if self.order.hld:
            msg = re.sub(r'{hld}',' and hold',msg)
        if self.order.short:
            msg = re.sub(r'{short}',' short',msg)
        if self.order.park:
            try:
                startup = StartupLocation.objects.get(pk=self.order.park)
                msg = re.sub(r'{park}',startup.name.replace("_"," "),msg)
            except StartupLocation.DoesNotExist:
                pass
        if self.order.qnh:
            msg = re.sub(r'{qnh}','. QNH %s' % say_number(self.order.qnh),msg)

        # Clean up tags not replaced
        msg = re.sub(r'{\w+}','',msg)
        msg += ", %s" % short_callsign(self.handler.aircraft.callsign)
        req = self.handler.new_request('roger')
        req.laor= self.order.ord
        llogger.debug("readback: %s | %s" % (req,msg))
        self.send_request(req)
        self.handler.messages.append(msg)
        self.done = True
    
class TuneInAction(Action):
    
    def __init__(self, handler, freq):
        Action.__init__(self, handler)
        if freq:
            comm =self.handler.get_comm_by_freq(self.handler.airport(),freq)
        elif self.handler.plane.state in ['stopped','starting','pushback','taxiing']:
            comm = self.handler.get_comm_by_type(self.handler.airport(),Comm.GND)
        elif self.handler.plane.is_approaching():
            comm = self.handler.get_comm_by_type(self.handler.airport(),Comm.APP)
        else:
            comm = self.handler.get_comm_by_type(self.handler.airport(),Comm.TWR)
        self.freq = comm.frequency
        self.controller = comm.identifier
        
    def execute(self):
        print("TUNEIN",self.handler.controller)
        self.handler.freq=self.freq
        
        req = self.new_request(alias.TUNE_IN)
        req.freq=self.freq
        
        self.send_request(req)
        self.sent=sim_time()
    
    def is_ready(self):
        return not hasattr(self, 'sent')
    
    def is_done(self):
        return self.handler.controller == self.controller

class ReadyTaxiAction(Action):
    
    def execute(self):
        print("{%s-CP} ReadyTaxiAction: requesting taxi clearance" % self.handler.aircraft)
        req = self.new_request(alias.TAXI_READY)
        self.send_request(req,True)
        self.done = True

class RunwayAction(Action):
    ''' Base clas for actions with runway '''
    
    def __init__(self, handler, runway):
        Action.__init__(self, handler)
        self.runway = runway
    
    def get_request_type(self):
        ''' subclasses must implement'''
        return None
    
    def execute(self):
        print("{%s-CP} RunwayAction: reporting %s on runway %s" % (self.handler.aircraft, self.get_request_type(),self.runway,))
        req = self.handler.new_request(self.get_request_type())
        req.rwy = self.runway
        self.send_request(req, True)
        self.done = True

class CrossRunwayAction(RunwayAction):
    
    def get_request_type(self):
        return alias.CROSS_RUNWAY
        
class HoldingShortAction(RunwayAction):
    
    def get_request_type(self):
        return alias.HOLDING_SHORT

class ReadyTakeoffAction(RunwayAction):
    
    def get_request_type(self):
        return alias.READY_TAKEOFF
    
class LeavingAction(RunwayAction):
    
    def get_request_type(self):
        return alias.LEAVING

class ClearedRunwayAction(RunwayAction):
    
    def get_request_type(self):
        return alias.CLEAR_RUNWAY

class RequestInboundAction(Action):
    
    def execute(self):
        print("{%s-CP} RequestInboundAction: requesting inbound approach" % self.handler.aircraft)
        req = self.new_request(alias.INBOUND_APPROACH)
        req.icao = self.handler.icao
        self.send_request(req, True)
        self.done = True

class ReportCircuitAction(Action):
    
    def __init__(self, handler, report,runway=None):
        Action.__init__(self, handler)
        self.report = report
        self.runway = runway

    def execute(self):
        req = self.new_request(self.report)
        req.rwy = self.runway
        req.cirw = self.report
        self.send_request(req, True)
        self.done = True 

class RequestParkAction(Action):
    def execute(self):
        req = self.new_request('park')
        self.send_request(req, True)
        self.done = True
