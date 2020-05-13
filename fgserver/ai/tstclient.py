'''
Created on 3 may. 2020

@author: julio
'''
import django
import threading
import time
from random import randint
django.setup()
from fgserver.ai.models import Circuit
from fgserver.ai.state_plane import StatePlane
from fgserver.ai.dynamics import TurboPropDynamicManager
from fgserver.ai.planes import CircuitClient, StatePlaneClient

clients = []

if __name__ == '__main__':
    for plan in Circuit.objects.filter(enabled=True):
        plane = StatePlane(plan.aircraft, TurboPropDynamicManager)
        plane.clearances.start = True
        plane.dynamics.wait(randint(5,60))
    
        client = StatePlaneClient(plane,.2)
        clients.append(client)
        client.thread = threading.Thread(target=client.init)
        client.thread.start()
        time.sleep(10)
    