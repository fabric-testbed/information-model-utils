from typing import List, Any
from dataclasses import dataclass

import pyjq
import logging
import re

# Xilinx Corporation Alveo U280 Golden Image
FPGA_MODELS = ['Alveo U280', 'Alveo SN1022']
PORT_REGEX = ".+port ([\\w\\d/]+) .+"
MAX_PORTS = 8


@dataclass(frozen=True)
class FPGA:
    """
    Note that because GPUs aren't properly part of Ralph catalog structure,
    they appear as special fields inside the node and as such are not
    subclassed from RalphAsset (they don't have a URL).
    """
    Model: str
    Description: str
    BDF: str
    USB_ID: str
    SN: str
    Ports: list[str]
    NUMA: str

    @staticmethod
    def find_fpgas(node_raw_json) -> List[Any]:
        """
        Find if there are FPGAs in this node. Returns a list
        of FPGA objects (which can be empty).
        """
        custom_fields = pyjq.one('.custom_fields', node_raw_json)
        ret = list()
        fpga_index = 1
        for field in custom_fields:
            for fpga_model in FPGA_MODELS:
                try:
                    ports = []
                    if fpga_model in custom_fields[field]:
                        logging.debug(f'Detected FPGA {fpga_model}')
                        model = fpga_model
                        description = custom_fields[field]
                        bdf = custom_fields[field + '_pci_id']
                        # -1 means unknown
                        numa = custom_fields.get(field + '_numa_node', '-1')
                        sn = custom_fields[f'fpga{fpga_index}_sn']
                        usb_id = custom_fields.get(f'fpga{fpga_index}_usb_device_id')
                        for i in range(1, MAX_PORTS):
                            # find ports
                            port_string = custom_fields.get(f'fpga{fpga_index}_port_{i}')
                            if port_string:
                                matches = re.match(PORT_REGEX, port_string)
                                if matches is not None:
                                    ports.append(matches.group(1))
                        if len(ports) == 0:
                            logging.error(f'Unable to find any ports for FPGA {model}, expecting fpgaX_port_1 etc')
                        ret.append(FPGA(model, description, bdf, usb_id, sn, ports, numa))
                        fpga_index += 1
                except KeyError:
                    logging.error('Unable to find one of the expected FPGA fields: fpgaX_[usb_device_id, port_1, port_2]')
                    logging.error(f'Available custom fields are: {custom_fields=}')
        return ret
