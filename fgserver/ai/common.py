'''
Created on 28 abr. 2020

@author: julio
'''

class PlaneInfo():
    

    DEFAULT_MODEL="Aircraft/c310/Models/c310-dpm.xml"

    STOPPED = 1
    PUSHBACK = 2
    TAXIING = 3
    DEPARTING = 4
    TURNING = 5
    CLIMBING = 6
    CRUISING = 7
    APPROACHING = 8
    LANDING = 9
    TOUCHDOWN = 10
    CIRCUIT_CROSSWIND=11
    CIRCUIT_DOWNWIND=12
    CIRCUIT_BASE=13
    CIRCUIT_STRAIGHT=14
    CIRCUIT_FINAL=15
    SHORT=16
    LINED_UP=17
    TUNNED=18
    PARKING = 19
    LINING_UP=20
    HOLD = 21
    CIRCUITS=[CIRCUIT_CROSSWIND,CIRCUIT_DOWNWIND,CIRCUIT_BASE,CIRCUIT_STRAIGHT,CIRCUIT_FINAL]
    CHOICES = (
        (0,'None'),               
        (STOPPED,'Stopped'),
        (PUSHBACK,'Pushback'),
        (TAXIING,'Taxiing'),
        (DEPARTING,'Departing'),
        (TURNING,'Turning'),
        (CLIMBING,'Climbing'),
        (CRUISING,'Cruising'),
        (APPROACHING,'Approaching'),
        (LANDING,'Landing'),
        (TOUCHDOWN,'Touchdown'),
        (CIRCUIT_CROSSWIND,'Crosswind'),
        (CIRCUIT_DOWNWIND,'Downwind'),
        (CIRCUIT_BASE,'Base'),
        (CIRCUIT_STRAIGHT,'Straight'),
        (CIRCUIT_FINAL,'Final'),
        (SHORT,'Short of runway'),
        (HOLD,'On Hold'),
        (LINED_UP,'Lined up'),
        (TUNNED,'Tunned'),
        (PARKING,'Parking'),
        (LINING_UP,'Lining up'),
    )
    CHOICES_STR = (
        ('0','None'),               
        (str(STOPPED),'Stopped'),
        (str(PUSHBACK),'Pushback'),
        (str(TAXIING),'Taxiing'),
        (str(DEPARTING),'Departing'),
        (str(TURNING),'Turning'),
        (str(CLIMBING),'Climbing'),
        (str(CRUISING),'Cruising'),
        (str(APPROACHING),'Approaching'),
        (str(LANDING),'Landing'),
        (str(TOUCHDOWN),'Touchdown'),
        (str(CIRCUIT_CROSSWIND),'Crosswind'),
        (str(CIRCUIT_DOWNWIND),'Downwind'),
        (str(CIRCUIT_BASE),'Base'),
        (str(CIRCUIT_STRAIGHT),'Straight'),
        (str(CIRCUIT_FINAL),'Final'),
        (str(SHORT),'Short of runway'),
        (str(HOLD),'On Hold'),
        (str(LINED_UP),'Lined up'),
        (str(TUNNED),'Tunned'),
        (str(PARKING),'Parking'),
        (str(LINING_UP),'Lining up'),
    )

class StatePlane(object):
    states = ['stopped','pushback','taxiing','departing','turn'] 
    STOPPED = 1
    PUSHBACK = 2
    TAXIING = 3
    DEPARTING = 4
    TURNING = 5
    CLIMBING = 6
    CRUISING = 7
    APPROACHING = 8
    LANDING = 9
    TOUCHDOWN = 10
    CIRCUIT_CROSSWIND=11
    CIRCUIT_DOWNWIND=12
    CIRCUIT_BASE=13
    CIRCUIT_STRAIGHT=14
    CIRCUIT_FINAL=15
    SHORT=16
    LINED_UP=17
    TUNNED=18
    PARKING = 19
    LINING_UP=20
