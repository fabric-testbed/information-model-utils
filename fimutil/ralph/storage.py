import pyjq

from fimutil.ralph.ralph_uri import RalphURI
from fimutil.ralph.asset import RalphAsset, RalphAssetType, RalphAssetMimatch
from fimutil.ralph.model import StorageModel


class Storage(RalphAsset):
    """
    Storage array has pretty minimal information
    """
    FIELD_MAP = '{Name: .hostname, SN: .sn}'

    def __init__(self, *, uri: str, ralph: RalphURI):
        super().__init__(uri=uri, ralph=ralph)
        self.type = RalphAssetType.Storage
        self.model = None

    def parse(self):
        super().parse()

        # find model
        model_url = pyjq.one('.model.url', self.raw_json_obj)
        self.model = StorageModel(uri=model_url, ralph=self.ralph)
        try:
            self.model.parse()
        except RalphAssetMimatch:
            pass

    def __str__(self):
        ret = super().__str__()
        return ret + '\n\t' + str(self.model)
