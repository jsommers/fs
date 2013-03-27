import unittest
from mock import Mock
import tempfile
import configurator
import os

testconf = '''
graph test {
    // 2 nodes: a and b
    flowexportfn=text_export_factory

    a [ 
        autoack="False"
        ipdests="10.1.0.0/16"
        traffic="m1"
        m1="modulator start=0.0 generator=s1 profile=((3600,),(1,))"
        s1="harpoon ipsrc=10.1.0.0/16 ipdst=10.3.1.0/24 flowsize=exponential(1/10000.0) flowstart=exponential(100) ipproto=randomchoice(6) sport=randomchoice(22,80,443) dport=randomunifint(1025,65535) lossrate=randomchoice(0.001)"
    ];

    b [ 
        autoack="False"
        ipdests="10.0.0.0/8 10.2.0.0/16 10.3.0.0/16" 
    ];

    // links 
    a -- b [weight=10, capacity=100000000, delay=0.042];
}
'''

class ConfiguratorTests(unittest.TestCase):
    def setUp(self):
        fd,fname = tempfile.mkstemp()
        self.cfgfname = fname
        print self.cfgfname
        fh = os.fdopen(fd, 'w')
        fh.write(testconf)
        fh.close()
        
    def tearDown(self):
        os.unlink(self.cfgfname)

    def testReadConfig(self):
        cfg = configurator.FsConfigurator(debug=True)
        topology = cfg.load_config(self.cfgfname)

if __name__ == '__main__':
    unittest.main()
