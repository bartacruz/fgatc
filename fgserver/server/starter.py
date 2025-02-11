'''
Created on 6 de may. de 2017

@author: julio
'''
import django
import threading
from queue import Empty
django.setup()
import logging
from django.conf import settings
from fgserver.models import Airport, Order
from fgserver.server.utils import get_pos_msg, process_message
from fgserver.server.server import FGServer

llogger = logging.getLogger(__name__)

class ATCClient(FGServer):
    def __init__(self, airport, delay=0.2):
        self.airport=airport
        Order.objects.filter(sender__airport=airport).update(expired=True)
        FGServer.port=5100
        FGServer.__init__(self, delay=delay)
        # self.server_to = settings.FGATC_AI_SERVER
        
    
    def incomming_message(self,pos):
        process_message(pos)
    
    def get_position_message(self):
        pos = get_pos_msg(self.airport)
        return pos

    def after_init(self):
        llogger.debug('Starting client loop')
        while True:
            try:
                pos = self.server.incoming.get(True,.1)
                self.incomming_message(pos)
            except (KeyboardInterrupt, SystemExit):
                self.server.shutdown()
                self.server.server_close()
                exit()
            except Empty:
                pass
            except:
                llogger.exception("On after_init")
    
if __name__ == '__main__':
    airport = Airport.objects.filter(active=True).first()
    client = ATCClient(airport,.5)
    client.thread = threading.Thread(target=client.init)
    client.thread.start()

