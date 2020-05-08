'''
Created on 6 de may. de 2017

@author: julio
'''
import socket

from django.utils import timezone

from fgserver import settings, units, messages, get_controller
from fgserver.atc.models import Tag
from fgserver.models import Aircraft, Order, airportsWithinRange, Request
from xdrlib import Unpacker
from fgserver.messages import PosMsg
import logging
from fgserver.helper import move, cart2geod, Quaternion, Vector3D
import time
from threading import Thread
from queue import Empty, Queue
from fgserver.server.fgmpie import PacketData

llogger = logging.getLogger(__name__)

AIPLANES_ENABLED=False

class FGServer():
    MSG_MAGIC = 0x46474653

    orders = {}
    positions = {}
    aircrafts={}
    circuits={}
    controllers={}

    last_orders={}
    received_orders = {}
    ai_thread = None
    date_started=None
    last_update=None
    fgsock = None
    relaysock=None
    running=False
    
    incoming = Queue()
    
    def process_incoming(self):
        while self.running:
            data=None
            try:
                data,addr = self.incoming.get(True,1)
                self.relay(data)
                unp = PacketData(data)
                pos = PosMsg()
                pos.receive_pie(unp)
                pos.header.reply_addr=addr[0]
                pos.header.reply_port=addr[1]
                #llogger.debug("processing %s" % pos)
                resp = self.process_pos(pos)
                self.save_cache()
                self.process_queues()
                self.send_pos(pos.callsign())
                
            except Empty:
                pass
            except:
                llogger.exception("in process_incoming")
                self.running=False
                
    
    def start(self):
        # Reset all planes to 0
        Aircraft.objects.all().update(state=0)
        Order.objects.all().update(expired=True)
        Tag.objects.all().delete()
        self.date_started=timezone.now()
        self.last_update=timezone.now()
        
        
        
        self.fgsock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        self.relaysock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        fglisten = ("localhost",settings.FGATC_SERVER_PORT)
        self.fgsock.bind(fglisten)
        
        self.running = True
        llogger.info("Starting")
        
        # Main loop
        self._thread = Thread(target=self.process_incoming)
        self._thread.start()
        while self.running:
            try:
                data,addr = self.fgsock.recvfrom(1200)
                self.incoming.put((data,addr))
            except:
                llogger.exception("on main loop")
                self.running=False
        
        llogger.info("End Run")

    def sim_time(self):
        return (timezone.now() - self.date_started).total_seconds()
    
    
    def set_circuit(self,circuit):
        if circuit:
            if not self.circuits.get(circuit.name,False):
                llogger.info("storing circuit %s" % circuit.name)
                self.circuits[circuit.name]=circuit
    
    def get_circuit(self,name):
        return self.circuits.get(name)
    
    def check_circuits(self,controller):
        if not AIPLANES_ENABLED:
            return
        print(type(controller))
        llogger.info('checking circuits for %s' % controller)
        self.load_circuits(controller.comm.airport)
    
    def load_circuits(self,airport):
        if not AIPLANES_ENABLED:
            return
        
        for circuit in airport.circuits.filter(enabled=True):
            if not self.get_circuit(circuit.name):
                self.set_circuit(circuit)
                circuit.init()
                self.set_aircraft(circuit.aircraft)
                llogger.info("Circuit %s added" % circuit)
    
    
    def get_aircraft(self,callsign):
        a = self.aircrafts.get(callsign)
        if not a:
            try:
                a,create = Aircraft.objects.get_or_create(callsign=callsign)
                if create:
                    llogger.info("New Plane: %s" % a)
                else:
                    llogger.info("Loaded plane %s" % a)
                a.state = 1
                self.set_aircraft(a)
            except Exception as e:
                llogger.info("ERROR. Can't find or create aircraft: %s %s " % (callsign,e))
        return a
    
    def set_aircraft(self,aircraft):
        self.aircrafts[aircraft.callsign]=aircraft
    
    def get_pos(self,callsign):
        pos = self.positions.get(callsign)
        # TODO: if doesn't exists, see if we can recreate it from the aircraft.
        return pos
    
    
    def set_pos(self,pos):
        if pos:
            pos.sim_time = self.sim_time()
            self.positions[pos.callsign()]=pos
        
    def queue_order(self,order):
        llogger.info("queue_order %s %s" % (order,order.date,))
        self.orders.setdefault(order.sender.id,[]).append(order)

    def relay(self,data):
        if getattr(settings, 'FGATC_RELAY_ENABLED',False):
            try:
                self.relaysock.sendto(data, settings.FGATC_RELAY_SERVER)
            except:
                llogger.exception("Error relaying data to server")
            
    
    def process_queues(self):
        for apt in self.orders:
            if len(self.orders[apt]):
                try:
                    o = self.orders[apt][0]
                    dif =(timezone.now() - o.date).total_seconds()
                    if dif > 2:
                        o = self.orders[apt].pop(0)
                        o.confirmed=True
                        llogger.info("activating order %s" %o)
                        o.save()
                        self.last_orders[o.sender.id]=o
                        if not o.receiver.ip:
                            c = self.get_circuit(o.receiver.callsign)
                            llogger.info("processing order %s" % o)
                            c.process_order(o)
                            self.set_circuit(c)
                except:
                    llogger.exception("procesando orden de %s" % apt)
                    
    def receive_order(self,aircraft,oid):
        if not self.is_order_received(aircraft,oid):
            o = aircraft.orders.filter(pk=oid).last()
            o.received=True
            o.save()
            self.received_orders[str(aircraft.id)]=int(oid)
            llogger.info("order received for %d : %s" %(aircraft.id, oid))
            return True
        return False
    
    def is_order_received(self,aircraft,oid):
        last = self.received_orders.get(str(aircraft.id),0)
        return int(oid) <= int(last)
        
    def save_cache(self):
        _last_update = self.last_update
        sim_time = self.sim_time()
        if not _last_update or (timezone.now() - _last_update).total_seconds() > settings.FGATC_UPDATE_RATE:
            for callsign in self.aircrafts.keys():
                p = self.get_pos(callsign)
                a = self.get_aircraft(callsign)
                #llogger.info("saving aircraft %s" % a.__dict__)
                if p and sim_time - p.sim_time > 10:
                    llogger.info("Deactivating aircraft: %s" % callsign, sim_time,p.sim_time)
                    self.aircrafts.pop(callsign)
                    a.state=0
                else:
                    a.state=1
                #llogger.info("saving aircraft", a.callsign, a.lat,a.lon,a.altitude)
                a.save()
            self.last_update=timezone.now()
    
    def get_mpplanes(self,aircraft):
        planes = []
        sw = move(aircraft.get_position(),-135,50*units.NM,aircraft.altitude)
        ne = move(aircraft.get_position(),45,50*units.NM,aircraft.altitude)
        #afs = Aircraft.objects.filter(state__gte=1,lat__lte=ne.x, lat__gte=sw.x,lon__lte=ne.y,lon__gte=sw.y)
        for af in self.aircrafts.values():
            if af.callsign != aircraft.callsign and af.state >= 1 \
            and af.lat<=ne.x and af.lat>=sw.x\
            and af.lon<=ne.y and af.lon>=sw.y:
                planes.append(af)
        return planes
        #return []
    
    def send_pos(self,callsign):
        aircraft = self.get_aircraft(callsign)
        request = aircraft.requests.last()
        msg = None
        if aircraft.freq and request and request.receiver:
            #llogger.info("aircraft.freq =%s, receiver.freq=%s" % (aircraft.freq,request.receiver.get_FGfreq()))
            order = self.last_orders.get(request.receiver.id)
            if order:
                try:
                    msg = PosMsg()
                    msg.send_from_comm(order.sender)
                    msg.time = self.sim_time()
                    msg.lag=0.1
                    msg.properties.set_prop(messages.PROP_FREQ, str(order.sender.get_FGfreq()))
                    #print 'CHK',order.id,aircraft.id,self.received_orders
                    if not self.is_order_received(order.receiver, order.id):
                        ostring = order.get_order()
                        ostring2=''
                        if len(ostring) >=128:
                            ostring2 = ostring[127:]
                            msg.properties.set_prop(messages.PROP_ORDER2, ostring2)
                            ostring=ostring[:127]
                        else:
                            msg.properties.set_prop(messages.PROP_ORDER2, '')
                        msg.properties.set_prop(messages.PROP_ORDER, ostring)
                        msg.properties.set_prop(messages.PROP_CHAT, '')
                        msg.properties.set_prop(messages.PROP_CHAT2, '')                    
                    else:
                        msg.properties.set_prop(messages.PROP_ORDER, "{'oid':'%d'}" % order.id)    
                        chat = order.message
                        chat2=''
                        if len(chat) >=128:
                            chat2 = chat[127:]
                            msg.properties.set_prop(messages.PROP_CHAT2,chat2 )
                            chat=chat[:127]
                        else:
                            msg.properties.set_prop(messages.PROP_CHAT2,'' )
                         
                        if chat:
                            msg.properties.set_prop(messages.PROP_CHAT,chat )
                            msg.properties.set_prop(messages.PROP_ORDER,'')
                            msg.properties.set_prop(messages.PROP_ORDER2,'')
                    #llogger.info("sending to",order.sender.get_position(),msg.position,msg.orientation)
                    buff = msg.send()
                    if len(buff) > 1200: 
                        llogger.warning("ERROR msg size=%d. Not sending" % len(buff))
                    else:
                        self.sendto(buff, aircraft.get_addr())
                    
                    
                except:
                    llogger.exception("Sending msg")
                
            else:
                msg = PosMsg()
                msg.send_from_comm(request.receiver)
                msg.time = self.sim_time()
                msg.lag=0.1
                msg.properties.set_prop(messages.PROP_FREQ, request.receiver.get_FGfreq())
                self.sendto(msg.send(), aircraft.get_addr())
    
        ''' send mp and ai planes positions to player '''
        if not AIPLANES_ENABLED:
            return
         
        for mp in self.get_mpplanes(aircraft):
            if msg and mp.plans.count():
                for p in mp.plans.all():
                    if p.circuit:
                        cir = self.get_circuit(p.circuit.name)
                        if cir: 
                            pos = cir.update(msg.time)
                            self.set_circuit(cir)
                            self.set_aircraft(cir.aircraft)
                            aaa= self.get_aircraft(cir.aircraft.callsign)
                    else:
                        pos = p.update(msg.time)
                    
                    if pos:
                        self.set_pos(pos)
            else:
                pos = self.get_pos(mp.callsign)
            
            if pos:
                pos.time = self.sim_time()
                pos.lag=0.1
                #llogger.info("sending mp",pos.__dict__)
                self.sendto(pos.send(),aircraft.get_addr())
                oid_p = pos.get_property(messages.PROP_OID)
                if oid_p:
                    self.receive_order(mp, oid_p['value'])
                
    def update_aiplanes(self):
        if not AIPLANES_ENABLED:
            return
        
        cont=True
        
        while cont: 
            time.sleep(settings.FGATC_AI_INTERVAL)
            for mp in self.aircrafts.values():
                if mp.plans.count():
                    for p in mp.plans.all():
                        if p.circuit:
                            cir = self.get_circuit(p.circuit.name)
                            if cir: 
                                pos = cir.update(self.sim_time())
                                if not pos.time:
                                    pos.time = self.sim_time()
                                    #print "setting time of %s to %s" % (pos.header.callsign, pos.time)
                                    
#                                 self.set_circuit(cir)
#                                 self.set_aircraft(cir.aircraft)
                                self.set_pos(pos)
                                oid_p = pos.get_property(messages.PROP_OID)
                                if oid_p:
                                    self.receive_order(mp, oid_p['value'])
                        
                    
    
    def sendto(self,data,addr):
        try:
            self.fgsock.sendto(data,addr)
        except:
            pass
            #llogger.info("Error sending to", addr)
        
    def find_comm(self,request):
        
        # fgfs sends integer freqs in Mhz but apt.dat has freqs in 1/100 Mhz (integers) 
        freq = request.get_request().freq
        freq = freq.replace('.','').ljust(5,'0') # replace the dot and add padding
        tag = "%s-%s" % (request.sender.callsign,freq)
        # TODO Clean the cache!!!  
        comm = self.controllers.get(tag,None)
        if comm:
            return comm
        #llogger.debug("Finding COMM for %s" % tag)
        apts = airportsWithinRange(request.sender.get_position(), 50, units.NM)
        #llogger.debug("Airports in range=%s " % apts)
        for apt in apts:
            c = apt.comms.filter(frequency=freq)
            if c.count():
                self.controllers[tag]=c.first().id
                return c.first().id
        self.controllers[tag]=None
        return None
    
        
    def process_pos(self,pos):
        
        self.set_pos(pos)
        aircraft = self.get_aircraft(pos.callsign())
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
        if pos.has_property(messages.PROP_FREQ):
            freq = pos.get_value(messages.PROP_FREQ)
            aircraft.freq = freq
        
        #self.set_aircraft(aircraft)
        
        request = pos.get_value(messages.PROP_REQUEST)
        llogger.debug("process request %s. LAST=%s" % (request,aircraft.last_request))
        if request:
            if request != aircraft.last_request:
                llogger.info("aircraft %s requests %s at %s. last=%s" % (aircraft.callsign, request, freq,aircraft.last_request) )
                aircraft.last_request = request
                self.set_aircraft(aircraft)
                req = Request(sender=aircraft,date=timezone.now(),request=request)
                req.receiver_id = self.find_comm(req)
                llogger.info("receiver=%s" % req.receiver )
                req.save()
        oid = pos.get_value(messages.PROP_OID)
        if oid:
            self.receive_order(aircraft, oid)
        return True
    
    def process_request(self,instance):
        if instance.receiver:
            llogger.debug("Processing request %s " % instance)
            controller = get_controller(instance.receiver)
            controller.manage(instance)
            self.check_circuits(controller)
        else:
            llogger.warning("Ignoring request without receiver %s " % instance)

