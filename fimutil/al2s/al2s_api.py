import requests
from requests.exceptions import HTTPError
import urllib3
from yaml import load as yload
from yaml import FullLoader
import os
import itertools

urllib3.disable_warnings()

def to_ranges(iterable):
    iterable = sorted(set(iterable))
    for key, group in itertools.groupby(enumerate(iterable),
                                        lambda t: t[1] - t[0]):
        group = list(group)
        yield group[0][1], group[-1][1]
        
def ranges_to_str(iterable)->str:
    rangeStr=""
    for start, end in iterable:
        # item = f"{start}" if start == end else f"{start}-{end}"
        item = f"{start}-{end}"
        rangeStr = item if rangeStr=="" else  rangeStr + "," + item
        
    return rangeStr

class Al2sClient:
    """
    Retrieve AL2S resources information via Virtual Networks REST API.
    """
    
    CONF_FILE_PATH = "al2s.conf"
    
    ENDPOINT_SESSIONS_ACCESS = "/v1/sessions/access"
    ENDPOINT_FOOTPRINT_CLOUDCONNECT = "/v1/footprint/cloudconnect"
    ENDPOINT_FOOTPRINT_MYINTERFACES = "/v1/footprint/myinterfaces"
    ENDPOINT_VIRTUALNETWORKS_INTERFACES = "/v1/virtualnetworks/interfaces"
    
    ACCEPTED_STATUS_CODES = [200, range(300, 399)]
    
    MAX_RETRIES = 3
    
    CLOUD_VLAN_RANGES = {
        "AZURE": list(range(1,4095)),
        "AWS": list(range(2, 4095)),
        "GCP": list(range(2,4095)),
        "OCI": list(range(100, 4095))
        }

    def __init__(self, *, config=None, config_file=None):
        if not config:
            self.config = self._get_config(config_file)
        else:
            self.config = config
        self.api_base_url = self.config['api_base_url']
        self.api_access_key = self.config['api_access_key']
        self._auth = self.bearer_token
        self._retries = 0


    def _get_config(self, config_file):
        """
        Return configureation from the config_file
        
        Parameters
        ----------
        config_file: the path to configuration file
        
        Return
        -------
        The data from configuration file
        """
        if not config_file:
            config_file = os.getenv('HOME') + '/' + f'{self.CONF_FILE_PATH}'
            if not os.path.isfile(config_file):
                config_file = f'/etc/{self.CONF_FILE_PATH}'
                if not os.path.isfile(config_file):
                    raise Exception('Config file not found: %s' % config_file)
                
        with open(config_file, 'r') as fd:
            return yload(fd.read(), Loader=FullLoader)

    def _get_bearer_token(self) -> str:
        """
        Call API to get the bearer_token
        
        Returns
        --------
        The bearer token string
        """
        
        # Establish API session using token-based access
        hdr = {"Accept": "application/json",
               "x-api-key": f"{self.api_access_key}",
               "content_type": "application/json"}
        url = f"{self.api_base_url}{self.ENDPOINT_SESSIONS_ACCESS}"
        try:
            access_response = requests.post(url, headers=hdr, verify=False)
            access_response.raise_for_status()
        except HTTPError as http_err:
            raise Al2sAmVNError(f"POST: {url}: {http_err}")
        except Exception as e:
            raise Al2sAmVNError(f"POST: {url}: {e}")
        
        refresh_token = access_response.cookies['arroyoRefreshToken']
        
        # Exchange the refresh token
        hdr = {"Accept": "application/json",
               "Cookie": f"arroyoRefreshToken={refresh_token}",
               "content_type": "application/json"}
        url = f"{self.api_base_url}/v1/sessions/refresh"
        try:
            refresh_response = requests.get(url, headers=hdr, verify=False)
            access_response.raise_for_status()
        except HTTPError as http_err:
            raise Al2sAmVNError(f"POST: {url}: {http_err}")
        except Exception as e:
            raise Al2sAmVNError(f"GET: {url}: {e}")
        
        if 'Authorization' in refresh_response.headers:
            authorization_header = refresh_response.headers['Authorization']
        else:
            raise Al2sAmVNError(f'GET {url}: No Authorization Header in the response.')
        
        bearer_token = authorization_header
        
        return bearer_token
    
    @property
    def bearer_token(self):
        return self._get_bearer_token()
    
    def _list_cloudconnect(self) -> list:
        """
        Call API to list cloudconnect
        
        Returns
        --------
        The list of cloudconnects
        """
                
        # Establish API session using token-based access
        hdr = {"Accept": "application/json",
               "x-api-key": f"{self.api_access_key}",
               "content_type": "application/json",
               "Authorization": f"{self._auth}"}
        url = f"{self.api_base_url}{self.ENDPOINT_FOOTPRINT_CLOUDCONNECT}"
        try:
            list_response = requests.get(url, headers=hdr, verify=False)
            list_response.raise_for_status()
        except HTTPError as http_err:
            if list_response.status_code == 403:
                if self._retries > self.MAX_RETRIES:
                    self._retries = 0
                    raise Al2sAmVNError(f"GET: {url}: {http_err}")
                self._auth = self.bearer_token
                self._retries += 1
                return self._list_cloudconnect()
        except Exception as e:
            raise Al2sAmVNError(f"GET: {url}: {e}")
        
        if list_response.status_code not in self.ACCEPTED_STATUS_CODES:
            raise Exception(f"List cloudconnect error: {list_response.status_code}")
        
        return list_response.json()
    
    @property
    def cloudconnects(self):
        return self._list_cloudconnect()    
    
    def _list_myinterfaces(self) -> list:
        """
        Call API to list myinterfaces
        
        Returns
        --------
        The list of myinterfaces
        """
                
        # Establish API session using token-based access
        hdr = {"Accept": "application/json",
               "x-api-key": f"{self.api_access_key}",
               "content_type": "application/json",
               "Authorization": f"{self._auth}"}
        url = f"{self.api_base_url}{self.ENDPOINT_FOOTPRINT_MYINTERFACES}"
        try:
            list_response = requests.get(url, headers=hdr, verify=False)
            list_response.raise_for_status()
        except HTTPError as http_err:
            if list_response.status_code == 403:
                if self._retries > self.MAX_RETRIES:
                    self._retries = 0
                    raise Al2sAmVNError(f"GET: {url}: {http_err}")
                self._auth = self.bearer_token
                self._retries += 1
                return self._list_myinterfaces()
        except Exception as e:
            raise Al2sAmVNError(f"GET: {url}: {e}")
        
        return list_response.json()
    
    @property
    def myinterfaces(self):
        return self._list_myinterfaces()  
    
    def _retrieve_interface_availability(self, interface_id: str) -> dict:
        """
        Call API to retrieve the availability of given interface
        
        Parameters
        ----------
        interface_id: the id string of interface
        
        Returns
        --------
        The availability of the given interface
        """
        
        # Establish API session using token-based access
        hdr = {"Accept": "application/json",
               "x-api-key": f"{self.api_access_key}",
               "content_type": "application/json",
               "Authorization": f"{self._auth}"}
        url = f"{self.api_base_url}{self.ENDPOINT_VIRTUALNETWORKS_INTERFACES}/{interface_id}/availability"
        try:
            retrieve_response = requests.get(url, headers=hdr, verify=False)
            retrieve_response.raise_for_status()
        except HTTPError as http_err:
            if retrieve_response.status_code == 403:
                if self._retries > self.MAX_RETRIES:
                    self._retries = 0
                    raise Al2sAmVNError(f"GET: {url}: {http_err}")
                self._auth = self.bearer_token
                self._retries += 1
                return self._retrieve_interface_availability(interface_id)
            else:
                raise Al2sAmVNError(f"Get failed: {url}: {http_err}")
        except Exception as e:
            raise Al2sAmVNError(f"GET: {url}: {e}")
        
        self._retries = 0
        return retrieve_response.json()
    
    def _get_available_vlans(self, interface, interface_availability) -> list:
        """
        Extract the available VLAN ranges for the specified interface.
        
        parameters
        ----------
        interface: the interface
        interface_availability: the availablity
        
        Returns
        -------
        List of ranges of VLANs, e.g. [(1,10),(15, 20)]
        """
        
        if interface_availability['delegations']:
            vlan_range = []
            for delegation in interface_availability['delegations']:
                vlan_range += list(range(delegation['firstVlanId'], delegation['lastVlanId']))
        elif interface["type"] == "cloudconnect":
            provider = interface["cloudRegion"]["provider"]
            vlan_range = self.CLOUD_VLAN_RANGES[provider] if provider in self.CLOUD_VLAN_RANGES.keys() else list(range(1,4097))
        else:
            vlan_range = list(range(1,4096))
            
        usedVlans = []
        if interface_availability['inUse']:
            usedVlans = [v['vlanOuterId'] for v in interface_availability['inUse']]
        
        available_vlans = [i for i in vlan_range if i not in usedVlans]
        
        return list(to_ranges(available_vlans))
    
    def _get_bandwidth(self, interface, interface_availability) -> tuple:
        """
        Extract the bandwidth of the specified interface
        
        parameters
        ----------
        interface: the interface
        interface_availability: the availablity
        
        Returns
        -------
        tuple of the bandwidth (total, available)
        """
        bw = interface_availability['interface']['bandwidth']
        total = bw['total'] if isinstance(bw['total'], int) else 0
        avail = bw['available'] if isinstance(bw['available'], int) else 0
        return total, avail
    
        
    def list_endpoints(self, cloud_connect=True) -> list:
        """
        This generator returns a list of all AL2S EndPoints (device+interface) with attributes
        {   "name": "device_name:interface_name:...",
            "description": "",
            "device_name": "",
            "interface_name": "",
            "capacity": "100", # in gbps
            "vlan_range": [(101,110), (200,299)]
            other ...
        }
        
        Parameters:
        cloud_connect:  contain cloud endpoints if it is true
        
        Returns:
            list of endpoints
        """
        interface_list = []
        interface_list += self.myinterfaces
        if cloud_connect is True:
            interface_list += self.cloudconnects
            
        for interface in interface_list:
            endpoint = {}
            endpoint['name'] = interface['device']['name'] + ':' + interface['name']
            endpoint['description'] = interface['description']
            endpoint['device_name'] = interface['device']['name']
            endpoint['interface_name'] = interface['name']
            
            interface_availability = self._retrieve_interface_availability(interface['id'])
            endpoint['vlan_range'] = ranges_to_str(self._get_available_vlans(interface, interface_availability))
            endpoint['capacity'] = str(int(float(self._get_bandwidth(interface, interface_availability)[0]) / 1000.0))
            
            if interface['type'] == "cloudconnect":
                endpoint['cloud_region'] = interface_availability['interface']['cloudRegion']['code'].split('/')[-1]
                endpoint['cloud_provider'] = interface_availability['interface']['cloudRegion']["provider"]
            
            yield endpoint
            

class Al2sAmVNError(Exception):
    def __init__(self, msg: str):
        super().__init__(f'Al2sAmVNError: {msg}')
