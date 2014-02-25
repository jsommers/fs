from trafgen import TrafficGenerator
from fslib.flowlet import SubtractiveFlowlet,FlowIdent
from fslib.common import fscore
from fslib.util import *

class SubtractiveTrafficGenerator(TrafficGenerator):
    def __init__(self, srcnode, dstnode=None, action=None, ipdstfilt=None,
                 ipsrcfilt=None, ipprotofilt=None):
        TrafficGenerator.__init__(self, srcnode)
        self.dstnode = dstnode
        self.logger.debug('subtractive: %s %s %s %s %s %s' % (srcnode,dstnode,action,ipdstfilt, ipsrcfilt, ipprotofilt))

        self.ipdstfilt = self.ipsrcfilt = ''
        self.ipprotofilt = 0

        assert(action)
        self.action = eval(action)

        if ipdstfilt:
            self.ipdstfilt = ipaddr.IPNetwork(ipdstfilt)

        if ipsrcfilt:
            self.ipsrcfilt = ipaddr.IPNetwork(ipsrcfilt)

        if ipprotofilt:
            self.ipprotofilt = int(ipprotofilt)


    def start(self):
        fscore().after(0.0, 'subtractive-gen-callback', self.callback)

    def callback(self):
        # pass oneself from srcnode to dstnode, performing action at each router
        # at end, set done to True
        f = SubtractiveFlowlet(FlowIdent(self.ipsrcfilt, self.ipdstfilt, ipproto=self.ipprotofilt), action=self.action)
        self.logger.info('Subtractive generator callback')
        fscore().topology.node(self.srcnode).flowlet_arrival(f, 'subtractor', self.dstnode)
