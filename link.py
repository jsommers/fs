#!/usr/bin/python

'''
Models a single link in fs.  Each link knows about it's head (ingress) end
and tail (egress) end, how long (delay) and fat (capacity) it is, and can
optionally keep track of backlog (queuing delay).
'''

__author__ = 'jsommers@colgate.edu'

from fscommon import get_logger, fscore

class Link(object):
    '''
    Models a link in fs.
    '''
    __slots__ = ['capacity', 'delay', 'egress_node', 'egress_port', 'egress_name', 
                 'ingress_node', 'ingress_port', 'ingress_name', 'backlog', 'bdp',
                 'queuealarm', 'lastalarm', 'alarminterval', 'doqdelay', 'logger' ]
    def __init__(self, capacity, delay, ingress_node, egress_node):
        self.capacity = capacity/8.0 # bytes/sec
        self.delay = delay
        self.egress_node = egress_node
        self.egress_port = -1
        self.egress_name = Link.make_portname(self.egress_node.name, self.egress_port)
        self.ingress_node = ingress_node
        self.ingress_port = -1
        self.ingress_name = Link.make_portname(self.ingress_node.name, self.ingress_port)
        self.backlog = 0
        self.bdp = self.capacity * self.delay  # bytes
        self.queuealarm = 1.0
        self.lastalarm = -1
        self.alarminterval = 30
        self.doqdelay = True
        self.logger = get_logger()

    @staticmethod
    def make_portname(node, port):
        '''
        Make a canonical string representing a node/port pair (interface).
        '''
        return "{}:{}".format(node, port)

    def set_egress_port(self, endpoint):
        '''
        Set the egress port number of the link.
        '''
        self.egress_port = endpoint
        self.egress_name = Link.make_portname(self.egress_node, self.egress_port)

    def set_ingress_port(self, endpoint):
        '''
        Set the ingress port number of the link.
        '''
        self.ingress_port = endpoint
        self.ingress_name = Link.make_portname(self.ingress_node, self.ingress_port)

    def decrbacklog(self, amt):
        '''
        When a flowlet is forwarded, decrement the backlog for this link.
        '''
        self.backlog -= amt

    def flowlet_arrival(self, flowlet, prevnode, destnode):
        '''
        Handler for when a flowlet arrives on a link.  Compute how long the flowlet should be delayed
        before arriving at next node, and optionally handle computing queueing delay (backlog) on
        the link.
        '''
        wait = self.delay + flowlet.size / self.capacity

        if self.doqdelay:
            queuedelay = max(0, (self.backlog - self.bdp) / self.capacity)
            wait += queuedelay
            self.backlog += flowlet.size 
            if queuedelay > self.queuealarm and fscore().now - self.lastalarm > self.alarminterval:
                self.lastalarm = fscore().now
                self.logger.warn("Excessive backlog on link {}-{}({:3.2f} sec ({} bytes))".format(self.ingress_name, self.egress_name, queuedelay, self.backlog))
            fscore().after(wait, "link-decrbacklog-{}".format(self.egress_node.name), self.decrbacklog, flowlet.size)

        fscore().after(wait, "link-flowarrival-{}".format(self.egress_name, self.egress_port), self.egress_node.flowlet_arrival, flowlet, prevnode, destnode, self.egress_port)
