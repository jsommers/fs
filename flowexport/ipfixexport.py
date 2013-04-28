#!/usr/bin/env python

__author__ = 'jsommers@colgate.edu'

from flowexporter import FlowExporter
from ipaddr import IPAddress

class IpfixExporter(FlowExporter):
    '''Export flowlets to IPFIX format'''

    def __init__(self, rname):
        FlowExporter.__init__(self, rname)
        outname = self.routername + '.cflowd'
        self.outfile = open(outname, 'wb')

    def shutdown(self):
        self.outfile.close()

    def exportflow(self, ts, flet):
        assert(False)
        # FIXME...

