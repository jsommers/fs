from abc import ABCMeta, abstractmethod
from fslib.common import fscore, get_logger

class TrafficGenerator(object):
    __metaclass__ = ABCMeta

    def __init__(self, srcnode):
        self.srcnode = srcnode
        self.done = False
        self.logger = get_logger("tgen.{}".format(self.srcnode))
        
    @abstractmethod
    def start(self):
        pass

    def get_done(self):
        return self.__done

    def set_done(self, tf):
        self.__done = tf

    done = property(get_done, set_done, None, 'done flag')

    def stop(self):
        self.done = True
