'''
Created on 28 de abr. de 2017

@author: julio
'''
from tornado import websocket,web,ioloop
from fgserver import llogger, setInterval
from fgserver.models import Aircraft
import json
from django.core.serializers import serialize
import threading

clients = []

class SocketHandler(websocket.WebSocketHandler):
    lat =None
    lon=None
    zoom=0
    
    def update(self,adict):
        for key in adict:
            setattr(self, key,adict[key])
        
    def check_origin(self, origin):
        #llogger.debug("check_origin %s" % origin)
        return True
    
    def open(self, *args, **kwargs):
        llogger.info("WebSocket open %s" % self.request.remote_ip)
        if self not in clients:
            clients.append(self)
    
    def on_close(self):
        llogger.info("WebSocket close %s" % self.request.remote_ip)
        if self in clients:
            clients.remove(self)
    
    def on_message(self, message):
        #llogger.debug("message %s %s" % (self.zoom, message))
        try:
            message_dict = json.loads(message)
            self.update(message_dict)
        except:
            llogger.exception("message %s %s" % (self.request.remote_ip, message))

@setInterval(5)
def update_loop():
    if len(clients) ==0 :
        return
    aircrafts = Aircraft.objects.filter(state__gte=1)
    acfts = []
    for aircraft in aircrafts:
        acfts.append(aircraft)
    message = {'Model':'Aircraft','data':json.loads(serialize('json',acfts))}
    jmessage =json.dumps(message )
    #llogger.debug("updating message: %s" % jmessage)
    for client in clients:
        #llogger.debug("updating client %s [%s]" % (client,client.zoom))
        client.write_message(jmessage)

def start_server_thread():
    try:
        thread = threading.Thread(target=start_server)
        thread.start()
    except:
        llogger.exception("While starting websocket server thread")
       
def start_server(port=8888,url=r'/ws'):
    app = web.Application([(r'/ws', SocketHandler),])
    app.listen(8888)
    loop = update_loop()
    llogger.info("WebSocket update loop started")
    ioloop.IOLoop.instance().start()
    llogger.info("WebSocket IOLoop ended")
    loop.set()
    llogger.info("WebSocket Update loop ended")
    
if __name__ == '__main__':
    start_server()
    