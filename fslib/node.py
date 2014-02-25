#!/usr/bin/python

__author__ = 'jsommers@colgate.edu'

from abc import ABCMeta, abstractmethod
from importlib import import_module
import logging
from random import random
import copy
from fslib.flowlet import *
from collections import Counter, defaultdict, namedtuple
import copy
import networkx
from pytricia import PyTricia
import time
from fslib.common import *
from fslib.link import NullLink
from socket import IPPROTO_TCP


class MeasurementConfig(object):
    __slots__ = ['__counterexport','__exporttype','__exportinterval','__exportfile','__pktsampling','__flowsampling','__maintenance_cycle','__longflowtmo','__flowinactivetmo']
    def __init__(self, **kwargs):
        self.__counterexport = bool(eval(str(kwargs.get('counterexport','False'))))
        self.__exporttype = kwargs.get('flowexport','null')
        self.__exportinterval = int(kwargs.get('counterexportinterval',1))
        self.__exportfile = kwargs.get('counterexportfile',None)
        self.__pktsampling = float(kwargs.get('pktsampling',1.0))
        self.__flowsampling = float(kwargs.get('flowsampling',1.0))
        self.__maintenance_cycle = float(kwargs.get('maintenance_cycle',60.0))
        self.__longflowtmo = int(kwargs.get('longflowtmo',-1))
        self.__flowinactivetmo = int(kwargs.get('flowinactivetmo',-1))

    @property 
    def counterexport(self):
        return self.__counterexport

    @property
    def exporttype(self):
        return self.__exporttype

    def exportclass(self):
        '''Based on exporter name, return the class object that can be
        used to instantiate actual flow exporter objects'''
        mod = import_module("flowexport.{}export".format(self.exporttype))
        cls = getattr(mod, "{}Exporter".format(self.exporttype.capitalize()))
        return cls

    @property 
    def exportinterval(self):
        return self.__exportinterval

    @property 
    def exportfile(self):
        return self.__exportfile

    @property 
    def pktsampling(self):
        return self.__pktsampling

    @property 
    def flowsampling(self):
        return self.__flowsampling

    @property 
    def maintenance_cycle(self):
        return self.__maintenance_cycle

    @property 
    def longflowtmo(self):
        return self.__longflowtmo

    @property 
    def flowinactivetmo(self):
        return self.__flowinactivetmo

    def __str__(self):
        return 'MeasurementConfig <{}, {}, {}>'.format(str(self.exporttype), str(self.counterexport), self.exportfile)


class NullMeasurement(object):
    def start(self):
        pass
    def stop(self):
        pass
    def add(self, flowlet, prevnode, inport):
        pass
    def remove(self, flowlet, prevnode):
        pass


class NodeMeasurement(NullMeasurement):
    BYTECOUNT = 0
    PKTCOUNT = 1
    FLOWCOUNT = 2
    __slots__ = ['config','counters','flow_table','node_name','exporter','counters','counter_exportfh']

    def __init__(self, measurement_config, node_name):
        self.config = measurement_config
        self.node_name = node_name
        self.flow_table = {}
        self.counters = defaultdict(Counter)
        self.counter_exportfh = None
        self.exporter = self.config.exportclass()(node_name)

    def start(self):
        '''
        start router maintenance loop at random within first 10 seconds.
        maintenance loop periodically fires thereafter
        (below code is used to desynchronize router maintenance across net)
        '''
        fscore().after(random()*self.config.maintenance_cycle, 'node-flowexport-'+str(self.node_name), self.flow_export)

        if self.config.counterexport and self.config.exportinterval > 0:
            if self.config.exportfile == 'stdout':
                self.counter_exportfh = sys.stdout
            else:
                self.counter_exportfh = open('{}_{}.txt'.format(self.node_name, self.config.exportfile), 'w')
            fscore().after(0, 'router-snmpexport-'+str(self.node_name), self.counter_export)

    def counter_export(self):
        if not self.config.counterexport:
            return

        for k,v in self.counters.iteritems():
            print >>self.counter_exportfh, '%8.3f %s->%s %d bytes %d pkts %d flows' % (fscore().now, k, self.node_name, v[self.BYTECOUNT], v[self.PKTCOUNT], v[self.FLOWCOUNT])
        self.counters = defaultdict(Counter)
        fscore().after(self.config.exportinterval, 'node-snmpexport-'+str(self.node_name), self.counter_export)

    def flow_export(self):
        config = self.config
        killlist = []
        for k,v in self.flow_table.iteritems():
            # if flow has been inactive for inactivetmo seconds, or
            # flow has been active longer than longflowtmo seconds, expire it
            if config.flowinactivetmo > 0 and ((fscore().now - v.flowend) >= config.flowinactivetmo) and v.flowend > 0:
                self.exporter.exportflow(fscore().now, v)
                killlist.append(k)

            if config.longflowtmo > 0 and ((fscore().now - v.flowstart) >= config.longflowtmo) and v.flowend > 0:
                self.exporter.exportflow(fscore().now, v)
                killlist.append(k)

        for k in killlist:
            if k in self.flow_table:
                del self.flow_table[k]

        # reschedule next router maintenance
        fscore().after(self.config.maintenance_cycle, 'node-flowexport-'+str(self.node_name), self.flow_export)

    def stop(self):
        killlist = []
        for k,v in self.flow_table.iteritems():
            if v.flowend < 0:
                v.flowend = fscore().now
            self.exporter.exportflow(fscore().now, v)
            killlist.append(k)

        for k in killlist:
            del self.flow_table[k]
        self.exporter.shutdown()
        if self.counter_exportfh and self.config.exportfile != 'stdout':
            self.counter_exportfh.close() 

    def __nosample(self):
        if self.config.flowsampling < 1.0:
            return random() > self.config.flowsampling

    def __addflow(self, flowlet, prevnode, inport):
        newflow = 0
        flet = None
        if flowlet.key in self.flow_table:
            flet = self.flow_table[flowlet.key]
            # flet.flowend = fscore().now ### FIXME!!!
            flet += flowlet
        else:
            # NB: shallow copy of flowlet; will share same reference to
            # five tuple across the entire simulation
            newflow = 1
            flet = copy.copy(flowlet) 
            flet.flowend += fscore().now 
            flet.flowstart = fscore().now
            self.flow_table[flet.key] = flet
            flet.ingress_intf = "{}:{}".format(prevnode,inport)
        return newflow

    def __addcounters(self, flowlet, prevnode, newflow):
        counters = self.counters[prevnode]
        counters[self.BYTECOUNT] += flowlet.bytes
        counters[self.PKTCOUNT] += flowlet.pkts
        counters[self.FLOWCOUNT] += newflow

    def add(self, flowlet, prevnode, inport):
        if self.__nosample():
            return
        newflow = self.__addflow(flowlet, prevnode, inport)
        if self.config.counterexport:
            self.__addcounters(flowlet, prevnode, newflow)

    def remove(self, flowlet, prevnode):
        if flowlet.key not in self.flow_table:
            return

        stored_flowlet = self.flow_table[flowlet.key]
        if stored_flowlet.flowend < 0:
            stored_flowlet.flowend = fscore().now
        del self.flow_table[flowlet.key]
        self.exporter.exportflow(fscore().now, stored_flowlet)

class ArpFailure(Exception):
    pass

PortInfo = namedtuple('PortInfo', ('link','localip','remoteip','localmac','remotemac'))

class Node(object):
    '''Base Node class in fs.  All subclasses will want to at least override flowlet_arrival to handle
       the arrival of a new flowlet at the node.'''
    __metaclass__ = ABCMeta

    __slots__ = ['__name','__started','node_measurements','ports','logger','node_to_port_map']

    def __init__(self, name, measurement_config, **kwargs):
        # exportfn, exportinterval, exportfile):
        self.__name = name
        if measurement_config:
            self.node_measurements = NodeMeasurement(measurement_config, name)
        else:
            self.node_measurements = NullMeasurement()
        self.ports = {}
        self.node_to_port_map = defaultdict(list)
        self.logger = get_logger(self.name)
        self.__started = False

    @property
    def started(self):
        return self.__started

    def portFromNexthopNode(self, nodename, flowkey=None):
        '''Given a next-hop node name, return a link object that gets us to that node.  Optionally provide
        a flowlet key in order to hash correctly to the right link in the case of multiple links.'''
        tlist = self.node_to_port_map.get(nodename)
        if not tlist:
            return None
        localip = tlist[hash(flowkey) % len(tlist)]
        return self.ports[localip]

    @property
    def name(self):
        return self.__name

    def start(self):
        self.__started = True
        self.node_measurements.start()

    def stop(self):
        self.node_measurements.stop()

    @abstractmethod
    def flowlet_arrival(self, flowlet, prevnode, destnode, input_ident=None):
        pass

    def measure_flow(self, flowlet, prevnode, inport):
        self.node_measurements.add(flowlet, prevnode, inport)

    def unmeasure_flow(self, flowlet, prevnode):
        self.node_measurements.remove(flowlet, prevnode)

    def add_link(self, link, localip, remoteip, next_node):
        '''Add a new interface and link to this node.  link is the link object connecting
        this node to next_node.  hostip is the ip address assigned to the local interface for this
        link, and remoteip is the ip address assigned to the remote interface of the link.'''
        localip = str(localip)
        remoteip = str(remoteip)
        self.ports[localip] = PortInfo(link, localip, remoteip, None, None)
        self.node_to_port_map[next_node].append(localip)

class ForwardingFailure(Exception):
    pass

class Router(Node):
    __slots__ = ['autoack', 'forwarding_table', 'default_link', 'trafgen_ip']

    def __init__(self, name, measurement_config, **kwargs): 
        Node.__init__(self, name, measurement_config, **kwargs)
        self.autoack=bool(eval(str(kwargs.get('autoack','False'))))
        self.forwarding_table = PyTricia(32)
        self.default_link = None

        from fslib.configurator import FsConfigurator
        ipa,ipb = [ ip for ip in next(FsConfigurator.link_subnetter).iterhosts() ]
        self.add_link(NullLink, ipa, ipb, 'remote')
        self.trafgen_ip = str(ipa)

    def setDefaultNextHop(self, nexthop):
        '''Set up a default next hop route.  Assumes that we just select the first link to the next
        hop node if there is more than one.'''
        self.logger.debug("Default: {}, {}".format(nexthop, str(self.node_to_port_map)))
        self.default_link = self.portFromNexthopNode(nexthop).link
        if not self.default_link:
            raise ForwardingFailure("Error setting default next hop: there's no static ARP entry to get interface")
        self.logger.debug("Setting default next hop for {} to {}".format(self.name, nexthop))

    def addForwardingEntry(self, prefix, nexthop):
        '''Add new forwarding table entry to Node, given a destination prefix
           and a nexthop (node name)'''
        pstr = str(prefix)
        self.logger.debug("Adding forwarding table entry: {}->{}".format(pstr, nexthop))
        xnode = self.forwarding_table.get(pstr, None)
        if not xnode:
            xnode = []
            self.forwarding_table[pstr] = xnode
        xnode.append(nexthop)

    def removeForwardingEntry(self, prefix, nexthop):
        '''Remove an entry from the Node forwarding table.'''
        pstr = str(prefix)
        if not self.forwarding_table.has_key(pstr):
            return
        xnode = self.forwarding_table.get(pstr)
        xnode.remove(nexthop)
        if not xnode:
            del self.forwarding_table[pstr]

    def nextHop(self, destip):
        '''Return the next hop from the local forwarding table (next node, ipaddr), based on destination IP address (or prefix)'''
        xlist = self.forwarding_table.get(str(destip), None)
        if xlist:
            return xlist[hash(destip) % len(xlist)]
        raise ForwardingFailure()

    def flowlet_arrival(self, flowlet, prevnode, destnode, input_ip=None):
        if input_ip is None:
            input_ip = self.trafgen_ip
        input_port = self.ports[input_ip]

        if isinstance(flowlet, SubtractiveFlowlet):
            killlist = []
            ok = []
            self.unmeasure_flow(flowlet, prevnode)
            if destnode != self.name:
                self.forward(flowlet, destnode)
            return

        # a "normal" Flowlet object
        self.measure_flow(flowlet, prevnode, str(input_port.localip))

        if flowlet.endofflow:
            self.unmeasure_flow(flowlet, prevnode)

        if destnode == self.name:
            if self.__should_make_acknowledgement_flow(flowlet):
                revflow = Flowlet(flowlet.flowident.mkreverse())
                
                revflow.ackflow = True
                revflow.flowstart = revflow.flowend = fscore().now

                if flowlet.tcpflags & 0x04: # RST
                    return

                if flowlet.tcpflags & 0x02: # SYN
                    revflow.tcpflags = revflow.tcpflags | 0x10
                    # print 'setting syn/ack flags',revflow.tcpflagsstr

                if flowlet.tcpflags & 0x01: # FIN
                    revflow.tcpflags = revflow.tcpflags | 0x10 # ack
                    revflow.tcpflags = revflow.tcpflags | 0x01 # fin

                revflow.pkts = flowlet.pkts / 2 # brain-dead ack-every-other
                revflow.bytes = revflow.pkts * 40

                self.measure_flow(revflow, self.name, input_port)

                # weird, but if reverse flow is short enough, it might only
                # stay in the flow cache for a very short period of time
                if revflow.endofflow:
                    self.unmeasure_flow(revflow, prevnode)

                destnode = fscore().topology.destnode(self.name, revflow.dstaddr)

                # guard against case that we can't do the autoack due to
                # no "real" source (i.e., source was spoofed or source addr
                # has no route)
                if destnode and destnode != self.name:
                    self.forward(revflow, destnode)
        else:
            self.forward(flowlet, destnode)


    def __should_make_acknowledgement_flow(self, flowlet):
        return self.autoack and flowlet.ipproto == IPPROTO_TCP and (not flowlet.ackflow)


    def forward(self, flowlet, destnode):
        nextnode = self.nextHop(flowlet.dstaddr)
        port = self.portFromNexthopNode(nextnode, flowkey=flowlet.key)
        link = port.link or self.default_link
        link.flowlet_arrival(flowlet, self.name, destnode)   
