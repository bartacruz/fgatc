'''
Created on 4 may. 2019

@author: julio
'''
from ajax_select import register, LookupChannel
from fgserver.models import Airport

@register('airports')
class AirportsLookup(LookupChannel):

    model = Airport

    def get_query(self, q, request):
        q = self.model.objects.filter(name__icontains=q).order_by('name') | self.model.objects.filter(icao__icontains=q).order_by('icao')
        return q