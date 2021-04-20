import unittest

from fimutil.netam.nso import NsoClient


class NetAmTest(unittest.TestCase):

    def testNetAmComponents(self):
        self.nso = NsoClient(nso_url="https://192.168.11.246/restconf/data", nso_user="admin", nso_pass="password")
        devs = self.nso.devices()
