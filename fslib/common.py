#!/usr/bin/env python
'''
Functions that are commonly used in various fs modules and subsystems.
'''
import logging

LOG_FORMAT = '%(created)4.4f %(name)-12s %(levelname)-8s %(message)s'

_applog = None
def setup_logger(logfile, debug):
    loglevel = logging.INFO
    if debug:
        loglevel = logging.DEBUG

    applog = logging.getLogger('fs')
    logging.basicConfig(level=loglevel, format=LOG_FORMAT)

    if logfile:
        h = logging.FileHandler(logfile)
        h.setLevel(loglevel)
        h.setFormatter(logging.Formatter(LOG_FORMAT))
        applog.addHandler(h)

    global _applog
    _applog = applog

def get_logger():
    return _applog

def _fs_monkeypatch(obj):
    '''monkey patch current time function in time module to give
    simulation time.'''
    import time
    setattr(time, "time", obj.nowfn)

_obj = None
def set_fscore(obj):
    '''Set the fs core object.  Heaven forgive me for using global.'''
    global _obj
    _obj = obj
    _fs_monkeypatch(obj)

def fscore():
    '''Get the fs core object'''
    return _obj
