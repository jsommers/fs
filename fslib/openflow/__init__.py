# version 1 OpenflowSwitch and OpenflowController
# from ofmessage_v1 import * # from ofnode_v1 import *

# version 2: direct integration and monkeypatching of POX

import pox.lib.recoco
recoco.

class LibraryPatch(object):
    def __getattr__(self, attr):
        print "Faker lib get attribute {}".format(attr)
        assert(False)

patch = LibraryPatch()




setattr(pox.lib, "recoco", patch)
setattr(pox.lib, "revent", patch)
setattr(pox, "messenger", patch)
setattr(pox, "misc", patch)