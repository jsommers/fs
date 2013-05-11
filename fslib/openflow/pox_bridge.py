from socket import IPPROTO_TCP, IPPROTO_UDP, IPPROTO_ICMP

from pox.datapaths.switch import SoftwareSwitch
from pox.openflow import libopenflow_01 as oflib
import pox.lib.packet as pktlib
from pox.lib.addresses import *
import pox.openflow.of_01 as ofcore
from fslib.openflow import load_pox_component
import pox.core

from fslib.node import Node
from fslib.common import fscore, get_logger
from fslib.flowlet import Flowlet, FlowIdent

from pytricia import PyTricia

class UnhandledPoxPacketFlowletTranslation(Exception):
    pass


'''Because 'bridge' sounds better than 'monkeypatch'.'''

class OpenflowMessage(Flowlet):
    __slots__ = ['ofmsg']

    def __init__(self, ident, ofmsg):
        Flowlet.__init__(self, ident)
        self.ofmsg = ofmsg
        self.bytes = len(ofmsg)

def flowlet_to_packet(flowlet):
    ident = flowlet.ident.key

    etherhdr = pktlib.ethernet()
    etherhdr.src = EthAddr(ident.srcmac)
    etherhdr.dst = EthAddr(ident.dstmac)
    etherhdr.type = pktlib.ethernet.IP_TYPE

    ipv4 = pktlib.ipv4() 
    ipv4.srcip = IPAddr(ident.srcip)
    ipv4.dstip = IPAddr(ident.dstip)
    ipv4.protocol = ident.ipproto
    ipv4.tos = flowlet.iptos
    ipv4.iplen = flowlet.bytes / flowlet.pkts

    etherhdr.payload = ipv4

    if ident.ipproto == IPPROTO_ICMP:
        layer4 = pktlib.icmp()
        layer4.type = ident.dport >> 8
        layer4.code = ident.dport & 0x00FF
    elif ident.ipproto == IPPROTO_UDP:
        layer4 = pktlib.udp()
        layer4.srcport = ident.sport 
        layer4.dstport = ident.dport 
    elif ident.ipproto == IPPROTO_TCP:
        layer4 = pktlib.tcp()
        layer4.srcport = ident.sport 
        layer4.dstport = ident.dport 
        layer4.flags = flowlet.tcpflags
    else:
        raise UnhandledPoxPacketFlowletTranslation("Can't translate IP protocol {} from flowlet to POX packet".format(fident.ipproto))
    ipv4.payload = layer4
    layer4.payload = str(flowlet)
    etherhdr.origflet = flowlet
    return etherhdr

def packet_to_flowlet(pkt):
    try:
        return getattr(pkt, "origflet")
    except AttributeError,e:
        raise UnhandledPoxPacketFlowletTranslation("No cached flowlet found in pkt out.")

class PoxBridgeSoftwareSwitch(SoftwareSwitch):
    def _output_packet_physical(self, packet, port_num):
        self.forward(packet, port_num)
        SoftwareSwitch._output_packet_physical(self, packet, port_num)

    def set_output_packet_callback(self, fn):
        self.forward = fn

class OpenflowSwitch(Node):
    __slots__ = ['dpid', 'pox_switch', 'controller_name', 'controller_links', 'ipdests']

    def __init__(self, name, measurement_config, **kwargs):
        Node.__init__(self, name, measurement_config, **kwargs)
        self.dpid = abs(hash(name))
        self.pox_switch = PoxBridgeSoftwareSwitch(self.dpid, name=name, 
            ports=0, miss_send_len=2**16, max_buffers=2**8, features=None)
        self.pox_switch.set_connection(self)
        self.pox_switch.set_output_packet_callback(self. send_packet)
        self.controller_name = kwargs['controller']
        self.controller_links = {}

        self.ipdests = PyTricia()
        for prefix in kwargs.get('ipdests','').split():
            self.ipdests[prefix] = True

        # explicitly add a localhost link
        self.interfaces[1] = (None, '127.0.0.1', '127.0.0.1', None)
        self.arp_table_ip['host'] = ("00:00:00:00:{:02x}:01".format(self.dpid % 255), 1, '127.0.0.1', None, None)
        self.pox_switch.add_port(1)

    def send_packet(self, packet, port_num):
        '''Forward a data plane packet out a given port'''
        flet = packet_to_flowlet(packet)
        nhinfo = self.interfaces[port_num]
        nhinfo[0].flowlet_arrival(flet, self.name, nhinfo[3])

    def send(self, ofmessage):
        '''Callback function for POX SoftwareSwitch to send an outgoing OF message
        to controller.'''
        if not self.started:
            self.logger.debug("OF switch-to-controller deferred message {}".format(ofmessage))
            evid = 'deferred switch->controller send'
            fscore().after(0.0, evid, self.send, ofmessage)
        else:
            self.logger.debug("OF switch-to-controller {} - {}".format(str(self.controller_links[self.controller_name]), ofmessage))
            clink = self.controller_links[self.controller_name]
            self.controller_links[self.controller_name].flowlet_arrival(OpenflowMessage(FlowIdent(), ofmessage), self.name, self.controller_name)

    def set_message_handler(self, *args):
        '''Dummy callback function for POX SoftwareSwitchBase'''
        pass

    def flowlet_arrival(self, flowlet, prevnode, destnode, input_ip):
        '''Incoming flowlet: determine whether it's a data plane flowlet or whether it's an OF message
        coming back from the controller'''
        if isinstance(flowlet, OpenflowMessage):
            self.pox_switch.rx_message(self, flowlet.ofmsg)
        elif isinstance(flowlet, Flowlet):
            self.measure_flow(flowlet, prevnode, input_ip)
            # assume this is an incoming flowlet on the dataplane.  
            # reformat it and inject it into the POX switch
            # self.pox_switch.rx_packet(self, packet, in_port)
            self.logger.debug("Flowlet arrival in OF switch {} {} {} {}".format(flowlet.dstaddr, prevnode, destnode, input_ip))
            if self.ipdests.get(flowlet.dstaddr, None):
                # FIXME: autoack
                pass
            else:                
                input_port = self.arp_table_ip[input_ip][1]
                pkt = flowlet_to_packet(flowlet)
                pkt.flowlet = flowlet
                self.pox_switch.rx_packet(pkt, input_port)
        else:
            raise UnhandledPoxPacketFlowletTranslation("Unexpected message in OF switch: {}".format(type(flowlet)))

    def add_link(self, link, hostip, remoteip, next_node):
        if next_node == self.controller_name:
            self.logger.debug("Adding link to {}: {}".format(self.name, link))
            self.controller_links[self.controller_name] = link
        else:
            portnum = len(self.interfaces) + 1
            self.interfaces[portnum] = (link, hostip, remoteip, next_node)
            self.pox_switch.add_port(portnum)
            hwaddr = "00:00:00:00:%02x:%02x" % (self.dpid % 255, portnum)
            self.arp_table_node[next_node].append( (hwaddr, portnum, hostip, remoteip, link) )
            self.arp_table_ip[remoteip] = (hwaddr, portnum, hostip, next_node, link)
            self.logger.debug("New port in OF switch {}: port:{} hwaddr:{} hostip:{} next:{}".format(self.name, portnum, hwaddr, hostip, next_node))


class OpenflowController(Node):
    __slots__ = ['components', 'switch_links']

    def __init__(self, name, measurement_config, **kwargs):
        Node.__init__(self, name, measurement_config, **kwargs)
        self.components = kwargs.get('components','').split()
        self.switch_links = {}

    def flowlet_arrival(self, flowlet, prevnode, destnode, input_port):
        '''Handle switch-to-controller incoming messages'''
        # assumption: flowlet is an OpenflowMessage
        assert(isinstance(flowlet,OpenflowMessage))
        self.switch_links[prevnode][0].simrecv(flowlet.ofmsg) 

    def add_link(self, link, hostip, remoteip, next_node):
        '''don't do much except create queue of switch connections so that we can
        eventually build ofcore.Connection objects for each one
        once start() gets called.'''
        xconn = ofcore.Connection(-1, self.controller_to_switch, next_node, link.egress_node.dpid)
        self.switch_links[next_node] = (xconn, link)

    def controller_to_switch(self, switchname, mesg):
        '''Ferry an OF message from controller to switch'''
        if not self.started:
            self.logger.debug("OF controller-to-switch deferred message {}".format(mesg))
            evid = 'deferred controller->switch send'
            fscore().after(0, evid, self.controller_to_switch, switchname, mesg)
        else:
            self.logger.debug("OF controller-to-switch {}->{}: {}".format(self.name, switchname, mesg))
            link = self.switch_links[switchname][1]
            link.flowlet_arrival(OpenflowMessage(FlowIdent(), mesg), self.name, switchname)
       
    def start(self):
        '''Load POX controller components'''
        Node.start(self)
        for component in self.components:
            self.logger.debug("Starting OF Controller Component {}".format(component))
            load_pox_component(component)
