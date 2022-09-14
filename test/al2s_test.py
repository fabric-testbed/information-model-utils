import unittest

from fimutil.al2s.oess import OessClient


class Al2sTest(unittest.TestCase):

    def testOessClient(self):
        oess = OessClient()
        eps = oess.endpoints(cloud_connect=True)
        self.assertTrue(eps, "Endpoint not found")
        if eps:
            for ep in eps:
                dev_name = ep['name']
                # ifaces = nso.isis_interfaces(dev_name)
                # l = len(ifaces)
                print(ep, flush=True)
