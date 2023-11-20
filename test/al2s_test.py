import unittest

# from fimutil.al2s.oess import OessClient
from fimutil.al2s.al2s_api import Al2sClient

class Al2sTest(unittest.TestCase):

    # def testOessClient(self):
    #     oess = OessClient()
    #     eps = oess.endpoints(cloud_connect=True)
    #     self.assertTrue(eps, "Endpoint not found")
    #     if eps:
    #         for ep in eps:
    #             dev_name = ep['name']
    #             # ifaces = nso.isis_interfaces(dev_name)
    #             # l = len(ifaces)
    #             print(ep, flush=True)
                
    def test_bearer_token(self):
        client = Al2sClient()
        auth = client.bearer_token
        assert(auth)
        print("Authorization Header:", auth)
                
    def test_cloudconnects(self):
        client = Al2sClient()
        cloudconnects = client.cloudconnects
        assert(cloudconnects)
        for c in cloudconnects:
            print(c)
                
    def test_myinterfaces(self):
        client = Al2sClient()
        myinterfaces = client.myinterfaces
        assert(myinterfaces)
        for c in myinterfaces:
            print(c)
                
    def test_retrieveinterfaces(self):
        client = Al2sClient()
        ifid = "7bf53ea1-babb-4f85-b06a-89084f9b25ae"
        intf = client._retrieve_interface_availability(ifid)
        assert(intf)
        print(intf)
        
    def test_listendpoints(self):
        client = Al2sClient()
        for ep in client.list_endpoints():
            print(ep)
        
