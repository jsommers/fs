#!/usr/bin/env python

__author__ = 'jsommers@colgate.edu'

import copy
import ipaddr
import socket
import time
from collections import namedtuple
from fsutil import removeuniform
from pox.openflow.libopenflow_01 import ofp_match
import pox.openflow.libopenflow_01 as of
import pdb

class IncompatibleFlowlets(Exception):
    pass

class InvalidFlowletTimestamps(Exception):
    pass

class InvalidFlowletVolume(Exception):
    pass

class FlowIdent(object):
    '''the class formerly known as 'FiveTuple', now a bit more general.'''
    __slots__ = ['__key']

    FLOW_IDENTIFIERS = ('srcip','dstip','ipproto','sport','dport','srcmac','dstmac','vlan')
    FlowKey = namedtuple('FlowKey',FLOW_IDENTIFIERS)

    def __init__(self, srcip=0, dstip=0, ipproto=0, sport=0, dport=0, srcmac=0, dstmac=0, vlan=0):
        # store the flow identifier as a (named) tuple for efficiency
        self.__key = FlowIdent.FlowKey(srcip, dstip, ipproto, sport, dport, srcmac, dstmac, vlan)

    def mkreverse(self):
        rv = FlowIdent(self.key.dstip, self.key.srcip, self.key.ipproto, self.key.dport, self.key.sport, self.key.dstmac, self.key.srcmac, self.key.vlan)
        return rv

    def __str__(self):
        return str(self.key)

    @property
    def key(self):
        return self.__key

class Flowlet(object):
    __slots__ = ['__mss','__iptos','__pkts','__bytes','__flowident','__tcpflags','__ackflow','__flowstart','__flowend','ingress_intf']
    def __init__(self, ident, pkts=0, bytes=0, tcpflags=0):
        self.__flowident = ident
        self.__flowstart = -1.0
        self.__flowend = -1.0
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
        return self.ipproto == socket.IPPROTO_TCP and (self.tcpflags & 0x01 or self.tcpflags & 0x04)

    @property
    def key(self):
        return self.flowident.key

    @property
    def size(self):
        return self.bytes

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
        if self.ipproto == socket.IPPROTO_TCP:
            return 'tcp'
        elif self.ipproto == socket.IPPROTO_UDP:
            return 'udp'
        elif self.ipproto == socket.IPPROTO_ICMP:
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
    def srcmac(self):
        return self.flowident.key.srcmac

    @property
    def dstmac(self):
        return self.flowident.key.dstmac

    @property
    def vlan(self):
        return self.flowident.key.vlan

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
            raise InvalidFlowletTimestamps()
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

# Wrapper Class around POX for openflow messages
class ofp_pox_messages:
    __slots__ = ['pox_ofp_message']

    def __init__(self, message_type, **kargs):
        if message_type == 'ofp_packet_out':
            self.pox_ofp_message = of.ofp_packet_out()
            if 'action' in kargs:
                if kargs['action'] == 'flood':
                    self.pox_ofp_message.actions.append(of.ofp_action_output(port = of.OFPP_FLOOD))
                elif kargs['action'] == 'ofpp_all':
                    self.pox_ofp_message.actions.append(of.ofp_action_output(port = of.OFPP_ALL))

        elif message_type == 'ofp_flow_mod':
            if 'match' in kargs:
                if 'command' in kargs:
                    if kargs['command'] == 'add':
                        self.pox_ofp_message = of.ofp_flow_mod(command=of.OFPFC_ADD, \
                                                                   match=kargs['match'])
                else:
                    self.pox_ofp_message = of.ofp_flow_mod(match=kargs['match'])
            else:
                self.pox_ofp_message = of.ofp_flow_mod()
            if 'match_dl_dst' in kargs:
                self.pox_ofp_message.match.dl_dst = kargs['match_dl_dst']
            if 'match_dl_src' in kargs:
                self.pox_ofp_message.match.dl_src = kargs['match_dl_src']
            if 'idle_timeout' in kargs:
                self.pox_ofp_message.idle_timeout = kargs['idle_timeout']
            if 'hard_timeout' in kargs:
                self.pox_ofp_message.hard_timeout = kargs['hard_timeout']
            if 'action' in kargs:
                if kargs['action'] == 'flood':
                    self.pox_ofp_message.actions.append(of.ofp_action_output(port = of.OFPP_FLOOD))
                elif isinstance(kargs['action'], dict):
                    if 'dstmac' in kargs['action'].keys():
                        self.pox_ofp_message.actions.append(of.ofp_action_dl_addr.set_dst(\
                                kargs['action']['dstmac']))
                    if 'port' in kargs['action'].keys():
                        self.pox_ofp_message.actions.append(of.ofp_action_output(port = kargs['action']['port']))
                else:
                    self.pox_ofp_message.actions.append(of.ofp_action_output(port = kargs['action']))
            
        elif message_type == 'ofp_packet_in':
            self.pox_ofp_message = of.ofp_packet_in()
            if 'reason' in kargs:
                self.pox_ofp_message.reason = kargs['reason']
            if 'in_port' in kargs:
                self.pox_ofp_message.in_port = kargs['in_port']

        elif message_type == 'ofp_flow_removed':
            self.pox_ofp_message = of.ofp_flow_removed()
            if 'match' in kargs:
                self.pox_ofp_message.match = kargs['match']
            if 'cookie' in kargs:
                self.pox_ofp_message.cookie = kargs['cookie']
            if 'priority' in kargs:
                self.pox_ofp_message.priority = kargs['priority']
            if 'reason' in kargs:
                self.pox_ofp_message.reason = kargs['reason']
            if 'duration_sec' in kargs:
                self.pox_ofp_message.suration_sec = kargs['duration_sec']
            if 'duration_nsec' in kargs:
                self.pox_ofp_message.duration_nsec = kargs['duration_nsec']
            if 'packet_count' in kargs:
                self.pox_ofp_message.packet_count = kargs['packet_count']
            if 'byte_count' in kargs:
                self.pox_ofp_message.byte_count = kargs['byte_count']

class OpenflowMessage(Flowlet):
    __slots__ = ['context', 'message', 'message_type', 'data', 'actions']

    def __init__(self, flowid, message_type, **kargs):
        Flowlet.__init__(self, flowid)
        # Creating class object of the message_type
        self.message = ofp_pox_messages(message_type, **kargs) # e.g., ofp_packet_out, ofp_flow_mod, 
        self.message_type = message_type
        self.data = None
        self.context = (None,None,None)

    def set_context(self, origin, destination, previous):
        self.context = (origin, destination, previous)

    def get_context(self):
        return self.context
    
    @property
    def in_port(self):
        if (self.message_type == 'ofp_packet_in'):
            return self.message.pox_ofp_message.in_port

    @property
    def actions(self):
        if (self.message_type == 'ofp_packet_out'):
            return self.message.pox_ofp_message.actions

    def __str__(self):
        return "--".join([Flowlet.__str__(self), self.message_type])

# Added by Joel
# class OpenflowMessage(Flowlet):
#     __slots__ = ['message','data']

#     def __init__(self, flowid, message):
#         Flowlet.__init__(self, flowid)
#         self.message = message # e.g., object types ofp_packet_out, ofp_flow_mod
#         self.data = None       # e.g., an attached data flowlet to go along with OF
#                                # control message


def ofp_match_from_flowlet(flowlet, ports=False):
    m = ofp_match()
    m.dl_src = flowlet.srcmac
    m.dl_dst = flowlet.dstmac
    m.dl_vlan = flowlet.vlan
    m.nw_src = flowlet.srcaddr
    m.nw_dst = flowlet.dstaddr
    m.nw_proto = flowlet.ipproto
    if ports:
        m.tp_src = flowlet.srcport
        m.tp_dst = flowlet.dstport
    return m 
    

def flowident_from_ofp_match(m):
    return FlowIdent(srcip=m.nw_src, dstip=m.nw_dst, ipproto=m.nw_proto, sport=m.tp_src, dport=m.tp_dst, srcmac=m.dl_src, dstmac=m.dl_dst, vlan=m.dl_vlan)
    
