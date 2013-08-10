import unittest
import fslib.common as fscommon

class FsTestBase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        '''Set up logging; turn on debug messages'''
        fscommon.setup_logger(None, True)

