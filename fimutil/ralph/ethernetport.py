import logging
import re
from fimutil.ralph.asset import RalphAsset, RalphAssetType, RalphAssetMimatch

from fimutil.ralph.ralph_uri import RalphURI


class EthernetPort(RalphAsset):
    """
    This is a ethernet port on a switch (or other generic port)
    """
    FIELD_MAP = '{MAC: .mac, Description: .model_name, Speed: .speed, Connection: .label}'
    REGEX_FIELDS = {'Peer_port': ['Connection', ".+port ([\\w]+[0-9/]+) .+"]}

    def __init__(self, *, uri: str, ralph: RalphURI):
        super().__init__(uri=uri, ralph=ralph)
        self.type = RalphAssetType.Ethernet

    def parse(self):
        super().parse()
        if self.fields['Connection'] is not None and  \
                ('Management' in self.fields['Connection'] or
                 'Campus' in self.fields['Connection']):
            raise RalphAssetMimatch('This is not a usable port on dataplane switch')


class EthernetCardPort(EthernetPort):
    """
    This is a port on a allocatable card in worker
    """
    FIELD_MAP = '{MAC: .mac, Description: .model_name, Speed: .speed, Connection: .label}'
    # "Description": "Mellanox Technologies MT27800 Family [ConnectX-5] in PCIe Slot 3 (0000:41:00.0)"
    # "Connection": "Connected to port TwentyFiveGigE0/0/0/23/2 on lbnl-data-sw"
    # or
    # "Description": "Mellanox Technologies MT28908 Family
    # [ConnectX-6 Virtual Function] in (0000:e2:00.1)/(0000:e2:12.3)"
    # "Connection": "Connected to port HundredGigE0/0/0/21 and Tagged using VLAN 2018 on lbnl-data-sw"
    REGEX_FIELDS = {'BDF': ['Description', ".+?\\(([0-9a-f:.]+)\\).*"],
                    'vBDF': ['Description', ".+/\\(([0-9a-f:.]+)\\).*"],
                    'Peer_port': ['Connection', ".+port ([\\w]+[0-9/]+) .+"],
                    'VLAN': ['Connection', ".+ VLAN ([\\d]+) on.+"],
                    'Model': ['Description', ".+\\[([\\w-]+).*?\\].*"],
                    'Slot': ['Description', ".+Slot ([\\d]+) .*"]}

    def __init__(self, *, uri: str, ralph: RalphURI):
        super().__init__(uri=uri, ralph=ralph)
        self.type = RalphAssetType.EthernetCardPF

    def parse(self):
        super().parse()
        if 'data-sw' not in self.fields['Connection']:
            raise RalphAssetMimatch('This is not a usable card')
        if self.fields.get('vBDF', None) is not None:
            self.type = RalphAssetType.EthernetCardVF
