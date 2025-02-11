'''
Created on 27 abr. 2020

@author: julio
'''
from django.dispatch.dispatcher import Signal

message_received=Signal()
signal_order_sent=Signal()
signal_order_expired=Signal()
signal_order_receved=Signal()
signal_order_acked=Signal()
signal_order_lost=Signal()
signal_server_started=Signal()
signal_posmsg = Signal()