from random import choice
from math import log, floor, ceil, sqrt

def model(bytes, mss, rtt, interval, p, rwnd=1048576):
    '''Implements the cardwell, savage, anderson infocom 2000 improvement on pftk98.'''

    # assume losspr is same in forward and reverse direction
    pr = pf = p

    # initial syn timeout = 3.0 sec
    ts = 3.0

    initial_window = choice([1,2,3])

    gamma = 1.5
    wmax = rwnd / mss  # receive window, in MSS
    # print 'wmax:',wmax

    # eq(4): expected handshake time
    elh = rtt + ts * ( (1.0-pr) / (1-2.0*pr) + (1.0 - pf) / (1 - 2*pf) - 2.0)

    # eq(5): expected number of packets in initial slow-start phase
    d = bytes // mss
    if bytes % mss > 0:
        d += 1
    edss = floor((1 - (1 - p) ** d) * (1 - p) / p + 1)

    # eq(11): expected window at the end of slowstart
    ewss = edss * (gamma - 1) / gamma + initial_window/gamma

    # eq(15): expected time to send edss in initial slow start
    # NB: assume that sources are not receive window limited
    ewss = edss * (gamma - 1) / gamma + initial_window/gamma
    if ewss > wmax:
        etss = rtt * log(wmax/initial_window, gamma) + 1.0 + 1.0/wmax *(edss - (gamma * wmax - initial_window)/(gamma - 1.0))
    else:
        etss = rtt * log(edss*(gamma-1)/initial_window+1,gamma)

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
    # to = rtt * 4
    # to = 3 # initial rto (sec)
    to = rtt * 2
    Ezto = G(p)*to/(1-p)

    # eq(20)
    etloss = lss * (Q(p,ewss) * Ezto + (1-Q(p,ewss)) * rtt)
    
    # eq(23)
    b = 2.0
    wp = 2+b/3*b + sqrt(8*(1-p)/3*b*p + (2*b/(3*b))**2)

    # eq(22)
    if wp < wmax:
        R = ((1-p)/p+wp/2.0+Q(p,wp)) / (rtt*(b/2.0*wp+1)+(Q(p,wp)*G(p)*to)/(1-p))
    else:
        R = ((1-p)/p+wmax/2.0+Q(p,wmax))/(rtt*(b/8.0*wmax+(1-p)/(p*wmax)+Q(p,wmax)*G(p)*to/(1-p)))

    # eq(24): expected time to send remaining data in congestion avoidance
    etca = edca/R

    etdelack = 0.1
    
    # eq(25): expected time for data transfer
    flowduration = etss + etloss + etca + etdelack
    
    #print 'exp handshake',elh
    #print 'data bytes: %d mss %d pkts %d' % (bytes, mss, d)
    #print 'expt d in ss',edss
    #print 'etss',etss
    #print 'etloss',etloss
    #print 'etca',etca
    #print 'etdelack',etdelack
    #print 'entire estimated time',flowduration

    # assert(flowduration >= rtt)
    flowduration = max(flowduration, rtt)

    csa00bw = bytes / flowduration
    # print "flow duration",flowduration
    # print "flow rate",csa00bw

    nintervals = ceil(flowduration / interval)

    nintervals = max(nintervals, 1)
    avgemit = bytes/nintervals

    def byteemit():
        for i in xrange(int(nintervals)+1):
            yield avgemit

    return flowduration, byteemit()


if __name__ == '__main__':
    print model(1048576, 1470, 0.060, 1, 0.01)
