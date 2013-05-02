# version 1 OpenflowSwitch and OpenflowController
# from ofmessage_v1 import *
# from ofnode_v1 import *


# version 2: bridge and delegate to POX

import pox.core

# FIXME
def monkeypatcher(module):
    '''Just because it's named monkeypatching doesn't mean it's all bad :-)'''
    pass


monkeypatcher()


from pox_bridge import *

