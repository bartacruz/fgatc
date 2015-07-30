import logging
from fgserver.settings import METAR_URL, METAR_UPDATE
import urllib
from datetime import datetime
from fgserver import units
from metar.Metar import Metar

llogger = logging.getLogger("fgserver")
llogger.setLevel(logging.DEBUG)


def info(sender,*argv):
    msg = "[%s]" % sender
    for arg in argv:
        msg += " %s" % arg
    llogger.info(msg)

def error(sender,*argv):
    msg = "[%s]" % sender
    for arg in argv:
        msg += " %s" % arg
    llogger.error(msg)

def debug(sender,*argv):
    msg = "[%s]" % sender
    for arg in argv:
        msg += " %s" % arg
    llogger.debug(msg)

CACHE = {}

def fetch_metar(icao):
    try:
        url = "%s/%s.TXT" % (METAR_URL, icao)
        urlh = urllib.urlopen(url)
        for line in urlh:
            if line.startswith(icao):
                obs = Metar(line)
                # print obs
                return obs
    except:
        pass
    llogger.debug("No METAR station for %s" % icao)
    return None

def get_metar(apt):
    icao = apt.icao
    if CACHE.has_key(icao):
        cached_metar= CACHE.get(icao)
        if not cached_metar:
            # no metar for this station
            #llogger.debug("Null METAR cached for %s" % apt)
            return cached_metar
        diff = datetime.now() - cached_metar.time
        if diff.total_seconds() > METAR_UPDATE:
            llogger.debug('Refreshing metar for %s because %s. (%s, %s)' % (apt,diff.total_seconds(),datetime.now(),cached_metar.time))
            CACHE.pop(icao)
            return get_metar(apt)
        #llogger.debug("Cached METAR for %s" % apt)
        return cached_metar
    else:
        metar = get_closest_metar(apt)
        CACHE[icao]=metar
        llogger.debug("METAR for %s fetched and cached=%s" % (apt,metar))
        return metar

def get_closest_metar(apt,max_range=50,unit=units.NM):
    from fgserver.models import airportsWithinRange
    obs = fetch_metar(apt.icao)
    if not obs:
        apts = airportsWithinRange(apt.get_position(),max_range,unit)
        apts.remove(apt)
        for napt in apts:
            obs = fetch_metar(napt.icao)
            if obs:
                llogger.debug("METAR found for %s" % napt)
                return obs
        print "NO METAR FOR %s or any airport within range" % apt
    else:
        return obs
