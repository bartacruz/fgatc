'''
Created on 27 abr. 2020

@author: julio
'''

from fgserver.celery import app
from fgserver import messages
from fgserver.models import Aircraft, Request
import logging
from django.utils import timezone
from fgserver.server.utils import find_comm

llogger = logging.getLogger(__name__)

def do_message_received(sender, msg, **kwargs):
    task_message_received.apply_async((msg,))
    
@app.task
def task_message_received(msg):
    aircraft = Aircraft.objects.get(callsign=msg.callsign())    
    freq = msg.get_value(messages.PROP_FREQ)
    if not freq:
        #llogger.debug("Ignoring request without freq from %s" % aircraft)
        return
    request = msg.get_value(messages.PROP_REQUEST)
    if not request:
        #llogger.debug("Avoiding null request")
        return
    last_r = aircraft.requests.filter(received=True).last()
    if last_r and request == last_r.request:
        #llogger.debug("Avoiding request already processed %s | %s" % (request, last_r,))
        return
    llogger.info("aircraft %s on %s requests %s" % (aircraft.callsign, freq, request) )
    
    req = Request(sender=aircraft,date=timezone.now(),request=request, received=True)
    req.receiver_id = find_comm(req)
    if not req.receiver:
        llogger.debug("Receiver for %s on %s not found" % (aircraft,freq,))
        req.processed=True
    try:
        req.save()
        llogger.debug("Saved request %s" % req)
    except:
        llogger.exception("Al guardar req %s" % req)
    