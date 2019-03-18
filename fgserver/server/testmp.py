'''
Created on 16 mar. 2019

@author: julio
'''
import django
from fgserver.messages import PosMsg
from fgserver import messages, settings, setInterval, units, llogger,\
    get_controller
from django.utils import timezone
import socket
from xdrlib import Unpacker
from queue import Queue, Empty
from fgserver.helper import cart2geod, Quaternion, Vector3D
django.setup()

from fgserver.models import Airport, Comm, Aircraft, Request,\
    airportsWithinRange, Order


def get_order_strings(string):
    ''' 
    Split string into 2 strings if len > 127
    '''
    ostring = string
    ostring2=''
    if len(ostring) >=128:
        ostring2 = ostring[127:]
        ostring=ostring[:127]
    return ostring,ostring2    


def sim_time():
        return (timezone.now() - date_started).total_seconds()

def find_comm(request):
    '''
    Find a Comm object with the request freq and inside a 50mi radius
    '''
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
    return None


def get_msg():
    msg = PosMsg()
    msg.send_from_comm(comm)
    #msg.time = self.sim_time()
    msg.time = sim_time()
    msg.lag=0.1
    msg.properties.set_prop(messages.PROP_FREQ, str(comm.get_FGfreq()))
    order = comm.orders.last()    
    if order and not order.received:
        print(order)
        ostring, ostring2 = get_order_strings(order.get_order())
        msg.properties.set_prop(messages.PROP_ORDER, ostring)
        msg.properties.set_prop(messages.PROP_ORDER2, ostring2)
        
        chat, chat2 = get_order_strings(order.message)
        msg.properties.set_prop(messages.PROP_CHAT,chat )
        msg.properties.set_prop(messages.PROP_CHAT2,chat2 )
    #print(msg)
    return msg

@setInterval(1)
def send_msg():
    msg = get_msg()
    incoming.put(msg)
    #print("Put",msg)

def get_aircraft(callsign):
    aircraft = aircrafts.get(pos.callsign(),None)
    if not aircraft:
        try:
            aircraft = Aircraft.objects.get(callsign=callsign)
            aircraft.posmsg = PosMsg()
            print("Loaded ACFT:",aircraft)
            aircrafts[callsign]=aircraft
        except Aircraft.DoesNotExist:
            llogger.warn("Unknown aircraft |%s|" % callsign )
        except:
            llogger.exception("Trying to get aircraft %s" % callsign)
    return aircraft


def process_msg(pos):
    aircraft = get_aircraft(pos.callsign())
    freq = pos.get_value(messages.PROP_FREQ)
    if not aircraft:
        if freq:
            aircraft=Aircraft(callsign=pos.callsign())
            aircraft.posmsg = PosMsg()
            aircraft.save()
            aircrafts[pos.callsign()]=aircraft
    old_freq = aircraft.posmsg.get_value(messages.PROP_FREQ) 
    if freq != old_freq:
        print("ACFT %s changed freqs from %s to %s" % (pos.callsign(),old_freq,freq))
        aircraft.freq = freq
    oid = pos.get_value(messages.PROP_OID)
    old_oid = aircraft.posmsg.get_value(messages.PROP_OID)
    if oid and oid != old_oid:
        order = Order.objects.get(pk=oid)
        order.received = True
        order.save()
        
        
    
    
    aircraft.posmsg = pos
    aircraft.update_position()
    
    request = pos.get_value(messages.PROP_REQUEST)
    if request and request != aircraft.last_request:
        llogger.info("aircraft %s requests %s at %s. last=%s" % (aircraft.callsign, request, freq,aircraft.last_request) )
        aircraft.last_request = request
        req = Request(sender=aircraft,date=timezone.now(),request=request)
        req.receiver_id = find_comm(req)
        llogger.info("receiver=%s" % req.receiver )
        req.save()
        process_request(req)
        

def process_request(instance):
    if instance.receiver:
        llogger.debug("Processing request %s " % instance)
        controller = get_controller(instance.receiver)
        controller.manage(instance)
    else:
        llogger.warning("Ignoring request without receiver %s " % instance)    

aircrafts = {}

icao = "SAAR"
incoming = Queue()

date_started = timezone.now()
airport = Airport.objects.get(icao=icao)
airport.altitude = airport.altitude * units.FT
print(airport.altitude)
comm = airport.comms.filter(type=Comm.TWR).first()
relaysock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
fglisten = ("localhost",settings.FGATC_SERVER_PORT)
send_msg()
# relaysock.bind(fglisten)
relaysock.setblocking(0)
llogger.info("Starting")
while relaysock:
    try:
        msg = incoming.get(False)
        #print("Sending",type(msg.send()),settings.FGATC_RELAY_SERVER)
        relaysock.sendto(msg.send(), settings.FGATC_RELAY_SERVER)
        #print("Sent",msg)
    except Empty:
        pass
    try:
        data,addr = relaysock.recvfrom(1200)
        unp = Unpacker(data)
        pos = PosMsg()
        pos.receive(unp)
        pos.header.reply_addr=addr[0]
        pos.header.reply_port=addr[1]
        #print("Received",pos)
        process_msg(pos)
    except BlockingIOError:
        pass
    
print("end")
 



