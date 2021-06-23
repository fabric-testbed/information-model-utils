import logging
import re
from fimutil.ralph.asset import RalphAsset, RalphAssetType, RalphAssetMimatch

from fimutil.ralph.ralph_uri import RalphURI


class EthernetPort(RalphAsset):
    """
    This class knows how to parse necessary worker fields in Ralph
    """
    FIELD_MAP = '{MAC: .mac, Description: .model_name, Speed: .speed, Connection: .label}'
    REGEX_FIELDS = {'Peer_port': ['Connection', ".+port ([\\w]+ [0-9/]+) on.+"]}

    def __init__(self, *, uri: str, ralph: RalphURI):
        super().__init__(uri=uri, ralph=ralph)
        self.type = RalphAssetType.Ethernet

    def parse(self):
        super().parse()
        if self.fields['Connection'] is not None and  \
                ('Management' in self.fields['Connection'] or \
                 'Campus' in self.fields['Connection']):
            raise RalphAssetMimatch('This is not a usable port on dataplane switch')


class EthernetCardPort(EthernetPort):
    """
    This is a port on a allocatable card in worker
    """
    FIELD_MAP = '{MAC: .mac, Description: .model_name, Speed: .speed, Connection: .label}'
    REGEX_FIELDS = {'BDF': ['Description', ".+\\(([0-9a-f:.]+)\\).*"],
                    'Peer_port': ['Connection', ".+port ([\\w]+ [0-9/]+) on.+"],
                    'Model': ['Description', ".+\\[([\\w-]+)\\].*"]}

    def __init__(self, *, uri: str, ralph: RalphURI):
        super().__init__(uri=uri, ralph=ralph)
        self.type = RalphAssetType.Ethernet

    def parse(self):
        super().parse()
        if 'data-sw' not in self.fields['Connection']:
            raise RalphAssetMimatch('This is not a usable card')