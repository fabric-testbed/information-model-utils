import requests
from requests.exceptions import HTTPError
import urllib3
from yaml import load as yload
from yaml import FullLoader
import os
import urllib

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
        self.oess_group = self.config['oess_group']
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

    # TODO: @Liang return a list of all AL2S EndPoints (interfaces / ports) with attributes
    """
        {   "name": "node_name:port_name:...",
            "description": "",
            "device_name": "",
            "interface_name": "",
            "capacity": "100", # in gbps
            "vlan_range": "101-110",
            cloud peering related ? ...
            other ...
        }
    """
    def endpoints(self, device_name=None) -> list:
        hdr = {"Accept": "application/yang-data+json"}
        url = f"{self.oess_url}/data.cgi?"
        params = {'method': 'get_all_resources_for_workgroup', 'workgroup_id': 1504 }
        url = (url + urllib.parse.urlencode(params))
        try:
            response = requests.get(url, auth=(self.oess_user, self.oess_pass), headers=hdr, verify=False)
            if not response.text:
                raise Al2sAmOessError(f'GET {url}: Empty response')
            jsonResponse = response.json()
            print("Entire JSON response")
            # print(jsonResponse)
            results = jsonResponse["results"]
            endpoint_list = []
            for item in results:
                # print(item)
                endpoint = {}
                endpoint['name'] = item['node_name'] + ':' + item['interface_name']
                endpoint['description'] = item['description']
                endpoint['device_name'] = item['node_name']
                endpoint['interface_name'] = item['interface_name']
                # endpoint['capacity'] = 0
                endpoint['vlan_range'] = item['vlan_tag_range'] 
                endpoint_list.append(endpoint)
            return endpoint_list
        except HTTPError as http_err:
            print(f'HTTP error occurred: {http_err}')
        except Exception as e:
            raise Al2sAmOessError(f"GET: {url}: {e}")
        pass

    # reuse .netam.conf as the default config file
    def get_config(self, config_file):
        if not config_file:
            config_file = os.getenv('HOME') + '/.oess.conf'
            if not os.path.isfile(config_file):
                config_file = '/etc/oess.conf'
                if not os.path.isfile(config_file):
                    raise Exception('Config file not found: %s' % config_file)
        with open(config_file, 'r') as fd:
            return yload(fd.read(), Loader=FullLoader)


class Al2sAmOessError(Exception):
    def __init__(self, msg: str):
        super().__init__(f'Al2sAmOessError: {msg}')
