#!/usr/bin/python

__author__ = 'jsommers@colgate.edu'

import pydot
from node import *
from link import *
from traffic import *
from pytricia import PyTricia
import ipaddr
import fscommon

import networkx
try:
    from networkx.algorithms.traversal.path import single_source_dijkstra_path, dijkstra_path_length
except:
    from networkx.algorithms.shortest_paths.weighted import single_source_dijkstra_path, dijkstra_path_length
else:
    print >>sys.stderr,"Can't find the necessary dijkstra's functions in your networkx installation.  You should probably upgrade to a more recent version."
    sys.exit(-1)


class InvalidTrafficSpecification(Exception):
    pass

class InvalidRoutingConfiguration(Exception):
    pass

class NullTopology(object):
    def start(self):
        pass

    def stop(self):
        pass

class Topology(NullTopology):
    def __init__(self, graph, routing, nodes, ipdestlpm, owdhash, traffic_modulators):
        self.logger = fscommon.get_logger()
        self.graph = graph
        self.routing = routing
        self.nodes = nodes
        self.ipdestlpm = ipdestlpm
        self.owdhash = owdhash
        self.traffic_modulators = traffic_modulators

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
            self.after(uptime, 'link-recovery-'+a+'-'+b, self.__linkup, a, b, edict, ttf, ttr)

        
    def __linkup(self, a, b, edict, ttf, ttr):
        '''revive a link & recompute routing '''
        self.logger.info('Link recovered %s - %s' % (a,b))
        self.graph.add_edge(a,b,weight=edict.get('weight',1),delay=edict.get('delay',0),capacity=edict.get('capacity',1000000))
        FsConfigurator.configure_routing(self.routing, self.graph)

        downtime = None
        try:
            downtime = next(ttf)
        except:
            self.logger.info('Link %s-%s permanently going into service (no failure time remains in generator)' % (a, b))
            return
        else:
            self.after(downtime, 'link-failure-'+a+'-'+b, self.__linkdown, a, b, edict, ttf, ttr)


    def owd(self, a, b):
        '''get the raw one-way delay between a and b '''
        key = a + ':' + b
        rv = None
        if key in self.owdhash:
            rv = self.owdhash[key]
        return rv


    def delay(self, a, b):
        '''get the link delay between a and b '''
        d = self.graph[a][b]
        if d and 0 in d:
            return float(d[0]['delay'])
        return None

        
    def capacity(self, a, b):
        '''get the bandwidth between a and b '''
        d = self.graph[a][b]
        if d and 0 in d:
            return int(d[0]['capacity'])
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
                    w = dijkstra_path_length(self.graph, node, d)
                    if w < bestw:
                        bestw = w
                        best = d
            else:
                best = dlist[0]

            return best
        else:
            raise InvalidRoutingConfiguration('No route for ' + dest)


class FsConfigurator(object):
    def __init__(self, debug):
        self.debug = debug
        self.logger = fscommon.get_logger(debug)

    def load_config(self, config):
        self.graph = networkx.nx_pydot.read_dot(config)
        mconfig_dict = {'counterexport':False, 'flowexportfn':'null_export_factory','counterexportinterval':0, 'counterexportfile':None, 'maintenance_cycle':60, 'pktsampling':1.0, 'flowsampling':1.0, 'longflowtmo':-1, 'flowinactivetmo':-1}

        print "Reading config for graph {}.".format(self.graph.graph.get('name','(unnamed)'))

        measurement_nodes = self.graph.nodes()
        for key in self.graph.graph['graph']:
            val = self.graph.graph['graph'][key].replace('"','')
            mconfig_dict[key] = val
            if key in ['measurenodes','measurementnodes','measurements']:
                if val != 'all':
                    measurement_nodes = [ n.strip() for n in val.split() ]

        measurement_config = MeasurementConfig(**mconfig_dict)
        print "Only running measurements on these nodes: <{}>".format(','.join(measurement_nodes))

        for a,b,d in self.graph.edges(data=True):
            w = 1
            if 'weight' in d:
                w = d['weight']
            d['weight'] = int(w)

            if 'reliability' in d:
                self.__configure_edge_reliability(a,b,d['reliability'],d)

        if self.debug:
            for a,b,d in self.graph.edges_iter(data=True):
                print a,b,d

        self.routing = {}
        self.nodes = {}
        self.ipdestlpm = PyTricia()
        self.owdhash = {}
        self.traffic_modulators = []

        self.__configure_routing()
        self.__configure_parallel_universe(measurement_config, measurement_nodes)
        self.__configure_traffic()
        return Topology(self.graph, self.routing, self.nodes, self.ipdestlpm, self.owdhash, self.traffic_modulators)

    def __configure_edge_reliability(self, a, b, relistr, edict):
        relidict = mkdict(relistr.replace('"', '').strip())
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
            self.after(xttf, 'link-failure-'+a+'-'+b, self.__linkdown, a, b, edict, ttf, ttr)
            
    def __configure_routing(self):
        for n in self.graph:
            self.routing[n] = single_source_dijkstra_path(self.graph, n)
        if self.debug:
            for n,d in self.graph.nodes_iter(data=True):
                print n,d

        self.ipdestlpm = PyTricia()
        for n,d in self.graph.nodes_iter(data=True):
            dlist = d.get('ipdests','').split()
            if self.debug:
                print dlist,n
            for destipstr in dlist:
                destipstr = destipstr.replace('"','')
                ipnet = ipaddr.IPNetwork(destipstr)
                xnode = {}
                self.ipdestlpm[str(ipnet)] = xnode
                if 'dests' in xnode:
                    xnode['dests'].append(n)
                else:
                    xnode['net'] = ipnet
                    xnode['dests'] = [ n ]

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

    def delay(self, a, b):
        '''get the link delay between a and b '''
        d = self.graph[a][b]
        if d and 0 in d:
            return float(d[0]['delay'])
        return None

        
    def capacity(self, a, b):
        '''get the bandwidth between a and b '''
        d = self.graph[a][b]
        if d and 0 in d:
            return int(d[0]['capacity'])
        return None


    def nexthop(self, node, dest):
        '''
        FIXME *** -- this is also in fs.py
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

    def __addupd_router(self, rname, rdict, measurement_config):
        robj = None
        forwarding = None
        typehash = {'iprouter':Router, 'ofswitch':OpenflowSwitch, 'ofcontroller':OpenflowController}
        if rname not in self.nodes:
            aa = 'False'
            if 'autoack' in rdict:
                aa = rdict['autoack']
            aa = eval(aa.replace('"', ''))
            classtype = rdict.get('type','iprouter').replace('"','')
            # Checking if controller then find out the forwarding technique to be used
            forwarding=None
            if classtype == 'ofcontroller':
                forwarding = rdict.get('forwarding').replace('"','')

            if self.debug:
                self.logger.debug('Adding router {}, {}, autoack={}'.format(rname,rdict,aa))

            if classtype not in typehash:
                raise InvalidTrafficSpecification('Unrecognized node type {}.'.format(classtype))
            robj = typehash[classtype](rname, measurement_config, autoack=aa, forwarding=forwarding)
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
            mc = measurement_config                
            if rname not in measurement_nodes:
                mc = None
            self.__addupd_router(rname, rdict, mc)

        for a,b,d in self.graph.edges_iter(data=True):
            mc = measurement_config                
            if a not in measurement_nodes:
                mc = None
            ra = self.__addupd_router(a, d, mc)

            mc = measurement_config                
            if b not in measurement_nodes:
                mc = None
            rb = self.__addupd_router(b, d, mc)
            
            cap = self.capacity(a,b)
            delay = self.delay(a,b)
            ra.add_link(Link(cap/8, delay, ra, rb), b)
            rb.add_link(Link(cap/8, delay, rb, ra), a)


    def __configure_traffic(self):
        for n,d in self.graph.nodes_iter(data=True):
            if 'traffic' not in d:
                continue
                
            modulators = d['traffic'].split()
            self.logger.debug("Traffic modulators configured: {}".format(str(modulators)))

            for mkey in modulators:
                mkey = mkey.replace('"','')
                modspecstr = d[mkey].replace('"', '')

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
        if not 'profile' in moddict or 'sustain' in moddict:
            self.logger.warn("Need a 'profile' or 'sustain' in traffic specification for {}".format(moddict))
            sys.exit(-1)

        trafprofname = moddict.get('generator', None)
        st = moddict.get('start', None)
        st = eval(st)
        if isinstance(st, (int, float)):
            st = randomchoice(st)

        profile = moddict.get('profile', None)
        if not profile:
            profile = moddict.get('sustain', None)

        emerge = moddict.get('emerge', None)
        withdraw = moddict.get('withdraw', None)

        if not trafprofname in xdict:
            self.logger.warn("Need a traffic generator name ('generator') in {}".format(xdict))
            sys.exit(-1)

        trafprofstr = xdict[trafprofname]
        trafprofstr = trafprofstr.replace('"','')
        tgen = self.__configure_traf_spec(trafprofstr, srcnode, xdict)
        fm = FlowEventGenModulator(tgen, stime=st, emerge_profile=emerge, sustain_profile=profile, withdraw_profile=withdraw)
        return fm

     
    def __configure_traf_spec(self, trafspec, srcnode, xdict):
        trafspeclist = trafspec.split()
                
        gen = None
        if trafspeclist[0] == 'rawflow' or trafspeclist[0] == 'simple':
            # configure really simple 'rawflow' traffic generator
            trafdict = mkdict(trafspeclist[1:])
            self.logger.debug("Making simple traffic generator source at {}: {}".format(srcnode, trafdict))
            gen = lambda: SimpleGeneratorNode(srcnode, **trafdict)

        elif trafspeclist[0] == 'harpoon':
            # configure harpoon-style generator
            # configure really simple traffic generator
            trafdict = mkdict(trafspeclist[1:])
            self.logger.debug("Making harpoon traffic generator source at {}: {}".format(srcnode, trafdict))
            gen = lambda: HarpoonGeneratorNode(srcnode, **trafdict)

        elif trafspeclist[0] == 'subtractive':
            # configure subtractive anomaly
            trafdict = mkdict(trafspeclist[1:])
            self.logger.debug("Making subtractive traffic generator source at {}: {}".format(srcnode, trafdict))
            gen = lambda: SubtractiveGeneratorNode(srcnode, **trafdict)

        else:
            raise InvalidTrafficSpecification(trafspecstr)
        return gen
