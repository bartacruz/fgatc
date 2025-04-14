'''
Created on 28 abr. 2020

@author: julio
'''

import logging
import time
import threading

from django.conf import settings
from django.utils import timezone
from random import randint
from fgserver.celery import app
from fgserver.atc.models import Order
from fgserver.server.utils import process_message
from fgserver.messages import sim_time, PositionMessages
from fgserver.ai.state_plane import StatePlane
from fgserver.ai.consumers import StatePlaneConsumer
from fgserver.ai.common import ReceivedOrder

llogger = logging.getLogger(__name__)
loop_enabled = True

def init_plane(plan):
    ''' Inits a state plane, with a Start clearance and an initial push'''
    plane = StatePlane(plan, init_delay=randint(20,120))
    plane.clearances.start = True
    #plane.dynamics.wait(randint(5,60))
    plane.update(sim_time())
    plane._saved = timezone.now()
    return plane

def stateplanes_loop():
    from fgserver.ai.models import FlightPlan
    global loop_enabled
    delay = getattr(settings,'FGATC_CIRCUITS_DELAY',0.2)
    llogger.info('Starting AI stateplanes loop')
    planes = {}
    while loop_enabled:
        try:
            for plan in FlightPlan.objects.filter(enabled=True):
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
