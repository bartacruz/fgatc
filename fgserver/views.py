'''
Created on 14 mar. 2019

@author: julio
'''
from fgserver import settings
from django.shortcuts import render_to_response
from django.template.context import RequestContext

def home(request):
    template = getattr(settings,'FGATC_HOME_TEMPLATE','home.html')
    return render_to_response(template)
 
    