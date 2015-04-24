# -*- encoding: utf-8 -*-
'''
Created on Apr 24, 2015

@author: bartacruz
'''
from fgserver.models import Airport, Runway
from fgserver.helper import normalize

def rwy_from_aptdat(airport,line):
    rwy = Runway()
    rname = line[3].replace('x','')
    # Runway
    #r,created = Runway.objects.get_or_create(airport__icao=airport.icao, name=designation)
    r = Runway(airport=airport, name=rname)
    r.altitude=airport.altitude
    r.bearing = line[4]
    r.lat = line[1]
    r.lon = line[2]
    r.length = line[5]
    r.width = line[8]
    r.save()
    print r.__dict__
    if not r.name.startswith('H'):
        rbearing = normalize(float(r.bearing)+180)
        rname = str(int(normalize(float(r.name[:2])*10+180)/10))
        if r.name[2:3]=='L':
            rname= rname + "R"
        if r.name[2:3]=='R':
            rname= rname + "L"
             
        rinv = Runway(airport=airport, name=rname)
        rinv.altitude=airport.altitude
        rinv.bearing = rbearing
        rinv.lat = line[1]
        rinv.lon = line[2]
        rinv.length = line[5]
        rinv.width = line[8]
        rinv.save()
        print "I",rinv.__dict__

def import_apts(file):
    import gzip
    f=gzip.open(file,'rb')
    cont = True
    while cont:
        line=f.readline()
        if line.startswith('1 '):
            line = line.strip()
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
            else:
                done=True
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
                        designation = al[3].replace('x','')
                        # Runway
                        #r,created = Runway.objects.get_or_create(airport__icao=airport.icao, name=designation)
                        r = Runway(airport=airport, name=designation)
                        created = True
                        if created:
                            r.altitude=airport.altitude
                            r.bearing = al[4]
                            r.lat = al[1]
                            r.lon = al[2]
                            r.length = al[5]
                            r.width = al[8]
                            r.save()
                            print r.__dict__
                            if not r.name.startswith('H'):
                                rbearing = normalize(float(r.bearing)+180)
                                rname = str(int(normalize(float(r.name[:2])*10+180)/10))
                                if r.name[2:3]=='L':
                                    rname= rname + "R"
                                if r.name[2:3]=='R':
                                    rname= rname + "L"
                                     
                                rinv = Runway(airport=airport, name=rname)
                                rinv.altitude=airport.altitude
                                rinv.bearing = rbearing
                                rinv.lat = al[1]
                                rinv.lon = al[2]
                                rinv.length = al[5]
                                rinv.width = al[8]
                                rinv.save()
                                print "I",rinv.__dict__
                            
                    #TODO: generate runways
                if l.startswith('14 '):
                    #TODO: Generate controller
                    print "found tower %s " % al[5]
                    airport.lat = al[1]
                    airport.lon = al[2]
            airport.save()
            print airport.icao, airport.name, airport.lat, airport.lon,airport.altitude

import_apts("../data/apt.dat.gz")