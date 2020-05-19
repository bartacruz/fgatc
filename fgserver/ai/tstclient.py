'''
Created on 3 may. 2020

@author: julio
'''
import django
import threading
import time
from random import randint
import sys
django.setup()
from fgserver.ai.models import Circuit
from fgserver.ai.state_plane import StatePlane
from fgserver.ai.dynamics import TurboPropDynamicManager
from fgserver.ai.planes import CircuitClient, StatePlaneClient

clients = []

if __name__ == '__main__':
    if len(sys.argv) >1:
        plan = Circuit.objects.get(aircraft__callsign=sys.argv[1])
    else:
        plan = Circuit.objects.filter(enabled=True).first()
    if len(sys.argv) >2:
        port = int(sys.argv[2])
    else:
        port = None
    #for plan in Circuit.objects.filter(enabled=True):
    plane = StatePlane(plan.aircraft, TurboPropDynamicManager, init_delay=randint(30,120))
    

    client = StatePlaneClient(plane,.2, port)
    clients.append(client)
    client.thread = threading.Thread(target=client.init)
    client.thread.start()
    time.sleep(10)
    