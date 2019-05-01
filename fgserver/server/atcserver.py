'''
Created on 20 mar. 2019

@author: julio
'''
import socketserver
from fgserver.messages import PosMsg
from fgserver import llogger, settings, setInterval
from xdrlib import Unpacker
from queue import Queue, Empty
import threading
from fgserver.server.testmp import process_msg, get_pos_msg
from fgserver.models import Airport
from fgserver.atc.models import ATC

class FGServer(socketserver.ThreadingMixIn, socketserver.UDPServer):
    incoming = Queue()
    outgoing = Queue()

class FGHandler(socketserver.BaseRequestHandler):
    
    def handle(self):
        data = self.request[0]
        try:
            unp = Unpacker(data)
            pos = PosMsg()
            pos.receive(unp)
            pos.header.reply_addr=self.client_address[0]
            pos.header.reply_port=self.client_address[1]
            #print("Received",pos)
            #process_msg(pos)
            self.server.incoming.put(pos)
        except:
            llogger.exception("While receiving message")

@setInterval(1)
def send_msg():
    for airport in Airport.objects.filter(active=True):
        msg = get_pos_msg(airport)
        server.outgoing.put(msg)
    
if __name__ == "__main__":
    HOST, PORT = "0.0.0.0", 5100
    
    server = FGServer((HOST, PORT), FGHandler)

    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True

    try:
        server_thread.start()
        print("Server started at {} port {}".format(HOST, PORT))
        send_msg()
        while True:
            try:
                pos = server.incoming.get(True, .1)
                process_msg(pos)
            except Empty:
                pass
            try:
                msg = server.outgoing.get(False)
                #llogger.debug("Sending message %s" % msg )
                buff = msg.send()
                if len(buff) > 1200: 
                    llogger.warning("ERROR msg size=%d. Not sending" % len(buff))
                else:
                    server.socket.sendto(msg.send(),settings.FGATC_RELAY_SERVER)
            except Empty:
                pass
        
    except (KeyboardInterrupt, SystemExit):
        server.shutdown()
        server.server_close()
        exit()
