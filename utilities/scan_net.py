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

    parser.add_argument("-s", "--site", action="store",
                        help="Scan a site for information")
    parser.add_argument("-n", "--nso_url", action="store",
                        help="NSO API URL")
    parser.add_argument("-u", "--nso_user", action="store",
                        help="NSO username")
    parser.add_argument("-p", "--nso_pass", action="store",
                        help="NSO password")
    parser.add_argument("-d", "--debug", action="count",
                        help="Turn on debugging")
    parser.add_argument("-m", "--model", action="store",
                        help="Produce an ARM model of a site and save into indicated file")

    args = parser.parse_args()

    if args.debug is None:
        logging.basicConfig(level=logging.INFO)
    elif args.debug >= 1:
        logging.basicConfig(level=logging.DEBUG)

    if args.nso_url is None or \
        args.nso_user is None or \
        args.nso_pass is None:
        print('You must specify the NSO URL, username and password', file=sys.stderr)
        sys.exit(-1)

    if args.model is None:
        print('You must specify the name of the file to save the model into', file=sys.stderr)
        sys.exit(-1)

    arm = NetworkARM(nso_url=args.nso_url, nso_user=args.nso_user, nso_pass=args.nso_pass)

    logging.info('Querying NSO')
    arm.build_topology()

    logging.info('Generating delegations')
    delegation1 = 'primary'
    arm.delegate_topology(delegation1)

    logging.info(f'Model completed, saving to {args.model}')
    arm.write_topology(file_name=args.model)
    logging.info('Saving completed')



