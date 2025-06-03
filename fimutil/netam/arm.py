import fim.user as f
from fimutil.netam.nso import NsoClient
from fimutil.netam.sr_pce import SrPceClient
import re
import os
from yaml import load as yload
from yaml import FullLoader
from ipaddress import IPv4Interface
from ipaddress import IPv4Network
import logging


def _in_same_network(ip1: str, ip2: str, netmask: str) -> bool:
    return IPv4Interface(f'{ip1}/{netmask}').network == IPv4Interface(f'{ip2}/{netmask}').network


def _normalize_netmask(prefix: str) -> str:
    # compatible to prefix string
    if re.fullmatch(r'(\d+\.\d+\.\d+\.\d+)', prefix):
        return prefix
    # compatible to slash format
    if prefix[0] == '/':
        prefix_length = int(prefix.lstrip('/'))
    else:
        prefix_length = int(prefix)
    try:
        if 0 <= prefix_length <= 32:
            return str(IPv4Network(f'0.0.0.0/{prefix_length}', strict=False).netmask)
        else:
            raise ValueError("Prefix length must be between 0 and 32.")
    except ValueError as e:
        return f"Invalid input: {e}"


def _generate_device_model_ciena_saos10(site_info: dict, dev: dict):
    dev_name = dev['name']
    re_site = re.findall(r'(\w+)-.+', dev_name)
    site_name = str.upper(re_site[0])
    if 'site_etc' not in site_info:
        return
    site_etc = site_info['site_etc']
    dev['interfaces'] = []
    if 'ifopts' in site_etc:
        for name in site_etc['ifopts']:
            iface = site_etc['ifopts'][name]
            iface['name'] = name
            dev['interfaces'].append(iface)
        dev['loopback_ipv4'] = site_etc['loopback_ipv4']
        dev['loopback_ipv6'] = site_etc['loopback_ipv6']
    return

class NetworkARM:
    """
    Generate Network AM resources information model.
    """

    def __init__(self, *, config_file=None, isis_link_validation=False, skip_device=None):
        self.topology = None
        self.config = self.get_config(config_file)
        self.nso = NsoClient(config=self.config)
        if isis_link_validation:
            self.sr_pce = SrPceClient(config=self.config)
        else:
            self.sr_pce = None
        if skip_device is not None:
            self.skipped_devices = skip_device.split(',')
        else:
            self.skipped_devices = []
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
            re_site = re.findall(r'(\w+)-.+', dev_name)
            site_name = str.upper(re_site[0])
            device_type = self._get_device_type(site_name)
            if device_type and 'cisco' not in device_type.lower():
                globals()[f"_generate_device_model_{device_type}"](self.sites_metadata[site_name], dev)
            # skip the devices that has no p2p links configured
            if not self._has_p2p_links(dev_name):
                continue
            # skip the devices that explicitly asked to skip
            if dev_name in self.skipped_devices:
                continue
            logging.info(f"Fetching {site_name} interfaces from NSO")
            ifaces = self.nso.interfaces(dev_name)
            isis_ifaces = self.nso.isis_interfaces(dev_name)
            if ifaces:
                if isis_ifaces is None:
                    raise NetAmArmError(f"Device '{dev_name}' has no active isis interface - fix that or consider '--skip-device device-name'")
                for iface in list(ifaces):
                    # get loopback addresses
                    if iface['name'] == 'Loopback0':
                        if 'ietf-ip:ipv4' in iface:
                            dev['loopback_ipv4'] = iface['ietf-ip:ipv4']['address'][0]['ip']
                        if 'ietf-ip:ipv6' in iface:
                            dev['loopback_ipv6'] = iface['ietf-ip:ipv6']['address'][0]['ip']
                        continue
                    # skip if not an isis l2 p2p interfaces
                    is_isis_iface = False
                    for isis_iface in isis_ifaces:
                        if iface['name'] == isis_iface['name']:
                            is_isis_iface = True
                    # only keep interfaces in up status and of "*GigE0/1/2*" pattern
                    if re.search('GigE\d/\d/\d|Bundle-Ether\d+', iface['name']):
                        iface.pop('statistics', None)  # remove 'statistics' attributes
                        if is_isis_iface:
                            iface['isis'] = True  # mark ISIS interface
                        continue
                    ifaces.remove(iface)
                dev['interfaces'] = ifaces
        return devs

    def _has_p2p_links(self, dev_name) -> bool:
        re_site = re.findall(r'(\w+)-.+', dev_name)
        site_name = str.upper(re_site[0])
        if self.sites_metadata and site_name in self.sites_metadata:
            site_info = self.sites_metadata[site_name]
            if 'p2p_links' in site_info:
                return bool(site_info['p2p_links'])
        return False

    def _get_device_type(self, site_name) -> str:
        if self.sites_metadata and site_name in self.sites_metadata:
            site_info = self.sites_metadata[site_name]
            if 'site_etc' in site_info and 'devtype' in site_info['site_etc']:
                return site_info['site_etc']['devtype']
        return None


    def _get_port_link_cap(self, site_name, port_name) -> dict:
        ret_cap_dict = {}
        if self.sites_metadata and site_name in self.sites_metadata:
            site_info = self.sites_metadata[site_name]
            if 'p2p_links' in site_info:
                if ' ' not in port_name:
                    port_name = port_name.replace("GigE", "GigE ")
                    port_name = port_name.replace("Bundle-Ether", "Bundle-Ether ")
                if port_name in site_info['p2p_links']:
                    port_info = site_info['p2p_links'][port_name]
                    if 'port-capacity' in port_info:
                        ret_cap_dict['port-capacity'] = port_info['port-capacity']
                    if 'link-capacity' in port_info:
                        ret_cap_dict['link-capacity'] = port_info['link-capacity']
                    if 'link-reserve-capacity' in port_info:
                        ret_cap_dict['link-reserve-capacity'] = port_info['link-reserve-capacity']
        return ret_cap_dict


    def _get_link_type(self, site_name, port_name) -> str:
        if self.sites_metadata and site_name in self.sites_metadata:
            site_info = self.sites_metadata[site_name]
            if 'p2p_links' in site_info:
                if ' ' not in port_name:
                    port_name = port_name.replace("GigE", "GigE ")
                    port_name = port_name.replace("Bundle-Ether", "Bundle-Ether ")
                if port_name in site_info['p2p_links']:
                    port_info = site_info['p2p_links'][port_name]
                    if 'ltype' in port_info:
                        return port_info['ltype']
        # by default, return `l1path`
        return 'l1path'


    def build_topology(self) -> None:
        # firstly get SR-PCE active links
        if self.sr_pce is not None:
            self.sr_pce.get_topology_json()
            self.valid_ipv4_links = self.sr_pce.get_ipv4_links()
        # start topology model
        self.topology = f.SubstrateTopology()
        nodes = self._get_device_interfaces()
        port_ipv4net_map = {}
        port_link_cap_map = {}

        # add AL2S abstract switch node and ns
        al2s_node = self.topology.add_node(name='AL2S', site='AL2S',
                                           node_id='node+AL2S', ntype=f.NodeType.Switch,  stitch_node=True,
                                           capacities=f.Capacities(unit=1))
        al2s_l2_ns = al2s_node.add_network_service(name=al2s_node.name + '-ns', layer=f.Layer.L2,  stitch_node=True,
                                                   node_id=al2s_node.node_id + '-ns', nstype=f.ServiceType.MPLS)
        regexVlanPort = re.compile(r'\/\d+/\d+\/\d+\.\d+$') # ignore BE (like Bundle-Ether101.3000) for site ports
        # add site nodes
        for node in nodes:
            if 'interfaces' not in node:
                continue
            # add switch node
            node_name = node['name']
            logging.info(f"Building model for node {node_name}")
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
                    l2_ns_labs = f.Labels.update(l2_ns_labs, vlan_range=site_info['l2_vlan_range'].split(','))
                ipv4_ns_labs = f.Labels()
                if 'ipv4_net' in site_info:
                    ipv4_ns_labs = f.Labels.update(ipv4_ns_labs, ipv4_subnet=site_info['ipv4_net'])
                if 'ipv4_vlan_range' in site_info:
                    ipv4_ns_labs = f.Labels.update(ipv4_ns_labs, vlan_range=site_info['ipv4_vlan_range'].split(','))
                if 'loopback_ipv4' in node:
                    ipv4_ns_labs = f.Labels.update(ipv4_ns_labs, ipv4=node['loopback_ipv4'])
                ipv4_ns = switch.add_network_service(name=switch.name + '-ipv4-ns', layer=f.Layer.L3,
                                                     labels=ipv4_ns_labs,
                                                     node_id=switch.node_id + '-ipv4-ns', nstype=f.ServiceType.FABNetv4)
                ipv4ext_ns_labs = f.Labels()
                if 'ipv4_public_net' in site_info:
                    ipv4ext_ns_labs = f.Labels.update(ipv4ext_ns_labs, ipv4_subnet=site_info['ipv4_public_net'])
                if 'ipv4_vlan_range' in site_info:
                    ipv4ext_ns_labs = f.Labels.update(ipv4ext_ns_labs, vlan_range=site_info['ipv4_vlan_range'].split(','))
                ipv4ext_ns = switch.add_network_service(name=switch.name + '-ipv4ext-ns', layer=f.Layer.L3,
                                                     labels=ipv4ext_ns_labs,
                                                     node_id=switch.node_id + '-ipv4ext-ns', nstype=f.ServiceType.FABNetv4Ext)

                ipv6_ns_labs = f.Labels()
                if 'ipv6_net' in site_info:
                    ipv6_ns_labs = f.Labels.update(ipv6_ns_labs, ipv6_subnet=site_info['ipv6_net'])
                if 'ipv6_vlan_range' in site_info:
                    ipv6_ns_labs = f.Labels.update(ipv6_ns_labs, vlan_range=site_info['ipv6_vlan_range'].split(','))
                if 'loopback_ipv6' in node:
                    ipv6_ns_labs = f.Labels.update(ipv6_ns_labs, ipv6=node['loopback_ipv6'])
                ipv6_ns = switch.add_network_service(name=switch.name + '-ipv6-ns', layer=f.Layer.L3,
                                                     labels=ipv6_ns_labs,
                                                     node_id=switch.node_id + '-ipv6-ns', nstype=f.ServiceType.FABNetv6)
                ipv6ext_ns_labs = f.Labels()
                if 'ipv6_net' in site_info:
                    ipv6ext_ns_labs = f.Labels.update(ipv6ext_ns_labs, ipv6_subnet=site_info['ipv6_net'])
                if 'ipv6_vlan_range' in site_info:
                    ipv6ext_ns_labs = f.Labels.update(ipv6ext_ns_labs, vlan_range=site_info['ipv6_vlan_range'].split(','))
                ipv6ext_ns = switch.add_network_service(name=switch.name + '-ipv6ext-ns', layer=f.Layer.L3,
                                                     labels=ipv6ext_ns_labs,
                                                     node_id=switch.node_id + '-ipv6ext-ns', nstype=f.ServiceType.FABNetv6Ext)

                l3vpn_ns_labs = f.Labels()
                l3vpn_ns_labs = f.Labels.update(l3vpn_ns_labs, asn='398900')
                # TODO: add more labels (per-site vlan_range and ipv4_range for bgp peering)
                l3vpn_ns = switch.add_network_service(name=switch.name + '-l3vpn-ns', layer=f.Layer.L3,
                                                     labels=l3vpn_ns_labs,
                                                     node_id=switch.node_id + '-l3vpn-ns', nstype=f.ServiceType.L3VPN)

            # add L2 NetworkService
            l2_ns = switch.add_network_service(name=switch.name + '-ns', layer=f.Layer.L2, labels=l2_ns_labs,
                                               node_id=switch.node_id + '-ns', nstype=f.ServiceType.MPLS)
            # add ports
            if 'interfaces' in node:
                for port in node['interfaces']:
                    port_name = port['name']
                    if 'admin-status' in port and port ['admin-status'] == 'up':
                        port_active = True
                    else:
                        port_active = False
                    if 'phys-address' not in port:
                        continue
                    port_mac = port['phys-address']
                    port_nid = f"port+{node_name}:{port_name}"
                    # get port/links capacities from site_config SoT file
                    port_link_cap = self._get_port_link_cap(site_name, port_name)
                    if port_link_cap:
                        port_link_cap_map[port_nid] = port_link_cap
                    if 'port-capacity' in port_link_cap: # we defined
                        speed_gbps = port_link_cap['port-capacity']
                    else: # use system default
                        speed_gbps = int(int(port['speed']) / 1000000000)
                    # add capabilities
                    port_caps = f.Capacities(bw=speed_gbps)
                    # add labels (vlan ??)
                    port_labs = f.Labels(local_name=port_name, mac=port_mac)
                    if 'ietf-ip:ipv6' in port and 'address' in port['ietf-ip:ipv6']:
                        for ipv6_addr in port['ietf-ip:ipv6']['address']:
                            ipv6_addr_ip = ipv6_addr['ip']
                            ipv6_addr_prefix_len = ipv6_addr['prefix-length']
                            port_labs = f.Labels().update(port_labs, local_name=port_name, ipv6=ipv6_addr_ip)
                            # only take the first
                            break
                    elif regexVlanPort.search(port_name):  # skip if no ipv6 address (it's a slice vlan port)
                        continue
                    if 'ietf-ip:ipv4' in port and 'address' in port['ietf-ip:ipv4']:
                        for ipv4_addr in port['ietf-ip:ipv4']['address']:
                            ipv4_addr_ip = ipv4_addr['ip']
                            ipv4_addr_mask = ipv4_addr['netmask']
                            port_labs = f.Labels().update(port_labs, local_name=port_name, ipv4=ipv4_addr_ip)
                            if port_active:
                                port_ipv4net_map[port_nid] = {"site": site_name, "port": port_name,
                                    "ip": ipv4_addr_ip, "netmask": ipv4_addr_mask}
                            # only take the first
                            break
                    elif regexVlanPort.search(port_name):  # skip if no ipv4 address (it's a slice vlan port)
                        continue
                    sp = None
                    if port_active:
                        sp = l2_ns.add_interface(name=port_name, itype=f.InterfaceType.TrunkPort,
                                                 node_id=port_nid, labels=port_labs,
                                                 capacities=port_caps)
                        if port_nid in port_ipv4net_map:
                            port_ipv4net_map[port_nid]["interface"] = sp
                    # add external facility stitching links
                    # refer to port_name as stitch_port

                    # add facility_ports based on stitching metadata
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
                                if '-' in stitch_info['vlan_range']:
                                    facility_port_labs = f.Labels.update(facility_port_labs,
                                                                         vlan_range=stitch_info['vlan_range'].split(','))
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
                                                                     device_name=stitch_info['local_device'])
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
                            if not sp:
                                sp = l2_ns.add_interface(name=port_name, itype=f.InterfaceType.TrunkPort,
                                                         node_id=port_nid, labels=port_labs,
                                                         capacities=port_caps)
                            link_caps = None
                            link_cap_allocs = None
                            if 'link-capacity' in port_link_cap:
                                link_caps = f.Capacities(bw=port_link_cap['link-capacity'])
                                if 'link-reserve-capacity' in port_link_cap:
                                    link_cap_allocs = f.Capacities(bw=port_link_cap['link-reserve-capacity'])
                            self.topology.add_link(name=facility_name + '-link',
                                                   node_id=f'{port_nid}:facility+{facility_name}+link',
                                                   ltype=f.LinkType.L2Path,  # could be Patch too
                                                   capacities=link_caps,
                                                   capacity_allocations=link_cap_allocs,
                                                   interfaces=[sp, fac.interface_list[
                                                       0]])  # there is only one interface on the facility

                    # add al2s_ports based on stitching metadata
                    if site_info and 'al2s_ports' in site_info:
                        for al2s_port_name, al2s_stitch_info in site_info['al2s_ports'].items():
                            if 'stitch_port' not in al2s_stitch_info:
                                raise NetAmArmError('no peer / stitch_port defined for al2s_port: ' + al2s_port_name)
                            stitch_port_name = al2s_stitch_info['stitch_port'].replace(' ', '')
                            if stitch_port_name != port_name:
                                continue
                            al2s_port_labs = f.Labels()
                            if 'vlan_range' in al2s_stitch_info:
                                al2s_port_labs = f.Labels().update(al2s_port_labs, vlan_range=al2s_stitch_info['vlan_range'].split(','))
                            al2s_sp = al2s_l2_ns.add_interface(name=al2s_port_name, itype=f.InterfaceType.TrunkPort,
                                                    labels=al2s_port_labs, node_id='port+al2s:'+al2s_port_name,
                                                    stitch_node=True)
                            # connect it to the FABRIC port via link
                            if not sp:
                                sp = l2_ns.add_interface(name=port_name, itype=f.InterfaceType.TrunkPort,
                                                         node_id=port_nid, labels=port_labs,
                                                         capacities=port_caps)
                            link_caps = None
                            link_cap_allocs = None
                            if 'link-capacity' in port_link_cap:
                                link_caps = f.Capacities(bw=port_link_cap['link-capacity'])
                                if 'link-reserve-capacity' in port_link_cap:
                                    link_cap_allocs = f.Capacities(bw=port_link_cap['link-reserve-capacity'])
                            self.topology.add_link(name=al2s_port_name + '-link',
                                                   node_id=f'{port_nid}:{al2s_port_name}+link',
                                                   ltype=f.LinkType.L2Path,  # could be Patch too
                                                   capacities=link_caps,
                                                   capacity_allocations=link_cap_allocs,
                                                   interfaces=[sp, al2s_sp])

        # add FABRIC Testbed internal links
        for k in list(port_ipv4net_map):
            if k not in port_ipv4net_map:
                continue
            v = port_ipv4net_map[k]
            site_name = v['site']
            port_name = v['port']
            port_ip = v['ip']
            port_netmask = v['netmask']
            port_sp = v['interface']
            link_caps = None
            link_cap_allocs = None
            if k in port_link_cap_map:
                port_link_cap = port_link_cap_map[k]
                if 'link-capacity' in port_link_cap:
                    link_caps = f.Capacities(bw=port_link_cap['link-capacity'])
                    if 'link-reserve-capacity' in port_link_cap:
                        link_cap_allocs = f.Capacities(bw=port_link_cap['link-reserve-capacity'])
            port_ipv4net_map.pop(k, None)
            # look up paring remote interface
            for k_r in list(port_ipv4net_map):
                v_r = port_ipv4net_map[k_r]
                port_ip_r = v_r['ip']
                has_link = False
                if self.valid_ipv4_links is None:  # form link if local and remote ipv4 addresses in same subnet
                    port_netmask_r = v_r['netmask']
                    port_netmask = _normalize_netmask(port_netmask)
                    port_netmask_r = _normalize_netmask(port_netmask_r)
                    if port_netmask == port_netmask_r and _in_same_network(port_ip, port_ip_r, port_netmask):
                        has_link = True
                elif f'{port_ip}-{port_ip_r}' in self.valid_ipv4_links:
                    has_link = True
                if has_link:
                    port_ipv4net_map.pop(k_r, None)
                    port_sp_r = v_r['interface']
                    # determine link type: L2 vs L1
                    link_type = self._get_link_type(site_name, port_name)
                    layer = f.Layer.L1
                    ltype = f.LinkType.L1Path
                    if link_type == 'l2path':
                        layer = f.Layer.L2
                        ltype = f.LinkType.L2Path
                    # add link
                    link_nid = f"link:local-{port_sp.node_id}:remote-{port_sp_r.node_id}"
                    link = self.topology.add_link(name=f'{port_sp.node_id} to {port_sp_r.node_id}',
                                                  layer=layer,
                                                  ltype=ltype,
                                                  capacities = link_caps,
                                                  capacity_allocations = link_cap_allocs,
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
