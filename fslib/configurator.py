#!/usr/bin/python

__author__ = 'jsommers@colgate.edu'

import sys
from importlib import import_module
from abc import ABCMeta, abstractmethod
import json
import pydot
import ipaddr
from pytricia import PyTricia
from fslib.node import *
from fslib.link import Link
from fslib.common import get_logger
from fslib.traffic import FlowEventGenModulator
import fslib.util as fsutil
from fslib.util import *
from fslib.common import fscore

from networkx import single_source_dijkstra_path, single_source_dijkstra_path_length, read_gml, read_dot
from networkx.readwrite import json_graph


class InvalidTrafficSpecification(Exception):
    pass

class InvalidRoutingConfiguration(Exception):
    pass

class InvalidConfiguration(Exception):
    pass

class NullTopology(object):
    ___metaclass__ = ABCMeta
    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def stop(self):
        pass

class Topology(NullTopology):
    def __init__(self, graph, nodes, links, traffic_modulators):
        self.logger = get_logger('fslib.config')
        self.__graph = graph
        self.nodes = nodes
        self.links = links
        self.traffic_modulators = traffic_modulators
        self.routing = {}
        self.ipdestlpm = None
        self.owdhash = {}
        self.__configure_routing()

        for a,b,d in self.graph.edges(data=True):
            if 'reliability' in d:
                self.__configure_edge_reliability(a,b,d['reliability'],d)

    @property
    def graph(self):
        return self.__graph

    def remove_node(self, name):
        self.__graph.remove_node(name)
        for n in self.graph:
            self.routing[n] = single_source_dijkstra_path(self.graph, n)

    def __configure_edge_reliability(self, a, b, relistr, edict):
        relidict = fsutil.mkdict(relistr)
        ttf = ttr = None
        for k,v in relidict.iteritems():
            if k == 'failureafter':
                ttf = eval(v)
                if isinstance(ttf, (int, float)):
                    ttf = modulation_generator([ttf])

            elif k == 'downfor':
                ttr = eval(v)
                if isinstance(ttr, (int, float)):
                    ttr = modulation_generator([ttr])

            elif k == 'mttf':
                ttf = eval(v)

            elif k == 'mttr':
                ttr = eval(v)

        if ttf or ttr:
            assert(ttf and ttr)
            xttf = next(ttf)
            fscore().after(xttf, 'link-failure-'+a+'-'+b, self.__linkdown, a, b, edict, ttf, ttr)

    def __configure_routing(self):
        for n in self.graph:
            self.routing[n] = single_source_dijkstra_path(self.graph, n)

        self.ipdestlpm = PyTricia()
        for n,d in self.graph.nodes_iter(data=True):
            dlist = d.get('ipdests','').split()
            for destipstr in dlist:
                ipnet = ipaddr.IPNetwork(destipstr)
                xnode = {}
                self.ipdestlpm[str(ipnet)] = xnode
                if 'dests' in xnode:
                    xnode['dests'].append(n)
                else:
                    xnode['net'] = ipnet
                    xnode['dests'] = [ n ]

        # install static forwarding table entries to each node

        # FIXME: there's a problematic bit of code here that triggers
        # pytricia-related (iterator) core dump
        for nodename,nodeobj in self.nodes.iteritems():
            if isinstance(nodeobj, Router):
                for prefix in self.ipdestlpm.keys():
                    lpmnode = self.ipdestlpm.get(prefix)
                    if nodename not in lpmnode['dests']:
                        routes = self.routing[nodename]
                        for d in lpmnode['dests']:
                            try:
                                path = routes[d]
                            except KeyError:
                                self.logger.warn("No route from {} to {}".format(nodename, d)) 
                                continue
                                
                            nexthop = path[1]
                            nodeobj.addForwardingEntry(prefix, nexthop)
                
        self.owdhash = {}
        for a in self.graph:
            for b in self.graph:
                key = a + ':' + b
                
                rlist = [ a ]
                while rlist[-1] != b:
                    nh = self.nexthop(rlist[-1], b)
                    if not nh:
                        self.logger.debug('No route from %s to %s (in owd; ignoring)' % (a,b))
                        return None
                    rlist.append(nh)

                owd = 0.0
                for i in xrange(len(rlist)-1):
                    owd += self.delay(rlist[i],rlist[i+1])
                self.owdhash[key] = owd


    def node(self, nname):
        '''get the node object corresponding to a name '''
        return self.nodes[nname]

    def start(self):
        for tm in self.traffic_modulators:
            tm.start()

        for nname,n in self.nodes.iteritems():
            n.start()

    def stop(self):
        for nname,n in self.nodes.iteritems():
            n.stop()     
            
    def __linkdown(self, a, b, edict, ttf, ttr):
        '''kill a link & recompute routing '''
        self.logger.info('Link failed %s - %s' % (a,b))
        self.graph.remove_edge(a,b)
        self.__configure_routing()

        uptime = None
        try:
            uptime = next(ttr)
        except:
            self.logger.info('Link %s-%s permanently taken down (no recovery time remains in generator)' % (a, b))
            return
        else:
            fscore().after(uptime, 'link-recovery-'+a+'-'+b, self.__linkup, a, b, edict, ttf, ttr)

        
    def __linkup(self, a, b, edict, ttf, ttr):
        '''revive a link & recompute routing '''
        self.logger.info('Link recovered %s - %s' % (a,b))
        self.graph.add_edge(a,b,weight=edict.get('weight',1),delay=edict.get('delay',0),capacity=edict.get('capacity',1000000))
        self.__configure_routing()

        downtime = None
        try:
            downtime = next(ttf)
        except:
            self.logger.info('Link %s-%s permanently going into service (no failure time remains in generator)' % (a, b))
            return
        else:
            fscore().after(downtime, 'link-failure-'+a+'-'+b, self.__linkdown, a, b, edict, ttf, ttr)


    def owd(self, a, b):
        '''get the raw one-way delay between a and b '''
        key = a + ':' + b
        rv = None
        if key in self.owdhash:
            rv = self.owdhash[key]
        return rv


    def delay(self, a, b):
        '''get the link delay between a and b '''
        d = self.graph.edge[a][b]
        if d is not None:
            return d.values()[0]['delay']
        return None

        
    def capacity(self, a, b):
        '''get the bandwidth between a and b '''
        d = self.graph.edge[a][b]
        if d is not None:
            return d.values()[0]['capacity']
        return None
        
    def nexthop(self, node, dest):
        '''
        return the next hop node for a given destination.
        node: current node
        dest: dest node name
        returns: next hop node name
        '''
        try:
            nlist = self.routing[node][dest]
        except:
            return None
        if len(nlist) == 1:
            return nlist[0]
        return nlist[1]

    def destnode(self, node, dest):
        '''
        return the destination node corresponding to a dest ip.
        node: current node
        dest: ipdest
        returns: destination node name
        '''
        # radix trie lpm lookup for destination IP prefix
        xnode = self.ipdestlpm.get(dest, None)

        if xnode:
            dlist = xnode['dests']
            best = None
            if len(dlist) > 1: 
                # in the case that there are multiple egress nodes
                # for the same IP destination, choose the closest egress
                best = None
                bestw = 10e6
                for d in dlist:
                    w = single_source_dijkstra_path_length(self.graph, node, d)
                    if w < bestw:
                        bestw = w
                        best = d
            else:
                best = dlist[0]

            return best
        else:
            raise InvalidRoutingConfiguration('No route for ' + dest)


class FsConfigurator(object):
    link_subnetter = None

    def __init__(self):
        self.logger = get_logger('fslib.config')
        # FIXME: let this be configurable
        FsConfigurator.link_subnetter = fsutil.subnet_generator("172.16.0.0/12", 2) 

    def __strip_strings(self):
        '''Clean up all the strings in the imported config.'''
        for k in self.graph.graph['graph']:
            if isinstance(self.graph.graph['graph'][k], (str,unicode)):
                v = self.graph.graph['graph'][k].replace('"','').strip()
                self.graph.graph['graph'][k] = v

        for n,d in self.graph.nodes(data=True):
            for k in d:
                if isinstance(d[k], (str,unicode)):
                    v = d[k].replace('"','').strip()
                    d[k] = v

        for a,b,d in self.graph.edges(data=True):
            for k in d:
                if isinstance(d[k], (str,unicode)):
                    v = d[k].replace('"','').strip()
                    d[k] = v

    def __substitute(self, val):
        '''Recursively substitute $identifiers in a config string'''
        if not isinstance(val, (str,unicode)):
            return val

        # if $identifier (minus $) is a key in graph, replace
        # it with value of that key.  then fall-through and
        # recursively substitute any $identifiers
        if val in self.graph.graph['graph']:
            self.logger.debug("Found substitution for {}: {}".format(val, self.graph.graph['graph'][val]))
            val = self.graph.graph['graph'][val]

            # if the resolved value isn't a string, no possible way to do further substitutions, BUT
            # still need to return as a string to make any higher-up joins work correctly.  ugh.
            if not isinstance(val, (str,unicode)):
                return str(val)

        items = val.split()
        for i in range(len(items)):
            if items[i][0] == '$':
                # need to do a substitution
                self.logger.debug("Found substitution symbol {} -- recursing".format(items[i]))
                items[i] = self.__substitute(items[i][1:])
        return ' '.join(items)

    def __do_substitutions(self):
        '''For every string value in graph, nodes, and links, find any $identifier
           and do a (recursive) substitution of strings, essentially in place (use split/join 
           to effectively do that.'''
        for k in self.graph.graph['graph']:
            v = self.graph.graph['graph'][k]
            self.graph.graph['graph'][k] = self.__substitute(v)

        for n,d in self.graph.nodes(data=True):
            for k,v in d.iteritems():
                d[k] = self.__substitute(v)

        for a,b,d in self.graph.edges(data=True):
            for k,v in d.iteritems():
                d[k] = self.__substitute(v)

    def load_config(self, config, configtype="json"):
        try:
            if configtype == "dot":
                self.graph = read_dot(config)
            elif configtype == "json":
                self.graph = json_graph.node_link_graph(json.load(open(config)))
            elif configtype == "gml":
                self.graph = read_gml(config)
        except Exception,e:
            print "Config read error: {}".format(str(e))
            self.logger.error("Error reading configuration: {}".format(str(e)))
            sys.exit(-1)
         
        mconfig_dict = {'counterexport':False, 'flowexport':'null','counterexportinterval':0, 'counterexportfile':None, 'maintenance_cycle':60, 'pktsampling':1.0, 'flowsampling':1.0, 'longflowtmo':-1, 'flowinactivetmo':-1}

        self.logger.info("Reading config for graph {}.".format(self.graph.graph.get('name','(unnamed)')))

        self.__strip_strings()
        self.__do_substitutions()

        measurement_nodes = self.graph.nodes()
        for key in self.graph.graph['graph']:
            val = self.graph.graph['graph'][key]
            mconfig_dict[key] = val
            if key in ['measurenodes','measurementnodes','measurements']:
                if val != 'all':
                    measurement_nodes = [ n.strip() for n in val.split() ]

        try:
            # test importing the flow export module before we get too far...
            import_module("flowexport.{}export".format(mconfig_dict['flowexport']))
        except ImportError,e:
            s = "No such flow exporter {0} (module flowexport.{0}export doesn't exist.".format(mconfig_dict['flowexport'])
            raise InvalidConfiguration(s)

        measurement_config = MeasurementConfig(**mconfig_dict)
        self.logger.info("Running measurements on these nodes: <{}>".format(','.join(measurement_nodes)))

        for a,b,d in self.graph.edges(data=True):
            w = 1
            if 'weight' in d:
                w = d['weight']
            d['weight'] = int(w)

        self.nodes = {}
        self.links = defaultdict(list)
        self.traffic_modulators = []

        self.__configure_parallel_universe(measurement_config, measurement_nodes)
        self.__configure_traffic()
        self.__print_config()
        return Topology(self.graph, self.nodes, self.links, self.traffic_modulators)

    def __print_config(self):
        self.logger.debug("*** Begin Configuration Dump ***".center(30))
        self.logger.debug("*** graph nodes ***")
        for n,d in self.graph.nodes(data=True):
            self.logger.debug("{},{}".format(n,d))
        self.logger.debug("*** graph links ***")
        for a,b,d in self.graph.edges(data=True):
            self.logger.debug("{}->{} -- {}".format(a,b,d))
        self.logger.debug("*** fs objects ***")
        for nname,nobj in self.nodes.iteritems():
            self.logger.debug("{} -> {}".format(nname, nobj))
        for xtup,lobj in self.links.iteritems():
            self.logger.debug("link {}->{}: {}".format(xtup[0], xtup[1], lobj))
        self.logger.debug("*** End Configuration Dump ***".center(30))

    def __addupd_router(self, rname, rdict, measurement_config):
        robj = None
        if rname not in self.nodes:
            ctype = rdict.get('type', 'Router')
            self.logger.debug('Adding node {} type {} config {}'.format(rname,ctype,rdict))

            # ctype is the ClassName of the node to construct.
            # the class may be in fslib.node or fslib.openflow

            m = import_module("fslib.node")
            cls = getattr(m, ctype, None)
            if not cls:
                m = import_module("fslib.openflow")
                cls = getattr(m, ctype, None)
                if not cls:
                    raise InvalidTrafficSpecification('Unrecognized node type {}.'.format(ctype))
            robj = cls(rname, measurement_config, **rdict)
            self.nodes[rname] = robj
        else:
            robj = self.nodes[rname]
        return robj


    def __configure_parallel_universe(self, measurement_config, measurement_nodes):
        '''
        using the the networkx graph stored in the simulator,
        build corresponding Routers and Links in the sim world.
        '''
        for rname,rdict in self.graph.nodes_iter(data=True):
            self.logger.debug("Adding node {} with data {}".format(rname, rdict))
            mc = measurement_config                
            if rname not in measurement_nodes:
                mc = None
            self.__addupd_router(rname, rdict, mc)

        for a,b,d in self.graph.edges_iter(data=True):
            self.logger.debug("Adding bidirectional link from {}-{} with data {}".format(a, b, d))

            mc = measurement_config                
            if a not in measurement_nodes:
                mc = None
            ra = self.__addupd_router(a, d, mc)

            mc = measurement_config                
            if b not in measurement_nodes:
                mc = None
            rb = self.__addupd_router(b, d, mc)
            
            # parse link delay/capacity values and substitute back into
            # networkx graph to ensure that no additional parsing is needed
            delay = d.get('delay',0)
            delay = Link.parse_delay(delay)
            cap = d.get('capacity',0)
            cap = Link.parse_capacity(cap)
            d['capacity'] = cap
            d['delay'] = delay

            ipa,ipb = [ ip for ip in next(FsConfigurator.link_subnetter).iterhosts() ]

            linkfwd = Link(cap, delay, ra, rb)
            linkrev = Link(cap, delay, rb, ra)
            self.logger.debug("Adding single dir link: {}, {}, {}, {}".format(str(linkfwd), ipa, ipb, b))
            ra.add_link(linkfwd, ipa, ipb, rb.name)
            self.logger.debug("Adding single dir link: {}, {}, {}, {}".format(str(linkrev), ipb, ipa, ra.name))
            rb.add_link(linkrev, ipb, ipa, ra.name)
            self.links[(a,b)].append( (linkfwd,ipa,ipb) )
            self.links[(b,a)].append( (linkrev,ipb,ipa) )
            linkfwd.set_ingress_ip(ipa)
            linkfwd.set_egress_ip(ipb)
            linkrev.set_ingress_ip(ipb)
            linkrev.set_egress_ip(ipa)

        for rname,rdict in self.graph.nodes_iter(data=True):
            if 'defaultroute' in rdict:
                default = rdict['defaultroute']
                nextnode = None
                self.logger.debug("trying to add default route for {} - {}".format(rname, default))
                if isinstance(default, bool):
                    adjacencies = self.graph[rname]
                    print "Adjacencies:",adjacencies
                    nextnode = adjacencies.keys()[0]
                elif isinstance(default, (str,unicode)):
                    nextnode = default
                self.nodes[rname].setDefaultNextHop(nextnode)


    def __configure_traffic(self):
        for n,d in self.graph.nodes_iter(data=True):
            if 'traffic' not in d:
                continue
                
            modulators = d['traffic'].split()
            self.logger.debug("Traffic modulators configured: {}".format(str(modulators)))

            for mkey in modulators:
                modspecstr = d[mkey]

                self.logger.debug('Configing modulator: {}'.format(str(modspecstr)))
                m = self.__configure_traf_modulator(modspecstr, n, d)
                self.traffic_modulators.append(m)


    def __configure_traf_modulator(self, modstr, srcnode, xdict):
        modspeclist = modstr.split()
        moddict = {}
        for i in xrange(1,len(modspeclist)):
            k,v = modspeclist[i].split('=')
            moddict[k] = v

        self.logger.debug("inside config_traf_mod: {}".format(moddict))
        if not ('profile' in moddict or 'sustain' in moddict):
            self.logger.warn("Need a 'profile' or 'sustain' in traffic specification for {}".format(moddict))
            raise InvalidTrafficSpecification(moddict)

        trafprofname = moddict.get('generator', None)
        st = moddict.get('start', None)
        st = eval(st)
        if isinstance(st, (int, float)):
            st = fsutil.randomchoice(st)

        profile = moddict.get('profile', None)
        if not profile:
            profile = moddict.get('sustain', None)

        emerge = moddict.get('emerge', None)
        withdraw = moddict.get('withdraw', None)

        trafprocstr = ""
        if trafprofname in xdict:
            trafprofstr = xdict[trafprofname]
        elif trafprofname in self.graph.graph['graph']:
            trafprofstr = self.graph.graph['graph'][trafprofname]
        else:
            self.logger.warn("Need a traffic generator name ('generator') in {}".format(moddict))
            raise InvalidTrafficSpecification(xdict)

        self.logger.debug("Found traffic specification for {}: {}".format(trafprofname,trafprofstr))
        tgen = self.__configure_traf_spec(trafprofname, trafprofstr, srcnode)
        fm = FlowEventGenModulator(tgen, stime=st, emerge_profile=emerge, sustain_profile=profile, withdraw_profile=withdraw)
        return fm

     
    def __configure_traf_spec(self, trafname, trafspec, srcnode):
        '''Configure a traffic generator based on specification elements'''
        trafspeclist = trafspec.split()

        # first item in the trafspec list should be the traffic generator name.
        # also need to traverse the remainder of the and do substitutions for common configuration elements
        specname = trafspeclist[0].strip()
        tclass = specname.capitalize()
        fulltrafspec = trafspeclist[1:]
        trafgenname = "{}TrafficGenerator".format(tclass)

        try:
            importname = "traffic_generators.{}".format(specname)
            m = import_module(importname)
        except ImportError,e:
            raise InvalidTrafficSpecification(trafspec)

        classobj = getattr(m, trafgenname)
        if not classobj:
            self.logger.warn("Bad config: can't find TrafficGenerator class named {0}.  Add the class '{0}' to traffic.py, or fix the config.".format(trafgenname))
            raise InvalidTrafficSpecification(trafspec)
        else:
            trafdict = fsutil.mkdict(fulltrafspec)
            self.logger.debug("Creating {} with specification {}".format(str(classobj),trafdict))
            gen = lambda: classobj(srcnode, **trafdict)
            return gen
