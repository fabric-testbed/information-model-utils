#!/usr/bin/env python3
"""
Scan the network (NSO and later PCE) for connectivity information and produce a model of the network
"""

import argparse
import logging
import sys

from fimutil.netam.arm import NetworkARM

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    # split into different mutually exclusive operations

    parser.add_argument("-c", "--config", action="store",
                        help="config file")
    parser.add_argument("-d", "--debug", action="count",
                        help="Turn on debugging")
    parser.add_argument("-m", "--model", action="store",
                        help="Produce an ARM model of a site and save into indicated file")

    parser.add_argument("--isis-link-validation", action="store_true",
                        help="Generate model only based on NSO information")

    args = parser.parse_args()

    if args.debug is None:
        logging.basicConfig(level=logging.INFO)
    elif args.debug >= 1:
        logging.basicConfig(level=logging.DEBUG)

    if args.model is None:
        print('You must specify the name of the file to save the model into', file=sys.stderr)
        sys.exit(-1)

    arm = NetworkARM(config_file=args.config, isis_link_validation=args.isis_link_validation)

    logging.info('Querying NSO')
    if args.isis_link_validation:
        logging.info('Querying SR-PCE for IS-IS link validation')
    arm.build_topology()

    logging.info('Generating delegations')
    delegation1 = 'primary'
    arm.delegate_topology(delegation1)

    logging.info(f'Model completed, saving to {args.model}')
    arm.write_topology(file_name=args.model)
    logging.info('Saving completed')


