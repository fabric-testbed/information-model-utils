import fim.user as f
from fimutil.al2s.oess import OessClient
import re
import os
from yaml import load as yload
from yaml import FullLoader
from ipaddress import IPv4Interface



class OessARM:
    """
    Generate AL2S AM resources information model.
    """

    def __init__(self, *, config_file=None, isis_link_validation=False):
        self.topology = None
        self.config = self.get_config(config_file)
        self.oess = OessClient(config=self.config)
        self.sites_metadata = None
        if 'sites_config' in self.config:
            sites_config_file = self.config['sites_config']
            if not os.path.isfile(sites_config_file):
                raise OessAmArmError('sites_config file does not exists at: ' + sites_config_file)
            with open(sites_config_file, 'r') as fd:
                self.sites_metadata = yload(fd.read(), Loader=FullLoader)



class OessAmArmError(Exception):
    def __init__(self, msg: str):
        super().__init__(f'OessAmArmError: {msg}')
