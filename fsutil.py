#!/usr/bin/env python

__author__ = 'jsommers@colgate.edu'

import random
import math

logformat='%(asctime)s %(name)-5s %(levelname)-8s %(message)s'

def zipit(xtup):
    assert(len(xtup) == 2)
    a = list(xtup[0])
    b = list(xtup[1])
    if len(a) < len(b):
        a = a * len(b)
    a.insert(0,0)
    b.insert(0,b[0])
    # print 'zipit a',a
    # print 'zipit b',b
    # print 'xzip',zip(a,b)
    mg = modulation_generator(zip(a,b))
    return mg


def frange(a, b, c):
    xlist = []
    if a < b:
        assert (c > 0)
        while a <= b:
            xlist.append(a)
            a += c
        if a > b and xlist[-1] != b:
            xlist.append(b)
    else:
        assert (c < 0)
        while a >= b:
            xlist.append(a)
            a += c
        if a < b and xlist[-1] != b:
            xlist.append(b)
    return xlist

def modulation_generator(xlist):
    for x in xlist:
        yield x

def randomunifint(lo, hi):
    while True:
        yield random.randint(lo, hi)

def randomuniffloat(lo, hi):
    while True:
        yield random.random()*(hi-lo)+lo

def randomchoice(*choices):
    while True:
        yield random.choice(choices)

def randomchoicefile(infilename):
    xlist = []
    with open(infilename) as inf:
        for line in inf:
            for value in line.strip().split():
                try:
                    xlist.append(float(value))
                except:
                    pass
    index = 0
    while True:
        yield xlist[index]
        index = (index + 1) % len(xlist)

def pareto(offset,alpha):
    while True:
        # yield offset*random.paretovariate(alpha)
        yield (offset * ((1.0/math.pow(random.random(), 1.0/alpha)) - 1.0));

#def mypareto(scale, shape):
#    return (scale * ((1.0/math.pow(random.random(), 1.0/shape)) - 1.0));

def exponential(lam):
    while True:
        yield random.expovariate(lam)

def normal(mean, sdev):
    while True:
        yield random.normalvariate(mean, sdev)

def lognormal(mean, sdev):
    while True:
        yield random.lognormvariate(mean, sdev)

def gamma(alpha, beta):
    while True:
        yield random.gammavariate(alpha, beta)

def weibull(alpha, beta):
    while True:
        yield random.weibullvariate(alpha, beta)

def mkdict(s):
    xdict = {}
    if isinstance(s, str):
        s = s.split()
    for kvstr in s:
        k,v = kvstr.split('=')
        xdict[k] = v
    return xdict

def removeuniform(p):
    while True:
        yield (random.random() < p)
