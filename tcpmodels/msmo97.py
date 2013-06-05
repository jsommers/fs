from math import sqrt, ceil

def model(bytes, mss, rtt, interval, p):
    '''Function to implement MSMO97 tcp model.  Returns flow duration
    in seconds and a byte emitter (generator) given number of bytes, rtt,
    simulation interval, and an emitter str to eval'''

    # mathis model constant C
    C = sqrt(3.0/2)
    # C = sqrt(3.0/4) - delack
    # C = 1.31
    # C = 0.93
    bw = mss / rtt * C/sqrt(p)
    # print "bw computation",bw

    # how many intervals will this flowlet last?
    flowduration = bytes / bw

    nintervals = ceil(flowduration / interval)
    nintervals = max(nintervals, 1)
    avgemit = bytes/float(nintervals)
    assert(avgemit > 0.0)

    def byteemit():
        for i in xrange(int(nintervals)+1):
            yield avgemit

    return flowduration, byteemit()

if __name__ == '__main__':
    print model(1048576, 1470, 0.060, 1, 0.01)
