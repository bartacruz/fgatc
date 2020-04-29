'''
Created on 1 may. 2019

@author: julio
'''
import threading

import django
django.setup()

from fgserver.ai.models import Circuit, Circuits
from fgserver.models import Aircraft, Airport, Order, Aircrafts
from fgserver.server.atcserver import FGServer, FGHandler
from fgserver.server.testmp import sim_time, get_order_strings
from queue import Empty
from fgserver.server.fgmpie import pie_msg
from fgserver import settings, setInterval, messages, llogger


airport = Airport.objects.get(icao="SABE")
circuit = airport.circuits.filter(enabled=True).first()

circuit._waiting=0


# def process_msg(pos):
#     if not hasattr(circuit, "pos"):
#         return
#     freq = pos.get_value(messages.PROP_FREQ)
#     myfreq = circuit.pos.get_value(messages.PROP_FREQ)
#     if not freq:
#         #print("ignoring request without freq",pos.properties.properties)
#         return
#     if freq != myfreq:
#         #print("ignoring request not on my freq",freq,myfreq)
#         return
#     #print("INCOMMING",pos.properties.properites)
#     ostring1 = pos.get_value(messages.PROP_ORDER)
#     ostring2 = pos.get_value(messages.PROP_ORDER2)
#     if ostring1:
#         order = eval(ostring1+ostring2)
#     else:
#         #print("ignoring msg without order",ostring1,pos.properties.properties)
#         order = None
#     if not order:
#         return
#     
#     receiver = order.get(Order.PARAM_RECEIVER)
#     if receiver !=circuit.aircraft.callsign:
#         return
#     o = Order.objects.get(pk=order.get("oid"))
#     if hasattr(circuit, "_last_order") and o == circuit._last_order:
#         return
#     print("INCOMMING",pos.properties.properties)
#     circuit.process_order(o)

def process_incomming(pos):
    try:
        ostring1 = pos.get_value(messages.PROP_ORDER)
        ostring2 = pos.get_value(messages.PROP_ORDER2)
        order_dict = eval(ostring1+ostring2)
    except:
        return
    
    receiver = order_dict.get(Order.PARAM_RECEIVER)
    circuit = Circuits.get(receiver)
    
    if not circuit:
        llogger.warn("Message for inactive receiver %s " % receiver)
        return
    receiver_freq = pos.get_value(messages.PROP_FREQ)
    circuit_freq = circuit.pos.get_value(messages.PROP_FREQ)
    if not receiver_freq or receiver_freq != circuit_freq:
        #print("ignoring request not on my freq",freq,circuit_freq)
        llogger.warn("Message for %s on %s, but she is tunned to %s " % (receiver,receiver_freq,circuit_freq,))
        return
    #print("INCOMMING",pos.properties.properites)
    order = Order.objects.get(pk=order_dict.get("oid"))
    if hasattr(circuit, "_last_order") and order == circuit._last_order:
        # Already processed
        return
    print("INCOMMING",pos.properties.properties)
    circuit.process_order(order)

def update_circuit(circuit):
    stime = sim_time()
    pos = circuit.update(stime)
    pos.time = stime
    pos.lag=1
    request = circuit.aircraft.requests.last()
    if request:
        pos.properties.set_prop(messages.PROP_REQUEST, request.request)
    circuit.pos = pos
    return pos

@setInterval(1)
def circuits_loop():
    enabled = [circuit for circuit in Circuit.objects.filter(enabled=True, airport__active=True)]
    for circuit in Circuits.values():
        if circuit not in enabled:
            llogger.info("Removing circuit %s" % circuit)
            Circuits.remove(circuit.aircraft.callsign)
            continue
        
        enabled.remove(circuit)
        
        pos = update_circuit(circuit)
        server.outgoing.put(pos)
    
    for circuit in enabled:
        # Enabled but not yet active
        llogger.info("Starting circuit %s" % circuit)
        circuit.init()
        Circuits.set(circuit.aircraft.callsign, circuit)
        
        pos = update_circuit(circuit)
        server.outgoing.put(pos)
    


    

HOST, PORT = "0.0.0.0", 5200
    
server = FGServer((HOST, PORT), FGHandler)

server_thread = threading.Thread(target=server.serve_forever)
server_thread.daemon = True

try:
    server_thread.start()
    print("Server started at {} port {}".format(HOST, PORT))
    circuits_loop()
    while True:
        try:
            pos = server.incoming.get(True, .1)
            process_incomming(pos)
        except Empty:
            pass
        try:
            msg = server.outgoing.get(False)
            #llogger.debug("Sending message %s" % msg )
            buff = pie_msg(msg)
            server.socket.sendto(buff,settings.FGATC_RELAY_SERVER)
        except Empty:
            pass
    
except (KeyboardInterrupt, SystemExit):
    server.shutdown()
    server.server_close()
    exit()
    