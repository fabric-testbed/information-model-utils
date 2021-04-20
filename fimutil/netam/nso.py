import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class NsoClient:
    """
    Retrieve Network AM resources information from Cisco NSO.
    """

    def __init__(self, *, nso_url: str, nso_user: str, nso_pass: str):
        self.nso_url = nso_url
        self.nso_user = nso_user
        self.nso_pass = nso_pass
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
        ret_json = self._get(ep)
        if 'ietf-interfaces:interface' not in ret_json:
            raise NetAmNsoError(f"GET: {self.nso_url}/{ep}: 'ietf-interfaces:interface' unfound in response")
        return ret_json['ietf-interfaces:interface']


class NetAmNsoError(Exception):
    def __init__(self, msg: str):
        super().__init__(f'NetAmNsoError: {msg}')
