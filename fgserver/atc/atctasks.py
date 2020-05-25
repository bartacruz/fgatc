'''
Created on 21 may. 2020

@author: julio
'''
import django
django.setup()

from fgserver.atc.controllers import Requests, process_request


def process_queued_request(instance):
    print("request received",instance)
    process_request(instance,instance)
    

Requests.listen(process_queued_request)