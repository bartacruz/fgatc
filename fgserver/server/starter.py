'''
Created on 6 de may. de 2017

@author: julio
'''
import django
django.setup()
    
from django.db.models.signals import post_save
from django.dispatch.dispatcher import receiver
from fgserver.models import Order, Request
from fgserver.server.mpserver import FGServer


@receiver(post_save, sender=Order)
def process_order(sender, instance, **kwargs):
    if not instance.expired and not instance.received:
        server.queue_order(instance)

@receiver(post_save, sender=Request)
def process_request(sender, instance, **kwargs):
    server.process_request(instance)
    
if __name__ == '__main__':
    django.setup()
    server = FGServer()
    server.start()
