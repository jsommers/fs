import unittest
from mock import Mock

#from fslib.flowlet import FlowIdent, Flowlet, SubtractiveFlowlet, OpenflowMessage, ofp_match_from_flowlet
#from pox.openflow.flow_table import SwitchFlowTable, TableEntry
#import pox.openflow.libopenflow_01 as poxof
#from node import *
#import ipaddr
#import time
#import copy

class TestOfSwitch(unittest.TestCase):
    def setUp(self):
        self.mocksim = Mock()
        self.mocksim.now = 0
        self.mconfig = Mock()
        self.mocknode = Mock()
        self.mocklink = Mock()
        self.switch = OpenflowSwitch("test",self.mocksim,True,self.mconfig)
        self.linkobj = Mock()
        self.linkobj.flowlet_arrival = Mock()
        self.switch.link_table = {'next': self.linkobj}

    def testFlowletArrNoTableEntry(self):
        flowlet = Flowlet(FlowIdent())
        self.switch.match_table = Mock(return_value=None)
        controller_link = Mock()
        self.switch.link_table['controller'] = controller_link
        controller_link.flowlet_arrival = Mock(return_value=None)
        self.mocksim.now = 1
        self.assertEqual(self.switch.flowlet_arrival(flowlet, "prev","next"),"controller")
        self.switch.match_table.assert_called_with(flowlet,"prev")

    def testFlowletArrHasTableEntry(self):
        flowlet = Flowlet(FlowIdent())
        self.switch.match_table = Mock(return_value="next")
        self.mocksim.now = 1
        self.assertEqual(self.switch.flowlet_arrival(flowlet, "prev","next"), "next")
        self.switch.match_table.assert_called_with(flowlet, "prev")
        self.linkobj.flowlet_arrival.assert_called_with(flowlet, "test", "next")

    def testMatchTableNoMatch(self):
        flowlet = Flowlet(FlowIdent())
        self.assertIsNone(self.switch.match_table(flowlet, "prev"))

    def testMatchTableOneExactMatch(self):
        flowlet = Flowlet(FlowIdent(srcip='1.1.1.1',dstip='2.2.2.2',ipproto=6,sport=20000,dport=80,srcmac='00:00:00:00:00:01',dstmac='00:00:00:00:00:02',vlan=1))
        new_rule = ofp_match_from_flowlet(flowlet)
        queuer = poxof.ofp_action_enqueue()
        queuer.port = "next"
        self.switch.flow_table.add_entry(TableEntry(match=new_rule,now=self.mocksim.now, actions=[queuer]))
        rv = self.switch.match_table(flowlet, "prev")
        self.assertEqual(rv, "next")

    def testMatcher(self):
        flowlet = Flowlet(FlowIdent(srcip='1.1.1.1',dstip='2.2.2.2',ipproto=6,sport=20000,dport=80,srcmac='00:00:00:00:00:01',dstmac='00:00:00:00:00:02',vlan=1))
        match_obj = poxof.ofp_match()
        match_obj.dl_src = flowlet.srcmac
        match_obj.dl_dst = flowlet.dstmac
        match_obj.dl_vlan = flowlet.vlan
        match_obj.nw_src = flowlet.srcaddr
        match_obj.nw_dst = flowlet.dstaddr
        match_obj.nw_proto = flowlet.ipproto
        match_obj.tp_src = flowlet.srcport
        match_obj.tp_dst = flowlet.dstport

        matcher = ofp_match_from_flowlet(flowlet, ports=True)
        self.assertTrue(match_obj == matcher)

        match_obj = poxof.ofp_match()
        # match_obj.dl_src = flowlet.srcmac
        # match_obj.dl_dst = flowlet.dstmac
        match_obj.dl_vlan = flowlet.vlan
        match_obj.nw_src = flowlet.srcaddr
        match_obj.nw_dst = flowlet.dstaddr
        match_obj.nw_proto = flowlet.ipproto
        # match_obj.tp_src = flowlet.srcport
        match_obj.tp_dst = flowlet.dstport
        self.assertFalse(match_obj == matcher)
        self.assertTrue(match_obj.matches_with_wildcards(matcher))

        flowlet = Flowlet(FlowIdent(ipproto=6))
        matcher = ofp_match_from_flowlet(flowlet)
        match_obj = poxof.ofp_match()
        self.assertTrue(match_obj.matches_with_wildcards(matcher))
        match_obj.nw_proto = 17
        self.assertFalse(match_obj.matches_with_wildcards(matcher))

    def testMatchTableOneWildcardMatch(self):
        flowlet = Flowlet(FlowIdent(srcip='1.1.1.1',dstip='2.2.2.2',ipproto=6,sport=20000,dport=80,srcmac='00:00:00:00:00:01',dstmac='00:00:00:00:00:02',vlan=1))
        # new_rule = self.switch.flow_table.matcher_from_flowlet(flowlet)
        new_rule = ofp_match() # as wildcardish as it gets
        queuer = poxof.ofp_action_enqueue()
        queuer.port = "next"
        self.switch.flow_table.add_entry(TableEntry(match=new_rule,now=self.mocksim.now, actions=[queuer]))
        rv = self.switch.match_table(flowlet, "prev")
        self.assertEqual(rv, "next")

    def testUpdateTable(self):
        flet = Flowlet(FlowIdent(srcip='1.1.1.1',dstip='2.2.2.2',ipproto=6,sport=20000,dport=80,srcmac='00:00:00:00:00:01',dstmac='00:00:00:00:00:02',vlan=1))
        actions = {}
        actions['port'] = 'fakeport'
        match = ofp_match_from_flowlet(flet)
        ofm = OpenflowMessage(flet.flowident, message_type = 'ofp_flow_mod', \
                                          match = match, action = actions, match_dl_src = None, \
                                          command = "add") 
        self.assertEqual(ofm.message_type, "ofp_flow_mod")
        self.assertTrue(isinstance(ofm.message.pox_ofp_message,poxof.ofp_flow_mod))
        rv = self.switch.update_table(ofm)
        self.assertEqual(rv[0],'added')
        self.assertEqual(len(self.switch.flow_table.entries), 1)
        self.assertEqual(self.switch.flow_table.entries[0].match, match)
        print self.switch.flow_table.entries[0]
        print "Matching entries for port: ",self.switch.flow_table.entries_for_port('fakeport')
        self.assertIsNotNone(self.switch.flow_table.entries_for_port('fakeport')) ##

    def testEvictTableEntry(self):
        self.mocksim.now = 2
        flet = Flowlet(FlowIdent(srcip='1.1.1.1',dstip='2.2.2.2',ipproto=6,sport=20000,dport=80,srcmac='00:00:00:00:00:01',dstmac='00:00:00:00:00:02',vlan=1))
        actions = {}
        actions['port'] = 'fakeport'
        match = ofp_match_from_flowlet(flet)
        ofm = OpenflowMessage(flet.flowident, message_type = 'ofp_flow_mod', \
                                          match = match, action = actions, match_dl_src = None, \
                                          command = "add", idle_timeout=0.5) 
        self.assertEqual(ofm.message_type, "ofp_flow_mod")
        self.assertTrue(isinstance(ofm.message.pox_ofp_message,poxof.ofp_flow_mod))
        rv = self.switch.update_table(ofm)
        self.assertEqual(rv[0],'added')
        self.assertEqual(len(self.switch.flow_table.entries), 1)
        self.assertEqual(self.switch.flow_table.entries[0].match, match)
        self.switch.flow_table.entries[0].counters['created'] = 1
        self.switch.flow_table.entries[0].counters['last_touched'] = 1

        self.linkobj = Mock()
        self.linkobj.flowlet_arrival = Mock()
        self.switch.link_table = {'controller': self.linkobj}
        print self.switch.flow_table.entries[0]
        self.assertEqual(self.switch.table_ager(),1)
        self.linkobj.flowlet_arrival.assert_called_once()

if __name__ == '__main__':
    # unittest.main()
    raise Exception("Test cases out of date.")
