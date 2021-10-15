from fimutil.ralph.asset import RalphAsset, RalphAssetType, RalphAssetMimatch

from fimutil.ralph.ralph_uri import RalphURI


class NVMeDrive(RalphAsset):
    """
    This class knows how to parse necessary worker fields in Ralph
    """
    FIELD_MAP = '{SN: .serial_number, Description: .model_name}'
    # "Description": "Dell Express Flash NVMe P4510 1TB SFF in PCIe
    # SSD Slot 22 in Bay 2 (0000:21:00.0)", "BDF": "0000:21:00.0"
    REGEX_FIELDS = {'BDF': ["Description", ".+\\(([0-9a-f:.]+)\\).*"],
                    'Model': ["Description", ".+(NVMe|CD5) ([\\w]+).*"],
                    'Disk': ["Description", ".+ ([\\d]+[MGTP]B|[\\d]+[MGTP]) .*"]}

    def __init__(self, *, uri: str, ralph: RalphURI):
        super().__init__(uri=uri, ralph=ralph)
        self.type = RalphAssetType.NVMe

    def parse(self):
        super().parse()
        if 'NVMe' not in self.fields['Description'] and 'CD5' not in self.fields['Description']:
            raise RalphAssetMimatch('This is not an NVMe drive')
        if self.fields['Model'] == 'CD5':
            # FIXME: temporary override to old model
            self.fields['Model'] = "P4510"

