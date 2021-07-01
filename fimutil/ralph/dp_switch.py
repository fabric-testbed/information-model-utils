import pyjq
import logging

from fimutil.ralph.ralph_uri import RalphURI
from fimutil.ralph.asset import RalphAsset, RalphAssetType, RalphAssetMimatch
from fimutil.ralph.model import SimpleModel
from fimutil.ralph.ethernetport import EthernetPort


class DPSwitch(RalphAsset):
    """
    Dataplane switch
    """
    FIELD_MAP = '{Name: .hostname, SN: .sn, IP: .ipaddresses[0]}'

    def __init__(self, *, uri: str, ralph: RalphURI):
        super().__init__(uri=uri, ralph=ralph)
        self.type = RalphAssetType.DPSwitch
        self.model = None

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

    def __str__(self):
        ret = super().__str__()
        return ret + '\n\t' + str(self.model)