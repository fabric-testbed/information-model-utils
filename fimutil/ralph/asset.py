from abc import ABC, abstractmethod
from typing import List, Dict

import json
from enum import Enum, auto

from fimutil.ralph.ralph_uri import RalphURI


class RalphAssetType(Enum):
    Worker = auto()
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
    FIELD_MAP = dict()

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
        """
        Populate fields dictionary based on a json response
        from API.
        """
        for k, v in self.fieldmap.items():
            # each fieldmap value is a . separated path in dictionary
            # if a value of a dictionary is a list, then '/[0-9]' refers
            # to the list index
            # hierarchy

            level_dict = json_obj
            for level in v.split('.'):
                # e.g. results/0.sn
                level_list = level.split('/')
                level = level_list[0]
                if len(level_list) == 2:
                    level_index = int(level_list[1])
                else:
                    level_index = -1
                if level_dict.get(level, None) is None:
                    raise RalphJSONError(f'Unable to find entry for {level} in asset '
                                         f'response for type {self.type} within {v} hierarchy')
                if level_index < 0:
                    level_dict = level_dict[level]
                else:
                    level_dict = level_dict[level][level_index]

            level_val = level_dict  # this is now the value we sought
            if not isinstance(level_val, str):
                raise RalphJSONError(f'Expected to return string instead of object in asset'
                                     f'response for type {self.type} within {v} hierarchy')
            self.fields[k] = level_val

    def get_fields(self) -> Dict[str, str]:
        return self.fields.copy()

    def parse(self):
        """
        Parse itself and subcomponents
        """
        self.self_populate()

    def __str__(self):
        ret = list()
        ret.append('Worker: ' + json.dumps(self.fields))
        for n, comp in self.components.items():
            ret.append('\t' + n + ": " + json.dumps(comp.fields))
        return "\n".join(ret)


class RalphJSONError(Exception):
    def __init__(self, msg: str):
        super().__init__(f'RalphJSONError: {msg}')


class RalphAssetMimatch(Exception):
    def __init__(self, msg: str):
        super().__init__(f'Ralph asset mismatch: {msg}')