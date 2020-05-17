'''
Created on 28 abr. 2020

@author: julio
'''
from fgserver.models import Aircrafts, Aircraft, Order, airportsWithinRange,\
    AircraftStatus, Cache, Request
from fgserver.messages import PosMsg, alias, sim_time
from fgserver import messages, units
import logging
from django.utils import timezone
import random
from fgserver.signals import signal_order_sent, signal_order_expired

llogger = logging.getLogger(__name__)

class AckedOrders(Cache):
    pass

def get_aircraft(callsign):
    aircraft = Aircrafts.get(callsign)
    if aircraft:
        aircraft.posmsg = getattr(aircraft,"posmsg", PosMsg())
    return aircraft

def process_message(pos):
    #llogger.debug("Processing message %s" % pos)
    try:
        aircraft = Aircrafts.get(pos.callsign())
        aircraft.posmsg=pos
        aircraft.update_position()
        
        aircraft.status.update_from_position(pos)
        #llogger.debug("Processing message %s" % pos)
        if not aircraft.plans.filter(enabled=True).count() and not "ATC" in pos.model:
            if not hasattr(aircraft, '_saved') or (timezone.now() - aircraft._saved).seconds > 1:
                #llogger.debug("saving %s %s" % (aircraft, pos,))
                aircraft.save()
                aircraft.status.save()
                aircraft._saved = timezone.now()
        
        
        freq = pos.get_frequency()
        if not freq:
            llogger.debug("Ignoring request without freq from %s: %s" % (aircraft, pos.properties.properties,))
            return
        
        # Handle aircraft
        check_acked_order(pos)
        process_request(aircraft, pos)
    except:
        llogger.exception("Processing msg")

def check_acked_order(pos):
    oid = pos.get_value(messages.PROP_OID)
    if oid and not "ATC" in pos.model and not AckedOrders.has(oid):
        try:
            order = Order.objects.get(pk=oid)
            if not order.received:
                order.received = True
                order.save()
                llogger.debug("Order marked as received %s" % order)
            AckedOrders.set(oid, order)   
        except:
            llogger.exception("al recibir orden %s" % oid)

def process_request(aircraft,pos):
    #llogger.debug("process request %s %s" % (aircraft, pos,))
    request = pos.get_value(messages.PROP_REQUEST)
    freq = pos.get_frequency()
    if not request:
        #llogger.debug("Avoiding null request")
        return
    last_r = aircraft.requests.filter(received=True).last()
    if last_r and request == last_r.request:
        #llogger.debug("Avoiding request already processed %s | %s" % (request, last_r,))
        return
    llogger.info("aircraft %s on %s (%s) requests %s" % (aircraft.callsign, freq, pos.time, request) )
    
    req = Request(sender=aircraft,date=timezone.now(),request=request, received=True)
    req.receiver_id = find_comm(req)
    if not req.receiver:
        llogger.debug("Receiver for %s on %s not found" % (aircraft,freq,))
        req.processed=True
    try:
        req.save()
        llogger.debug("Saved request %s" % req)
    except:
        llogger.exception("Al guardar req %s" % req)


ORDER_DELAY=5
ORDER_MIN_LIFESPAN=5
ORDER_MAX_LIFESPAN=15


def get_pos_msg(airport, simtime=None):
    msg = PosMsg()
    msg.send_from(airport)
    msg.time = simtime or sim_time()
    msg.lag=1
    
    # HACK clean chat
    msg.properties.set_prop(messages.PROP_CHAT,"" )
    msg.properties.set_prop(messages.PROP_CHAT2,"")
    # TODO: sort by type and then by order id (priorities)
    orders = Order.objects.filter(expired=False, lost=False, sender__airport=airport).order_by('id')
    order = orders.first()
    if not order:
        return msg
    
    if not order.get_instruction() == alias.TUNE_OK and (timezone.now() - order.date).total_seconds()<ORDER_DELAY:
        return msg
    
    if not order.sent_date:
        order.sent_date=timezone.now()
        llogger.info("Sending order from %s : %s" % (order.sender,order,))
        order.save()
        
        signal_order_sent.send_robust(None,order=order)
        
    lifespan = random.randrange(ORDER_MIN_LIFESPAN,ORDER_MAX_LIFESPAN) / orders.count()
    dif =(timezone.now() - order.sent_date).total_seconds()
    
    if dif > lifespan:
        order.expired = True
        if order.received:
            llogger.debug("Order expired %s" % order)
        else:
            order.lost = True
            llogger.warn("Order lost %s" % order)
        
        order.save();
        signal_order_expired.send_robust(None,order=order)
    else:
        msg.properties.set_prop(messages.PROP_FREQ, str(order.sender.get_FGfreq()))
#         msg.properties.set_prop(messages.PROP_FREQ_V2, order.sender.frequency)
        msg.properties.set_prop(messages.PROP_OID, str(order.id))
        ostring, ostring2 = get_order_strings(order.get_order())
        msg.properties.set_prop(messages.PROP_ORDER, ostring)
        msg.properties.set_prop(messages.PROP_ORDER2, ostring2)
    
        chat, chat2 = get_order_strings(order.message)
        msg.properties.set_prop(messages.PROP_CHAT,chat )
        msg.properties.set_prop(messages.PROP_CHAT2,chat2 )
    return msg

def find_comm(request):
    '''
    Find a Comm object with the request freq and inside a 50mi radius
    '''
    try:
        # fgfs sends integer freqs in Mhz but apt.dat has freqs in 1/100 Mhz (integers) 
        freq = request.get_request().freq
        freq = freq.replace('.','').ljust(5,'0') # replace the dot and add padding
        tag = "%s-%s" % (request.sender.callsign,freq)
        # TODO Clean the cache!!!  
    #     comm = self.controllers.get(tag,None)
    #     if comm:
    #         return comm
        llogger.debug("Finding COMM for %s" % tag)
        apts = airportsWithinRange(request.sender.get_position(), 50, units.NM)
        llogger.debug("Airports in range=%s " % apts)
        for apt in apts:
            c = apt.comms.filter(frequency=freq)
            if c.count():
                #self.controllers[tag]=c.first().id
                return c.first().id
        #self.controllers[tag]=None
    except:
        llogger.exception("Finding comm for %s" % request)
    return None

def get_order_strings(string):
    ''' 
    Split string into 2 strings if len > 127
    '''
    ostring = string
    ostring2=''
    if len(ostring) >=128:
        ostring2 = ostring[127:]
        ostring=ostring[:127]
    #print("ORDER STRINGS",[ostring,ostring2])
    return ostring,ostring2    


