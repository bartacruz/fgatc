'''
Created on 11 mar. 2019

@author: julio
'''
from django.apps.config import AppConfig
from django.db.models.signals import post_save


class ATCConfig(AppConfig):
    name = "fgserver.atc"
    
    def ready(self):
        AppConfig.ready(self)
        from fgserver.models import Request
        from .controllers import publish_request
        post_save.connect(
            sender=Request, 
            receiver=publish_request, 
            dispatch_uid="atc_process_request")
        print("ATC HOOKED", __name__ )
        


