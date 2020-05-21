'''
Created on 29 abr. 2020

@author: julio
'''
from fgserver import settings
import os
import xml.etree.ElementTree as ET
from django.contrib.gis.geos.point import Point
from django.contrib.gis.geos.linestring import LineString
from django.contrib.gis.ptr import CPointerBase
import math
from _functools import reduce
from fgserver.helper import get_heading_to, angle_diff, Position
from django.contrib.gis.db.models.functions import Distance
from fgserver.messages import sim_time

# Fix nasty bug in geodjango
original_del = CPointerBase.__del__

def patched_del(self):
    try:
        original_del(self)
    except ImportError:
        pass
    
CPointerBase.__del__ = patched_del

class Vertex:
    ''' Represents points in the graph '''
    
    def __init__(self, node, point):
        self.id = node
        self.point = point
        self.adjacent = {}
        # Set distance to infinity for all nodes
        self.distance = math.inf
        # Mark all nodes unvisited        
        self.visited = False  
        # Predecessor
        self.previous = None

    def add_neighbor(self, neighbor, weight=0):
        self.adjacent[neighbor] = weight

    def get_connections(self):
        return self.adjacent.keys()  

    def get_id(self):
        return self.id

    def get_weight(self, neighbor):
        return self.adjacent[neighbor]

    def set_distance(self, dist):
        self.distance = dist

    def get_distance(self):
        return self.distance

    def set_previous(self, prev):
        self.previous = prev

    def set_visited(self):
        self.visited = True

    def __str__(self):
        return str(self.id) + ' adjacent: ' + str([x.id for x in self.adjacent])
    def __lt__(self,other):
        return self.distance < other.distance
    def __le__(self,other):
        return self.distance <= other.distance
    def __gt__(self,other):
        return self.distance > other.distance
    def __ge__(self,other):
        return self.distance >= other.distance
    
class Graph:
    '''  Dijkstra's matrix '''
    
    def __init__(self):
        self.vert_dict = {}
        self.num_vertices = 0

    def __iter__(self):
        return iter(self.vert_dict.values())

    def add_vertex(self, node, point):
        self.num_vertices = self.num_vertices + 1
        new_vertex = Vertex(node, point)
        self.vert_dict[node] = new_vertex
        return new_vertex
    
    def get_vertex(self, n):
        if n in self.vert_dict:
            return self.vert_dict[n]
        else:
            return None

    def add_edge(self, frm, to, cost = 0):
        if frm not in self.vert_dict:
            self.add_vertex(frm)
        if to not in self.vert_dict:
            self.add_vertex(to)
        if not cost:
            cost = self.get_vertex(frm).point.distance(self.get_vertex(to).point)*1000000
        self.vert_dict[frm].add_neighbor(self.vert_dict[to], cost)
        self.vert_dict[to].add_neighbor(self.vert_dict[frm], cost)

    def get_vertices(self):
        return self.vert_dict.keys()

    def set_previous(self, current):
        self.previous = current

    def get_previous(self, current):
        return self.previous

def shortest(v, path):
    ''' make shortest path from v.previous'''
    if v.previous:
        path.append(v.previous.get_id())
        shortest(v.previous, path)
    return

import heapq

def dijkstra(aGraph, start, target):
    '''Dijkstra's shortest path'''
    
    # Set the distance for the start node to zero 
    start.set_distance(0)

    # Put tuple pair into the priority queue
    unvisited_queue = [(v.get_distance(),v) for v in aGraph]
    heapq.heapify(unvisited_queue)

    while len(unvisited_queue):
        # Pops a vertex with the smallest distance 
        uv = heapq.heappop(unvisited_queue)
        current = uv[1]
        current.set_visited()

        #for next in v.adjacent:
        for nextn in current.adjacent:
            # if visited, skip
            if nextn.visited:
                continue
            new_dist = current.get_distance() + current.get_weight(nextn)
            
            if new_dist < nextn.get_distance():
                nextn.set_distance(new_dist)
                nextn.set_previous(current)
        # Rebuild heap
        # 1. Pop every item
        while len(unvisited_queue):
            heapq.heappop(unvisited_queue)
        # 2. Put all vertices not visited into the queue
        unvisited_queue = [(v.get_distance(),v) for v in aGraph if not v.visited]
        heapq.heapify(unvisited_queue)


class Way(LineString):
    def __init__(self, *args, **kwargs):
        LineString.__init__(self, *args, srid=4362,**kwargs)
        self.name = kwargs.get('name',None)
    
def shit_to_deg(val):
    ''' Converts shitty (?) degrees and fractional minutes (e.g. S58 15.21323) 
        into fractional signed degrees (-58.26123123) 
    '''
    mult = int('%s1' % val[:1].replace("S",'-').replace('W',"-").replace("N","").replace("E",""))
    v1 = val[1:3]
    v2 = val[4:]
    res = round( (float(v1)+float(v2)/60)*mult, 7)
    return res

def closest_node(icao,pos):
    ''' Finds the closest taxi node of a position 
        pos is an instance of Point or Position
    '''
    if isinstance(pos, Position):
        pos = pos.to_point()
    
    # get taxi nodes from ground net file. TODO: use the DB     
    root = ET.parse(os.path.join(settings.FGATC_FG_SCENERY,"Airports",icao[0],icao[1],icao[2],"%s.groundnet.xml" % icao))
    nodes = [Point(
            shit_to_deg(n.attrib.get('lon')),
            shit_to_deg(n.attrib.get('lat')),
            ) for n in list(root.findall('.//TaxiNodes/node')) if n.attrib.get('isOnRunway')=='1']
    n = reduce(lambda x,y: x if x.distance(pos) < y.distance(pos) else y,nodes)
    return n

def get_next_on_runway(pos, runway, heading):
    ''' Finds closest taxi node ON RUNWAY for a position in a particular
        heading. Useful to find the starting point of a runway exit path
    '''
    if isinstance(pos, Position):
        pos = pos.to_point()
    def delta(node):
        p = node.point
        dist = pos.distance(p)
        diff = angle_diff(float(heading),get_heading_to(pos,p))
        return dist*diff
    
    points = list(runway.airport.taxinodes.filter(on_runway=True))
    points.sort(key = delta)
    
#         p = entry[1]
#         ident=entry[0].attrib.get('index')
#         dist = pos.distance(p)
#         diff = angle_diff(float(heading),get_heading_to(pos,p))
#         delta = dist*diff
#         print(ident, delta)
#         points.append((delta,p))
#     points.sort(key=lambda x: x[0])
    print('on runway:', points)
    return points[0]

def get_runway_exit(runway, pos, heading):
    if isinstance(pos, Position):
        pos = pos.to_point()
    
    first = get_next_on_runway(pos, runway, heading)
    
    # Get short nodes, sort by angle difference and distance
    s = list(runway.airport.taxinodes.filter(short=True))    
    def delta(node):
        p = node.point
        dist = pos.distance(p)
        diff = angle_diff(runway.bearing,get_heading_to(first.point,p))
        return (dist/100)*diff
    s.sort(key=delta)
    dest = s.pop(0)
    
    route = taxi_path(runway.airport, first.point, dest.point)
    return route
    
    

def get_nodes_from_xml(icao, on_runway=None):
    icao = icao
    root = ET.parse(os.path.join(settings.FGATC_FG_SCENERY,"Airports",icao[0],icao[1],icao[2],"%s.groundnet.xml" % icao))
    nodes = list(root.findall('.//parkingList/Parking'))+list(root.findall('.//TaxiNodes/node'))
    ret = []
    for node in nodes:
        p = Point(
            shit_to_deg(node.attrib.get('lon')),
            shit_to_deg(node.attrib.get('lat')),
        )
        if on_runway == None:
            ret.append((node,p))
        elif on_runway == False and node.attrib.get('isOnRunway') == "0":
            ret.append((node,p))
        elif on_runway == True and node.attrib.get('isOnRunway') == "1":
            ret.append((node,p))
    return ret
    
#icao = "SADF"
def taxi_path(airport, start, endp, start_on_rwy=False,end_on_rwy=False):
    if airport.taxi_ways.count() == 0:
        return dj_waypoints(airport, start, endp, start_on_rwy=False,end_on_rwy=False)
    
    if isinstance(start,Position):
        start = start.to_point()
    if isinstance(endp,Position):
        endp = endp.to_point()
    
    print('%s Taxipath! in %s from %s to %s' % (sim_time(),airport,start,endp))
    graph = Graph()
    for node in airport.taxinodes.all():
        if not graph.get_vertex(node.name):
            graph.add_vertex(node.name, node.point)
        for adjacent in node.adjacents.all():
            if not graph.get_vertex(adjacent.name):
                graph.add_vertex(adjacent.name, adjacent.point)
            graph.add_edge(node.name, adjacent.name)
            graph.add_edge(adjacent.name, node.name)
    print('%s Taxipath! ended' % sim_time())
    # TODO: filter on runway and heading
    vstart = graph.get_vertex(airport.taxinodes.annotate(distance=Distance('point', start)).order_by('distance').first().name)
    vend = graph.get_vertex(airport.taxinodes.annotate(distance=Distance('point',endp)).order_by('distance').first().name)
    print (vstart,vend)
    dijkstra(graph, vstart, vend)
    
    path = [vend.get_id()]
    shortest(vend, path)
    print('The shortest path : %s' %(path[::-1]))
    route = [graph.get_vertex(x) for x in path[::-1]]
    return route
    
def dj_waypoints(airport, start, endp, start_on_rwy=False,end_on_rwy=False):
    print('dj_waypoints in %s from %s to %s' % (airport,start,endp))
    if isinstance(start,Position):
        start = start.to_point()
    if isinstance(endp,Position):
        endp = endp.to_point()
    
    icao = airport.icao
    root = ET.parse(os.path.join(settings.FGATC_FG_SCENERY,"Airports",icao[0],icao[1],icao[2],"%s.groundnet.xml" % icao))
    
    graph = Graph()
    #nodes = list(root.findall('.//parkingList/Parking'))+list(root.findall('.//TaxiNodes/node'))
    nodes = list(root.findall('.//parkingList/Parking'))+list(root.findall('.//TaxiNodes/node'))
    runway_points = []
    
    for node in nodes:
        p = Point(
            shit_to_deg(node.attrib.get('lon')),
            shit_to_deg(node.attrib.get('lat')),
            )
        ident=node.attrib.get('index')
        runw=node.attrib.get('isOnRunway') == "1"
        
        #runw=node.attrib.get('isOnRunway') == "1"
        v = graph.add_vertex(ident, p)
        if runw :
            runway_points.append(ident)
    print('on runway:', runway_points)
    
    # Store routed points to avoid orphaned in file.
    routed = []
    for node in root.findall('.//TaxiWaySegments/arc'):
        ident=node.attrib.get('name')
        first=node.attrib.get('begin')
        last=node.attrib.get('end')
        graph.add_edge(first, last)
        routed.append(first)
        routed.append(last)
    routed = list(set(routed))
    vstart = None
    vend = None
    
    # loop on routed points to find closest to start and end.
    for ident in routed:
        v = graph.get_vertex(ident)
        p = v.point
        if (not start_on_rwy or ident in runway_points) and (not vstart or start.distance(vstart.point) > start.distance(p)):
            #print("vstart=",ident)
            vstart = v
        if (not end_on_rwy or ident in runway_points)  and (not vend or endp.distance(vend.point) > endp.distance(p)):
            #print("vend=",ident)
            vend = v
    print("Searching from %s to %s" % (vstart,vend))
    dijkstra(graph, vstart, vend) 
    
    path = [vend.get_id()]
    shortest(vend, path)
    print('The shortest path : %s' %(path[::-1]))
    route = [graph.get_vertex(x) for x in path[::-1]]
    return route
