import unittest
from mock import MagicMock, Mock

from spec_base import FsTestBase

from fslib.flowlet import FlowIdent, Flowlet, SubtractiveFlowlet
import ipaddr
import time
import copy


class TestFlowlet(FsTestBase):
    def setUp(self):
        self.ident1 = FlowIdent(srcip="1.1.1.1",dstip="2.2.2.2",ipproto=6, dport=80, sport=10000)
        self.ident2 = FlowIdent(str(ipaddr.IPAddress('10.0.1.1')), str(ipaddr.IPAddress('192.168.5.2')), 17, 5, 42)

    def testFlowIdent(self):
        ftfwd2 = self.ident2.mkreverse().mkreverse()
        self.assertEqual(self.ident2.key, ftfwd2.key)

    def testBuildFlowlet(self):
        f1 = Flowlet(self.ident1)
        f1.flowstart = time.time()
        f1.flowend = time.time() + 10
        self.assertEqual(repr(f1.key), repr(self.ident1))

    def testCopy(self):
        # NB: shallow copy of f1; flow key will be identical
        f1 = Flowlet(self.ident2)
        f2 = copy.copy(f1)
        # test whether FlowIdent keys referred to by each flowlet
        # are the same object
        self.assertIs(f1.key, f2.key)

    def testAdd(self):
        f1 = Flowlet(self.ident1)
        f1.pkts = 1 
        f1.bytes = 1 
        f2 = copy.copy(f1)
        f2.pkts = 1
        f2.bytes = 1
        f1 += f2
        self.assertEqual(f1.pkts, 2)
        self.assertEqual(f1.bytes, 2)
        self.assertEqual(f2.pkts, 1)
        self.assertEqual(f2.bytes, 1)

    def testSubtractive(self):
        f1 = SubtractiveFlowlet(self.ident1, "removeuniform(0.001)")
        # need to do some mocking to test action


if __name__ == '__main__':
    unittest.main()
