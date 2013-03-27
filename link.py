#!/usr/bin/python

__author__ = 'jsommers@colgate.edu'

import logging
from fs import FsCore
import fscommon

class Link(object):
    __slots__ = ['capacity','delay','egress_node','ingress_node','backlog','bdp','queuealarm','lastalarm','alarminterval','doqdelay','logger']
    def __init__(self, capacity, delay, ingress_node, egress_node):
        self.capacity = capacity # bytes/sec
        self.delay = delay
        self.egress_node = egress_node
        self.ingress_node = ingress_node
        self.backlog = 0
        self.bdp = self.capacity * self.delay  # bytes
        self.queuealarm = 1.0
        self.lastalarm = -1
        self.alarminterval = 30
        self.doqdelay = True
        self.logger = fscommon.get_logger()

    def decrbacklog(self, amt):
        self.backlog -= amt

    def flowlet_arrival(self, flowlet, prevnode, destnode):
        wait = self.delay + flowlet.size / self.capacity

        if self.doqdelay:
            queuedelay = max(0, (self.backlog - self.bdp) / self.capacity)
            wait += queuedelay
            self.backlog += flowlet.size 
            if queuedelay > self.queuealarm and FsCore.sim.now - self.lastalarm > self.alarminterval:
                self.lastalarm = FsCore.sim.now
                self.logger.warn("Excessive backlog on link %s-%s (%f sec (%d bytes))" % (self.ingress_node.name, self.egress_node.name, queuedelay, self.backlog))
            FsCore.sim.after(wait, 'link-decrbacklog-'+str(self.egress_node.name), self.decrbacklog, flowlet.size)

        FsCore.sim.after(wait, 'link-flowarrival-'+str(self.egress_node.name), self.egress_node.flowlet_arrival, flowlet, prevnode, destnode)
