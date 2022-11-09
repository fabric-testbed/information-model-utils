import pyjq
import logging
from typing import List

from fimutil.ralph.ralph_uri import RalphURI
from fimutil.ralph.asset import RalphAsset, RalphAssetType, RalphAssetMimatch
from fimutil.ralph.model import SimpleModel
from fimutil.ralph.ethernetport import EthernetPort


class DPSwitch(RalphAsset):
    """
    Dataplane switch
    """
    FIELD_MAP = '{Name: .hostname, SN: .sn, IP: .ipaddresses[0], ' \
                'AL2S_SWITCH: .custom_fields.al2s_remote_switch_name,' \
                'AL2S_vlans: .custom_fields.al2s_vlan_ranges, ' \
                'Local_vlans: .custom_fields.dataplane_vlan_ranges}'

    def __init__(self, *, uri: str, ralph: RalphURI):
        super().__init__(uri=uri, ralph=ralph)
        self.type = RalphAssetType.DPSwitch
        self.model = None
        self.vlan_ranges = None

    @staticmethod
    def __vlan_list(*vlan_ranges) -> List[int]:
        """
        Convert vlan range string into a list of vlans. Can be a-b, c-d etc.
        """
        ret = list()
        for vr in vlan_ranges:
            if not vr:
                continue
            # each range can be a-b,c-d
            sr = vr.split(',')

            for r in sr:
                r = r.strip()
                start, end = r.split('-')
                ret.extend(range(int(start), int(end) + 1))
        return ret or None

    def parse(self):
        super().parse()

        # find model
        model_url = pyjq.one('.model.url', self.raw_json_obj)
        self.model = SimpleModel(uri=model_url, ralph=self.ralph)
        try:
            self.model.parse()
        except RalphAssetMimatch:
            logging.warning('Unable to parse switch model, continuing')

        try:
            port_urls = pyjq.all('.ethernet[].url', self.raw_json_obj)
        except ValueError:
            logging.warning('Unable to find any ethernet ports in node, continuing')
            port_urls = list()

        port_index = 1
        for port in port_urls:
            port = EthernetPort(uri=port, ralph=self.ralph)
            try:
                port.parse()
            except RalphAssetMimatch:
                continue
            self.components['port-' + str(port_index)] = port
            port_index += 1

        # vlan ranges
        self.vlan_ranges = self.__vlan_list(self.fields['Local_vlans'], self.fields['AL2S_vlans'])

    def __str__(self):
        ret = super().__str__()
        return ret + '\n\t' + str(self.model)