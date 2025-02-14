'''
Created on 21 may. 2020

@author: julio
'''
import django
from fgserver.celery import app
from fgserver.atc.controllers import Requests, process_request
import logging
llogger = logging.getLogger(__name__)

# def process_queued_request(instance):
#     print("Atctasks: request received",instance)
#     process_request(instance,instance)
    
def process_request_async(sender, instance,  **kwargs):
    task_process_request.apply_async(args=[instance], queue="atc")

# Requests.listen(process_queued_request)
@app.task
def task_process_request(instance):
    process_request(instance,instance)
    llogger.info("request received %s" % instance)
print("ATC TASKS HOOKED")