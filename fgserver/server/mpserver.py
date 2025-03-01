'''
Created on 6 de may. de 2017

@author: julio
'''
import django
import threading
from queue import Empty
from fgserver import units, setInterval
from fgserver.server.fgmpie import pie_msg
import time
from django.utils import timezone
from datetime import timedelta
from fgserver.messages import PositionMessages
django.setup()
import logging
from django.conf import settings
from fgserver.models import Airport, Order, Aircrafts, airportsWithinRange,\
    Aircraft, AircraftStatus
from fgserver.server.utils import get_pos_msg, process_message
from fgserver.server.server import FGServer

llogger = logging.getLogger(__name__)

ACTIVE_DELAY=60

@setInterval(10)
def aircraft_updater():
    loaded = list(Aircrafts.keys())
    for active in Aircraft.objects.filter(status__gt=0, updated__gte=timezone.now()-timedelta(seconds=ACTIVE_DELAY)):
        if active.callsign in loaded:
            loaded.remove(active.callsign)
        else:
            print("Loading new: %s" % active)
            Aircrafts.get(active.callsign)
    
    for non_active in loaded:
        print("Removing non-active: %s" % non_active)
        Aircrafts.remove(non_active)
        PositionMessages.remove(non_active)
    
def find_comm(aircraft):
        pos = PositionMessages.get(aircraft.callsign)
        #print("Pos for %s: %s" % (aircraft.callsign,pos,))
        freq = pos.get_frequency() 
        if freq:
            freq = str(freq)[:5]
        #print("Finding COMM for %s (%s)" % (freq, str(freq)[:5]))
        apts = airportsWithinRange(aircraft.get_position(), 50, units.NM)
        llogger.debug("Airports in range=%s " % apts)
        for apt in apts:
            c = apt.comms.filter(frequency=freq)
            if c.count():
                return c.first()
        return None

class MPServer(FGServer):
    
    def __init__(self, delay=0.5, port=None, relay=False):
        FGServer.__init__(self, delay=delay, port=port)
        self.relay = relay
        aircraft_updater()

    def incomming_message(self,pos):
        #print("incomming %s" % pos)
        try:
            PositionMessages.set(pos)
            process_message(pos)
        except:
            llogger.exception("Processing incomming message %s" % pos)

    def after_init(self):
        llogger.debug('Starting server loop')
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

    def get_posmsg_for_plane(self,aircraft):
        comm = find_comm(aircraft)
        if comm:
        #print("relaying %s to %s@%s but %s" % (comm, aircraft,aircraft.get_addr(), aircraft.posmsg.header.reply_addr))
            pos = get_pos_msg(comm.airport)
            #print('airport',pos)
            yield pos
        #print(aircraft,list(Aircrafts.get_near(aircraft)))
        for other in Aircrafts.get_near(aircraft):
            pos = PositionMessages.get(other.callsign)
            #print("sending %s to %s" % (pos.callsign(), aircraft,))
            if pos:
                yield pos
            else:
                status = AircraftStatus.objects.get(aircraft=other)
                yield status.get_position_message()
        
        
    def sender_task(self):
        while True:
            try:
                for callsign in list(Aircrafts.keys()):
                    #print("updating %s" % callsign)
                    aircraft = Aircrafts.get(callsign)
                    if not hasattr(aircraft, 'posmsg'):
                        # Probably AI aircraft 
                        continue
                    for pos in self.get_posmsg_for_plane(aircraft):
                        try:
                            addr = aircraft.get_addr()
                            if not addr:
                                continue
                            if hasattr(pos,'buff'):
                                buff = pos.buff
                            else:
                                buff = pie_msg(pos)
        
                            if len(buff) > 2000:
                                print("super long message",pos)
                            self.server.socket.sendto(buff,addr)
                        except Exception:
                            llogger.exception("Sending to %s:  %s" % (callsign,str(pos),))
                time.sleep(self.delay)
            except (KeyboardInterrupt, SystemExit):
                self.server.shutdown()
                self.server.server_close()
                exit()
            except Empty:
                pass
            except:
                llogger.exception("On sender_task")

if __name__ == '__main__':
    server = MPServer(.1, 5100)
    server.thread = threading.Thread(target=server.init)
    server.thread.start()

