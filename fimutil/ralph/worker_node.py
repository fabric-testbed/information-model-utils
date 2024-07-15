import dataclasses

import pyjq
import logging
import json
import re
import binascii
from typing import Dict

from fimutil.ralph.asset import RalphAsset, RalphAssetType, RalphJSONError, RalphAssetMimatch
from fimutil.ralph.nvme import NVMeDrive
from fimutil.ralph.ethernetport import EthernetCardPort
from fimutil.ralph.gpu import GPU
from fimutil.ralph.fpga import FPGA
from fimutil.ralph.model import WorkerModel
from fimutil.ralph.ralph_uri import RalphURI
from fimutil.ralph.dp_switch import DPSwitch


class WorkerNode(RalphAsset):
    """
    This class knows how to parse necessary worker fields in Ralph
    """
    FIELD_MAP = '{Name: .hostname, SN: .sn}'
    # don't start at 1 - that's typically 'uplink'
    OPENSTACK_NIC_INDEX = 10
    OPENSTACK_VNIC_COUNT = 2000 # randomly set 2000 vNICs to be created
    WORKER_NAME_REGEX = r'^[\w]+-w([\d]+).fabric-testbed.net$'
    # first octet must be even
    OPENSTACK_NIC_MAC_REG = r'([a-fA-F0-9][aceACE02468])[:-]([a-fA-F0-9]{2})'

    def __init__(self, *, uri: str, ralph: RalphURI, site: str = None, dp_switch: DPSwitch, config: Dict = None,
                 ptp: bool = False):
        super().__init__(uri=uri, ralph=ralph)
        self.type = RalphAssetType.Node
        self.model = None
        self.site = site
        self.config = config
        self.ptp = ptp # comes from site
        # so we can get VLAN info
        self.dp_switch = dp_switch

    @staticmethod
    def generate_openstack_mac(site_offset: str, worker: str, count: int) -> str:
        """
        generate a unique MAC address for a single OpenStack vNIC on a given
        a site offset (from config file) and a unique counter
        :param site_offset - string from config file representing two first octets in hex (0xabcd)
        :param worker - FQDN of worker node
        :param count - index of the vNIC
        return: string
        """

        assert site_offset and worker
        assert count < 4096

        m = re.match(WorkerNode.OPENSTACK_NIC_MAC_REG, site_offset)
        if not m:
            raise RuntimeError(f'OpenStack MAC address offset for the site must match the '
                               f'following regex: {WorkerNode.OPENSTACK_NIC_MAC_REG}')

        mac_bytes = bytearray()
        # prepend site offset
        mac_bytes.extend(bytes.fromhex(m[1]+m[2]))
        # add worker
        m = re.match(WorkerNode.WORKER_NAME_REGEX, worker)
        if not m:
            raise RuntimeError(f'Worker name {worker} doesnt match expected regex')
        w_index = int(m[1])
        mac_bytes.extend(w_index.to_bytes(length=1, byteorder='big'))
        # add counter (up to 4096)
        mac_bytes.extend(count.to_bytes(length=3, byteorder='big'))
        assert len(mac_bytes) == 6
        mac_string = binascii.hexlify(mac_bytes, ':', 1)
        return mac_string.decode('utf-8')

    def parse(self):
        super().parse()

        # find model
        model_url = pyjq.one('.model.url', self.raw_json_obj)
        self.model = WorkerModel(uri=model_url, ralph=self.ralph)
        try:
            self.model.parse()
        except RalphAssetMimatch:
            pass

        custom_fields_dict = pyjq.one('.custom_fields', self.raw_json_obj)

        # check for usable_ram _disk and _cores custom fields provided from OpenStack -
        # they override anything on the model. Note they are reported without units
        self.model.fields['Core'] = custom_fields_dict.get('usable_cores', self.model.fields['Core'])
        # RAM is in MB reported by OpenStack
        ram = int(custom_fields_dict.get('usable_memory', '0'))//1024
        if ram > 0:
            self.model.fields['RAM'] = f'{ram}G'
        disk = custom_fields_dict.get('usable_disk')
        if disk:
            self.model.fields['Disk'] = f'{disk}G'

        if self.config and self.config.get(self.site) and self.config.get(self.site).get('ram_offset'):
            ram_offset = self.config.get(self.site).get('ram_offset')
            ram -= ram_offset
            if ram > 0:
                self.model.fields['RAM'] = f'{ram}G'

        # override from config if present
        if self.config and self.config.get(self.site) and self.config.get(self.site).get('workers') and \
            self.config.get(self.site).get('workers').get(self.fields['Name']):
            worker_override = self.config.get(self.site).get('workers').get(self.fields['Name'])
            self.model.fields['RAM'] = worker_override.get('RAM', self.model.fields['RAM'])
            self.model.fields['CPU'] = worker_override.get('CPU', self.model.fields['CPU'])
            self.model.fields['Core'] = worker_override.get('Core', self.model.fields['Core'])
            # Multiply the core count with cpu allocation ratio for over subscription
            self.model.fields['Core'] = int(self.model.fields['Core']) * worker_override.get("cpu_allocation_ratio", 1)
            self.model.fields['Disk'] = worker_override.get('Disk', self.model.fields['Disk'])

        # find NVMe drives in 'disks' section
        try:
            disk_urls = pyjq.all('.disk[].url', self.raw_json_obj)
        except ValueError:
            logging.warning('Unable to find any disks in node, continuing')
            disk_urls = list()

        disk_index = 1
        for disk in disk_urls:
            drive = NVMeDrive(uri=disk, ralph=self.ralph)
            try:
                drive.parse()
            except RalphAssetMimatch:
                continue
            self.components['nvme-' + str(disk_index)] = drive
            disk_index += 1

        # in lightweight sites skip looking for ports, add OpenStack vNIC instead
        if self.LIGHTWEIGHT_SITE:
            logging.debug('Since this is a lightweight site, skipping looking for ethernet ports, '
                          'adding OpenStack parent port and vNICs instead')
            if self.config and self.config.get(self.site) and self.config.get(self.site).get('mac_offset'):
                mac_offset = self.config.get(self.site).get('mac_offset')
            else:
                raise RuntimeError('For OpenStack sites you must specify "mac_offset" under site static configuration')

            port_index = 1
            # 'parent'
            port = EthernetCardPort(uri='no-url', ralph=self.ralph)
            port.force_values(model='OpenStack-vNIC', desc='OpenStack parent NIC', speed='1Gbps',
                              bdf='0000:00:00.0', mac=self.generate_openstack_mac(mac_offset, self.fields['Name'], 1),
                              peer_port=str(self.OPENSTACK_NIC_INDEX), numa='-1')
            self.components['port-' + str(port_index)] = port
            port_index += 1
            if not self.dp_switch.vlan_ranges:
                raise RuntimeError('OpenStack sites should define at least local VLANs '
                                   '(and usually AL2S vlans) as custom fields of dp switch in Ralph, none found')

            # Add children with bdf=0000:00:00.0 and vBDF=0000:AB:CD.0 have VLAN 0 set (VLANs are saved on NetworkService)
            # NOTE: vfs have 'vBDF' set to their own and 'BDF' set to parent.
            for vnic_idx in range(2, self.OPENSTACK_VNIC_COUNT):
                port = EthernetCardPort(uri='no-url', ralph=self.ralph)
                # make all vbdfs different and reflection of VLAN tag
                vbdf_diff = binascii.hexlify(vnic_idx.to_bytes(2, 'big'), ':', 1).decode('utf-8')
                port.force_values(model='OpenStack-vNIC', desc='OpenStack vNIC', speed='1Gbps', vlan='0',
                                  bdf='0000:00:00.0', vbdf='0000:' + vbdf_diff + '.0',
                                  ctype=RalphAssetType.EthernetCardVF,
                                  mac=self.generate_openstack_mac(mac_offset, self.fields['Name'], vnic_idx),
                                  peer_port=str(self.OPENSTACK_NIC_INDEX), numa='-1')
                self.components['port-' + str(port_index)] = port
                port_index += 1
            type(self).OPENSTACK_NIC_INDEX += 1
        else:
            # scan for physical NICs and virtual NICs
            try:
                port_urls = pyjq.all('.ethernet[].url', self.raw_json_obj)
            except ValueError:
                logging.warning('Unable to find any ethernet ports in node, continuing')
                port_urls = list()

            port_index = 1
            for port in port_urls:
                port = EthernetCardPort(uri=port, ralph=self.ralph)
                try:
                    port.parse()
                except RalphAssetMimatch:
                    continue
                self.components['port-' + str(port_index)] = port
                port_index += 1

        gpus = GPU.find_gpus(self.raw_json_obj)
        gpu_index = 1
        for gpu in gpus:
            self.components['gpu-' + str(gpu_index)] = gpu
            gpu_index += 1

        fpgas = FPGA.find_fpgas(self.raw_json_obj)
        fpga_index = 1
        for fpga in fpgas:
            self.components['fpga-' + str(fpga_index)] = fpga
            fpga_index += 1

    def __str__(self):
        retl = list()
        if RalphAsset.PRINT_SUMMARY:
            retl.append(str(self.type) + " " + self.fields['Name'] + f" Flags: {{ PTP: {self.ptp} }}")
        else:
            retl.append(str(self.type) + "[" + self.uri + "]: " + json.dumps(self.fields) +
                        f" Flags: {{ PTP: {self.ptp} }}")
            retl.append('\t' + str(self.model))
        vfcount = 0
        for n, comp in self.components.items():
            if comp.__dict__.get('type', None) is None:
                # GPU or some other typeless thing
                retl.append('\t' + n + " " + str(comp))
            elif comp.type != RalphAssetType.EthernetCardVF:
                # something with type that isn't a VF
                retl.append('\t' + n + " " + str(comp))
            else:
                # a VF
                vfcount += 1
        retl.append(f'\tDetected {vfcount} SR-IOV functions')
        ret = "\n".join(retl)
        return ret

    def to_json(self):
        ret = {
                'Name': self.fields['Name'],
                'PTP': self.ptp,
                'SN': self.fields.get('SN', 'Not available'),
                'Model': self.model.fields.copy()
        }
        comps = list()
        for n, comp in self.components.items():
            if comp.__dict__.get('type') and comp.type != RalphAssetType.EthernetCardVF:
                d = comp.fields.copy()
                d['Type'] = str(comp.type)
                comps.append(d)
            elif not comp.__dict__.get('type'):
                # GPU or FPGA
                d = comp.__dict__.copy()
                d['Type'] = str(RalphAssetType.GPU) if isinstance(comp, GPU) else str(RalphAssetType.FPGA)
                comps.append(d)
        ret['Components'] = comps
        return ret

    def get_dp_ports(self):
        """
        Return a list of names of DP switch ports this node is connected to
        """
        dp_ports = list()
        for n, comp in self.components.items():
            if comp.__dict__.get('type') and comp.type == RalphAssetType.EthernetCardPF:
                if comp.fields.get('Peer_port'):
                    dp_ports.append(comp.fields.get('Peer_port'))
            if isinstance(comp, FPGA):
                dp_ports.extend(comp.Ports)

        return dp_ports
