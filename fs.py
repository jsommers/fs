#!/usr/bin/python
'''
Main class for fs: FsCore
'''

__author__ = 'jsommers@colgate.edu'


import sys
import signal
import os.path
from optparse import OptionParser
from heapq import heappush, heappop
import configurator 
import fscommon
import random


class FsCore(object):
    '''Core simulation object --- handles event scheduling and
    mediation between configuration and the classes that implement
    simulation functionalities.'''
    inited = False

    def __init__(self, interval, endtime=1.0, debug=False, progtick=0.05):
        if FsCore.inited:
            fscommon.get_logger().warn(
                    "Trying to initialize a new simulation object.")
            sys.exit(-1)

        self.__debug = debug
        self.__interval = interval
        self.__now = 0.0
        self.__logger = fscommon.get_logger(debug)

        self.__heap = []
        self.endtime = endtime
        self.starttime = self.__now
        self.intr = False
        self.progtick = progtick
        self.__topology = configurator.NullTopology()
        fscommon.set_fscore(self)

    def progress(self):
        '''Callback for printing simulation timeline progress'''
        complete = (self.now - self.starttime) / float(self.endtime)
        self.logger.info('simulation completion: %2.2f' % (complete))
        self.after(self.endtime*self.progtick, 
            'progress indicator', self.progress)

    def sighandler(self, signum, stackframe):
        '''Handle INT signal for shutting down simulation'''
        self.intr = True

    @property
    def topology(self):
        '''Return the topology object'''
        return self.__topology

    @property
    def debug(self):
        '''Return debug settings'''
        return self.__debug

    @property
    def now(self):
        '''Get the current simulation time'''
        return self.__now

    @property  
    def logger(self):
        '''Get the logger singleton object'''
        return self.__logger

    @property
    def interval(self):
        '''Get the core simulation event interval'''
        return self.__interval

    def after(self, delay, evid, callback, *fnargs):
        '''Schedule an event after delay seconds, identified by
        evid (string), a callback function, and any necessary arguments
        to the function'''
        if not isinstance(delay, (float,int)):
            print "Invalid delay: {}".format(delay)
            sys.exit(-1)
        expire_time = self.now + delay
        heappush(self.__heap, (expire_time, evid, callback, fnargs))

    def run(self, scenario, configonly=False):
        '''Start the simulation using a particular scenario filename'''
        cfg = configurator.FsConfigurator(self.debug)
        if scenario:
            root, ext = os.path.splitext(scenario)
            self.__topology = cfg.load_config(scenario, configtype=ext[1:])
        else:
            self.logger.info("No simulation scenario specified." +
                             "  I'll just do nothing!")

        if configonly:
            self.logger.info("Exiting after doing config.")
            return

        self.after(0.0, 'progress indicator', self.progress)

        simstart = self.__now
        self.topology.start()
        while (self.__now - simstart) < self.endtime and not self.intr:
            if len(self.__heap) == 0:
                break
            expire_time, evid, callback, fnargs = heappop(self.__heap)
            self.logger.debug("FS event: '{}'' @{}".format(evid, expire_time))
            self.__now = expire_time
            callback(*fnargs)
            
        self.logger.debug("Reached simulation end time: {}, {}"
                .format(self.now, self.endtime))
        self.topology.stop()


def main():
    '''Parse command-line arguments and start up the simulation'''
    parser = OptionParser()
    parser.prog = "fs.py"
    parser.add_option("-d", "--debug", dest="debug", 
                      default=False, action="store_true", 
                      help="Turn on debugging output")
    parser.add_option("-t", "--simtime", dest="simtime", 
                      default=300, type=int,
                      help="Set amount of simulation time")
    parser.add_option("-i", "--interval", dest="interval", 
                      default=1.0, type=float,
                      help="Set the simulation tick interval (sec)")
    parser.add_option("-c", "--configonly", dest="configonly",
                      default=False, action="store_true",
                      help="Just do configuration then exit")
    parser.add_option("-s", "--seed", dest="seed",
                      default=None, type="int",
                      help="Set random number generation seed.")
    (options, args) = parser.parse_args()

    if len(args) != 1:
        print >> sys.stderr,"Usage: %s [options] <scenario.dot>" % (sys.argv[0])
        sys.exit(0)

    random.seed(options.seed)

    sim = FsCore(options.interval, endtime=options.simtime, debug=options.debug)
    signal.signal(signal.SIGINT, sim.sighandler)
    sys.path.append("./traffic_generators")
    sys.path.append("./tcpmodels")
    sys.path.append("./flowexport")
    sim.run(args[0], configonly=options.configonly)

if __name__ == '__main__':
    main()
