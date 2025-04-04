import json
from typing import Tuple, List, Dict, Any, Set
import logging
import re
from collections import defaultdict

from fim.user.topology import SubstrateTopology
from fim.user.node import Node, NodeType
from fim.user.interface import Interface, InterfaceType
from fim.user.component import Component, ComponentType
from fim.user.link import LinkType
from fim.user.network_service import ServiceType
from fim.slivers.identifiers import *
from fim.slivers.capacities_labels import Capacities, Labels, Location, Flags

from fimutil.ralph.ralph_uri import RalphURI
from fimutil.ralph.site import Site
from fimutil.ralph.gpu import GPU
from fimutil.ralph.fpga import FPGA
from fimutil.ralph.ethernetport import EthernetCardPort, EthernetPort
from fimutil.ralph.nvme import NVMeDrive
from fimutil.ralph.asset import RalphAssetType, RalphAsset

SIZE_REGEX = "([\\d.]+)[ ]?([MGTP])B?"
SPEED_REGEX = "([\\d.]+)[ ]?([MGT])(bps)?"


class CardOrganizer:
    """
    This class helps organize PF and VF cards of a single worker node
    """

    def __init__(self):
        # organized by PCI id
        self.all_pf_cards = dict()
        # lists of VFs organized by parent PCI id
        self.vf_cards = defaultdict(list)
        # list of ids that are parents of VFs
        self.vf_parents = set()
        # dedicated PF cards - dictionary by slot id
        self.dedicated_cards = defaultdict(list)
        # VF parent cards - dictionary by slot id
        self.shared_cards = defaultdict(list)
        self.organized = False

    def add_pf(self, port: EthernetCardPort):
        if port.type != RalphAssetType.EthernetCardPF:
            logging.error(f'Port {port=} is not a PF type, unable to continue')
            raise RuntimeError()
        self.all_pf_cards[port.fields['BDF']] = port

    def add_vf(self, port: EthernetCardPort):
        if port.type != RalphAssetType.EthernetCardVF:
            logging.error(f'Port {port=} is not a VF type, unable to continue')
            raise RuntimeError()
        # BDF is parent, vBDF is own
        self.vf_cards[port.fields['BDF']].append(port)

    def organize(self):
        """
        Called after the first scan to organize VFs and PFs
        """
        # find VF parents
        for k in self.vf_cards.keys():
            self.vf_parents.add(k)
        # find and organize dedicated cards by slot
        for k, v in self.all_pf_cards.items():
            # Organize parents of VFs/shared cards separately from dedicated cards
            if k in self.vf_parents:
                self.shared_cards[v.fields['Slot']].append(v)
            else:
                self.dedicated_cards[v.fields['Slot']].append(v)
        self.organized = True

    def get_dedicated_cards(self) -> Dict[str, List[EthernetCardPort]]:
        """
        Get a dict of dedicated card PFs organized by slot
        """
        if not self.organized:
            logging.error('Please call organize() method prior to invoking this, unable to continue')
            raise RuntimeError()
        return self.dedicated_cards.copy()

    def get_shared_cards(self) -> Dict[str, List[EthernetCardPort]]:
        """
        Get a dict of shared card port PFs organized by slot
        """
        if not self.organized:
            logging.error('Please call organize() method prior to invoking this, unable to continue')
            raise RuntimeError()
        return self.shared_cards.copy()

    def get_vf_parents(self) -> Set[EthernetCardPort]:
        """
        get all parents of VFs
        """
        if not self.organized:
            logging.error('Please call organize() method prior to invoking this, unable to continue')
            raise RuntimeError()
        ret = set()
        for c in self.vf_parents:
            ret.add(self.all_pf_cards[c])
        return ret

    def get_vfs_of_parent(self, parent_bdf: str) -> List[EthernetCardPort] or None:
        """
        Get VFs of a given parent (specified by PCI id)
        """
        if not self.organized:
            logging.error('Please call organize() method prior to invoking this, unable to continue')
            raise RuntimeError()
        return self.vf_cards.get(parent_bdf, None)

    def get_parent_of_vf(self, vf_bdf: str) -> EthernetCardPort or None:
        """
        Find a parent of a given VF by PCI id
        """
        if not self.organized:
            logging.error('Please call organize() method prior to invoking this, unable to continue')
            raise RuntimeError()
        parent_bdf = None
        for k, v in self.vf_cards.items():
            # inefficient search
            for c in v:
                if vf_bdf == c.fields['vBDF']:
                    parent_bdf = k
                    break
        if parent_bdf is not None:
            return self.all_pf_cards[parent_bdf]
        return None


def __parse_size_spec(spec: str) -> Tuple[float, str]:
    """
    Parse a size spec of type <float number> [MGTP]B
    """
    matches = re.match(SIZE_REGEX, spec)
    if matches is None:
        logging.error(f'Unable to parse size spec {spec}, exiting')
        raise RuntimeError('Unable to continue')
    size_spec = matches.group(2)

    return float(matches.group(1)), size_spec


def __parse_speed_spec(spec: str) -> Tuple[float, str]:
    """
    Parse a speed spec of type <float number> [MGT]bps
    """
    matches = re.match(SPEED_REGEX, spec)
    if matches is None:
        logging.error(f'Unable to parse speed spec {spec}, exiting')
        raise RuntimeError('Unable to continue')
    size_spec = matches.group(2)

    return float(matches.group(1)), size_spec


CONVERSION_FACTOR = { 'M': {'M': 1e0, 'G': 1e-3, 'T': 1e-6, 'P': 1e-9},
                      'G': {'M': 1e3, 'G': 1e0, 'T': 1e-3, 'P': 1e-6},
                      'T': {'M': 1e6, 'G': 1e3, 'T': 1e0, 'P': 1e-3},
                      'P': {'M': 1e9, 'G': 1e6, 'T': 1e3, 'P': 1e0},
                      }


def __normalize_units(siz: float, from_units: str, to_units: str) -> float:
    """
    Convert from to units (e.g. G to T)
    """
    if from_units not in CONVERSION_FACTOR.keys():
        logging.error(f'Unit {from_units=} is not known, exiting')
        raise RuntimeError('Unable to continue')
    if to_units not in CONVERSION_FACTOR[from_units].keys():
        logging.error(f'Unit {to_units=} is not known, exiting')
        raise RuntimeError('Unable to continue')
    factor = CONVERSION_FACTOR[from_units][to_units]
    return siz * factor


def __add_gpu(node: Node, gpu_name: str, gpu: GPU) -> None:
    """
    Add a GPU to a topology node
    """
    node.add_component(name=node.name + '-' + gpu_name,
                       model=gpu.Model,
                       node_id=node.node_id + '-' + gpu_name,
                       ctype=ComponentType.GPU,
                       capacities=Capacities(unit=1),
                       labels=Labels(bdf=gpu.BDF, numa=gpu.NUMA),
                       details=gpu.Description)


def __add_fpga(node: Node, fpga_name: str, fpga: FPGA, port_map: Dict[str, str]) -> None:
    """
    Add FPGA to a node
    """
    interface_node_ids = list()
    interface_labels = list()
    fpga_node_id = f'fpga-{fpga.SN}'
    port_id = 1
    for p in fpga.Ports:
        interface_node_ids.append(f'{fpga_node_id}-p{port_id}')
        interface_labels.append(Labels(vlan_range='1-4096'))
        port_id += 1
    if fpga.USB_ID:
        labels = Labels(bdf=fpga.BDF, usb_id=fpga.USB_ID, numa=fpga.NUMA)
    else:
        labels = Labels(bdf=fpga.BDF, numa=fpga.NUMA)
    c = node.add_component(name=node.name + '-' + fpga_name,
                           model=fpga.Model,
                           node_id=fpga_node_id,
                           ctype=ComponentType.FPGA,
                           capacities=Capacities(unit=1),
                           labels=labels,
                           interface_node_ids=interface_node_ids,
                           interface_labels=interface_labels,
                           details=fpga.Description)
    for intf in c.interface_list:
        # use local name index (p1, p2 etc) to index into the Ports array
        port_index = int(intf.labels.local_name[1:])
        port_map[fpga.Ports[port_index - 1]] = intf


def __add_nvme(node: Node, nvme_name: str, nvme: NVMeDrive) -> None:
    """
    Add an NVME drive to a topology node
    """
    # {"SN": "PHLJ015301K31P0FGN", "Description": "Dell ....",
    # "BDF": "0000:22:00.0", "Model": "P4510"}
    disk_size, disk_units = __parse_size_spec(nvme.fields['Disk'])
    disk_size = __normalize_units(disk_size, disk_units, 'G')
    disk_size_int = int(disk_size)
    node.add_component(name=node.name + '-' + nvme_name,
                       model=nvme.fields['Model'],
                       node_id=nvme.fields['SN'],
                       ctype=ComponentType.NVME,
                       capacities=Capacities(unit=1, disk=disk_size_int),
                       labels=Labels(bdf=nvme.fields['BDF'], numa=nvme.fields.get('NUMA', '-1')),
                       details=nvme.fields['Description'])


def __process_card_port(port: EthernetCardPort, org: CardOrganizer) -> None:
    """
    Aggregate and organize the ports:
    - VFs need to be kept together (matched by parent PCI id) - 100s of ports
    - PFs need to be kept together (by common PCI id or Slot) - 1, 2, 4 or more ports
    Note that PFs could be parents of VFs.
    They get processed and added to nodes after the first pass (e.g. we don't know if the
    card has 1, 2, 4 or more ports - this can only be determined after the pass is complete)
    """
    if port.type == RalphAssetType.EthernetCardPF:
        if port.fields.get('Slot', None) is None:
            logging.warning(f'Unable to determine slot for card that owns {port=}, assigning Slot 0')
            port.fields['Slot'] = '0'
            #raise RuntimeError('Unable to continue')
        org.add_pf(port)
    elif port.type == RalphAssetType.EthernetCardVF:
        org.add_vf(port)
    else:
        logging.error(f'Unsupported port type {port.type=}')
        raise RuntimeError('Unable to continue')


def __convert_vf_list_to_interface_labels(vfs: List[EthernetCardPort]) -> Tuple[List[str], List[str], List[str], List[str]]:
    """
    Take a list of VFs of a single parent PF and convert into a tuple of lists one for MAC, child BDF and VLAN
    (in that order)
    """
    macs = list()
    bdfs = list()
    vlans = list()
    numas = list()
    for vf in vfs:
        macs.append(vf.fields['MAC'])
        bdfs.append(vf.fields['vBDF'])
        vlans.append(vf.fields['VLAN'])
        numas.append(vf.fields.get('NUMA', '-1'))

    return macs, bdfs, vlans, numas


def __convert_pf_list_to_interface_data(pfs: List[EthernetCardPort]) -> Tuple[List[str], List[str], List[str], List[str]]:
    """
    Take a list of PF ports of the same card and convert into tuple of  lists -
    macs, bdfs and peer ports and numa nodes
    """
    macs = list()
    bdfs = list()
    peers = list()
    numas = list()
    slot = None
    for i, pf in enumerate(pfs):
        macs.append(pf.fields['MAC'])
        bdfs.append(pf.fields['BDF'])
        peers.append(pf.fields['Peer_port'])
        numas.append(pf.fields.get('NUMA', '-1'))

        # DMA Controller for BlueField
        if i == (len(pfs) - 1) and pf.fields.get("Model") and 'BlueField' in pf.fields["Model"]:
            numas.append(pf.fields["NUMA"])
            last_bdf = pf.fields["BDF"]
            # Parse the last BDF into Bus, Device, and Function
            bus, device_function = last_bdf.split(":")[1:3]
            device, function = map(int, device_function.split("."))
            # Determine the next BDF
            function += 1  # Increment the Function
            if function > 7:  # If Function exceeds 7, reset and increment Device
                function = 0
                device += 1
                if device > 31:  # If Device exceeds 31, reset and increment Bus
                    device = 0
                    bus = hex(int(bus, 16) + 1)[2:].zfill(2)  # Increment Bus and format as hex
            next_bdf = f"0000:{bus}:{str(device).zfill(2)}.{function}"
            bdfs.append(next_bdf)

        if slot is None:
            slot = pf.fields['Slot']
        else:
            if slot != pf.fields['Slot']:
                logging.error(f'Slot of {pf} does not match the slot of other PFs in this card')
                raise RuntimeError()

    return macs, bdfs, peers, numas


def site_to_fim(site: Site, address: str, config: Dict = None) -> SubstrateTopology:
    """
    Produce a site substrate topology advertisements from Ralph site information.
    Optionally supply externally obtained postal address.
    """
    logging.info(f'Producing SubstrateTopology model for site {site.name}')

    loc = None
    if address is not None:
        loc = Location(postal=address)
        loc.to_latlon()

    if config and config.get(site.name) and config.get(site.name).get('location'):
        loc = Location.from_json(json_string=json.dumps(config.get(site.name).get('location')))

    topo = SubstrateTopology()

    port_map = dict()
    # create workers with components
    for worker in site.workers:
        # {"Name": "lbnl-w1.fabric-testbed.net", "SN": "5B3BR53"} {"Model": "R7525", "RAM": "512G", "CPU": "2", "Core": 64, "Disk": "0.0 TB"}
        disk_size, disk_unit = __parse_size_spec(worker.model.fields['Disk'])
        disk_size = __normalize_units(disk_size, disk_unit, 'G')
        disk_size_int = int(disk_size)
        ram_size, ram_unit = __parse_size_spec(worker.model.fields['RAM'])
        ram_size = __normalize_units(ram_size, ram_unit, 'G')
        ram_size_int = int(ram_size)
        cap = Capacities(unit=1,
                         cpu=int(worker.model.fields['CPU']),
                         core=int(worker.model.fields['Core']),
                         ram=ram_size_int,
                         disk=disk_size_int)
        w = topo.add_node(name=worker.fields['Name'], model=worker.model.fields['Model'],
                          node_id=worker.fields['SN'], ntype=NodeType.Server,
                          capacities=cap, site=site.name, location=loc, flags=Flags(ptp=worker.ptp))
        #
        # handle various component types
        #
        org = CardOrganizer()

        # NVMEs and GPUs; Network Cards (need to merge ports to cards), FPGAs (later)
        for comp_name, comp in worker.components.items():
            if isinstance(comp, NVMeDrive):
                __add_nvme(w, comp_name, comp)
            elif isinstance(comp, EthernetCardPort):
                __process_card_port(comp, org)
            elif isinstance(comp, GPU):
                __add_gpu(w, comp_name, comp)
            elif isinstance(comp, FPGA):
                __add_fpga(w, comp_name, comp, port_map)

        org.organize()

        logging.debug('Adding shared SR-IOV cards')
        # create VF components
        for k, v_temp in org.get_shared_cards().items():
            logging.debug(f'Processing {k} with {v_temp}')
            # some shared NICs have one port connected, but some have two - need to be treated
            # separately - each as a individual single port shared NIC
            name_idx = 0
            for v in v_temp:
                v = [v]  # list is expected
                parent_macs, parent_bdfs, parent_peers, parent_numas = __convert_pf_list_to_interface_data(v)
                units = 0
                labs = list()
                child_bdfs = list()
                child_numas = list()
                for pf_parent in v:
                    child_vfs = org.get_vfs_of_parent(pf_parent.fields['BDF'])
                    macs, bdfs, vlans, numas = __convert_vf_list_to_interface_labels(child_vfs)
                    labs.append(Labels(mac=macs, vlan=vlans, bdf=bdfs))
                    child_bdfs.extend(bdfs)
                    child_numas.extend(numas)
                    units += len(child_vfs)
                slot = v[0].fields['Slot']
                model = v[0].fields['Model']
                descr = v[0].fields['Description']
                interface_node_ids = list(map(mac_to_node_id, parent_macs))
                # to maintain backwards compatibility with models created before, we do the
                # ('' if name_idx == 0 else 'f' + str(name_idx)) - now that we added name_idx
                # so that without it, the names look as before
                shnic = w.add_component(name=w.name + '-slot' + slot + ('' if name_idx == 0 else '-f' + str(name_idx)),
                                        node_id=w.node_id + '-slot' + slot + ('' if name_idx == 0 else '-f' + str(name_idx)),
                                        model=model,
                                        network_service_node_id=w.node_id + '-slot' + slot + '-ns' +
                                                                ('' if name_idx == 0 else '-f' + str(name_idx)),
                                        # these are lists with element for every PF
                                        interface_node_ids=interface_node_ids,
                                        interface_labels=labs,
                                        capacities=Capacities(unit=units),
                                        labels=Labels(bdf=child_bdfs, numa=child_numas),
                                        ctype=ComponentType.SharedNIC,
                                        details=descr
                                        )
                # need to match interfaces of the component
                for intf in shnic.interface_list:
                    # becase ports/interfaces on shared cards don't carry parent MAC
                    # we have to trace it back from (any) child MAC to parent MAC
                    intf_lab = intf.get_property('labels')
                    intf_bdfs = intf_lab.bdf
                    parent = org.get_parent_of_vf(intf_bdfs[0])
                    parent_mac = parent.fields['MAC']
                    port_map[parent_peers[parent_macs.index(parent_mac)]] = intf
                name_idx += 1

        # create PF components
        logging.debug('Adding physical cards')
        for k, v in org.get_dedicated_cards().items():
            logging.debug(f'Processing {v}')
            macs, bdfs, peers, numas = __convert_pf_list_to_interface_data(v)
            interface_node_ids = list(map(mac_to_node_id, macs))
            labels = list()
            for m in macs:
                labels.append(Labels(mac=m, vlan_range='1-4096'))

            # k is PCI id, v is list of EthernetCardPorts
            smnic = w.add_component(name=w.name + '-slot' + v[0].fields['Slot'],
                                    node_id=w.node_id + '-slot' + v[0].fields['Slot'],
                                    model=v[0].fields['Model'],
                                    network_service_node_id=w.node_id + '-slot' + v[0].fields['Slot'] + '-ns',
                                    interface_node_ids=interface_node_ids,
                                    interface_labels=labels,
                                    ctype=ComponentType.SmartNIC,
                                    capacities=Capacities(unit=1),
                                    labels=Labels(bdf=bdfs, numa=numas),
                                    details=v[0].fields['Description']
                                    )
            for intf in smnic.interface_list:
                intf_lab = intf.get_property('labels')
                intf_mac = intf_lab.mac
                port_map[peers[macs.index(intf_mac)]] = intf

    # create storage
    logging.debug('Adding storage')
    nas = None
    dp = None
    if site.storage is None:
        logging.warning(f'Storage in site {site.name} was not detected/catalogued, continuing')
    else:
        disk_size, disk_unit = __parse_size_spec(site.storage.model.fields['Disk'])
        disk_size = __normalize_units(disk_size, disk_unit, 'G')
        disk_size_int = int(disk_size)
        nas = topo.add_node(name=site.storage.fields['Name'], model=site.storage.model.fields['Model'],
                            node_id=site.storage.fields['SN'], capacities=Capacities(unit=1, disk=disk_size_int),
                            site=site.name, ntype=NodeType.NAS)

    # create dataplane switch with interfaces and links back to server ports
    logging.debug('Adding dataplane switch')
    if site.dp_switch is None:
        logging.warning(f'DP Switch was not detected/catalogued, unable to continue')
        raise RuntimeError('Unable to continue')

    # check if we are using someone else's DP switch
    real_switch_site = site.name
    if config and config.get(site.name) and config.get(site.name).get('dpswitch'):
        dpswitch_override = config.get(site.name) and config.get(site.name).get('dpswitch')
        real_switch_site = dpswitch_override.get('Site')
        if not real_switch_site:
            logging.error(f'Config file does not specify site for dpswitch mapping of site {site.name}')
            raise RuntimeError('Unable to continue')

    # this prefers an IP address, but uses S/N if IP is None (like in GENI racks)
    dp_name = dp_switch_name_id(real_switch_site.lower(),
                                site.dp_switch.fields['IP'] if site.dp_switch.fields['IP'] else site.dp_switch.fields['SN'])
    logging.info(f'Adding DP switch {dp_name}')
    dp = topo.add_node(name=dp_name[0],
                       node_id=dp_name[1],
                       site=site.name, ntype=NodeType.Switch, stitch_node=True)

    # if this is a lightweight site and AL2S_vlans are specified, we use VLAN service
    if RalphAsset.LIGHTWEIGHT_SITE and site.dp_switch.fields.get('AL2S_SWITCH'):
        dp_service_type = ServiceType.VLAN
        # for OpenStack sites add VLANs and other info
        vlans = list()
        peer_vlans = list()
        if site.dp_switch.fields.get('Local_vlans'):
            vlans.extend(site.dp_switch.fields['Local_vlans'].split(','))
        if site.dp_switch.fields.get('AL2S_vlans'):
            peer_vlans.extend(site.dp_switch.fields['AL2S_vlans'].split(','))
        dp_ns = dp.add_network_service(name=dp.name + '-ns', node_id=dp.node_id + '-ns',
                                       labels=Labels(vlan_range=vlans),
                                       peer_labels=Labels(vlan_range=peer_vlans,
                                                          device_name=site.dp_switch.fields['AL2S_SWITCH']),
                                       nstype=dp_service_type, stitch_node=True)
    else:
        dp_service_type = ServiceType.MPLS
        dp_ns = dp.add_network_service(name=dp.name + '-ns', node_id=dp.node_id + '-ns',
                                       nstype=dp_service_type, stitch_node=True)

    # add switch ports (they are stitch nodes, so just need to get their ids right)
    link_idx = 1
    for k, v in port_map.items():
        sp = dp_ns.add_interface(name=k,
                                 node_id=dp_port_id(dp.name, k),
                                 itype=InterfaceType.TrunkPort,
                                 stitch_node=True)
        topo.add_link(name='l' + str(link_idx),
                      node_id=sp.node_id + '-DAC',
                      ltype=LinkType.Patch,
                      interfaces=[sp, v])
        link_idx += 1

    # create p4 switch with interfaces and links back to dataplane switch ports
    logging.debug('Adding p4 switch')
    if site.p4_switch is None:
        logging.info(f'P4 Switch was not detected/catalogued')
        return topo

    # this prefers an IP address, but uses S/N if IP is None (like in GENI racks)
    logging.debug(f'Adding P4 switch {site.name}')

    p4_name = p4_switch_name_id(real_switch_site.lower(),
                                site.p4_switch.fields['IP'] if site.p4_switch.fields['IP'] else site.p4_switch.fields['SN'])
    logging.info(f'Adding P4 switch {p4_name}')
    p4 = topo.add_node(name=p4_name[0],
                       node_id=p4_name[1],
                       site=site.name, ntype=NodeType.Switch, stitch_node=False,
                       capacities=Capacities(unit=1), management_ip=site.p4_switch.fields['IP'])

    p4_service_type = ServiceType.P4
    p4_ns = p4.add_network_service(name=p4.name + '-ns', node_id=p4.node_id + '-ns',
                                   nstype=p4_service_type, stitch_node=False)

    dp_to_p4_ports = []

    for c in site.p4_switch.components.values():
        speed, unit = __parse_speed_spec(c.fields['Speed'])
        speed = __normalize_units(speed, unit, 'G')
        speed_int = int(speed)
        capacities = Capacities(bw=speed_int)

        description = c.fields['Description']
        if "management" in description:
            port_name = "mgmt"
        else:
            # Use regular expression to find the value after "Port"
            match = re.search(r'Port (\d+)', description)
            if not match:
                logging.warning(f"Port could not be determined from Description for component: {c}")
                continue
            port_name = match.group(1)

        labels = Labels(local_name=f'p{port_name}')
        if c.fields['MAC']:
            labels.mac = c.fields['MAC']

        connection = c.fields['Connection']

        match2 = re.search(r'port\s+(\S+)', connection, re.IGNORECASE)
        if not match2:
            logging.warning(f"Data Plane port could not be determined from Connection for component: {c}")
            continue

        # Build dp_to_p4_ports here
        dp_to_p4_ports.append(match2.group(1))

        p4_ns.add_interface(name=f'p{port_name}', node_id=p4_name[1] + f'-int{port_name}' if p4_name[1] else None,
                            itype=InterfaceType.DedicatedPort,
                            labels=labels, capacities=capacities)

    # add dp switch ports that link to P4 switch ports (note they are not stitch nodes!!)
    for d, p4idx in zip(dp_to_p4_ports, range(1, 8 + 1)):
        sp = dp_ns.add_interface(name=d, itype=InterfaceType.TrunkPort,
                                 node_id=dp_port_id(dp.name, d), stitch_node=False)
        try:
            topo.add_link(name='l' + str(link_idx), ltype=LinkType.Patch,
                               interfaces=[p4.interfaces[f'p{p4idx}'], sp],
                               node_id=sp.node_id + '-DAC')
        except KeyError:
            logging.info(f'P4 is not connected on port p{p4idx}')
        link_idx += 1

    return topo


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(__parse_speed_spec('10 Gbps'))
    print(__parse_speed_spec('10G'))
    print(__parse_speed_spec('10 G'))
    print(__parse_size_spec('100Tbps'))
    print(__parse_size_spec('123 TB'))
    print(__parse_size_spec('1045GB'))
    print(__parse_size_spec('1 T'))
    print(__parse_size_spec('10M'))
    print(__normalize_units(30, 'M', 'G'))
    print(__normalize_units(30, 'T', 'G'))
    size, from_unit = __parse_size_spec('30.01 MB')
    print(size, from_unit, int(size))

    ralph = RalphURI(token='abcdefg',
                     base_uri='https://url/api/')
    site = Site(site_name='LBNL', ralph=ralph)
    site.catalog()
    topo = site_to_fim(site, '123 Frienship Street')
    print(topo)
