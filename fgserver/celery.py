'''
Created on 27 abr. 2020

@author: julio
'''
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fgserver.settings')

app = Celery('fgserver')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.conf.task_routes = {}
app.autodiscover_tasks()