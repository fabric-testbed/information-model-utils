import pyjq

from fimutil.ralph.asset import RalphAsset, RalphAssetType, RalphJSONError, RalphAssetMimatch
from fimutil.ralph.nvme import NVMeDrive
from fimutil.ralph.ethernet import Ethernet
from fimutil.ralph.ralph_uri import RalphURI


class WorkerNode(RalphAsset):
    """
    This class knows how to parse necessary worker fields in Ralph
    """
    FIELD_MAP = '{SN: .results[0].sn, Model: .results[0].model.category.name}'

    def __init__(self, *, uri: str, ralph: RalphURI):
        super().__init__(uri=uri, ralph=ralph)
        self.type = RalphAssetType.Node

    def parse(self):

        super().parse()

        # find NVMe drives in 'disks' section
        disk_urls = pyjq.one('[ .results[0].disk[].url ]', self.raw_json_obj)
        disk_index = 1
        for disk in disk_urls:
            drive = NVMeDrive(uri=disk, ralph=self.ralph)
            try:
                drive.parse()
            except RalphAssetMimatch:
                continue
            self.components['nvme-' + str(disk_index)] = drive
            disk_index = disk_index + 1

        port_urls = pyjq.one('[ .results[0].ethernet[].url ]', self.raw_json_obj)
        port_index = 1
        for port in port_urls:
            port = Ethernet(uri=port, ralph=self.ralph)
            try:
                port.parse()
            except RalphAssetMimatch:
                continue
            self.components['port-' + str(port_index)] = port
            port_index = port_index + 1




