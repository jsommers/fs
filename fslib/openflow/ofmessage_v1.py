from pox.openflow.libopenflow_01 import ofp_match
import pox.openflow.libopenflow_01 as of
from fslib.flowlet import Flowlet, FlowIdent

# Wrapper Class around POX for openflow messages
class ofp_pox_messages:
    __slots__ = ['pox_ofp_message']

    def __init__(self, message_type, **kargs):
        if message_type == 'ofp_packet_out':
            self.pox_ofp_message = of.ofp_packet_out()
            if 'action' in kargs:
                if kargs['action'] == 'flood':
                    self.pox_ofp_message.actions.append(of.ofp_action_output(port = of.OFPP_FLOOD))
                elif kargs['action'] == 'ofpp_all':
                    self.pox_ofp_message.actions.append(of.ofp_action_output(port = of.OFPP_ALL))

        elif message_type == 'ofp_flow_mod':
            if 'match' in kargs:
                if 'command' in kargs:
                    if kargs['command'] == 'add':
                        self.pox_ofp_message = of.ofp_flow_mod(command=of.OFPFC_ADD, \
                                                                   match=kargs['match'])
                else:
                    self.pox_ofp_message = of.ofp_flow_mod(match=kargs['match'])
            else:
                self.pox_ofp_message = of.ofp_flow_mod()
            if 'match_dl_dst' in kargs:
                self.pox_ofp_message.match.dl_dst = kargs['match_dl_dst']
            if 'match_dl_src' in kargs:
                self.pox_ofp_message.match.dl_src = kargs['match_dl_src']
            if 'idle_timeout' in kargs:
                self.pox_ofp_message.idle_timeout = kargs['idle_timeout']
            if 'hard_timeout' in kargs:
                self.pox_ofp_message.hard_timeout = kargs['hard_timeout']
            if 'action' in kargs:
                if kargs['action'] == 'flood':
                    self.pox_ofp_message.actions.append(of.ofp_action_output(port = of.OFPP_FLOOD))
                elif isinstance(kargs['action'], dict):
                    if 'dstmac' in kargs['action'].keys():
                        self.pox_ofp_message.actions.append(of.ofp_action_dl_addr.set_dst(\
                                kargs['action']['dstmac']))
                    if 'port' in kargs['action'].keys():
                        self.pox_ofp_message.actions.append(of.ofp_action_output(port = kargs['action']['port']))
                else:
                    self.pox_ofp_message.actions.append(of.ofp_action_output(port = kargs['action']))
            
        elif message_type == 'ofp_packet_in':
            self.pox_ofp_message = of.ofp_packet_in()
            if 'reason' in kargs:
                self.pox_ofp_message.reason = kargs['reason']
            if 'in_port' in kargs:
                self.pox_ofp_message.in_port = kargs['in_port']

        elif message_type == 'ofp_flow_removed':
            self.pox_ofp_message = of.ofp_flow_removed()
            if 'match' in kargs:
                self.pox_ofp_message.match = kargs['match']
            if 'cookie' in kargs:
                self.pox_ofp_message.cookie = kargs['cookie']
            if 'priority' in kargs:
                self.pox_ofp_message.priority = kargs['priority']
            if 'reason' in kargs:
                self.pox_ofp_message.reason = kargs['reason']
            if 'duration_sec' in kargs:
                self.pox_ofp_message.suration_sec = kargs['duration_sec']
            if 'duration_nsec' in kargs:
                self.pox_ofp_message.duration_nsec = kargs['duration_nsec']
            if 'packet_count' in kargs:
                self.pox_ofp_message.packet_count = kargs['packet_count']
            if 'byte_count' in kargs:
                self.pox_ofp_message.byte_count = kargs['byte_count']

class OpenflowMessage(Flowlet):
    __slots__ = ['context', 'message', 'message_type', 'data', 'actions']

    def __init__(self, flowid, message_type, **kargs):
        Flowlet.__init__(self, flowid)
        # Creating class object of the message_type
        self.message = ofp_pox_messages(message_type, **kargs) # e.g., ofp_packet_out, ofp_flow_mod, 
        self.message_type = message_type
        self.data = None
        self.context = (None,None,None)

    def set_context(self, origin, destination, previous):
        self.context = (origin, destination, previous)

    def get_context(self):
        return self.context
    
    @property
    def in_port(self):
        if (self.message_type == 'ofp_packet_in'):
            return self.message.pox_ofp_message.in_port

    @property
    def actions(self):
        if (self.message_type == 'ofp_packet_out'):
            return self.message.pox_ofp_message.actions

    def __str__(self):
        return "--".join([Flowlet.__str__(self), self.message_type])

# Added by Joel
# class OpenflowMessage(Flowlet):
#     __slots__ = ['message','data']

#     def __init__(self, flowid, message):
#         Flowlet.__init__(self, flowid)
#         self.message = message # e.g., object types ofp_packet_out, ofp_flow_mod
#         self.data = None       # e.g., an attached data flowlet to go along with OF
#                                # control message


def ofp_match_from_flowlet(flowlet, ports=False):
    m = ofp_match()
    m.dl_src = flowlet.srcmac
    m.dl_dst = flowlet.dstmac
    m.dl_vlan = flowlet.vlan
    m.nw_src = flowlet.srcaddr
    m.nw_dst = flowlet.dstaddr
    m.nw_proto = flowlet.ipproto
    if ports:
        m.tp_src = flowlet.srcport
        m.tp_dst = flowlet.dstport
    return m 
    

def flowident_from_ofp_match(m):
    return FlowIdent(srcip=m.nw_src, dstip=m.nw_dst, ipproto=m.nw_proto, sport=m.tp_src, dport=m.tp_dst, srcmac=m.dl_src, dstmac=m.dl_dst, vlan=m.dl_vlan)
  
