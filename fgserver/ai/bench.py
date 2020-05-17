'''
Created on 9 may. 2020

@author: julio

Bench for testing AI StatePlanes.
Simulates a MP Server and ATC and can run in speed-up time (or speed-down!) 
'''
import django
import time
from django.utils import timezone
django.setup()
from fgserver.server import utils
from fgserver.ai.consumers import StatePlaneConsumer
from fgserver.ai.dynamics import TurboPropDynamicManager
from fgserver.ai.state_plane import StatePlane
from fgserver.models import Airport, Order
from random import randint
from fgserver.messages import sim_time, Clock
from fgserver.server.utils import get_pos_msg, process_message
from fgserver.ai.common import ReceivedOrder

def init_plane(plan):
    ''' Inits a state plane, with a Start clearance and an initial push'''
    plane = StatePlane(plan.aircraft, TurboPropDynamicManager)
    plane.clearances.start = True
    plane.dynamics.wait(randint(5,60))
    plane.update(sim_time())
    plane._saved = timezone.now()
    return plane

    
def dummy_atc(icao):
    
    airport = Airport.objects.get(icao=icao)
    Order.objects.all().update(expired=True)
    planes = []
    
    
    time_factor = 2
    
    # Very accurate clock for sim-time determination
    clock = Clock(time_factor)
    
    ''' Updates ATC message timmings according to time factor '''
    utils.ORDER_DELAY=utils.ORDER_DELAY/(time_factor*2)
    utils.ORDER_MIN_LIFESPAN/(time_factor*2)
    utils.ORDER_MAX_LIFESPAN/(time_factor*2)
    
    ''' Loads all available circuits on the selected airport'''
    for plan in airport.circuits.filter(enabled=True):
        plane = init_plane(plan)
        planes.append(plane)
        plane.start()
        

    while(True): # main loop
        
        time.sleep(.1/time_factor) # 100ms loop, time-factorized 
        
        atcpos = get_pos_msg(airport,clock.time)
        
        strorder = atcpos.get_order() # get last order from ATC
        if strorder:
            order = ReceivedOrder.from_string(strorder)
        else:
            order = None
        
        for plane in planes: # planes loop
            
            status = plane.update(clock.time)
            pos = status.get_position_message()
            
            if (timezone.now()-plane._saved).seconds > 1:
                # Save every second so we dont kill the DB
                plane.aircraft.save()
                plane.aircraft.status.save()
                plane._saved = timezone.now()
                StatePlaneConsumer.publish_plane(plane) # publish to map!
            
            process_message(pos) # check the Pos msg for requests
            
            if order and order.to ==plane.aircraft.callsign:
                plane.process_order(order)

if __name__ == '__main__':
    dummy_atc("SADF")

