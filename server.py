# -*- encoding: utf-8 -*-
'''
Created on Apr 14, 2015

@author: bartacruz@gmail.com
'''
import socket
from xdrlib import Unpacker
from fgserver.messages import PROP_REQUEST, PROP_FREQ, PosMsg, PROP_CHAT,\
    PROP_ORDER, alias, PROP_CHAT2, PROP_ORDER2, PROP_OID
from fgserver.helper import cart2geod, Quaternion, Vector3D,\
    move
from django.db.models.signals import post_save
from django.dispatch.dispatcher import receiver
from fgserver.models import Order, Aircraft, Request, Airport,\
    airportsWithinRange
from django.utils import timezone
from fgserver.atc.models import Tower, ATC, Departure, Approach
from fgserver import units, llogger, messages, get_controller
from django.core.cache import  get_cache
import os 
from __builtin__ import Exception, max
os.environ['DJANGO_SETTINGS_MODULE'] = 'fgserver.settings' 
import django

orders = {}

UPDATE_RATE=2
_aircrafts=[]
POSITIONS = {}
_aaa={}
_circuits={}

_last_orders={}
_received_orders = {}

def log(*argv):
    msg = "[Server]"
    for arg in argv:
        msg += " %s" % arg
    llogger.info(msg)

def error(*argv):
    msg = "[Server]"
    for arg in argv:
        msg += " %s" % arg
    llogger.error(msg)

# def get_airport(icao):
#     a = get_cache('airports').get(icao)
#     if not a:
#         try:
#             a = Airport.objects.get(icao=icao)
#             get_cache('airports').set(icao,a)
#         except Airport.DoesNotExist as e:
#             error("ERROR. Airport not found:",icao,e)
#     return a

def set_circuit(circuit):
    if circuit:
        #log("storing circuit",circuit.__dict__)
        #get_cache('circuits').set(circuit.name,circuit)
        if not _circuits.has_key(circuit.name):
            log("storing circuit",circuit.name)
            _circuits[circuit.name]=circuit
        
def get_circuit(name):
    #return get_cache('circuits').get(name)
    return _circuits.get(name)

def check_circuits(controller):
    log('checking circuits for %s' % controller)
    load_circuits(controller.comm.airport)

def load_circuits(airport):
    for circuit in airport.circuits.all():
        if not get_circuit(circuit.name):
            circuit.init()
            set_aircraft(circuit.aircraft)
            set_circuit(circuit)
            log("Circuit %s added" % circuit)
             
# def get_controller(airport):
#     a,create=ATC.objects.get_or_create(airport=airport)
#     if create:
#         log("Creating controller for %s" % airport)
#         Departure.objects.create(atc=a,name="%s Departure" % airport.name)
#         Approach.objects.create(atc=a,name="%s Approach" % airport.name)
#         Tower.objects.create(atc=a,name="%s Tower" % airport.name)
#     load_circuits(airport)
#     #log("get_controller. returning %s" % a)
#     return a

def get_aicraft(callsign):
    #a = get_cache('aircrafts').get(callsign)
    a = _aaa.get(callsign)
    #log(callsign,"a",a,"_aaa",_aaa)
    if not a:
        try:
            a,create = Aircraft.objects.get_or_create(callsign=pos.callsign())
            if create:
                log("New Plane:", a)
            else:
                log("Loaded plane",a)
            a.state = 1
            set_aircraft(a)
        except Exception as e:
            log("ERROR. Can't find or create aircraft:",callsign,e)
    return a

def set_aircraft(aircraft):
    _aaa[aircraft.callsign]=aircraft
    #get_cache('aircrafts').set(aircraft.callsign,aircraft)
    if not _aircrafts.count(aircraft.callsign):
        log("adding aircraft to cache: %s" % aircraft.callsign)
        _aircrafts.append(aircraft.callsign)

def get_pos(callsign):
    pos = POSITIONS.get(callsign)
    # TODO: if doesn't exists, see if we can recreate it from the aircraft.
    return pos


def set_pos(pos):
    if pos:
        pos.sim_time = sim_time()
        POSITIONS[pos.callsign()]=pos
    
def queue_order(order):
    log("queue_order.",order,order.date)
    orders.setdefault(order.sender.id,[]).append(order)
    
        
def process_queues():
    for apt in orders:
        if len(orders[apt]):
            o = orders[apt][0]
            dif =(timezone.now() - o.date).total_seconds()
            if dif > 1:
                o = orders[apt].pop(0)
                o.confirmed=True
                log("activating order ",o)
                o.save()
                _last_orders[o.sender.id]=o
                if not o.receiver.ip:
                    c = get_circuit(o.receiver.callsign)
                    log("processing order",o)
                    c.process_order(o)
                    set_circuit(c)
                    
def receive_order(aircraft,oid):
    if not is_order_received(aircraft,oid):
        o = aircraft.orders.filter(pk=oid).last()
        print "RECEIVE",oid,o,aircraft
        o.received=True
        o.save()
        _received_orders[str(aircraft.id)]=int(oid)
        log("order received for %d : %s" %(aircraft.id, oid))
        return True
    return False

def is_order_received(aircraft,oid):
    last = _received_orders.get(str(aircraft.id),0)
    return int(oid) == int(last)
    
def save_cache():
    _last_update = get_cache('default').get('last_update')
    if not _last_update or (timezone.now() - _last_update).total_seconds() > UPDATE_RATE:
        for callsign in _aircrafts:
            p = get_pos(callsign)
            a = get_aicraft(callsign)
            #log("saving aircraft %s" % a.__dict__)
            if p and sim_time() - p.sim_time > 10:
                log("Deactivating aircraft: %s" % callsign, sim_time(),p.sim_time)
                _aircrafts.remove(callsign)
                a.state=0
            else:
                a.state=1
            #log("saving aircraft", a.callsign, a.lat,a.lon,a.altitude)
            a.save()
        get_cache('default').set('last_update',timezone.now())

@receiver(post_save,sender=Order)
def process_order(sender, instance, **kwargs):
    if not instance.confirmed:
        queue_order(instance)

@receiver(post_save,sender=Request)
def process_request(sender, instance, **kwargs):
    if instance.receiver:
        log("Processing request %s " % instance)
        controller = get_controller(instance.receiver)
        controller.manage(instance)
        check_circuits(controller)
    else:
        log("Ignoring request without receiver %s " % instance)
#     order= 
#     if order:
#         order.sender = airport
#         order.save()
#         log("saving order",order,order.date,timezone.now())

def get_mpplanes(aircraft):
    planes = []
    sw = move(aircraft.get_position(),-135,50*units.NM,aircraft.altitude)
    ne = move(aircraft.get_position(),45,50*units.NM,aircraft.altitude)
    #afs = Aircraft.objects.filter(state__gte=1,lat__lte=ne.x, lat__gte=sw.x,lon__lte=ne.y,lon__gte=sw.y)
    for af in _aaa.itervalues():
        if af.callsign != aircraft.callsign and af.state >= 1 \
        and af.lat<=ne.x and af.lat>=sw.x\
        and af.lon<=ne.y and af.lon>=sw.y:
            planes.append(af)
    return planes
    #return []

def send_pos(callsign):
    #aircraft = Aircraft.objects.get(callsign=callsign)
    #request = Request.objects.filter(sender=aircraft).order_by('-date').first()
    aircraft = get_aicraft(callsign)
    request = aircraft.requests.last()
    if aircraft.freq and request and request.receiver:
        #log("aircraft.freq =%s, receiver.freq=%s" % (aircraft.freq,request.receiver.get_FGfreq()))
        order = _last_orders.get(request.receiver.id)
        if order:
            try:
                msg = PosMsg()
                msg.send_from_comm(order.sender)
                msg.time = sim_time()
                msg.lag=0.1
                msg.properties.set_prop(PROP_FREQ, str(order.sender.get_FGfreq()))
                #print 'CHK',order.id,aircraft.id,_received_orders
                if not is_order_received(order.receiver, order.id):
                    ostring = order.get_order()
                    ostring2=''
                    if len(ostring) >=128:
                        ostring2 = ostring[127:]
                        msg.properties.set_prop(PROP_ORDER2, ostring2)
                        ostring=ostring[:127]
                    else:
                        msg.properties.set_prop(PROP_ORDER2, '')
                    msg.properties.set_prop(PROP_ORDER, ostring)
                    msg.properties.set_prop(PROP_CHAT, '')
                    msg.properties.set_prop(PROP_CHAT2, '')                    
                else:
                    msg.properties.set_prop(PROP_ORDER, "{'oid':'%d'}" % order.id)    
                    chat = order.message
                    chat2=''
                    if len(chat) >=128:
                        chat2 = chat[127:]
                        msg.properties.set_prop(PROP_CHAT2,chat2 )
                        chat=chat[:127]
                    else:
                        msg.properties.set_prop(PROP_CHAT2,'' )
                     
                    if chat:
                        msg.properties.set_prop(PROP_CHAT,chat )
                        msg.properties.set_prop(PROP_ORDER,'')
                        msg.properties.set_prop(PROP_ORDER2,'')
                #log("sending to",order.sender.get_position(),msg.position,msg.orientation)
                buff = msg.send()
                if len(buff) > 1200: 
                    log("ERROR msg size=%d. Not sending", len(buff))
                else:
                    sendto(buff, aircraft.get_addr())
                
                
            except:
                llogger.exception("Sending msg")
        else:
            msg = PosMsg()
            msg.send_from_comm(request.receiver)
            msg.time = sim_time()
            msg.lag=0.1
            msg.properties.set_prop(PROP_FREQ, request.receiver.get_FGfreq())
            sendto(msg.send(), aircraft.get_addr())
    ''' send mp and ai planes positions to player ''' 
    for mp in get_mpplanes(aircraft):
        if msg and mp.plans.count():
            for p in mp.plans.all():
                if p.circuit:
                    cir = get_circuit(p.circuit.name)
                    if cir: 
                        pos = cir.update(msg.time)
                        set_circuit(cir)
                        set_aircraft(cir.aircraft)
                        aaa= get_aicraft(cir.aircraft.callsign)
                else:
                    pos = p.update(msg.time)
                
                if pos:
                    set_pos(pos)
        else:
            pos = get_pos(mp.callsign)
        
        if pos:
            pos.time = sim_time()
            pos.lag=0.1
            #log("sending mp",pos.__dict__)
            sendto(pos.send(),aircraft.get_addr())
            oid_p = pos.get_property(PROP_OID)
            if oid_p:
                receive_order(mp, oid_p['value'])
            
def sim_time():
    return (timezone.now() - DATE_STARTED).total_seconds()

def sendto(data,addr):
    global fgsock
    try:
        fgsock.sendto(data,addr)
    except:
        pass
        #log("Error sending to", addr)

def find_comm(request):
    
    # fgfs sends integer freqs in Mhz but apt.dat has freqs in 1/100 Mhz (integers) 
    freq = request.get_request().freq
    freq = freq.replace('.','').ljust(5,'0') # replace the dot and add padding
    comm = get_cache('controllers').get("%s-%s" % (request.sender.callsign,freq))
    if comm:
        print "RETURNING CACHED COMM for %s" % freq
        return comm
    print "FINDING COMM for %s" % freq
    apts = airportsWithinRange(request.sender.get_position(), 50, units.NM)
    print "Airports in range=%s " % apts
    for apt in apts:
        c = apt.comms.filter(frequency=freq)
        if c.count():
            get_cache('controllers').set("%s-%s" % (request.sender.callsign,freq),c.first().id)
            return c.first().id
    return None


def process_pos(pos):
    
    set_pos(pos)
    aircraft = get_aicraft(pos.callsign())
    aircraft.ip=pos.header.reply_addr 
    aircraft.port=pos.header.reply_port
    geod = cart2geod(pos.position)
    aircraft.lat=geod[0]
    aircraft.lon=geod[1]
    aircraft.altitude=geod[2]
    
    
    qor = Quaternion.fromAngleAxis(Vector3D.from_array(pos.orientation))
    h10r = Quaternion.fromLatLon(aircraft.lat, aircraft.lon).conjugate().multiply(qor)
    eul = h10r.getEuler().scale(units.RAD)
    aircraft.heading= eul.z
    
    freq = pos.get_property(PROP_FREQ)['value']
    aircraft.freq = freq
    
    set_aircraft(aircraft)
    
    request_p = pos.get_property(PROP_REQUEST)
    if request_p:
        request = request_p['value']
        if request != aircraft.last_request:
            log("aircraft %s requests %s at %s. last=%s" % (aircraft.callsign, request, freq,aircraft.last_request) )
            aircraft.last_request = request
            set_aircraft(aircraft)
            req = Request(sender=aircraft,date=timezone.now(),request=request)
            req.receiver_id = find_comm(req)
            log("receiver=%s" % req.receiver )
            req.save()
    oid_p = pos.get_property(PROP_OID)
    if oid_p:
        receive_order(aircraft, oid_p['value'])
    return True
#     except Exception as e:
#         log("ERROR al procesar posicion",e,pos)
#         return False

#t = threading.Thread(target=processor, name='Servicio')
DATE_STARTED = timezone.now()

MSG_MAGIC = 0x46474653

# Reset all planes to 0
Aircraft.objects.all().update(state=0)
Order.objects.all().update(confirmed=False)
get_cache('default').set('last_update',timezone.now())

fgsock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
fglisten = ("localhost",5100)
fgsock.bind(fglisten)

cont = True
while cont:
    data,addr = fgsock.recvfrom(1200)
    #xs= ":".join("{:02x}".format(ord(c)) for c in data)
    unp = Unpacker(data)
    pos = PosMsg()
    pos.receive(unp)
    pos.header.reply_addr=addr[0]
    pos.header.reply_port=addr[1]
    resp = process_pos(pos)
    save_cache()
    process_queues()
    send_pos(pos.callsign())
