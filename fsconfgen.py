#!/usr/bin/env python

__author__ = 'jsommers@colgate.edu'

import sys
from optparse import OptionParser
import string
import json

def add_flow_measurement(cfgdict, nodelist, flowtype="text_export"):
    '''Add flow measurement to config for nodes identified in nodelist'''
    strlist = " ".join(nodelist)
    cfgdict["graph"]["graph"]["measurementnodes"] = strlist
    cfgdict["graph"]["graph"]["flowexportfn"] = flowtype + "_factory"


def base_config(name, ):
    '''Make a base config dictionary for eventual export to JSON'''
    cfgdict = {
        "directed": False,
        "graph": [
            ["node", {}], 
            ["graph", {
                "flowexportfn": "null_export_factory",
                "measurementnodes": "",
                "flowsampling": 1.0,
                "counterexportinterval": 1,
                "pktsampling": 1.0,
                "longflowtmo": 60,
                "exportcycle": 60,
                "counterexport": True,
                "counterexportfile": "counters",
                "flowinactivetmo": 60
                }], 
            ["edge", {}], 
            ["name", name], 
        ],
        "nodes": [
        ],
        "links": [
        ],
        "multigraph": True
    }
    return cfgdict

def get_graphdict(cfg):
    '''Retrieve 'graph' dictionary from configuration'''
    for name,xdict in cfg['graph']:
        if name == 'graph':
            return xdict
    return None

def make_node(cfgdict, dst=-1, addtraffic=False):
    nodename,nodeindex = gen_nodename(cfgdict)
    srcprefix = "10.{}.{}.0/24".format(nodeindex/256, nodeindex%256)
    dstindex = nodeindex+1
    if dst >= 0:
        dstindex = dst 
    dstprefix = "10.{}.{}.0/24".format(dstindex/256, dstindex%256)

    nodedict = {
        "ipdests": srcprefix,
        "id": nodename, "autoack": False
    }

    if addtraffic:
        harpoon = "flowsize=pareto(10000.0,1.2) flowstart=exponential(100) ipproto=randomchoice(6) sport=randomchoice(22,80,443) dport=randomunifint(1025,65535) lossrate=randomchoice(0.001)"
        gdict = get_graphdict(cfgdict)
        gdict['commonharpoon'] = harpoon

        trafficcfg = "harpoon ipsrc={} ipdst={} $commonharpoon".format(srcprefix, dstprefix)
        nodedict["traffic"] = "modulate"
        nodedict["modulate"] = "modulator start=0.0 generator=tcfg profile=((3600,),(1,))"
        nodedict["tcfg"] = trafficcfg

    cfgdict['nodes'].append(nodedict)
    return nodename,nodeindex

def make_link(cfgdict, nodea, nodeb):
    '''Make a new link from nodea to nodeb and add it to configuration'''
    stdlink = {
        "delay": "43ms", 
        "capacity": "1Gb", 
        "weight": 10
    }
    sourceidx = get_nodeindex(cfgdict, nodea)
    targetidx = get_nodeindex(cfgdict, nodeb)

    stdlink["source"] = sourceidx
    stdlink["target"] = targetidx

    cfgdict["links"].append(stdlink)
    return len(cfgdict["links"])

class MissingNodeException(Exception):
    pass

def get_nodeindex(cfgdict, nodeid):
    '''Given a node id (name), return its index in the nodelist'''
    for idx, ndict in enumerate(cfgdict["nodes"]):
        if ndict['id'] == nodeid:
            return idx
    raise MissingNodeException("Couldn't get index for missing node name {}".format(nodeid))


def gen_nodename(cfgdict):
    '''Generate a new node name given existing node configurations in the cfg dictionary'''
    i = len(cfgdict['nodes']) 
    replication = i / len(string.ascii_lowercase) + 1
    return string.ascii_lowercase[i%len(string.ascii_lowercase)] * replication, i

def write_config(cfg, outname):
    '''Write config to json-format file'''
    with open(outname, "w") as outfile:
        json.dump(cfg, outfile)


def main():
    parser = OptionParser()
    parser.prog = "fsconfgen.py"
    parser.add_option("-n", "--name", 
                      dest="name",
                      default="myfs", 
                      help="Set the name of the generated configuration.") 
    (options, args) = parser.parse_args()
    cfg = base_config(options.name)
    namea, idxa = make_node(cfg, addtraffic=True)
    nameb, idxb = make_node(cfg, addtraffic=False)
    make_link(cfg, namea, nameb)
    write_config(cfg, "test.json")


if __name__ == '__main__':
    main()
