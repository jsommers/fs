#!/usr/bin/env python

__author__ = 'jsommers@colgate.edu'

from flowlet import *
from fsutil import *
import ipaddr
import math
import copy
import sys
import socket
import re
import logging
import random
from fscommon import *
from pox.lib.addresses import EthAddr 

haveIPAddrGen = False
try:
    import ipaddrgen
    haveIPAddrGen = True
except:
    pass

def get_mac_addr(ipAddr):
    mac = ''
    num = 0
    for i in range(len(ipAddr)):
        if ipAddr[i].isdigit():
            num += 1
            mac += ipAddr[i]
            if num % 2 == 0:
                mac += ':'
    while num < 12:
        mac += '0'
        num += 1
        if num != 12 and num % 2 == 0:
            mac += ':'
    mac = ''.join(reversed(mac))
    return mac

class TrafficGenerator(object):
    def __init__(self, srcnode):
        self.srcnode = srcnode
        self.done = False
        self.logger = get_logger()
        
    def start(self):
        fscore().after(0.0, 'gencallback', self.callback)

    def get_done(self):
        return self.__done

    def set_done(self, tf):
        self.__done = tf

    done = property(get_done, set_done, None, 'done flag')

    def stop(self):
        self.done = True


class InvalidFlowConfiguration(Exception):
    pass


class SimpleTrafficGenerator(TrafficGenerator):
    def __init__(self, srcnode, ipsrc=None, ipdst=None, ipproto=None,
                 dport=None, sport=None, continuous=True, flowlets=None, tcpflags=None, iptos=None,
                 fps=None, pps=None, bps=None, pkts=None, bytes=None, pktsize=None, 
                 icmptype=None, icmpcode=None, interval=None, autoack=False):
        TrafficGenerator.__init__(self, srcnode)
        # assume that all keyword params arrive as strings
        # print ipsrc,ipdst
        self.ipsrc = ipaddr.IPNetwork(ipsrc)
        self.ipdst = ipaddr.IPNetwork(ipdst)
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
                self.ipproto = socket.IPPROTO_TCP
            elif ipproto == 'udp':
                self.ipproto = socket.IPPROTO_UDP
            elif ipproto == 'icmp':
                self.ipproto = socket.IPPROTO_ICMP
            else:
                raise InvalidFlowConfiguration('Unrecognized protocol:'+str(ipproto))

        if not iptos:
            self.iptos = randomchoice(0x0)
        else:
            if isinstance(iptos, int):
                self.iptos = randomchoice(self.iptos)
            elif isinstance(iptos, (str,unicode)):
                self.iptos = eval(iptos)
   
        if self.ipproto == socket.IPPROTO_ICMP:
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
        elif self.ipproto == socket.IPPROTO_UDP or self.ipproto == socket.IPPROTO_TCP:
            self.dport = eval(dport)
            if isinstance(self.dport, int):
                self.dport = randomchoice(self.dport)
            self.sport = eval(sport)
            if isinstance(self.sport, int):
                self.sport = randomchoice(self.sport)
            # print 'sport,dport',self.sport, self.dport
            if self.ipproto == socket.IPPROTO_TCP:
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
            srcip = str(ipaddr.IPv4Address(ipaddrgen.generate_addressv4(self.ipsrcgen)))
            dstip = str(ipaddr.IPv4Address(ipaddrgen.generate_addressv4(self.ipdstgen)))
        else:
            srcip = str(ipaddr.IPAddress(int(self.ipsrc) + random.randint(0,self.ipsrc.numhosts-1)))
            dstip = str(ipaddr.IPAddress(int(self.ipdst) + random.randint(0,self.ipdst.numhosts-1)))

        ipproto = self.ipproto
        sport = dport = 0
        if ipproto == socket.IPPROTO_ICMP:
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
                
        # Creating src and dst mac addresses
        srcmac = get_mac_addr(srcip)
        dstmac = get_mac_addr(dstip)

        flet = Flowlet(FlowIdent(srcip, dstip, ipproto, sport, dport, srcmac, dstmac))
        flet.iptos = next(self.iptos)

        if flet.ipproto == socket.IPPROTO_TCP:
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

        fscore().node(self.srcnode).flowlet_arrival(f, 'rawgen', destnode)
        ticks -= 1
        fscore().after(xinterval, 'rawflow-flowemit-'+str(self.srcnode), self.flowemit, flowlet, destnode, xinterval, ticks)

       
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


        destnode = fscore().destnode(self.srcnode, f.dstaddr)

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
            fscore().node(self.srcnode).flowlet_arrival(f, 'rawgen', destnode)
        else:
            fscore().after(0, 'rawflow-flowemit-'+str(self.srcnode), self.flowemit, f, destnode, xinterval, ticks)
      
        if self.continuous and not self.done:
            fscore().after(xinterval, 'rawflow-cb-'+str(self.srcnode), self.callback)
        else:
            self.done = True



class HarpoonTrafficGenerator(TrafficGenerator):
    def __init__(self, srcnode, ipsrc='0.0.0.0', ipdst='0.0.0.0', sport=0, dport=0, flowsize=1500, pktsize=1500, flowstart=0, ipproto=socket.IPPROTO_TCP, lossrate=0.001, mss=1460, emitprocess='randomchoice(x)', iptos=0x0, xopen=True, tcpmodel='csa00'):
        TrafficGenerator.__init__(self, srcnode)
        self.srcnet = ipaddr.IPNetwork(ipsrc)
        self.dstnet = ipaddr.IPNetwork(ipdst)
        if haveIPAddrGen:
            self.ipsrcgen = ipaddrgen.initialize_trie(int(self.srcnet), self.srcnet.prefixlen, 0.61)
            self.ipdstgen = ipaddrgen.initialize_trie(int(self.dstnet), self.dstnet.prefixlen, 0.61)

        if isinstance(ipproto, (str,unicode)):
            self.ipproto = eval(ipproto)
        else: 
            self.ipproto = randomchoice(ipproto)

        if isinstance(sport, (str,unicode)):
            self.srcports = eval(sport)
        else:
            self.srcports = randomchoice(sport)

        if isinstance(dport, (str,unicode)):
            self.dstports = eval(dport)
        else:
            self.dstports = randomchoice(dport)

        if isinstance(flowsize, (str,unicode)):
            self.flowsizerv = eval(flowsize)
        else:
            self.flowsizerv = randomchoice(flowsize)

        if isinstance(pktsize, (str,unicode)):
            self.pktsizerv = eval(pktsize)
        else:
            self.pktsizerv = randomchoice(pktsize)

        if isinstance(flowstart, (str,unicode)):
            self.flowstartrv = eval(flowstart)
        else:
            self.flowstartrv = randomchoice(flowstart)

        if isinstance(lossrate, (str,unicode)):
            self.lossraterv = eval(lossrate)
        else:
            self.lossraterv = randomchoice(lossrate)

        if isinstance(mss, (str,unicode)):
            self.mssrv = eval(mss)
        else:
            self.mssrv = randomchoice(mss)

        if isinstance(iptos, (str,unicode)):
            self.iptosrv = eval(iptos)
        else:
            self.iptosrv = randomchoice(iptos)

        self.emitrvstr = emitprocess

        self.xopen = xopen
        self.activeflows = {}
        self.tcpmodel = tcpmodel
        if self.tcpmodel not in ['mathis','msmo97','csa00']:
            raise InvalidFlowConfiguration('Unrecognized tcp model for harpoon:'+str(tcpmodel))


    def start(self):
        startt = next(self.flowstartrv)
        # print >>sys.stderr, 'harpoon node starting up at',startt
        fscore().after(startt, 'harpoon-start'+str(self.srcnode), self.newflow)


    def newflow(self, test=False, xint=1.0):
        if self.done:
            print 'harpoon generator done'
            return

        # print >>sys.stderr, 'making new harpoon flow at',fscore().now

        flet = self.__makeflow()
        self.activeflows[flet.key] = 1

        destnode = 'test'
        owd = random.random()*0.05
        if not test:
            destnode = fscore().topology.destnode(self.srcnode, flet.dstaddr)
            owd = fscore().topology.owd(self.srcnode, destnode)

        # owd may be None if routing is temporarily broken because of
        # a link being down and no reachability
        if not owd:
            owd = 1.0 

        flet.mss = next(self.mssrv)
        p = next(self.lossraterv)
        basertt = owd * 2.0
        flowduration = 0.0


        if self.tcpmodel == 'mathis' or self.tcpmodel == 'msmo97':
            # mathis model constant C
            C = math.sqrt(3.0/2)
            # C = math.sqrt(3.0/4) - delack
            # C = 1.31
            # C = 0.93
            bw = flet.mss / basertt * C/math.sqrt(p)

            if test:
                print 'mathis bw,loss,owd,mss',bw,p,owd,flet.mss

            # how many intervals will this flowlet last?
            flowduration = flet.size / bw
            if test:
                nintervals = math.ceil(flowduration / xint)
            else:
                nintervals = math.ceil(flowduration / fscore().interval)
            nintervals = max(nintervals, 1)
            avgemit = flet.size/float(nintervals)
            assert(avgemit > 0.0)

            if test:
                print 'intervals to emit',flet.size,':',nintervals
                print 'emit bytes on avg',avgemit
    
            byteemit = eval(self.emitrvstr.replace('x', 'avgemit'))
    
            if test:
                return flet,0,byteemit,destnode

        elif self.tcpmodel == 'csa00':
            # cardwell, savage, anderson infocom 2000 improvement on pftk98

            # assume losspr is same in forward and reverse direction
            pr = pf = p

            # initial syn timeout = 3.0 sec
            ts = 3.0

            initial_window = random.choice([1,2,3])

            gamma = 1.5
            wmax = 2**20 / flet.mss
            # print 'wmax:',wmax


            # eq(4): expected handshake time
            elh = basertt + ts * ( (1.0-pr) / (1-2.0*pr) + (1.0 - pf) / (1 - 2*pf) - 2.0)

            # eq(5): expected number of packets in initial slow-start phase
            d = flet.size // flet.mss
            if flet.size % flet.mss > 0:
                d += 1
            edss = math.floor((1 - (1 - p) ** d) * (1 - p) / p + 1)

            # eq(11): expected window at the end of slowstart
            ewss = edss * (gamma - 1) / gamma + initial_window/gamma

            # eq(15): expected time to send edss in initial slow start
            # NB: assume that sources are not receive window limited
            ewss = edss * (gamma - 1) / gamma + initial_window/gamma
            if ewss > wmax:
                etss = basertt * math.log(wmax/initial_window, gamma) + 1.0 + 1.0/wmax *(edss - (gamma * wmax - initial_window)/(gamma - 1.0))
            else:
                etss = basertt * math.log(edss*(gamma-1)/initial_window+1,gamma)

            # eq(21)
            edca = d - edss
            # print 'data left after slowstart:',edca
            
            # eq(16); pr that slowstart ends with a loss
            lss = 1 - (1-p)**d

            # eq(17)
            Q = lambda p,w: min(1.0, (1+(1-p)**3*(1-(1-p)**(w-3)))/((1-(1-p)**w)/(1-(1-p)**3)))

            # eq(19)
            G = lambda p: 1 + p + 2*p**2 + 4*p**3 + 8*p**4 + 16*p**5 + 32*p**6

            # eq(18); cost of an RTO
            # to = basertt * 4
            # to = 3 # initial rto (sec)
            to = basertt * 2
            Ezto = G(p)*to/(1-p)

            # eq(20)
            etloss = lss * (Q(p,ewss) * Ezto + (1-Q(p,ewss)) * basertt)
            
            # eq(23)
            b = 2.0
            wp = 2+b/3*b + math.sqrt(8*(1-p)/3*b*p + (2*b/(3*b))**2)

            # eq(22)
            if wp < wmax:
                R = ((1-p)/p+wp/2.0+Q(p,wp)) / (basertt*(b/2.0*wp+1)+(Q(p,wp)*G(p)*to)/(1-p))
            else:
                R = ((1-p)/p+wmax/2.0+Q(p,wmax))/(basertt*(b/8.0*wmax+(1-p)/(p*wmax)+Q(p,wmax)*G(p)*to/(1-p)))

            # eq(24): expected time to send remaining data in congestion avoidance
            etca = edca/R

            etdelack = 0.1
            
            # eq(25): expected time for data transfer
            flowduration = etss + etloss + etca + etdelack
            
            #print 'exp handshake',elh
            #print 'data bytes: %d mss %d pkts %d' % (flet.size, flet.mss, d)
            #print 'expt d in ss',edss
            #print 'etss',etss
            #print 'etloss',etloss
            #print 'etca',etca
            #print 'etdelack',etdelack
            #print 'entire estimated time',flowduration

            # assert(flowduration >= basertt)
            flowduration = max(flowduration, basertt)

            csa00bw = flet.size / flowduration
            if test:
                nintervals = math.ceil(flowduration / xint)
            else:
                nintervals = math.ceil(flowduration / fscore().interval)

            nintervals = max(nintervals, 1)
            avgemit = flet.size/nintervals
            byteemit = eval(self.emitrvstr.replace('x', 'avgemit'))

            if test:
                return flet,0,byteemit,destnode


        # FIXME: add an end timestamp onto flow to indicate its estimated
        # duration; routers along path can add that end to arrival time to get
        # better flow duration in record.
        # unclear what to do with raw flows.
        flet.flowstart = 0.0
        flet.flowend = flowduration


        fscore().after(0.0, 'flowemit-'+str(self.srcnode), self.flowemit, flet, 0, byteemit, destnode)
        
        # if operating in an 'open-loop' fashion, schedule next
        # incoming flow now (otherwise schedule it when this flow ends;
        # see code in flowemit())
        if self.xopen:
            nextst = next(self.flowstartrv)
            # print >>sys.stderr, 'scheduling next new harpoon flow at',nextst
            fscore().after(nextst, 'newflow-'+str(self.srcnode), self.newflow)


    def flowemit(self, flowlet, numsent, emitrv, destnode, test=False):
        fsend = copy.copy(flowlet)
        fsend.bytes = int(min(next(emitrv), flowlet.bytes)) 
        flowlet.bytes -= fsend.bytes
        psize = min(next(self.pktsizerv), flowlet.mss)
        psize = int(max(40, psize))
        fsend.pkts = fsend.bytes / psize
        if fsend.pkts * psize < fsend.bytes:
            fsend.pkts += 1
        fsend.bytes += fsend.pkts * 40

        # print 'pkts:',fsend.pkts
        # print 'psize:',psize
        # print 'flowlet has %d bytes remaining' % (flowlet.size)

        if flowlet.ipproto == socket.IPPROTO_TCP:
            flags = 0x0
            if numsent == 0: # start of flow
                # set SYN flag
                flags |= 0x02 

                # if first flowlet, add 1 3-way handshake pkt.
                # simplifying assumption: 3-way handshake takes place in one
                # simulator tick interval with final ack piggybacked with data.
                fsend.pkts += 1
                fsend.bytes += 40

            if flowlet.bytes == 0: # end of flow
                # set FIN flag
                flags |= 0x01

                fsend.pkts += 1
                fsend.bytes += 40

            # set ACK flag regardless
            flags |= 0x10 # ack
            fsend.tcpflags = flags

        numsent += 1

        if test:
            return fsend,numsent,emitrv,destnode


        # print '0x%0x flags' % (fsend.tcpflags)
        fscore().topology.node(self.srcnode).flowlet_arrival(fsend, 'harpoon', destnode)

        # if there are more flowlets, schedule the next one
        if flowlet.bytes > 0:
            fscore().after(fscore().interval, 'flowemit-'+str(self.srcnode), self.flowemit, flowlet, numsent, emitrv, destnode)
        else:
            # if there's nothing more to send, remove from active flows 
            del self.activeflows[flowlet.key]

            # if we're operating in closed-loop mode, schedule beginning of next flow now that
            # we've completed the current one.
            if not self.xopen:
                fscore().after(next(self.flowstartrv), 'newflow-'+str(self.srcnode), self.newflow)
    
    def __makeflow(self):
        while True:
            if haveIPAddrGen:
                srcip = str(ipaddr.IPv4Address(ipaddrgen.generate_addressv4(self.ipsrcgen)))
                dstip = str(ipaddr.IPv4Address(ipaddrgen.generate_addressv4(self.ipdstgen)))
            else:
                # srcip = str(ipaddr.IPAddress(int(self.srcnet) + random.randint(0,self.srcnet.numhosts-1)))
                # dstip = str(ipaddr.IPAddress(int(self.dstnet) + random.randint(0,self.dstnet.numhosts-1)))
                srcip = str(ipaddr.IPAddress(int(self.srcnet) + random.randint(0, 2)))
                dstip = str(ipaddr.IPAddress(int(self.dstnet) + random.randint(0, 2)))

            ipproto = next(self.ipproto)
            sport = next(self.srcports)
            dport = next(self.dstports)
            fsize = int(next(self.flowsizerv))
            # Creating src and dst mac addresses
            srcmac = get_mac_addr(srcip)
            dstmac = get_mac_addr(dstip)
            flet = Flowlet(FlowIdent(srcip, dstip, ipproto, sport, dport, srcmac, dstmac), 
                           bytes=fsize)
            
            flet.iptos = next(self.iptosrv)
            if flet.key not in self.activeflows:
                break

        return flet
    
class SubtractiveTrafficGenerator(TrafficGenerator):
    def __init__(self, srcnode, dstnode=None, action=None, ipdstfilt=None,
                 ipsrcfilt=None, ipprotofilt=None):
        TrafficGenerator.__init__(self, srcnode)
        self.dstnode = dstnode
        self.logger.debug('subtractive: %s %s %s %s %s %s' % (srcnode,dstnode,action,ipdstfilt, ipsrcfilt, ipprotofilt))
        # print >>sys.stderr, 'subtractive: %s %s %s %s %s %s' % (srcnode,dstnode,action,ipdstfilt, ipsrcfilt, ipprotofilt)

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


    def callback(self):
        # pass oneself from srcnode to dstnode, performing action at each router
        # at end, set done to True
        f = SubtractiveFlowlet(FlowIdent(self.ipsrcfilt, self.ipdstfilt, ipproto=self.ipprotofilt), action=self.action)
        self.logger.info('Subtractive generator callback')
        fscore().node(self.srcnode).flowlet_arrival(f, 'subtractor', self.dstnode)


class FlowEventGenModulator(object):
    def __init__(self, gfunc, stime=0, emerge_profile=None, sustain_profile=None, withdraw_profile=None):
        self.generators = {}
        self.generator_generator = gfunc
        self.starttime = stime
        self.logger = get_logger()
        if isinstance(self.starttime, (int, float)):
            self.starttime = randomchoice(self.starttime)

        # profiles should be generators that return a list of tuples: (time, numsources)
        self.emerge = self.sustain = self.withdraw = None

        # print 'emerge',emerge_profile
        # print 'sustain',sustain_profile
        # print 'withdraw',withdraw_profile

        # examples:
        #    profile=((10,10,10,10,10,10),(1,2,3,4,5,6))"
        #    profile=((10,),(1,))"
        #    emerge=((1,),range(1,100,10)) sustain=((0,30),(100,100)) withdraw=((1,),range(100,1,10))"

        if emerge_profile:
            emerge = eval(emerge_profile)
            # print 'emerge',emerge
            self.emerge = zipit(emerge)

        if sustain_profile:
            sustain = eval(sustain_profile)
            # print 'sustain',sustain
            self.sustain = zipit(sustain)

        if withdraw_profile:
            withdraw = eval(withdraw_profile)
            print 'withdraw',withdraw
            self.withdraw = zipit(withdraw)


    def start(self):
        fscore().after(next(self.starttime), 'flowev modulator startup', self.emerge_phase)


    def start_generator(self):
        g = self.generator_generator()
        g.start()
        self.generators[g] = 1


    def kill_all_generator(self):
        self.__modulate(0)


    def kill_generator(self):
        g = random.choice(self.generators.keys())
        g.stop()
        del self.generators[g]
        

    def reap_generators(self):
        donelist = []
        for g,x in self.generators.iteritems():
            if g.done:
                donelist.append(g)
        for g in donelist:
            del self.generators[g]


    def __modulate(self, target_sources):
        num_sources = len(self.generators)

        while num_sources != target_sources:
            if num_sources < target_sources:
                self.start_generator()
                num_sources += 1
            else:
                self.kill_generator()
                num_sources -= 1


    def emerge_phase(self):
        self.reap_generators()
        nexttime,sources = 0,0
        try:
            nexttime,sources = next(self.emerge)
        except:
            self.logger.info('scheduling transition from emerge to sustain')
            fscore().after(0.0, 'modulator transition: emerge->sustain', self.sustain_phase)
        else:
            assert(sources>=0)
            self.__modulate(sources)
            self.logger.info('emerge: %f %d' % (nexttime,sources))
            fscore().after(nexttime, 'modulator: emerge', self.emerge_phase)


    def sustain_phase(self):
        self.reap_generators()
        nexttime,sources = 0,0
        try:
            nexttime,sources = next(self.sustain)
        except:
            self.logger.info('scheduling transition from sustain to withdraw')
            fscore().after(0.0, 'modulator transition: sustain->withdraw', self.withdraw_phase)
        else:
            assert(sources>=0)
            self.__modulate(sources)
            self.logger.info('sustain: %f %d' % (nexttime,sources))
            fscore().after(nexttime, 'modulator: sustain', self.sustain_phase)


    def withdraw_phase(self):
        self.reap_generators()
        nexttime,sources = 0,0
        try:
            nexttime,sources = next(self.withdraw)
        except:
            self.logger.info('finished with withdraw phase')
            fscore().after(0, 'modulator: kill_all', self.kill_all_generator)
        else:
            assert(sources>=0)
            self.__modulate(sources)
            self.logger.info('withdraw: %f %d' % (nexttime,sources))
            fscore().after(nexttime, 'modulator: withdraw', self.withdraw_phase)

