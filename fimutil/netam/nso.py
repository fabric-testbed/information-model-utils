import requests
import urllib3
from yaml import load as yload
from yaml import FullLoader
import os
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class NsoClient:
    """
    Retrieve Network AM resources information from Cisco NSO.
    """

    def __init__(self, *, config=None, config_file=None):
        if not config:
            self.config = self.get_config(config_file)
        else:
            self.config = config
        if 'nso_url' not in self.config or 'nso_user' not in self.config or 'nso_pass' not in self.config:
            raise NetAmNsoError('NSO config missing nso_url, nso_usr or nso_pass ')
        self.nso_url = self.config['nso_url']
        self.nso_user = self.config['nso_user']
        self.nso_pass = self.config['nso_pass']
        self.json_topology = None

    def _get(self, ep) -> dict:
        hdr = {"Accept": "application/yang-data+json"}
        url = f"{self.nso_url}/{ep}"
        try:
            ret = requests.get(url, auth=(self.nso_user, self.nso_pass), headers=hdr, verify=False)
            if not ret.text:
                raise NetAmNsoError(f'GET {url}: Empty response')
            return ret.json()
        except Exception as e:
            raise NetAmNsoError(f"GET: {url}: {e}")

    def devices(self) -> list:
        base = "tailf-ncs:devices/device"
        params = "fields=name;address;description"
        ep = f"{base}?{params}"
        ret_json = self._get(ep)
        if 'tailf-ncs:device' not in ret_json:
            raise NetAmNsoError(f"GET: {self.nso_url}/{ep}: 'tailf-ncs:device' unfound in response")
        return ret_json['tailf-ncs:device']

    def interfaces(self, device_name) -> list:
        # base = f"tailf-ncs:devices/device={device_name}/live-status/ietf-interfaces:interfaces-state/interface"
        # params = "fields=name;admin-status;phys-address;speed;ietf-ip:ipv4;ietf-ip:ipv6"
        # ep = f"{base}?{params}"
        ep = f"tailf-ncs:devices/device={device_name}/live-status/ietf-interfaces:interfaces-state/interface"
        try:
            ret_json = self._get(ep)
        except NetAmNsoError as e:
            if 'Empty response' in str(e):  # skip devices that are not ready
                return None
            raise e
        if 'ietf-interfaces:interface' not in ret_json:
            return None
            # raise NetAmNsoError(f"GET: {self.nso_url}/{ep}: 'ietf-interfaces:interface' unfound in response")
        return ret_json['ietf-interfaces:interface']

    def isis_interfaces(self, device_name) -> list:
        # base = f"tailf-ncs:devices/device={device_name}/live-status/ietf-interfaces:interfaces-state/interface"
        # params = "fields=name;admin-status;phys-address;speed;ietf-ip:ipv4;ietf-ip:ipv6"
        # ep = f"{base}?{params}"
        ep = f"tailf-ncs:devices/device={device_name}/config/tailf-ned-cisco-ios-xr:router/isis/tag"
        try:
            ret_json = self._get(ep)
        except NetAmNsoError as e:
            if 'Empty response' in str(e):  # skip devices that are not ready
                return None
            raise e
        if 'tailf-ned-cisco-ios-xr:tag' not in ret_json:
            return None
        tags = ret_json['tailf-ned-cisco-ios-xr:tag']
        if type(tags) is not list or len(tags) < 1:
            return None
            # raise NetAmNsoError(f"GET: {self.nso_url}/{ep}: 'ietf-interfaces:interface' unfound in response")
        ifaces = tags[0]['interface']
        for iface in list(ifaces):
            if 'circuit-type' not in iface or iface['circuit-type'] != 'level-2-only' or 'point-to-point' not in iface:
                ifaces.remove(iface)
        return ifaces

    def get_config(self, config_file):
        if not config_file:
            config_file = os.getenv('HOME') + '/.netam.conf'
            if not os.path.isfile(config_file):
                config_file = '/etc/netam.conf'
                if not os.path.isfile(config_file):
                    raise Exception('Config file not found: %s' % config_file)
        with open(config_file, 'r') as fd:
            return yload(fd.read(), Loader=FullLoader)


class NetAmNsoError(Exception):
    def __init__(self, msg: str):
        super().__init__(f'NetAmNsoError: {msg}')
