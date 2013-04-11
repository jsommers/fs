#!/usr/bin/python

__author__ = 'jsommers@colgate.edu'

import logging
from fscommon import *

class Link(object):
    __slots__ = ['capacity','delay','egress_node','egress_port', 'ingress_node','ingress_port', 'backlog','bdp','queuealarm','lastalarm','alarminterval','doqdelay','logger']
    def __init__(self, capacity, delay, ingress_node, egress_node):
        self.capacity = capacity # bytes/sec
        self.delay = delay
        self.egress_node = egress_node
        self.egress_port = -1
        self.ingress_node = ingress_node
        self.ingress_port = -1
        self.backlog = 0
        self.bdp = self.capacity * self.delay  # bytes
        self.queuealarm = 1.0
        self.lastalarm = -1
        self.alarminterval = 30
        self.doqdelay = True
        self.logger = get_logger()

    def set_egress_port(self, ep):
        self.egress_port = ep

    def set_ingress_port(self, ip):
        self.ingress_port = ip

    def decrbacklog(self, amt):
        self.backlog -= amt

    def flowlet_arrival(self, flowlet, prevnode, destnode):
        wait = self.delay + flowlet.size / self.capacity

        if self.doqdelay:
            queuedelay = max(0, (self.backlog - self.bdp) / self.capacity)
            wait += queuedelay
            self.backlog += flowlet.size 
            if queuedelay > self.queuealarm and fscore().now - self.lastalarm > self.alarminterval:
                self.lastalarm = fscore().now
                self.logger.warn("Excessive backlog on link %s:%d-%s:%d (%f sec (%d bytes))" % (self.ingress_node.name, self.ingress_port, self.egress_node.name, self.egress_port, queuedelay, self.backlog))
            fscore().after(wait, 'link-decrbacklog-'+str(self.egress_node.name), self.decrbacklog, flowlet.size)

        fscore().after(wait, "link-flowarrival-{}:{}".format(self.egress_node.name, self.egress_port), self.egress_node.flowlet_arrival, flowlet, prevnode, destnode, self.egress_port)
