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
    # or
    # "Description: "Intel Corporation I350 Gigabit Network Connection (rev 01) in NIC Port 2 (0000:02:00.1)"
    # "Connection": "Connected to port 7 on uky2-data-sw"
    # or
    # "Description": "Mellanox Technologies MT42822 BlueField-2 integrated ConnectX-6 Dx network controller (rev 01)  in PCIe Slot 5 (0000:81:00.0) on NUMA Node 7"
    # "Connection": "Connected to port HundredGigE0/0/0/15 on renc-data-sw"
    REGEX_FIELDS = {'BDF': ['Description', ".+?\\(([0-9a-f:.]+)\\).*"],
                    'vBDF': ['Description', ".+/\\(([0-9a-f:.]+)\\).*"],
                    'Peer_port': ['Connection', ".+port ([\\w\\d/]+) .+"],
                    'VLAN': ['Connection', ".+ VLAN ([\\d]+) on.+"],
                    'Model': [['Description', ".+\\[([\\w-]+).*?\\].*"],
                              ['Description', r".*?\b(BlueField-\d+)\b.*?\b(ConnectX-\d+)\b"]],
                    'Slot': ['Description', ".+Slot ([\\d]+) .*"],
                    'NUMA': ['Description', '.+ NUMA Node ([\\+\\-\\d]+).*']}

    def __init__(self, *, uri: str, ralph: RalphURI):
        super().__init__(uri=uri, ralph=ralph)
        self.type = RalphAssetType.EthernetCardPF

    def parse(self):
        super().parse()
        if 'data-sw' not in self.fields['Connection']:
            raise RalphAssetMimatch('This is not a usable card')
        if self.fields.get('vBDF', None) is not None:
            self.type = RalphAssetType.EthernetCardVF

    def force_values(self, bdf: str or None = None,
                     vbdf: str or None = None,
                     mac: str or None = None,
                     desc: str or None = None,
                     speed: str or None = None,
                     connection: str or None = None,
                     peer_port: str or None = None,
                     vlan: str or None = None,
                     model: str or None = None,
                     slot: str or None = None,
                     numa: str or None = None,
                     ctype: RalphAssetType = RalphAssetType.EthernetCardPF):
        """
        when you just want to force values without parsing. type defaults to a VF
        """
        self.type = ctype
        if bdf:
            self.fields['BDF'] = bdf
        if vbdf:
            self.fields['vBDF'] = vbdf
        if peer_port:
            self.fields['Peer_port'] = peer_port
        if vlan:
            self.fields['VLAN'] = vlan
        if model:
            self.fields['Model'] = model
        if slot:
            self.fields['Slot'] = slot
        if mac:
            self.fields['MAC'] = mac
        if desc:
            self.fields['Description'] = desc
        if speed:
            self.fields['Speed'] = speed
        if connection:
            self.fields['Connection'] = connection
        if numa:
            self.fields['NUMA'] = numa
