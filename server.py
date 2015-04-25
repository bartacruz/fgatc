# -*- encoding: utf-8 -*-
'''
Created on Apr 14, 2015

@author: bartacruz
'''
import socket
from xdrlib import Unpacker
from fgserver.messages import PROP_REQUEST, PROP_FREQ, PosMsg, PROP_CHAT,\
    PROP_ORDER
from fgserver.helper import cart2geod, random_callsign
from django.db.models.signals import post_save
from django.dispatch.dispatcher import receiver
from fgserver.models import Order, Aircraft, Request, Airport
from datetime import datetime
from django.utils import timezone
from fgserver.controllers import get_controller
from random import randint
from fgserver import ai
from django.core.cache import cache, get_cache
import os 
from fgserver.ai.models import Circuit
os.environ['DJANGO_SETTINGS_MODULE'] = 'fgserver.settings' 
import django

orders = {}

def queue_order(order):
    print "queue_order.",order
    orders.setdefault(order.sender.icao,[]).append(order)

def process_queues():
    for apt in orders:
        if len(orders[apt]):
            o = orders[apt][0]
            dif =(timezone.now() - o.date).total_seconds()
            if dif > 5+randint(0,5):
                o = orders[apt].pop(0)
                o.confirmed=True
                print "activating order ",o
                o.save()
                
@receiver(post_save,sender=Request)
def process_request(sender, instance, **kwargs):
    req = instance.get_request()
    airport = Airport.objects.get(icao=req.apt)
    controller = get_controller(airport)
    order= controller.manage(instance)
        
    if order:
        order.date = timezone.now()
        order.sender = airport
        order.receiver = instance.sender
        order.add_param(Order.PARAM_RECEIVER,instance.sender.callsign)
        order.save()
        print "saving order",order
        
        queue_order(order)

def get_mpplanes(apt):
    planes = []
    # TODO: Search by aircraft closeness and radio frequency
    cch = get_cache('default')
    aicircuit = cch.get(apt.icao)
    #print "get_mpplanes",aicircuit,apt
    if aicircuit==None:
        try:
            aicircuit= Circuit.objects.get(airport=apt)
            cch.set(apt.icao,aicircuit)
            aicircuit.reset()
            cch.set(apt.icao,aicircuit)
            print "Circuit loaded:",aicircuit
        except Circuit.DoesNotExist:
            cch.set(apt.icao,'',60)
    elif aicircuit != '':
        planes.append(aicircuit)
        
    return planes

def send_pos(callsign):
    aircraft = Aircraft.objects.get(callsign=callsign)
    request = Request.objects.filter(sender=aircraft).order_by('-date').first()
    if request:
        req = request.get_request()
        apt = Airport.objects.get(icao=req.apt)
        order = Order.objects.filter(sender=apt, confirmed=True).exclude(message='').order_by('-date').first()
        if order:
            msg = PosMsg()
            msg.send_from(order.sender)
            msg.time = sim_time()
            msg.lag=0.1
            msg.properties.set_prop(PROP_ORDER, order.get_order())
            msg.properties.set_prop(PROP_CHAT,order.message )
            
            #print "sending to",order.sender.get_position(),msg.position,msg.orientation
            sendto(msg.send(), aircraft.get_addr())
            
            ''' send mp and ai planes positions to player ''' 
            for mp in get_mpplanes(apt):
                cch = get_cache('default')
                wait = mp._waiting
                #print "mp found:",wait,mp.time
                mp.update(msg.time)
                cch.set(apt.icao,mp)
                if not wait:
                    msg2 = mp.get_pos_message()
                    msg2.time = msg.time
                    msg2.lag=msg.lag
                    #print "time:",msg.time, msg.lag,msg2.position
                    sendto(msg2.send(),aircraft.get_addr())
            
            
                
def sim_time():
    return (timezone.now() - DATE_STARTED).total_seconds()

def sendto(data,addr):
    global fgsock
    try:
        fgsock.sendto(data,addr)
    except:
        pass
        #print "Error sending to", addr

def process_pos(pos):
    request_p = pos.get_property(PROP_REQUEST)
    if not request_p:
        return False
    request = request_p['value']
    aircraft,create = Aircraft.objects.get_or_create(callsign=pos.callsign())
    if create:
        print "New Plane:", aircraft 
    freq = pos.get_property(PROP_FREQ)['value']
    #print "request=", request
    if aircraft.state == 0 or aircraft.ip != pos.header.reply_addr:
        print "setting addr:",pos.header.reply_addr,pos.header.reply_port 
        aircraft.ip=pos.header.reply_addr 
        aircraft.port=pos.header.reply_port
        aircraft.save()
    if request != aircraft.last_request or freq != aircraft.freq or not aircraft.state:
        print "aircraft %s requests %s at %s" % (aircraft.callsign, request, freq) 
        geo = cart2geod(pos.position)
        aircraft.state=1
        geod = cart2geod(pos.position)
        aircraft.lat=geod[0]
        aircraft.lon=geod[1]
        aircraft.altitude=geod[2]
        aircraft.freq = freq
        aircraft.last_request = request
        aircraft.save()
        request = Request(sender=aircraft,date=timezone.now(),request=request)
        request.save()
        return True
    return False

#t = threading.Thread(target=processor, name='Servicio')
DATE_STARTED = timezone.now()

MSG_MAGIC = 0x46474653

# Reset all planes to 0
Aircraft.objects.all().update(state=0)
Order.objects.all().update(confirmed=False)

fgsock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
fglisten = ("localhost",5100)
fgsock.bind(fglisten)

cont = True
while cont:
    data,addr = fgsock.recvfrom(1200)
    #xs= ":".join("{:02x}".format(ord(c)) for c in data)
    unp = Unpacker(data)
    pos = PosMsg()
    pos.receive(unp)
    pos.header.reply_addr=addr[0]
    pos.header.reply_port=addr[1]
    resp = process_pos(pos)
    process_queues()
    send_pos(pos.callsign)
