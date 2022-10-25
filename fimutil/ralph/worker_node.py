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
from fimutil.ralph.model import WorkerModel
from fimutil.ralph.ralph_uri import RalphURI


class WorkerNode(RalphAsset):
    """
    This class knows how to parse necessary worker fields in Ralph
    """
    FIELD_MAP = '{Name: .hostname, SN: .sn}'
    # don't start at 1 - that's typically 'uplink'
    OPENSTACK_NIC_INDEX = 10
    WORKER_NAME_REGEX = r'^[\w]+-w([\d]+).fabric-testbed.net$'

    def __init__(self, *, uri: str, ralph: RalphURI, site: str = None, config: Dict = None):
        super().__init__(uri=uri, ralph=ralph)
        self.type = RalphAssetType.Node
        self.model = None
        self.site = site
        self.config = config

    @staticmethod
    def generate_openstack_mac(site: str, worker: str) -> str:
        """
        generate a unique MAC address for a single OpenStack vNIC on a given worker in a site
        For site 'UKY2' and worker 'uky2-w2.fabric-testbed.net' it will return
        return: string
        """
        # take the last 4 letters of site name (so we include index like UKY2, UKY3)
        # take worker index (assume 0-9)
        # prepend 0xF1 (to make it private)
        assert worker and site
        m = re.match(WorkerNode.WORKER_NAME_REGEX, worker)
        w_index = int(m[1])
        mac_bytes = bytearray()
        # prepend 0xF1
        mac_bytes.append(0xf1)
        mac_bytes.extend(bytes(site[-4:], 'utf-8'))
        mac_bytes.append(w_index)
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
            # override from config if present
            if self.config and self.config.get(self.site) and self.config.get(self.site).get('workers') and \
                self.config.get(self.site).get('workers').get(self.fields['Name']):
                worker_override = self.config.get(self.site).get('workers').get(self.fields['Name'])
                self.model.fields['RAM'] = worker_override.get('RAM', self.model.fields['RAM'])
                self.model.fields['CPU'] = worker_override.get('CPU', self.model.fields['CPU'])
                self.model.fields['Core'] = worker_override.get('Core', self.model.fields['Core'])
                self.model.fields['Disk'] = worker_override.get('Disk', self.model.fields['Disk'])
        except RalphAssetMimatch:
            pass

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
                          'adding OpenStack port instead')
            port = EthernetCardPort(uri='no-url', ralph=self.ralph)
            port.force_values(model='OpenStack', desc='OpenStack vNIC', speed='1Gbps',
                              bdf='0000:00:00.0', mac=self.generate_openstack_mac(self.site, self.fields['Name']),
                              peer_port=str(self.OPENSTACK_NIC_INDEX))
            self.components['port-1'] = port
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

    def __str__(self):
        retl = list()
        if RalphAsset.PRINT_SUMMARY:
            retl.append(str(self.type) + " " + self.fields['Name'])
        else:
            retl.append(str(self.type) + "[" + self.uri + "]: " + json.dumps(self.fields))
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
                'Model': self.model.fields.copy()
        }
        comps = list()
        for n, comp in self.components.items():
            if comp.__dict__.get('type') and comp.type != RalphAssetType.EthernetCardVF:
                d = comp.fields.copy()
                d['Type'] = str(comp.type)
                comps.append(d)
            elif not comp.__dict__.get('type'):
                # GPU
                d = comp.__dict__.copy()
                d['Type'] = str(RalphAssetType.GPU)
                comps.append(d)
        ret['Components'] = comps
        return ret





