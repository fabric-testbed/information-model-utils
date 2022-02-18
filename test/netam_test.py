import unittest

from fimutil.netam.nso import NsoClient
from fimutil.netam.sr_pce import SrPceClient
from fimutil.netam.arm import NetworkARM


class NetAmTest(unittest.TestCase):
    def setUp(self) -> None:
        pass

    @unittest.skip
    def testNsoClient(self):
        nso = NsoClient()
        devs = nso.devices()
        for dev in devs:
            dev_name = dev['name']
            ifaces = nso.isis_interfaces(dev_name)
            l = len(ifaces)

    def testSrPceClient(self):
        sr_pce = SrPceClient()
        sr_pce.get_topology_json()
        links_json = sr_pce.get_ipv4_links()
        assert len(links_json) >= 1 and len(links_json) % 2 == 0

    def testBuildNetworkARM(self):
        arm = NetworkARM()
        arm.build_topology()
        arm.delegate_topology("primary")
        arm.write_topology(file_name="/tmp/network-arm.graphml")

    def testBuildNetworkARMwithISISvalidattion(self):
        arm = NetworkARM(isis_link_validation=True)
        arm.build_topology()
        arm.delegate_topology("primary")
        arm.write_topology(file_name="/tmp/network-arm.graphml")
