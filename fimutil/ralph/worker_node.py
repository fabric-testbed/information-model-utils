import dataclasses

import pyjq
import logging
import json

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

    def __init__(self, *, uri: str, ralph: RalphURI):
        super().__init__(uri=uri, ralph=ralph)
        self.type = RalphAssetType.Node
        self.model = None

    def parse(self):
        super().parse()

        # find model
        model_url = pyjq.one('.model.url', self.raw_json_obj)
        self.model = WorkerModel(uri=model_url, ralph=self.ralph)
        try:
            self.model.parse()
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
        retl.append(str(self.type) + "[" + self.uri + "]" + ": " + json.dumps(self.fields))
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




