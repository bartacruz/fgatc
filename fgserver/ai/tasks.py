'''
Created on 28 abr. 2020

@author: julio
'''
from fgserver.celery import app

import logging



from django.conf import settings
import time

import threading
from fgserver.messages import sim_time

llogger = logging.getLogger(__name__)

def do_ai_start_loop(**kwargs):
    llogger.debug('Starting AI loop')
    task_ai_start_circuits_loop.apply_async()


def get_circuit(aircraft):
    from fgserver.ai.models import Circuit, Circuits
    
    circuit = Circuit.objects.filter(aircraft=aircraft, enabled=True).first()
    circuit = Circuits.get(circuit.id)
    if not circuit.started():
        circuit.init()
    return circuit


def circuits_loop():
    from fgserver.ai.models import Circuit, Circuits
    
    delay = getattr(settings,'FGATC_CIRCUITS_DELAY',0.5)
    llogger.info('Starting AI circuits loop')
    while True:
        try:
            for c in Circuit.objects.filter(enabled=True):
                #llogger.debug('Updating circuit %s' % c)
                circuit = Circuits.get(c.id)
                if not circuit.started():
                    llogger.info('Starting new AI circuit for %s' % circuit)
                    circuit.init()
                circuit.update(sim_time())
            time.sleep(delay)
        except:
            llogger.exception('In AI loop')
            return

@app.task
def task_ai_start_circuits_loop():
    loop_thread = threading.Thread(target=circuits_loop)
    loop_thread.daemon = True
    loop_thread.start()
    

