'''
Created on 27 abr. 2020

@author: julio
'''
from django.dispatch.dispatcher import Signal

message_received=Signal(providing_args=["msg"])
signal_order_sent=Signal(providing_args=["order"])
signal_order_expired=Signal(providing_args=["order"])
signal_order_receved=Signal(providing_args=["order"])
signal_order_acked=Signal(providing_args=["order"])
signal_order_lost=Signal(providing_args=["order"])
signal_server_started=Signal()