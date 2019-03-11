# -*- encoding: utf-8 -*-
'''
Created on Apr 22, 2015

@author: bartacruz
'''
from django.conf.urls import patterns, url


urlpatterns = patterns('',
    # Examples:
    # url(r'^$', 'fgserver.views.home', name='home'),
    # url(r'^blog/', include('blog.urls')),

    #url(r'^$', 'fgserver.map.views.map_view'),
    url(r'^callsign/', 'fgserver.tracker.views.callsign'),
    #url(r'^flightplan/', 'fgserver.map.views.flightplan'),
)
