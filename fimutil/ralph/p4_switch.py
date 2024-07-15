import pyjq
import logging

from fimutil.ralph.ralph_uri import RalphURI
from fimutil.ralph.asset import RalphAsset, RalphAssetType, RalphAssetMimatch
from fimutil.ralph.model import SimpleModel
from fimutil.ralph.ethernetport import EthernetPort


class P4Switch(RalphAsset):
    """
    Dataplane switch
    """
    FIELD_MAP = '{Name: .hostname, SN: .sn, IP: .ipaddresses[0]}'

    def __init__(self, *, uri: str, ralph: RalphURI):
        super().__init__(uri=uri, ralph=ralph)
        self.type = RalphAssetType.P4Switch
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

    def get_dp_ports(self):
        """
        Return a list of names of DP switch ports this node is connected to
        """
        dp_ports = list()
        for n, comp in self.components.items():
            if comp.__dict__.get('type') and comp.type == RalphAssetType.EthernetCardPF:
                if comp.fields.get('Peer_port'):
                    dp_ports.append(comp.fields.get('Peer_port'))

        return dp_ports
