'''
Created on 11 mar. 2019

@author: julio
'''
from django.apps.config import AppConfig
from django.db.models.signals import post_save
from fgserver.atc.tasks import do_process_request

class ATCConfig(AppConfig):
    name = "fgserver.atc"
    
    def ready(self):
        AppConfig.ready(self)
        from fgserver.models import Request
        post_save.connect(
            sender=Request, 
            receiver=do_process_request, 
            dispatch_uid="atc_process_request")
        print("ATC HOOKED")
        
