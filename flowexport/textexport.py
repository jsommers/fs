#!/usr/bin/env python

__author__ = 'jsommers@colgate.edu'

from flowexporter import FlowExporter

class TextExporter(FlowExporter):
    '''Export flowlets to a simple text format'''
    def __init__(self, rname, bufsize=500):
        FlowExporter.__init__(self, rname)
        outname = self.routername + '_flow.txt'
        self.outfile = open(outname, 'wb')
        self.buffer = []
        self.bufsize = bufsize

    def _flush_buffer(self):
        self.outfile.write(''.join(self.buffer))
        self.buffer = []

    def shutdown(self):
        self._flush_buffer()
        self.outfile.close()

    def exportflow(self, ts, flet):
        record = 'textexport %s %0.06f %s\n' % (self.routername, ts, str(flet))
        self.buffer.append(record)
        if len(self.buffer) >= self.bufsize:
            self._flush_buffer()
        
