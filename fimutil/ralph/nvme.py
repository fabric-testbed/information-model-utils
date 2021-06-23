import re
import logging

from fimutil.ralph.asset import RalphAsset, RalphAssetType, RalphAssetMimatch

from fimutil.ralph.ralph_uri import RalphURI


class NVMeDrive(RalphAsset):
    """
    This class knows how to parse necessary worker fields in Ralph
    """
    FIELD_MAP = '{SN: .serial_number, Description: .model_name}'
    REGEX_FIELDS = {'BDF': ["Description", ".+\\(([0-9a-f:.]+)\\).*"],
                    'Model': ["Description", ".+NVMe ([\\w]+).*"]}

    def __init__(self, *, uri: str, ralph: RalphURI):
        super().__init__(uri=uri, ralph=ralph)
        self.type = RalphAssetType.NVMe

    def parse(self):
        super().parse()
        if 'NVMe' not in self.fields['Description']:
            raise RalphAssetMimatch('This is not an NVMe drive')

