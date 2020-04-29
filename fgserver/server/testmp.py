'''
Created on 16 mar. 2019

@author: julio
'''
import django
from fgserver.messages import PosMsg
from fgserver import settings, setInterval
import socket
from xdrlib import Unpacker
from queue import Queue, Empty
import logging
from fgserver.server.utils import process_msg, get_pos_msg

django.setup()

from fgserver.models import Airport, Comm

MAX_TEXT_SIZE=768

llogger = logging.getLogger(__name__)



@setInterval(1)
def send_msg():
    msg = get_pos_msg(airport)
    incoming.put(msg)
    #print("Put",msg)


if __name__ == "__main__":
    

    icao = "SAZV"
    incoming = Queue()
    airport = Airport.objects.get(icao=icao)
    comm = airport.comms.filter(type=Comm.TWR).first()
    relaysock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    fglisten = ("localhost",settings.FGATC_SERVER_PORT)
    send_msg()
    # relaysock.bind(fglisten)
    relaysock.setblocking(0)
    llogger.info("Starting")
    while relaysock:
        try:
            msg = incoming.get(False)
            #print("Sending",type(msg.send()),settings.FGATC_RELAY_SERVER)
            relaysock.sendto(msg.send(), settings.FGATC_RELAY_SERVER)
            #print("Sent",msg)
        except Empty:
            pass
        try:
            data,addr = relaysock.recvfrom(1200)
            unp = Unpacker(data)
            pos = PosMsg()
            pos.receive(unp)
            pos.header.reply_addr=addr[0]
            pos.header.reply_port=addr[1]
            #print("Received",pos)
            process_msg(pos)
        except BlockingIOError:
            pass
        
    print("end")
 



