import unittest

from fimutil.netam.netam_arm import NetAmARM


class NetAmTest(unittest.TestCase):

    def testNetAmComponents(self):
        self.arm = NetAmARM(sr_pce_url="http://192.168.113.7:8080/topo/subscribe/txt",
                            sr_pce_user="admin", sr_pce_pass="password")
        json_topo = self.arm.get_json_topology()
        print(json_topo)
