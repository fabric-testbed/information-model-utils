import fim.user as f
from fimutil.netam.nso import NsoClient
from fimutil.netam.sr_pce import SrPceClient
import re
import os
from yaml import load as yload
from yaml import FullLoader
from ipaddress import IPv4Interface


def _in_same_network(ip1: str, ip2: str, netmask: str) -> bool:
    return IPv4Interface(f'{ip1}/{netmask}').network == IPv4Interface(f'{ip2}/{netmask}').network


class NetworkARM:
    """
    Generate Network AM resources information model.
    """

    def __init__(self, *, config_file=None, isis_link_validation=False):
        self.topology = None
        self.config = self.get_config(config_file)
        self.nso = NsoClient(config=self.config)
        if isis_link_validation:
            self.sr_pce = SrPceClient(config=self.config)
        else:
            self.sr_pce = None
        self.valid_ipv4_links = None
        self.sites_metadata = None
        if 'sites_config' in self.config:
            sites_config_file = self.config['sites_config']
            if not os.path.isfile(sites_config_file):
                raise NetAmArmError('sites_config file does not exists at: ' + sites_config_file)
            with open(sites_config_file, 'r') as fd:
                self.sites_metadata = yload(fd.read(), Loader=FullLoader)

    def _get_device_interfaces(self) -> list:
        devs = self.nso.devices()
        for dev in devs:
            dev_name = dev['name']
            ifaces = self.nso.interfaces(dev_name)
            if ifaces:
                for iface in list(ifaces):
                    # only keep interfaces in up status and of "*GigE0/1/2*" pattern
                    if iface['admin-status'] == 'up' and re.search('GigE\d/\d/\d', iface['name']):
                        # get rid of 'statistics' attributes
                        iface.pop('statistics', None)
                        continue
                    ifaces.remove(iface)
                dev['interfaces'] = ifaces
        return devs

    def build_topology(self) -> None:
        # firstly get SR-PCE active links
        if self.sr_pce is not None:
            self.sr_pce.get_topology_json()
            self.valid_ipv4_links = self.sr_pce.get_ipv4_links()
        # start topology model
        self.topology = f.SubstrateTopology()
        nodes = self._get_device_interfaces()
        port_ipv4net_map = {}
        for node in nodes:
            # add switch node
            node_name = node['name']
            # TODO: get model name from NSO
            model_name = 'NCS 55A1-36H'
            # TODO: get official site name from Ralph (or in switch description string) ?
            re_site = re.findall(r'(\w+)-.+', node_name)
            if re_site is None or len(re_site) == 0:
                continue
            site_name = str.upper(re_site[0])
            node_nid = "node+" + node_name + ":ip+" + node['address']
            switch = self.topology.add_node(name=node_name, model=model_name, site=site_name,
                                            node_id=node_nid, ntype=f.NodeType.Switch,
                                            capacities=f.Capacities(unit=1),
                                            labels=f.Labels(local_name=node_name, ipv4=node['address']))
            l2_ns_labs = f.Labels()
            site_info = None
            # add FABIpv4 and FABIpv6 NetworkService
            if self.sites_metadata and site_name in self.sites_metadata:
                site_info = self.sites_metadata[site_name]
                if 'l2_vlan_range' in site_info:
                    l2_ns_labs = f.Labels.update(l2_ns_labs, vlan_range=site_info['l2_vlan_range'])
                ipv4_ns_labs = f.Labels()
                if 'ipv4_net' in site_info:
                    ipv4_ns_labs = f.Labels.update(ipv4_ns_labs, ipv4_subnet=site_info['ipv4_net'])
                if 'ipv4_vlan_range' in site_info:
                    ipv4_ns_labs = f.Labels.update(ipv4_ns_labs, vlan_range=site_info['ipv4_vlan_range'])
                ipv4_ns = switch.add_network_service(name=switch.name + '-ipv4-ns', layer=f.Layer.L3, labels=ipv4_ns_labs,
                                                        node_id=switch.node_id + '-ipv4-ns', nstype=f.ServiceType.FABNetv4)
                ipv6_ns_labs = f.Labels()
                if 'ipv6_net' in site_info:
                    ipv6_ns_labs = f.Labels.update(ipv6_ns_labs, ipv6_subnet=site_info['ipv6_net'])
                if 'ipv6_vlan_range' in site_info:
                    ipv6_ns_labs = f.Labels.update(ipv6_ns_labs, vlan_range=site_info['ipv6_vlan_range'])
                ipv6_ns = switch.add_network_service(name=switch.name + '-ipv6-ns', layer=f.Layer.L3, labels=ipv6_ns_labs,
                                                         node_id=switch.node_id + '-ipv6-ns', nstype=f.ServiceType.FABNetv6)

            # add L2 NetworkService
            l2_ns = switch.add_network_service(name=switch.name + '-ns', layer=f.Layer.L2, labels=l2_ns_labs,
                                            node_id=switch.node_id + '-ns', nstype=f.ServiceType.MPLS)
            # add ports
            if 'interfaces' in node:
                for port in node['interfaces']:
                    port_name = port['name']
                    port_mac = port['phys-address']
                    port_nid = f"port+{node_name}:{port_name}"
                    speed_gbps = int(int(port['speed']) / 1000000000)
                    # add capabilities
                    port_caps = f.Capacities(bw=speed_gbps)
                    # add labels (vlan ??)
                    port_labs = f.Labels(local_name=port_name, mac=port_mac)
                    if 'ietf-ip:ipv4' in port and 'address' in port['ietf-ip:ipv4']:
                        for ipv4_addr in port['ietf-ip:ipv4']['address']:
                            ipv4_addr_ip = ipv4_addr['ip']
                            ipv4_addr_mask = ipv4_addr['netmask']
                            port_labs = f.Labels().update(port_labs, local_name=port_name, ipv4=ipv4_addr_ip)
                            port_ipv4net_map[port_nid] = {"ip": ipv4_addr_ip, "netmask": ipv4_addr_mask}
                            # only take the first
                            break
                    if 'ietf-ip:ipv6' in port and 'address' in port['ietf-ip:ipv6']:
                        for ipv6_addr in port['ietf-ip:ipv6']['address']:
                            ipv6_addr_ip = ipv6_addr['ip']
                            ipv6_addr_prefix_len = ipv6_addr['prefix-length']
                            port_labs = f.Labels().update(port_labs, local_name=port_name, ipv6=ipv6_addr_ip)
                            # only take the first
                            break
                    sp = l2_ns.add_interface(name=port_name, itype=f.InterfaceType.TrunkPort,
                                             node_id=port_nid, labels=port_labs,
                                             capacities=port_caps)
                    if port_nid in port_ipv4net_map:
                        port_ipv4net_map[port_nid]["interface"] = sp
                    # add external facility stitching links
                    # refer to port_name as stitch_port

                    # add facility_ports based on stitcihng metadata
                    if site_info and 'facility_ports' in site_info:
                        for facility_name, stitch_info in site_info['facility_ports'].items():
                            if 'stitch_port' not in stitch_info:
                                raise NetAmArmError('no peer / stitch_port defined for facility_port: ' + facility_name)
                            stitch_port_name = stitch_info['stitch_port'].replace(' ', '')
                            if stitch_port_name != port_name:
                                continue
                            # build facility_port out of stitch_info
                            facility_port_labs = f.Labels()
                            if 'vlan_range' in stitch_info:
                                facility_port_labs = f.Labels.update(facility_port_labs,
                                                                     vlan_range=stitch_info['vlan_range'])
                            if 'ipv4_net' in stitch_info:
                                facility_port_labs = f.Labels.update(facility_port_labs,
                                                                     ipv4_subnet=stitch_info['ipv4_net'])
                            if 'ipv6_net' in stitch_info:
                                facility_port_labs = f.Labels.update(facility_port_labs,
                                                                     ipv6_subnet=stitch_info['ipv6_net'])
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
                                                             site=facility_name,
                                                             labels=facility_port_labs, capacities=facility_port_caps)
                            # connect it to the switch port via link
                            self.topology.add_link(name=facility_name + '-link',
                                                   node_id=f'{port_nid}:facility+{facility_name}+link',
                                                   ltype=f.LinkType.L2Path, # could be Patch too
                                                   interfaces=[sp, fac.interface_list[0]]) # there is only one interface on the facility

        # add FABRIC Testbed internal links
        for k in list(port_ipv4net_map):
            if k not in port_ipv4net_map:
                continue
            v = port_ipv4net_map[k]
            port_ip = v['ip']
            port_netmask = v['netmask']
            port_sp = v['interface']
            port_ipv4net_map.pop(k, None)
            # look up paring remote interface
            for k_r in list(port_ipv4net_map):
                v_r = port_ipv4net_map[k_r]
                port_ip_r = v_r['ip']
                has_link = False
                if self.valid_ipv4_links is None: # form link if local and remote ipv4 addresses in same subnet
                    port_netmask_r = v_r['netmask']
                    if port_netmask == port_netmask_r and _in_same_network(port_ip, port_ip_r, port_netmask):
                        has_link = True
                elif f'{port_ip}-{port_ip_r}' in self.valid_ipv4_links:
                    has_link = True
                if has_link:
                    port_ipv4net_map.pop(k_r, None)
                    port_sp_r = v_r['interface']
                    # add link
                    link_nid = f"link:local-{port_sp.node_id}:remote-{port_sp_r.node_id}"
                    link = self.topology.add_link(name=f'{port_sp.node_id} to {port_sp_r.node_id}', ltype=f.LinkType.L2Path,
                                                  layer=f.Layer.L2,
                                                  interfaces=[port_sp, port_sp_r],
                                                  node_id=link_nid)

    def delegate_topology(self, delegation: str) -> None:
        self.topology.single_delegation(delegation_id=delegation,
                                        label_pools=f.Pools(atype=f.DelegationType.LABEL),
                                        capacity_pools=f.Pools(atype=f.DelegationType.CAPACITY))

    def write_topology(self, file_name: str) -> None:
        if not self.topology:
            raise NetAmArmError("Topology is None")
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


class NetAmArmError(Exception):
    def __init__(self, msg: str):
        super().__init__(f'NetAmArmError: {msg}')
