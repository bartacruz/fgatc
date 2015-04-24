# -*- encoding: utf-8 -*-
'''
Created on Apr 17, 2015

@author: julio
'''
from random import randint
from fgserver.helper import short_callsign
from fgserver.models import Order
from django.utils import timezone

# class Response():
#     sender=None
#     receiver=None
#     message=None
#     order=None
#     def __init__(self,sender=None,receiver=None,message=None,order=None):
#         self.sender=sender
#         self.receiver=receiver
#         self.message=message
#         self.order=order
    
    
class Controller():
    airport = None
    name="Controller"
    
    def __init__(self,airport):
        self.airport=airport
    
    def manages(self,req):
        return req and hasattr(self,req)
    
    def manage(self,request):
        req = request.get_request().req
        if self.manages(req):
            handler = getattr(self, req)
            return handler(request)
        return False    
    def tunein(self,request):
        response=Order(sender=self.airport,receiver=request.sender,date=timezone.now())
        response.message = ""
        response.add_param('ord', 'tuneok')
        return response
    
    def reset(self,request):
        Order.objects.filter(receiver=request.sender, confirmed=True).update(confirmed=False)
        
    def repeat(self,request):
        order = Order.objects.filter(receiver=request.sender, confirmed=True).order_by('-date').first()
        response=Order(sender=self.airport,receiver=request.sender,date=timezone.now())
        rep = order.get_param(Order.PARAM_REPEAT,0) +1
        response._order = order._order
        response.add_param(Order.PARAM_REPEAT, rep)
        if rep > 1:
            response.message = order.message.replace(', I say again','')
        else:
            response.message = order.message.replace(',', ', I say again,',1)
        return response

class Tower(Controller):
    controllers = []
    def __init__(self,airport):
        Controller.__init__(self,airport)
        self.name="Tower"
        self.controllers=[Departure(airport),Approach(airport)]

    def manage(self, request):
        for controller in self.controllers:
            ret = controller.manage(request)
            if ret:
                print "Responde %s" % controller.name
                return ret
        return Controller.manage(self, request)
    
class Departure(Controller):
    def __init__(self,airport):
        Controller.__init__(self,airport)
        self.name="Departure"
        
    def readytaxi(self,request):
        response=Order()
        rwy = self.airport.active_runway()
        msg = "%s, taxi to runway %s" % (short_callsign(request.sender.callsign),rwy.name)
        short = randint(0,1)
        if short:
            msg += " and hold short"
        else:
            msg += " and line up"
        response.message=msg
        response.add_param(Order.PARAM_ORDER,'taxito')
        response.add_param(Order.PARAM_RUNWAY,rwy.name)
        response.add_param('short',short)
        return response

    def startup(self,request):
        response=Order()
        response.message = "%s, start up approved. Call when ready to taxi." % request.sender.callsign
        response.add_param(Order.PARAM_ORDER, 'startup')
        return response
    
    def holdingshort(self,request):
        response=Order()
        rwy = self.airport.active_runway()
        response.add_param(Order.PARAM_RUNWAY, rwy.name)
        if randint(0,1)==1:
            response.message = "%s, line up on runway %s and hold" % (request.sender.callsign,rwy.name)
            response.add_param(Order.PARAM_ORDER, 'lineup')
        else:
            response.message = "%s, cleared for takeoff" % request.sender.callsign
            response.add_param(Order.PARAM_ORDER, 'cleartk')
        return response
    
    def readytko(self,request):
        response=Order()
        rwy = self.airport.active_runway()
        response.add_param(Order.PARAM_RUNWAY, rwy.name)
        response.add_param(Order.PARAM_ORDER, 'cleartk')
        response.message = "%s, cleared for takeoff" % request.sender.callsign
        return response
    
class Approach(Controller):
    pass_alt = 8000
    
    def transition(self,request):
        response=Order()
        response.message = "%s, clear to cross airspace above %s" % (request.sender.callsign,self.pass_alt)
        response.add_param(Order.PARAM_ORDER, 'clearcross')
        response.add_param(Order.PARAM_ALTITUDE,self.pass_alt )
        return response
    
    def __init__(self,airport):
        Controller.__init__(self,airport)
        self.name="Approach"
    
    
def get_controller(airport):
    #TODO determinar el tipo de controlador y configurarlo
    return Tower(airport)