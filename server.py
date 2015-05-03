# -*- encoding: utf-8 -*-
'''
Created on Apr 14, 2015

@author: bartacruz
'''
import socket
from xdrlib import Unpacker
from fgserver.messages import PROP_REQUEST, PROP_FREQ, PosMsg, PROP_CHAT,\
    PROP_ORDER
from fgserver.helper import cart2geod, Quaternion, Vector3D,\
    move
from django.db.models.signals import post_save
from django.dispatch.dispatcher import receiver
from fgserver.models import Order, Aircraft, Request, Airport
from django.utils import timezone
from fgserver.atc.models import Tower, ATC, Departure, Approach
from random import randint
from fgserver import units, llogger
from django.core.cache import  get_cache
import os 
from fgserver.ai.models import Circuit
from __builtin__ import Exception, max
os.environ['DJANGO_SETTINGS_MODULE'] = 'fgserver.settings' 
import django

orders = {}

UPDATE_RATE=2
_aircrafts=[]
_aaa={}
_circuits={}

_last_orders={}

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

def get_airport(icao):
    a = get_cache('airports').get(icao)
    if not a:
        try:
            a = Airport.objects.get(icao=icao)
            get_cache('airports').set(icao,a)
        except Airport.DoesNotExist as e:
            error("ERROR. Airport not found:",icao,e)
    return a

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

def load_circuits(airport):
    for circuit in airport.circuits.all():
        if not get_circuit(circuit.name):
            circuit.init()
            set_aircraft(circuit.aircraft)
            set_circuit(circuit)
            log("Circuit %s added" % circuit)
             
def get_controller(airport):
    a,create=ATC.objects.get_or_create(airport=airport)
    if create:
        log("Creating controller for %s" % airport)
        Departure.objects.create(atc=a,name="%s Departure" % airport.name)
        Approach.objects.create(atc=a,name="%s Approach" % airport.name)
        Tower.objects.create(atc=a,name="%s Tower" % airport.name)
    load_circuits(airport)
    #log("get_controller. returning %s" % a)
    return a

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
    pos = get_cache('positions').get(callsign)
    # TODO: if doesn't exists, see if we can recreate it from the aircraft.
    return pos


def set_pos(pos):
    if pos:
        pos.sim_time = sim_time()
        get_cache('positions').set(pos.callsign(),pos)
    
def queue_order(order):
    log("queue_order.",order,order.date)
    orders.setdefault(order.sender.icao,[]).append(order)
    
        
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
                _last_orders[o.sender.icao]=o
                if not o.receiver.ip:
                    c = get_circuit(o.receiver.callsign)
                    log("processint order",o)
                    c.process_order(o)
                    set_circuit(c)
                
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
            #log("saving aircraft", a.callsign, a.lat,a.lon,a.altitude)
            a.save()
        get_cache('default').set('last_update',timezone.now())
@receiver(post_save,sender=Order)
def process_order(sender, instance, **kwargs):
    if not instance.confirmed:
        queue_order(instance)


@receiver(post_save,sender=Request)
def process_request(sender, instance, **kwargs):
    req = instance.get_request()
    airport = get_airport(req.apt)
    controller = get_controller(airport)
    controller.manage(instance)
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
    if request:
        req = request.get_request()
        apt = Airport.objects.get(icao=req.apt)
        order = _last_orders.get(apt.icao)
        #order = apt.orders.filter(confirmed=True).exclude(message='').order_by('-date').first()
        #order = Order.objects.filter(sender=apt, confirmed=True).exclude(message='').order_by('-date').first()
        if order:
            msg = PosMsg()
            msg.send_from(order.sender)
            msg.time = sim_time()
            msg.lag=0.1
            msg.properties.set_prop(PROP_ORDER, order.get_order())
            msg.properties.set_prop(PROP_CHAT,order.message )
            
            #log("sending to",order.sender.get_position(),msg.position,msg.orientation)
            sendto(msg.send(), aircraft.get_addr())
        else:
            msg = PosMsg()
            msg.send_from(apt)
            msg.time = sim_time()
            msg.lag=0.1
            sendto(msg.send(), aircraft.get_addr())
    ''' send mp and ai planes positions to player ''' 
    for mp in get_mpplanes(aircraft):
        if mp.plans.count():
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
            
                
def sim_time():
    return (timezone.now() - DATE_STARTED).total_seconds()

def sendto(data,addr):
    global fgsock
    try:
        fgsock.sendto(data,addr)
    except:
        pass
        #log("Error sending to", addr)

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
            req.save()
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
