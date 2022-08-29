import fim.user as f
from fimutil.al2s.oess import OessClient
import os
from yaml import load as yload
from yaml import FullLoader


class OessARM:
    """
    Generate AL2S AM resources information model.
    """

    def __init__(self, *, config_file=None, isis_link_validation=False):
        self.topology = None
        self.config = self.get_config(config_file)
        self.oess = OessClient(config=self.config)
        self.site_info = None
        if 'sites_config' in self.config:
            sites_config_file = self.config['sites_config']
            if not os.path.isfile(sites_config_file):
                raise OessAmArmError('sites_config file does not exists at: ' + sites_config_file)
            with open(sites_config_file, 'r') as fd:
                sites_metadata = yload(fd.read(), Loader=FullLoader)
                if 'AL2S' in sites_metadata:
                    self.site_info = sites_metadata['AL2S']

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
                                        labels=f.Labels(local_name=node_name), stitch_node=True)
        # add L2 NetworkService
        l2_ns_labs = f.Labels()
        # ? add AL2S site-wide labels
        l2_ns = switch.add_network_service(name=switch.name + '-ns', layer=f.Layer.L2, labels=l2_ns_labs,
                                           node_id=switch.node_id + '-ns', nstype=f.ServiceType.MPLS,
                                           stitch_node=True)

        l3vpn_ns_labs = f.Labels()
        l3vpn_ns_labs = f.Labels.update(l3vpn_ns_labs, asn='398900')
        # ? add more AL2S site-wide labels (per-site vlan_range and ipv4_range for bgp peering)
        l3vpn_ns = switch.add_network_service(name=switch.name + '-l3vpn-ns', layer=f.Layer.L3,
                                              labels=l3vpn_ns_labs,
                                              node_id=switch.node_id + '-l3vpn-ns', nstype=f.ServiceType.L3VPN,
                                              stitch_node=True)

        # TODO: Add ServiceController ?

        al2s_eps = self.oess.endpoints()
        for port in al2s_eps:
            port_name = port['name']
            # port_mac = port['phys-address'] # add to port_labs if available
            port_nid = f"port+al2s:{port_name}"
            speed_gbps = int(port['capacity'])
            vlan_range = port['vlan_range']
            # add capabilities
            port_caps = f.Capacities(bw=speed_gbps)
            # add labels
            port_labs = f.Labels(local_name=port_name, vlan_range=vlan_range)

            # TODO: identify Cloud facing interface
            # ? add ipv4 and ipv6 range from site-config
            # ? add controller_url etc.

            # TODO: identify FABRIC facing interface
            # ? stitch_node = True (set all interfaces to True for now)

            sp = l2_ns.add_interface(name=port_name, itype=f.InterfaceType.TrunkPort,
                                     node_id=port_nid, labels=port_labs,
                                     capacities=port_caps, stitch_node=True)


            # add facility_ports based on stitching metadata
            if self.site_info and 'facility_ports' in self.site_info:
                for facility_name, stitch_info in self.site_info['facility_ports'].items():
                    if 'stitch_port' not in stitch_info:
                        raise OessAmArmError('no peer / stitch_port defined for facility_port: ' + facility_name)
                    stitch_port_name = stitch_info['stitch_port'].replace(' ', '')
                    if stitch_port_name != port_name:
                        continue
                    # build facility_port out of stitch_info
                    facility_port_labs = f.Labels()
                    if 'vlan_range' in stitch_info:
                        if '-' in stitch_info['vlan_range']:
                            facility_port_labs = f.Labels.update(facility_port_labs,
                                                                 vlan_range=stitch_info['vlan_range'])
                        else:
                            facility_port_labs = f.Labels.update(facility_port_labs,
                                                                 vlan=stitch_info['vlan_range'])
                    if 'ipv4_net' in stitch_info:
                        facility_port_labs = f.Labels.update(facility_port_labs,
                                                             ipv4_subnet=stitch_info['ipv4_net'])
                    if 'ipv6_net' in stitch_info:
                        facility_port_labs = f.Labels.update(facility_port_labs,
                                                             ipv6_subnet=stitch_info['ipv6_net'])
                    if 'local_device' in stitch_info:
                        facility_port_labs = f.Labels.update(facility_port_labs,
                                                             device_name=stitch_info['local_port'])
                    if 'local_port' in stitch_info:
                        facility_port_labs = f.Labels.update(facility_port_labs,
                                                             local_name=stitch_info['local_port'])
                    facility_port_caps = f.Capacities()
                    if 'mtu' in stitch_info:
                        facility_port_caps = f.Labels.update(facility_port_caps, mtu=stitch_info['mtu'])
                    if 'bandwidth' in stitch_info:
                        facility_port_caps = f.Labels.update(facility_port_caps, bw=stitch_info['bandwidth'])
                    # create a facility with a VLAN network service and a single FacilityPort interface
                    fac = self.topology.add_facility(name=facility_name,
                                                     node_id=f'{port_nid}:facility+{facility_name}',
                                                     site=site_name,
                                                     labels=facility_port_labs, capacities=facility_port_caps)
                    if 'description' in stitch_info:
                        fac.interface_list[0].details = stitch_info['description']
                    # connect it to the switch port via link
                    self.topology.add_link(name=facility_name + '-link',
                                           node_id=f'{port_nid}:facility+{facility_name}+link',
                                           ltype=f.LinkType.L2Path,  # could be Patch too
                                           interfaces=[sp, fac.interface_list[
                                               0]])  # there is only one interface on the facility

    def delegate_topology(self, delegation: str) -> None:
        self.topology.single_delegation(delegation_id=delegation,
                                        label_pools=f.Pools(atype=f.DelegationType.LABEL),
                                        capacity_pools=f.Pools(atype=f.DelegationType.CAPACITY))

    def write_topology(self, file_name: str) -> None:
        if not self.topology:
            raise OessAmArmError("Topology is None")
        self.topology.serialize(file_name=file_name)

    def get_config(self, config_file):
        if not config_file:
            config_file = os.getenv('HOME') + '/.netam.conf'
            if not os.path.isfile(config_file):
                config_file = '/etc/netam.conf'
                if not os.path.isfile(config_file):
                    raise Exception('Config file not found: %s' % config_file)
        with open(config_file, 'r') as fd:
            return yload(fd.read(), Loader=FullLoader)


class OessAmArmError(Exception):
    def __init__(self, msg: str):
        super().__init__(f'OessAmArmError: {msg}')
