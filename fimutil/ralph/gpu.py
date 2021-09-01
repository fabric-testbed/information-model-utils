from typing import List, Any
from dataclasses import dataclass

import pyjq

GPU_MODELS = ['Quadro RTX 6000/8000', 'Tesla T4']


@dataclass(frozen=True)
class GPU:
    """
    Note that because GPUs aren't properly part of Ralph catalog structure,
    they appear as special fields inside the node and as such are not
    subclassed from RalphAsset (they don't have a URL).
    """
    Model: str
    Description: str
    BDF: str

    @staticmethod
    def find_gpus(node_raw_json) -> List[Any]:
        """
        Find if there are GPUs in this node. Returns a list
        of GPU objects (which can be empty).
        """
        custom_fields = pyjq.one('.custom_fields', node_raw_json)
        ret = list()
        for field in custom_fields:
            for gpu_model in GPU_MODELS:
                if gpu_model in custom_fields[field]:
                    model = gpu_model
                    description = custom_fields[field]
                    bdf = custom_fields[field + '_pci_id']
                    ret.append(GPU(model, description, bdf))
        return ret