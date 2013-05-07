from pox.datapaths.switch import SoftwareSwitchBase
from pox.openflow import libopenflow_01 as oflib
import pox.openflow.of_01 as ofcore
from fslib.openflow import load_pox_component

from fslib.node import Node
from fslib.common import fscore, get_logger
from fslib.flowlet import Flowlet, FlowIdent

'''Because 'bridge' sounds better than 'monkeypatch'.'''

class OpenflowMessage(Flowlet):
    __slots__ = ['ofmsg']

    def __init__(self, ident, ofmsg):
        Flowlet.__init__(self, ident)
        self.ofmsg = ofmsg
        self.bytes = len(ofmsg)


class PoxBridgeSoftwareSwitch(SoftwareSwitchBase):
    def _output_packet_physical(self, packet, port_num):
        self.forward(packet, port_num)

    def set_output_packet_callback(self, fn):
        self.forward = fn

class OpenflowSwitch(Node):
    __slots__ = ['dpid', 'pox_switch', 'controller_name', 'controller_links']

    def __init__(self, name, measurement_config, **kwargs):
        Node.__init__(self, name, measurement_config, **kwargs)
        self.dpid = abs(hash(name))
        self.pox_switch = PoxBridgeSoftwareSwitch(self.dpid, name=name, ports=0)
        self.pox_switch.set_connection(self)
        self.pox_switch.set_output_packet_callback(self. send_packet)
        self.controller_name = kwargs['controller']
        self.controller_links = {}

        # self.interfaces = {}
        # self.arp_table_ip = {}
        # self.arp_table_node = defaultdict(list)

    def send_packet(self, packet, port_num):
        '''Forward a data plane packet out a given port'''
        self.interfaces[port_num].flowlet_arrival()

    def send(self, ofmessage):
        '''Callback function for POX SoftwareSwitchBase to send an outgoing OF message
        to controller.'''
        self.logger.debug("OF switch sending to controller: {}".format(ofmessage))
        self.controller_links[self.controller_name].flowlet_arrival(OpenflowMessage(None, ofmessage), self.name, self.controller_name)

    def set_message_handler(self, *args):
        '''Dummy callback function for POX SoftwareSwitchBase'''
        pass

    def flowlet_arrival(self, flowlet, prevnode, destnode, input_ip):
        '''Incoming flowlet: determine whether it's a data plane flowlet or whether it's an OF message
        coming back from the controller'''
        if isinstance(flowlet, Flowlet):
            # assume this is an incoming flowlet on the dataplane.  
            # reformat it and inject it into the POX switch
            # self.pox_switch.rx_packet(self, packet, in_port)
            input_port = self.arp_table_ip[input_ip][1]
            self.pox_switch.rx_packet(self, flowlet, input_port)
        else:
            self.pox_switch.rx_message(self, flowlet)

    def add_link(self, link, hostip, remoteip, next_node):
        if next_node == self.controller_name:
            self.controller_links[self.controller_name] = link
        else:
            portnum = len(self.interfaces) + 1
            self.interfaces[portnum] = (link, hostip, remoteip, next_node)
            hwaddr = "00:00:00:00:%2x:%2x" % (self.dpid % 255, portnum)
            self.arp_table_node[next_node].append( (hwaddr, portnum, hostip, remoteip, link) )
            self.arp_table_ip[remoteip] = (hwaddr, portnum, hostip, next_node, link)

    def start(self):
        Node.start(self)
        for portnum,ifinfo in self.interfaces.iteritems():
            self.pox_switch.add_port(portnum)




class OpenflowController(Node):
    __slots__ = ['components', 'switch_links']

    def __init__(self, name, measurement_config, **kwargs):
        Node.__init__(self, name, measurement_config, **kwargs)
        self.components = kwargs.get('components','').split()
        for component in self.components:
            load_pox_component(component)
        self.switch_links = {}

    def flowlet_arrival(self, flowlet, prevnode, destnode, input_port):
        '''Handle switch-to-controller incoming messages'''
        # assumption: flowlet is an openflow message
        self.logger.debug("Switch-to-controller {}->{}: {}".format(prevnode, destnode, flowlet))
        assert(isinstance(flowlet,OpenflowMessage))
        self.switch_links[prevnode][0].simrecv(flowlet.ofmsg) 

    def add_link(self, link, hostip, remoteip, next_node):
        '''don't do much except create queue of switch connections so that we can
        eventually build ofcore.Connection objects for each one
        once start() gets called.'''

        # two assumptions: every link that is created for an OF controller is to
        # some OF switch, and there's only one link between controller and switch.
        self.switch_links[next_node] = (link, hostip, remoteip)

    def controller_to_switch(self, switchlink, mesg):
        '''Ferry an OF message from controller to switch'''
        self.logger.debug("Controller-to-switch {}->{}: {}".format(self.name, switchlink.egress_node.name, mesg))
        switchlink.flowlet_arrival(OpenflowMessage(None, mesg), self.name, switchlink.egress_node)

    def start(self):
        '''create POX quasi-connections from switch to controller
        can't do this until everything is set up (i.e. until start
        method is called) because this will immediately result in
        some OF control messages getting generated'''
        Node.start(self)

        # NB: make a list of switch_link info so we can modify switch_links as we go
        for switch_name,xtup in self.switch_links.items():
            callbackfn = lambda msg: self.controller_to_switch(xtup[0], msg)
            switchconn = ofcore.Connection(-1, callbackfn)
            switch_info = [ switchconn ] 
            switch_info.extend(xtup)
            self.switch_links[switch_name] = tuple(switch_info)
