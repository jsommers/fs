#!/usr/bin/env python

__author__ = 'jsommers@colgate.edu'

from random import random, choice, randint, expovariate, \
                   gammavariate, paretovariate, weibullvariate, \
                   lognormvariate, normalvariate
from ipaddr import IPv4Network, IPv4Address
from math import log, ceil, pow

logformat='%(asctime)s %(name)-5s %(levelname)-8s %(message)s'

def zipit(xtup):
    assert(len(xtup) == 2)
    a = list(xtup[0])
    b = list(xtup[1])
    if len(a) < len(b):
        a = a * len(b)
    a.insert(0,0)
    b.insert(0,b[0])
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
        yield randint(lo, hi)

def randomuniffloat(lo, hi):
    while True:
        yield random()*(hi-lo)+lo

def randomchoice(*choices):
    while True:
        yield choice(choices)

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
        yield (offset * ((1.0/pow(random(), 1.0/alpha)) - 1.0));

def exponential(lam):
    while True:
        yield expovariate(lam)

def normal(mean, sdev):
    while True:
        yield normalvariate(mean, sdev)

def lognormal(mean, sdev):
    while True:
        yield lognormvariate(mean, sdev)

def gamma(alpha, beta):
    while True:
        yield gammavariate(alpha, beta)

def weibull(alpha, beta):
    while True:
        yield weibullvariate(alpha, beta)

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
        yield (random() < p)

def empiricaldistribution(fname):
    assert(os.path.exists(fname))
    while True:    
        with open(fname, 'r') as infile:
            for line in infile:
                for x in line.split():
                    yield float(x)

# function alias
empirical = empiricaldistribution

def subnet_generator(prefix, numhosts):
    '''Given a prefix and number of hosts to carve out for
    subnets within this prefix, create a generator object
    that returns a new subnet (as an ipaddr.IPv4Network) with
    each subsequent call to next()'''

    ipfx = IPv4Network(prefix)
    prefixhosts = ipfx.numhosts
    numhosts += 2
    numhosts = int(ceil(log(numhosts, 2)) ** 2)
    prefixlen = '/' + str(32 - int(log(numhosts,2)))
    baseint = int(ipfx)
    numsubnets = prefixhosts / numhosts
    for i in xrange(numsubnets):
        addr = IPv4Address(baseint + (numhosts * i))
        prefix = IPv4Network(str(addr) + prefixlen)
        yield prefix    
