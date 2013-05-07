from pox.datapaths.switch import SoftwareSwitchBase
from pox.openflow import libopenflow_01 as oflib
import pox.openflow.of_01 as ofcore
from fslib.openflow import load_pox_component

from fslib.node import Node
from fslib.common import fscore, get_logger

'''Because 'bridge' sounds better than 'monkeypatch'.'''

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
        # self.logger = get_logger()
        # self.arp_table_ip = {}
        # self.arp_table_node = defaultdict(list)

    def send_packet(self, packet, port_num):
        '''Forward a data plane packet out a given port'''
        self.interfaces[port_num].flowlet_arrival()

    def send(self, ofmessage):
        '''Callback function for POX SoftwareSwitchBase to send an outgoing OF message.'''
        self.controller_links[self.controller_name].flowlet_arrival()

    def set_message_handler(self, *args):
        '''Dummy callback function for POX SoftwareSwitchBase'''
        pass

    def flowlet_arrival(self, flowlet, prevnode, destnode, input_port):
        '''Incoming flowlet: determine whether it's a data plane flowlet or whether it's an OF message
        coming back from the controller'''

        # self.pox_switch.rx_message(self, ofmessage)
        # self.pox_switch.rx_packet(self, packet, in_port)
        pass

    def add_link(self, link, hostip, remoteip, next_node):
        # self.pox_switch.add_port(int)
        pass


class OpenflowController(Node):
    __slots__ = ['components']

    def __init__(self, name, measurement_config, **kwargs):
        Node.__init__(self, name, measurement_config, **kwargs)
        self.components = kwargs.get('components','').split()
        for component in self.components:
            load_pox_component(component)

    def flowlet_arrival(self, flowlet, prevnode, destnode, input_port):
        # figure out which switch controller, then call
        # ofcore.Connection.simrecv(message)
        pass

    def add_link(self, link, hostip, remoteip, next_node):
        pass

    def controller_to_switch(self, mesg):
        pass

    def start(self):
        Node.start(self)
        # create POX quasi-connections from switch to controller
        # can't do this until everything is set up (i.e. until start
        # method is called) because this will immediately result in
        # some OF control messages getting generated

        # fconn = ofcore.Connection(-1, self.controller_to_switch)
