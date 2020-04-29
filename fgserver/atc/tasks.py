'''
Created on 28 abr. 2020

@author: julio
'''
from fgserver.celery import app
import logging
from django.utils.module_loading import import_string
from django.conf import settings
llogger = logging.getLogger(__name__)

CONTROLLERS = {}

def get_cached_controller(id):
    return CONTROLLERS.get(id)

def get_controller(comm):
    controller =  get_cached_controller(comm.id)
    if not controller:
        try:
            llogger.debug("Creating controller for %s" % comm)
            clazz = import_string(settings.DEFAULT_CONTROLLERS.get(comm.type))
            llogger.debug("class=%s" % clazz)
            controller = clazz(comm)
            CONTROLLERS[comm.id]=controller
        except:
            llogger.exception("Error al crerar un controller para %s" % comm)
    return controller


def do_process_request(sender, instance, **kwargs):
    task_process_request.apply_async((instance,))

@app.task
def task_process_request(instance):
    if instance.receiver and instance.received and not instance.processed:
        llogger.debug("Processing request %s " % instance)
        controller = get_controller(instance.receiver)
        controller.manage(instance)
        instance.processed=True
        instance.save()
    
