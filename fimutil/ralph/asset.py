from abc import ABC, abstractmethod
from typing import List, Dict

import json
import pyjq
from enum import Enum, auto

from fimutil.ralph.ralph_uri import RalphURI


class RalphAssetType(Enum):
    Node = auto()
    NVMe = auto()
    GPU = auto()
    Ethernet = auto()
    Abstract = auto()

    def __str__(self):
        return self.name


class RalphAsset(ABC):
    """
    Abstract Ralph asset - has one or more REST URIs knows
    how to remap JSON responses from those URIs into needed
    fields.
    """
    FIELD_MAP = str()

    def __init__(self, *, uri: str, ralph: RalphURI):
        self.uri = uri
        self.fieldmap = self.FIELD_MAP
        self.fields = dict()
        self.type = RalphAssetType.Abstract
        self.ralph = ralph
        self.raw_json_obj = None
        self.components = dict()

    def self_populate(self):
        # save JSON object
        self.raw_json_obj = self.ralph.get_json_object(self.uri)
        self.populate_fields_from_obj(json_obj=self.raw_json_obj)

    def populate_fields_from_obj(self, *, json_obj):

        self.fields = pyjq.first(self.fieldmap, json_obj)

    def get_fields(self) -> Dict[str, str]:
        return self.fields.copy()

    def parse(self):
        """
        Parse itself and subcomponents
        """
        self.self_populate()

    def __str__(self):
        ret = list()
        ret.append(str(self.type) + ": " + json.dumps(self.fields))
        for n, comp in self.components.items():
            ret.append('\t' + n + " " + str(comp))
        return "\n".join(ret)


class RalphJSONError(Exception):
    def __init__(self, msg: str):
        super().__init__(f'RalphJSONError: {msg}')


class RalphAssetMimatch(Exception):
    def __init__(self, msg: str):
        super().__init__(f'Ralph asset mismatch: {msg}')