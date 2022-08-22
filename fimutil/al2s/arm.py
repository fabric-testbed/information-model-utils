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

    def build_topology(self) -> None:
        # start topology model
        self.topology = f.SubstrateTopology()
        model_name = 'AL2S OESS'
        site_name = "Internet2"
        node_name = "AL2S"
        node_nid = "node+" + node_name
        switch = self.topology.add_node(name=node_name, model=model_name, site=site_name,
                                        node_id=node_nid, ntype=f.NodeType.Switch,
                                        capacities=f.Capacities(unit=1),
                                        labels=f.Labels(local_name=node_name))
        # add L2 NetworkService
        l2_ns_labs = f.Labels()
        # ? add AL2S site-wide labels
        l2_ns = switch.add_network_service(name=switch.name + '-ns', layer=f.Layer.L2, labels=l2_ns_labs,
                                           node_id=switch.node_id + '-ns', nstype=f.ServiceType.MPLS)


        interfaces = self.oess.interfaces()
        for

class OessAmArmError(Exception):
    def __init__(self, msg: str):
        super().__init__(f'OessAmArmError: {msg}')
