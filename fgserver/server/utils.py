'''
Created on 28 abr. 2020

@author: julio
'''
from fgserver.models import Aircrafts, Aircraft, Order, airportsWithinRange,\
    AircraftStatus
from fgserver.messages import PosMsg, alias, sim_time
from fgserver import messages, units
import logging
from django.utils import timezone
import random
from fgserver.signals import signal_order_sent, signal_order_expired
from django.core.exceptions import ObjectDoesNotExist

llogger = logging.getLogger(__name__)

def get_aircraft(callsign):
    aircraft = Aircrafts.get(callsign)
    if aircraft:
        aircraft.posmsg = getattr(aircraft,"posmsg", PosMsg())
    return aircraft

def process_msg(pos):
    #request = None
    #llogger.debug("Processing message %s" % pos)
    try:
        try:
            aircraft = Aircraft.objects.get(callsign=pos.callsign())
        except Aircraft.DoesNotExist:
            llogger.info("Creating new Aircraft %s" % pos.callsign())
            aircraft=Aircraft(callsign=pos.callsign())
            aircraft.save()
        try: 
            status = aircraft.status
        except:
            llogger.info("Creating new AircraftStatus for %s" % aircraft)
            status = AircraftStatus(aircraft=aircraft)
            status.save()
        #llogger.debug("Status %s from %s on %s,  order=%s,  updated=%s" % (status.id, aircraft, status.freq, status.order, status.date)) 
        freq = pos.get_value(messages.PROP_FREQ)
        if not freq:
            #llogger.debug("Ignoring request without freq from %s" % aircraft)
            return
        
        if not "ATC" in pos.model and status.get_fg_freq() != freq:
            llogger.info("Aircraft %s changed freqs from %s to %s" % (pos.callsign(),status.get_fg_freq(),freq))
        
        oid = pos.get_value(messages.PROP_OID)
        if not "ATC" in pos.model and oid and status.order != oid:
            try:
                llogger.debug("orden nueva %s -> %s" % (status.order,oid,))
                order = Order.objects.get(pk=oid)
                order.received = True
                order.save()
                llogger.debug("Order marked as received %s" % order)   
            except:
                llogger.exception("al recibir orden %s" % oid)
                
        if not aircraft.plans.filter(enabled=True).count() and not "ATC" in pos.model:
            status.update_from_position(pos)
            status.save()
            #llogger.debug("External aircraft updated")
    except:
        llogger.exception("Processing msg")

ORDER_DELAY=3
ORDER_MIN_LIFESPAN=3
ORDER_MAX_LIFESPAN=10
def get_pos_msg(airport):
    msg = PosMsg()
    msg.send_from(airport)
    msg.time = sim_time()
    msg.lag=1
    # TODO: sort by type and then by order id (priorities)
    orders = Order.objects.filter(expired=False, lost=False, sender__airport=airport).order_by('id')
    order = orders.first()
    if not order:
        return msg
    
    if not order.get_instruction() == alias.TUNE_OK and (timezone.now() - order.date).total_seconds()<ORDER_DELAY:
        return msg
    
    if not order.sent_date:
        order.sent_date=timezone.now()
        llogger.info("Sending order %s" % order)
        order.save()
        
        signal_order_sent.send_robust(None,order=order)
        
    lifespan = random.randrange(ORDER_MIN_LIFESPAN,ORDER_MAX_LIFESPAN)
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
    
    msg.properties.set_prop(messages.PROP_FREQ, str(order.sender.get_FGfreq()))
    msg.properties.set_prop(messages.PROP_OID, str(order.id))
    ostring, ostring2 = get_order_strings(order.get_order())
    msg.properties.set_prop(messages.PROP_ORDER, ostring)
    msg.properties.set_prop(messages.PROP_ORDER2, ostring2)

    chat, chat2 = get_order_strings(order.message)
    msg.properties.set_prop(messages.PROP_CHAT,chat )
    msg.properties.set_prop(messages.PROP_CHAT2,chat2 )
    
    try:
        status,created = AircraftStatus.objects.get_or_create(aircraft__callsign=airport.icao)
        status.order = str(order.id)
        status.freq = order.sender.frequency
        status.date = timezone.now()
        status.save()
    except:
        llogger.exception("Updating status for %s" % airport)
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


