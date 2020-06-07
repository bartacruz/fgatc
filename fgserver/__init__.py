from datetime import datetime
import logging
from threading import Thread

from django.utils.module_loading import  import_string
from metar.Metar import Metar

from fgserver import units, settings
from fgserver.settings import METAR_URL, METAR_UPDATE
import threading
from urllib import request


llogger = logging.getLogger("fgserver")
llogger.setLevel(logging.DEBUG)


from .celery import app as celery_app

__all__ = ('celery_app',)

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

CONTROLLERS = {}

def get_cached_controller(id):
    return CONTROLLERS.get(id)

def get_controller(comm):
    controller =  get_cached_controller(comm.id)
    if not controller:
        try:
            llogger.debug("Creating controller for %s" % comm)
            clazz = import_string(settings.DEFAULT_CONTROLLERS.get(comm.type))
            llogger.debug("class=%s" % clazz)
            controller = clazz(comm)
            CONTROLLERS[comm.id]=controller
        except:
            llogger.exception("Error al crerar un controller para %s" % comm)
    return controller


def get_controllers(airport,controller_type=None):
    controllers = []
    comms= airport.comms.all()
    if controller_type:
        comms = comms.filter(type=controller_type)
    for comm in comms:
        controllers.append(get_controller(comm))
    return controllers

def fetch_metar(icao):
    url = "%s/%s.TXT" % (METAR_URL, icao)
    try:
        urlh = request.urlopen(url)
        for line in urlh:
            line = line.decode()
            if line.startswith(icao):
                obs = Metar(line)
                # print obs
                return obs
    except:
        llogger.exception("while searching for %s" % url)
    llogger.debug("No METAR station for %s - %s" % (icao,url))
    return None

def get_metar_cycle(apt):
    metar = apt.metar.last()
    if metar:
        return chr(ord('a')+metar.cycle)
    return None

def get_qnh(apt):
    metar = apt.metar.last()
    if metar:
        obs = Metar(metar.observation)
        return round(obs.press.value('in'),2)
    return None

def get_closest_metar(apt,max_range=80,unit=units.NM):
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
        llogger.info("NO METAR FOR %s or any airport within range" % apt)
    else:
        return obs

def setInterval(interval, times = -1):
    # This will be the actual decorator,
    # with fixed interval and times parameter
    def outer_wrap(function):
        # This will be the function to be
        # called
        def wrap(*args, **kwargs):
            stop = threading.Event()

            # This is another function to be executed
            # in a different thread to simulate setInterval
            def inner_wrap():
                i = 0
                while i != times and not stop.isSet():
                    stop.wait(interval)
                    function(*args, **kwargs)
                    i += 1

            t = threading.Timer(0, inner_wrap)
            t.daemon = True
            t.start()
            return stop
        return wrap
    return outer_wrap
