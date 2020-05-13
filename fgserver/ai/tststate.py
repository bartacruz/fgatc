'''
Created on 7 may. 2020

@author: julio
'''

import time
import django
from django.utils import timezone
from random import randint
django.setup()



from fgserver.ai.models import Circuit
from fgserver.messages import alias, sim_time
from fgserver.ai.common import ReceivedOrder, PlaneRequest
from fgserver.ai.state_plane import StatePlane
from fgserver.models import Aircraft, Comm, Airport
from fgserver.ai.dynamics import TurboPropDynamicManager

def init_plane(plan):
    plane = StatePlane(plan.aircraft, TurboPropDynamicManager)
    plane.clearances.start = True
    plane.dynamics.wait(randint(5,40))
    plane.start()
    plane.update(timezone.now())
    plane._request = None
    plane._order = None
    plane._rerouted = False
    return plane

def process_request(plane,request):
    callsign = plane.aircraft.callsign
                
                if request.req == alias.TUNE_IN:
                    freq = int(request.freq.replace(".",''))
                    comm = plane.copilot.get_comm_by_freq(airport, freq)
                    plane._order = ReceivedOrder(apt=airport.icao,to=callsign,ord=alias.TUNE_OK, atc=comm.identifier, freq=request.freq)
                
                elif request.req == alias.TAXI_READY:
                    comm = plane.copilot.get_comm_by_type(airport, Comm.TWR) 
                    rwy = airport.active_runway().name
                    plane._order = ReceivedOrder(apt=airport.icao,to=callsign,ord=alias.TAXI_TO, rwy =rwy, freq=comm.get_FGfreq(),atc=comm.identifier, hld=1,short=1)
                
                elif request.req == alias.HOLDING_SHORT:
                    rwy = airport.active_runway().name
                    if not busy:
                        plane._order = ReceivedOrder(apt=airport.icao,to=callsign,ord=alias.LINEUP, rwy=rwy)
                    else:
                        plane._order = ReceivedOrder(apt=airport.icao,to=callsign,ord=alias.WAIT, rwy=rwy)
                elif request.req == alias.READY_TAKEOFF:
                    rwy = airport.active_runway().name
                    if not busy or busy == plane:
                        plane._order = ReceivedOrder(apt=airport.icao,to=callsign,ord=alias.CLEAR_TK, rwy=rwy)
                        busy = plane
                    else:
                        plane._order = ReceivedOrder(apt=airport.icao,to=callsign,ord=alias.WAIT, rwy=rwy)
                elif request.req == alias.LEAVING:
                    if busy and busy == plane:
                        busy = False
                elif request.req == alias.INBOUND_APPROACH:
                    rwy = airport.active_runway().name
                    plane._order = ReceivedOrder(apt=airport.icao,to=callsign,ord=alias.JOIN_CIRCUIT, rwy=rwy, cirt=alias.CIRCUIT_LEFT,\
                                          cirw = alias.CIRCUIT_CROSSWIND, alt = plan.altitude )
                
                elif request.req == alias.CIRCUIT_CROSSWIND:
                    plane._order = ReceivedOrder(apt=airport.icao,to=callsign,ord=alias.REPORT_CIRCUIT, rwy=rwy,cirw = alias.CIRCUIT_DOWNWIND)
                
                elif request.req == alias.CIRCUIT_DOWNWIND:
                    plane._order = ReceivedOrder(apt=airport.icao,to=callsign,ord=alias.REPORT_CIRCUIT, rwy=rwy,cirw = alias.CIRCUIT_BASE)
                
                elif request.req == alias.CIRCUIT_BASE:
                    plane._order = ReceivedOrder(apt=airport.icao,to=callsign,ord=alias.REPORT_CIRCUIT, rwy=rwy,cirw = alias.CIRCUIT_FINAL)
                
                elif request.req == alias.CIRCUIT_FINAL:
                    if not busy or busy == plane:
                        plane._order = ReceivedOrder(apt=airport.icao,to=callsign,ord=alias.CLEAR_LAND, rwy=rwy,)
                        busy = plane 
                    else:
                        plane._order = ReceivedOrder(apt=airport.icao,to=callsign,ord=alias.GO_AROUND, rwy=rwy,cirw = alias.CIRCUIT_CROSSWIND)
                        plane._rerouted = True
 
    
def dummy_atc(icao):
    airport = Airport.objects.get(icao=icao)
    planes = []
    for plan in airport.circuits.filter(enabled=True):
        plane = init_plane(plan)
        planes.append(plane)
        
    factor =1
    busy = False
    holding = []
    
    while(True):
        time.sleep(.2/factor)
        for plane in planes:   
            status = plane.update(sim_time()*factor)
            status.save()
            if plane._order:
                print("new order=%s" % plane._order)
                plane.process_order(plane._order)
                plane._order = None
            
            if plane.copilot.request == plane._request:
                
                print("new request from copilot %s" % plane.copilot.request)
                request = plane.copilot.request
                plane._request = request
                               
            if plane.is_stopped():
                print("%s is stopped. ")
                planes.remove(plane)
                plane = init_plane(plan)
                
                planes.append(plane)
                 
 
dummy_atc("SABE")
# aircraft = Aircraft.objects.get(callsign="barta")
# print(aircraft.orders.last().order)
# for order in aircraft.orders.all().order_by("-id")[:30]:
#     #order = ReceivedOrder.from_string(ord.order)
#     print(order.order)
# # print(order.__dict__)
# # print(order.ord)
# # print(cont.identifier)
# for req in aircraft.requests.all().order_by("-id")[:30]:
# #     #print(req.request)
#     request = PlaneRequest.from_string(req.request)
# #     #print(request.__dict__)
#     print(request.get_request())
#     #print(eval('{%s}' % aircraft.requests.last().request.replace("=",":").replace(";",",")))
#p = StatePlane(aircraft,TurboPropDynamicManager)


