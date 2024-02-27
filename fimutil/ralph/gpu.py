from typing import List, Any
from dataclasses import dataclass

import pyjq
import logging

GPU_MODELS = ['Quadro RTX 6000/8000', 'Tesla T4', 'A40', 'A30 PCIe']


@dataclass(frozen=True)
class GPU:
    """
    Note that because GPUs aren't properly part of Ralph catalog structure,
    they appear as special fields inside the node and as such are not
    subclassed from RalphAsset (they don't have a URL).
    """
    Model: str
    Description: str
    BDF: list
    NUMA: list

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
                    logging.debug(f'Detected GPU {gpu_model}')
                    model = gpu_model
                    description = custom_fields[field]
                    # May contain multiple PCI devices depending on GPU type
                    # GPUs at CIEN rack have both an audio and video PCI device associated
                    # [root@cien-w1 ~]# lspci  | grep 25:00.
                    # 25:00.0 VGA compatible controller: NVIDIA Corporation AD102GL [RTX 6000 Ada Generation] (rev a1)
                    # 25:00.1 Audio device: NVIDIA Corporation AD102 High Definition Audio Controller (rev a1)
                    # bdf field woul show as 25:00.0 25:00.1
                    # Extract PCI devices information
                    bdf_values = custom_fields.get(f'{field}_pci_id', '').split()
                    bdf = [bdf.strip() for bdf in bdf_values]
                    # -1 means unknown
                    # Extract NUMA information
                    numa_val = custom_fields.get(f'{field}_numa_node', '-1')
                    numa = [numa_val] * len(bdf) if bdf else [numa_val]
                    ret.append(GPU(model, description, bdf, numa))
        return ret