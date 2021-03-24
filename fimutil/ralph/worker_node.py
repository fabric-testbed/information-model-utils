from fimutil.ralph.asset import RalphAsset, RalphAssetType, RalphJSONError, RalphAssetMimatch
from fimutil.ralph.nvme import NVMeDrive
from fimutil.ralph.ethernet import Ethernet
from fimutil.ralph.ralph_uri import RalphURI


class WorkerNode(RalphAsset):
    """
    This class knows how to parse necessary worker fields in Ralph
    """
    FIELD_MAP = {
        "SN": "results/0.sn",
        "Model": "results/0.model.category.name",
    }

    def __init__(self, *, uri: str, ralph: RalphURI):
        super().__init__(uri=uri, ralph=ralph)
        self.type = RalphAssetType.Worker

    def parse(self):

        super().parse()

        # find NVMe drives in 'disks' section
        if self.raw_json_obj['results'][0]['disk'] is None:
            raise RalphJSONError(f'Expected to find a disks array in worker node')
        disks = self.raw_json_obj['results'][0]['disk']
        disk_index = 1
        for disk in disks:
            drive = NVMeDrive(uri=disk['url'], ralph=self.ralph)
            try:
                drive.parse()
            except RalphAssetMimatch:
                continue
            self.components['nvme-' + str(disk_index)] = drive
            disk_index = disk_index + 1

        ports = self.raw_json_obj['results'][0]['ethernet']
        port_index = 1
        for port in ports:
            port = Ethernet(uri=port['url'], ralph=self.ralph)
            try:
                port.parse()
            except RalphAssetMimatch:
                continue
            self.components['port-' + str(port_index)] = port
            port_index = port_index + 1




