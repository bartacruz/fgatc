'''
Created on 28 abr. 2020

@author: julio
'''
from fgserver.celery import app

import logging



from django.conf import settings
import time

import threading
from fgserver.messages import sim_time, PosMsg
import socketserver
from queue import Queue, Empty
from fgserver import messages
from fgserver.models import Order
llogger = logging.getLogger(__name__)

def do_ai_process_order(sender, order, **kwargs):
    if order.receiver.plans.filter(enabled=True).count():
        llogger.debug("Received order %s" % order)
        task_ai_process_order.apply_async((order,))

def do_ai_start_loop(**kwargs):
    llogger.debug("Starting AI loop")
    task_ai_start_circuits_loop.apply_async()


def get_circuit(aircraft):
    from fgserver.ai.models import Circuit, Circuits
    
    circuit = Circuit.objects.filter(aircraft=aircraft, enabled=True).first()
    circuit = Circuits.get(circuit.id)
    if not circuit.started():
        circuit.init()
    return circuit

def update_ai_plan(plan):
    pass
#     for plan in FlightPlan.objects.filter(enabled=True):
#         try:
#             pos = plan.aircraft.status.get_position_message()
#             server.outgoing.put(pos)
#         except AircraftStatus.DoesNotExist:
#             AircraftStatus(aircraft=plan.aircraft, date=timezone.now()).save()
#             pos = plan.aircraft.status.get_position_message()
#             server.outgoing.put(pos)
#         except:
#             llogger.exception("In loop")

def circuits_loop():
    from fgserver.ai.models import Circuit, Circuits
    
    delay = getattr(settings,"FGATC_CIRCUITS_DELAY",0.5)
    llogger.info("Starting AI circuits loop")
    while True:
        try:
            for c in Circuit.objects.filter(enabled=True):
                #llogger.debug("Updating circuit %s" % c)
                circuit = Circuits.get(c.id)
                if not circuit.started():
                    llogger.info("Starting new AI circuit for %s" % circuit)
                    circuit.init()
                circuit.update(sim_time())
            time.sleep(delay)
        except:
            llogger.exception("In AI loop")
            return

@app.task
def task_ai_start_circuits_loop():
    loop_thread = threading.Thread(target=circuits_loop)
    loop_thread.daemon = True
    loop_thread.start()
    
        
@app.task
def task_ai_process_order(order):
    llogger.debug("Received order %s" % order)
    circuit = get_circuit(order.receiver)
    circuit.process_order(order)
    

class CircuitHandler():
    def __init__(self,circuit):
        pass
    
class FGServer(socketserver.ThreadingMixIn, socketserver.UDPServer):
    incoming = Queue()
    outgoing = Queue()
    _thread = None
    port = 5020
    
    def __init__(self, circuit, delay=0.2):
        server_address = ("0.0.0.0", FGServer.port)
        self.delay=delay
        self.circuit = circuit
        FGServer.port = FGServer.port +1
        socketserver.UDPServer.__init__(self, server_address , FGHandler(self))
    
    def init(self):
        self._thread = threading.Thread(target=self.serve_forever)
        self._thread.daemon = True
        self._thread.start()
    
    def incomming_task(self):
        while True:
            try:
                pos = self.incoming.get(True,.1)
                if not pos or not pos.get_order():
                    continue
                freq = pos.get_value(messages.PROP_FREQ)
                if not freq or freq != self.circuit.aircraft.status:
                    continue
                try:
                    order = eval(pos.get_order())
                except:
                    continue
                if order[Order.PARAM_RECEIVER]==self.circuit.aircraft.callsign:
                    llogger.debug("Order received: %s" % order)
                    # TODO: call process order
            except:
                pass
                
    def sender_task(self):
        while True:
            try:
                self.circuit.update(sim_time())
                msg = self.circuit.aircraft.status.get_position_message()
                #llogger.debug("Sending message %s" % msg )
                buff = pie_msg(msg)
                self.socket.sendto(buff,settings.FGATC_RELAY_SERVER)
                time.sleep(self.delay)
            except Empty:
                pass
        
    
    def put(self,msg):
        self.outgoing.put(msg)
    
    def get(self,msg):
        self.incoming.get(msg)
    
    
class FGHandler(socketserver.BaseRequestHandler):
    
    def handle(self):
        data = self.request[0]
        try:
            unp = PacketData(data)
            pos = PosMsg()
            pos.receive_pie(unp)
            pos.header.reply_addr=self.client_address[0]
            pos.header.reply_port=self.client_address[1]
            #print("Received",pos)
            #process_msg(pos)
            self.server.incoming.put(pos)
        except:
            llogger.exception("While receiving message")

    
