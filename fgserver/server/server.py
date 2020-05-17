'''
Created on 3 may. 2020

@author: julio
'''
import socketserver
import threading
import time
import logging
from queue import Queue, Empty

from django.conf import settings

from fgserver.messages import PosMsg
from .fgmpie import pie_msg, PacketData

llogger = logging.getLogger(__name__)

class FGServer():
    port = 5020
    
    def __init__(self, delay=0.5, port=None):
        port = port or FGServer.port
        server_address = ("0.0.0.0", port)
        self.server_to = settings.FGATC_RELAY_SERVER
        self.delay=delay
        FGServer.port = FGServer.port +1
        llogger.debug("Client address %s:%s" % server_address)
        self.server = FGUDPServer(server_address,FGHandler)
 
    def init(self):
        
        self._thread = threading.Thread(target=self.server.serve_forever)
        self._thread.daemon = True
        self._thread.start()
        self._sender_thread = threading.Thread(target=self.sender_task)
        self._sender_thread.daemon = True
        self._sender_thread.start()
        self.after_init()
    
    def after_init(self):
        raise NotImplemented()
    
    def get_position_message(self):
        raise NotImplemented()
        
    def sender_task(self):
        while True:
            try:
                msg = self.get_position_message()
                #llogger.debug("Sending message to %s:" % msg.get_property(messages.PROP_FREQ) )
                buff = pie_msg(msg)
                self.server.socket.sendto(buff,self.server_to)
                time.sleep(self.delay)
            except Empty:
                pass
   
    def put(self,msg):
        self.server.outgoing.put(msg)
    
    def get(self,msg):
        self.server.incoming.get(msg)    


class FGUDPServer(socketserver.ThreadingMixIn, socketserver.UDPServer):
    ''' 
    Subclasses must implement get_position_message()
    '''
    incoming = Queue()
    outgoing = Queue()
    _thread = None

    
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
            self.server.incoming.put(pos)
        except:
            llogger.exception("While receiving message")

    
