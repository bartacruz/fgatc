'''
Created on 11 mar. 2019

@author: julio
'''
import re

from fgserver.helper import short_callsign, say_number
from fgserver.messages import alias
from fgserver.models import Order
from fgserver import get_qnh


templates={
           alias.CLEAR_CROSS:"{cs}, clear to cross airspace above {alt}",
           alias.CLEAR_LAND:"{cs}, runway {rwy}, clear to land{onum}{qnh}",
           alias.CLEAR_TOUCHNGO:"{cs}, runway {rwy}, clear touch and go{onum}{qnh}",
           alias.CLEAR_TK : "{cs}, runway {rwy}, cleared for take off",
           alias.GO_AROUND : "{cs}, go around, I repeat, go around. Report on {cirw}",
           alias.JOIN_CIRCUIT:"{cs}, join {cirt} hand {cirw} for runway {rwy} at {alt}{qnh}",
           alias.CIRCUIT_STRAIGHT:"{cs}, make straight-in approach runway {rwy}, report on {cirw}{qnh} ",
           alias.LINEUP : "{cs}, line up on runway {rwy}{hld}",
           alias.REPORT_CIRCUIT: '{cs}, report on {cirw}, number {num}',
           alias.STARTUP: "{cs}, start up approved{qnh}. Call ready to taxi",
           alias.TAXI_TO: "{cs}, taxi to runway {rwy} {via}{hld}{short}{lineup}",
           alias.WAIT: "{cs}, wait until advised",
           alias.TUNE_TO: "{cs}", 
           alias.SWITCHING_OFF: "{cs} {comm} switching off, good day!",
           alias.TAXI_PARK: "{cs}, taxi to parking {parkn}"
                
    }
    
def get_message(order):
    msg = templates.get(order.get_instruction())
    
    if not msg:
        return None
    if order.get_param(Order.PARAM_CONTROLLER):
        msg = "%s, contact {conn} on {freq}" % msg
    msg = re.sub(r'{cs}',short_callsign(order.receiver.callsign),msg)
    msg = re.sub(r'{icao}',order.sender.airport.icao,msg)
    msg = re.sub(r'{comm}',order.sender.identifier,msg)
    msg = re.sub(r'{rwy}',say_number(order.get_param(Order.PARAM_RUNWAY,'')),msg)
    msg = re.sub(r'{alt}',str(order.get_param(Order.PARAM_ALTITUDE,'')),msg)
    msg = re.sub(r'{cirt}',order.get_param(Order.PARAM_CIRCUIT_TYPE,''),msg)
    msg = re.sub(r'{cirw}',order.get_param(Order.PARAM_CIRCUIT_WP,''),msg)
    msg = re.sub(r'{num}',str(order.get_param(Order.PARAM_NUMBER,'')),msg)
    msg = re.sub(r'{freq}',str(order.get_param(Order.PARAM_FREQUENCY,'')),msg)
    msg = re.sub(r'{conn}',str(order.get_param(Order.PARAM_CONTROLLER,'')),msg)
    msg = re.sub(r'{park}',str(order.get_param(Order.PARAM_PARKING,'')),msg)
    msg = re.sub(r'{parkn}',str(order.get_param(Order.PARAM_PARKING_NAME,'')),msg)
    
    if order.get_param(Order.PARAM_NUMBER):
        msg = re.sub(r'{onum}',', number %s' % order.get_param(Order.PARAM_NUMBER),msg)
    if order.get_param(Order.PARAM_LINEUP):
        msg = re.sub(r'{lineup}',' and line up',msg)
    if order.get_param(Order.PARAM_HOLD):
        msg = re.sub(r'{hld}',' and hold',msg)
    if order.get_param(Order.PARAM_SHORT):
        msg = re.sub(r'{short}',' short',msg)
    qnh = get_qnh(order.sender.airport)
    if qnh:
        msg = re.sub(r'{qnh}','. QNH %s' % say_number(qnh),msg)
        #msg = re.sub(r'{qnh}','. QNH %s' % qnh,msg)
    else:
        msg = re.sub(r'{qnh}','',msg)
    # Clean up tags not replaced
    msg = re.sub(r'{\w+}','',msg)
    return msg
