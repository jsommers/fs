#!/usr/bin/env python

__author__ = 'jsommers@colgate.edu'

import copy
import ipaddr
from socket import IPPROTO_TCP, IPPROTO_UDP, IPPROTO_ICMP
import time
from collections import namedtuple
from fslib.util import removeuniform, default_ip_to_macaddr


class IncompatibleFlowlets(Exception):
    pass

class InvalidFlowletTimestamps(Exception):
    pass

class InvalidFlowletVolume(Exception):
    pass

class FlowIdent(object):
    '''the class formerly known as FiveTuple'''
    __slots__ = ['__key']

    FLOW_IDENTIFIERS = ('srcip','dstip','ipproto','sport','dport')
    FlowKey = namedtuple('FlowKey',FLOW_IDENTIFIERS)

    def __init__(self, srcip='0.0.0.0', dstip='0.0.0.0', ipproto=0, sport=0, dport=0):
        # store the flow identifier as a (named) tuple for efficiency
        self.__key = FlowIdent.FlowKey(srcip, dstip, ipproto, sport, dport)

    def mkreverse(self):
        rv = FlowIdent(self.key.dstip, self.key.srcip, self.key.ipproto, self.key.dport, self.key.sport)
        return rv

    def __str__(self):
        return str(self.key)

    def __repr__(self):
        return str(self.key)

    @property
    def key(self):
        return self.__key

class Flowlet(object):
    __slots__ = ['__srcmac','__dstmac','__mss','__iptos','__pkts',
                 '__bytes','__flowident','__tcpflags','__ackflow',
                 '__flowstart','__flowend','ingress_intf']
    def __init__(self, ident, 
                 srcmac=None, dstmac=None,
                 pkts=0, bytes=0, tcpflags=0):
        self.__flowident = ident
        self.__flowstart = -1.0
        self.__flowend = -1.0
        self.__srcmac = srcmac 
        self.__dstmac = dstmac 
        self.pkts = pkts
        self.bytes = bytes
        self.ingress_intf = None
        self.iptos = 0x0
        self.mss = 1500
        self.tcpflags = 0x0
        self.ackflow = False

    @property
    def flowident(self):
        return self.__flowident

    @property
    def iptos(self):
        return self.__iptos

    @iptos.setter
    def iptos(self, iptos):
        self.__iptos = iptos

    @property
    def mss(self):
        return self.__mss

    @mss.setter
    def mss(self, m):
        assert(100 <= m <= 1500)
        self.__mss = m

    @property
    def endofflow(self):
        # check if tcp and FIN or RST
        return self.ipproto == IPPROTO_TCP and (self.tcpflags & 0x01 or self.tcpflags & 0x04)

    @property  
    def ident(self):
        return self.__flowident
        
    @property
    def key(self):
        return self.flowident.key

    @property
    def size(self):
        return self.bytes

    @property
    def srcmac(self):
        return self.__srcmac

    @srcmac.setter
    def srcmac(self, macaddr):
        self.__srcmac = macaddr

    @property
    def dstmac(self):
        return self.__dstmac

    @dstmac.setter
    def dstmac(self, macaddr):
        self.__dstmac = macaddr

    @property
    def srcaddr(self):
        return self.flowident.key.srcip

    @property
    def dstaddr(self):
        return self.flowident.key.dstip

    @property
    def ipproto(self):
        return self.flowident.key.ipproto

    @property
    def ipprotoname(self):
        if self.ipproto == IPPROTO_TCP:
            return 'tcp'
        elif self.ipproto == IPPROTO_UDP:
            return 'udp'
        elif self.ipproto == IPPROTO_ICMP:
            return 'icmp'
        else:
            return 'ip'

    @property
    def srcport(self):
        return self.flowident.key.sport

    @property
    def dstport(self):
        return self.flowident.key.dport

    @property
    def pkts(self):
        return self.__pkts

    @pkts.setter
    def pkts(self, p):
        if p < 0:
            raise InvalidFlowletVolume()
        self.__pkts = p

    @property
    def bytes(self):
        return self.__bytes
    
    @bytes.setter
    def bytes(self, b):
        if b < 0:
            raise InvalidFlowletVolume()
        self.__bytes = b

    @property
    def ackflow(self):
        return self.__ackflow

    @ackflow.setter
    def ackflow(self, a):
        self.__ackflow = a;

    def clear_tcp_flags(self):
        self.__tcpflags = 0x0

    def add_tcp_flag(self, flag):
        self.__tcpflags |= flag

    @property
    def tcpflags(self):
        return self.__tcpflags

    @tcpflags.setter
    def tcpflags(self, flags):
        self.__tcpflags = flags

    @property
    def tcpflagsstr(self):
        rv = []
        if self.tcpflags & 0x01: #fin
            rv.append('F')
        if self.tcpflags & 0x02: #syn
            rv.append('S')
        if self.tcpflags & 0x04: #rst
            rv.append('R')
        if self.tcpflags & 0x08: #push
            rv.append('P')
        if self.tcpflags & 0x10: #ack
            rv.append('A')
        if self.tcpflags & 0x20: #urg
            rv.append('U')
        if self.tcpflags & 0x40: #ece
            rv.append('E')
        if self.tcpflags & 0x80: #cwr
            rv.append('C')
        return ''.join(rv)

    @property
    def flowstart(self):
        return self.__flowstart

    @flowstart.setter
    def flowstart(self, fstart):
        if fstart < 0:
            raise InvalidFlowletTimestamps()
        self.__flowstart = fstart

    @property
    def flowend(self):
        return self.__flowend

    @flowend.setter
    def flowend(self, fend):
        if fend < 0 or fend < self.flowstart:
            raise InvalidFlowletTimestamps(self.__str__())
        self.__flowend = fend

    def __cmp__(self, other):
        return cmp(self.key, other.key)

    def __iadd__(self, other):
        if self.key != other.key:
            raise IncompatibleFlowlets()
        self.pkts += other.pkts
        self.bytes += other.bytes
        self.tcpflags |= other.tcpflags
        return self

    def __add__(self, other):
        if self.key != other.key:
            raise IncompatibleFlowlets()
        rv = copy.copy(self)
        rv.pkts += other.pkts
        rv.bytes += other.bytes
        rv.tcpflags |= other.tcpflags
        return rv

    def __str__(self):
        return "%0.06f %0.06f %s:%d->%s:%d %s 0x%0x %s %d %d %s" % (self.flowstart, self.flowend, self.srcaddr, self.srcport, self.dstaddr, self.dstport, self.ipprotoname, self.iptos, self.ingress_intf, self.pkts, self.bytes, self.tcpflagsstr)


class SubtractiveFlowlet(Flowlet):
    __slots__ = ['action']

    def __init__(self, ident, action):
        Flowlet.__init__(self, ident)
        self.action = action

  
