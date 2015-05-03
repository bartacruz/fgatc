import re

from fgserver.helper import short_callsign, say_number
from fgserver.messages import alias
from fgserver.models import Order


templates={
           alias.CLEAR_CROSS:"{cs}, clear to cross airspace above {alt}",
           alias.CLEAR_LAND:"{cs}, clear to land{onum}",
           alias.CLEAR_TK : "{cs}, cleared for take off",
           alias.GO_AROUND : "{cs}, go around, I repeat, go around. Report on {cirw}",
           alias.JOIN_CIRCUIT:"{cs}, join {cirt} hand {cirw} for runway {rwy} at {alt}",
           alias.LINEUP : "{cs}, line up on runway {rwy}{hld}",
           alias.REPORT_CIRCUIT: '{cs}, report on {cirw}, number {num}',
           alias.STARTUP: "{cs}, start up approved. Call when ready to taxi.",
           alias.TAXI_TO: "{cs}, taxi to runway {rwy} {via}{hld}{short}{lineup}",
           alias.WAIT: "{cs}, wait until advised",     
    }
    
def get_message(order):
    msg = templates.get(order.get_instruction())
    if not msg:
        return None
    msg = re.sub(r'{cs}',short_callsign(order.receiver.callsign),msg)
    msg = re.sub(r'{icao}',order.sender.icao,msg)
    msg = re.sub(r'{rwy}',say_number(order.get_param(Order.PARAM_RUNWAY,'')),msg)
    msg = re.sub(r'{alt}',str(order.get_param(Order.PARAM_ALTITUDE,'')),msg)
    msg = re.sub(r'{cirt}',order.get_param(Order.PARAM_CIRCUIT_TYPE,''),msg)
    msg = re.sub(r'{cirw}',order.get_param(Order.PARAM_CIRCUIT_WP,''),msg)
    msg = re.sub(r'{num}',str(order.get_param(Order.PARAM_NUMBER,'')),msg)
    if order.get_param(Order.PARAM_NUMBER):
        msg = re.sub(r'{onum}',', number %s' % order.get_param(Order.PARAM_NUMBER),msg)
    if order.get_param(Order.PARAM_LINEUP):
        msg = re.sub(r'{lineup}',' and line up',msg)
    if order.get_param(Order.PARAM_HOLD):
        msg = re.sub(r'{hld}',' and hold',msg)
    if order.get_param(Order.PARAM_SHORT):
        msg = re.sub(r'{short}',' short',msg)
    
    # Clean up tags not replaced
    msg = re.sub(r'{\w+}','',msg)
    return msg
