# -*- encoding: utf-8 -*-
'''
Created on Apr 24, 2015

@author: bartacruz
'''
from fgserver.models import Airport, Runway
from fgserver.helper import normalize
import re


def rwys_from_aptdat(airport,line):
    ''' 
    Decodes a runway from FG apt.dat and his opposite too 
        - airport is an fgserver.Airport instance
        - line is an array with the line of apt.dat already splitted
    returns an array with the runways suited to use in Runway.objects.bulk_create
    
    WARNING: it'll take a couple of minutes to import all the database!
    '''
    
    runways=[]
    
    # get rid of the extra x's
    rname = line[3].replace('x','')
    #r,created = Runway.objects.get_or_create(airport__icao=airport.icao, name=designation)
    r = Runway(airport=airport, name=rname)
    r.altitude=airport.altitude
    r.bearing = line[4]
    r.lat = line[1]
    r.lon = line[2]
    r.length = line[5]
    r.width = line[8]
    runways.append(r)
    #print r.__dict__
    rwy_match = re.compile("(\d+)([RL]*)").match(r.name) # e.g.:31x, 18R, 8xx
    
    ''' If it's not an helipad, calculate the opposite runway '''
    if rwy_match:
        oname,oside = rwy_match.groups()
        obearing = normalize(float(r.bearing)+180) # the opposite bearing
        oname = str(int(normalize(float(oname)*10+180)/10)) #the opposite name
        oname +={'R':'L','L':'R'}.get(oside) # rwy side vodoo ;-) 
        rinv = Runway(airport=airport, name=oname)
        rinv.bearing = obearing
        ''' The original runway lat/lon mark the center of the rwy, which is the same for the opposite.''' 
        rinv.lat = r.lat
        rinv.lon = r.lon
        ''' ditto for length, altitude and with. ''' 
        rinv.length = r.length
        rinv.altitude=r.altitude
        rinv.width = r.width
        runways.append(rinv)
        #print "I",rinv.__dict__
    return runways

def import_apts(file):
    import gzip
    f=gzip.open(file,'rb')
    cont = True
    while cont:
        line=f.readline()
        line = line.decode('iso-8859-1').encode('utf8').strip()
        if line.startswith('99'):
            cont= False
        elif line.startswith('1 '):
            #print line
            aline = line.split(None,5)
#            print aline
            airport,created = Airport.objects.get_or_create(icao = aline[4])
            #airport.icao=aline[4]
            if created:
                airport.name = aline[5]
                airport.altitude=aline[1]
                airport.save()
                done = False
                runways=[]
                while not done:
                    l = f.readline()
                    if l == '\n':
                        done=True
                        break
                    l = l.strip()
                    al = l.split(None)
                    if l.startswith('10 '):
                        if not airport.lat:
                            airport.lat = al[1]
                            airport.lon = al[2]
                        if al[3] != 'xxx':
                            runways += rwys_from_aptdat(airport, al)
                    if l.startswith('14 '):
                        #TODO: Generate controller
                        print "found tower %s " % al[5]
                        airport.lat = al[1]
                        airport.lon = al[2]
                airport.save()
                Runway.objects.bulk_create(runways)
                print airport.icao, airport.name, airport.lat, airport.lon,airport.altitude, len(runways)

#import_apts("../data/apt.dat.gz")