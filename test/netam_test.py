import unittest

from fimutil.netam.nso import NsoClient
from fimutil.netam.sr_pce import SrPceClient
from fimutil.netam.arm import NetworkARM


class NetAmTest(unittest.TestCase):
    def setUp(self) -> None:
        self.nso = NsoClient(nso_url="https://192.168.11.246/restconf/data", nso_user="admin", nso_pass="password")
        self.sr_pce = SrPceClient(sr_pce_url="http://192.168.113.7:8080/topo/subscribe/txt", sr_pce_user="admin", sr_pce_pass="password")
        self.arm = NetworkARM(nso_url="https://192.168.11.246/restconf/data", nso_user="admin", nso_pass="",
                         sr_pce_url=None, sr_pce_user=None, sr_pce_pass=None)

    @unittest.skip
    def testNsoClient(self):
        devs = self.nso.devices()

    @unittest.skip
    def testSrPceClient(self):
        devs = self.sr_pce.get_topology_json()

    def testBuildNetworkARM(self):
        topo_model = "NetAM-TestAd"
        self.arm.build_topology(topo_model)
        self.arm.write_topology(file_name="/tmp/network-arm.graphml")
