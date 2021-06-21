import fim.user as f
from fimutil.netam.nso import NsoClient
from fimutil.netam.sr_pce import SrPceClient

import re
import json
from ipaddress import IPv4Interface


def _in_same_network(ip1: str, ip2: str, netmask: str) -> bool:
    return IPv4Interface(f'{ip1}/{netmask}').network == IPv4Interface(f'{ip2}/{netmask}').network


class NetworkARM:
    """
    Generate Network AM resources information model.
    """

    def __init__(self, *, nso_url: str, nso_user: str, nso_pass: str, sr_pce_url: str, sr_pce_user: str,
                 sr_pce_pass: str):
        self.nso = NsoClient(nso_url=nso_url, nso_user=nso_user, nso_pass=nso_pass)
        self.sr_pce = SrPceClient(sr_pce_url=sr_pce_url, sr_pce_user=sr_pce_user, sr_pce_pass=sr_pce_pass)
        self.topology = None

    def _get_device_interfaces(self) -> list:
        devs = self.nso.devices()
        for dev in devs:
            dev_name = dev['name']
            ifaces = self.nso.interfaces(dev_name)
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
        self.topology = f.SubstrateTopology()
        nodes = self._get_device_interfaces()
        port_ipv4net_map = {}
        for node in nodes:
            # add switch node
            node_name = node['name']
            # TODO: get model name from NSO
            model_name = 'NCS 55A1-36H'
            # TODO: get official site name from Ralph (or in switch description string) ?
            site_name = node_name + '-site'
            re_site = re.findall(r'(\w+)-.+', node_name)
            if re_site is not None and len(re_site) > 0:
                site_name = str.upper(re_site[0])
            node_nid = "node+" + node_name + ":ip+" + node['address']
            switch = self.topology.add_node(name=node_name, model=model_name, site=site_name,
                                            node_id=node_nid,
                                            capacities=f.Capacities().set_fields(unit=1),
                                            labels=f.Labels().set_fields(local_name=node_name, ipv4=node['address']),
                                            stitch_node=True)
            dp_ns = switch.add_network_service(name=switch.name + '-ns', layer=f.Layer.L2,
                                             node_id=switch.node_id + '-ns', nstype=f.ServiceType.MPLS, stitch_node=True)
            # add ports
            for port in node['interfaces']:
                port_name = port['name']
                port_mac = port['phys-address']
                port_nid = f"port+{node_name}:{port_name}"
                speed_gbps = int(int(port['speed']) / 1000000000)
                # add capabilities
                port_caps = f.Capacities()
                port_caps.set_fields(bw=speed_gbps)
                # add labels (vlan ??)
                port_labs = f.Labels()
                port_labs.set_fields(local_name=port_name, mac=port_mac)
                if port['ietf-ip:ipv4']:
                    if 'ietf-ip:ipv4' in port and 'address' in port['ietf-ip:ipv4']:
                        for ipv4_addr in port['ietf-ip:ipv4']['address']:
                            ipv4_addr_ip = ipv4_addr['ip']
                            ipv4_addr_mask = ipv4_addr['netmask']
                            port_labs.set_fields(local_name=port_name, ipv4=ipv4_addr_ip)
                            port_ipv4net_map[port_nid] = {"ip": ipv4_addr_ip, "netmask": ipv4_addr_mask,
                                                          "interface": sp}
                            # only take the first
                            break
                if port['ietf-ip:ipv6']:
                    if 'ietf-ip:ipv6' in port and 'address' in port['ietf-ip:ipv6']:
                        for ipv6_addr in port['ietf-ip:ipv6']['address']:
                            ipv6_addr_ip = ipv6_addr['ip']
                            ipv6_addr_prefix_len = ipv6_addr['prefix-length']
                            port_labs.set_fields(local_name=port_name, ipv6=ipv6_addr_ip)
                            # only take the first
                            break
                sp = dp_ns.add_interface(name=port_name, itype=f.InterfaceType.TrunkPort,
                                         node_id=port_nid, labels=port_labs,
                                         capacities=port_caps)
        # add links
        # loop fetch interface (remove)
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
                port_netmask_r = v_r['netmask']
                if port_netmask == port_netmask_r and _in_same_network(port_ip, port_ip_r, port_netmask):
                    port_ipv4net_map.pop(k_r, None)
                    port_sp_r = v_r['interface']
                    # add link
                    link_nid = f"link:local-{port_sp.node_id}:remote-{port_sp_r.node_id}"
                    link = self.topology.add_link(name=f'{port_sp.node_id}-link', ltype=f.LinkType.L2Path,
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


class NetAmArmError(Exception):
    def __init__(self, msg: str):
        super().__init__(f'NetAmArmError: {msg}')
