'''
Created on Apr 20, 2015

@author: bartacruz
'''
from math import pi
M=1.0
SEC=1.0
KG=1.0
MB=1.0

''' Pressure '''
INHG=33.8653*MB

''' Distances '''
FT=0.3048*M
KM=1000.0*M
NM=1852.0*M

''' Time '''
MIN=60.0*SEC
HOUR=60.0*MIN
''' Frequency '''
HZ=1.0
KHZ=1.0E3*HZ
MHZ=1.0E6*HZ

''' Angles '''
DEG=1.0
RAD=180.0/pi*DEG
FULLCIRCLE=360.0*DEG

''' Velocities '''
MPS=M/SEC
FPM=FT/MIN
KMH=KM/HOUR
KNOTS=NM/HOUR

''' Forces '''
NEWTON=KG*M/(SEC*SEC)
''' Constants '''
g=9.81*NEWTON/KG
ERAD = 6378138.12
EPSILON = 0.0000000000001
