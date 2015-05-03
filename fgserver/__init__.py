import logging

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
