#!/usr/bin/python

__author__ = 'jsommers@colgate.edu'

import heapq
import sys
import signal
import logging
import time
from optparse import OptionParser
import configurator 
import fscommon

class FsCore(object):
    # FIXME: should make this a static property, non-modifiable
    sim = None

    def __init__(self, interval, endtime=1.0, debug=False, progtick=0.05):
        self.__debug = debug
        self.__interval = interval
        self.__now = 0.0
        self.__logger = fscommon.get_logger(debug)

        self.__heap = []
        self.endtime = endtime
        self.starttime = self.__now
        self.intr = False
        self.progtick = progtick
        self.topology = configurator.NullTopology()
        FsCore.sim = self

    def progress(self):
        complete = (self.now - self.starttime) / float(self.endtime)
        self.logger.info('simulation completion: %2.2f' % (complete))
        self.after(self.endtime*self.progtick, 'progress indicator', self.progress)

    def sighandler(self, signum, stackframe):
        self.intr = True

    @property
    def debug(self):
        return self.__debug

    @property
    def now(self):
        return self.__now

    @property  
    def logger(self):
        return self.__logger

    @property
    def interval(self):
        return self.__interval

    def after(self, delay, evid, fn, *fnargs):
        expire_time = self.now + delay
        heapq.heappush(self.__heap, (expire_time, evid, fn, fnargs))

    def run(self, scenario):
        cfg = configurator.FsConfigurator(self.debug)
        if scenario:
            self.topology = cfg.load_config(scenario)
        else:
            self.logger.info("No simulation scenario specified.  I'll just do nothing!")

        self.after(0.0, 'progress indicator', self.progress)

        simstart = self.__now
        self.topology.start()
        while (self.__now - simstart) < self.endtime and not self.intr:
            if len(self.__heap) == 0:
                break
            expire_time,evid,fn,fnargs = heapq.heappop(self.__heap)
            self.logger.debug("FS event: '{}'' @{}".format(evid, expire_time))
            self.__now = expire_time
            fn(*fnargs)
            
        self.logger.debug("Reached simulation end time: {}, {}".format(self.now, self.endtime))
        self.topology.stop()


def main():
    parser = OptionParser()
    parser.prog = "flowmax.py"
    parser.add_option("-d", "--debug", dest="debug", default=False,
                      action="store_true", help="Turn on debugging output")
    parser.add_option("-t", "--simtime", dest="simtime", default=300, type=int,
                      help="Set amount of simulation time; default=300 sec")
    parser.add_option("-i", "--interval", dest="interval", default=1.0, type=float,
                      help="Set the simulation tick interval (sec); default=1 sec")
    (options, args) = parser.parse_args()

    if len(args) != 1:
        print >>sys.stderr,"Usage: %s [options] <scenario.dot>" % (sys.argv[0])
        sys.exit(0)

    sim = FS(options.interval, endtime=options.simtime, debug=options.debug)
    signal.signal(signal.SIGINT, sim.sighandler)
    sim.run(args[0])

if __name__ == '__main__':
    main()
