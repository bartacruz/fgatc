'''
Created on 7 may. 2020

@author: julio

StatePlane dynamics calculation

'''

from fgserver import units
from fgserver.helper import move, Position, Quaternion, normdeg, normalize,\
    get_heading_to, get_distance, angle_diff
from django.utils import timezone
from fgserver.models import AircraftStatus
from django.contrib.gis.geos.point import Point
from fgserver.ai.common import PlaneInfo
import logging
from numpy import angle

llogger = logging.getLogger(__name__)


class DynamicProps():
    name = None
    speed=0
    vertical_speed=0
    turn_rate=0
    target_vertical_speed=0
    
    def __str__(self):
        return str(self.__dict__)
    
    def update(self,*args, **kwargs):
        for dictionary in args:
            for key in dictionary:
                setattr(self, key, dictionary[key])
        for key in kwargs:
            setattr(self, key, kwargs[key])
    
class DynamicManager():
    ''' Basic dynamic calculations '''
    
    position=None
    orientation=None
    course=0
    linear_velocity=None
    bank_sense=0
    actual_turn_rate=0
    message=""
    target_course=0
    target_altitude=0
    waypoint = None
    waypoint_next=None
    waypoint_distance=None
    _waiting = 0
    roll = 0
    
    def __init__(self,plane):
        self.plane = plane
        self.props = DynamicProps()
        self._time = None
        
    def wait(self,seconds):
        llogger.debug("Waiting %s seconds" % seconds)
        self._waiting = seconds
        
    def set_waypoint(self,waypoint, waypoint_next):
        self.waypoint = waypoint
        self.waypoint_next = waypoint_next
        self.target_altitude=waypoint.get_position().z
        
    def update(self,time):
        if not self.waypoint:
            llogger.debug("no waypoint. state=%s" % self.plane.state)
            return
        if not self._time:
            self._time=time
            return
        dt = time - self._time
        self._time=time
        if self._waiting:
            # dont move
            self._waiting= max(0,self._waiting-dt)
            llogger.debug("WAITING on %s: %s" % (self.plane.state,self._waiting,))
            return
        course = get_heading_to(self.position, self.waypoint.get_position())
        dist = self.props.speed * dt
        dist_to=get_distance(self.position, self.waypoint.get_position())
        self.waypoint_distance=dist_to
        
        if self.props.speed == 0:
            # Don't move!
            return
        
        #self.log("course: %s, dist:%s, dist_to:%s" % (course,dist,dist_to))
        seconds_before=0
        nang=0
        
        #if self.waypoints.count()-1 > self._waypoint and not plane.on_ground():
        '''Calculate turn time to next waypoint to see if we reached actual'''
        if self.waypoint_next and not self.on_ground():
            #llogger.debug("%s => %s" % (self.waypoint,self.waypoint_next,))
            ncourse = get_heading_to(self.waypoint.get_position(), self.waypoint_next.get_position())
            nang = angle_diff(course, ncourse) 
            seconds_before = nang/self.props.turn_rate+2
        turn_dist = dist_to - dist*seconds_before/(dt*2)
        #self.debug("sec before",seconds_before,'turn_dist',turn_dist)
        step = False
        if dist >= abs(turn_dist) or dist_to < 0.1:
            llogger.debug("Reached waypoint %s" % self.waypoint)
            llogger.debug('nang=%s, seconds_before=%s ,dist=%s,dist_to=%s,turn_dist=%s' % (nang,seconds_before,dist,dist_to,turn_dist))
            
            dist = min(dist,dist_to)
            #plane.course = course
            step = True
            
            
        self.move(course,dist,dt)
        
        if step:
            if self.waypoint.status == PlaneInfo.LINED_UP:
                llogger.debug("calculating course heading from %s to %s" % (self.position,self.waypoint_next))
                depart_course = get_heading_to(self.position, self.waypoint_next.get_position())
                llogger.debug("is_linedup. Setting course from %s to %s" % (self.course, depart_course))
                self.course=depart_course
                
            self.plane.reached(self.waypoint)
        
    def move(self,course,distance,dt):
        self.target_course=course
        newcourse = self.next_course(dt)
        newalt = self.next_altitude(dt)
        newpos = move(self.position, newcourse, distance, newalt)
        p1=self.position.to_cart()
        p = newpos.to_cart()
        dif =  p.substract(p1)
        #asspeed = dif.get_length()/dt
        vs = Position.fromV3D(dif.scale(1/dt))
        q1 = Quaternion.fromLatLon(newpos.x, newpos.y)
        
        coursediff=abs(newcourse - course)
        self.actual_turn_rate= coursediff/dt
        self.roll = 0
        if not self.on_ground() and coursediff >= 0.01:
            self.roll = (self.props.turn_rate*self.bank_sense)*2
            #self.log("tr",self.props.turn_rate,"self.roll",self.roll,"bank",self.bank_sense)
        q2 = Quaternion.fromYawPitchRoll(newcourse, 0, self.roll)
        
        self.position = newpos
        self.orientation =  Position.fromV3D(q1.multiply(q2).normalize().get_angle_axis())
        self.linear_velocity = vs
        self.course=newcourse
        
        
    def next_altitude(self,dt):
        if self.on_ground():
            return self.waypoint.altitude
        if self.props.speed == 0 or abs(self.position.z - self.target_altitude) <= 0.1:
            return self.target_altitude
        multi=1
        diff = self.target_altitude - self.position.z
        if diff < 0:
            multi = -1
        vsdiff = self.props.target_vertical_speed -self.props.vertical_speed
        vsdiffa = abs(vsdiff)
        if vsdiff !=0:
            if self.props.vertical_speed==0:
                self.props.vertical_speed=0.5
            vsmult = round(vsdiff / abs(vsdiff))
            self.props.vertical_speed += vsmult * min((self.props.vertical_speed*self.props.vertical_speed)/vsdiffa, vsdiffa)
        
        vs = multi * min(self.props.vertical_speed*dt,abs(diff))
        na= self.position.z+vs;
        return na

    def next_course(self,dt):
        diff = normdeg(self.course - self.target_course)
        hdiff = abs(diff)
        if self.props.speed == 0 or hdiff < 0.01:
            return self.target_course
        
        self.bank_sense=1.0
        if diff > 0.01:
            self.bank_sense = -1.0
        nc =normalize(self.course + self.bank_sense*min(hdiff, self.props.turn_rate*dt))
        if angle_diff(self.course, nc) > angle_diff(self.course, self.target_course):
            return self.target_course
        return nc
    
    def on_ground(self):
        return self.plane.state in ['stopped','taxiing','linedup','short', 'rolling']
    
    def update_aircraft(self):
        a = self.plane.aircraft
        a.lat = self.position.x
        a.lon = self.position.y
        a.altitude = self.position.z
        a.heading= self.course
        a.updated = timezone.now()
        try:
            status = a.status
        except:
            status = AircraftStatus(aircraft=a)
        status.position= Point(self.position.get_array_cart())
        if self.orientation:
            status.orientation = Point(self.orientation.get_array())
        if self.linear_velocity:
            status.linear_vel = Point(self.linear_velocity.get_array_cart())
        status.angular_vel = Point([0,0,0])
        status.linear_accel = Point([0,0,0])
        status.angular_accel = Point([0,0,0])
        status.date = timezone.now()
        return status

class TurboPropDynamicManager(DynamicManager):
    
    def check(self):
        if self.plane.state == self.props.name:
            return
        plane = self.plane
        state = plane.state
        
        if state in ['stopped', 'short','linedup', 'starting']:
            self.props.update(name=state, speed=0, vertical_speed=0, turn_rate=1, target_vertical_speed=1)
        elif plane.is_pushback():
            self.props.update(name=state,turn_rate = 160, speed = 0.1*units.KNOTS, target_vertical_speed=1)
        elif plane.is_taxiing():
            self.props.update(name=state,turn_rate = 160, speed = 15*units.KNOTS, target_vertical_speed=1)
        elif plane.is_departing():
            self.props.update(name=state,turn_rate = 3,speed = 70*units.KNOTS,target_vertical_speed=200*units.FPM)
        elif plane.is_climbing():
            self.props.update(name=state,turn_rate = 5, speed = 80*units.KNOTS,target_vertical_speed=700*units.FPM)
        elif plane.is_cruising():
            self.props.update(name=state,turn_rate = 5, speed = 120*units.KNOTS, target_vertical_speed=300*units.FPM)
        elif plane.is_approaching():
            self.props.update(name=state,turn_rate = 5, speed = 90*units.KNOTS,target_vertical_speed=700*units.FPM)
        elif plane.is_on_circuit():
            self.props.update(name=state,turn_rate = 5, speed = 80*units.KNOTS,target_vertical_speed=300*units.FPM)
        elif plane.is_landing():
            self.props.update(name=state,turn_rate = 3, speed = 70*units.KNOTS, target_vertical_speed=500*units.FPM)
        elif plane.is_rolling():
            self.props.update(name=state,turn_rate=160, speed=40*units.KNOTS)
        else:
            llogger.debug("no state known: %s" % state)
        llogger.debug("Props: %s" % self.props)
    
        