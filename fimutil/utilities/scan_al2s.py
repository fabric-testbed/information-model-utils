#!/usr/bin/env python3
"""
Scan the Virtual Networks API to create an ARM for AL2S
"""

import argparse
import logging
import sys

from fimutil.al2s.arm import Al2sARM


def main():
    parser = argparse.ArgumentParser()
    # split into different mutually exclusive operations

    parser.add_argument("-c", "--config", action="store",
                        help="config file")
    parser.add_argument("-d", "--debug", action="count",
                        help="Turn on debugging")
    parser.add_argument("-m", "--model", action="store",
                        help="Produce an ARM model of a site and save into indicated file")

    args = parser.parse_args()

    if args.debug is None:
        logging.basicConfig(level=logging.INFO)
    elif args.debug >= 1:
        logging.basicConfig(level=logging.DEBUG)

    if args.model is None:
        print('You must specify the name of the file to save the model into', file=sys.stderr)
        sys.exit(-1)

    arm = Al2sARM(config_file=args.config)

    logging.info('Querying AL2S')
    arm.build_topology()

    logging.info('Generating delegations')
    delegation1 = 'primary'
    arm.delegate_topology(delegation1)

    logging.info(f'Model completed, saving to {args.model}')
    arm.write_topology(file_name=args.model)
    logging.info('Saving completed')


if __name__ == "__main__":
    main()
