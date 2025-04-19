'''
Created on 7 may. 2020

@author: julio

StatePlane dynamics calculation

'''
import math
from fgserver import units
from fgserver.helper import move, Position, Quaternion, normdeg, normalize,\
    get_heading_to, get_distance, angle_diff
from django.utils import timezone
from fgserver.models import AircraftStatus
from django.contrib.gis.geos.point import Point
from fgserver.ai.common import PlaneInfo
import logging

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
    vertical_speed=0
    speed = 0
    _waiting = 0
    roll = 0
    
    def __init__(self,plane,fdm):
        self.plane = plane
        self.fdm = fdm
        self.props = self.fdm.get_props(plane.state)

        self._time = None
        
    def wait(self,seconds):
        llogger.debug("Waiting %s seconds" % seconds)
        self._waiting = seconds
        
    def set_waypoint(self,waypoint, waypoint_next):
        self.waypoint = waypoint
        self.waypoint_next = waypoint_next
        if waypoint:
            self.target_altitude=waypoint.get_position().z

    def check_speed(self,dt):
        if self.speed  == self.props.speed * units.KNOTS:
            return
        # (de)accelerate to target speed
        if self.props.speed == 0:
            self.speed=0
        accel = self.props.acceleration
        diff = self.props.speed * units.KNOTS - self.speed
        if abs(diff) < 0.001:
            self.speed = self.props.speed * units.KNOTS
            llogger.debug("Rounding speed to target %s" % self.speed)
        else:
            delta_speed = min(accel * dt,abs(diff))
            mult = diff / abs(diff)
            self.speed += delta_speed*mult
            # llogger.debug("(De)accelerating %s" % self.speed)

    def update(self,time):
        if not self.waypoint:
            if not self.plane.is_stopped():
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
            #llogger.debug("WAITING on %s: %s" % (self.plane.state,self._waiting,))
            return
        
        self.check_speed(dt)
        
        course_to_wp = get_heading_to(self.position, self.waypoint.get_position())
        move_distance = self.speed * dt
        distance_to_wp=get_distance(self.position, self.waypoint.get_position())
        self.waypoint_distance=distance_to_wp
        
        if self.speed == 0:
            # Don't move!
            return
        
        #self.log("course_to_wp: %s, move_distance:%s, distance_to_wp:%s" % (course_to_wp,move_distance,distance_to_wp))
        seconds_before=0
        turn_angle=0
        turn_course = 0
        L=0
        '''Calculate turn time and distance to next waypoint to see if we reached actual'''
        if self.waypoint_next and not self.on_ground():
            #llogger.debug("%s => %s" % (self.waypoint,self.waypoint_next,))
            turn_course = get_heading_to(self.waypoint.get_position(), self.waypoint_next.get_position())
            turn_angle = angle_diff(course_to_wp, turn_course)
            seconds_before = turn_angle/self.props.turn_rate-1
            turn_arc_length = seconds_before*self.speed
            turn_angle_rad = turn_angle/units.RAD
            turn_radio = turn_arc_length / turn_angle_rad
            turn_chord = 2*turn_radio*math.sin(turn_angle_rad/2)
            L = (turn_chord/2) / math.cos(turn_angle_rad/2)

        turn_dist = distance_to_wp - L        
        step = False

        if move_distance > abs(turn_dist) or distance_to_wp < move_distance:
            llogger.debug("{%s-DYN} Reached waypoint %s" % (self.plane, self.waypoint))
            llogger.debug('{%s-DYN} nang=%s, ncourse=%s, ctwp=%s, course=%s, seconds_before=%s ,move_distance=%s,distance_to_wp=%s,L=%sturn_distance=%s' % (self.plane,turn_angle, turn_course, course_to_wp, self.course, seconds_before,move_distance,distance_to_wp,L,turn_dist))
            
            move_distance = min(move_distance,distance_to_wp)
            step = True
            
            
        self.move(course_to_wp,move_distance,dt)
        
        if step:
            # Hack to align plane to the runway when lined up.
            # TODO: Make sure we reach every waypoint heading to the next, and remove this hack
            if self.waypoint.status == PlaneInfo.LINED_UP and self.waypoint_next:
                llogger.debug("{%s-DYN} calculating course heading from %s to %s" % (self.plane, self.position,self.waypoint_next))
                depart_course = get_heading_to(self.position, self.waypoint_next.get_position())
                llogger.debug("{%s-DYN} is_linedup. Setting course from %s to %s" % (self.plane, self.course, depart_course))
                self.course=depart_course
                
            self.plane.reached(self.waypoint)
        
    def move(self,target_course,distance,dt):
        self.target_course=target_course
        newcourse = self.next_course(dt)
        newalt = self.next_altitude(dt)
        newpos = move(self.position, newcourse, distance, newalt)
        p1=self.position.to_cart()
        p = newpos.to_cart()
        dif =  p.substract(p1)
        vs = Position.fromV3D(dif.scale(1/dt))
        q1 = Quaternion.fromLatLon(newpos.x, newpos.y)
        
        coursediff=abs(normdeg(self.course - newcourse))
        self.actual_turn_rate= coursediff/dt
        self.roll = 0
        if not self.on_ground() and coursediff >= 0.01:
            #self.roll = (self.props.turn_rate*self.bank_sense)*2
            self.roll = coursediff * self.bank_sense *2 /dt
            #llogger.debug("turn_rate=%s, actual_tr=%s, roll=%s, bank=%s",self.props.turn_rate, self.actual_turn_rate,self.roll,self.bank_sense)
        q2 = Quaternion.fromYawPitchRoll(newcourse, 0, self.roll)
        
        self.position = newpos
        self.orientation =  Position.fromV3D(q1.multiply(q2).normalize().get_angle_axis())
        self.linear_velocity = vs
        self.course=newcourse

    def next_altitude(self,dt):
        if self.on_ground():
            return self.waypoint.altitude
        
        if self.speed == 0 or abs(self.position.z - self.target_altitude) <= 0.1:
            self.vertical_speed = 0
            return self.target_altitude
        
        # Pitch up or down?
        diff = self.target_altitude - self.position.z
        multi  = round(diff / abs(diff))
        vsdiff = self.props.vertical_speed*units.FPM - self.vertical_speed
        vsdiffa = abs(vsdiff)
        
        if vsdiffa > 0:
            vsmult = round(vsdiff / vsdiffa)
            if self.vertical_speed==0:
                self.vertical_speed=0.5*vsmult
            self.vertical_speed += vsmult * min(abs(self.vertical_speed*self.vertical_speed)/vsdiffa, vsdiffa)
        
        delta_alt = multi * min(abs(self.vertical_speed)*dt,abs(diff))
        next_altitude= self.position.z+delta_alt;
        return next_altitude

    def next_course(self,dt):
        diff = normdeg(self.course - self.target_course)
        heading_diff = abs(diff)
        if self.speed == 0 or heading_diff < 0.01:
            self.bank_sense=0
            return self.target_course
        
        self.bank_sense=1.0
        if diff > 0.01:
            self.bank_sense = -1.0
        
        # Respect the current turn_rate.
        max_diff = self.props.turn_rate*dt
        turn_angle = min(heading_diff, max_diff) * self.bank_sense
        next_course =normalize(self.course + turn_angle)
        
        # Avoid rounding errors.
        if angle_diff(self.course, next_course) >= angle_diff(self.course, self.target_course):
            return self.target_course
        #llogger.debug("{%s-DYN} heading_diff=%s, max_diff=%s, TURN ANGLE=%s, dt=%s, real turn_rate=%s, course=%s, next=%s, target=%s" % (self.plane, heading_diff, max_diff, turn_angle, dt, turn_angle/dt, self.course, next_course, self.target_course))
        return next_course
    
    def on_ground(self):
        return self.plane.state in ['stopped','pushback','taxiing','linedup','short', 'rolling']
    
    def update_aircraft(self):
        ''' Update aircraft and status with current data '''
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
    def check(self):
        if self.plane.state == self.props.state:
            return
        self.props = self.fdm.get_props(self.plane.state) or self.props

