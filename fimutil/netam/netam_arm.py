import fim.user as f
from fim.graph.abc_property_graph import ABCPropertyGraph
import requests
from requests.auth import HTTPDigestAuth
import json
from jsonpath_ng import jsonpath
from jsonpath_ng.ext import parse


class NetAmARM:
    """
    Generate NetworkAM Aggregate Resource Model (ARM).
    """

    def __init__(self, *, sr_pce_url: str, sr_pce_user: str, sr_pce_pass: str):
        self.sr_pce_url = sr_pce_url
        self.sr_pce_user = sr_pce_user
        self.sr_pce_pass = sr_pce_pass

    def get_topology_json(self) -> object:
        s = requests.Session()
        # headers = {'X-Subscribe': 'stream'}
        r = s.get(self.sr_pce_url, auth=HTTPDigestAuth(self.sr_pce_user, self.sr_pce_pass), stream=True)
        print(r.status_code)
        if r.status_code != 200:
            raise NetAmARMSrPceError(f'Failed to retrieve SR-PCE topology from URL:{self.sr_pce_url}')
        json_text = ''
        for line in r.iter_lines():
            if line:
                str_line = line.decode("utf-8")
                json_text += str_line
        if json_text.startswith('{') and json_text.find('Cisco-IOS-XR-infra-xtc-oper:pce/topology-nodes/topology-node') == -1:
            raise NetAmARMSrPceError(f'Invalid JSON topology retrieved from SR-PCE from URL:{self.sr_pce_url}')
        return json.load(json_text)


class NetAmARMSrPceError(Exception):
    def __init__(self, msg: str):
        super().__init__(f'NetAmARMSrPceError: {msg}')


class NetAmARMNsoError(Exception):
    def __init__(self, msg: str):
        super().__init__(f'NetAmARMNsoError: {msg}')
