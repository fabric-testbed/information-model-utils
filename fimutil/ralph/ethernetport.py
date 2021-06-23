import logging
import re
from fimutil.ralph.asset import RalphAsset, RalphAssetType, RalphJSONError, RalphAssetMimatch

from fimutil.ralph.ralph_uri import RalphURI


class Ethernet(RalphAsset):
    """
    This class knows how to parse necessary worker fields in Ralph
    """
    FIELD_MAP = '{MAC: .mac, Description: .model_name, Speed: .speed, Connection: .label}'
    REGEX_FIELDS = {'BDF': ['Description', ".+\\(([0-9a-f:.]+)\\).*" ],
                    'Peer_port': ['Connection', ".+port ([\\w]+ [0-9/]+) on.+"],
                    'Model': ['Description', ".+\\[([\\w-]+)\\].*"]}

    def __init__(self, *, uri: str, ralph: RalphURI):
        super().__init__(uri=uri, ralph=ralph)
        self.type = RalphAssetType.Ethernet

