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
        
    def workgroupid(self, workgroup_name) -> int:
        """
        return the workgroup_id for the given group name.
        """
        
        if not workgroup_name:
            raise Al2sAmOessError(f'Invalid input argument')
        
        hdr = {"Accept": "application/yang-data+json"}
        url = f"{self.oess_url}/user.cgi?"
        params = {'method': 'get_current'}
        url = (url + urllib.parse.urlencode(params))
        try:
            response = requests.get(url, auth=(self.oess_user, self.oess_pass), headers=hdr, verify=False)
            if not response.text:
                raise Al2sAmOessError(f'GET {url}: Empty response')
            jsonResponse = response.json()
            
            users = jsonResponse["results"]
            workgroup_id = -1
            for user in users:
                workgroups = user['workgroups']
                for group in workgroups:
                    if group['name'] == workgroup_name:
                        workgroup_id = group['workgroup_id']
                        return workgroup_id
            raise Al2sAmOessError(f'OESS warning: workgroup_id not found for {workgroup_name}')
        except HTTPError as http_err:
            print(f'HTTP error occurred: {http_err}')
        except Exception as e:
            raise Al2sAmOessError(f"GET: {url}: {e}")
        pass
        
    def interface(self, interface_id) -> dict:
        """
        return the info of interface with the given interface_id.
        """
        
        if not interface_id:
            raise Al2sAmOessError(f'Invalid input argument')
        
        hdr = {"Accept": "application/yang-data+json"}
        url = f"{self.oess_url}/interface.cgi?"
        params = {'method': 'get_interface', 'interface_id': interface_id}
        url = (url + urllib.parse.urlencode(params))
        try:
            response = requests.get(url, auth=(self.oess_user, self.oess_pass), headers=hdr, verify=False)
            if not response.text:
                raise Al2sAmOessError(f'GET {url}: Empty response')
            jsonResponse = response.json()
            
            interfaces = jsonResponse["results"]
            if interfaces:
                return interfaces[0]
            else:
                raise Al2sAmOessError(f'OESS warning: interface not found for {interface_id}')
        except HTTPError as http_err:
            print(f'HTTP error occurred: {http_err}')
        except Exception as e:
            raise Al2sAmOessError(f"GET: {url}: {e}")
        pass
        
    def vlan_tag_range(self, workgroup_id, interface_id) -> str:
        """
        return the info of interface with the given interface_id.
        """
        
        if not workgroup_id or not interface_id:
            raise Al2sAmOessError(f'Invalid input argument')
        
        hdr = {"Accept": "application/yang-data+json"}
        url = f"{self.oess_url}/data.cgi?"
        params = {'method': 'get_all_resources_for_workgroup', 'workgroup_id': workgroup_id}
        url = (url + urllib.parse.urlencode(params))
        try:
            response = requests.get(url, auth=(self.oess_user, self.oess_pass), headers=hdr, verify=False)
            if not response.text:
                raise Al2sAmOessError(f'GET {url}: Empty response')
            jsonResponse = response.json()
            
            resources = jsonResponse["results"]
            
            for resource in resources:
                if resource["interface_id"] == interface_id:
                    return resource["vlan_tag_range"]
            else:
                raise Al2sAmOessError(f'OESS warning: interface not found for {interface_id}')
        except HTTPError as http_err:
            print(f'HTTP error occurred: {http_err}')
        except Exception as e:
            raise Al2sAmOessError(f"GET: {url}: {e}")
        pass
        
    def endpoints(self, device_name=None, cloud_connect=True) -> list:
        """
        return a list of all AL2S EndPoints (interfaces / ports) with attributes
        {   "name": "node_name:port_name:...",
            "description": "",
            "device_name": "",
            "interface_name": "",
            "capacity": "100", # in gbps
            "vlan_range": "101-110",
            cloud peering related ? ...
            other ...
        }
        
        parameters:
        cloud_connect:  contain cloud endpoints if it is true
        """
        try:
            workgid = self.workgroupid(self.oess_group)
            # Or hardcoded as "workgroup_id": "1482".
        except Exception as e:
            raise Al2sAmOessError(f"GET: endpoints: {e}")
        
        hdr = {"Accept": "application/yang-data+json"}
        url = f"{self.oess_url}/entity.cgi?"
        params = {'method': 'get_entities', 'workgroup_id': workgid }
        url = (url + urllib.parse.urlencode(params))
        try:
            response = requests.get(url, auth=(self.oess_user, self.oess_pass), headers=hdr, verify=False)
            if not response.text:
                raise Al2sAmOessError(f'GET {url}: Empty response')
            jsonResponse = response.json()
            entities = jsonResponse["results"]
            endpoint_list = []
            for entity in entities:
                for interface in entity['interfaces']:
                    endpoint = {}
                    vlan_range = ""
                    for acl in interface['acls']:
                        if acl['workgroup_id'] == workgid:
                            if vlan_range:
                                vlan_range = vlan_range + ',' + acl["start"] + "-" + acl["end"]
                            else:
                                vlan_range = acl["start"] + "-" + acl["end"]
                    
                    if vlan_range: 
                        endpoint['name'] = interface['node'] + ':' + interface['name']
                        endpoint['description'] = interface['description']
                        endpoint['device_name'] = interface['node']
                        endpoint['interface_name'] = interface['name']
                        endpoint['capacity'] =str(int(float(interface['bandwidth'])/1000.0))
                        endpoint['vlan_range'] = vlan_range
                        endpoint['cloud_interconnect_id'] = interface['cloud_interconnect_id']
                        endpoint['cloud_interconnect_type'] = interface['cloud_interconnect_type'] 
                        if endpoint not in endpoint_list:
                            endpoint_list.append(endpoint)
                        
                        # workgroup_id: 'null' means all working group?
                    if cloud_connect and not endpoint and interface['cloud_interconnect_id']:
                            endpoint['name'] = interface['node'] + ':' + interface['name']
                            endpoint['description'] = interface['description']
                            endpoint['device_name'] = interface['node']
                            endpoint['interface_name'] = interface['name']
                            endpoint['capacity'] = str(int(float(interface['bandwidth'])/1000.0))
                            endpoint['cloud_interconnect_id'] = interface['cloud_interconnect_id']
                            endpoint['cloud_interconnect_type'] = interface['cloud_interconnect_type']
                            endpoint['cloud_region'] = entity['name']
                            if entity['parents']:
                                parent_name = entity['parents'][0]['name']
                                grandparent_name = self.get_parent_entity_name(parent_name, entities)
                                if grandparent_name == 'Cloud Providers':
                                    endpoint['cloud_provider'] = parent_name
                                else:
                                    endpoint['cloud_provider'] = grandparent_name
                            vlan_range = ""
                            for acl in interface['acls']:
                                if vlan_range:
                                    vlan_range = vlan_range + ',' + acl["start"] + "-" + acl["end"]
                                else:
                                    vlan_range = acl["start"] + "-" + acl["end"]
                            endpoint['vlan_range'] = vlan_range
                            if endpoint not in endpoint_list:
                                endpoint_list.append(endpoint)
                        
            return endpoint_list
        except HTTPError as http_err:
            print(f'HTTP error occurred: {http_err}')
        except Exception as e:
            raise Al2sAmOessError(f"GET: {url}: {e}")
        pass


    def get_parent_entity_name(self, name, entities: list) -> str:
        for entity in entities:
            if entity["children"]:
                for child_entity in entity["children"]:
                    if name == child_entity['name']:
                        return entity['name']
        return None


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
