from fimutil.ralph.asset import RalphAsset, RalphAssetType, RalphJSONError, RalphAssetMimatch

from fimutil.ralph.ralph_uri import RalphURI


class Ethernet(RalphAsset):
    """
    This class knows how to parse necessary worker fields in Ralph
    """
    FIELD_MAP = '{MAC: .mac, Description: .model_name, Speed: .speed, Connection: .label}'

    def __init__(self, *, uri: str, ralph: RalphURI):
        super().__init__(uri=uri, ralph=ralph)
        self.type = RalphAssetType.Ethernet

    def parse(self):
        super().parse()
        if 'data-sw' not in self.fields['Connection']:
            raise RalphAssetMimatch('This is not an dataplane card port')
