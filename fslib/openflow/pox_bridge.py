from pox.datapaths.switch import SoftwareSwitchBase
from pox.openflow import libopenflow_01 as oflib
from fslib.node import Node
from fslib.common import fscore, get_logger

'''Because 'bridge' sounds better than 'monkeypatch'.'''

class OpenflowSwitch(Node):
    def __init__(self, name, **kwargs):
        self.pox_switch = SoftwareSwitchBase()


class OpenflowController(Node):
    def __init__(self, name, **kwargs):
        pass

class PoxBridgeRuntimeError(Exception):
    pass

class FakePoxTimer(object):
    '''Timer class that supports same interface as pox.lib.recoco.Timer'''

    timerid = 0
    def __init__ (self, timeToWake, callback, absoluteTime = False,
                recurring = False, args = (), kw = {}, scheduler = None,
                started = True, selfStoppable = True):

        if absoluteTime and recurring:
            raise PoxBridgeRuntimeError("Can't have a recurring timer for an absolute time!")

        if absoluteTime:
            raise PoxBridgeRuntimeError("Can't have an absolute time in FakePoxTimer")

        self._self_stoppable = selfStoppable
        self._timeToWake = timeToWake
        self._cancelled = False

        self.id = "poxtimer{}".format(FakeTimer.timerid)
        FakePoxTimer.timerid += 1

        self._recurring = recurring
        self._callback = callback
        self._args = args
        self._kw = kw

        if started: self.start()

    def cancel(self):
        fscore.cancel(self.id)
        self._cancelled = True

    def docallback(self):
        if self._recurring and not self._cancelled:
            fscore().after(self._timeToWake, self.id, self.docallback, None)
        rv = self._callback(*self._args, **self._kw)
        
    def start(self, scheduler=None):
        self.run()

    def run (self):
        fscore().after(self._timeToWake, self.id, self.docallback, None)
        

class PoxLibPlug(object):
    def __getattr__(self, attr):
        print "Pox library plug get attribute {}".format(attr)
        assert(False)

fakerlib = PoxLibPlug()

import pox
import pox.lib
import pox.lib.recoco as recoco

setattr(recoco, "Timer", FakePoxTimer)
setattr(pox.lib, "revent", fakerlib)
setattr(pox, "messenger", fakerlib)
setattr(pox, "misc", fakerlib)


import pox.openflow as openflow_component
from pox.datapaths.switch import SoftwareSwitchBase
from pox.openflow import libopenflow_01 as oflib
import pox.core 

class OpenflowSwitch(Node):
    def __init__(self, name):
        Node.__init__(name)
        self.__poxswitch = SoftwareSwitchBase(42, name="a", ports=0)
        for i in range(1,4):
            s.add_port(i)

import pox.openflow.of_01 as ofcore

origConn = ofcore.Connection
class FakeOpenflowConnection(ofcore.Connection):
    def __init__(self, sock, controller_send):
        self.sendfn = controller_send
        origConn.__init__(self, -1)         
        self.idle_time = now()

    def send(self, ofmessage):
        print "FakeOpenflowConnection Sending {}".format(str(ofmessage))
        self.sendfn(ofmessage)

    def read(self):
        print "Got read() in Fake Connection, but we expect simrecv to be called"

    def simrecv(self, msg):
        print "Received message in FakeOpenflowConnection:", str(msg)
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


setattr(ofcore, "Connection", FakeOpenflowConnection)
setattr(ofcore, "OpenFlow_01_Task", fakerlib)


class FakeSwitchConnection(object):
    def __init__(self, sendfn):
        self.sendfn = sendfn

    def send(self, ofmessage):
        print "FakeSwitchConnection Sending {}".format(str(ofmessage))
        self.sendfn(ofmessage)
    
    def set_message_handler(self, x=None):
        pass

def load_pox_component(name):
    log = get_logger()
    try:
        m = import_module(name)
        if 'launch' not in dir(m):
            log.error("Can't load POX module {}".format(name))
            raise PoxBridgeRuntimeError()
        else:
            m.launch()
    except ImportError,e:
        log.error("Error trying to import {} POX component".format(name))
        raise PoxBridgeRuntimeError()


# load_pox_component("pox.forwarding.l2_learning")
# load_pox_component("pox.openflow.discovery")

switchconn = None

def controller_to_switch(mesg):
    print "Sending from controller to switch", mesg
    s.rx_message(switchconn, mesg)

def switch_to_controller(mesg):
    print "Sending from switch to controller", mesg
    fconn.simrecv(mesg)

fconn = ofcore.Connection(-1, controller_to_switch)
switchconn = FakeSwitchConnection(switch_to_controller)

s.set_connection(switchconn)

msg = oflib.ofp_hello()
fconn.simrecv(msg)


load_pox_component("pox.openflow")
