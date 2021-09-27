#!/usr/bin/env python3
"""
Scan workers given on command line printing to stdout all pertinent info
"""

import argparse
import traceback

import logging
import sys

from fimutil.ralph.ralph_uri import RalphURI
from fimutil.ralph.worker_node import WorkerNode

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    # split into different mutually exclusive operations

    parser.add_argument("-w", "--worker", action="store",
                        help="Scan single worker information (use FQDN)")
    parser.add_argument("-b", "--base_uri", action="store",
                        help="Base URL of API")
    parser.add_argument("-d", "--debug", action="count",
                        help="Turn on debugging")
    parser.add_argument("-t", "--token", action="store",
                        help="Ralph API token value")
    parser.add_argument("-n", "--no-ssl", action="store_true",
                        help="Disable SSL server sert validation (use with caution!)")

    args = parser.parse_args()

    if args.debug is None:
        logging.basicConfig(level=logging.INFO)
    elif args.debug >= 1:
        logging.basicConfig(level=logging.DEBUG)

    if args.worker is None:
        print('You must specify the worker', file=sys.stderr)
        sys.exit(-1)

    if args.base_uri is None:
        print('You must specify the base URL (typically https://hostname/api/data-center-assets/',
              file=sys.stderr)
        sys.exit(-1)

    if not args.base_uri.endswith('/'):
        args.base_uri += '/'

    if args.token is None:
        print('You must specify a Ralph API token, you can find it in your profile page in Ralph',
              file=sys.stderr)
        sys.exit(-1)

    ralph = RalphURI(token=args.token, base_uri=args.base_uri, disable_ssl=args.no_ssl)
    worker = WorkerNode(uri=args.base_uri + 'data-center-assets/?hostname=' + args.worker,
                        ralph=ralph)
    worker.parse()
    print(worker)

