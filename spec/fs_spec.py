import unittest
import fs

class SimTests(unittest.TestCase):
    pass

## FIXME...
    
#     def 


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

if __name__ == '__main__':
    unittest.main()