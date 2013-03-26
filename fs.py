#!/usr/bin/python

__author__ = 'jsommers@colgate.edu'

import heapq
import sys
import ipaddr
import networkx

try:
    from networkx.algorithms.traversal.path import single_source_dijkstra_path, dijkstra_path_length
except:
    from networkx.algorithms.shortest_paths.weighted import single_source_dijkstra_path, dijkstra_path_length
else:
    print >>sys.stderr,"Can't find the necessary dijkstra's functions in your networkx installation.  You should probably upgrade to a more recent version."
    sys.exit(-1)

import random
import signal
import socket
import logging
from optparse import OptionParser

from pytricia import PyTricia
from flowlet import *
from traffic import *
from flowexport import *
from node import *
from node import *
from configurator import FsConfigurator


class InvalidRoutingConfiguration(Exception):
    pass


class Simulator(object):
    def __init__(self, interval, config, endtime=1.0, debug=False, progtick=0.05):
        self.debug = debug
        self.__interval = interval
        self.__now = time.time()
        self.heap = []
        self.endtime = endtime
        self.starttime = self.__now
        self.intr = False
        self.progtick = progtick
        self.logger = logging.getLogger('flowmax')
        if self.debug:
            logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
        else:
            logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s')

        configurator = FsConfigurator(self, self.debug)
        self.graph, self.routing, self.nodes, self.ipdestlpm, self.owdhash = configurator.loadconfig(config)

        self.after(0.0, 'progress indicator', self.progress)

    def progress(self):
        complete = (self.now - self.starttime) / float(self.endtime)
        self.logger.info('simulation completion: %2.2f' % (complete))
        self.after(self.endtime*self.progtick, 'progress indicator', self.progress)

    def sighandler(self, signum, stackframe):
        self.intr = True

    @property
    def now(self):
        return self.__now

    def after(self, delay, evid, fn, *fnargs):
        expire_time = self.now + delay
        heapq.heappush(self.heap, (expire_time, evid, fn, fnargs))

    @property
    def interval(self):
        return self.__interval


    def node(self, nname):
        '''get the node object corresponding to a name '''
        return self.nodes[nname]
        
        	
    def __linkdown(self, a, b, edict, ttf, ttr):
        '''kill a link & recompute routing '''
        self.logger.info('Link failed %s - %s' % (a,b))
        self.graph.remove_edge(a,b)
        self.__configure_routing()

        uptime = None
        try:
            uptime = next(ttr)
        except:
            self.logger.info('Link %s-%s permanently taken down (no recovery time remains in generator)' % (a, b))
            return
        else:
            self.after(uptime, 'link-recovery-'+a+'-'+b, self.__linkup, a, b, edict, ttf, ttr)

		
    def __linkup(self, a, b, edict, ttf, ttr):
        '''revive a link & recompute routing '''
        self.logger.info('Link recovered %s - %s' % (a,b))
        self.graph.add_edge(a,b,weight=edict.get('weight',1),delay=edict.get('delay',0),capacity=edict.get('capacity',1000000))
        FsConfigurator.configure_routing(self.routing, self.graph)

        downtime = None
        try:
            downtime = next(ttf)
        except:
            self.logger.info('Link %s-%s permanently going into service (no failure time remains in generator)' % (a, b))
            return
        else:
            self.after(downtime, 'link-failure-'+a+'-'+b, self.__linkdown, a, b, edict, ttf, ttr)


    def owd(self, a, b):
        '''get the raw one-way delay between a and b '''
        key = a + ':' + b
        rv = None
        if key in self.owdhash:
            rv = self.owdhash[key]
        return rv


    def delay(self, a, b):
        '''get the link delay between a and b '''
        d = self.graph[a][b]
        if d and 0 in d:
            return float(d[0]['delay'])
        return None

		
    def capacity(self, a, b):
        '''get the bandwidth between a and b '''
        d = self.graph[a][b]
        if d and 0 in d:
            return int(d[0]['capacity'])
        return None
		
    def nexthop(self, node, dest):
        '''
        return the next hop node for a given destination.
        node: current node
        dest: dest node name
        returns: next hop node name
        '''
        try:
            nlist = self.routing[node][dest]
        except:
            return None
        if len(nlist) == 1:
            return nlist[0]
        return nlist[1]

    def destnode(self, node, dest):
        '''
        return the destination node corresponding to a dest ip.
        node: current node
        dest: ipdest
        returns: destination node name
        '''
        # radix trie lpm lookup for destination IP prefix
        xnode = self.ipdestlpm.get(dest, None)

        if xnode:
            dlist = xnode['dests']
            best = None
            if len(dlist) > 1: 
                # in the case that there are multiple egress nodes
                # for the same IP destination, choose the closest egress
                best = None
                bestw = 10e6
                for d in dlist:
                    w = dijkstra_path_length(self.graph, node, d)
                    if w < bestw:
                        bestw = w
                        best = d
            else:
                best = dlist[0]

            if self.debug:
                print 'destnode search',dest,dlist,best
            return best
        else:
            raise InvalidRoutingConfiguration('No route for ' + dest)


    def __start_nodes(self):
        for nname,n in self.nodes.iteritems():
            n.start()

    def __stop_nodes(self):
        for nname,n in self.nodes.iteritems():
            n.stop()

    def run(self):
        self.__start_nodes()
            
        simstart = self.__now
        while (self.__now - simstart) < self.endtime and not self.intr:
            if len(self.heap) == 0:
                break
            expire_time,evid,fn,fnargs = heapq.heappop(self.heap)
            self.__now = expire_time
            if self.debug:
                print ("Event fires at {0}: {1}".format(self.now, evid))
            fn(*fnargs)
            
        if self.debug:
            print >>sys.stderr,'Reached simulation end time:',self.now,self.endtime

        self.__stop_nodes()
    


def main():
    parser = OptionParser()
    parser.prog = "flowmax.py"
    parser.add_option("-x", "--debug", dest="debug", default=False,
                      action="store_true", help="Turn on debugging output")
    parser.add_option("-t", "--simtime", dest="simtime", default=300, type=int,
                      help="Set amount of simulation time; default=300 sec")
    parser.add_option("-i", "--interval", dest="interval", default=1.0, type=float,
                      help="Set the simulation tick interval (sec); default=1 sec")

    # these next three options are no longer supported...
    parser.add_option("-s", "--snmpinterval", dest="snmpinterval", default=0.0, type=float,
                      help="Set the interval for dumping SNMP-like counters at each router (specify non-zero value to dump counters)")
    parser.add_option("-S", "--snmpexportfile", dest="snmpexportfile", default=None,
                      help="Specify file for dumping SNMP-like counters (or 'stdout')")
    parser.add_option("-e", "--exporter", dest="exporter", default="",
                      help="Set the export type (text,cflow)")
    (options, args) = parser.parse_args()

    if len(args) != 1:
        print >>sys.stderr,"Usage: %s [options] <scenario.dot>" % (sys.argv[0])
        sys.exit(0)

    scenario = args[0]

    if options.snmpexportfile:
        print >>sys.stderr,"This option is no longer supported.  Add 'counterexport=True' and 'counterexportfile=prefix' to your dot config file."
        sys.exit()        

    if options.exporter:
        print >>sys.stderr,"This option is no longer supported.  Add 'flowexportfn=text_export_factory' (or similar) to your dot config file."
#        sys.exit()        

    sim = Simulator(options.interval, scenario, endtime=options.simtime, debug=options.debug)
    signal.signal(signal.SIGINT, sim.sighandler)
    sim.run()

if __name__ == '__main__':
    main()
