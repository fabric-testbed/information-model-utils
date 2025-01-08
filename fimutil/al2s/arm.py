import fim.user as f
import fim.slivers.capacities_labels as caplab
from fim.slivers.interface_info import InterfaceType
from fim.slivers.network_node import NodeType
from fim.slivers.network_service import ServiceType

from fimutil.al2s.al2s_api import Al2sClient
from fimutil.al2s.cloud_cfg import REGION_NAME_MAP
from yaml import load as yload
from yaml import FullLoader
import logging
import os
import re



def _update_vlan_label(labs, vlan: str):
    if '-' not in vlan and ',' not in vlan:
        return f.Labels.update(labs, vlan=vlan)
    else:
        try:
            return f.Labels.update(labs, vlan_range=vlan.split(','))
        except caplab.LabelException:
            return labs


def _tralsate_cloud_region_name(name: str):
    if name not in REGION_NAME_MAP.keys():
        for k in REGION_NAME_MAP.keys():
            if k in name:
                return REGION_NAME_MAP[k]
        return name
    else:
        return REGION_NAME_MAP[name]


class Al2sARM:
    """
    Generate AL2S AM resources information model.
    """

    def __init__(self, *, config_file=None, isis_link_validation=False):
        self.topology = None
        self.config = self.get_config(config_file)
        self.al2s = Al2sClient(config=self.config)
        self.site_info = None
        if self.config and 'sites_config' in self.config:
            sites_config_file = self.config['sites_config']
            if not os.path.isfile(sites_config_file):
                raise Al2sAmArmError('sites_config file does not exists at: ' + sites_config_file)
            with open(sites_config_file, 'r') as fd:
                sites_metadata = yload(fd.read(), Loader=FullLoader)
                if 'AL2S' in sites_metadata:
                    self.site_info = sites_metadata['AL2S']

    def build_topology(self) -> None:
        # start topology model
        self.topology = f.SubstrateTopology()
        model_name = 'AL2S VirtualNetworks'
        site_name = "AL2S"
        node_name = "AL2S"
        node_nid = "node+" + node_name
        switch = self.topology.add_node(name=node_name, model=model_name, site=site_name,
                                        node_id=node_nid, ntype=f.NodeType.Switch,
                                        capacities=f.Capacities(unit=1),
                                        labels=f.Labels(local_name=node_name), stitch_node=False)
        # add L2 NetworkService
        l2_ns_labs = f.Labels()
        # ? add AL2S site-wide labels
        l2_ns = switch.add_network_service(name=switch.name + '-ns', layer=f.Layer.L2, labels=l2_ns_labs,
                                           node_id=switch.node_id + '-ns', nstype=f.ServiceType.MPLS,
                                           stitch_node=False)

        l3vpn_ns_labs = f.Labels()
        l3vpn_ns_labs = f.Labels.update(l3vpn_ns_labs, asn='55038')
        # ? add more AL2S site-wide labels (per-site vlan_range and ipv4_range for bgp peering)
        l3vpn_ns = switch.add_network_service(name=switch.name + '-l3vpn-ns', layer=f.Layer.L3,
                                              labels=l3vpn_ns_labs,
                                              node_id=switch.node_id + '-l3vpn-ns', nstype=f.ServiceType.L3VPN,
                                              stitch_node=False)

        # TODO: Add ServiceController ?

        cloud_facs = {}  # cloud facility name to network service map
        for port in self.al2s.list_endpoints():
            port_name = port['name']
            # port_mac = port['phys-address'] # add to port_labs if available
            port_nid = f"port+al2s:{port_name}"
            speed_gbps = int(port['capacity'])
            vlan_range = port['vlan_range']
            if vlan_range == '':
                logging.warning(f'Port {port_name} has empty vlan range - skip')
                continue
            # add capabilities
            port_caps = f.Capacities(bw=speed_gbps)
            # add labels
            port_labs = f.Labels(device_name=port['device_name'], local_name=port['interface_name'])
            port_labs = _update_vlan_label(port_labs, vlan_range)
            # TODO: identify FABRIC facing interface
            #   Add WAN switch node, network_service and ports with stitch_node=True
            #   Add Links with stitch_node=False
            #   ++ The peering WAN site / port IDs will come from config inventory.
            #   ++ Or ask Internet2 to incldue peering into FABRIC entity->interface->description instead

            sp = l2_ns.add_interface(name=port_name, itype=f.InterfaceType.TrunkPort,
                                     node_id=port_nid, labels=port_labs,
                                     capacities=port_caps, stitch_node=False)

            # add facility_ports based on stitching metadata
            if 'cloud_provider' in port:
                # if port['cloud_interconnect_type'] == 'aws-hosted-connection' \
                #         or port['cloud_interconnect_type'] == 'gcp-partner-interconnect' \
                #         or port['cloud_interconnect_type'] == 'azure-express-route':
                if True:
                    # facility by cloud peering port
                    fac_name = re.sub("\s|:|\(|\)", "-", f"Cloud-Facility:{port['cloud_provider']}")
                    # print(f'Facility: {fac_name}\n')
                    faci_name = re.sub("\s|:|\(|\)", "-",
                                       f"{port['cloud_provider']}:{port['cloud_region']}:{port_name}")
                    # facility_port attributes
                    facility_port_labs = f.Labels()
                    facility_port_labs = _update_vlan_label(facility_port_labs, vlan_range)
                    facility_port_labs = f.Labels.update(facility_port_labs,
                                                         region=_tralsate_cloud_region_name(port['cloud_region']))
                    facility_port_labs = f.Labels.update(facility_port_labs, device_name=port['device_name'])
                    facility_port_labs = f.Labels.update(facility_port_labs, local_name=port['interface_name'])
                    facility_port_caps = f.Capacities()
                    facility_port_caps = f.Labels.update(facility_port_caps, bw=speed_gbps)
                    if fac_name in cloud_facs:
                        facs = cloud_facs[fac_name]
                        # add an interface / facility_port to the facility
                        faci = facs.add_interface(name=faci_name, node_id=f"{port_nid}:{fac_name}:facility_port",
                                                  itype=InterfaceType.FacilityPort,
                                                  labels=facility_port_labs,
                                                  capacities=facility_port_caps)
                        self.topology.add_link(name=fac_name + '-link:' + port_name,
                                               node_id=f'{port_nid}:facility+{fac_name}+link',
                                               ltype=f.LinkType.L2Path,  # could be Patch too
                                               interfaces=[sp, faci])  # add additional interface to the facility
                    else:
                        facn = self.topology.add_node(name=fac_name, node_id=f'{port_nid}:facility+{fac_name}',
                                                      site=re.sub("\s|:|\(|\)", "-", port['cloud_provider']),
                                                      ntype=NodeType.Facility)
                        facs = facn.add_network_service(name=facn.name + '-ns',
                                                        node_id=f'{port_nid}:facility+{fac_name}-ns',
                                                        nstype=ServiceType.VLAN)
                        faci = facs.add_interface(name=faci_name, node_id=f"{port_nid}:{fac_name}:facility_port",
                                                  itype=InterfaceType.FacilityPort,
                                                  labels=facility_port_labs,
                                                  capacities=facility_port_caps)

                        if 'description' in port:
                            faci.details = port['description']
                        # connect it to the switch port via link
                        self.topology.add_link(name=fac_name + '-link:' + port_name,
                                               node_id=f'{port_nid}:facility+{fac_name}+link',
                                               ltype=f.LinkType.L2Path,  # could be Patch too
                                               interfaces=[sp, faci])  # add first interface to the facility
                        cloud_facs[fac_name] = facs

    def delegate_topology(self, delegation: str) -> None:
        self.topology.single_delegation(delegation_id=delegation,
                                        label_pools=f.Pools(atype=f.DelegationType.LABEL),
                                        capacity_pools=f.Pools(atype=f.DelegationType.CAPACITY))

    def write_topology(self, file_name: str) -> None:
        if not self.topology:
            raise Al2sAmArmError("Topology is None")
        self.topology.serialize(file_name=file_name)

    def get_config(self, config_file):
        if not config_file:
            config_file = os.getenv('HOME') + '/.netam.conf'
            if not os.path.isfile(config_file):
                config_file = '/etc/netam.conf'
                if not os.path.isfile(config_file):
                    return None
        with open(config_file, 'r') as fd:
            return yload(fd.read(), Loader=FullLoader)


class Al2sAmArmError(Exception):
    def __init__(self, msg: str):
        super().__init__(f'Al2sAmArmError: {msg}')
