from trafgen import TrafficGenerator
from fslib.util import *
from ipaddr import IPAddress, IPNetwork
from socket import IPPROTO_UDP, IPPROTO_TCP, IPPROTO_ICMP
from fslib.flowlet import Flowlet, FlowIdent
from fslib.common import fscore
import copy
import re


# FIXME
haveIPAddrGen = False

class SimpleTrafficGenerator(TrafficGenerator):

    def __init__(self, srcnode, ipsrc=None, ipdst=None, ipproto=None,
                 dport=None, sport=None, continuous=True, flowlets=None, tcpflags=None, iptos=None,
                 fps=None, pps=None, bps=None, pkts=None, bytes=None, pktsize=None, 
                 icmptype=None, icmpcode=None, interval=None, autoack=False):
        TrafficGenerator.__init__(self, srcnode)
        # assume that all keyword params arrive as strings
        # print ipsrc,ipdst
        self.ipsrc = IPNetwork(ipsrc)
        self.ipdst = IPNetwork(ipdst)
        if haveIPAddrGen:
            self.ipsrcgen = ipaddrgen.initialize_trie(int(self.ipsrc), self.ipsrc.prefixlen, 0.61)
            self.ipdstgen = ipaddrgen.initialize_trie(int(self.ipdst), self.ipdst.prefixlen, 0.61)


        self.sport = self.dport = None
        self.icmptype = self.icmpcode = None
        self.autoack = False
        if autoack and isinstance(autoack, (str,unicode)):
            self.autoack = eval(autoack)
        else:
            self.autoack = autoack

        try:
            self.ipproto = int(ipproto)
        except:
            if ipproto == 'tcp':
                self.ipproto = IPPROTO_TCP
            elif ipproto == 'udp':
                self.ipproto = IPPROTO_UDP
            elif ipproto == 'icmp':
                self.ipproto = IPPROTO_ICMP
            else:
                raise InvalidFlowConfiguration('Unrecognized protocol:'+str(ipproto))

        if not iptos:
            self.iptos = randomchoice(0x0)
        else:
            if isinstance(iptos, int):
                self.iptos = randomchoice(self.iptos)
            elif isinstance(iptos, (str,unicode)):
                self.iptos = eval(iptos)
   
        if self.ipproto == IPPROTO_ICMP:
            xicmptype = xicmpcode = 0
            if icmptype:
                xicmptype = eval(icmptype)
            if icmpcode:
                xicmpcode = eval(icmpcode)
            if isinstance(xicmptype, int):
                xicmptype = randomchoice(xicmptype)
            if isinstance(xicmpcode, int):
                xicmpcode = randomchoice(xicmpcode)
            self.icmptype = xicmptype
            self.icmpcode = xicmpcode
        elif self.ipproto == IPPROTO_UDP or self.ipproto == IPPROTO_TCP:
            self.dport = eval(dport)
            if isinstance(self.dport, int):
                self.dport = randomchoice(self.dport)
            self.sport = eval(sport)
            if isinstance(self.sport, int):
                self.sport = randomchoice(self.sport)
            # print 'sport,dport',self.sport, self.dport
            if self.ipproto == IPPROTO_TCP:
                self.tcpflags = randomchoice('')
                if tcpflags:
                    if re.search('\(\S+\)', tcpflags):
                        self.tcpflags = eval(tcpflags)
                    else:
                        self.tcpflags = randomchoice(tcpflags)
        else:
            self.dport = self.sport = 0

        self.continuous = None
        self.nflowlets = None
        if continuous:
            if isinstance(continuous, (str,unicode)):
                self.continuous = eval(continuous)
            else:
                self.continuous = continuous

        if flowlets:
            self.nflowlets = eval(flowlets)
            if isinstance(self.nflowlets, (int, float)):
                self.nflowlets = randomchoice(self.nflowlets)

        if not self.nflowlets:
            self.nflowlets = randomchoice(1)
                

        if not fps and not interval:
            raise InvalidFlowConfiguration('Need one of fps or interval in rawflow configuration.')

        self.fps = self.interval = None
        if fps:
            fps = eval(fps)
            if isinstance(fps, int):
                fps = randomchoice(fps)
            self.fps = fps
        elif interval:
            self.interval = eval(interval)
            if isinstance(self.interval, (int, float)):
                self.interval = randomchoice(self.interval)

        assert(bytes)
        self.bytes = eval(bytes)
        if isinstance(self.bytes, int):
            self.bytes = randomchoice(self.bytes)

        self.pkts = self.pktsize = None

        if pkts:
            self.pkts = eval(pkts)
            if isinstance(self.pkts, int):
                self.pkts = randomchoice(self.pkts)

        if pktsize:
            self.pktsize = eval(pktsize)
            if isinstance(self.pktsize, int):
                self.pktsize = randomchoice(self.pktsize)

        assert(self.fps or self.interval)
        assert(self.pkts or self.pktsize)


    def __makeflow(self):
        if haveIPAddrGen:
            srcip = str(IPv4Address(ipaddrgen.generate_addressv4(self.ipsrcgen)))
            dstip = str(IPv4Address(ipaddrgen.generate_addressv4(self.ipdstgen)))
        else:
            srcip = str(IPAddress(int(self.ipsrc) + random.randint(0,self.ipsrc.numhosts-1)))
            dstip = str(IPAddress(int(self.ipdst) + random.randint(0,self.ipdst.numhosts-1)))

        ipproto = self.ipproto
        sport = dport = 0
        if ipproto == IPPROTO_ICMP:
            # std way that netflow encodes icmp type/code:
            # type in high-order byte of dport, 
            # code in low-order byte
            t = next(self.icmptype)
            c = next(self.icmpcode)
            dport = t << 8 | c
            # print 'icmp t,c,dport',hex(t),hex(c),hex(dport)
        else:
            if self.sport:
                sport = next(self.sport)
            if self.dport:
                dport = next(self.dport)
                
        flet = Flowlet(FlowIdent(srcip, dstip, ipproto, sport, dport))
        flet.iptos = next(self.iptos)
        flet.flowstart = flet.flowend = fscore().now

        if flet.ipproto == IPPROTO_TCP:
            flet.ackflow = not self.autoack

            tcpflags = next(self.tcpflags)
            flaglist = tcpflags.split('|')
            xtcpflags = 0x0
            for f in flaglist:
                if f == 'FIN':
                    xtcpflags |= 0x01
                elif f == 'SYN':
                    xtcpflags |= 0x02
                elif f == 'RST':
                    xtcpflags |= 0x04
                elif f == 'PUSH' or f == 'PSH':
                    xtcpflags |= 0x08
                elif f == 'ACK':
                    xtcpflags |= 0x10
                elif f == 'URG':
                    xtcpflags |= 0x20
                elif f == 'ECE':
                    xtcpflags |= 0x40
                elif f == 'CWR':
                    xtcpflags |= 0x80
                else:
                    raise InvalidFlowConfiguration('Invalid TCP flags mnemonic ' + f)

            flet.tcpflags = xtcpflags
        return flet


    def flowemit(self, flowlet, destnode, xinterval, ticks):
        assert(xinterval > 0.0)
        f = copy.copy(flowlet)
        f.bytes = next(self.bytes)
        if self.pktsize:
            psize = next(self.pktsize)
            f.pkts = f.bytes / psize
            if f.bytes % psize > 0:
                f.pkts += 1
        else:
            f.pkts = next(self.pkts)

        fscore().topology.node(self.srcnode).flowlet_arrival(f, 'simple', destnode)

        ticks -= 1
        fscore().after(xinterval, 'rawflow-flowemit-'+str(self.srcnode), self.flowemit, flowlet, destnode, xinterval, ticks)

    def start(self):
        self.callback()
        
    def callback(self):
        f = self.__makeflow()
        f.bytes = next(self.bytes)
        if self.pktsize:
            psize = next(self.pktsize)
            f.pkts = f.bytes / psize
            if f.bytes % psize > 0:
                f.pkts += 1
        else:
            f.pkts = next(self.pkts)


        destnode = fscore().topology.destnode(self.srcnode, f.dstaddr)

        # print 'rawflow:',f
        # print 'destnode:',destnode

        xinterval = None
        if self.interval:
            xinterval = next(self.interval)
            xinterval = max(0, xinterval)
        else:
            fps = next(self.fps)
            xinterval = 1.0/fps

        ticks = None
        if not self.continuous:
            ticks = next(self.nflowlets)
        else:
            if self.nflowlets:
                ticks = next(self.nflowlets)
            else:
                ticks = 1

        # print 'ticks',ticks
        # print 'xinterval',xinterval

        if not ticks or ticks == 1:
            fscore().topology.node(self.srcnode).flowlet_arrival(f, 'simple', destnode)
        else:
            fscore().after(0, "rawflow-flowemit-{}".format(self.srcnode), self.flowemit, f, destnode, xinterval, ticks)
      
        if self.continuous and not self.done:
            fscore().after(xinterval, "rawflow-cb-".format(self.srcnode), self.callback)
        else:
            self.done = True


# rawflow -> alias for simple
RawflowTrafficGenerator = SimpleTrafficGenerator

