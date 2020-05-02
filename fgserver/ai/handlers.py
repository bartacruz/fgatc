'''
Created on 29 abr. 2020

@author: julio
'''
from fgserver.ai.models import WayPoint
from fgserver.ai.common import PlaneInfo
from django.contrib.gis.geos.point import Point
from fgserver.models import Runway
from fgserver.ai.dijkstra import dj_waypoints
from fgserver import units
from fgserver.helper import move, normdeg, Position
from random import randrange

class CircuitHandler():
    
    def __init__(self,circuit):
        self.circuit = circuit
        self.airport = circuit.airport
        self.aircraft = circuit.aircraft
        self.generate_start_waypoints()
        self.status=None
    
    def waypoint_reached(self,wp):
        self.status=wp.status
        
    def get_startup_location(self):     
        s1 = self.airport.startups.filter(aircraft = self.aircraft).first()
        if not s1:
            s1 = self.airport.startups.filter(active=True,aircraft=None).order_by("?").first()
        if s1:
            s1.aircraft=self.aircraft
            s1.save()
        return s1
    
    def generate_start_waypoints(self):
        start_l = self.get_startup_location()
        position= start_l.get_position()
        self.create_waypoint(position, start_l.name, WayPoint.PARKING, PlaneInfo.STOPPED)
        self.create_waypoint(position, start_l.name, WayPoint.PUSHBACK, PlaneInfo.TAXIING)
    
    def generate_taxi_waypoints(self, pos1, pos2, short=False):
        # TODO: Change when geodjango is completly implemented
        apalt=float(self.airport.altitude*units.FT+2)
        p1 = Point((pos1.y,pos1.x))
        if isinstance(pos2, Runway):
            rwystart = move(pos2.position(), normdeg(pos2.bearing-180), pos2.length/2,apalt)
            p2 = Point((rwystart.y,rwystart.x))
        else:
            p2 = Point((pos2.y,pos2.x))
        taxi = dj_waypoints(self.airport.icao,p1, p2)
        if len(taxi) > 2:
            for way in taxi[:-2]:
                p=Position(way.point.y,way.point.x, apalt)
                self.create_waypoint(p, "Taxi %s" % way.id, WayPoint.TAXI, PlaneInfo.TAXIING)
            position=Position(taxi[-2].point.y, taxi[-2].point.x, apalt)
            if short:
                self.create_waypoint(position, "Hold Short", WayPoint.HOLD, PlaneInfo.SHORT)
                
            else:
                self.create_waypoint(position, "Hold Short", WayPoint.TAXI, PlaneInfo.TAXIING)
                
            position=Position(taxi[-1].point.y, taxi[-1].point.x, apalt)
            if isinstance(pos2, Runway):
#                 self.create_waypoint(position, "Ramping for %s" % pos2.name, WayPoint.TAXI, PlaneInfo.TAXIING)
#                 position = move(rwystart,pos2.bearing,10,apalt)
                self.create_waypoint(position, "Lineup %s"% pos2.name, WayPoint.HOLD, PlaneInfo.LINED_UP)
            else:
                self.create_waypoint(position, "Taxi step ", WayPoint.TAXI, PlaneInfo.TAXIING)

    def generate_circuit_waypoints(self, runway):
        radius = self.circuit.radius
        apalt=float(runway.airport.altitude*units.FT+2)
        altitude = self.circuit.altitude
        roll = randrange(1900,max(3000,runway.length))
        rwystart = move(runway.position(), normdeg(runway.bearing-180), runway.length/2,apalt)
        
        straight=runway.bearing
        position = move(rwystart,straight,roll/5,apalt)
        self.create_waypoint(position, "Roll start %s" % runway.name, WayPoint.RWY, PlaneInfo.DEPARTING) # Set to start roll
        position = move(rwystart,straight,roll,apalt)
        self.create_waypoint(position, "Rotate %s" % runway.name, WayPoint.RWY, PlaneInfo.DEPARTING)
        # get to 20 meters altitude after exit the runway, then start climbing
        position = move(rwystart,straight,runway.length+roll/5,apalt+30)
        self.create_waypoint(position, "Departure %s" % runway.name, WayPoint.RWY, PlaneInfo.CLIMBING)
        #self.create_waypoint(position, "Departure %s"%runway.name, WayPoint.RWY, PlaneInfo.CLIMBING)
        position = move(position,straight,radius,apalt+altitude)
        self.create_waypoint(position, "Cruising", WayPoint.POINT, PlaneInfo.CRUISING)
        position = move(position,normdeg(straight+40),radius*0.7,apalt+altitude)
        self.create_waypoint(position, "Cruising 2", WayPoint.POINT, PlaneInfo.CRUISING)
        position = move(position,normdeg(straight+80),radius*0.6,apalt+altitude)
        self.create_waypoint(position, "Cruising 3", WayPoint.POINT, PlaneInfo.CRUISING)
        position = move(position,normdeg(straight+120),radius*0.6,apalt+altitude)
        self.create_waypoint(position, "Cruising 4", WayPoint.POINT, PlaneInfo.CRUISING)
        position = move(position,normdeg(straight+150),radius*0.6,apalt+altitude)
        self.create_waypoint(position, "Cruising 5", WayPoint.POINT, PlaneInfo.CRUISING)
        position = move(position,normdeg(straight+190),radius*0.6,apalt+altitude)
        self.create_waypoint(position, "Cruising 5", WayPoint.POINT, PlaneInfo.APPROACHING)
        position = move(position,normdeg(straight+230),radius*0.6,apalt+altitude)
        self.create_waypoint(position, "Cruising 6", WayPoint.POINT, PlaneInfo.APPROACHING)

    def generate_landing_waypoints(self,runway):
        radius = self.circuit.radius
        altitude = self.circuit.altitude
        apalt=float(runway.airport.altitude*units.FT+2)
        straight=runway.bearing
        reverse= normdeg(straight-180)
        left = normdeg(straight-90)
        right = normdeg(straight+90)
        rwystart = move(runway.position(), reverse, runway.length/2,apalt)
        rwyend = move(runway.position(), straight, runway.length/2,apalt)
        position = move(rwyend,right,radius,apalt+altitude+1000*units.FT)
        self.create_waypoint(position, "Crosswind %s"%runway.name, WayPoint.CIRCUIT, PlaneInfo.CIRCUIT_CROSSWIND)
        position = move(position,left,radius*2,apalt+altitude)
        self.create_waypoint(position, "Downwind %s"%runway.name, WayPoint.CIRCUIT, PlaneInfo.CIRCUIT_DOWNWIND)
        position = move(position,reverse,radius*2+runway.length,apalt+altitude)
        self.create_waypoint(position, "Base %s"%runway.name, WayPoint.CIRCUIT, PlaneInfo.CIRCUIT_BASE)
        position = move(position,right,radius,apalt+500*units.FT)
        self.create_waypoint(position, "Final %s"%runway.name, WayPoint.CIRCUIT, PlaneInfo.CIRCUIT_FINAL)
        position = move(rwystart,reverse,30,apalt+15)
        self.create_waypoint(position, "Flare %s"%runway.name, WayPoint.CIRCUIT, PlaneInfo.LANDING)
        position = move(rwystart,straight,20,apalt)
        
    def create_waypoint(self,position, name, atype, status):
        self.circuit.create_waypoint(position,name,atype,status)

