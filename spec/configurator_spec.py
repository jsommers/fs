import unittest
from mock import Mock
import tempfile
from spec_base import FsTestBase
import fslib.configurator as configurator
import fslib.common as fscommon
import os

# dry out configuration stuff
# better conf tests 
# work on lower-layer stuff arp/etc.

dot_conf1 = '''
graph test {
    // 2 nodes: a and b
    flowexportfn=text_export_factory
    counterexportfile="counters"
    flowsampling=1.0
    pktsampling=1.0
    exportcycle=60
    counterexport=True
    counterexportinterval=1
    longflowtmo=60
    flowinactivetmo=60
    measurementnodes="a"

    // slightly DRYer form of configuration
    harpoon="harpoon ipsrc=10.1.0.0/16 ipdst=10.3.1.0/24 flowsize=exponential(1/10000.0) flowstart=exponential(100) ipproto=randomchoice(6) sport=randomchoice(22,80,443) dport=randomunifint(1025,65535) lossrate=randomchoice(0.001)"

    // another way to DRY things out; only specify things that change
    harpoonsubspec="flowsize=exponential(1/10000.0) flowstart=exponential(100) ipproto=randomchoice(6) sport=randomchoice(22,80,443) dport=randomunifint(1025,65535) lossrate=randomchoice(0.001)"

    harpoonsubspec2="flowsize=empiricaldistribution('/tmp/filesizes.txt') flowstart=exponential(100) ipproto=randomchoice(6) sport=randomchoice(22,80,443) dport=randomunifint(1025,65535) lossrate=randomchoice(0.001)"

    a [ 
        autoack="False"
        ipdests="10.1.0.0/16"
        traffic="m1 m2 m3"
        m1="modulator start=0.0 generator=harpoon profile=((3600,),(1,))"
        m2="modulator start=0.0 generator=s1 profile=((3600,),(1,))"
        m3="modulator start=0.0 generator=s2 profile=((3600,),(1,))"
        m4="modulator start=0.0 generator=s3 profile=((3600,),(1,))"
        s1="harpoon ipsrc=10.1.0.0/16 ipdst=10.3.1.0/24 flowsize=exponential(1/10000.0) flowstart=exponential(100) ipproto=randomchoice(6) sport=randomchoice(22,80,443) dport=randomunifint(1025,65535) lossrate=randomchoice(0.001)"
        s2="harpoon ipsrc=10.2.0.0/16 ipdst=10.4.1.0/24 $harpoonsubspec"
        s3="harpoon ipsrc=10.2.0.0/16 ipdst=10.4.1.0/24 $harpoonsubspec2"
    ];

    b [ 
        autoack="False"
        ipdests="10.0.0.0/8 10.2.0.0/16 10.3.0.0/16" 
    ];

    // links 
    a -- b [weight=10, capacity=100000000, delay=0.042];
}
'''

json_conf1 = '''
{
    "directed": false, 
    "graph": [
        ["node", {}], 
        ["graph", {
            "flowsampling": 1.0, 
            "counterexportinterval": 1, 
            "harpoonsubspec2": "flowsize=empiricaldistribution('/tmp/filesizes.txt') flowstart=exponential(100) ipproto=randomchoice(6) sport=randomchoice(22,80,443) dport=randomunifint(1025,65535) lossrate=randomchoice(0.001)", 
            "measurementnodes": "a", 
            "harpoon": "harpoon ipsrc=10.1.0.0/16 ipdst=10.3.1.0/24 flowsize=exponential(1/10000.0) flowstart=exponential(100) ipproto=randomchoice(6) sport=randomchoice(22,80,443) dport=randomunifint(1025,65535) lossrate=randomchoice(0.001)", 
            "flowexportfn": "text_export_factory", 
            "harpoonsubspec": "flowsize=exponential(1/10000.0) flowstart=exponential(100) ipproto=randomchoice(6) $portspartial $lossconfig", 
            "portspartial": "sport=randomchoice(22,80,443) dport=randomunifint(1025,65535)",
            "lossconfig": "lossrate=randomchoice(0.001)",
            "linkcap": 1000000000,
            "linkdel": 0.042,
            "pktsampling": 1.0, 
            "longflowtmo": 60, 
            "exportcycle": 60, 
            "counterexport": true,
            "counterexportfile": "counters", 
            "flowinactivetmo": 60}
        ], 
        ["edge", {}], 
        ["name", "test"]
    ], 
    "nodes": [
        {"ipdests": "10.1.0.0/16", "traffic": "m1 m2 m3", "id": "a", 
         "s3": "harpoon ipsrc=10.2.0.0/16 ipdst=10.4.1.0/24 $harpoonsubspec2", 
         "s2": "harpoon ipsrc=10.2.0.0/16 ipdst=10.4.1.0/24 $harpoonsubspec", 
         "s1": "harpoon ipsrc=10.1.0.0/16 ipdst=10.3.1.0/24 flowsize=exponential(1/10000.0) flowstart=exponential(100) ipproto=randomchoice(6) $portspartial $lossconfig",
         "m4": "modulator start=0.0 generator=s3 profile=((3600,),(1,))", 
         "m1": "modulator start=0.0 generator=harpoon profile=((3600,),(1,))", 
         "m3": "modulator start=0.0 generator=s2 profile=((3600,),(1,))", 
         "m2": "modulator start=0.0 generator=s1 profile=((3600,),(1,))", "autoack": false},
        {"ipdests": "10.0.0.0/8 10.2.0.0/16 10.3.0.0/16", "id": "b", "autoack": false}
    ], 
    "links": [
        {"delay": "$linkdel", "source": 0, "capacity": "$linkcap", "target": 1, "weight": 10}
    ], 
    "multigraph": true
}

'''

json_conf2 = '''
{
    "directed": false, 
    "graph": [
        ["node", {}], 
        ["graph", {
            "flowsampling": 1.0, 
            "counterexportinterval": 1, 
            "measurementnodes": "a", 
            "harpooncfg": "ipsrc=10.1.0.0/16 ipdst=10.3.1.0/24 flowsize=exponential(1/10000.0) flowstart=exponential(100) ipproto=randomchoice(6) sport=randomchoice(22,80,443) dport=randomunifint(1025,65535) lossrate=randomchoice(0.001)", 
            "flowexportfn": "text_export_factory", 
            "linkdel": 0.042,
            "linkcap": 1000000000,
            "pktsampling": 1.0, 
            "longflowtmo": 60, 
            "exportcycle": 60, 
            "counterexport": true,
            "counterexportfile": "counters", 
            "flowinactivetmo": 60}
        ], 
        ["edge", {}], 
        ["name", "test"]
    ], 
    "nodes": [
        {"id": "a",
         "ipdests": "10.1.0.0/16", "traffic": "m1", 
         "s1": "harpoon $harpooncfg",
         "m1": "modulator start=0.0 generator=s1 profile=((3600,),(1,))", "autoack": false},
        {
         "id": "b", 
         "ipdests": "10.0.0.0/8 10.2.0.0/16 10.3.0.0/16", 
         "autoack": false}
    ], 
    "links": [
        {"delay": "$linkdel", "source": 0, "capacity": "$linkcap", "target": 1, "weight": 10},
        {"delay": "$linkdel", "source": 0, "capacity": "$linkcap", "target": 1, "weight": 10},
        {"delay": "$linkdel", "source": 0, "capacity": "$linkcap", "target": 1, "weight": 10}
    ], 
    "multigraph": true
}

'''

class ConfiguratorTests(FsTestBase):
    def setUp(self):
        fh = open("/tmp/filesizes.txt", "w")
        fh.write("100 200 300 400 500\n600 700 800 900 1000\n")
        fh.close()

    def tearDown(self):
        os.unlink(self.cfgfname)
        os.unlink("/tmp/filesizes.txt")

    def mkconfig(self, cfg):
        fd,fname = tempfile.mkstemp()
        self.cfgfname = fname
        print self.cfgfname
        fh = os.fdopen(fd, 'w')
        fh.write(cfg)
        fh.close()

    def testReadConfigDot(self):
        self.mkconfig(dot_conf1)
        cfg = configurator.FsConfigurator()
        topology = cfg.load_config(self.cfgfname, configtype="dot")
        self.assertItemsEqual(topology.nodes.keys(), ['a','b'])
        self.assertItemsEqual(topology.links.keys(), [('a','b'),('b','a')])

    def testReadConfigJson1(self):
        self.mkconfig(json_conf1)
        cfg = configurator.FsConfigurator()
        topology = cfg.load_config(self.cfgfname, configtype="json")
        self.assertItemsEqual(topology.nodes.keys(), ['a','b'])
        self.assertItemsEqual(topology.links.keys(), [('a','b'),('b','a')])

    def testReadConfigJson2(self):
        self.mkconfig(json_conf2)
        cfg = configurator.FsConfigurator()
        topology = cfg.load_config(self.cfgfname, configtype="json")
        self.assertItemsEqual(topology.nodes.keys(), ['a','b'])
        self.assertItemsEqual(topology.links.keys(), [('a','b'),('b','a')])

if __name__ == '__main__':
    unittest.main()
