'''
Created on 31/07/2015

@author: julio
'''
import fgserver
from fgserver.atc.models import Tag
from fgserver.models import Order, Comm, Request
from django.utils import timezone
from fgserver.messages import alias
from fgserver.ai import PlaneInfo
from random import randint
from fgserver.atc import get_message
from fgserver import get_qnh, units, llogger, get_controllers
from math import sqrt, atan
from fgserver.helper import normalize, move, point_inside_polygon, get_distance,\
    get_heading_to, angle_diff
from datetime import timedelta
from pip._vendor.requests.models import Response

class Controller(object):
    comm=None    
    last_order_date=None
    runway_boundaries = ()
    
    def __init__(self,comm):
        self.comm = comm
        self.configure()
        llogger.info("Controller type %s for %s created" % (type(self).__name__, comm))
    
    
    def configure(self):
        ''' Called from init. Subclasses can implement it '''
        pass
    
    def runway_boundaries(self):        
        if self._runway_boundaries:
            return self._runway_boundaries
        runway = self.active_runway()
        w2= runway.width*units.FT/2
        l2= runway.length*units.FT/2
        bearing = float(runway.bearing)
        pos = runway.get_position()
        cat = sqrt(w2 * w2+l2*l2)
        alpha = atan(w2/l2)*units.RAD
        #self.log(l2,w2,cat,alpha)
        angles = []
        angles.append(normalize(bearing + alpha)) # front right
        angles.append(normalize(bearing - alpha))
        angles.append(normalize(bearing + alpha -180 ))
        angles.append(normalize(bearing - alpha -180 ))
        #self.log("runway angles", angles)        
        self._runway_boundaries=[]
        for angle in angles:
            p = move(pos, angle, cat, pos.z)
            self._runway_boundaries.append((p.x,p.y))
        self.log("RWY boundaries",self._runway_boundaries)
        return self._runway_boundaries

    def on_runway(self,aircraft):
        pos = aircraft.get_position()
        return point_inside_polygon(pos.x,pos.y,self.runway_boundaries())
                
    def check_waiting(self):
        landing = self.comm.tags.filter(status=PlaneInfo.LANDING)
        lined = self.comm.tags.filter(status=PlaneInfo.LINED_UP)
        short = self.comm.tags.filter(status=PlaneInfo.SHORT)
        runway = self.active_runway()
        self.log("check_waiting:",landing,lined,short)
        if lined.count():
            '''there's someone taking-off'''
            for ll in lined.all():
                a = ll.aircraft
                if not self.on_runway(a):
                    ''' nop, there isn't'''
                    self.log("acft not in runway. removing LINED_UP state",a)
                    self.set_status(a, 0, 0)
                    return self.check_waiting() #check again
            if landing.count():
                l = landing.first().aircraft
                request = Request(sender=l,date=timezone.now(),request="req=go_around;apt=%s"%self.airport.icao)
                response = self.manage(request)
                response.save()
        elif landing.count():
            '''there's someone landing and no one departing'''
            for ll in landing.all():
                l = landing.first().aircraft
                dist = get_distance(l.get_position(),runway.get_position())
                head = get_heading_to(l.get_position(),runway.get_position())
                adiff = angle_diff(head, - l.heading)
                if dist > 1*units.NM or adiff > 5 :
                    ''' nop, he isn't'''
                    self.log("acft not in runway. removing LINED_UP state",l)
                    self.set_status(l,0,0)
                    return self.check_waiting() #check again
        elif short.count():
            s = short.first()
            self.log("Short number",s.number)
            if s.number > 1:
                s.number=1
                s.save()
                '''No one landing and no one departing, let them take off'''
                self.manage(s.aircraft.requests.all().last())    
    def log(self,*argv):
        fgserver.info(self.comm,*argv)

    def active_runway(self):
        return self.comm.airport.active_runway()
    def rwy_name(self):
        return self.comm.airport.active_runway().name
        
    def next_order_date(self):
        d=timezone.now()
        if self.last_order_date:
            d = max([self.last_order_date,d])
        self.last_order_date= d + timedelta(seconds=randint(5,12))
        #print "LAST ORDER DATE",self.last_order_date
        return self.last_order_date
    
    def manages(self,req):
        # TODO: possible security leak?. A plane can issue a request with '__init__', or destroy. 
        return req and hasattr(self,req)
    
    def find_controller(self,request):
        css = get_controllers(request.receiver.airport)
        req = request.get_request().req
        for c in css:
            if c.manages(req):
                return c
        return None
    
    def get_tag(self,aircraft):
        tag,created = Tag.objects.get_or_create(comm=self.comm,aircraft=aircraft)
        if created:
            self.log(": Controller tag created for %s " % aircraft)
        return tag
    
    def set_status(self,aircraft,status,number=None):
        tag,created = Tag.objects.get_or_create(aircraft=aircraft,comm=self.comm)
        tag.status=str(status)
        if number != None:
            tag.number=number
        tag.save()
        if created:
            self.log("created", tag)

    def _init_response(self,request):
        order = Order(sender=self.comm,receiver=request.sender,date=self.next_order_date())
        order.add_param(Order.PARAM_AIRPORT,self.comm.airport.icao)
        order.add_param(Order.PARAM_RECEIVER,request.sender.callsign)
        #self.log("init response devuelve",order)
        return order
    
    def manage(self,request):
        req = request.get_request().req
        if self.manages(req):
            handler = getattr(self, req)
            response = handler(request)    
        else:
            self.log("Rerouting request")
            response= self.reroute(request)
        if response:
                response.save()
                self.log("Order saved",response)
                return True
        return False
    
    def reroute(self,request):
        c = self.find_controller(request)
        self.log("reroute: controller=%s" % c)
        if c:
            response=self._init_response(request)
            response.add_param(Order.PARAM_ORDER,alias.TUNE_TO)
            self.pass_control(response, c)
            response.message=get_message(response)
            return response
    
    def pass_control(self,response,controller):
        response.add_param(Order.PARAM_FREQUENCY,controller.comm.get_FGfreq())
        response.add_param(Order.PARAM_CONTROLLER,controller.comm.identifier)
        
    def roger(self,request):
        tag=self.comm.tags.get(aircraft=request.sender)
        tag.ack_order=request.get_request().laor
        tag.save()
        
    def tunein(self,request):
        response=self._init_response(request)
        response.date = timezone.now() # inmediate
        response.message = ""
        response.add_param(Order.PARAM_CONTROLLER,self.comm.identifier)
        response.add_param(Order.PARAM_ORDER, alias.TUNE_OK)
        self.set_status(request.sender, PlaneInfo.TUNNED)
        return response
    
    def reset(self,request):
        # TODO: Eeeewwww! change this!
        Order.objects.filter(receiver=request.sender, confirmed=True).update(confirmed=False)
        
    def repeat(self,request):
        order = Order.objects.filter(receiver=request.sender, confirmed=True).order_by('-date').first()
        response=self._init_response(request)
        rep = order.get_param(Order.PARAM_REPEAT,0) +1
        response._order = order._order
        response.add_param(Order.PARAM_REPEAT, rep)
        if rep > 1:
            response.message = order.message.replace(', I say again','')
        else:
            response.message = order.message.replace(',', ', I say again,',1)
        return response

    def __unicode__(self):
        return '%s for %s' % (type(self).__name__, self.comm)
    
    def __str__(self):
        return self.__unicode__().encode('utf-8')
    
class Ground(Controller):
    def readytaxi(self,request):
        response=self._init_response(request)
        response.add_param(Order.PARAM_ORDER,'taxito')
        response.add_param(Order.PARAM_RUNWAY,self.rwy_name())
        twr = get_controllers(self.comm.airport, Comm.TWR)[0]
        self.pass_control(response, twr)
        count = self.comm.tags.filter(status=PlaneInfo.SHORT).count()
        count_others = self.comm.tags.filter(status__in=[PlaneInfo.LINED_UP,PlaneInfo.LANDING]).count()
        self.log("readytaxi",count,count_others)
        if count or count_others:
            response.add_param(Order.PARAM_HOLD, 1)
            response.add_param(Order.PARAM_SHORT, 1)
            num = count +1
        else:
            response.add_param(Order.PARAM_LINEUP,1)
            num = 1
            
        response.add_param(Order.PARAM_NUMBER, num)
        response.message=get_message(response)
        self.set_status(request.sender, PlaneInfo.TAXIING,num)
        return response

    def startup(self,request):
        response=self._init_response(request)
        response.add_param(Order.PARAM_ORDER, alias.STARTUP)
        response.add_param(Order.PARAM_QNH, str(get_qnh(self.comm.airport)))
        response.message=get_message(response)
        self.set_status(request.sender, PlaneInfo.STOPPED)
        return response


class Tower(Controller):
    
    
    def __unicode__(self):
        return '%s for %s' % (type(self).__name__, self.comm)

    def configure(self):
        Controller.configure(self)
        self.log("creating helpers...")
        self.helpers=[]
        self.helpers.append(Ground(self.comm))
        self.helpers.append(Departure(self.comm))
        self.helpers.append(Approach(self.comm))
    
    def manage(self, request):
        if Controller.manage(self, request):
            return True
        self.log("Trying with helpers")
        for c in self.helpers:
            if c.manages(request.get_request().req):
                self.log("Helper found: %s " % c )
                return c.manage(request)
        return False

    def holdingshort(self,request):
        response=self._init_response(request)
        response.add_param(Order.PARAM_RUNWAY,self.rwy_name())
        count = self.comm.tags.filter(status=PlaneInfo.SHORT).exclude(aircraft=request.sender).count()
        count_others = self.comm.tags.filter(status__in=[PlaneInfo.LINED_UP,PlaneInfo.LANDING]).exclude(aircraft=request.sender).count()
        self.set_status(request.sender, PlaneInfo.SHORT,count)
        tag = self.get_tag(request.sender)
        
        if count_others or (tag.number > 1 and count) :
            response.add_param(Order.PARAM_ORDER, alias.WAIT)
            response.add_param(Order.PARAM_HOLD, 1)
            response.add_param(Order.PARAM_SHORT, 1)
            response.add_param(Order.PARAM_NUMBER, count+count_others+1)
            self.set_status(request.sender, PlaneInfo.SHORT,count+count_others+1)
        elif randint(0,2)==1:
            response.add_param(Order.PARAM_ORDER, alias.LINEUP)
            response.add_param(Order.PARAM_HOLD, 1)
            response.add_param(Order.PARAM_NUMBER, 1)
            response.add_param(Order.PARAM_LINEUP, 1)
        else:
            response.add_param(Order.PARAM_ORDER, alias.CLEAR_TK)
            response.add_param(Order.PARAM_NUMBER, 1)
        response.message=get_message(response)
        return response
    
    def readytko(self,request):
        response=self._init_response(request)
        response.add_param(Order.PARAM_RUNWAY,self.rwy_name())
        response.add_param(Order.PARAM_ORDER, alias.CLEAR_TK)
        response.message=get_message(response)
        self.set_status(request.sender, PlaneInfo.LINED_UP)
        return response
    
    def leaving(self,request):
        response=self._init_response(request)
        response.add_param(Order.PARAM_ORDER,alias.SWITCHING_OFF)
        response.message=get_message(response)
        self.set_status(request.sender, PlaneInfo.CLIMBING)
        return response
    
    def _report_circuit(self,request,cur_circuit,report_circuit):
        response=self._init_response(request)
        response.add_param(Order.PARAM_ORDER,alias.REPORT_CIRCUIT)
        response.add_param(Order.PARAM_CIRCUIT_WP,report_circuit)
        count = self.comm.tags.filter(status=cur_circuit).exclude(aircraft__callsign=request.sender.callsign).count()
        response.add_param(Order.PARAM_NUMBER,count+1)
        response.message=get_message(response)
        self.set_status(request.sender, cur_circuit)
        return response

    def crosswind(self,request):
        response=self._report_circuit(request,PlaneInfo.CIRCUIT_CROSSWIND,alias.CIRCUIT_DOWNWIND)
        return response
            
    def downwind(self,request):
        response=self._report_circuit(request,PlaneInfo.CIRCUIT_DOWNWIND,alias.CIRCUIT_BASE)
        return response
        
    def base(self,request):
        response=self._report_circuit(request,PlaneInfo.CIRCUIT_BASE,alias.CIRCUIT_FINAL)
        return response

    def final(self,request):
        response=self._init_response(request)
        lined = self.comm.tags.filter(status=PlaneInfo.LINED_UP).count()
        landing = self.comm.tags.filter(status=PlaneInfo.LANDING).count()
        if lined:
            response.add_param(Order.PARAM_ORDER,alias.GO_AROUND)
            response.add_param(Order.PARAM_CIRCUIT_WP,alias.CIRCUIT_BASE)
            self.set_status(request.sender, PlaneInfo.APPROACHING)
        else:
            response.add_param(Order.PARAM_ORDER,alias.CLEAR_LAND)
            response.add_param(Order.PARAM_NUMBER,landing+1)
            response.add_param(Order.PARAM_RUNWAY,self.rwy_name())
            response.add_param(Order.PARAM_QNH, str(get_qnh(self.comm.airport)))
            self.set_status(request.sender, PlaneInfo.LANDING)
        response.message=get_message(response)
        return response

    def straight(self,request):
        ''' alias for "final" '''
        return self.final(request)

    def go_around(self,request):
        aircraft = request.sender
        response = self._init_response(request)
        response.add_param(Order.PARAM_ORDER,alias.GO_AROUND)
        response.add_param(Order.PARAM_CIRCUIT_WP,alias.CIRCUIT_BASE)
        self.set_status(aircraft, PlaneInfo.APPROACHING)
        response.message=get_message(response)
        return response
    
    def around(self,request):
        response=self._report_circuit(request,PlaneInfo.APPROACHING,alias.CIRCUIT_BASE)
        return response
    
class Departure(Controller):
        
    def readytaxi(self,request):
        response=self._init_response(request)
        response.add_param(Order.PARAM_ORDER,'taxito')
        response.add_param(Order.PARAM_RUNWAY,self.rwy_name())
        count = self.comm.tags.filter(status=PlaneInfo.SHORT).count()
        count_others = self.comm.tags.filter(status__in=[PlaneInfo.LINED_UP,PlaneInfo.LANDING]).count()
        self.log("readytaxi",count,count_others)
        if count or count_others:
            response.add_param(Order.PARAM_HOLD, 1)
            response.add_param(Order.PARAM_SHORT, 1)
            num = count +1
        else:
            response.add_param(Order.PARAM_LINEUP,1)
            num = 1
            
        response.add_param(Order.PARAM_NUMBER, num)
        response.message=get_message(response)
        self.set_status(request.sender, PlaneInfo.TAXIING,num)
        return response

    def startup(self,request):
        response=self._init_response(request)
        response.add_param(Order.PARAM_ORDER, alias.STARTUP)
        response.add_param(Order.PARAM_QNH, str(get_qnh(self.comm.airport)))
        response.message=get_message(response)
        self.set_status(request.sender, PlaneInfo.STOPPED)
        return response
    
    
class Approach(Controller):
    pass_alt = 8000
    circuit_alt= 1000
    circuit_type= alias.CIRCUIT_LEFT
    
    def transition(self,request):
        response=self._init_response(request)
        response.add_param(Order.PARAM_ORDER, alias.CLEAR_CROSS)
        response.add_param(Order.PARAM_ALTITUDE,self.pass_alt )
        response.message=get_message(response)
        self.set_status(request.sender, PlaneInfo.CRUISING)
        return response

    def inbound(self,request):
        response=self._init_response(request)
        response.add_param(Order.PARAM_ORDER, alias.JOIN_CIRCUIT)
        response.add_param(Order.PARAM_RUNWAY,self.rwy_name())
        response.add_param(Order.PARAM_ALTITUDE,str(self.circuit_alt) )
        response.add_param(Order.PARAM_CIRCUIT_TYPE, self.circuit_type)
        response.add_param(Order.PARAM_CIRCUIT_WP,[alias.CIRCUIT_CROSSWIND,alias.CIRCUIT_DOWNWIND][randint(0,1)])
        response.add_param(Order.PARAM_QNH, str(get_qnh(self.comm.airport)))
        twr = get_controllers(self.comm.airport, Comm.TWR)[0]
        self.pass_control(response, twr)
        response.message=get_message(response)        
        self.set_status(request.sender, PlaneInfo.APPROACHING)
        return response
    
    def withyou(self,request):
        return self.inbound(request)
        
