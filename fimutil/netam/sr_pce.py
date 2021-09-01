import requests
from requests.auth import HTTPDigestAuth
import json
import os
from yaml import load as yload
from yaml import FullLoader
from jsonpath_ng.ext import parse


class SrPceClient:
    """
    Retrieve Network AM resources information from Cisco SR-PCE.
    """

    def __init__(self, *, config=None, config_file=None):
        if not config:
            self.config = self.get_config(config_file)
        else:
            self.config = config
        if 'sr_pce_url' not in self.config or 'sr_pce_user' not in self.config or 'sr_pce_pass' not in self.config:
            raise NetAmSrPceError('PCE config missing sr_pce_url, sr_pce_usr or sr_pce_pass ')
        self.sr_pce_url = self.config['sr_pce_url']
        self.sr_pce_user = self.config['sr_pce_user']
        self.sr_pce_pass = self.config['sr_pce_pass']
        self.json_topology = None

    def get_topology_json(self) -> object:
        s = requests.Session()
        # headers = {'X-Subscribe': 'stream'}
        r = s.get(self.sr_pce_url, auth=HTTPDigestAuth(self.sr_pce_user, self.sr_pce_pass), stream=True)
        if r.status_code != 200:
            raise NetAmSrPceError(f'Failed to retrieve SR-PCE topology from URL:{self.sr_pce_url} -- error code:{r.status_code}')
        json_text = ''
        for line in r.iter_lines():
            if line:
                str_line = line.decode("utf-8")
                json_text += str_line
        r.close()
        s.close()
        if not json_text.startswith('{') or json_text.find('Cisco-IOS-XR-infra-xtc-oper:pce/topology-nodes/topology-node') == -1:
            raise NetAmSrPceError(f'Invalid JSON topology retrieved from SR-PCE from URL:{self.sr_pce_url}')
        self.json_topology = json.loads(json_text)
        # print(json.dumps(self.json_topology['data_gpbkv'][1]))
        return self.json_topology

    def get_ipv4_links(self) -> object:
        if not self.json_topology:
            return None
        ipv4_links = {}
        # extract links
        jsonpath_expression = parse("$..fields[?(@.name='ipv4-links')]")
        match = jsonpath_expression.find(self.json_topology)
        for result in match:
            ipv4_local = None
            ipv4_remote = None
            for item in result.value['fields']:
                if 'name' in item and item['name'] == 'local-ipv4-address':
                    ipv4_local = item['string_value']
                elif 'name' in item and item['name'] == 'remote-ipv4-address':
                    ipv4_remote = item['string_value']
            if ipv4_local and ipv4_remote:
                link_name = ipv4_local + '-' + ipv4_remote
                if link_name not in ipv4_links:
                    # record ipv4 link with name key and (local-ip, remote-ip) tuple value
                    ipv4_links[link_name] = (ipv4_local, ipv4_remote)
        return ipv4_links

    def get_config(self, config_file):
        if not config_file:
            config_file = os.getenv('HOME') + '/.netam.conf'
            if not os.path.isfile(config_file):
                config_file = '/etc/netam.conf'
                if not os.path.isfile(config_file):
                    raise Exception('Config file not found: %s' % config_file)
        with open(config_file, 'r') as fd:
            return yload(fd.read(), Loader=FullLoader)

class NetAmSrPceError(Exception):
    def __init__(self, msg: str):
        super().__init__(f'NetAmSrPceError: {msg}')
