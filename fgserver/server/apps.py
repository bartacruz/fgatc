'''
Created on 28 abr. 2020

@author: julio
'''
from django.apps.config import AppConfig
from fgserver.signals import message_received


class ServerConfig(AppConfig):
    name = 'fgserver.server'
    
#     def ready(self):
#         AppConfig.ready(self)
#         
#         from .tasks import do_message_received        
#         
#         message_received.connect( 
#             receiver=do_message_received, 
#             dispatch_uid="server_message_received")
#         print("SERVER HOOKED")