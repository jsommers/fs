#!/usr/bin/env python

__author__ = 'jsommers@colgate.edu'

import random
from ipaddr import IPv4Network, IPv4Address
import math 

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
    r = random.randint
    while True:
        yield r(lo, hi)

def randomuniffloat(lo, hi):
    r = random.random
    while True:
        yield r()*(hi-lo)+lo

def randomchoice(*choices):
    r = random.choice
    while True:
        yield r(choices)

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
    pow = math.pow
    r = random.random
    while True:
        yield (offset * ((1.0/pow(r(), 1.0/alpha)) - 1.0));

def exponential(lam):
    r = random.expovariate
    while True:
        yield r(lam)

def normal(mean, sdev):
    r = random.normalvariate
    while True:
        yield r(mean, sdev)

def lognormal(mean, sdev):
    r = random.lognormvariate
    while True:
        yield r(mean, sdev)

def gamma(alpha, beta):
    r = random.gammavariate
    while True:
        yield r(alpha, beta)

def weibull(alpha, beta):
    r = random.weibullvariate
    while True:
        yield r(alpha, beta)

def mkdict(s):
    xdict = {}
    if isinstance(s, str):
        s = s.split()
    for kvstr in s:
        k,v = kvstr.split('=')
        xdict[k] = v
    return xdict

def removeuniform(p):
    r = random.random
    while True:
        yield (r() < p)

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
    ceil = math.ceil
    log = math.log

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


def default_ip_to_macaddr(ipaddr):
    '''Convert an IPv4 address to a 48-bit MAC address-like creature.  Just
    hardcode the two high-order bytes, and fill in remainder with IP address'''
    ip = int(IPv4Address(ipaddr))
    mac = []
    for i in xrange(4): 
        mac.append(((ip >> (8*i)) & 0xff))
    mac.extend([0x02,0x00])
    mac = [ "{:02x}".format(b) for b in reversed(mac) ]
    return ':'.join(mac)

