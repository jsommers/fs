#!/usr/bin/env python

__author__ = 'jsommers@colgate.edu'

from abc import ABCMeta, abstractmethod

class FlowExporter(object):
    __metaclass__ = ABCMeta

    def __init__(self, rname):
        self.routername = str(rname)

    @abstractmethod
    def exportflow(self, ts, flet):
        pass

    @abstractmethod
    def shutdown(self):
        pass


## obsolete test code: FIXME
# def main():
#     f1 = Flowlet(ipaddr.IPAddress('10.0.1.1'), ipaddr.IPAddress('192.168.5.2'), 17, 5, 42)
#     f1.flowstart = time.time()
#     f1.flowend = time.time() + 10
#     f1.srcport = 2345
#     f1.dstport = 6789

#     f2 = copy.copy(f1)
#     f2.flowend = time.time() + 20
#     f2.ipproto = 6
#     f2.tcpflags = 0xff
#     f2.srcport = 9999
#     f2.dstport = 80
#     f2.iptos = 0x08

#     textexp = text_export_factory('testrouter')
#     textexp.exportflow(time.time(),f1)
#     textexp.exportflow(time.time(),f2)
#     textexp.shutdown()

# if __name__ == '__main__':
#     main()
