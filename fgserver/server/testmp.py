'''
Created on 16 mar. 2019

@author: julio
'''
import django
from fgserver.messages import PosMsg
from fgserver import messages, settings, setInterval
from django.utils import timezone
from time import sleep
import socket
from xdrlib import Unpacker
from queue import Queue, Empty
import traceback
django.setup()

from fgserver.models import Airport, Comm


def get_order_strings(string):
    ostring = string
    ostring2=''
    if len(ostring) >=128:
        ostring2 = ostring[127:]
        ostring=ostring[:127]
    return ostring,ostring2    


def sim_time():
        return (timezone.now() - date_started).total_seconds()
    

def get_msg():
    msg = PosMsg()
    msg.send_from_comm(comm)
    #msg.time = self.sim_time()
    msg.time = sim_time()
    msg.lag=0.1
    msg.properties.set_prop(messages.PROP_FREQ, str(comm.get_FGfreq()))
    order = comm.orders.last()    
    if order:
        print(order)
        ostring, ostring2 = get_order_strings(order.get_order())
        msg.properties.set_prop(messages.PROP_ORDER, ostring)
        msg.properties.set_prop(messages.PROP_ORDER2, ostring2)
        
        chat, chat2 = get_order_strings(order.message)
        msg.properties.set_prop(messages.PROP_CHAT,chat )
        msg.properties.set_prop(messages.PROP_CHAT2,chat2 )
    print(msg)
    return msg

@setInterval(.5)
def send_msg():
    msg = get_msg()
    incoming.put(msg)
    print("Put",msg)

icao = "LOWI"
incoming = Queue()

date_started = timezone.now()
airport = Airport.objects.get(icao=icao)
comm = airport.comms.filter(type=Comm.TWR).first()
relaysock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
fglisten = ("localhost",settings.FGATC_SERVER_PORT)
send_msg()
# relaysock.bind(fglisten)
relaysock.setblocking(0)

while relaysock:
    try:
        msg = incoming.get(False)
        print("Sending",type(msg.send()),settings.FGATC_RELAY_SERVER)
        relaysock.sendto(msg.send(), settings.FGATC_RELAY_SERVER)
        print("Sent",msg)
    except Empty:
        pass
    try:
        data,addr = relaysock.recvfrom(1200)
        unp = Unpacker(data)
        pos = PosMsg()
        pos.receive(unp)
        pos.header.reply_addr=addr[0]
        pos.header.reply_port=addr[1]
        if pos.has_property(messages.PROP_FREQ):
            freq = pos.get_property(messages.PROP_FREQ)['value']
            print("FREQ", freq,pos)
        #print("Received",pos)
    except socket.error:
        pass
    
print("end")
 



