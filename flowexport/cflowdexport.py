#!/usr/bin/env python

__author__ = 'jsommers@colgate.edu'

from flowexporter import FlowExporter
from ipaddr import IPAddress
from cflow import cflow

class CflowdExporter(FlowExporter):
    '''Export flowlets to Cflow format'''

    def __init__(self, rname):
        FlowExporter.__init__(self, rname)
        outname = self.routername + '.cflowd'
        self.outfile = open(outname, 'wb')

    def shutdown(self):
        self.outfile.close()

    def exportflow(self, ts, flet):
        flowrec = cflow.packrecord(srcaddr=int(IPAddress(flet.srcaddr)), dstaddr=int(IPAddress(flet.dstaddr)), pkts=flet.pkts, bytes=flet.size, start=int(flet.flowstart), end=int(flet.flowend), srcport=flet.srcport, dstport=flet.dstport, tcpflags=flet.tcpflags, ipproto=flet.ipproto, iptos=flet.iptos)
        self.outfile.write(flowrec)

