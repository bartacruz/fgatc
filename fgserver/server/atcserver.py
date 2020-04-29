'''
Created on 20 mar. 2019

@author: julio
'''
import socketserver
import threading
import django
from queue import Queue, Empty
from django.utils import timezone


django.setup()

from fgserver.models import Airport, Order, Aircrafts, AircraftStatus
from fgserver.messages import PosMsg, sim_time
from fgserver import llogger, settings, setInterval
from fgserver.server.fgmpie import pie_msg, PacketData
from fgserver.signals import message_received, signal_server_started
from fgserver.server.utils import get_pos_msg, process_msg
    
class FGServer(socketserver.ThreadingMixIn, socketserver.UDPServer):
    incoming = Queue()
    outgoing = Queue()
    _thread = None
    
    def init(self):
        self._thread = threading.Thread(target=self.serve_forever)
        self._thread.daemon = True
        server_thread.start()
    
    
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
            #process_msg(pos)
            self.server.incoming.put(pos)
        except:
            llogger.exception("While receiving message")

def startup_tasks():
    Order.objects.all().update(expired=True)
    


@setInterval(0.3)
def send_msg():
    for airport in Airport.objects.filter(active=True):
        msg = get_pos_msg(airport)
        #llogger.debug("Sending pos for AI ATC   %s" % msg)
        server.outgoing.put(msg)
    
    from fgserver.ai.models import FlightPlan
    for plan in FlightPlan.objects.filter(enabled=True):
        try:
            pos = plan.aircraft.status.get_position_message()
            server.outgoing.put(pos)
        except AircraftStatus.DoesNotExist:
            AircraftStatus(aircraft=plan.aircraft, date=timezone.now()).save()
            pos = plan.aircraft.status.get_position_message()
            server.outgoing.put(pos)
        except:
            llogger.exception("In loop")
         
        
#     else:
#         diff =(timezone.now() - (aircraft.updated or timezone.now())).total_seconds()
#             if diff < 2:
#                 #print("saving",aircraft.__dict__)
#                 aircraft.save()
    
if __name__ == "__main__":
    HOST, PORT = "0.0.0.0", 5100
    
    server = FGServer((HOST, PORT), FGHandler)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    
    startup_tasks()
    
    try:
        server_thread.start()
        signal_server_started.send_robust(None)
        print("Server started at {} port {}".format(HOST, PORT))
        send_msg()
        while True:
            try:
                pos = server.incoming.get(True, .1)
                message_received.send_robust(sender=server,msg=pos)
                process_msg(pos)
                
            except Empty:
                pass
            try:
                msg = server.outgoing.get(False)
                #llogger.debug("Sending message %s" % msg )
                buff = pie_msg(msg)
                server.socket.sendto(buff,settings.FGATC_RELAY_SERVER)
            except Empty:
                pass
        
    except (KeyboardInterrupt, SystemExit):
        server.shutdown()
        server.server_close()
        exit()
