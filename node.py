#!/usr/bin/python

__author__ = 'jsommers@colgate.edu'

import logging
from random import random
import copy
from flowlet import *
from collections import Counter, defaultdict
from flowexport import null_export_factory, text_export_factory, cflowd_export_factory
import pdb
import copy
import networkx

from pox.openflow.flow_table import SwitchFlowTable, TableEntry
from pox.openflow.libopenflow_01 import * # total pollution of namespace - yuck.

class MeasurementConfig(object):
    __slots__ = ['__counterexport','__exportfn','__exportinterval','__exportfile','__pktsampling','__flowsampling','__maintenance_cycle','__longflowtmo','__flowinactivetmo']
    def __init__(self, **kwargs):
        self.__counterexport = bool(kwargs.get('counterexport',False))
        self.__exportfn = eval(kwargs.get('flowexportfn','null_export_factory'))
        self.__exportinterval = int(kwargs.get('counterexportinterval',1))
        self.__exportfile = kwargs.get('counterexportfile',None)
        self.__pktsampling = float(kwargs.get('pktsampling',1.0))
        self.__flowsampling = float(kwargs.get('flowsampling',1.0))
        self.__maintenance_cycle = float(kwargs.get('maintenance_cycle',60.0))
        self.__longflowtmo = int(kwargs.get('longflowtmo',-1))
        self.__flowinactivetmo = int(kwargs.get('flowinactivetmo',-1))

    @property 
    def counterexport(self):
        return self.__counterexport

    @property
    def exportfn(self):
        return self.__exportfn

    @property 
    def exportinterval(self):
        return self.__exportinterval

    @property 
    def exportfile(self):
        return self.__exportfile

    @property 
    def pktsampling(self):
        return self.__pktsampling

    @property 
    def flowsampling(self):
        return self.__flowsampling

    @property 
    def maintenance_cycle(self):
        return self.__maintenance_cycle

    @property 
    def longflowtmo(self):
        return self.__longflowtmo

    @property 
    def flowinactivetmo(self):
        return self.__flowinactivetmo

    def __str__(self):
        return 'MeasurementConfig <{}, {}, {}>'.format(str(self.exportfn), str(self.counterexport), self.exportfile)


class NullMeasurement(object):
    def start(self):
        pass
    def stop(self):
        pass
    def add(self, flowlet, prevnode):
        pass
    def remove(self, flowlet, prevnode):
        pass


class NodeMeasurement(NullMeasurement):
    BYTECOUNT = 0
    PKTCOUNT = 1
    FLOWCOUNT = 2
    __slots__ = ['sim','config','counters','flow_table','node_name','exporter','counters','counter_exportfh']

    def __init__(self, sim, measurement_config, node_name):
        self.sim = sim
        self.config = measurement_config
        self.node_name = node_name
        self.flow_table = {}
        self.counters = defaultdict(Counter)
        self.counter_exportfh = None
        self.exporter = self.config.exportfn(node_name)
        # print self.config, self.node_name

    def start(self):
        # start router maintenance loop at random within first 10 seconds
        # maintenance loop periodically fires thereafter
        # (below code is used to desynchronize router maintenance across net)

        self.sim.after(random()*self.config.maintenance_cycle, 'node-flowexport-'+str(self.node_name), self.flow_export)

        if self.config.counterexport and self.config.exportinterval > 0:
            if self.config.exportfile == 'stdout':
                self.counter_exportfh = sys.stdout
            else:
                self.counter_exportfh = open('{}_{}.txt'.format(self.node_name, self.config.exportfile), 'w')
            self.sim.after(0, 'router-snmpexport-'+str(self.node_name), self.counter_export)

    def counter_export(self):
        if not self.config.counterexport:
            return

        for k,v in self.counters.iteritems():
            print >>self.counter_exportfh, '%8.3f %s->%s %d bytes %d pkts %d flows' % (self.sim.now, k, self.node_name, v[self.BYTECOUNT], v[self.PKTCOUNT], v[self.FLOWCOUNT])
        self.counters = defaultdict(Counter)
        self.sim.after(self.config.exportinterval, 'node-snmpexport-'+str(self.node_name), self.counter_export)

    def flow_export(self):
        config = self.config
        killlist = []
        for k,v in self.flow_table.iteritems():
            # if flow has been inactive for inactivetmo seconds, or
            # flow has been active longer than longflowtmo seconds, expire it
            if config.flowinactivetmo > 0 and ((self.sim.now - v.flowend) >= config.flowinactivetmo) and v.flowend > 0:
                self.exporter.exportflow(self.sim.now, v)
                killlist.append(k)

            if config.longflowtmo > 0 and ((self.sim.now - v.flowstart) >= config.longflowtmo) and v.flowend > 0:
                self.exporter.exportflow(self.sim.now, v)
                killlist.append(k)

        for k in killlist:
            if k in self.flow_table:
                del self.flow_table[k]

        # reschedule next router maintenance
        self.sim.after(self.config.maintenance_cycle, 'node-flowexport-'+str(self.node_name), self.flow_export)

    def stop(self):
        killlist = []
        for k,v in self.flow_table.iteritems():
            if v.flowend < 0:
                v.flowend = self.sim.now
            self.exporter.exportflow(self.sim.now, v)
            killlist.append(k)

        for k in killlist:
            del self.flow_table[k]
        self.exporter.shutdown()
        if self.counter_exportfh and self.config.exportfile != 'stdout':
            self.counter_exportfh.close() 

    def __nosample(self):
        if self.config.flowsampling < 1.0:
            return random() > self.config.flowsampling

    def __addflow(self, flowlet, prevnode):
        newflow = 0
        flet = None
        if flowlet.key in self.flow_table:
            flet = self.flow_table[flowlet.key]
            flet.flowend = self.sim.now
            flet += flowlet
        else:
            # NB: shallow copy of flowlet; will share same reference to
            # five tuple across the entire simulation
            newflow = 1
            flet = copy.copy(flowlet) 
            flet.flowend += self.sim.now
            flet.flowstart = self.sim.now
            self.flow_table[flet.key] = flet
            flet.ingress_intf = prevnode
        return newflow

    def __addcounters(self, flowlet, prevnode, newflow):
        counters = self.counters[prevnode]
        counters[self.BYTECOUNT] += flowlet.bytes
        counters[self.PKTCOUNT] += flowlet.pkts
        counters[self.FLOWCOUNT] += newflow

    def add(self, flowlet, prevnode):
        if self.__nosample():
            return
        newflow = self.__addflow(flowlet, prevnode)
        if self.config.counterexport:
            self.__addcounters(flowlet, prevnode, newflow)

    def remove(self, flowlet, prevnode):
        if flowlet.key not in self.flow_table:
            return

        stored_flowlet = self.flow_table[flowlet.key]
        if stored_flowlet.flowend < 0:
            stored_flowlet.flowend = self.sim.now
        del self.flow_table[flowlet.key]
        self.exporter.exportflow(self.sim.now, stored_flowlet)



class Node(object):
    '''Base Node class in fs.  All subclasses will want to at least override flowlet_arrival to handle
       the arrival of a new flowlet at the node.'''

    __slots__ = ['name','sim','debug','node_measurements','link_table','logger']

    def __init__(self, name, sim, debug, measurement_config, **kwargs):
        # exportfn, exportinterval, exportfile):
        self.name = name
        self.sim = sim
        self.debug = debug
        if measurement_config:
            self.node_measurements = NodeMeasurement(sim, measurement_config, name)
        else:
            self.node_measurements = NullMeasurement()
        self.link_table = {}
        self.logger = logging.getLogger('flowmax')

    def start(self):
        self.node_measurements.start()

    def stop(self):
        self.node_measurements.stop()

    def flowlet_arrival(self, flowlet, prevnode, destnode):
        pass

    def measure_flow(self, flowlet, prevnode):
        self.node_measurements.add(flowlet, prevnode)

    def unmeasure_flow(self, flowlet, prevnode):
        self.node_measurements.remove(flowlet, prevnode)

    def add_link(self, link, next_router):
        self.link_table[next_router] = link

    def get_link(self, next_router):
        rv = None
        if next_router in self.link_table:
            rv = self.link_table[next_router]
        return rv

class UnhandledOpenflowMessage(Exception):
    pass

class FsSwitchFlowTable(SwitchFlowTable):
    def entry_for_packet(self, flowlet, prevnode):
        '''override entry_for_packet in pox SwitchFlowTable class to construct
        an ofp_match object from an fs flowlet, and get matching table entries.

        return highest priority flow table entry matching incoming flowlet and
        previous node, or None if no match.
        '''
        matcher = ofp_match_from_flowlet(flowlet)
        for entry in self._table:
            if entry.match == matcher or entry.match.matches_with_wildcards(matcher, consider_other_wildcards=False):
                return entry
        return None

class OpenflowSwitch(Node):
    def __init__(self, name, sim, debug, measurement_config, **kwargs):
        Node.__init__(self, name, sim, debug, measurement_config, **kwargs)
        self.flow_table = FsSwitchFlowTable()

    def apply_actions(self, flowlet, actions):
        nh = None
        # FIXME: actions don't actually do anything (yet); just enqueue/output are implemented
        actionmap = {
            type(ofp_action_strip_vlan()): lambda f: None,
            type(ofp_action_vlan_vid()): lambda f: None, # .vlan_vid
            type(ofp_action_vlan_pcp()): lambda f: None, # .vlan_pcp
            type(ofp_action_dl_addr()): lambda f: None, # .type OFPAT_SET_DL_SRC/DST, .dl_addr
            type(ofp_action_nw_addr()): lambda f: None, # .type OFPAT_SET_NW_SRC/DST, .nw_addr
            type(ofp_action_nw_tos()): lambda f: None, # .nw_tos
            type(ofp_action_tp_port()): lambda f: None, # .type OFPAT_SET_TP_SRC/DST, .tp_addr
            type(ofp_action_output()): lambda f: None, 
        }
        for act in actions:
            if isinstance(act,ofp_action_enqueue) or isinstance(act,ofp_action_output):
                if act.port == 65532 or act.port == 65531:
                    # output port OFPP_FLOOD
                    nh = []
                    for node in self.sim.graph.node.keys():
                        if node != self.name and node != 'controller':
                            nh.append(node)
                    return nh
                else:
                    nh = act.port
                # also .queue_id for enqueue action
            else:
                # apply ofp actions
                nh = actionmap[type(act)](flowlet)
        return nh

    def match_table(self, flowlet, prevnode):
        # delegate to POX flowtable
        entry = self.flow_table.entry_for_packet(flowlet, prevnode)
        if not entry:
            return None
        entry.touch_packet(flowlet.bytes,now=self.sim.now)
        nh = self.apply_actions(flowlet, entry.actions)
        return nh

    def update_table(self, ofmessage):
        # print ofmessage.message.pox_ofp_message.actions
        rv = self.flow_table.process_flow_mod(ofmessage.message.pox_ofp_message)
        # JS: because of limitation in being able to explicitly set current timestamp
        # through process_flow_mod (it doesn't correctly return the new table entry created),
        # find matches in the table (which should be exactly what we just added), and explicitly
        # set created and last_touched timestamps to "now" in simulation time.
        for m in self.flow_table.matching_entries(ofmessage.message.pox_ofp_message.match):
            m.counters['created'] = self.sim.now
            m.counters['last_touched'] = self.sim.now
        return rv

    def table_ager(self):
        entries = self.flow_table.remove_expired_entries(self.sim.now)
        # print "in table ager, evicting {} entries.".format(len(entries))
        for entry in entries:
            msg = OpenflowMessage(flowident_from_ofp_match(entry.match), 'ofp_flow_removed', match=entry.match, cookie=entry.cookie, priority=entry.priority, reason=0, duration_sec=0, duration_nsec=0, idle_timeout=entry.idle_timeout, packet_count=entry.counters['packets'], byte_count=entry.counters['bytes'])

            # FIXME: controller name is hard-coded.  need a general way to identify
            # the link to/name of the controller node
            self.link_table['controller'].flowlet_arrival(msg, self.name, 'controller')
        self.sim.after(1, "openflow-switch-table-ager"+str(self.name), self.table_ager)
        return len(entries)

    def start(self):
        Node.start(self)
        self.sim.after(1, "openflow-switch-table-ager"+str(self.name), self.table_ager)

    def flowlet_arrival(self, flowlet, prevnode, destnode):
        '''totally ugly, non-DRY grumpy method.  yuck'''

        nexthop = None
        if isinstance(flowlet, OpenflowMessage):
            origin, dest, prev = flowlet.get_context()
            flowlet_out = flowlet.data
            if origin:
                assert(origin == self.name)

            # self.logger.info("At {} got OpenflowMessage: {} flet: {} context: {}".format(self.name, str(flowlet), str(flowlet_out), str(flowlet.get_context())))
            if (flowlet.message_type == 'ofp_flow_mod'):
                self.update_table(flowlet)
                nexthop = self.match_table(flowlet_out, prev)
                # self.logger.info("At {} next hop for {}: {}".format(self.name, flowlet_out, nexthop))
                self.link_table[nexthop].flowlet_arrival(flowlet_out, self.name, dest)

            elif (flowlet.message_type == 'ofp_packet_out'):
                # FIXME: assume that the flowlet is passed along as the openflow flowlet data
                nexthop = self.apply_actions(flowlet_out, flowlet.actions)
                if not nexthop:
                    raise UnhandledOpenflowMessage("Got packet_out message from controller, but I still don't know how to forward it: {}, {}".format(flowlet_out, flowlet.actions))
                elif isinstance(nexthop, list):
                    for nh in nexthop:
                        egress_link = self.link_table[nh]
                        egress_link.flowlet_arrival(flowlet_out, self.name, destnode)
                else:
                    self.link_table[nexthop].flowlet_arrival(flowlet_out, self.name, nexthop)

            else:
                raise UnhandledOpenflowMessage("We only support ofp_flow_mod for now.")

        elif isinstance(flowlet, Flowlet):
            self.measure_flow(flowlet, prevnode)

            # JS: done: got to destination
            if destnode == self.name:
                return None

            # match flowlet against flow table and figure out what to do with it
            nexthop = self.match_table(flowlet, prevnode)

            # JS: can't test against iterable since a string is iterable
            #if isinstance(nexthop, collections.Iterable):
            if isinstance(nexthop, list):
                for nh in nexthop:
                    egress_link = self.link_table[nh]
                    egress_link.flowlet_arrival(flowlet, self.name, destnode)
            elif nexthop and nexthop != self.name and nexthop != 'harpoon':
                egress_link = self.link_table[nexthop]
                egress_link.flowlet_arrival(flowlet, self.name, destnode)
            else:
                #msg.reason = 0 # FIXME
                ofm = OpenflowMessage(flowlet.flowident, 'ofp_packet_in', in_port=prevnode, reason=0)
                ofm.data = flowlet                
                ofm.set_context(self.name, destnode, prevnode)
                self.link_table['controller'].flowlet_arrival(flowlet=ofm, prevnode=self.name, destnode='controller')
                nexthop = 'controller'

        return nexthop

TIMEOUT = 60*2

class Entry (object):
  """
  We use the port to determine which port to forward traffic out of.
  We use the MAC to answer replies.
  We use the timeout so that if an entry is older than FLOWLET_TIMEOUT, we
  remove it from the ipTable
  """
  def __init__ (self, port, mac):
    self.timeout = time.time() + TIMEOUT
    self.port = port
    self.mac = mac


class ControllerModule(object):
    def __init__(self, sim):
        self.sim = sim


class L3Learning(ControllerModule):
    """
    A stupid L3 switch
    
    For each switch:
    1) Keep a table that maps IP addresses to MAC addresses and switch ports.
    Stock this table using information from flowlets.
    2) When you see a flowlet, try to answer it using information in the table
    from step 1.  If the info in the table is old, just flood the flowlet.
    3) When you see an IP packet, if you know the destination port (because it's
    in the table from step 1), install a flow for it.
    """
    def __init__ (self, sim):
        # For each switch, we map IP addresses to Entries
        ControllerModule.__init__(self, sim)
        self.ipTable = {}

    def handlePacketIn(self, flet, prevnode):
        dpid = prevnode
        if dpid not in self.ipTable:
            # New switch -- create an empty table
            self.ipTable[dpid] = {}
        
        # Learn or update port/MAC info
        self.ipTable[dpid][flet.key.srcip] = Entry(flet.in_port, flet.srcmac)
        # Try to forward
        dstaddr = flet.key.dstip
        if dstaddr in self.ipTable[dpid]:
            # We have info about what port to send it out on...
            prt = self.ipTable[dpid][dstaddr].port
            mac = self.ipTable[dpid][dstaddr].mac
            if prt != prevnode:
                # next hop should not be same as the node from which this 
                # ofp_packet_out is received.
                # print "Installing flow_mod"
                actions = {}
                actions['dstmac'] = mac
                actions['port'] = prt
                match = ofp_match_from_flowlet(flet)
                match.dl_src = None # Wildcard source MAC
                idle_timeout = 10
                hard_timeout = 0
                ofm = OpenflowMessage(flet.flowident, 'ofp_flow_mod', match = match, action = actions, hard_timeout = hard_timeout, idle_timeout = idle_timeout, command = "add")
                ofm.data = flet
                return ofm

            else:
                # Flood the packet
                ofm = OpenflowMessage(flet.flowident, 'ofp_flow_mod', idle_timeout = 1, hard_timeout = 1, action = 'flood')
                ofm.data = flet
                return ofm
        
        else:
            # Flood the packet
            ofm = OpenflowMessage(flet.flowident, 'ofp_flow_mod', idle_timeout = 1, hard_timeout = 1, action = 'flood')
            ofm.data = flet
            return ofm
        

class Hub(ControllerModule):
    """
    Turns your complex OpenFlow switches into stupid hubs.
    """
    def __init__(self, sim):
        ControllerModule.__init__(self, sim)

    def handlePacketIn (self, flet, prevnode):
        # No need to set idle and hard timeouts as hub floods flowlets to all the ports
        # in the network.

        ofm = OpenflowMessage(flet.flowident, 'ofp_flow_mod', action = 'flood')
        ofm.data = flet
        return ofm
        
class L2PairsSwitch(object):
    """
    A super simple OpenFlow learning switch that installs rules for
    each pair of L2 addresses.
    """
    def __init__(self, sim):
        # This table maps (switch,MAC-addr) pairs to the port on 'switch' at
        # which we last saw a packet *from* 'MAC-addr'.
        # (In this case, we use a Switch name for the switch.)
        ControllerModule.__init__(self, sim)
        self.table = {}

    # Handle messages the switch has sent us because it has no
    # matching rule.
    def handlePacketIn (self, flet, prevnode):
        # Learn the source if source is not 'harpoon'
        if flet.in_port != 'harpoon':
            self.table[(prevnode,flet.srcmac)] = flet.in_port
        dst_port = self.table.get((prevnode,flet.dstmac))
        if dst_port is None:
            # We don't know where the destination is yet.  So, we'll just
            # send the packet out all ports (except the one it came in on!)
            # and hope the destination is out there somewhere. :)
            # To send out all ports, we can use either of the special ports
            # OFPP_FLOOD or OFPP_ALL.  We'd like to just use OFPP_FLOOD,
            # but it's not clear if all switches support this. :(
            ofm = OpenflowMessage(flet.flowident, 'ofp_flow_mod', idle_timeout = 1, hard_timeout = 1, action = 'flood')
            ofm.data = flet
            return ofm

        else:
            # print "Installing flow table entry"
            # Since we know the switch ports for both the source and dest
            # MACs, we can install rules for both directions.
            ofm = OpenflowMessage(flet.flowident, 'ofp_flow_mod', match_dl_dst = flet.dstmac, match_dl_src = flet.srcmac, action = flet.in_port)
            ofm.data = flet
            return ofm


class L2LearningSwitch(ControllerModule):
    """
    The learning switch "brain" associated with a single OpenFlow switch.

    When we see a packet, we'd like to output it on a port which will
    eventually lead to the destination.  To accomplish this, we build a
    table that maps addresses to ports.

    We populate the table by observing traffic.  When we see a packet
    from some source coming from some port, we know that source is out
    that port.

    When we want to forward traffic, we look up the desintation in our
    table.  If we don't know the port, we simply send the message out
    all ports except the one it came in on.  (In the presence of loops,
    this is bad!).

    In short, our algorithm looks like this:

    For each packet from the switch:
    1) Use source address and switch port to update address/port table
    2) Is transparent = False and either Ethertype is LLDP or the packet's
    destination address is a Bridge Filtered address?
    Yes:
    2a) Drop packet -- don't forward link-local traffic (LLDP, 802.1x)
    DONE
    3) Is destination multicast?
    Yes:
    3a) Flood the packet
    DONE
    4) Port for destination address in our address/port table?
    No:
    4a) Flood the packet
    DONE
    5) Is output port the same as input port?
    Yes:
    5a) Drop packet and similar ones for a while
    6) Install flow table entry in the switch so that this
    flow goes out the appopriate port
    6a) Send the packet out appropriate port
    """
    def __init__(self, sim, transparent = False):
        ControllerModule.__init__(self, sim)
        self.macToPort = {}
        self.transparent = transparent

    def handlePacketIn (self, flet, prevnode):
        """
        Handle packet in messages from the switch to implement above algorithm.
        """
        # Right now we have implemented only ofp_packet_in
        if (flet.message_type != 'ofp_packet_in'):
            sys.exit()
        if flet.in_port != 'harpoon':
            self.macToPort[flet.srcmac] = flet.in_port # 1

        def is_multicast(dstmac):
            """
            Returns True if this is a multicast address.
            """
            return True if (ord(dstmac[0]) & 1) else False
        
        # No packet type as of now
        # if not self.transparent: # 2
        #     if packet.type == packet.LLDP_TYPE or packet.dst.isBridgeFiltered():
        #         drop() # 2a
        #         return

        if is_multicast(flet.dstmac):
            # Flood the packet
            # Creating a message to be flooded
            # Flood the packet
            ofm = OpenflowMessage(flet.flowident, 'ofp_flow_mod', \
                                      idle_timeout = 1, hard_timeout = 1, action = 'flood')
            ofm.data = flet
            return ofm

        else:
            if flet.dstmac not in self.macToPort: # 4
                # Flood the packet
                # Creating a message to be flooded
                # Flood the packet
                ofm = OpenflowMessage(flet.flowident, 'ofp_flow_mod', \
                                          idle_timeout = 1, hard_timeout = 1, action = 'flood')
                ofm.data = flet
                return ofm

            else:
                port = self.macToPort[flet.dstmac]
                if port == flet.in_port: # 5
                    # 5a
                    match = ofp_match_from_flowlet(flet)
                    idle_timeout = 1
                    hard_timeout = 1
                    ofm = OpenflowMessage(flet.flowident, 'ofp_flow_mod', 
                                          match = match, idle_timeout = idle_timeout,
                                          hard_timeout = hard_timeout)
             
                    ofm.data = flet
                    return ofm
                # 6
                match = ofp_match_from_flowlet(flet)
                ofm = OpenflowMessage(flet.flowident, 'ofp_flow_mod', 
                                      match = match, idle_timeout = 1, hard_timeout = 3, 
                                      action = port)
                ofm.data = flet
                return ofm


class L3ShortestPaths(ControllerModule):
    def __init__(self, sim):
        ControllerModule.__init__(self, sim)
        self.logger = logging.getLogger('flowmax')
        self.graph = None

    def handlePacketIn (self, flet, prevnode):
        if not self.graph:
            self.graph = copy.deepcopy(self.sim.graph)
            self.graph.remove_node('controller')
            # FIXME: ignores weights!
            self.shortest_paths = networkx.shortest_path(self.graph)

        origin,dest,prev = flet.get_context()
        destnode = self.sim.destnode(origin, flet.dstaddr)
        
        path = self.shortest_paths[origin][dest]
        nh = path[1] 
        # self.logger.info("ShortestPath received: {} from: {} prev: {} dest: {} path: {} nexthop: {}".format(str(flet), origin, prev, dest, str(path), nh))

        match = ofp_match_from_flowlet(flet)
        ofm = OpenflowMessage(flet.flowident, 'ofp_flow_mod', match=match, idle_timeout=60, action=nh)
        ofm.data = flet
        return ofm

class OpenflowController(Node):
    __slots__ = ['forwarding', 'forwardingSwitch']

    def __init__(self, name, sim, debug, measurement_config, **kwargs):
        Node.__init__(self, name, sim, debug, measurement_config, **kwargs)
        if 'forwarding' in kwargs:
            self.forwarding = kwargs['forwarding']
            if (self.forwarding == 'l2_learning'):
                self.forwardingSwitch = L2LearningSwitch(sim)
            elif (self.forwarding == 'l2_pairs'):
                self.forwardingSwitch = L2PairsSwitch(sim)
            elif (self.forwarding == 'hub'):
                self.forwardingSwitch = Hub(sim)
            elif (self.forwarding == 'l3_learning'):
                self.forwardingSwitch = L3Learning(sim)
            elif (self.forwarding == 'shortest_paths'):
                self.forwardingSwitch = L3ShortestPaths(sim)

    def flowlet_arrival(self, flowlet, prevnode, destnode):
        if isinstance(flowlet, OpenflowMessage):
            # handle message from controller
            # Check if message_type is ofp_packet_in
            if (flowlet.message_type == 'ofp_packet_in'):
                # Calling handlePacketIn function of the forwardingSwitch which 
                # will handle the flowlet depending upon the switch forwarding type 
                # given in the DOT config file
                nexthop = prevnode # bounce back to switch that sent us control message
                context = flowlet.get_context()
                orig_flowlet = flowlet.data
                ofm = self.forwardingSwitch.handlePacketIn(flowlet, prevnode)
                ofm.set_context(*context)
                ofm.data = orig_flowlet
                self.link_table[prevnode].flowlet_arrival(ofm, 'controller', nexthop)
                return nexthop
            elif(flowlet.message_type == 'ofp_flow_removed'):
                # FIXME: currently unhandled --- should handle flow table removal events
                pass
            else:
                # This should not happen currently 
                raise UnhandledOpenflowMessage("Got unexpected {} in controller.".format(str(flowlet)))

        else:
            # this should never happen; the controller should *only* receive OpenflowMessage instances
            raise UnhandledOpenflowMessage("Got non-OpenflowMessage in controller.  Bad stuff.")
            


class Router(Node):
    def __init__(self, name, sim, debug, measurement_config, **kwargs): 
        Node.__init__(self, name, sim, debug, measurement_config, **kwargs)
        self.autoack=kwargs.get('autoack',False)

    def flowlet_arrival(self, flowlet, prevnode, destnode):
        if isinstance(flowlet, SubtractiveFlowlet):
            killlist = []
            ok = []
            for k,flet in self.flow_table.iteritems():
                if next(flowlet.action) and (not flowlet.srcaddr or flet.srcaddr in flowlet.srcaddr) and (not flowlet.dstaddr or flet.dstaddr in flowlet.dstaddr) and (not flowlet.ipproto or flet.ipproto == flowlet.ipproto):
                    killlist.append(k)
                else:
                    ok.append(k)
            for kkey in killlist:
                del self.flow_table[kkey]
            # print 'subtractive flowlet encountered: removing',len(killlist),'keeping',len(ok),'me:',self.name,'dest',destnode,flowlet
            if destnode != self.name:
                nh = self.sim.nexthop(self.name, destnode)
                if nh:
                    egress_link = self.link_table[nh]
                    egress_link.flowlet_arrival(flowlet, self.name, destnode)
            return

        else:
            # a "normal" Flowlet object
            self.measure_flow(flowlet, prevnode)

            # print 'flowlet_arrival',flowlet,'eof?',flowlet.endofflow
            if flowlet.endofflow:
                self.unmeasure_flow(flowlet, prevnode)

            if destnode == self.name:
                if self.autoack and flowlet.ipproto == socket.IPPROTO_TCP and not flowlet.ackflow:
                    revflow = Flowlet(flowlet.flowident.mkreverse())
                    
                    revflow.ackflow = True
                    revflow.flowstart = revflow.flowend = self.sim.now

                    if flowlet.tcpflags & 0x04: # RST
                        return

                    if flowlet.tcpflags & 0x02: # SYN
                        revflow.tcpflags = revflow.tcpflags | 0x10
                        # print 'setting syn/ack flags',revflow.tcpflagsstr

                    if flowlet.tcpflags & 0x01: # FIN
                        revflow.tcpflags = revflow.tcpflags | 0x10 # ack
                        revflow.tcpflags = revflow.tcpflags | 0x01 # fin

                    revflow.pkts = flowlet.pkts / 2 # brain-dead ack-every-other
                    revflow.bytes = revflow.pkts * 40

                    self.measure_flow(revflow, self.name)

                    # weird, but if reverse flow is short enough, it might only
                    # stay in the flow cache for a very short period of time
                    if revflow.endofflow:
                        self.__remove_flowlet(revflow)

                    destnode = self.sim.destnode(self.name, revflow.dstaddr)

                    # guard against case that we can't do the autoack due to
                    # no "real" source (i.e., source was spoofed or source addr
                    # has no route)
                    if destnode and destnode != self.name:
                        nh = self.sim.nexthop(self.name, destnode)
                        if nh:
                            egress_link = self.link_table[nh]
                            egress_link.flowlet_arrival(revflow, self.name, destnode)
                        else:
                            self.logger.debug('No route from %s to %s (trying to run ackflow)' % (self.name, destnode))
            else:
                nh = self.sim.nexthop(self.name, destnode)
                assert (nh != self.name)
                if nh:
                    egress_link = self.link_table[nh]
                    egress_link.flowlet_arrival(flowlet, self.name, destnode)
                else:
                    self.logger.debug('No route from %s to %s (in router nh decision; ignoring)' % (self.name, destnode))

