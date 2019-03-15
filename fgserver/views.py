'''
Created on 14 mar. 2019

@author: julio
'''
from fgserver import settings
from django.shortcuts import render

def home(request):
    template = getattr(settings,'FGATC_HOME_TEMPLATE','home.html')
    return render(request,template)
 
    