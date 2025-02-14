'''
Created on 27 abr. 2020

@author: julio
'''
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fgserver.settings')

app = Celery('fgserver')
app.conf.update(
    task_serializer='pickle',
    result_serializer='pickle',
    accept_content=['pickle']
)
app.config_from_object('django.conf:settings', namespace='CELERY')
app.conf.task_routes = {
    'fgatc.ai.tasks.*':{'queue':'ai'},
    'fgatc.atc.tasks.*':{'queue':'atc'},
}
app.conf.update(
    task_serializer='pickle',
    result_serializer='pickle',
    accept_content=['pickle']
)

app.autodiscover_tasks()