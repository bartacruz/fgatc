'''
Created on 28 abr. 2020

@author: julio
'''

class PlaneRequest():
    req = None
    laor = None
    freq = None
    mid = None
    apt = None
    rwy = None
    alt = None
    cirw = None
    
    def __init__(self,*args, **kwargs):
        for dictionary in args:
            for key in dictionary:
                setattr(self, key, dictionary[key])
        for key in kwargs:
            setattr(self, key, kwargs[key])
    
    @classmethod
    def from_string(cls, a_string):
        if not a_string:
            return None
        
        a_dict = {p.split('=')[0]:p.split('=')[1] for p in a_string.split(';')}
        return cls(a_dict)
    
    def get_request(self):
        return ';'.join('{}={}'.format(key,value) for key,value in self.__dict__.items())
    
    def __unicode__(self):
        return self.__str__().encode()
    def __str__(self):
        return str(self.__dict__)
    
class ReceivedOrder():
    ord=None;
    oid = None
    freq = None
    rwy = None
    park = None
    apt = None
    cirw = None
    cirt = None
    lnup = None
    number = None
    hld = None
    short = None
    repeat = None
    alt = None
    qnh = None
    leg = None
    atis = None
    to = None
    atc = None
    parkn = None
    
    
    def __init__(self,*args, **kwargs):
        for dictionary in args:
            for key in dictionary:
                setattr(self, key, dictionary[key])
        for key in kwargs:
            setattr(self, key, kwargs[key])
    
    @classmethod
    def from_string(cls, a_string):
        order= cls(eval(a_string))
        return order
        
    def __str__(self):
        return str(self.__dict__)
    
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
    ROLLING =22
    CROSS = 23
    
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
        (LINED_UP,'Lined up'),
        (TUNNED,'Tunned'),
        (PARKING,'Parking'),
        (LINING_UP,'Lining up'),
        (HOLD,'On Hold'),
        (ROLLING,'Rolling'),
        (CROSS,'Cross rwy'),
    )
    LABELS  = {x[0]:x[1] for x in CHOICES}
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
        (str(ROLLING),'Rolling'),
        (str(CROSS),'Cross rwy'),
    )
    @classmethod
    def label(cls,code):
        return cls.LABELS[int(code)]
