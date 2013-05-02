from pox.datapaths.switch import SoftwareSwitchBase
from pox.openflow import libopenflow_01 as oflib
from fslib.node import Node


class OpenflowSwitch(Node):
    def __init__(self, name, **kwargs):
        self.pox_switch = SoftwareSwitchBase()


class OpenflowController(Node):
    def __init__(self, name, **kwargs):
        pass


