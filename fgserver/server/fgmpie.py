'''
Created on 1 may. 2019

@author: julio
'''

#
# Part of this code is shamelessly borrowed from the ATC-pie project,
# and modified to suit our needs.
# 
# Copyright (C) 2015  Michael Filhol <mickybadia@gmail.com> (ATC-pie)
# Copyright (C) 2019  Julio Santa Cruz <bartacruz@gmail.com> (FGAtc)
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301  USA
#

import struct
from datetime import timedelta


# ---------- Constants ----------

fgms_string_encoding = 'utf8'
maximum_packet_size = 2048
dodgy_character_substitute = '_'

FGMS_live_ACFT_time = timedelta(seconds=2) # after which ACFT is considered disconnected (to appear as "?" on next sweep)
FGMS_connection_timeout = timedelta(seconds=60) # after which ACFT is considered a disconnected zombie (to be removed)
timestamp_ignore_maxdiff = 10 # s (as specified in FGMS packets)
fgms_listen_timeout = 1 # seconds

los_min_dist = 20 # NM (minimum line-of-sight radio propagation)

# FGMS packet type codes
position_message_type_code = 7

v2_magic_padding = bytes.fromhex('1face002')
v2_version_prop_value = 2

# -------------------------------

def some(value, fallback):
    if value != None:
        return value
    return fallback

def FGMS_prop_code_by_name(name):
    return next(code for code, data in FGMS_properties.items() if data[0] == name)

def scaled_float(nv, scale):
    nv *= scale
    if nv >= 32767: return 32767
    if nv <= -32767: return -32767
    return int(nv)

class FgmsType:
    all_types = V1_Bool, V1_Int, V1_Float, V1_String, V2_NoSend, V2_LikeV1, \
            V2_ShortInt, V2_ShortFloat, V2_ShortFloat1, V2_ShortFloat3, V2_ShortFloat4, V2_BoolArray = range(12)
    v2_tightly_packed_types = [V1_Bool, V1_String, V2_ShortInt, V2_ShortFloat, V2_ShortFloat1, V2_ShortFloat3, V2_ShortFloat4]

class PacketData:
    '''
    Data packer/unpacker for FGFS stuff
    Includes funny FGFS behaviour like little endian ints and big endian doubles,
    "buggy strings" (encoded with int sequences), etc.
    '''
    def __init__(self, data=None):
        self.data = some(data, bytes(0))
    
    def __len__(self):
        return len(self.data)
    
    def allData(self):
        return self.data

    def peek_bytes(self, nbytes):
        return self.data[:nbytes]

    def pop_bytes(self, nbytes):
        popped = self.data[:nbytes]
        self.data = self.data[nbytes:]
        if len(popped) < nbytes:
            print('WARNING: Truncated packet detected. Expected %d bytes; only %d could be read.' % (nbytes, len(popped)))
            return bytes(nbytes)
        return popped
    
    def append_bytes(self, raw_data):
        self.data += raw_data
    
    def append_packed(self, data):
        self.data += data.allData()
    
    def pad(self, block_multiple):
        pad = block_multiple - (len(self) % block_multiple)
        self.append_bytes(bytes(pad % block_multiple))
    
    ## Low-level packing
    
    def pack_int(self, i):
        self.data += struct.pack('!i', i)
    def pack_float(self, f):
        self.data += struct.pack('!f', f)
    def pack_double(self, d):
        self.data += struct.pack('!d', d)
    def pack_padded_string(self, size, string): # For padded null-terminated string
        self.data += struct.pack('%ds' % size, bytes(string, encoding=fgms_string_encoding)[:size-1])
    
    def pack_ffloat(self,arr):
        ''' packs an array of floats '''
        for f in arr:
            self.pack_float(f)
            
    def pack_fdouble(self,arr):
        ''' packs an array of doubles '''
        for f in arr:
            self.pack_double(f)
    
    ## Low-level unpacking
    def unpack_int(self):
        return struct.unpack('!i', self.pop_bytes(4))[0]
    def unpack_float(self):
        return struct.unpack('!f', self.pop_bytes(4))[0]
    def unpack_double(self):
        return struct.unpack('!d', self.pop_bytes(8))[0]
    def unpack_padded_string(self, size):
        return self.pop_bytes(size).split(b'\x00', 1)[0].decode(encoding=fgms_string_encoding)
    def unpack_ffloat(self,size):
        ''' Unpacks an array of floats '''
        return [self.unpack_float() for i in range(size)]
    def unpack_fdouble(self,size):
        ''' Unpacks an array of doubles '''
        return [self.unpack_double() for i in range(size)]
        
    ## High-level property packing
    
    def pack_property(self, prop_code, prop_value, legacy_protocol):
        prop_name, prop_type_v1, prop_type_v2, prop_marked_v2 = FGMS_properties[prop_code]
        if legacy_protocol or prop_type_v2 == FgmsType.V2_LikeV1:
            prop_type = prop_type_v1
        else: # use v2 encoding
            prop_type = prop_type_v2
        buf = PacketData()
        if not legacy_protocol and prop_type in FgmsType.v2_tightly_packed_types: # TIGHT: pack code and value in same 4-byte int
            if prop_type == FgmsType.V2_ShortInt or prop_type == FgmsType.V1_Bool:
                if prop_type == FgmsType.V2_ShortInt:
                    if prop_value > 0xffff:
                        raise ValueError('Short int v2 prop %d overflow: %d; discarded.' % (prop_code, prop_value))
                    right_value = prop_value
                else: # prop_value is a bool
                    right_value = int(prop_value)
            elif prop_type == FgmsType.V2_ShortFloat:
                right_value = scaled_float(prop_value, 32767)
            elif prop_type == FgmsType.V2_ShortFloat1:
                right_value = scaled_float(prop_value, 10)
            elif prop_type == FgmsType.V1_String:
                right_value = len(prop_value or "")
            else: # ATC-pie should not need: V2_ShortFloat3, V2_ShortFloat4
                raise ValueError('Unhandled tight packing of prop %d (%s)' % (prop_code, prop_type))
            pint = prop_code << 16 | right_value
            #print("packing prop v2",prop_code, right_value,pint, prop_value)
            buf.pack_int(pint)
            if prop_type == FgmsType.V1_String: # v2 string contents still to pack
                try:
                    buf.append_bytes(bytes(str(prop_value), encoding=fgms_string_encoding))
                except:
                    buf.append_bytes(bytes(prop_value))
        else: # LEGACY: pack property code first, then its value separately
            buf.pack_int(prop_code)
            #print("packing prop v1",prop_code, prop_value)
            if prop_type == FgmsType.V1_Bool:
                buf.pack_int(int(prop_value))
            elif prop_type == FgmsType.V1_Float:
                buf.pack_float(prop_value)
            elif prop_type == FgmsType.V1_Int:
                buf.pack_int(prop_value)
            elif prop_type == FgmsType.V1_String:
                strbuf = PacketData()
                for c in prop_value:
                    strbuf.pack_int(ord(c))
                strbuf.pad(16)
                buf.pack_int(len(prop_value))
                buf.append_packed(strbuf)
            else: # ATC-pie should not need to send: V2_NoSend, V2_BoolArray
                raise ValueError('Unhandled legacy-style packing of prop %d' % prop_code)
        self.append_packed(buf)
    
    ## High-level property unpacking
    
    def unpack_property(self):
        unpacked_first = self.unpack_int()
        #DEBUG('Unpacking int %d ' % unpacked_first, end='')
        right_value = None
        try:
            left_value = unpacked_first >> 16
            if left_value == 0: # recognise legacy encoding of property
                prop_code = unpacked_first
                prop_type = FGMS_properties[prop_code][1]
            else: # recognising v2 tight encoding (code on the first two bytes, value in the low half)
                prop_code = left_value
                prop_type = FGMS_properties[prop_code][2]
                if prop_type == FgmsType.V2_LikeV1:
                    prop_type = FGMS_properties[prop_code][1]
                if prop_type not in FgmsType.v2_tightly_packed_types:
                    raise ValueError('Unrecognised property in 4-byte value %d' % unpacked_first)
                right_value = unpacked_first & 0xffff
                if right_value & 1 << 15 != 0: # right-value is negative
                    right_value |= ~0xffff
        except KeyError:
            raise ValueError('Unknown property code %d' % prop_code)
        #DEBUG('(code %d, type %d)' % (prop_code, prop_type), end='')
        if right_value == None: # LEGACY: property value still to unpack
            if prop_type == FgmsType.V1_Bool:
                prop_value = bool(self.unpack_int())
            elif prop_type == FgmsType.V1_Float:
                prop_value = self.unpack_float()
            elif prop_type == FgmsType.V1_Int:
                prop_value = self.unpack_int()
            elif prop_type == FgmsType.V1_String:
                nchars = self.unpack_int()
                intbytes = PacketData(self.pop_bytes((((4 * nchars - 1) // 16) + 1) * 16))
                chrlst = []
                for i in range(nchars):
                    try: chrlst.append(chr(intbytes.unpack_int()))
                    except ValueError: chrlst.append(dodgy_character_substitute)
                prop_value = ''.join(chrlst)
            elif prop_type == FgmsType.V2_BoolArray:
                prop_value = NotImplemented # CHECK: unpack bytes here? how many? is code even reachable?
            else:
                raise ValueError('Could not unpack property %d' % prop_code)
        else: # TIGHT: value already unpacked (or its length if type string)
            if prop_type == FgmsType.V1_Bool:
                prop_value = bool(right_value)
            elif prop_type == FgmsType.V1_String:
                prop_value = self.pop_bytes(right_value).decode(encoding=fgms_string_encoding)
            elif prop_type == FgmsType.V2_ShortInt:
                prop_value = right_value
            else: # ATC-pie should not need to interpret any tightly-packed property of other types so we can return a dummy value
                prop_value = prop_type
        #DEBUG(' %s style %s = %s' % (('legacy' if right_value == None else 'tight'), FGMS_properties[prop_code][0], prop_value))
        return prop_code, prop_value

def make_fgms_packet(sender_callsign, packet_type, content_data):
    packet = PacketData()
    # Header first (32 bytes)
    packet.append_bytes(b'FGFS') # Magic
    packet.append_bytes(bytes.fromhex('00 01 00 01')) # Protocol version 1.1
    packet.pack_int(packet_type) # Msg type: position message
    packet.pack_int(32 + len(content_data)) # Length of data
    packet.pack_int(80) # Visibility range (was: ReplyAddress; see message 35687340 on the FG devel list)
    packet.append_bytes(bytes(4)) # ReplyPort: ignored
    packet.pack_padded_string(8, sender_callsign) # Callsign
    # Append the data
    packet.append_packed(content_data)
    return packet

def mkFgmsMsg_position(callsign, aircraft_model, pos_coords, pos_amsl, hdg=0, pitch=0, roll=0, properties={}, legacy=False):
    '''
    pos_coords: EarthCoords
    pos_amsl should be geometric alt in feet
    '''
    pass

def pie_msg(msg, legacy=False):
    ''' Creates packed message from a PosMsg '''
    buf = PacketData()
    #print ("pie_msg", msg)
    buf.pack_padded_string(96, msg.model) # Aircraft model
    buf.pack_double(msg.time) # Time
    buf.pack_double(msg.lag) # Lag # WARNING zero value can make some FG clients crash (see SF tickets 1927 and 1942)
    #posX, posY, posZ = WGS84_geodetic_to_cartesian_metres(pos_coords, pos_amsl)
    #buf.pack_double(posX) # PosX
    #buf.pack_double(posY) # PosY
    #buf.pack_double(posZ) # PosZ
    buf.pack_fdouble(msg.position)
    buf.pack_ffloat(msg.orientation) # OriX
    buf.pack_ffloat(msg.linear_vel)
    buf.pack_ffloat(msg.angular_vel)
    buf.pack_ffloat(msg.linear_accel)
    buf.pack_ffloat(msg.angular_accel)
    buf.append_bytes(bytes(4) if legacy else v2_magic_padding) # pad # FUTURE[fgms_v2] remove legacy protocol?
    # finished position data; now packing properties
    if not legacy:
        buf.pack_property(FGMS_v2_virtual_prop, v2_version_prop_value, False)
    for prop_code, prop_value in msg.properties.properties.items():
        try:
            value = prop_value.get('value') if isinstance(prop_value,dict) else prop_value
            buf.pack_property(prop_code, value, legacy)
         
        except ValueError as err:
            print('Error packing property: %s' % err)
    return make_fgms_packet(str(msg.callsign()), position_message_type_code, buf).allData()



## ======= FGFS property code definitions =======

BOOLARRAY_BLOCKSIZE = 40
BOOLARRAY_BASE_1 = 11000
BOOLARRAY_BASE_2 = BOOLARRAY_BASE_1 + BOOLARRAY_BLOCKSIZE
BOOLARRAY_BASE_3 = BOOLARRAY_BASE_2 + BOOLARRAY_BLOCKSIZE

FGMS_properties = { # FGMS property ID: (prop name, v1 type, v2 type, marked as V2)
    # prop 10 marked V2_PROP_ID_PROTOCOL in source; marking as V2 here
    10: ('sim/multiplay/protocol-version', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    
    100: ('surface-positions/left-aileron-pos-norm', FgmsType.V1_Float, FgmsType.V2_ShortFloat, False),
    101: ('surface-positions/right-aileron-pos-norm', FgmsType.V1_Float, FgmsType.V2_ShortFloat, False),
    102: ('surface-positions/elevator-pos-norm', FgmsType.V1_Float, FgmsType.V2_ShortFloat, False),
    103: ('surface-positions/rudder-pos-norm', FgmsType.V1_Float, FgmsType.V2_ShortFloat, False),
    104: ('surface-positions/flap-pos-norm', FgmsType.V1_Float, FgmsType.V2_ShortFloat, False),
    105: ('surface-positions/speedbrake-pos-norm', FgmsType.V1_Float, FgmsType.V2_ShortFloat, False),
    106: ('gear/tailhook/position-norm', FgmsType.V1_Float, FgmsType.V2_ShortFloat, False),
    107: ('gear/launchbar/position-norm', FgmsType.V1_Float, FgmsType.V2_ShortFloat, False),
    108: ('gear/launchbar/state', FgmsType.V1_String, FgmsType.V2_LikeV1, True), # cf. property 120
    109: ('gear/launchbar/holdback-position-norm', FgmsType.V1_Float, FgmsType.V2_ShortFloat, False),
    110: ('canopy/position-norm', FgmsType.V1_Float, FgmsType.V2_ShortFloat, False),
    111: ('surface-positions/wing-pos-norm', FgmsType.V1_Float, FgmsType.V2_ShortFloat, False),
    112: ('surface-positions/wing-fold-pos-norm', FgmsType.V1_Float, FgmsType.V2_ShortFloat, False),
    
    120: ('gear/launchbar/state-value', FgmsType.V1_Int, FgmsType.V2_NoSend, True), # cf. property 108

    200: ('gear/gear[0]/compression-norm', FgmsType.V1_Float, FgmsType.V2_ShortFloat, False),
    201: ('gear/gear[0]/position-norm', FgmsType.V1_Float, FgmsType.V2_ShortFloat, False),
    210: ('gear/gear[1]/compression-norm', FgmsType.V1_Float, FgmsType.V2_ShortFloat, False),
    211: ('gear/gear[1]/position-norm', FgmsType.V1_Float, FgmsType.V2_ShortFloat, False),
    220: ('gear/gear[2]/compression-norm', FgmsType.V1_Float, FgmsType.V2_ShortFloat, False),
    221: ('gear/gear[2]/position-norm', FgmsType.V1_Float, FgmsType.V2_ShortFloat, False),
    230: ('gear/gear[3]/compression-norm', FgmsType.V1_Float, FgmsType.V2_ShortFloat, False),
    231: ('gear/gear[3]/position-norm', FgmsType.V1_Float, FgmsType.V2_ShortFloat, False),
    240: ('gear/gear[4]/compression-norm', FgmsType.V1_Float, FgmsType.V2_ShortFloat, False),
    241: ('gear/gear[4]/position-norm', FgmsType.V1_Float, FgmsType.V2_ShortFloat, False),

    300: ('engines/engine[0]/n1', FgmsType.V1_Float, FgmsType.V2_ShortFloat1, False),
    301: ('engines/engine[0]/n2', FgmsType.V1_Float, FgmsType.V2_ShortFloat1, False),
    302: ('engines/engine[0]/rpm', FgmsType.V1_Float, FgmsType.V2_ShortFloat1, False),
    310: ('engines/engine[1]/n1', FgmsType.V1_Float, FgmsType.V2_ShortFloat1, False),
    311: ('engines/engine[1]/n2', FgmsType.V1_Float, FgmsType.V2_ShortFloat1, False),
    312: ('engines/engine[1]/rpm', FgmsType.V1_Float, FgmsType.V2_ShortFloat1, False),
    320: ('engines/engine[2]/n1', FgmsType.V1_Float, FgmsType.V2_ShortFloat1, False),
    321: ('engines/engine[2]/n2', FgmsType.V1_Float, FgmsType.V2_ShortFloat1, False),
    322: ('engines/engine[2]/rpm', FgmsType.V1_Float, FgmsType.V2_ShortFloat1, False),
    330: ('engines/engine[3]/n1', FgmsType.V1_Float, FgmsType.V2_ShortFloat1, False),
    331: ('engines/engine[3]/n2', FgmsType.V1_Float, FgmsType.V2_ShortFloat1, False),
    332: ('engines/engine[3]/rpm', FgmsType.V1_Float, FgmsType.V2_ShortFloat1, False),
    340: ('engines/engine[4]/n1', FgmsType.V1_Float, FgmsType.V2_ShortFloat1, False),
    341: ('engines/engine[4]/n2', FgmsType.V1_Float, FgmsType.V2_ShortFloat1, False),
    342: ('engines/engine[4]/rpm', FgmsType.V1_Float, FgmsType.V2_ShortFloat1, False),
    350: ('engines/engine[5]/n1', FgmsType.V1_Float, FgmsType.V2_ShortFloat1, False),
    351: ('engines/engine[5]/n2', FgmsType.V1_Float, FgmsType.V2_ShortFloat1, False),
    352: ('engines/engine[5]/rpm', FgmsType.V1_Float, FgmsType.V2_ShortFloat1, False),
    360: ('engines/engine[6]/n1', FgmsType.V1_Float, FgmsType.V2_ShortFloat1, False),
    361: ('engines/engine[6]/n2', FgmsType.V1_Float, FgmsType.V2_ShortFloat1, False),
    362: ('engines/engine[6]/rpm', FgmsType.V1_Float, FgmsType.V2_ShortFloat1, False),
    370: ('engines/engine[7]/n1', FgmsType.V1_Float, FgmsType.V2_ShortFloat1, False),
    371: ('engines/engine[7]/n2', FgmsType.V1_Float, FgmsType.V2_ShortFloat1, False),
    372: ('engines/engine[7]/rpm', FgmsType.V1_Float, FgmsType.V2_ShortFloat1, False),
    380: ('engines/engine[8]/n1', FgmsType.V1_Float, FgmsType.V2_ShortFloat1, False),
    381: ('engines/engine[8]/n2', FgmsType.V1_Float, FgmsType.V2_ShortFloat1, False),
    382: ('engines/engine[8]/rpm', FgmsType.V1_Float, FgmsType.V2_ShortFloat1, False),
    390: ('engines/engine[9]/n1', FgmsType.V1_Float, FgmsType.V2_ShortFloat1, False),
    391: ('engines/engine[9]/n2', FgmsType.V1_Float, FgmsType.V2_ShortFloat1, False),
    392: ('engines/engine[9]/rpm', FgmsType.V1_Float, FgmsType.V2_ShortFloat1, False),

    800: ('rotors/main/rpm', FgmsType.V1_Float, FgmsType.V2_ShortFloat1, False),
    801: ('rotors/tail/rpm', FgmsType.V1_Float, FgmsType.V2_ShortFloat1, False),
    810: ('rotors/main/blade[0]/position-deg', FgmsType.V1_Float, FgmsType.V2_ShortFloat3, False),
    811: ('rotors/main/blade[1]/position-deg', FgmsType.V1_Float, FgmsType.V2_ShortFloat3, False),
    812: ('rotors/main/blade[2]/position-deg', FgmsType.V1_Float, FgmsType.V2_ShortFloat3, False),
    813: ('rotors/main/blade[3]/position-deg', FgmsType.V1_Float, FgmsType.V2_ShortFloat3, False),
    820: ('rotors/main/blade[0]/flap-deg', FgmsType.V1_Float, FgmsType.V2_ShortFloat3, False),
    821: ('rotors/main/blade[1]/flap-deg', FgmsType.V1_Float, FgmsType.V2_ShortFloat3, False),
    822: ('rotors/main/blade[2]/flap-deg', FgmsType.V1_Float, FgmsType.V2_ShortFloat3, False),
    823: ('rotors/main/blade[3]/flap-deg', FgmsType.V1_Float, FgmsType.V2_ShortFloat3, False),
    830: ('rotors/tail/blade[0]/position-deg', FgmsType.V1_Float, FgmsType.V2_ShortFloat3, False),
    831: ('rotors/tail/blade[1]/position-deg', FgmsType.V1_Float, FgmsType.V2_ShortFloat3, False),

    900: ('sim/hitches/aerotow/tow/length', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    901: ('sim/hitches/aerotow/tow/elastic-constant', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    902: ('sim/hitches/aerotow/tow/weight-per-m-kg-m', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    903: ('sim/hitches/aerotow/tow/dist', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    904: ('sim/hitches/aerotow/tow/connected-to-property-node', FgmsType.V1_Bool, FgmsType.V2_LikeV1, False),
    905: ('sim/hitches/aerotow/tow/connected-to-ai-or-mp-callsign', FgmsType.V1_String, FgmsType.V2_LikeV1, True),
    906: ('sim/hitches/aerotow/tow/brake-force', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    907: ('sim/hitches/aerotow/tow/end-force-x', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    908: ('sim/hitches/aerotow/tow/end-force-y', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    909: ('sim/hitches/aerotow/tow/end-force-z', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    930: ('sim/hitches/aerotow/is-slave', FgmsType.V1_Bool, FgmsType.V2_LikeV1, False),
    931: ('sim/hitches/aerotow/speed-in-tow-direction', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    932: ('sim/hitches/aerotow/open', FgmsType.V1_Bool, FgmsType.V2_LikeV1, False),
    933: ('sim/hitches/aerotow/local-pos-x', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    934: ('sim/hitches/aerotow/local-pos-y', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    935: ('sim/hitches/aerotow/local-pos-z', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),

    1001: ('controls/flight/slats', FgmsType.V1_Float, FgmsType.V2_ShortFloat4, False),
    1002: ('controls/flight/speedbrake', FgmsType.V1_Float, FgmsType.V2_ShortFloat4, False),
    1003: ('controls/flight/spoilers', FgmsType.V1_Float, FgmsType.V2_ShortFloat4, False),
    1004: ('controls/gear/gear-down', FgmsType.V1_Float, FgmsType.V2_ShortFloat4, False),
    1005: ('controls/lighting/nav-lights', FgmsType.V1_Float, FgmsType.V2_ShortFloat3, False),
    1006: ('controls/armament/station[0]/jettison-all', FgmsType.V1_Bool, FgmsType.V2_ShortInt, False),

    1100: ('sim/model/variant', FgmsType.V1_Int, FgmsType.V2_LikeV1, False),
    1101: ('sim/model/livery/file', FgmsType.V1_String, FgmsType.V2_LikeV1, True),

    1200: ('environment/wildfire/data', FgmsType.V1_String, FgmsType.V2_LikeV1, True),
    1201: ('environment/contrail', FgmsType.V1_Int, FgmsType.V2_ShortInt, False),

    1300: ('tanker', FgmsType.V1_Int, FgmsType.V2_ShortInt, False),

    1400: ('scenery/events', FgmsType.V1_String, FgmsType.V2_LikeV1, True),

    1500: ('instrumentation/transponder/transmitted-id', FgmsType.V1_Int, FgmsType.V2_ShortInt, False),
    1501: ('instrumentation/transponder/altitude', FgmsType.V1_Int, FgmsType.V2_LikeV1, False),
    1502: ('instrumentation/transponder/ident', FgmsType.V1_Bool, FgmsType.V2_ShortInt, False),
    1503: ('instrumentation/transponder/inputs/mode', FgmsType.V1_Int, FgmsType.V2_ShortInt, False),
    1504: ('instrumentation/transponder/ground-bit', FgmsType.V1_Bool, FgmsType.V2_ShortInt, True),
    1505: ('instrumentation/transponder/airspeed-kt', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),

    10001: ('sim/multiplay/transmission-freq-hz', FgmsType.V1_String, FgmsType.V2_LikeV1, True),
    10002: ('sim/multiplay/chat', FgmsType.V1_String, FgmsType.V2_LikeV1, True),
    
    13001: ('sim/multiplay/comm-transmit-frequency-hz', FgmsType.V1_Int, FgmsType.V2_LikeV1, True),
    13002: ('sim/multiplay/comm-transmit-power-norm', FgmsType.V1_Float, FgmsType.V2_ShortFloat, True),

    10100: ('sim/multiplay/generic/string[0]', FgmsType.V1_String, FgmsType.V2_LikeV1, True),
    10101: ('sim/multiplay/generic/string[1]', FgmsType.V1_String, FgmsType.V2_LikeV1, True),
    10102: ('sim/multiplay/generic/string[2]', FgmsType.V1_String, FgmsType.V2_LikeV1, True),
    10103: ('sim/multiplay/generic/string[3]', FgmsType.V1_String, FgmsType.V2_LikeV1, True),
    10104: ('sim/multiplay/generic/string[4]', FgmsType.V1_String, FgmsType.V2_LikeV1, True),
    10105: ('sim/multiplay/generic/string[5]', FgmsType.V1_String, FgmsType.V2_LikeV1, True),
    10106: ('sim/multiplay/generic/string[6]', FgmsType.V1_String, FgmsType.V2_LikeV1, True),
    10107: ('sim/multiplay/generic/string[7]', FgmsType.V1_String, FgmsType.V2_LikeV1, True),
    10108: ('sim/multiplay/generic/string[8]', FgmsType.V1_String, FgmsType.V2_LikeV1, True),
    10109: ('sim/multiplay/generic/string[9]', FgmsType.V1_String, FgmsType.V2_LikeV1, True),
    10110: ('sim/multiplay/generic/string[10]', FgmsType.V1_String, FgmsType.V2_LikeV1, True),
    10111: ('sim/multiplay/generic/string[11]', FgmsType.V1_String, FgmsType.V2_LikeV1, True),
    10112: ('sim/multiplay/generic/string[12]', FgmsType.V1_String, FgmsType.V2_LikeV1, True),
    10113: ('sim/multiplay/generic/string[13]', FgmsType.V1_String, FgmsType.V2_LikeV1, True),
    10114: ('sim/multiplay/generic/string[14]', FgmsType.V1_String, FgmsType.V2_LikeV1, True),
    10115: ('sim/multiplay/generic/string[15]', FgmsType.V1_String, FgmsType.V2_LikeV1, True),
    10116: ('sim/multiplay/generic/string[16]', FgmsType.V1_String, FgmsType.V2_LikeV1, True),
    10117: ('sim/multiplay/generic/string[17]', FgmsType.V1_String, FgmsType.V2_LikeV1, True),
    10118: ('sim/multiplay/generic/string[18]', FgmsType.V1_String, FgmsType.V2_LikeV1, True),
    10119: ('sim/multiplay/generic/string[19]', FgmsType.V1_String, FgmsType.V2_LikeV1, True),

    10200: ('sim/multiplay/generic/float[0]', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    10201: ('sim/multiplay/generic/float[1]', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    10202: ('sim/multiplay/generic/float[2]', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    10203: ('sim/multiplay/generic/float[3]', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    10204: ('sim/multiplay/generic/float[4]', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    10205: ('sim/multiplay/generic/float[5]', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    10206: ('sim/multiplay/generic/float[6]', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    10207: ('sim/multiplay/generic/float[7]', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    10208: ('sim/multiplay/generic/float[8]', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    10209: ('sim/multiplay/generic/float[9]', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    10210: ('sim/multiplay/generic/float[10]', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    10211: ('sim/multiplay/generic/float[11]', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    10212: ('sim/multiplay/generic/float[12]', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    10213: ('sim/multiplay/generic/float[13]', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    10214: ('sim/multiplay/generic/float[14]', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    10215: ('sim/multiplay/generic/float[15]', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    10216: ('sim/multiplay/generic/float[16]', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    10217: ('sim/multiplay/generic/float[17]', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    10218: ('sim/multiplay/generic/float[18]', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    10219: ('sim/multiplay/generic/float[19]', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),

    10220: ('sim/multiplay/generic/float[20]', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    10221: ('sim/multiplay/generic/float[21]', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    10222: ('sim/multiplay/generic/float[22]', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    10223: ('sim/multiplay/generic/float[23]', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    10224: ('sim/multiplay/generic/float[24]', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    10225: ('sim/multiplay/generic/float[25]', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    10226: ('sim/multiplay/generic/float[26]', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    10227: ('sim/multiplay/generic/float[27]', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    10228: ('sim/multiplay/generic/float[28]', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    10229: ('sim/multiplay/generic/float[29]', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    10230: ('sim/multiplay/generic/float[30]', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    10231: ('sim/multiplay/generic/float[31]', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    10232: ('sim/multiplay/generic/float[32]', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    10233: ('sim/multiplay/generic/float[33]', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    10234: ('sim/multiplay/generic/float[34]', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    10235: ('sim/multiplay/generic/float[35]', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    10236: ('sim/multiplay/generic/float[36]', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    10237: ('sim/multiplay/generic/float[37]', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    10238: ('sim/multiplay/generic/float[38]', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),
    10239: ('sim/multiplay/generic/float[39]', FgmsType.V1_Float, FgmsType.V2_LikeV1, False),

    10300: ('sim/multiplay/generic/int[0]', FgmsType.V1_Int, FgmsType.V2_LikeV1, False),
    10301: ('sim/multiplay/generic/int[1]', FgmsType.V1_Int, FgmsType.V2_LikeV1, False),
    10302: ('sim/multiplay/generic/int[2]', FgmsType.V1_Int, FgmsType.V2_LikeV1, False),
    10303: ('sim/multiplay/generic/int[3]', FgmsType.V1_Int, FgmsType.V2_LikeV1, False),
    10304: ('sim/multiplay/generic/int[4]', FgmsType.V1_Int, FgmsType.V2_LikeV1, False),
    10305: ('sim/multiplay/generic/int[5]', FgmsType.V1_Int, FgmsType.V2_LikeV1, False),
    10306: ('sim/multiplay/generic/int[6]', FgmsType.V1_Int, FgmsType.V2_LikeV1, False),
    10307: ('sim/multiplay/generic/int[7]', FgmsType.V1_Int, FgmsType.V2_LikeV1, False),
    10308: ('sim/multiplay/generic/int[8]', FgmsType.V1_Int, FgmsType.V2_LikeV1, False),
    10309: ('sim/multiplay/generic/int[9]', FgmsType.V1_Int, FgmsType.V2_LikeV1, False),
    10310: ('sim/multiplay/generic/int[10]', FgmsType.V1_Int, FgmsType.V2_LikeV1, False),
    10311: ('sim/multiplay/generic/int[11]', FgmsType.V1_Int, FgmsType.V2_LikeV1, False),
    10312: ('sim/multiplay/generic/int[12]', FgmsType.V1_Int, FgmsType.V2_LikeV1, False),
    10313: ('sim/multiplay/generic/int[13]', FgmsType.V1_Int, FgmsType.V2_LikeV1, False),
    10314: ('sim/multiplay/generic/int[14]', FgmsType.V1_Int, FgmsType.V2_LikeV1, False),
    10315: ('sim/multiplay/generic/int[15]', FgmsType.V1_Int, FgmsType.V2_LikeV1, False),
    10316: ('sim/multiplay/generic/int[16]', FgmsType.V1_Int, FgmsType.V2_LikeV1, False),
    10317: ('sim/multiplay/generic/int[17]', FgmsType.V1_Int, FgmsType.V2_LikeV1, False),
    10318: ('sim/multiplay/generic/int[18]', FgmsType.V1_Int, FgmsType.V2_LikeV1, False),
    10319: ('sim/multiplay/generic/int[19]', FgmsType.V1_Int, FgmsType.V2_LikeV1, False),

    10500: ('sim/multiplay/generic/short[0]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10501: ('sim/multiplay/generic/short[1]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10502: ('sim/multiplay/generic/short[2]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10503: ('sim/multiplay/generic/short[3]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10504: ('sim/multiplay/generic/short[4]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10505: ('sim/multiplay/generic/short[5]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10506: ('sim/multiplay/generic/short[6]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10507: ('sim/multiplay/generic/short[7]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10508: ('sim/multiplay/generic/short[8]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10509: ('sim/multiplay/generic/short[9]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10510: ('sim/multiplay/generic/short[10]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10511: ('sim/multiplay/generic/short[11]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10512: ('sim/multiplay/generic/short[12]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10513: ('sim/multiplay/generic/short[13]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10514: ('sim/multiplay/generic/short[14]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10515: ('sim/multiplay/generic/short[15]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10516: ('sim/multiplay/generic/short[16]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10517: ('sim/multiplay/generic/short[17]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10518: ('sim/multiplay/generic/short[18]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10519: ('sim/multiplay/generic/short[19]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10520: ('sim/multiplay/generic/short[20]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10521: ('sim/multiplay/generic/short[21]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10522: ('sim/multiplay/generic/short[22]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10523: ('sim/multiplay/generic/short[23]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10524: ('sim/multiplay/generic/short[24]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10525: ('sim/multiplay/generic/short[25]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10526: ('sim/multiplay/generic/short[26]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10527: ('sim/multiplay/generic/short[27]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10528: ('sim/multiplay/generic/short[28]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10529: ('sim/multiplay/generic/short[29]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10530: ('sim/multiplay/generic/short[30]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10531: ('sim/multiplay/generic/short[31]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10532: ('sim/multiplay/generic/short[32]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10533: ('sim/multiplay/generic/short[33]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10534: ('sim/multiplay/generic/short[34]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10535: ('sim/multiplay/generic/short[35]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10536: ('sim/multiplay/generic/short[36]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10537: ('sim/multiplay/generic/short[37]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10538: ('sim/multiplay/generic/short[38]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10539: ('sim/multiplay/generic/short[39]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10540: ('sim/multiplay/generic/short[40]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10541: ('sim/multiplay/generic/short[41]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10542: ('sim/multiplay/generic/short[42]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10543: ('sim/multiplay/generic/short[43]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10544: ('sim/multiplay/generic/short[44]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10545: ('sim/multiplay/generic/short[45]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10546: ('sim/multiplay/generic/short[46]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10547: ('sim/multiplay/generic/short[47]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10548: ('sim/multiplay/generic/short[48]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10549: ('sim/multiplay/generic/short[49]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10550: ('sim/multiplay/generic/short[50]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10551: ('sim/multiplay/generic/short[51]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10552: ('sim/multiplay/generic/short[52]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10553: ('sim/multiplay/generic/short[53]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10554: ('sim/multiplay/generic/short[54]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10555: ('sim/multiplay/generic/short[55]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10556: ('sim/multiplay/generic/short[56]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10557: ('sim/multiplay/generic/short[57]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10558: ('sim/multiplay/generic/short[58]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10559: ('sim/multiplay/generic/short[59]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10560: ('sim/multiplay/generic/short[60]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10561: ('sim/multiplay/generic/short[61]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10562: ('sim/multiplay/generic/short[62]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10563: ('sim/multiplay/generic/short[63]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10564: ('sim/multiplay/generic/short[64]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10565: ('sim/multiplay/generic/short[65]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10566: ('sim/multiplay/generic/short[66]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10567: ('sim/multiplay/generic/short[67]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10568: ('sim/multiplay/generic/short[68]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10569: ('sim/multiplay/generic/short[69]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10570: ('sim/multiplay/generic/short[70]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10571: ('sim/multiplay/generic/short[71]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10572: ('sim/multiplay/generic/short[72]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10573: ('sim/multiplay/generic/short[73]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10574: ('sim/multiplay/generic/short[74]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10575: ('sim/multiplay/generic/short[75]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10576: ('sim/multiplay/generic/short[76]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10577: ('sim/multiplay/generic/short[77]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10578: ('sim/multiplay/generic/short[78]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),
    10579: ('sim/multiplay/generic/short[79]', FgmsType.V1_Int, FgmsType.V2_ShortInt, True),

    BOOLARRAY_BASE_1 +  0: ('sim/multiplay/generic/bool[0]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_1 +  1: ('sim/multiplay/generic/bool[1]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_1 +  2: ('sim/multiplay/generic/bool[2]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_1 +  3: ('sim/multiplay/generic/bool[3]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_1 +  4: ('sim/multiplay/generic/bool[4]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_1 +  5: ('sim/multiplay/generic/bool[5]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_1 +  6: ('sim/multiplay/generic/bool[6]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_1 +  7: ('sim/multiplay/generic/bool[7]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_1 +  8: ('sim/multiplay/generic/bool[8]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_1 +  9: ('sim/multiplay/generic/bool[9]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_1 + 10: ('sim/multiplay/generic/bool[10]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_1 + 11: ('sim/multiplay/generic/bool[11]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_1 + 12: ('sim/multiplay/generic/bool[12]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_1 + 13: ('sim/multiplay/generic/bool[13]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_1 + 14: ('sim/multiplay/generic/bool[14]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_1 + 15: ('sim/multiplay/generic/bool[15]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_1 + 16: ('sim/multiplay/generic/bool[16]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_1 + 17: ('sim/multiplay/generic/bool[17]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_1 + 18: ('sim/multiplay/generic/bool[18]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_1 + 19: ('sim/multiplay/generic/bool[19]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_1 + 20: ('sim/multiplay/generic/bool[20]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_1 + 21: ('sim/multiplay/generic/bool[21]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_1 + 22: ('sim/multiplay/generic/bool[22]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_1 + 23: ('sim/multiplay/generic/bool[23]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_1 + 24: ('sim/multiplay/generic/bool[24]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_1 + 25: ('sim/multiplay/generic/bool[25]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_1 + 26: ('sim/multiplay/generic/bool[26]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_1 + 27: ('sim/multiplay/generic/bool[27]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_1 + 28: ('sim/multiplay/generic/bool[28]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_1 + 29: ('sim/multiplay/generic/bool[29]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_1 + 30: ('sim/multiplay/generic/bool[30]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),

    BOOLARRAY_BASE_2 + 0: ('sim/multiplay/generic/bool[31]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_2 + 1: ('sim/multiplay/generic/bool[32]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_2 + 2: ('sim/multiplay/generic/bool[33]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_2 + 3: ('sim/multiplay/generic/bool[34]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_2 + 4: ('sim/multiplay/generic/bool[35]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_2 + 5: ('sim/multiplay/generic/bool[36]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_2 + 6: ('sim/multiplay/generic/bool[37]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_2 + 7: ('sim/multiplay/generic/bool[38]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_2 + 8: ('sim/multiplay/generic/bool[39]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_2 + 9: ('sim/multiplay/generic/bool[40]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_2 + 10: ('sim/multiplay/generic/bool[41]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_2 + 11: ('sim/multiplay/generic/bool[42]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_2 + 12: ('sim/multiplay/generic/bool[42]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_2 + 13: ('sim/multiplay/generic/bool[43]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_2 + 14: ('sim/multiplay/generic/bool[44]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_2 + 15: ('sim/multiplay/generic/bool[45]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_2 + 16: ('sim/multiplay/generic/bool[46]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_2 + 17: ('sim/multiplay/generic/bool[47]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_2 + 18: ('sim/multiplay/generic/bool[48]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_2 + 19: ('sim/multiplay/generic/bool[49]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_2 + 20: ('sim/multiplay/generic/bool[50]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_2 + 21: ('sim/multiplay/generic/bool[51]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_2 + 22: ('sim/multiplay/generic/bool[52]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_2 + 23: ('sim/multiplay/generic/bool[53]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_2 + 24: ('sim/multiplay/generic/bool[54]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_2 + 25: ('sim/multiplay/generic/bool[55]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_2 + 26: ('sim/multiplay/generic/bool[56]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_2 + 27: ('sim/multiplay/generic/bool[57]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_2 + 28: ('sim/multiplay/generic/bool[58]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_2 + 29: ('sim/multiplay/generic/bool[59]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_2 + 30: ('sim/multiplay/generic/bool[60]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),

    BOOLARRAY_BASE_3 + 0: ('sim/multiplay/generic/bool[61]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_3 + 1: ('sim/multiplay/generic/bool[62]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_3 + 2: ('sim/multiplay/generic/bool[63]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_3 + 3: ('sim/multiplay/generic/bool[64]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_3 + 4: ('sim/multiplay/generic/bool[65]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_3 + 5: ('sim/multiplay/generic/bool[66]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_3 + 6: ('sim/multiplay/generic/bool[67]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_3 + 7: ('sim/multiplay/generic/bool[68]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_3 + 8: ('sim/multiplay/generic/bool[69]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_3 + 9: ('sim/multiplay/generic/bool[70]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_3 + 10: ('sim/multiplay/generic/bool[71]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_3 + 11: ('sim/multiplay/generic/bool[72]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_3 + 12: ('sim/multiplay/generic/bool[72]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_3 + 13: ('sim/multiplay/generic/bool[73]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_3 + 14: ('sim/multiplay/generic/bool[74]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_3 + 15: ('sim/multiplay/generic/bool[75]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_3 + 16: ('sim/multiplay/generic/bool[76]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_3 + 17: ('sim/multiplay/generic/bool[77]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_3 + 18: ('sim/multiplay/generic/bool[78]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_3 + 19: ('sim/multiplay/generic/bool[79]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_3 + 20: ('sim/multiplay/generic/bool[80]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_3 + 21: ('sim/multiplay/generic/bool[81]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_3 + 22: ('sim/multiplay/generic/bool[82]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_3 + 23: ('sim/multiplay/generic/bool[83]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_3 + 24: ('sim/multiplay/generic/bool[84]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_3 + 25: ('sim/multiplay/generic/bool[85]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_3 + 26: ('sim/multiplay/generic/bool[86]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_3 + 27: ('sim/multiplay/generic/bool[87]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_3 + 28: ('sim/multiplay/generic/bool[88]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_3 + 29: ('sim/multiplay/generic/bool[89]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True),
    BOOLARRAY_BASE_3 + 30: ('sim/multiplay/generic/bool[90]', FgmsType.V1_Bool, FgmsType.V2_BoolArray, True)
}

FGMS_v2_virtual_prop = FGMS_prop_code_by_name('sim/multiplay/protocol-version')

# Relevant properties from ATC's PoV
FGMS_prop_XPDR_capability = FGMS_prop_code_by_name('instrumentation/transponder/inputs/mode')
FGMS_prop_XPDR_code = FGMS_prop_code_by_name('instrumentation/transponder/transmitted-id')
FGMS_prop_XPDR_alt = FGMS_prop_code_by_name('instrumentation/transponder/altitude')
FGMS_prop_XPDR_gnd = FGMS_prop_code_by_name('instrumentation/transponder/ground-bit')
FGMS_prop_XPDR_ias = FGMS_prop_code_by_name('instrumentation/transponder/airspeed-kt')
FGMS_prop_XPDR_ident = FGMS_prop_code_by_name('instrumentation/transponder/ident')
FGMS_prop_chat_msg = FGMS_prop_code_by_name('sim/multiplay/chat')
FGMS_prop_comm_freq = FGMS_prop_code_by_name('sim/multiplay/comm-transmit-frequency-hz')
FGMS_prop_comm_signal_power = FGMS_prop_code_by_name('sim/multiplay/comm-transmit-power-norm')

# Prop's specific to ATC-pie
FGMS_prop_ATCpie_version_string = FGMS_prop_code_by_name('sim/multiplay/generic/string[0]')
FGMS_prop_ATCpie_social_name = FGMS_prop_code_by_name('sim/multiplay/generic/string[1]')
FGMS_prop_ATCpie_publicised_freq = FGMS_prop_code_by_name('sim/multiplay/generic/string[2]')
