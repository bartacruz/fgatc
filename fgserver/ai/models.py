'''
Created on Apr 24, 2015

@author: bartacruz
'''
from fgserver.helper import Position, get_distance, move, normdeg, Quaternion
from fgserver import units
from __builtin__ import min
from django.db.models.base import Model
from django.db.models.fields.related import ForeignKey
from django.db.models.fields import CharField, FloatField
from fgserver.models import Airport
from fgserver.ai import AIPlane, PlaneInfo, WayPoint


class Circuit(Model):
    airport=ForeignKey(Airport)
    name = CharField(max_length=8)
    description = CharField(max_length=255,null=True,blank=True)
    radius = FloatField(default=2*units.NM)
    radius.description="Radius of the circuit (in meters)"
    altitude=FloatField(default=1000*units.FT)
    altitude.description="Altitude of the circuit (in meters)"
    time=0
    aircraft=None
    waypoints=[]
    _waypoint=0
    FINAL = 500*units.FT
    _waiting=0

    def reset(self):
        self.aircraft=AIPlane(self.name)
        self.aircraft.airport = self.airport
        self.waypoints=[]
        self.calculateCircuit()
        self._waypoint=0
        for wp in self.waypoints:
            print "wp: %s" % wp
        
        rwy = self.airport.active_runway()
        #print "reset: rwy: %s" % rwy.position().get_array()
        
        #pos = move(rwy.position(),normalize(rwy.bearing),rwy.length / 2, rwy.altitude+1.8)
        self.aircraft.position=self.waypoint().position
        q1 = Quaternion.fromLatLon(rwy.lat, rwy.lon)
        q2 = Quaternion.fromYawPitchRoll(rwy.bearing, 0, 0)
        orient =q1.multiply(q2).normalize().get_angle_axis()
        self.aircraft.orientation=Position.fromV3D(orient)
        self.aircraft.waypoint = self.waypoint()
        self._waiting=30
        self.aircraft.set_state(PlaneInfo.TAXIING)
        print "reset: %s, %s" %( self.aircraft.position.get_array() ,self.aircraft.orientation.get_array())
    
    def get_pos_message(self):
        return self.aircraft.get_pos_message()

    def waypoint(self):
        if len(self.waypoints) > self._waypoint:
            return self.waypoints[self._waypoint]
        return None
    
    def update(self,time):
        #if self.aircraft.state < 1:
        #    return
        dt = time-self.time
        if self._waiting:
            self._waiting -=dt
            if self._waiting < 0:
                self._waiting=0
            return
        wp = self.waypoint()
        if not wp:
            return
        plane = self.aircraft
        course = plane.heading_to(wp.position)
        dist = plane.speed * dt
        dist_to=get_distance(plane.position, wp.position)
        #print "course: %s, dist:%s, dist_to:%s" % (course,dist,dist_to)
        seconds_before=0
        if len(self.waypoints)-1 > self._waypoint:
            seconds_before = 60/plane.turn_rate
        turn_dist = dist_to - dist*seconds_before*dt
        step = False
        if dist > turn_dist:
            print "reached waypoint %s" % wp
            dist = min(dist,dist_to)
            plane.course = course
            step = True
        plane.move(course,dist,dt)
        if step:
            plane.set_state(wp.status)
            self._waypoint += 1
            if self.waypoint():
                plane.waypoint = self.waypoint()
                plane.target_altitude=self.waypoint().position.z
                
                print "target altitude %sm" % plane.target_altitude
            else:
                self.reset()
        self.time = time
        
    def calculateCircuit(self):
        runway = self.airport.active_runway()
        thead = runway.bearing
        oheading= normdeg(thead+180)
        theading = normdeg(thead-90)
        apalt=float(self.airport.altitude)
        rwycenter = move(runway.position(), thead, 0,apalt)
        rwystart = move(runway.position(), oheading, runway.length/2-10,apalt)
        rwyhld = move(rwystart, thead, 50, apalt)
        landstart = move(rwystart, thead, 0, apalt+20*units.FT)
        rotate = move(rwystart, thead, min(900,runway.length*0.8), apalt+15)
        landend = move(rotate, thead, 0, apalt)
        rwyend = move(rwystart, thead, runway.length, apalt+10)
        apt_exit = move(rwyend, thead, 50, apalt+40)
        
        cruise = move(rwyend, thead, self.radius, apalt +self.altitude*2)
        dnwind = move(rwyend, theading, self.radius, apalt + self.altitude)
        base = move(dnwind, oheading,runway.length+ self.radius, apalt +self.altitude*0.8)
        finl = move(rwystart, oheading,self.radius, apalt + Circuit.FINAL)
        prefinl = move(finl,theading,0.3*units.NM,apalt + Circuit.FINAL+50*units.FT)
        postfinl = move(finl,thead,0.3*units.NM,apalt + Circuit.FINAL-50*units.FT)
        finl2 = move(rwystart, oheading,0.7*units.NM, apalt + 150*units.FT)
        sl= None # Startup location
        #self.waypoints.append(WayPoint(rwystart,WayPoint.PARKING,"%s Parking" % runway.name,PlaneInfo.TAXIING))
        park = WayPoint(rwystart,WayPoint.TAXI,"Start %s" % runway.name,PlaneInfo.TAXIING)
        self.waypoints.append(park)
        hold = WayPoint(rwyhld,WayPoint.RWY,"%s Hold" % runway.name,PlaneInfo.DEPARTING)
        self.waypoints.append(hold)
        self.waypoints.append(WayPoint(rwycenter,WayPoint.RWY,"%s Center" % runway.name,PlaneInfo.DEPARTING))
        self.waypoints.append(WayPoint(rotate,WayPoint.RWY,"%s Rotate" % runway.name,PlaneInfo.CLIMBING))
        self.waypoints.append(WayPoint(apt_exit,WayPoint.RWY,"%s APT exit" % runway.name,PlaneInfo.CLIMBING))
        self.waypoints.append(WayPoint(cruise,WayPoint.POINT,"%s Cruise" % runway.name,PlaneInfo.CRUISING))
        self.waypoints.append(WayPoint(dnwind,WayPoint.CIRCUIT_DOWNWIND,"%s Downwind" % runway.name,PlaneInfo.APPROACHING))
        self.waypoints.append(WayPoint(base,WayPoint.CIRCUIT_BASE,"%s Base" % runway.name,PlaneInfo.APPROACHING))
        self.waypoints.append(WayPoint(prefinl,WayPoint.CIRCUIT_FINAL,"%s PreFinal" % runway.name,PlaneInfo.LANDING))
        self.waypoints.append(WayPoint(postfinl,WayPoint.CIRCUIT_FINAL,"%s PostFinal" % runway.name,PlaneInfo.LANDING))
        self.waypoints.append(WayPoint(finl2,WayPoint.CIRCUIT_FINAL,"%s Final 2" % runway.name,PlaneInfo.LANDING))
        self.waypoints.append(WayPoint(landstart,WayPoint.RWY,"%s Land start" % runway.name,PlaneInfo.TOUCHDOWN))
        self.waypoints.append(WayPoint(landend,WayPoint.RWY,"%s landend" % runway.name,PlaneInfo.TAXIING))
