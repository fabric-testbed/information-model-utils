import pyjq
import re
import logging

from fimutil.ralph.ralph_uri import RalphURI
from fimutil.ralph.asset import RalphAsset, RalphAssetType


class SimpleModel(RalphAsset):
    """
    Some assets have a separate model entry that behaves like an asset.
    """
    FIELD_MAP = '{Model: .category.name}'

    def __init__(self, *, uri: str, ralph: RalphURI):
        super().__init__(uri=uri, ralph=ralph)
        self.type = RalphAssetType.Model

    def parse(self):
        super().parse()


class WorkerModel(SimpleModel):
    """
    Worker model has extra info like total RAM and cores that we need
    """
    FIELD_MAP = '{Model: .category.name, RAM: .custom_fields.total_memory_ram, ' \
                'CPU: .custom_fields.cpu_socket_count, Core: .cores_count}'
    # .*? to make the first match lazy
    DISK_REGEX = ".*?([\\d.]+)([TGM]B).*"

    def __init__(self, *, uri: str, ralph: RalphURI):
        super().__init__(uri=uri, ralph=ralph)

    def parse(self):
        super().parse()
        # some workers have sas disks - need to count them and sum up disk space
        sas_disk_count = 0
        sas_disk_size = 0.0
        unit = 'TB'
        try:
            sas_disk_count_str = pyjq.one('.custom_fields.sas_disk_count', self.raw_json_obj)
            if sas_disk_count_str is not None:
                sas_disk_count = int(sas_disk_count_str)
            sas_disk_desc = pyjq.one('.custom_fields.sas_disk', self.raw_json_obj)
            if sas_disk_desc is not None:
                match = re.match(self.DISK_REGEX, sas_disk_desc)
                if match is not None:
                    sas_disk_size = float(match.group(1))
                    unit = match.group(2)
        except ValueError:
            pass
        total_disk = sas_disk_size * sas_disk_count
        self.fields['Disk'] = str(total_disk) + ' ' + unit
        if not self.fields['RAM']:
            logging.warning('Unable to parse RAM, setting to 0')
            self.fields['RAM'] = '0G'
        if not self.fields['CPU']:
            logging.warning('Unable to parse CPU count, setting to 0')
            self.fields['CPU'] = '0'


class StorageModel(SimpleModel):
    """
    Storage model has extra info like total disks
    """
    FIELD_MAP = '{Model: .category.name}'
    # .*? to make the first match lazy
    DISK_REGEX = ".*?([\\d.]+)([TGMP]B).*"

    def __init__(self, *, uri: str, ralph: RalphURI):
        super().__init__(uri=uri, ralph=ralph)

    def parse(self):
        super().parse()
        # storage has SAS disks
        sas_disk_count = 0
        sas_disk_size = 0.0
        unit = 'TB'
        try:
            sas_disk_count_str = pyjq.one('.custom_fields.sas_disk_count', self.raw_json_obj)
            if sas_disk_count_str is not None:
                sas_disk_count = int(sas_disk_count_str)
            sas_disk_desc = pyjq.one('.custom_fields.sas_disk', self.raw_json_obj)
            if sas_disk_desc is not None:
                match = re.match(self.DISK_REGEX, sas_disk_desc)
                if match is not None:
                    sas_disk_size = float(match.group(1))
                    unit = match.group(2)
        except ValueError:
            pass
        total_disk = sas_disk_size * sas_disk_count
        self.fields['Disk'] = str(total_disk) + ' ' + unit
