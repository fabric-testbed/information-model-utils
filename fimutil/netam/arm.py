import fim.user as f
from fim.graph.abc_property_graph import ABCPropertyGraph

from fimutil.netam.nso import NsoClient
from fimutil.netam.sr_pce import SrPceClient

import re


class NetworkARM:
    """
    Generate Network AM resources information model.
    """

    def __init__(self, *, nso_url: str, nso_user: str, nso_pass: str, sr_pce_url: str, sr_pce_user: str, sr_pce_pass: str):
        self.nso = NsoClient(nso_url=nso_url, nso_user=nso_user, nso_pass=nso_pass)
        self.sr_pce = SrPceClient(sr_pce_url=sr_pce_url, sr_pce_user=sr_pce_user, sr_pce_pass=sr_pce_pass)
        self.json_topology = None

    def _get_device_interfaces(self):
        devs = self.nso.devices()
        for dev in devs:
            dev_name = dev['name']
            ifaces = self.nso.interfaces(dev_name)
            for iface in list(ifaces):
                if iface['admin-status'] == 'up' and re.search('GigE\d/\d/\d', iface['name']):
                    continue
                ifaces.remove(iface)
            dev['interfaces'] = ifaces
        return devs

    def test(self):
        devs = self._get_device_interfaces()
        print(devs)


## TESTING ##
arm = NetworkARM(nso_url="https://192.168.11.246/restconf/data", nso_user="admin", nso_pass="FL9uhqjdYPyBehFg",
                 sr_pce_url = None, sr_pce_user = None, sr_pce_pass=None)
arm.test()