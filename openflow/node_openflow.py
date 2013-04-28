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
    __slots__ = ['flow_table']

    def __init__(self, name, measurement_config, **kwargs):
        Node.__init__(self, name, measurement_config, **kwargs)
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
                    for node in fscore().graph.node.keys():
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
        entry.touch_packet(flowlet.bytes,now=fscore().now)
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
            m.counters['created'] = fscore().now
            m.counters['last_touched'] = fscore().now
        return rv

    def table_ager(self):
        entries = self.flow_table.remove_expired_entries(fscore().now)
        # print "in table ager, evicting {} entries.".format(len(entries))
        for entry in entries:
            msg = OpenflowMessage(flowident_from_ofp_match(entry.match), 'ofp_flow_removed', match=entry.match, cookie=entry.cookie, priority=entry.priority, reason=0, duration_sec=0, duration_nsec=0, idle_timeout=entry.idle_timeout, packet_count=entry.counters['packets'], byte_count=entry.counters['bytes'])

            # FIXME: controller name is hard-coded.  need a general way to identify
            # the link to/name of the controller node
            self.forward('controller', msg, 'controller')
        fscore().after(1, "openflow-switch-table-ager"+str(self.name), self.table_ager)
        return len(entries)

    def start(self):
        Node.start(self)
        fscore().after(1, "openflow-switch-table-ager"+str(self.name), self.table_ager)

    def flowlet_arrival(self, flowlet, prevnode, destnode, input_port):
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
                self.forward(nexthop, flowlet_out, dest)

            elif (flowlet.message_type == 'ofp_packet_out'):
                # FIXME: assume that the flowlet is passed along as the openflow flowlet data
                nexthop = self.apply_actions(flowlet_out, flowlet.actions)
                if not nexthop:
                    raise UnhandledOpenflowMessage("Got packet_out message from controller, but I still don't know how to forward it: {}, {}".format(flowlet_out, flowlet.actions))
                elif isinstance(nexthop, list):
                    for nh in nexthop:
                        self.forward(nh, flowlet_out, destnode)
                else:
                    self.forward(nexthop, flowlet_out, nexthop)

            else:
                raise UnhandledOpenflowMessage("We only support ofp_flow_mod for now.")

        elif isinstance(flowlet, Flowlet):
            self.measure_flow(flowlet, prevnode, input_port)

            # JS: done: got to destination
            if destnode == self.name:
                return None

            # match flowlet against flow table and figure out what to do with it
            nexthop = self.match_table(flowlet, prevnode)

            # JS: can't test against iterable since a string is iterable
            #if isinstance(nexthop, collections.Iterable):
            if isinstance(nexthop, list):
                for nh in nexthop:
                    self.forward(nh, flowlet, destnode)
            elif nexthop and nexthop != self.name and nexthop != 'harpoon':
                self.forward(nexthop, flowlet, destnode)
            else:
                #msg.reason = 0 # FIXME
                ofm = OpenflowMessage(flowlet.flowident, 'ofp_packet_in', in_port=prevnode, reason=0)
                ofm.data = flowlet                
                ofm.set_context(self.name, destnode, prevnode)
                self.forward('controller', ofm, 'controller')
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
    pass


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
    def __init__ (self):
        # For each switch, we map IP addresses to Entries
        ControllerModule.__init__(self)
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
    def __init__(self):
        ControllerModule.__init__(self)

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
    def __init__(self):
        # This table maps (switch,MAC-addr) pairs to the port on 'switch' at
        # which we last saw a packet *from* 'MAC-addr'.
        # (In this case, we use a Switch name for the switch.)
        ControllerModule.__init__(self)
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
    def __init__(self, transparent = False):
        ControllerModule.__init__(self)
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
    def __init__(self):
        ControllerModule.__init__(self)
        self.logger = get_logger()
        self.graph = None

    def handlePacketIn (self, flet, prevnode):
        if not self.graph:
            self.graph = copy.deepcopy(fscore().graph)
            self.graph.remove_node('controller')
            # FIXME: ignores weights!
            self.shortest_paths = networkx.shortest_path(self.graph)

        origin,dest,prev = flet.get_context()
        destnode = fscore().destnode(origin, flet.dstaddr)
        
        path = self.shortest_paths[origin][dest]
        nh = path[1] 
        # self.logger.info("ShortestPath received: {} from: {} prev: {} dest: {} path: {} nexthop: {}".format(str(flet), origin, prev, dest, str(path), nh))

        match = ofp_match_from_flowlet(flet)
        ofm = OpenflowMessage(flet.flowident, 'ofp_flow_mod', match=match, idle_timeout=60, action=nh)
        ofm.data = flet
        return ofm

class OpenflowController(Node):
    __slots__ = ['forwarding', 'forwardingSwitch']

    def __init__(self, name, measurement_config, **kwargs):
        Node.__init__(self, name, measurement_config, **kwargs)
        if 'forwarding' in kwargs:
            self.forwarding = kwargs['forwarding']
            if (self.forwarding == 'l2_learning'):
                self.forwardingSwitch = L2LearningSwitch()
            elif (self.forwarding == 'l2_pairs'):
                self.forwardingSwitch = L2PairsSwitch()
            elif (self.forwarding == 'hub'):
                self.forwardingSwitch = Hub()
            elif (self.forwarding == 'l3_learning'):
                self.forwardingSwitch = L3Learning()
            elif (self.forwarding == 'shortest_paths'):
                self.forwardingSwitch = L3ShortestPaths()

    def flowlet_arrival(self, flowlet, prevnode, destnode, input_port):
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
                self.forward(prevnode, ofm, nexthop)
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
            
