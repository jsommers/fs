#!/usr/bin/env python

__author__ = 'jsommers@colgate.edu'

from flowexporter import FlowExporter

class TextExporter(FlowExporter):
    '''Export flowlets to a simple text format'''
    def __init__(self, rname):
        FlowExporter.__init__(self, rname)
        outname = self.routername + '_flow.txt'
        self.outfile = open(outname, 'wb')

    def shutdown(self):
        self.outfile.close()

    def exportflow(self, ts, flet):
        print >>self.outfile,'textexport %s %0.06f %s' % (self.routername, ts, str(flet))

