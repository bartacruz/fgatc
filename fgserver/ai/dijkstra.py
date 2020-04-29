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

# Fix nasty bug in geodjango

original_del = CPointerBase.__del__

def patched_del(self):
    try:
        original_del(self)
    except ImportError:
        pass

CPointerBase.__del__ = patched_del

class Vertex:
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
    #print '''Dijkstra's shortest path'''
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
#                 print('updated : current = %s nextn = %s new_dist = %s' \
#                         %(current.get_id(), nextn.get_id(), nextn.get_distance()))
#             else:
#                 print('not updated : current = %s nextn = %s new_dist = %s' \
#                         %(current.get_id(), nextn.get_id(), nextn.get_distance()))

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
    mult = int('%s1' % val[:1].replace("S",'-').replace('W',"-").replace("N","").replace("E",""))
    v1 = val[1:3]
    v2 = val[4:]
    res = round( (float(v1)+float(v2)/60)*mult, 7)
    return res

#icao = "SADF"
def dj_waypoints(icao, start, endp):
    print('dj_waypoints from %s to %s' % (start,endp))
    root = ET.parse(os.path.join(settings.FGATC_FG_SCENERY,"Airports",icao[0],icao[1],icao[2],"%s.groundnet.xml" % icao))
    
    vstart = None
    vend = None
    
    graph = Graph()
    nodes = list(root.findall('.//parkingList/Parking'))+list(root.findall('.//TaxiNodes/node'))
    
    for node in nodes:
        p = Point(
            shit_to_deg(node.attrib.get('lon')),
            shit_to_deg(node.attrib.get('lat')),
            )
        ident=node.attrib.get('index')
        runw=node.attrib.get('isOnRunway') == "1"
        v = graph.add_vertex(ident, p)
        if not vstart or start.distance(vstart.point) > start.distance(p):
            vstart = v
        if runw and (not vend or endp.distance(vend.point) > endp.distance(p)):
            vend = v
            
    for node in root.findall('.//TaxiWaySegments/arc'):
        ident=node.attrib.get('name')
        first=node.attrib.get('begin')
        last=node.attrib.get('end')
        graph.add_edge(first, last)

    print("Searching from %s to %s" % (vstart,vend))
    dijkstra(graph, vstart, vend) 
    
    
    path = [vend.get_id()]
    shortest(vend, path)
    print('The shortest path : %s' %(path[::-1]))
    route = [graph.get_vertex(x) for x in path[::-1]]
    return route
