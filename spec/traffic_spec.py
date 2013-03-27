import unittest

class TrafficTests(unittest.TestCase):
    pass
    


# def regression():
#     exporter = text_export_factory
#     sim = Simulator(0.05, 'i2.dot', exporter, debug=True, endtime=30)
    
#     print 'houston->atl delay',sim.delay('houston', 'atlanta')
#     print 'houston->atl capacity',sim.capacity('houston', 'atlanta')
#     print 'next hop from ny to chicago',sim.nexthop('newyork','chicago')
#     print 'next hop from kc to seattle',sim.nexthop('kansascity','seattle')
#     print 'next hop from atlanta to losangeles',sim.nexthop('atlanta','losangeles')

#     #dn = sim.destnode('newyork', '10.1.1.5')
#     #print 'dest node from ny to 10.1.1.5 is',dn
#     #print 'path from ny to',dn,'is:',
#     #current = 'newyork'
#     #while current != dn:
#     #    nh = sim.nexthop(current, dn)
#     #    print nh,
#     #    current = nh
#     #print

#     print 'owd from ny to la:',sim.owd('newyork','losangeles')

#     #gen = SimpleGeneratorNode(sim, 'newyork', ipaddr.IPAddress('10.1.1.5'), ipaddr.IPAddress('10.5.2.5'), 1)
#     #sim.after(0.1, gen.start)
#     #sim.run()


    ## FIXME

    
    # d1 = { 'ipsrc':'10.4.0.0/16', 'ipdst':'10.7.1.0/24', 'flowsize':'pareto(10000,1.2)', 'flowstart':'exponential(0.1)', 'pktsize':'randomunifint(1000,1500)', 'ipproto':'randomchoice(socket.IPPROTO_TCP)', 'dport':'randomchoice(22,80,443)', 'sport':'randomunifint(1025,65535)', 'emitprocess':'randomchoice(x)' }

    # d2 = 'ipsrc=10.2.0.0/16 ipdst=10.3.1.0/24 flowsize=pareto(50000,1.18) flowstart=exponential(0.5) pktsize=normal(1000,200) ipproto=randomchoice(6) dport=randomchoice(22,80,443) sport=randomunifint(1025,65535) lossrate=randomuniffloat(0.005,0.01) mss=randomchoice(1500,576,1500) emitprocess=normal(x,x*0.1) iptos=randomchoice(0x0,0x10,0x08,0x04,0x02)'

    # d3 = 'ipsrc=10.2.0.0/16 ipdst=10.3.1.0/24 flowsize=exponential(1.0/100000) flowstart=randomchoice(10) ipproto=randomchoice(6) dport=randomchoice(22,80,443) sport=randomunifint(1025,65535) lossrate=randomuniffloat(0.05,0.10)'

    # d3 = mkdict(d3)
    # harpoon = HarpoonGeneratorNode(None, 'test', tcpmodel='mathis', **d3)

    # flowlet,sent,emitrv,dnode = harpoon.newflow(test=True, xint=1.0)
    # preflowlet = copy.copy(flowlet)
    # print "prestuff",flowlet, sent, emitrv, dnode

    # accum = copy.copy(flowlet)
    # accum.bytes = 0
    # accum.pkts = 0
    # # print 'accumulator:',accum
    # i = 0
    # while flowlet.bytes > 0:
    #     f,sent,emitrv,dnode = harpoon.flowemit(flowlet,sent,emitrv,dnode,test=True)
    #     print 'flowemit',i,f
    #     i += 1
    #     accum = accum + f
    # print 'pre:',preflowlet
    # print 'done:',accum
    # print 'avg pkt accum:',accum.bytes/float(accum.pkts)


    # harpoon = HarpoonGeneratorNode(None, 'test', tcpmodel='csa00', **d3)
    # flowlet,sent,emitrv,dnode = harpoon.newflow(test=True, xint=1.0)
    # preflowlet = copy.copy(flowlet)
    # print "prestuff",flowlet, sent, emitrv, dnode
        
if __name__ == '__main__':
    unittest.main()
