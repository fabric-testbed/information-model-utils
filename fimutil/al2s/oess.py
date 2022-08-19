import requests
import urllib3
from yaml import load as yload
from yaml import FullLoader
import os

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class OessClient:
    """
    Retrieve AL2S AM resources information from OESS REST API.
    """

    def __init__(self, *, config=None, config_file=None):
        if not config:
            self.config = self.get_config(config_file)
        else:
            self.config = config
        if 'oess_url' not in self.config or 'oess_user' not in self.config or 'oess_pass' not in self.config:
            raise Al2sAmOessError('OESS config missing oess_url, oess_usr or oess_pass ')
        self.oess_url = self.config['oess_url']
        self.oess_user = self.config['oess_user']
        self.oess_pass = self.config['oess_pass']
        self.json_topology = None

    def _get(self, ep) -> dict:
        hdr = {"Accept": "application/yang-data+json"}
        url = f"{self.oess_url}/{ep}"
        try:
            ret = requests.get(url, auth=(self.oess_user, self.oess_pass), headers=hdr, verify=False)
            if not ret.text:
                raise Al2sAmOessError(f'GET {url}: Empty response')
            return ret.json()
        except Exception as e:
            raise Al2sAmOessError(f"GET: {url}: {e}")

    # TODO: @Liang return a list of all AL2S interfaces (EndPoints) with attributes including
    #   1. VLAN range
    #   2. description
    #   3. Other attributes like indication of Cloud entity (if any)
    def interfaces(self, device_name) -> list:
        pass

    # reuse .netam.conf as the default config file
    def get_config(self, config_file):
        if not config_file:
            config_file = os.getenv('HOME') + '/.netam.conf'
            if not os.path.isfile(config_file):
                config_file = '/etc/netam.conf'
                if not os.path.isfile(config_file):
                    raise Exception('Config file not found: %s' % config_file)
        with open(config_file, 'r') as fd:
            return yload(fd.read(), Loader=FullLoader)


class Al2sAmOessError(Exception):
    def __init__(self, msg: str):
        super().__init__(f'Al2sAmOessError: {msg}')
