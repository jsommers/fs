import unittest
from mock import Mock

from spec_base import FsTestBase
from fs import *
from fslib.common import fscore

class SimTests(FsTestBase):
    @classmethod
    def setUpClass(cls):
        SimTests.sim = FsCore(1.0, debug=True, progtick=1.0)

    def testNewSimulatorSingleton(self):
        self.assertIs(fscore(), SimTests.sim)

    def testAfter(self):
        def doafter():
            self.assertEqual(SimTests.sim.now, 1.0)
        SimTests.sim.after(1.0, "test after", doafter)
        self.assertEqual(SimTests.sim.now, 0.0)
        SimTests.sim.run(None)

    @classmethod
    def tearDownClass(cls):
        SimTests.sim.unmonkeypatch()

if __name__ == '__main__':
    unittest.main()
