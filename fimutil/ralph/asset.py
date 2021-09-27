from abc import ABC, abstractmethod
from typing import List, Dict
import re
import logging

import json
import pyjq
from enum import Enum, auto

from fimutil.ralph.ralph_uri import RalphURI


class RalphAssetType(Enum):
    Node = auto()
    NVMe = auto()
    GPU = auto()
    Ethernet = auto()
    EthernetCardPF = auto()
    EthernetCardVF = auto()
    Model = auto()
    Storage = auto()
    DPSwitch = auto()
    Abstract = auto()

    def __str__(self):
        return self.name


class RalphAsset(ABC):
    """
    Abstract Ralph asset - has one or more REST URIs knows
    how to remap JSON responses from those URIs into needed
    fields.
    """
    # These are fields extractable using pyjq query expressions
    FIELD_MAP = str()
    # These are fields that require regex matching from the fields extracted in FIELD_MAP
    # unmatched regexes simply leave the field unfilled without generating errors
    REGEX_FIELDS = {}

    def __init__(self, *, uri: str, ralph: RalphURI):
        self.uri = uri
        self.fieldmap = self.FIELD_MAP
        self.regex_fields = self.REGEX_FIELDS
        self.fields = dict()
        self.type = RalphAssetType.Abstract
        self.ralph = ralph
        self.raw_json_obj = None
        self.components = dict()

    def self_populate(self):
        # save JSON object
        self.raw_json_obj = self.ralph.get_json_object(self.uri)
        # massage results - sometimes they are part of the larger query,
        # sometimes node by itself
        try:
            if self.raw_json_obj.get('results', None) is not None:
                self.raw_json_obj = self.raw_json_obj['results'][0]
        except IndexError:
            raise RuntimeError(f'Unable to find asset {self.uri}')

        self.populate_fields_from_obj(json_obj=self.raw_json_obj)
        # populate regex fields
        for k, v in self.regex_fields.items():
            if self.fields[v[0]] is None:
                continue
            matches = re.match(v[1], self.fields[v[0]])
            if matches is not None:
                self.fields[k] = matches.group(1)

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
        ret.append(str(self.type) + "[" + self.uri + "]" + ": " + json.dumps(self.fields))
        for n, comp in self.components.items():
            ret.append('\t' + n + " " + str(comp))
        return "\n".join(ret)

    def __repr__(self):
        return self.__str__()


class RalphJSONError(Exception):
    def __init__(self, msg: str):
        super().__init__(f'RalphJSONError: {msg}')


class RalphAssetMimatch(Exception):
    def __init__(self, msg: str):
        super().__init__(f'Ralph asset mismatch: {msg}')