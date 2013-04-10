#!/usr/bin/env python
'''
Common fs function for getting the logger object,
and getting the singleton fs core object.
'''
import logging

LOG_FORMAT = '%(asctime)s %(name)-5s %(levelname)-8s %(message)s'

def get_logger(debug=False):
    '''Get the logger object'''
    logger = logging.getLogger('fs')
    loglevel = logging.INFO
    if debug:
        loglevel = logging.DEBUG
    logging.basicConfig(level=loglevel, format=LOG_FORMAT)
    return logger


__obj = None
def set_fscore(obj):
    '''Set the fs core object.  Heaven forgive me for using global.'''
    global __obj
    __obj = obj

def fscore():
    '''Get the fs core object'''
    return __obj
