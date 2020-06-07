'''
Created on 31/07/2015

@author: julio
'''
from fgserver.atc.models import Tag
from fgserver.models import Order, Comm, Request, Cache
from django.utils import timezone
from fgserver.messages import alias
from fgserver.ai.planes import PlaneInfo
from random import randint
from fgserver import get_qnh, units, get_controllers, setInterval,\
    get_metar_cycle
from fgserver.helper import get_distance, get_heading_to, angle_diff, get_heading_to_360
import time
import threading
from fgserver.atc.functions import get_message
import logging
from datetime import timedelta
from django.utils.module_loading import import_string
from django.conf import settings
from fgserver.ai.common import PlaneInfo
import uuid
from requests.models import Response
import redis
import pickle

llogger = logging.getLogger(__name__)

class Controller(object):
    comm=None
    last_order_date=None
    _runway_boundaries = None
    master=None
    
    def __init__(self,comm):
        self.comm = comm
        self.configure()
        llogger.debug("Controller type %s for %s created" % (type(self).__name__, comm))
    
    
    def configure(self):
        ''' Called from init. Subclasses can implement it '''
        pass
                    
    def check_waiting(self):
        # expire tags:
#         expired = timezone.now() - timedelta(minutes=10)
#         self.comm.airport.tags.filter(status__gt=0,status_changed__lt=expired).update(status=0,number=0)
        
        landing = self.comm.airport.tags.filter(status=PlaneInfo.LANDING)
        lined = self.comm.airport.tags.filter(status__in=(PlaneInfo.LINED_UP, PlaneInfo.DEPARTING))
        short = self.comm.airport.tags.filter(status=PlaneInfo.SHORT).order_by('number')
        lining = self.comm.airport.tags.filter(status=PlaneInfo.LINING_UP)
        holding = self.comm.airport.tags.filter(status=PlaneInfo.HOLD)
        crossing = self.comm.airport.tags.filter(status=PlaneInfo.CROSS)
        
        runway = self.active_runway()
        self.debug("check_waiting:",landing,lined,short,lining)
        if lined.count():
            '''there's someone taking-off'''
            for ll in lined.all():
                a = ll.aircraft
                if not runway.on_runway(a.get_position()):
                    ''' nop, there isn't'''
                    llogger.info("Aircraft %s not in runway. removing LINED_UP state" % a)
                    self.set_status(a, 0, 0)
#                     return self.check_waiting() #check again
            if landing.count():
                l = landing.first().aircraft
                request = Request(sender=l,date=timezone.now(),request="req=go_around;apt=%s"%self.airport.icao)
                response = self.manage(request)
                response.save()
        elif landing.count():
            '''there's someone landing and no one departing'''
            for ll in landing.all():
                l = landing.first().aircraft
                #print("Landing?",l.get_position(),runway.get_position(),runway.bearing)
                dist = get_distance(l.get_position(),runway.get_position())
                head = get_heading_to_360(l.get_position(),runway.get_position())
                adiff = angle_diff(head, float(runway.bearing))
                # TODO: Make this values configurables.
                if dist > 5*units.NM or adiff > 20 :
                    ''' nop, he isn't'''
                    self.debug("acft is not on landing path. removing LANDING state",l,dist, head,l.heading, adiff)
                    self.set_status(l,0,0)
                    #return self.check_waiting() #check again
            
        elif holding.count():
            for s in holding.all():
                s = holding.first()
                self.debug("Cross number",s.number)
                self.debug('No one landing and no one departing, let %s cross the runway. %s,%s' % (s,s.id,s.number))
                '''No one landing and no one departing, let them cross the runway '''
                last_r=s.aircraft.requests.filter(request__contains=alias.CROSS_RUNWAY).last()
                self.manage(last_r)
        elif short.count() and not lining.count():
            s = short.first()
            self.debug("Short number",s.number)
            if s.number:
                s.number=0
                s.save()
                self.debug('No one landing and no one departing, let %s take off. %s,%s' % (s,s.id,s.number))
                '''No one landing and no one departing, let them take off'''
                last_r=s.aircraft.requests.filter(request__contains="holdingshort").last()
                self.manage(last_r)
        
            
    def log(self,*argv):
        msg = "[%s]" % self.comm
        for arg in argv:
            msg += " %s" % arg
        llogger.info(msg)
        
    def debug(self,*argv):
        msg = "[%s]" % self.comm
        for arg in argv:
            msg += " %s" % arg
        llogger.debug(msg)
        

    def active_runway(self):
        return self.comm.airport.active_runway()
    def rwy_name(self):
        return self.comm.airport.active_runway().name
        
    def manages(self,req):
        # TODO: possible security leak?. A plane can issue a request with '__init__', or destroy. 
        #print("MANAGES",req,hasattr(self,req),self)
        return req and hasattr(self,req)
    
    def find_controller(self,request):
        css = get_controllers(request.receiver.airport)
        req = request.get_request().req
        for c in css:
            if c.manages(req):
                return c
        return None
    
    def get_tag(self,aircraft):
        tag,created = Tag.objects.get_or_create(airport=self.comm.airport,aircraft=aircraft)
        if created:
            self.debug(": Controller tag created for %s " % aircraft)
        return tag
    
    def set_status(self,aircraft,status,number=None):
        tag,created = Tag.objects.get_or_create(aircraft=aircraft,airport=self.comm.airport)
        #print("%s changing status of %s from %s to %s" % (self.comm,aircraft, PlaneInfo.label(tag.status),PlaneInfo.label(status) ) )
        tag.status=str(status)
        if number != None:
            tag.number=number
        tag.save()
        if created:
            self.debug("created", tag)
        return tag

    def _init_response(self,request):
        order = Order(sender=self.comm,receiver=request.sender,date=timezone.now())
        order.add_param(Order.PARAM_AIRPORT,self.comm.airport.icao)
        order.add_param(Order.PARAM_RECEIVER,request.sender.callsign)
        #self.debug("init response devuelve",order)
        return order
    
    def manage(self,request):
        req = request.get_request().req
        response = None
        if self.manages(req):
            handler = getattr(self, req)
            response = handler(request)
            #check_waiting(self) 
        else:
            self.debug("Rerouting request %s" % request)
            response= self.reroute(request)
        
        if isinstance(response, Order):
                response.save()
                self.debug("Order saved",response)
        return response
    
    def reroute(self,request):
        c = self.find_controller(request)
        self.debug("reroute: controller=%s" % c)
        if c:
            response=self._init_response(request)
            response.add_param(Order.PARAM_ORDER,alias.TUNE_TO)
            self.pass_control(response, c)
            response.message=get_message(response)
            return response
    
    def pass_control(self,response,controller):
        if not self.master:
            response.add_param(Order.PARAM_FREQUENCY,controller.comm.get_FGfreq())
            response.add_param(Order.PARAM_CONTROLLER,controller.comm.identifier)
        
    def roger(self,request):
        tag=self.get_tag(request.sender)
        tag.ack_order=request.get_request().laor
        tag.save()
        order = tag.aircraft.orders.filter(received=True).last()
        if order.get_instruction() == tag.ack_order:
            self.debug("Orden %s acked" % order)
            order.acked = True
            order.save()
        
    def tunein(self,request):
        response=self._init_response(request)
        response.message = ""
        response.add_param(Order.PARAM_CONTROLLER,self.comm.identifier)
        response.add_param(Order.PARAM_ORDER, alias.TUNE_OK)
        self.set_status(request.sender, PlaneInfo.TUNNED)
        return response
    
    def reset(self,request):
        # TODO: Eeeewwww! change this!
        Order.objects.filter(receiver=request.sender, received=False).update(expired=True,lost=True)
        
    def repeat(self,request):
        order = Order.objects.filter(receiver=request.sender).exclude(sent_date=None).order_by('-date').first()
        response=self._init_response(request)
        rep = order.get_param(Order.PARAM_REPEAT,0) +1
        response._order = order._order
        response.add_param(Order.PARAM_REPEAT, rep)
        if rep > 1:
            response.message = order.message.replace(', I say again','')
        else:
            response.message = order.message.replace(',', ', I say again,',1)
        return response

    def check_atis(self,request, response):
        if request.get_param(Order.PARAM_ATIS) :
            atis = request.get_param(Order.PARAM_ATIS)
            cycle = get_metar_cycle(self.comm.airport)
            self.debug("ATIS: plane:%s, airport: %s" % (atis,cycle,))
            if cycle != atis:
                response.add_param(Order.PARAM_ATIS, atis)
        else:
            response.add_param(Order.PARAM_QNH, str(get_qnh(self.comm.airport)))

    def __unicode__(self):
        return '%s for %s' % (type(self).__name__, self.comm)
    
    def __str__(self):
        return str(self.__unicode__())
    
class Ground(Controller):
    def readytaxi(self,request):
        response=self._init_response(request)
        response.add_param(Order.PARAM_ORDER,'taxito')
        response.add_param(Order.PARAM_RUNWAY,self.rwy_name())
        twr = get_controllers(self.comm.airport, Comm.TWR)[0]
        self.pass_control(response, twr)
        count = self.comm.airport.tags.filter(status__in=(PlaneInfo.SHORT,PlaneInfo.TAXIING,)).count()
        count_others = self.comm.airport.tags.filter(status__in=[PlaneInfo.LINED_UP,PlaneInfo.LINING_UP, PlaneInfo.DEPARTING,PlaneInfo.LANDING, PlaneInfo.CIRCUIT_FINAL, PlaneInfo.CIRCUIT_BASE,PlaneInfo.CIRCUIT_DOWNWIND]).count()
        self.debug("readytaxi",count,count_others)
        if not self.master or count or count_others:
            response.add_param(Order.PARAM_HOLD, 1)
            response.add_param(Order.PARAM_SHORT, 1)
            num = count
            self.set_status(request.sender, PlaneInfo.TAXIING,num)
        else:
            response.add_param(Order.PARAM_LINEUP,1)
            num = 0
            self.set_status(request.sender, PlaneInfo.LINING_UP,num)
            
        response.add_param(Order.PARAM_NUMBER, num+1)
        response.message=get_message(response)
        
        return response
        
    def startup(self,request):
        response=self._init_response(request)
        response.add_param(Order.PARAM_ORDER, alias.STARTUP)
        self.check_atis(request, response)
        response.message=get_message(response)
        self.set_status(request.sender, PlaneInfo.STOPPED)
        return response


class Tower(Controller):
    
    
    def __unicode__(self):
        return '%s for %s' % (type(self).__name__, self.comm)

    def configure(self):
        Controller.configure(self)
        self.debug("creating helpers...")
        self.helpers=[]
        self.helpers.append(Ground(self.comm))
        self.helpers.append(Departure(self.comm))
        self.helpers.append(Approach(self.comm))
        for h in self.helpers:
            h.master=self
            
    def manage(self, request):
        if Controller.manage(self, request):
            return True
        self.debug("Trying with helpers")
        for c in self.helpers:
            if c.manages(request.get_request().req):
                self.debug("Helper found: %s " % c )
                return c.manage(request)
        return False

    def clearrw(self,request):
        response=self._init_response(request)
        tag = self.get_tag(request.sender)
        if int(tag.status) == PlaneInfo.CROSS:
            self.set_status(request.sender, PlaneInfo.TAXIING)
            last_r=request.sender.requests.filter(request__contains=alias.TAXI_READY).last()
            controller = Controllers.get_controller(last_r.receiver)
            return controller.manage(last_r)
        else:
            response.add_param(Order.PARAM_ORDER, alias.TAXI_PARK)
            pk = self.comm.airport.startups.filter(aircraft=request.sender).first()
            if not pk:
                pk=self.comm.airport.startups.filter(aircraft=None).order_by('?').first()
                pk.aircraft=request.sender
                pk.save()
                
            response.add_param(Order.PARAM_PARKING, pk.id)
            response.add_param(Order.PARAM_PARKING_NAME, pk.name)
            response.message=get_message(response)
            self.set_status(request.sender, PlaneInfo.PARKING)
            return response
    
    def crossrwy(self,request):
        response=self._init_response(request)
        
        rwy = request.get_param(Order.PARAM_RUNWAY)
        response.add_param(Order.PARAM_RUNWAY,rwy)
        count_others = self.comm.airport.tags.filter(status__in=[PlaneInfo.LINING_UP,PlaneInfo.LINED_UP, PlaneInfo.DEPARTING,PlaneInfo.LANDING,PlaneInfo.CIRCUIT_FINAL,PlaneInfo.LANDING,PlaneInfo.CIRCUIT_BASE]).exclude(aircraft=request.sender).count()
        if count_others:
            response.add_param(Order.PARAM_ORDER, alias.WAIT)
            response.add_param(Order.PARAM_HOLD, alias.CROSS_RUNWAY)
            self.set_status(request.sender, PlaneInfo.HOLD)
        else:
            response.add_param(Order.PARAM_ORDER, alias.CLEAR_CROSS_RUNWAY)
            self.set_status(request.sender, PlaneInfo.CROSS,0)
        response.message=get_message(response)
        return response
            
    def holdingshort(self,request):
        response=self._init_response(request)
        response.add_param(Order.PARAM_RUNWAY,self.rwy_name())
        count = self.comm.airport.tags.filter(status=PlaneInfo.SHORT).exclude(aircraft=request.sender).count()
        others = self.comm.airport.tags.filter(status__in=[PlaneInfo.LINING_UP,PlaneInfo.LINED_UP, PlaneInfo.DEPARTING,PlaneInfo.LANDING,PlaneInfo.CIRCUIT_FINAL,PlaneInfo.LANDING,PlaneInfo.CIRCUIT_BASE]).exclude(aircraft=request.sender)
        count_others = others.count()
        tag = self.get_tag(request.sender)
        self.set_status(request.sender, PlaneInfo.SHORT,count)
        self.debug("holdingshort %s %s  %s %s %s: %s" % (count_others,count,tag, tag.id,tag.number, [x for x in others]) )
        if count_others or (tag.number and count) :
            response.add_param(Order.PARAM_ORDER, alias.WAIT)
            response.add_param(Order.PARAM_HOLD, 1)
            response.add_param(Order.PARAM_SHORT, 1)
            response.add_param(Order.PARAM_NUMBER, count+count_others+1)
            tag = self.set_status(request.sender, PlaneInfo.SHORT,count+count_others)
            self.debug("Aircraft  %s must wait short. number=%s" % (response.receiver, tag.number))
        elif randint(0,3)==1:
            response.add_param(Order.PARAM_ORDER, alias.LINEUP)
            response.add_param(Order.PARAM_HOLD, 1)
            response.add_param(Order.PARAM_NUMBER, 1)
            response.add_param(Order.PARAM_LINEUP, 1)
            self.set_status(request.sender, PlaneInfo.LINING_UP,0)
        else:
            response.add_param(Order.PARAM_ORDER, alias.CLEAR_TK)
            response.add_param(Order.PARAM_NUMBER, 1)
            self.set_status(request.sender, PlaneInfo.LINING_UP,0)
        response.message=get_message(response)
        request.sender.startup_location.update(aircraft=None)
        return response
    
    def readytko(self,request):
        response=self._init_response(request)
        response.add_param(Order.PARAM_RUNWAY,self.rwy_name())
        response.add_param(Order.PARAM_ORDER, alias.CLEAR_TK)
        response.message=get_message(response)
        self.set_status(request.sender, PlaneInfo.LINED_UP)
        request.sender.startup_location.update(aircraft=None)
        return response
    
    def leaving(self,request):
        response=self._init_response(request)
        response.add_param(Order.PARAM_ORDER,alias.SWITCHING_OFF)
        response.message=get_message(response)
        self.set_status(request.sender, PlaneInfo.CLIMBING)
        return response
    
    def _circuiters(self):
            tags = self.comm.airport.tags.filter(status__in=[PlaneInfo.LANDING,PlaneInfo.CIRCUIT_FINAL,PlaneInfo.CIRCUIT_STRAIGHT,PlaneInfo.CIRCUIT_BASE,PlaneInfo.CIRCUIT_DOWNWIND,PlaneInfo.CIRCUIT_CROSSWIND,]).order_by('-status','status_changed')
            return [x.aircraft for x in tags]
        
    def _report_circuit(self,request,cur_circuit,report_circuit,number=None):
        response=self._init_response(request)
        response.add_param(Order.PARAM_ORDER,alias.REPORT_CIRCUIT)
        response.add_param(Order.PARAM_CIRCUIT_WP,report_circuit)
        self.set_status(request.sender, cur_circuit)
        try:
            number = self._circuiters().index(request.sender)
            response.add_param(Order.PARAM_NUMBER,number+1)
        except:
            pass
        response.message=get_message(response)
        self.set_status(request.sender, cur_circuit, number)
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
        lined = self.comm.airport.tags.filter(status__in=[PlaneInfo.LINED_UP, PlaneInfo.LINING_UP]).count()
        landing = self.comm.airport.tags.filter(status=PlaneInfo.LANDING).count()
        self.debug("final lined=%s landing=%s" % (lined,landing,))
        if lined or landing:
            response.add_param(Order.PARAM_ORDER,alias.GO_AROUND)
            response.add_param(Order.PARAM_CIRCUIT_WP,alias.CIRCUIT_BASE)
            self.set_status(request.sender, PlaneInfo.APPROACHING)
        else:
            tgo = request.get_param(alias.CIRCUIT_TNGO)
            if tgo:
                response.add_param(Order.PARAM_ORDER,alias.CLEAR_TOUCHNGO)
            else:
                response.add_param(Order.PARAM_ORDER,alias.CLEAR_LAND)
            #response.add_param(Order.PARAM_NUMBER,landing+1)
            response.add_param(Order.PARAM_RUNWAY,self.rwy_name())
            self.check_atis(request, response)
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
        count = self.comm.airport.tags.filter(status=PlaneInfo.SHORT).count()
        count_others = self.comm.airport.tags.filter(status__in=[PlaneInfo.LINING_UP,PlaneInfo.LINED_UP,PlaneInfo.LANDING]).count()
        self.debug("readytaxi",count,count_others)
        if count or count_others:
            response.add_param(Order.PARAM_HOLD, 1)
            response.add_param(Order.PARAM_SHORT, 1)
            num = count +1
            self.set_status(request.sender, PlaneInfo.TAXIING,num)
        else:
            response.add_param(Order.PARAM_LINEUP,1)
            self.set_status(request.sender, PlaneInfo.LINING_UP,0)
            
        response.add_param(Order.PARAM_NUMBER, num)
        response.message=get_message(response)
        
        return response

    def startup(self,request):
        response=self._init_response(request)
        response.add_param(Order.PARAM_ORDER, alias.STARTUP)
        self.check_atis(request, response)
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
        circp = self.comm.airport.tags.filter(status__in=(PlaneInfo.LANDING,PlaneInfo.CIRCUIT_FINAL,PlaneInfo.CIRCUIT_BASE,PlaneInfo.CIRCUIT_DOWNWIND,PlaneInfo.CIRCUIT_CROSSWIND,PlaneInfo.CIRCUIT_STRAIGHT)).exclude(aircraft__callsign=request.sender.callsign).count()
        ph = get_heading_to(request.sender.get_position(),self.active_runway().get_position())
        s = angle_diff(ph,float(self.active_runway().bearing))
        self.debug("circp=%s, ph=%s, s=%s" % (circp,ph,s))
        if circp or s > 40:
            # other planes in circuit or not straight of rwy, must join.
            response.add_param(Order.PARAM_ORDER, alias.JOIN_CIRCUIT)
            response.add_param(Order.PARAM_CIRCUIT_TYPE, self.circuit_type)
            response.add_param(Order.PARAM_CIRCUIT_WP,[alias.CIRCUIT_CROSSWIND,alias.CIRCUIT_DOWNWIND][randint(0,1)])
        else:
            llogger.info("[%s] straight landing for %s(%s) because of angle %s" % (self.comm,request.sender,request.sender.get_position(),s))
            response.add_param(Order.PARAM_ORDER, alias.CIRCUIT_STRAIGHT)
            response.add_param(Order.PARAM_CIRCUIT_WP,alias.CIRCUIT_FINAL)
        response.add_param(Order.PARAM_RUNWAY,self.rwy_name())
        response.add_param(Order.PARAM_ALTITUDE,str(self.circuit_alt) )
        self.check_atis(request, response)
        twr = get_controllers(self.comm.airport, Comm.TWR)[0]
        self.pass_control(response, twr)
        response.message=get_message(response)        
        self.set_status(request.sender, PlaneInfo.APPROACHING)
        return response
    
    def withyou(self,request):
        return self.inbound(request)

class Controllers(Cache):
    
    @classmethod
    def check(cls):
        super(Controllers, cls).check()
        if not hasattr(cls, 'started'):
            llogger.debug("Starting check_waiting")
            cls.started = True
            check_waiting()
    
    @classmethod
    def get_controller(cls, comm):
        controller =  cls.get(comm.id)
        if not controller:
            try:
                llogger.debug("Creating controller for %s" % comm)
                clazz = import_string(settings.DEFAULT_CONTROLLERS.get(comm.type))
                llogger.debug("class=%s" % clazz)
                controller = clazz(comm)
                cls.set(comm.id,controller)
            except:
                llogger.exception("Error al crerar un controller para %s" % comm)
        return controller

@setInterval(30)
def check_waiting():
    #llogger.debug("CHECK_WAITING" )
    for controller in Controllers.values():
        if isinstance(controller, Tower):
            controller.check_waiting()
    #llogger.debug("END CHECK_WAITING")

def process_request(sender, instance, **kwargs):
    if instance.receiver and instance.received and not instance.processed:
        llogger.debug("Processing request %s " % instance)
#         Requests.set(instance)
        controller = Controllers.get_controller(instance.receiver)
        if controller:
            llogger.debug("Controllers: %s" % [str(x) for x in Controllers.values()])
            controller.manage(instance)
            instance.processed=True
            instance.save()

def publish_request(sender, instance, **kwargs):
    print("PUBLISHING REQUEST",instance)
    Requests.set(instance)

class Requests():
    
    CHANNEL = 'requests'
    
    @classmethod
    def check(cls):
        if not hasattr(cls, 'thread'):
            cls.listeners = []
            cls.server = redis.Redis()
            cls.thread = threading.Thread(target=cls.loop)
            cls.thread.start()
        
    @classmethod
    def set(cls,instance):
        cls.check()
        pickled = pickle.dumps(instance)
        cls.server.publish(cls.CHANNEL, pickled)
    
    @classmethod
    def listen(cls,callback):
        cls.check()
        cls.listeners.append(callback)
    
    @classmethod
    def loop(cls):
        p = cls.server.pubsub()
        p.subscribe(cls.CHANNEL)
        for new_message in p.listen():
            if new_message.get('type',None) == 'message':
                request = pickle.loads(new_message.get('data'))
                #print("new posmsg",str(pos))
                for c in cls.listeners:
                    try:
                        c(request)
                    except:
                        llogger.exception("Calling callback %s with %s" % (c,request,))



    

