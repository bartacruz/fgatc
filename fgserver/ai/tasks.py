'''
Created on 28 abr. 2020

@author: julio
'''

import logging
import time
import threading

from django.conf import settings
from django.utils import timezone

from fgserver.celery import app
from fgserver.atc.models import Order
from fgserver.server.utils import process_message
from fgserver.messages import sim_time, PositionMessages
from fgserver.ai.state_plane import StatePlane
from fgserver.ai.dynamics import TurboPropDynamicManager
from fgserver.ai.consumers import StatePlaneConsumer
from fgserver.ai.common import ReceivedOrder

llogger = logging.getLogger(__name__)
loop_enabled = True

def do_ai_start_loop(**kwargs):
    llogger.debug('Starting AI loop')
    task_ai_start_circuits_loop.apply_async()

def init_plane(plan):
    ''' Inits a state plane, with a Start clearance and an initial push'''
    plane = StatePlane(plan.aircraft, TurboPropDynamicManager, init_delay=30)
    plane.clearances.start = True
    #plane.dynamics.wait(randint(5,60))
    plane.update(sim_time())
    plane._saved = timezone.now()
    return plane

def get_circuit(aircraft):
    from fgserver.ai.models import Circuit, Circuits
    
    circuit = Circuit.objects.filter(aircraft=aircraft, enabled=True).first()
    circuit = Circuits.get(circuit.id)
    if not circuit.started():
        circuit.init()
    return circuit

def stateplanes_loop():
    from fgserver.ai.models import Circuit, Circuits
    global loop_enabled
    delay = getattr(settings,'FGATC_CIRCUITS_DELAY',0.5)
    llogger.info('Starting AI stateplaes loop')
    planes = {}
    while loop_enabled:
        try:
            for plan in Circuit.objects.filter(enabled=True):
                plane = planes.get(plan.aircraft.callsign)
                if not plane:
                    plane = init_plane(plan)
                    planes[plane.aircraft.callsign]=plane
                status = plane.update(sim_time())
                pos = status.get_position_message()
                PositionMessages.set(pos)
                if (timezone.now()-plane._saved).seconds > 1:
                    # Save every second so we dont kill the DB
                    plane.aircraft.save()
                    plane.aircraft.status.save()
                    plane._saved = timezone.now()
                    StatePlaneConsumer.publish_plane(plane) # publish to map!
            
                process_message(pos) # check the Pos msg for requests
                order = Order.objects.filter(receiver=plane.aircraft, expired=False, received=False, acked=False, lost=False).first()
                if order:
                    received= ReceivedOrder.from_string(order.get_order())
                    plane.process_order(received)

                
            time.sleep(delay)
        except:
            llogger.exception('In AI loop')
            return
                  
def circuits_loop():
    from fgserver.ai.models import Circuit, Circuits
    global loop_enabled
    delay = getattr(settings,'FGATC_CIRCUITS_DELAY',0.5)
    llogger.info('Starting AI circuits loop')
    while loop_enabled:
        try:
            for c in Circuit.objects.filter(enabled=True):
                #llogger.debug('Updating circuit %s' % c)
                circuit = Circuits.get(c.id)
                if not circuit.started():
                    llogger.info('Starting new AI circuit for %s' % circuit)
                    circuit.init()
                
                status = circuit.update(sim_time())
                pos = status.get_position_message()
                process_message(pos) # check the Pos msg for requests

            time.sleep(delay)
        except:
            llogger.exception('In AI loop')
            return

@app.task
def task_ai_start_circuits_loop():
    global loop_enabled
    loop_enabled = True
    loop_thread = threading.Thread(target=stateplanes_loop)
    loop_thread.daemon = True
    loop_thread.start()
    
@app.task
def task_ai_stop_circuits_loop():
    global loop_enabled
    loop_enabled = False
