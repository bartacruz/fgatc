import logging
from fgserver.settings import METAR_URL, METAR_UPDATE
import urllib
from datetime import datetime
from fgserver import units, settings
from metar.Metar import Metar
from django.utils.module_loading import import_by_path
from threading import Thread
from south.modelsinspector import timezone
from django.db.models.signals import post_save
from django.dispatch.dispatcher import receiver

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

CONTROLLERS = {}

def get_cached_controller(id):
    return CONTROLLERS.get(id)

def get_controller(comm):
    controller =  get_cached_controller(comm.id)
    if not controller:
        try:
            llogger.debug("Creating controller for %s" % comm)
            clazz = import_by_path(settings.DEFAULT_CONTROLLERS.get(comm.type))
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

