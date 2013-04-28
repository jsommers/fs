#!/usr/bin/env python

__author__ = 'jsommers@colgate.edu'

from flowexporter import FlowExporter

class NullExporter(FlowExporter):
    '''Does nothing except implement minimal required methods'''
    def exportflow(self, ts, flet):
        pass

    def shutdown(self):
        pass
