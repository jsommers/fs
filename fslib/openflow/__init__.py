# version 1 OpenflowSwitch and OpenflowController
# from ofmessage_v1 import * # from ofnode_v1 import *

# version 2: direct integration and monkeypatching of POX

from fslib.common import fscore, get_logger
from fslib.node import Node
from importlib import import_module
import pox
import pox.core 
import pox.lib
import pox.lib.recoco as recoco
import pox.openflow as openflow_component
from pox.datapaths.switch import SoftwareSwitchBase
from pox.openflow import libopenflow_01 as oflib
import pox.openflow.of_01 as ofcore


class RuntimeError(Exception):
    pass

class FakePoxTimer(object):
    '''Timer class that supports same interface as pox.lib.recoco.Timer'''

    timerid = 0
    def __init__ (self, timeToWake, callback, absoluteTime = False,
                recurring = False, args = (), kw = {}, scheduler = None,
                started = True, selfStoppable = True):

        if absoluteTime and recurring:
            raise RuntimeError("Can't have a recurring timer for an absolute time!")

        if absoluteTime:
            raise RuntimeError("Can't have an absolute time in FakePoxTimer")

        self._self_stoppable = selfStoppable
        self._timeToWake = timeToWake
        self._cancelled = False

        self.id = "poxtimer{}".format(FakePoxTimer.timerid)
        FakePoxTimer.timerid += 1

        self._recurring = recurring
        self._callback = callback
        self._args = args
        self._kw = kw

        if started: self.start()

    def cancel(self):
        fscore().cancel(self.id)
        self._cancelled = True

    def docallback(self):
        if self._recurring and not self._cancelled:
            fscore().after(self._timeToWake, self.id, self.docallback, None)
        rv = self._callback(*self._args, **self._kw)
        
    def start(self, scheduler=None):
        self.run()

    def run (self):
        get_logger().debug("OF FakeTimer setting up timer callback {} {}".format(self._timeToWake, self._callback))
        fscore().after(self._timeToWake, self.id, self.docallback, None)
        

class PoxLibPlug(object):
    def __getattr__(self, attr):
        print "Pox library plug get attribute {}".format(attr)
        assert(False),"Unexpected POX call: monkeypatch may need update."


origConn = ofcore.Connection
class FakeOpenflowConnection(ofcore.Connection):
    def __init__(self, sock, controller_send, switchname="wrong", dpid=None):
        self.sendfn = controller_send
        self.idle_time = None
        self.connect_time = None
        self.switchname = switchname
        self.sock = -1
        origConn.__init__(self, -1) 
        self.ofnexus = pox.core.core.OpenFlowConnectionArbiter.getNexus(self)
        self.dpid = dpid
        self.ofnexus.connections[dpid] = self
                
    def send(self, ofmessage):
        get_logger().debug("Doing callback in OF connection from controller->switch {}".format(ofmessage)) 
        self.sendfn(self.switchname, ofmessage)

    def read(self):
        print "Got read() in Fake Connection, but we expect simrecv to be called"

    def simrecv(self, msg):
        # print "Received message in FakeOpenflowConnection:", str(msg)
        if msg.version != oflib.OFP_VERSION:
            log.warning("Bad OpenFlow version (0x%02x) on connection %s"
                % (ord(self.buf[offset]), self))
            return False # Throw connection away

        # don't need to pack/unpack because we control message send/recv
        # new_offset,msg = unpackers[ofp_type](self.buf, offset)
        ofp_type = msg.header_type

        try:
            from pox.openflow.of_01 import handlers
            h = handlers[ofp_type]
            h(self, msg)
        except:
            log.exception("%s: Exception while handling OpenFlow message:\n" +
                      "%s %s", self,self,
                      ("\n" + str(self) + " ").join(str(msg).split('\n')))
        return True

    def fileno(self):
        return -1

    def close(self):
        pass

def monkey_patch_pox():
    '''Override two key bits of POX functionality: the Timer class and
    the openflow connection class.  Other overrides are mainly to ensure
    that nothing unexpected happens, but are strictly not necessary at
    present (using betta branch of POX)'''
    get_logger().debug("Monkeypatching POX for integration with fs")

    fakerlib = PoxLibPlug()

    # setattr(recoco, "Timer", FakePoxTimer)
    setattr(pox.lib, "revent", fakerlib)
    setattr(pox.lib, "ioworker", fakerlib)
    setattr(pox.lib, "pxpcap", fakerlib)
    setattr(pox, "messenger", fakerlib)
    setattr(pox, "misc", fakerlib)
    setattr(ofcore, "Connection", FakeOpenflowConnection)
    setattr(ofcore, "OpenFlow_01_Task", fakerlib)


def load_pox_component(name):
    '''Load a pox component by trying to import the named module and
       invoking launch().  Raise a runtime error if something goes wrong.'''
    log = get_logger()
    try:
        m = import_module(name)
        if 'launch' not in dir(m):
            log.error("Can't load POX module {}".format(name))
            raise RuntimeError()
        else:
            log.debug("Loading POX component {}".format(name))
            m.launch()
    except ImportError,e:
        log.error("Error trying to import {} POX component".format(name))
        raise RuntimeError()


monkey_patch_pox()
load_pox_component("pox.openflow")

from pox_bridge import *

def pox_init():
    get_logger().debug("Kicking POX up.")
    pox.core.core.goUp()
    get_logger().debug("POX components: {}".format(pox.core.core.components))

fscore().after(0.0, "POX up", pox_init)
