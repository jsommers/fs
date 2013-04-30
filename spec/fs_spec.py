import unittest
from mock import Mock

from fs import *
from fslib.common import fscore

class SimTests(unittest.TestCase):
    def testNewSimulatorSingleton(self):
        sim = FsCore(1.0)
        self.assertIs(fscore(), sim)

    def testAfter(self):
        sim = FsCore(1.0, debug=True, progtick=1.0)
        def doafter():
            self.assertEqual(sim.now, 1.0)
        sim.after(1.0, "test after", doafter)
        self.assertEqual(sim.now, 0.0)
        sim.run(None)

if __name__ == '__main__':
    unittest.main()
