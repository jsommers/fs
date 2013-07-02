#!/usr/bin/env python

__author__ = 'jsommers@colgate.edu'

import random
from fslib.common import fscore, get_logger
from fslib.util import *


class InvalidFlowConfiguration(Exception):
    pass

class FlowEventGenModulator(object):
    def __init__(self, gfunc, stime=0, emerge_profile=None, sustain_profile=None, withdraw_profile=None):
        self.generators = {}
        self.generator_generator = gfunc
        self.starttime = stime
        self.logger = get_logger("fslib.traffic")
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

