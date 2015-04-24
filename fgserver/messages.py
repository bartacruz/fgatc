# -*- encoding: utf-8 -*-
'''
Created on Apr 16, 2015

@author: julio
'''
from xdrlib import Packer
import helper

PROP_FREQ = 10001
PROP_CHAT = 10116
PROP_REQUEST = 10117
PROP_ORDER = 10118

PROPERTIES = {
  100: {'node': 'surface-positions/left-aileron-pos-norm', 'type':'FLOAT'},
  101: {'node': 'surface-positions/right-aileron-pos-norm', 'type':'FLOAT'},
  102: {'node': 'surface-positions/elevator-pos-norm', 'type':'FLOAT'},
  103: {'node': 'surface-positions/rudder-pos-norm', 'type':'FLOAT'},
  104: {'node': 'surface-positions/flap-pos-norm', 'type':'FLOAT'},
  105: {'node': 'surface-positions/speedbrake-pos-norm', 'type':'FLOAT'},
  106: {'node': 'gear/tailhook/position-norm', 'type':'FLOAT'},
  107: {'node': 'gear/launchbar/position-norm', 'type':'FLOAT'},
  108: {'node': 'gear/launchbar/state', 'type':'STRING'},
  109: {'node': 'gear/launchbar/holdback-position-norm', 'type':'FLOAT'},
  110: {'node': 'canopy/position-norm', 'type':'FLOAT'},
  111: {'node': 'surface-positions/wing-pos-norm', 'type':'FLOAT'},
  112: {'node': 'surface-positions/wing-fold-pos-norm', 'type':'FLOAT'},

  200: {'node': 'gear/gear[0]/compression-norm', 'type':'FLOAT'},
  201: {'node': 'gear/gear[0]/position-norm', 'type':'FLOAT'},
  210: {'node': 'gear/gear[1]/compression-norm', 'type':'FLOAT'},
  211: {'node': 'gear/gear[1]/position-norm', 'type':'FLOAT'},
  220: {'node': 'gear/gear[2]/compression-norm', 'type':'FLOAT'},
  221: {'node': 'gear/gear[2]/position-norm', 'type':'FLOAT'},
  230: {'node': 'gear/gear[3]/compression-norm', 'type':'FLOAT'},
  231: {'node': 'gear/gear[3]/position-norm', 'type':'FLOAT'},
  240: {'node': 'gear/gear[4]/compression-norm', 'type':'FLOAT'},
  241: {'node': 'gear/gear[4]/position-norm', 'type':'FLOAT'},

  300: {'node': 'engines/engine[0]/n1', 'type':'FLOAT'},
  301: {'node': 'engines/engine[0]/n2', 'type':'FLOAT'},
  302: {'node': 'engines/engine[0]/rpm', 'type':'FLOAT'},
  310: {'node': 'engines/engine[1]/n1', 'type':'FLOAT'},
  311: {'node': 'engines/engine[1]/n2', 'type':'FLOAT'},
  312: {'node': 'engines/engine[1]/rpm', 'type':'FLOAT'},
  320: {'node': 'engines/engine[2]/n1', 'type':'FLOAT'},
  321: {'node': 'engines/engine[2]/n2', 'type':'FLOAT'},
  322: {'node': 'engines/engine[2]/rpm', 'type':'FLOAT'},
  330: {'node': 'engines/engine[3]/n1', 'type':'FLOAT'},
  331: {'node': 'engines/engine[3]/n2', 'type':'FLOAT'},
  332: {'node': 'engines/engine[3]/rpm', 'type':'FLOAT'},
  340: {'node': 'engines/engine[4]/n1', 'type':'FLOAT'},
  341: {'node': 'engines/engine[4]/n2', 'type':'FLOAT'},
  342: {'node': 'engines/engine[4]/rpm', 'type':'FLOAT'},
  350: {'node': 'engines/engine[5]/n1', 'type':'FLOAT'},
  351: {'node': 'engines/engine[5]/n2', 'type':'FLOAT'},
  352: {'node': 'engines/engine[5]/rpm', 'type':'FLOAT'},
  360: {'node': 'engines/engine[6]/n1', 'type':'FLOAT'},
  361: {'node': 'engines/engine[6]/n2', 'type':'FLOAT'},
  362: {'node': 'engines/engine[6]/rpm', 'type':'FLOAT'},
  370: {'node': 'engines/engine[7]/n1', 'type':'FLOAT'},
  371: {'node': 'engines/engine[7]/n2', 'type':'FLOAT'},
  372: {'node': 'engines/engine[7]/rpm', 'type':'FLOAT'},
  380: {'node': 'engines/engine[8]/n1', 'type':'FLOAT'},
  381: {'node': 'engines/engine[8]/n2', 'type':'FLOAT'},
  382: {'node': 'engines/engine[8]/rpm', 'type':'FLOAT'},
  390: {'node': 'engines/engine[9]/n1', 'type':'FLOAT'},
  391: {'node': 'engines/engine[9]/n2', 'type':'FLOAT'},
  392: {'node': 'engines/engine[9]/rpm', 'type':'FLOAT'},

  800: {'node': 'rotors/main/rpm', 'type':'FLOAT'},
  801: {'node': 'rotors/tail/rpm', 'type':'FLOAT'},
  810: {'node': 'rotors/main/blade[0]/position-deg', 'type':'FLOAT'},
  811: {'node': 'rotors/main/blade[1]/position-deg', 'type':'FLOAT'},
  812: {'node': 'rotors/main/blade[2]/position-deg', 'type':'FLOAT'},
  813: {'node': 'rotors/main/blade[3]/position-deg', 'type':'FLOAT'},
  820: {'node': 'rotors/main/blade[0]/flap-deg', 'type':'FLOAT'},
  821: {'node': 'rotors/main/blade[1]/flap-deg', 'type':'FLOAT'},
  822: {'node': 'rotors/main/blade[2]/flap-deg', 'type':'FLOAT'},
  823: {'node': 'rotors/main/blade[3]/flap-deg', 'type':'FLOAT'},
  830: {'node': 'rotors/tail/blade[0]/position-deg', 'type':'FLOAT'},
  831: {'node': 'rotors/tail/blade[1]/position-deg', 'type':'FLOAT'},

  900: {'node': 'sim/hitches/aerotow/tow/length', 'type':'FLOAT'},
  901: {'node': 'sim/hitches/aerotow/tow/elastic-constant', 'type':'FLOAT'},
  902: {'node': 'sim/hitches/aerotow/tow/weight-per-m-kg-m', 'type':'FLOAT'},
  903: {'node': 'sim/hitches/aerotow/tow/dist', 'type':'FLOAT'},
  904: {'node': 'sim/hitches/aerotow/tow/connected-to-property-node', 'type':'BOOL'},
  905: {'node': 'sim/hitches/aerotow/tow/connected-to-ai-or-mp-callsign', 'type':'STRING'},
  906: {'node': 'sim/hitches/aerotow/tow/brake-force', 'type':'FLOAT'},
  907: {'node': 'sim/hitches/aerotow/tow/end-force-x', 'type':'FLOAT'},
  908: {'node': 'sim/hitches/aerotow/tow/end-force-y', 'type':'FLOAT'},
  909: {'node': 'sim/hitches/aerotow/tow/end-force-z', 'type':'FLOAT'},
  930: {'node': 'sim/hitches/aerotow/is-slave', 'type':'BOOL'},
  931: {'node': 'sim/hitches/aerotow/speed-in-tow-direction', 'type':'FLOAT'},
  932: {'node': 'sim/hitches/aerotow/open', 'type':'BOOL'},
  933: {'node': 'sim/hitches/aerotow/local-pos-x', 'type':'FLOAT'},
  934: {'node': 'sim/hitches/aerotow/local-pos-y', 'type':'FLOAT'},
  935: {'node': 'sim/hitches/aerotow/local-pos-z', 'type':'FLOAT'},

  1001: {'node': 'controls/flight/slats', 'type':'FLOAT'},
  1002: {'node': 'controls/flight/speedbrake', 'type':'FLOAT'},
  1003: {'node': 'controls/flight/spoilers', 'type':'FLOAT'},
  1004: {'node': 'controls/gear/gear-down', 'type':'FLOAT'},
  1005: {'node': 'controls/lighting/nav-lights', 'type':'FLOAT'},
  1006: {'node': 'controls/armament/station[0]/jettison-all', 'type':'BOOL'},

  1100: {'node': 'sim/model/variant', 'type':'INT'},
  1101: {'node': 'sim/model/livery/file', 'type':'STRING'},

  1200: {'node': 'environment/wildfire/data', 'type':'STRING'},
  1201: {'node': 'environment/contrail', 'type':'INT'},

  1300: {'node': 'tanker', 'type':'INT'},

  1400: {'node': 'scenery/events', 'type':'STRING'},

  1500: {'node': 'instrumentation/transponder/transmitted-id', 'type':'INT'},
  1501: {'node': 'instrumentation/transponder/altitude', 'type':'INT'},
  1502: {'node': 'instrumentation/transponder/ident', 'type':'BOOL'},
  1503: {'node': 'instrumentation/transponder/inputs/mode', 'type':'INT'},

  10001: {'node': 'sim/multiplay/transmission-freq-hz', 'type':'STRING'},
  10002: {'node': 'sim/multiplay/chat', 'type':'STRING'},

  10100: {'node': 'sim/multiplay/generic/string[0]', 'type':'STRING'},
  10101: {'node': 'sim/multiplay/generic/string[1]', 'type':'STRING'},
  10102: {'node': 'sim/multiplay/generic/string[2]', 'type':'STRING'},
  10103: {'node': 'sim/multiplay/generic/string[3]', 'type':'STRING'},
  10104: {'node': 'sim/multiplay/generic/string[4]', 'type':'STRING'},
  10105: {'node': 'sim/multiplay/generic/string[5]', 'type':'STRING'},
  10106: {'node': 'sim/multiplay/generic/string[6]', 'type':'STRING'},
  10107: {'node': 'sim/multiplay/generic/string[7]', 'type':'STRING'},
  10108: {'node': 'sim/multiplay/generic/string[8]', 'type':'STRING'},
  10109: {'node': 'sim/multiplay/generic/string[9]', 'type':'STRING'},
  10110: {'node': 'sim/multiplay/generic/string[10]', 'type':'STRING'},
  10111: {'node': 'sim/multiplay/generic/string[11]', 'type':'STRING'},
  10112: {'node': 'sim/multiplay/generic/string[12]', 'type':'STRING'},
  10113: {'node': 'sim/multiplay/generic/string[13]', 'type':'STRING'},
  10114: {'node': 'sim/multiplay/generic/string[14]', 'type':'STRING'},
  10115: {'node': 'sim/multiplay/generic/string[15]', 'type':'STRING'},
  10116: {'node': 'sim/multiplay/generic/string[16]', 'type':'STRING'},
  10117: {'node': 'sim/multiplay/generic/string[17]', 'type':'STRING'},
  10118: {'node': 'sim/multiplay/generic/string[18]', 'type':'STRING'},
  10119: {'node': 'sim/multiplay/generic/string[19]', 'type':'STRING'},

  10200: {'node': 'sim/multiplay/generic/float[0]', 'type':'FLOAT'},
  10201: {'node': 'sim/multiplay/generic/float[1]', 'type':'FLOAT'},
  10202: {'node': 'sim/multiplay/generic/float[2]', 'type':'FLOAT'},
  10203: {'node': 'sim/multiplay/generic/float[3]', 'type':'FLOAT'},
  10204: {'node': 'sim/multiplay/generic/float[4]', 'type':'FLOAT'},
  10205: {'node': 'sim/multiplay/generic/float[5]', 'type':'FLOAT'},
  10206: {'node': 'sim/multiplay/generic/float[6]', 'type':'FLOAT'},
  10207: {'node': 'sim/multiplay/generic/float[7]', 'type':'FLOAT'},
  10208: {'node': 'sim/multiplay/generic/float[8]', 'type':'FLOAT'},
  10209: {'node': 'sim/multiplay/generic/float[9]', 'type':'FLOAT'},
  10210: {'node': 'sim/multiplay/generic/float[10]', 'type':'FLOAT'},
  10211: {'node': 'sim/multiplay/generic/float[11]', 'type':'FLOAT'},
  10212: {'node': 'sim/multiplay/generic/float[12]', 'type':'FLOAT'},
  10213: {'node': 'sim/multiplay/generic/float[13]', 'type':'FLOAT'},
  10214: {'node': 'sim/multiplay/generic/float[14]', 'type':'FLOAT'},
  10215: {'node': 'sim/multiplay/generic/float[15]', 'type':'FLOAT'},
  10216: {'node': 'sim/multiplay/generic/float[16]', 'type':'FLOAT'},
  10217: {'node': 'sim/multiplay/generic/float[17]', 'type':'FLOAT'},
  10218: {'node': 'sim/multiplay/generic/float[18]', 'type':'FLOAT'},
  10219: {'node': 'sim/multiplay/generic/float[19]', 'type':'FLOAT'},

  10300: {'node': 'sim/multiplay/generic/int[0]', 'type':'INT'},
  10301: {'node': 'sim/multiplay/generic/int[1]', 'type':'INT'},
  10302: {'node': 'sim/multiplay/generic/int[2]', 'type':'INT'},
  10303: {'node': 'sim/multiplay/generic/int[3]', 'type':'INT'},
  10304: {'node': 'sim/multiplay/generic/int[4]', 'type':'INT'},
  10305: {'node': 'sim/multiplay/generic/int[5]', 'type':'INT'},
  10306: {'node': 'sim/multiplay/generic/int[6]', 'type':'INT'},
  10307: {'node': 'sim/multiplay/generic/int[7]', 'type':'INT'},
  10308: {'node': 'sim/multiplay/generic/int[8]', 'type':'INT'},
  10309: {'node': 'sim/multiplay/generic/int[9]', 'type':'INT'},
  10310: {'node': 'sim/multiplay/generic/int[10]', 'type':'INT'},
  10311: {'node': 'sim/multiplay/generic/int[11]', 'type':'INT'},
  10312: {'node': 'sim/multiplay/generic/int[12]', 'type':'INT'},
  10313: {'node': 'sim/multiplay/generic/int[13]', 'type':'INT'},
  10314: {'node': 'sim/multiplay/generic/int[14]', 'type':'INT'},
  10315: {'node': 'sim/multiplay/generic/int[15]', 'type':'INT'},
  10316: {'node': 'sim/multiplay/generic/int[16]', 'type':'INT'},
  10317: {'node': 'sim/multiplay/generic/int[17]', 'type':'INT'},
  10318: {'node': 'sim/multiplay/generic/int[18]', 'type':'INT'},
  10319: {'node': 'sim/multiplay/generic/int[19]', 'type':'INT'}
}

def encode_node(unp,node):
    packers={'INT': unp.pack_uint,
               'BOOL': unp.pack_uint,
               'LONG': unp.pack_uint,
               'FLOAT': unp.pack_float,
               'DOUBLE': unp.pack_double,
               'STRING': unp.pack_string,
    }
    #print "packing a ",node
    unp.pack_uint(node['id'])
    if node['type'] == 'STRING':
        val = node['value']
        aux = len(val)
        unp.pack_uint(aux)
        aux2 = (aux+3)//4*4
        for s in val:
            unp.pack_uint(ord(s))
        for i in range(aux2-aux):
            unp.pack_uint(0)
    else:
        return packers[node['type']](node['value'])

def decode_node(unp):
    unpackers={'INT': unp.unpack_uint,
               'BOOL': unp.unpack_uint,
               'LONG': unp.unpack_uint,
               'FLOAT': unp.unpack_float,
               'DOUBLE': unp.unpack_double,
    }
    
    pid = unp.unpack_uint()
    if PROPERTIES.has_key(pid):
        prop = PROPERTIES[pid].copy()
        prop['id']=pid
        ptype = prop["type"]
        if ptype == 'STRING':
            aux = unp.unpack_uint()
            aux2 = (aux+3)//4*4
            val = ''
            for i in range(aux2):
                #unp.set_position(unp.get_position()+4)
                s = unp.unpack_uint()
                if (s > 0):
                    val=val + chr(s)          
        else: 
            val = unpackers[ptype]()
        prop['value']=val
        return prop
    else:
        print "Propiedad invalida: %d" % pid
        return None
    
class Header:
    magic=0x46474653
    version=0x00010001
    msgid=7
    msglen=0
    reply_addr=0
    reply_port=0
    callsign = None
    
    def receive(self,unp):
        self.magic = unp.unpack_uint()
        self.version = unp.unpack_uint()
        self.msgid = unp.unpack_uint()
        self.msglen = unp.unpack_uint()
        unp.unpack_uint() # reply_addr
        unp.unpack_uint() # reply_port
        self.callsign = unp.unpack_fstring(8).replace('\0','')
         
    def send(self):
        unp = Packer()
        unp.pack_uint(self.magic)
        unp.pack_uint(self.version)
        unp.pack_uint(self.msgid)
        unp.pack_uint(self.msglen)
        unp.pack_uint(0) # reply_addr y reply_port
        unp.pack_uint(0) # reply_addr y reply_port
        unp.pack_fstring(8,self.callsign)
        return unp.get_buffer()

    def __str__(self):
        return "magic=%s, version=%s, msgid=%s, msglen=%s, addr=%s, port=%s, callsign=%s" % (self.magic,self.version,self.msgid,self.msglen,self.reply_addr,self.reply_port,self.callsign)

class PropertyData:
    properties = {}
    def __init__(self):
        self.properties = {}
        
    def get(self,key):
        return self.properties.get(key)
    def get_value(self,key):
        return self.properties.get(key)['value']
    def set(self,key,prop):
        self.properties[key]=prop
    def has_key(self,key):
        return self.properties.has_key(key)
    def set_prop(self,key,value):
        prop = PROPERTIES.get(key)
        prop['value']=value
        prop['id']=key
        self.set(key, prop)
    
    def receive(self,unp,end):
        while unp.get_position() < end:
            prop = decode_node(unp)
            if prop:# -*- encoding: utf-8 -*-

                self.properties[prop['id']]=prop
                #print prop
    def send(self,unp):
        for key in self.properties:
            prop = self.get(key)
            encode_node(unp, prop)
            
    
class PosMsg:
    header = None
    properties = None
    model = None
    time = None
    lag = None
    position=[0,0,0]
    orientation=[0.1,0.1,0.1]
    linear_vel=[0,0,0]
    angular_vel=[0,0,0]
    linear_accel=[0,0,0]
    angular_accel=[0,0,0]
    def __init__(self):
        self.header = Header()
        self.properties = PropertyData()
    
    def get_request(self):
        r = self.get_property(PROP_REQUEST)
        if r:
            return r
        return None
        
    def send_from(self,apt):
        self.header.callsign=apt.icao
        self.model="ATC"
        self.time = 0
        self.lag = 0
        self.position=apt.get_position().get_array_cart()
    def addr(self):
        return (self.header.reply_addr,self.header.reply_port)
    def callsign(self):
        return self.header.callsign
    def request(self):
        return self.get_property(PROP_REQUEST)
    def get_property(self,key):
        return self.properties.get(key)
    def has_property(self,key):
        return self.properties.has_property(key)
    def set_property(self,key,value):
        self.properties.set(key, value)
    def receive(self,unp):
        self.header.receive(unp)
        self.model = unp.unpack_fstring(96).strip()
        self.time=unp.unpack_double()
        self.lag=unp.unpack_double()
        self.position=unp.unpack_farray(3, unp.unpack_double)
        self.orientation=unp.unpack_farray(3, unp.unpack_float)
        self.linear_vel=unp.unpack_farray(3, unp.unpack_float)
        self.angular_vel=unp.unpack_farray(3, unp.unpack_float)
        self.linear_accel=unp.unpack_farray(3, unp.unpack_float)
        self.angular_accel=unp.unpack_farray(3, unp.unpack_float)
        unp.unpack_uint()
        #print "pad",pad
        self.properties.receive(unp,self.header.msglen)

    def send(self):
        unp = Packer()
        unp.pack_fstring(96,self.model)
        unp.pack_double(self.time)
        unp.pack_double(self.lag)
        unp.pack_farray(3, self.position, unp.pack_double)
        unp.pack_farray(3, self.orientation,unp.pack_float)
        unp.pack_farray(3, self.linear_vel,unp.pack_float)
        unp.pack_farray(3, self.angular_vel,unp.pack_float)
        unp.pack_farray(3, self.linear_accel,unp.pack_float)
        unp.pack_farray(3, self.angular_accel,unp.pack_float)
        unp.pack_uint(0)
        self.properties.send(unp)
        msgbuf = unp.get_buffer()
        headbuf = self.header.send()
        self.header.msglen=len(headbuf+msgbuf)
        #print "setting len=",self.header.msglen
        headbuf = self.header.send()
        return headbuf + msgbuf
        
    def __str__(self):
        return "time=%s, position=%s, model=%s" % (self.time,self.position,self.model)