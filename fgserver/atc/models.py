# -*- encoding: utf-8 -*-
from datetime import timedelta
from random import randint

from django.db.models.base import Model
from django.db.models.fields import CharField, IntegerField, DateTimeField
from django.db.models.fields.related import ForeignKey
from django.utils import timezone

from fgserver import units, llogger, get_qnh
import fgserver
from fgserver.ai.planes import PlaneInfo
from fgserver.helper import  get_distance, angle_diff, get_heading_to_360
from fgserver.messages import alias
from fgserver.models import Order, Airport, Aircraft, Request
from model_utils.models import StatusModel
from fgserver.atc.functions import get_message
from django.db import models


class ATC(Model):
    airport = ForeignKey(Airport, on_delete=models.CASCADE, related_name="atc")
    last_order_date = DateTimeField(null=True,blank=True)
    
    def manage(self, request):
        for controller in self.controllers.all().select_subclasses():
            #print "Controller:",type(controller),controller
            try:
                ret = controller.manage(request)
                if ret:
                    ret.save()
                    self.log("Order saved",ret)
                    break
            except:
                llogger.exception("Error processing request : %s" % request)        
        self.check_waiting()

    def active_runway(self):
        return self.airport.active_runway()

    def set_status(self,aircraft,status,number=None):
        tag,created = Tag.objects.get_or_create(aircraft=aircraft,atc=self)
        tag.status=str(status)
        if number != None:
            tag.number=number
        tag.save()
        if created:
            self.log("created", tag)
    
    def check_waiting(self):
        landing = self.tags.filter(status=PlaneInfo.LANDING)
        lined = self.tags.filter(status=PlaneInfo.LINED_UP)
        short = self.tags.filter(status=PlaneInfo.SHORT)
        lining = self.tags.filter(status=PlaneInfo.LINING_UP)
        runway = self.active_runway()
        self.log("check_waiting=",landing,lined,short,lining)
        
        if lined.count():
            '''there's someone taking-off'''
            for ll in lined.all():
                a = ll.aircraft
                if not runway.on_runway(a.get_position()):
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
                head = get_heading_to_360(l.get_position(),runway.get_position())
                adiff = angle_diff(head, - l.heading)
                if dist > 1*units.NM or adiff > 5 :
                    ''' nop, he isn't'''
                    self.log("acft not in landing path. removing LANDING state",l)
                    self.set_status(l,0,0)
                    return self.check_waiting() #check again
        elif short.count() and not lining.count():
            s = short.first()
            self.log("Short number",s.number)
            if s.number > 1:
                s.number=1
                s.save()
                '''No one landing and no one departing, let them take off'''
                self.manage(s.aircraft.requests.all().last())
                
    def log(self,*argv):
        fgserver.info("ATC %s" % self.airport.icao,*argv)
    
    def __unicode__(self):
        try:
            return self.airport.icao.decode()
        except:
            return "%s" % self.airport
    
    def __str__(self):
        return str(self.__unicode__())
    
    def next_order_date(self):
        d=timezone.now()
        if self.last_order_date:
            d = max([self.last_order_date,d])
        self.last_order_date= d + timedelta(seconds=randint(5,12))
        self.save()
        #print "LAST ORDER DATE",self.last_order_date
        return self.last_order_date
                
    def airport_name(self):
        return self.airport.name
    
class Controller(Model):
    atc = ForeignKey(ATC, on_delete=models.CASCADE, related_name="controllers")
    name = CharField(max_length=60,default="Controller")
    
    def log(self,*argv):
        fgserver.info(self.name,*argv)

    def active_runway(self):
        return self.atc.airport.active_runway()
    def rwy_name(self):
        return self.atc.airport.active_runway().name
        
    def manages(self,req):
        # TODO: possible security leak?. A plane can issue a request with '__init__', or destroy. 
        return req and hasattr(self,req)
    
    def get_tag(self,aircraft):
        tag,created = Tag.objects.get_or_create(atc=self.atc,aircraft=aircraft)
        if created:
            print("%s: Controller tag created for %s" % (self.atc,aircraft))
        return tag
    
    def _init_response(self,request):
        order = Order(sender=self.atc.airport,receiver=request.sender,date=self.atc.next_order_date())
        order.add_param(Order.PARAM_AIRPORT,self.atc.airport.icao)
        order.add_param(Order.PARAM_RECEIVER,request.sender.callsign)
        #self.log("init response devuelve",order)
        return order
    
    def set_status(self,aircraft,status,number=None):
        self.atc.set_status(aircraft,status,number)
        
    def manage(self,request):
        req = request.get_request().req
        if self.manages(req):
            handler = getattr(self, req)
            return handler(request)
        return False
    
    def roger(self,request):
        tag=self.atc.tags.get(aircraft=request.sender)
        tag.ack_order=request.get_request().laor
        tag.save()
        
    def tunein(self,request):
        response=self._init_response(request)
        response.date = timezone.now() # inmediate
        response.message = ""
        response.add_param(Order.PARAM_ORDER, alias.TUNE_OK)
        self.set_status(request.sender, PlaneInfo.TUNNED)
        return response
    
    def reset(self,request):
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
        return self.name.decode()
    
    def __str__(self):
        return str(self.__unicode__())

class Tower(Controller):

    def holdingshort(self,request):
        response=self._init_response(request)
        response.add_param(Order.PARAM_RUNWAY,self.rwy_name())
        count = self.atc.tags.filter(status=PlaneInfo.SHORT).exclude(aircraft=request.sender).count()
        count_others = self.atc.tags.filter(status__in=[PlaneInfo.LINED_UP,PlaneInfo.LANDING]).exclude(aircraft=request.sender).count()
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
            self.set_status(request.sender, PlaneInfo.LINING_UP,1)
        else:
            response.add_param(Order.PARAM_ORDER, alias.CLEAR_TK)
            response.add_param(Order.PARAM_NUMBER, 1)
            self.set_status(request.sender, PlaneInfo.LINING_UP,1)
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
        self.set_status(request.sender, PlaneInfo.CLIMBING)
    
    def _report_circuit(self,request,cur_circuit,report_circuit):
        self.set_status(request.sender, cur_circuit)
        response=self._init_response(request)
        response.add_param(Order.PARAM_ORDER,alias.REPORT_CIRCUIT)
        response.add_param(Order.PARAM_CIRCUIT_WP,report_circuit)
        count = self.atc.tags.filter(status__in=PlaneInfo.CIRCUITS).order_by('status','status_changed')
        response.add_param(Order.PARAM_NUMBER,count+1)
        response.message=get_message(response)
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
        lined = self.atc.tags.filter(status=PlaneInfo.LINED_UP).count()
        landing = self.atc.tags.filter(status=PlaneInfo.LANDING).count()
        if lined:
            response.add_param(Order.PARAM_ORDER,alias.GO_AROUND)
            response.add_param(Order.PARAM_CIRCUIT_WP,alias.CIRCUIT_BASE)
            self.set_status(request.sender, PlaneInfo.APPROACHING)
        else:
            response.add_param(Order.PARAM_ORDER,alias.CLEAR_LAND)
            response.add_param(Order.PARAM_NUMBER,landing+1)
            response.add_param(Order.PARAM_RUNWAY,self.rwy_name())
            response.add_param(Order.PARAM_QNH, str(get_qnh(self.atc.airport)))
            self.set_status(request.sender, PlaneInfo.LANDING)
        response.message=get_message(response)
        return response

    def go_around(self,request):
        aircraft = request.sender
        response = self._init_response(request)
        response.add_param(Order.PARAM_ORDER,alias.GO_AROUND)
        response.add_param(Order.PARAM_CIRCUIT_WP,alias.CIRCUIT_BASE)
        self.set_status(aircraft, PlaneInfo.APPROACHING)
        response.message=get_message(response)
        return response
    
class Departure(Controller):
        
    def readytaxi(self,request):
        response=self._init_response(request)
        response.add_param(Order.PARAM_ORDER,'taxito')
        response.add_param(Order.PARAM_RUNWAY,self.rwy_name())
        count = self.atc.tags.filter(status=PlaneInfo.SHORT).count()
        count_others = self.atc.tags.filter(status__in=[PlaneInfo.LINED_UP,PlaneInfo.LANDING]).count()
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
        response.add_param(Order.PARAM_QNH, str(get_qnh(self.atc.airport)))
        response.message=get_message(response)
        self.set_status(request.sender, PlaneInfo.STOPPED)
        return response
    
    
class Approach(Controller):
    pass_alt = IntegerField(default=8000)
    circuit_alt= IntegerField(default=1000)
    circuit_type= CharField(max_length=20,default=alias.CIRCUIT_LEFT)
    
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
        response.add_param(Order.PARAM_ALTITUDE,self.circuit_alt )
        response.add_param(Order.PARAM_CIRCUIT_TYPE, self.circuit_type)
        response.add_param(Order.PARAM_CIRCUIT_WP,[alias.CIRCUIT_CROSSWIND,alias.CIRCUIT_DOWNWIND][randint(0,1)])
        response.add_param(Order.PARAM_QNH, str(get_qnh(self.atc.airport)))

        response.message=get_message(response)        
        self.set_status(request.sender, PlaneInfo.APPROACHING)
        return response
    
    
class Tag(StatusModel):
    STATUS = PlaneInfo.CHOICES_STR
    
    #comm = ForeignKey(Comm, related_name='tags')
    airport = ForeignKey(Airport, on_delete=models.CASCADE, related_name='tags',null=True)
    aircraft=ForeignKey(Aircraft, on_delete=models.CASCADE, related_name='tags')
    number = IntegerField(default=1)
    ack_order=CharField(max_length=255,null=True,blank=True)

    def __unicode__(self):
        return "%s - %s [%s]" % (self.airport,self.aircraft.callsign,self.status)
