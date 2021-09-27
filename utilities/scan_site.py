#!/usr/bin/env python3
"""
Scan a site given on command line printing to stdout all pertinent info
"""

import argparse
import traceback
import logging
import sys

from fimutil.ralph.ralph_uri import RalphURI
from fimutil.ralph.site import Site

from fimutil.ralph.fim_helper import site_to_fim

from fim.slivers.delegations import DelegationType, Pools
from fim.slivers.capacities_labels import Location, LocationException

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    # split into different mutually exclusive operations

    parser.add_argument("-s", "--site", action="store",
                        help="Scan a site for information")
    parser.add_argument("-b", "--base_uri", action="store",
                        help="Base URL of API")
    parser.add_argument("-d", "--debug", action="count",
                        help="Turn on debugging")
    parser.add_argument("-t", "--token", action="store",
                        help="Ralph API token value")
    parser.add_argument("-p", "--print", action="store_true",
                        help="Print output of a scan")
    parser.add_argument("-m", "--model", action="store",
                        help="Produce an ARM model of a site and save into indicated file")
    parser.add_argument("-a", "--address", action="store",
                        help="Provide address for the site")
    parser.add_argument("-n", "--no-ssl", action="store_true",
                        help="Disable SSL server sert validation (use with caution!)")

    args = parser.parse_args()

    if args.debug is None:
        logging.basicConfig(level=logging.INFO)
    elif args.debug >= 1:
        logging.basicConfig(level=logging.DEBUG)

    if args.site is None:
        print('You must specify the site name', file=sys.stderr)
        sys.exit(-1)

    args.site = args.site.upper()

    if args.base_uri is None:
        print('You must specify the base URL (typically https://hostname/api/data-center-assets/',
              file=sys.stderr)
        sys.exit(-1)

    if args.token is None:
        print('You must specify a Ralph API token, you can find it in your profile page in Ralph',
              file=sys.stderr)
        sys.exit(-1)

    if args.address is not None:
        loc = Location(postal=args.address)
        print(f'Validating site postal address {args.address}')
        try:
            lat, lon = loc.to_latlon()
            print(f'{lat=}, {lon=}')
        except LocationException as le:
            print(f'Unable to convert provided site postal address into coordinates. Please consider altering'
                  f'it, e.g. adding zip code, removing suite etc')
            sys.exit(-1)
    else:
        print('WARNING: you did not provide a site postal address with -a option - '
              'it is strongly recommended that you do.')

    ralph = RalphURI(token=args.token, base_uri=args.base_uri, disable_ssl=args.no_ssl)
    site = Site(site_name=args.site, ralph=ralph)

    logging.info(f'Cataloging site {args.site}')
    site.catalog()
    logging.info('Cataloging complete')

    if args.model is not None:
        logging.info('Producing an ARM model')
        topo = site_to_fim(site, args.address)
        logging.info('Generating delegations')
        delegation1 = 'primary'

        # pools are blank - all delegations for interfaces are in the network ad
        topo.single_delegation(delegation_id=delegation1,
                               label_pools=Pools(atype=DelegationType.LABEL),
                               capacity_pools=Pools(atype=DelegationType.CAPACITY))
        logging.info(f'Model completed, saving to {args.model}')
        topo.serialize(file_name=args.model)
        logging.info('Saving completed')

    if args.print:
        print(site)


