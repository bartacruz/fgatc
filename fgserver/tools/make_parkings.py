#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys

def latc(lat):
    if lat < 0:
        return "S%d %f"%(int(abs(lat)), (abs(lat) - int(abs(lat)) )* 60)
    else:
        return "N%d %f"%(int(abs(lat)), (abs(lat) - int(abs(lat)) )* 60)
def lonc(lon):
    if lon < 0:
        return "W%d %f"%(int(abs(lon)), (abs(lon) - int(abs(lon)) )* 60)
    else:
        return "E%d %f"%(int(abs(lon)), (abs(lon) - int(abs(lon)) )* 60)

infile = open(sys.argv[1], 'r', encoding="iso-8859-1")

airport = sys.argv[2]

found = False

for line in infile:
        line = line.strip()
        # 1 for airports, 16 for seaports
        if line.startswith("1 ") or line.startswith("16 "):
                if " %s "%airport in line:
                        found = True
                        break

if not found:
        print("Airport not found")
        sys.exit(1)


# Here, we are at the airport

import re
# There are two lines that describe parkings: line 15 and line 1300
pattern15 = re.compile(r"^15\s*([\-0-9\.]*)\s*([\-0-9\.]*)\s*([\-0-9\.]*)\s*(.*)$")
pattern1300 = re.compile(r"^1300\s*([\-0-9\.]*)\s*([\-0-9\.]*)\s*([\-0-9\.]*)\s*(\w*)\s*([\w|]*)\s*(.*)$")
pattern1201 = re.compile(r"^1201\s*([\-0-9\.]*)\s*([\-0-9\.]*)\s*([\w*\.]*)\s*([\-0-9\.]*)\s*(.*)$")
pattern1202 = re.compile(r"^1202\s*(\d+)\s*(\d+)\s*(\w+)\s*(\w+)\s*(.*)$")                                                                                            
parkings = []
nodes = []
ways = []
for line in infile:                                                                                                                                             
        line = line.strip()                                                                                                                                     
        # If the airport description ends, break                                                                                                               
        if line.startswith("1 "):                                                                                                                               
                break                                                                                                                                           
                                                                                                                                                               
        lat = -555                                                                                                                                             
        lon = -555
        heading = 0
        # Math line 15
        if pattern15.match(line):
            result = pattern15.match(line)
            lat = float(result.group(1))
            lon = float(result.group(2))
            heading = float(result.group(3))
            name = result.group(4).replace(' ', '_')
            parkings.append((latc(lat), lonc(lon), heading, name),)
        # Match line 1300
        elif pattern1300.match(line):
            result = pattern1300.match(line)
            lat = float(result.group(1))
            lon = float(result.group(2))
            heading = float(result.group(3))
            # group 4 has the type of aircraft and group 5 is services available at the parking
            name = result.group(6).replace(' ', '_')
            parkings.append((latc(lat), lonc(lon), heading, name),)
        elif pattern1201.match(line):
            result = pattern1201.match(line)
            lat = float(result.group(1))
            lon = float(result.group(2))
            both = result.group(3)
            index = float(result.group(4))
            name = result.group(5).replace(' ', '_').strip()
            nodes.append((latc(lat), lonc(lon), both, index, name),)
        elif pattern1202.match(line):
            result = pattern1202.match(line)
            node1 = result.group(1)
            node2 = result.group(2)
            oneway = result.group(3) == 'oneway'
            onrunway = 1 if result.group(4).replace(' ', '_').strip() == 'runway' else 0
            name = result.group(5).replace(' ', '_').strip()
            ways.append((node1,node2,onrunway,name))
            if not oneway:
                ways.append((node2,node1,onrunway,name,))
            
infile.close()

i = 0
print('<?xml version="1.0"?>\n<groundnet>\n  <version>1</version>\n  <parkingList>')
for p in parkings:
        print('    <Parking index="%d" type="gate" name="%s" lat="%s" lon="%s" heading="%f" />'%(i, p[3], p[0], p[1], p[2]))
        i = i + 1
print("</parkingList>")
print("<TaxiNodes>")
for p in nodes:
    print('    <node index="%d" lat="%s" lon="%s" name="%s" isOnRunWay="%s" holdPointType="%s" />'%(i+p[3], p[0], p[1], p[4],0,"none"))
print("</TaxiNodes>\n")
print("<TaxiWaySegments>")
for p in ways:
    print('    <arc begin="%s" end="%s" isPushBackRoute="%d" name="%s" />'% ( i+int(p[0]), i+int(p[1]), p[2],p[3]))
print("</TaxiWaySegments>")
print("</groundnet>")
