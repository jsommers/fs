#!/usr/bin/env python
'''
Functions that are commonly used in various fs modules and subsystems.
'''
import logging

LOG_FORMAT = '%(created)9.4f %(name)-12s %(levelname)-8s %(message)s'

_loginit = False
def setup_logger(logfile=None, debug=False):
    global _loginit
    _loginit = True
    loglevel = logging.INFO
    if debug:
        loglevel = logging.DEBUG

    logging.basicConfig(level=loglevel, format=LOG_FORMAT)

    applog = logging.getLogger()
    if logfile:
        h = logging.FileHandler(logfile)
        h.setLevel(loglevel)
        h.setFormatter(logging.Formatter(LOG_FORMAT))
        applog.addHandler(h)

def get_logger(name='fs'):
    global _loginit
    if not _loginit:
        setup_logger(None, False)
    return logging.getLogger(name)

_obj = None
def set_fscore(obj):
    '''Set the fs core object.  Heaven forgive me for using global.'''
    global _obj
    _obj = obj

def fscore():
    '''Get the fs core object'''
    return _obj
