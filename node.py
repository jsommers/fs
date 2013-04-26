#!/usr/bin/python

__author__ = 'jsommers@colgate.edu'

from abc import ABCMeta, abstractmethod
import logging
from random import random
import copy
from flowlet import *
from collections import Counter, defaultdict
from flowexport import null_export_factory, text_export_factory, cflowd_export_factory
import copy
import networkx
from pytricia import PyTricia
import time
from fscommon import *
from fsutil import default_ip_to_macaddr, subnet_generator

class MeasurementConfig(object):
    __slots__ = ['__counterexport','__exportfn','__exportinterval','__exportfile','__pktsampling','__flowsampling','__maintenance_cycle','__longflowtmo','__flowinactivetmo','__clockbase']
    def __init__(self, **kwargs):
        self.__counterexport = bool(kwargs.get('counterexport',False))
        self.__exportfn = eval(kwargs.get('flowexportfn','null_export_factory'))
        self.__exportinterval = int(kwargs.get('counterexportinterval',1))
        self.__exportfile = kwargs.get('counterexportfile',None)
        self.__pktsampling = float(kwargs.get('pktsampling',1.0))
        self.__flowsampling = float(kwargs.get('flowsampling',1.0))
        self.__maintenance_cycle = float(kwargs.get('maintenance_cycle',60.0))
        self.__longflowtmo = int(kwargs.get('longflowtmo',-1))
        self.__flowinactivetmo = int(kwargs.get('flowinactivetmo',-1))
        self.__clockbase = 0
        if bool(kwargs.get('usewallclock',False)):
            self.__clockbase = time.time()

    @property 
    def counterexport(self):
        return self.__counterexport

    @property
    def exportfn(self):
        return self.__exportfn

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

    @property
    def clockbase(self):
        return self.__clockbase

    def __str__(self):
        return 'MeasurementConfig <{}, {}, {}>'.format(str(self.exportfn), str(self.counterexport), self.exportfile)


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
        self.exporter = self.config.exportfn(node_name)

    def start(self):
        # start router maintenance loop at random within first 10 seconds
        # maintenance loop periodically fires thereafter
        # (below code is used to desynchronize router maintenance across net)

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
            print >>self.counter_exportfh, '%8.3f %s->%s %d bytes %d pkts %d flows' % (fscore().now+self.config.clockbase, k, self.node_name, v[self.BYTECOUNT], v[self.PKTCOUNT], v[self.FLOWCOUNT])
        self.counters = defaultdict(Counter)
        fscore().after(self.config.exportinterval, 'node-snmpexport-'+str(self.node_name), self.counter_export)

    def flow_export(self):
        config = self.config
        killlist = []
        for k,v in self.flow_table.iteritems():
            # if flow has been inactive for inactivetmo seconds, or
            # flow has been active longer than longflowtmo seconds, expire it
            if config.flowinactivetmo > 0 and ((fscore().now - v.flowend) >= config.flowinactivetmo) and v.flowend > 0:
                self.exporter.exportflow(fscore().now+self.config.clockbase, v)
                killlist.append(k)

            if config.longflowtmo > 0 and ((fscore().now - v.flowstart) >= config.longflowtmo) and v.flowend > 0:
                self.exporter.exportflow(fscore().now+self.config.clockbase, v)
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
            self.exporter.exportflow(fscore().now+self.config.clockbase, v)
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
            flet.flowend = fscore().now
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

class Node(object):
    '''Base Node class in fs.  All subclasses will want to at least override flowlet_arrival to handle
       the arrival of a new flowlet at the node.'''
    __metaclass__ = ABCMeta

    __slots__ = ['__name','node_measurements','interfaces','logger','arp_table_ip', 'arp_table_node']

    def __init__(self, name, measurement_config, **kwargs):
        # exportfn, exportinterval, exportfile):
        self.__name = name
        if measurement_config:
            self.node_measurements = NodeMeasurement(measurement_config, name)
        else:
            self.node_measurements = NullMeasurement()
        self.interfaces = {}
        self.logger = get_logger()
        self.arp_table_ip = {}
        self.arp_table_node = defaultdict(list)

    def addStaticArpEntry(self, ipaddr, macaddr, node):
        '''
        Key in ARP table: destination IP address (not a prefix, an actual address).

        Value in table: tuple containing MAC address corresponding to IP address, and node name.
        The node name is the node that "owns" the IP address/MAC address pair (i.e. remote IP/MAC.
        '''
        self.arp_table_ip[ipaddr] = (macaddr, node)
        self.arp_table_node[node].append( (ipaddr, macaddr) )

    def removeStaticArpEntry(self, ipaddr):
        '''
        Remove entry in ARP table for a given IP address.
        '''
        if ipaddr in self.arp_table_ip:
            mac,node = self.arp_table_ip.pop(ipaddr)
            xli = self.arp_table_node[node]
            xli.remove( (ipaddr,mac) )

    def linkFromNexthopIpAddress(self, ipaddr):
        '''Given a next-hop IP address, return the link object that connects current node
        to that remote IP address, or an exception if nothing exists.'''
        return self.interfaces.get(ipaddr,None)

    def linkFromNexthopNode(self, nodename, flowkey=None):
        '''Given a next-hop node name, return a link object that gets us to that node.  Optionally provide
        a flowlet key in order to hash correctly to the right link in the case of multiple links.'''
        tlist = self.arp_table_node.get(nodename)
        if not tlist:
            raise ArpFailure()
        tup = tlist[hash(flowkey) % len(tlist)]
        return self.interfaces[tup[0]]

    @property
    def name(self):
        return self.__name

    def start(self):
        self.node_measurements.start()

    def stop(self):
        self.node_measurements.stop()

    @abstractmethod
    def flowlet_arrival(self, flowlet, prevnode, destnode, input_port):
        pass

    def measure_flow(self, flowlet, prevnode, inport):
        self.node_measurements.add(flowlet, prevnode, inport)

    def unmeasure_flow(self, flowlet, prevnode):
        self.node_measurements.remove(flowlet, prevnode)

    def add_link(self, link, hostip, remoteip, next_node):
        '''Add a new interface and link to this node.  link is the link object connecting
        this node to next_node.  hostip is the ip address assigned to the local interface for this
        link, and remoteip is the ip address assigned to the remote interface of the link.'''
        self.interfaces[remoteip] = link
        remotemac = default_ip_to_macaddr(remoteip)
        self.addStaticArpEntry(remoteip, remotemac, next_node)


    # def forward(self, next_node, flet, destination):
    #     '''forward a flowlet to next_node, on its way to destination'''
    #     # FIXME: this does, effectively, ECMP for any parallel links, regardless
    #     # of weight.  what's the right thing to do?
    #     links = self.link_table[next_node]
    #     port = hash(flet) % len(links)
    #     links[port].flowlet_arrival(flet, self.name, destination)


class ForwardingFailure(Exception):
    pass

class Router(Node):
    __slots__ = ['autoack', 'forwarding_table']

    def __init__(self, name, measurement_config, **kwargs): 
        Node.__init__(self, name, measurement_config, **kwargs)
        self.autoack=kwargs.get('autoack',False)
        self.forwarding_table = PyTricia()

    def addForwardingEntry(self, prefix, nexthop):
        '''Add new forwarding table entry to Node, given a destination prefix
           and a nexthop (node name)'''
        pstr = str(prefix)
        xnode = None
        if pstr in self.forwarding_table:
            xnode = self.forwarding_table[pstr]
        else:
            xnode = {}
            self.forwarding_table[pstr] = xnode
        xnode['net'] = prefix
        dlist = xnode.get('dests', None)
        if not dlist:
            xnode['dests'] = [ nexthop ]
        else:
            if nexthop not in xnode['dests']:
                xnode['dests'].append(ipaddr)

    def removeForwardingEntry(self, prefix, nexthop):
        '''Remove an entry from the Node forwarding table.'''
        pstr = str(prefix)
        if pstr not in self.forwarding_table:
            return
        xnode = self.forwarding_table[pstr]
        dlist = xnode.get('dests', None)
        if dlist:
            # remove next hop entry.  if that was the last
            # entry, remove the entire prefix from the table.
            dlist.remove(nexthop)
            if not dlist:
                del self.forwarding_table[pstr]

    def nextHop(self, destip):
        '''Return the next hop from the local forwarding table (next node, ipaddr), based on destination IP address (or prefix)'''
        xnode = self.forwarding_table.get(str(destip), None)
        if xnode:
            dlist = xnode['dests']
            return dlist[hash(destip) % len(dlist)]
        raise ForwardingFailure()

    def flowlet_arrival(self, flowlet, prevnode, destnode, input_port):
        if isinstance(flowlet, SubtractiveFlowlet):
            killlist = []
            ok = []
            for k,flet in self.flow_table.iteritems():
                if next(flowlet.action) and (not flowlet.srcaddr or flet.srcaddr in flowlet.srcaddr) and (not flowlet.dstaddr or flet.dstaddr in flowlet.dstaddr) and (not flowlet.ipproto or flet.ipproto == flowlet.ipproto):
                    killlist.append(k)
                else:
                    ok.append(k)
            for kkey in killlist:
                del self.flow_table[kkey]

            if destnode != self.name:
                nh = fscore().nexthop(self.name, destnode)
                if nh:
                    self.forward(nh, flowlet, destnode)
            return

        else:
            # a "normal" Flowlet object
            self.measure_flow(flowlet, prevnode, input_port)

            if flowlet.endofflow:
                self.unmeasure_flow(flowlet, prevnode)

            if destnode == self.name:
                if self.autoack and flowlet.ipproto == socket.IPPROTO_TCP and not flowlet.ackflow:
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


                    destnode = fscore().destnode(self.name, revflow.dstaddr)

                    # guard against case that we can't do the autoack due to
                    # no "real" source (i.e., source was spoofed or source addr
                    # has no route)
                    if destnode and destnode != self.name:
                        nh = fscore().nexthop(self.name, destnode)
                        if nh:
                            self.forward(nh, revflow, destnode)
                        else:
                            self.logger.debug('No route from %s to %s (trying to run ackflow)' % (self.name, destnode))

            else:
                nextnode = self.nextHop(flowlet.dstaddr)                
                link = self.linkFromNexthopNode(nextnode, flowkey=flowlet.key)
                link.flowlet_arrival(flowlet, self.name, destnode)   

                # nh = fscore().topology.nexthop(self.name, destnode)
                # assert (nh != self.name)
                # if nh:
                #     self.forward(nh, flowlet, destnode)
                # else:
                #     self.logger.debug('No route from %s to %s (in router nh decision; ignoring)' % (self.name, destnode))

