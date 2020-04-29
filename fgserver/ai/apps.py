'''
Created on 11 mar. 2019

@author: julio
'''
import logging
from django.apps.config import AppConfig
from fgserver.signals import signal_order_sent, signal_server_started

from fgserver.celery import app
#

logger = logging.getLogger(__name__)

class AIConfig(AppConfig):
    name = "fgserver.ai"
    
    
    def ready(self):
        AppConfig.ready(self)
        from fgserver.ai.tasks import do_ai_process_order
        from fgserver.ai.tasks import do_ai_start_loop
        
        signal_order_sent.connect(
            do_ai_process_order,
            dispatch_uid="ai_process_order")
        signal_server_started.connect(
            do_ai_start_loop,
            dispatch_uid="ai_start_loop")
        logger.debug("Hooked")
        app.conf.task_routes['fgserver.ai.tasks.*']={'queue':'ai'}
        