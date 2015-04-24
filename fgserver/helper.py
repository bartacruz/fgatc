# -*- encoding: utf-8 -*-
'''
Created on Apr 13, 2015

@author: bartacruz
'''

from math import sqrt, fabs, atan2, pi, sin, cos, asin, acos
from fgserver.settings import METAR_URL
from metar.Metar import Metar
import urllib
from geographiclib.geodesic import Geodesic
from scipy import rint
from __builtin__ import float

LETTERS = [
"alpha", "bravo", "charlie", "delta", "echo",
"foxtrot", "golf", "hotel", "india", "juliet",
"kilo", "lima", "mike", "november", "oscar",
"papa", "quebec", "romeo", "sierra", "tango",
"uniform", "victor", "whiskey", "xray", "yankee", "zulu"
]
orders = []
ERAD = 6378138.12
RAD = 180 / pi
EPSILON = 0.0000000000001

    
def short_callsign(callsign):
        return "%s %s %s" % (LETTERS[ord(callsign[0].lower()) - ord('a')],
                             LETTERS[ord(callsign[1].lower()) - ord('a')],
                             LETTERS[ord(callsign[2].lower()) - ord('a')]
                             )

def normdeg(a):
    while a >= 180:
        a -= 360
    while a < -180:
        a += 360
    return a

def normalize(a):
    while a > 360:
        a -= 360
    while a < 0:
        a += 360
    return a
    
def geod2cart(geod):
    
    _SQUASH = 0.9966471893352525192801545
    e2 = fabs(1 - _SQUASH * _SQUASH)
    a = ERAD
    phi = geod[0]/RAD
    _lambda = geod[1]/RAD
    h = geod[2]
    sphi = sin(phi)
    n = a / sqrt(1 - e2 * sphi * sphi)
    cphi = cos(phi)
    slambda = sin(_lambda)
    clambda = cos(_lambda)
    cart = [(h + n) * cphi * clambda, (h + n) * cphi * slambda, (h + n - e2 * n) * sphi]
    return cart
def mod(n, m):
    x = n - m * rint(n / m)
    if x < 0:
        return x + abs(m)
    return x

def move(position, course, dist, alt):
    #print ("move %s,course=%s,dist=%s,alt=%s" % (position.get_array(),course,dist,alt))
    course = float(course)/ RAD
    dist = float(dist) / ERAD
    alt = float(alt)
    #position = position.to_cart()
    lat = position.x/RAD
    lon = position.y/RAD
    lat = asin(sin(lat) * cos(dist)
                        + cos(lat) * sin(dist) * cos(course));
    if cos(lat) > EPSILON:
        lon = pi - mod(pi - lon - asin(sin(course) * sin(dist)
                                / cos(lat)), 2 * pi);
    lat = lat * RAD
    lon = lon * RAD
    return Position(lat,lon,alt)

def cart2geod(cart):
    _EQURAD = 6378137.0
    _SQUASH = 0.9966471893352525192801545
    _STRETCH = 1.0033640898209764189003079
    _POLRAD = 6356752.3142451794975639668
    E2 = fabs(1 - _SQUASH * _SQUASH)
    ra2 = 1 / (_EQURAD * _EQURAD)
    e2 = E2;
    e4 = E2 * E2
    X = cart[0]
    Y = cart[1]
    Z = cart[2]
    XXpYY = X * X + Y * Y
    sqrtXXpYY = sqrt(XXpYY)
    p = XXpYY * ra2
    q = Z * Z * (1 - e2) * ra2
    r = 1 / 6.0 * (p + q - e4)
    s = e4 * p * q / (4 * r * r * r)
    if s >= -2.0 and s <= 0.0:
        s = 0.0
    t = pow(1 + s + sqrt(s * (2 + s)), 1 / 3.0)
    u = r * (1 + t + 1 / t)
    v = sqrt(u * u + e4 * q)
    w = e2 * (u + v - q) / (2 * v)
    k = sqrt(u + v + w * w) - w
    D = k * sqrtXXpYY / (k + e2)
    lon = 2 * atan2(Y, X + sqrtXXpYY) * RAD
    sqrtDDpZZ = sqrt(D * D + Z * Z);
    lat = 2 * atan2(Z, D + sqrtDDpZZ) * RAD
    alt = (k + e2 - 1) * sqrtDDpZZ / k
    return [lat, lon, alt]

def fetch_metar(icao):
    try:
        url = "%s/%s.TXT" % (METAR_URL, icao)
        urlh = urllib.urlopen(url)
        for line in urlh:
            if line.startswith(icao):
                obs = Metar(line)
                #print obs
                return obs
    except:
        pass
    print "NO METAR FOR %s" % icao
    return None

class Vector3D():
    x = 0
    y = 0
    z = 0
    def __init__(self, x=0,y=0,z=0):
        self.x = x
        self.y = y
        self.z = z

    def get_array(self):
        return [self.x,self.y,self.z]

    def add(self,b):
        return Vector3D(self.x+b.x, self.y + b.y, self.z + b.z)

    def substract(self,b):
        return Vector3D(self.x-b.x, self.y -b.y, self.z - b.z)
    def scale(self,b):
        return Vector3D(self.x*b, self.y*b, self.z*b)
    def get_length(self):
        return sqrt(self.x*self.x + self.y*self.y + self.z*self.z)
    def normalise(self):
        length = self.get_length()
        if length < 1e-22:
            return Vector3D(0,0,0)
        return Vector3D(self.x/length,self.y/length,self.z/length)
    
    def __unicode__(self):
        return "%s"%self.get_array()

class Position(Vector3D):
    def get_array_cart(self):
        return geod2cart(self.get_array())
    def to_cart(self):
        c = self.get_array_cart()
        return Position(c[0],c[1],c[2])
    @staticmethod
    def fromV3D(v3d):
        return Position(v3d.x,v3d.y,v3d.z)
    
class Quaternion():
    w=0
    x=0
    y=0
    z=0
    def __init__(self,w=0,x=0,y=0,z=0):
        self.w = w
        self.x=x
        self.y=y
        self.z=z
        
    def magnitude(self):
        return sqrt(self.w*self.w+self.x*self.x+self.y*self.y+self.z*self.z)
    
    def get_angle(self):
        return acos(self.w)*2.0*RAD
    
    def get_axis(self):
        angle=acos(self.w)
        sina=sin(angle)
        return Vector3D(self.x/sina,self.y/sina,self.z/sina)
    def get_angle_axis(self):
        angle=acos(self.w)
        sina=sin(angle)
        norm=self.magnitude()
        return Vector3D(2.0*angle*self.x/(sina*norm),2.0*angle*self.y/(sina*norm),2.0*angle*self.z/(sina*norm))
    def normalize(self):
        m=self.magnitude()
        return Quaternion(self.w/m,self.x/m,self.y/m,self.z/m)
    def inverse(self):
        m=self.magnitude()
        return Quaternion(self.w/m,-self.x/m,-self.y/m,-self.z/m)

    def conjugate(self):
        return Quaternion(self.w,-self.x,-self.y,-self.z)
    

    def add(self,q):
        return Quaternion(self.w+q.w,self.x+q.x,self.y+q.y,self.z+q.z)

    def multiply(self, q):
        return Quaternion(self.w*q.w-self.x*q.x-self.y*q.y-self.z*q.z,
                              self.w*q.x+q.w*self.x+self.y*q.z-self.z*q.y,
                              self.w*q.y+q.w*self.y+self.z*q.x-self.x*q.z,
                              self.w*q.z+q.w*self.z+self.x*q.y-self.y*q.x)

    @staticmethod
    def fromEulerAngles(z, y, x):
        # sequence is z,y,x
        z=float(z)
        y=float(y)
        x=float(x)
        cosz2=cos(z/RAD/2.0)
        sinz2=sin(z/RAD/2.0)
        cosy2=cos(y/RAD/2.0)
        siny2=sin(y/RAD/2.0)
        cosx2=cos(z/RAD/2.0)
        sinx2=sin(x/RAD/2.0)

        cosz2cosy2=cosz2*cosy2
        sinz2siny2=sinz2*siny2
        cosz2siny2=cosz2*siny2
        sinz2cosy2=sinz2*cosy2

        return Quaternion(cosz2cosy2*cosx2+sinz2siny2*sinx2,
                              cosz2cosy2*sinx2-sinz2siny2*cosx2,
                              cosz2siny2*cosx2+sinz2cosy2*sinx2,
                              sinz2cosy2*cosx2-cosz2siny2*sinx2)
    @staticmethod
    def fromYawPitchRoll(yaw, pitch, roll):
        return Quaternion.fromEulerAngles(yaw, pitch, roll)

    @staticmethod
    def fromLatLon(lat, lon):
        # sequence is z, y
        lat = float(lat)
        lon=float(lon)
        z2= lon/RAD/2.0
        y2= -1 * pi/4.0-lat/RAD/2.0
        cosz2=cos(z2)
        sinz2=sin(z2)
        cosy2=cos(y2)
        siny2=sin(y2)
        return Quaternion(cosz2*cosy2,-sinz2*siny2,cosz2*siny2,sinz2*cosy2)

meter = 1
def get_distance(fro, to, unit=meter):
    info = Geodesic.WGS84.Inverse(fro.x, fro.y, to.x, to.y)
    return info['s12'] * unit

def get_heading_to(fro, to):
    info = Geodesic.WGS84.Inverse(fro.x, fro.y, to.x, to.y)
    heading = info['azi2']
    if heading > 360.0:
        heading = heading - 360.0
    return heading
