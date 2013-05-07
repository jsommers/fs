from pox.datapaths.switch import SoftwareSwitchBase
from pox.openflow import libopenflow_01 as oflib
from fslib.node import Node
from fslib.common import fscore, get_logger

'''Because 'bridge' sounds better than 'monkeypatch'.'''

# class OpenflowSwitch(Node):
#     def __init__(self, name, **kwargs):
#         self.pox_switch = SoftwareSwitchBase()


# class OpenflowController(Node):
#     def __init__(self, name, **kwargs):
#         pass


class FakeSwitchConnection(object):
    def __init__(self, sendfn):
        self.sendfn = sendfn

    def send(self, ofmessage):
        # print "FakeSwitchConnection Sending {}".format(str(ofmessage))
        self.sendfn(ofmessage)
    
    def set_message_handler(self, x=None):
        pass




# switchconn = None

# def controller_to_switch(mesg):
#     log = get_logger()    
#     log.debug("Sending from controller to switch: {}".format(mesg))
#     s.rx_message(switchconn, mesg)

# def switch_to_controller(mesg):
#     log = get_logger()    
#     log.debug("Sending from switch to controller: {}".format(mesg))
#     fconn.simrecv(mesg)


# s = SoftwareSwitchBase(42, name="a", ports=0)
# for i in range(1,4):
#     s.add_port(i)

# fconn = ofcore.Connection(-1, controller_to_switch)
# switchconn = FakeSwitchConnection(switch_to_controller)

# s.set_connection(switchconn)

# msg = oflib.ofp_hello()
# fconn.simrecv(msg)
