#!/bin/env python3

"""
Generate a CSV file with instance sizes
"""
import argparse
import sys
import csv
import json

# steps/increments of what is possible
# Disk and Ram are counted in GB

CPUs = [1, 2, 4, 8, 16, 32]
Disk = [10, 100, 500, 2000]
RAM = [4, 8, 16, 32, 64, 128]

SPECIAL_FLAVORS = [
    [64, 384, 4000]
]


def _get_instance_name(c, m, d):
    """
    Generate an instance name from core, memory and disk sizes
    """
    return ".".join(['fabric', 'c' + str(c), 'm' + str(m), 'd' + str(d)])


def generate_csv(file, dialect, delimiter):
    """
    Output a CSV
    """
    with open(file, 'w+', newline='') as f:
        spamwriter = csv.writer(f, delimiter=delimiter, dialect=dialect,
                                quotechar='|', quoting=csv.QUOTE_MINIMAL)
        spamwriter.writerow(['Flavor Name', 'CPUs', 'RAM', 'Disk'])
        # all possible combinations
        for c in CPUs:
            for m in RAM:
                for d in Disk:
                    flavor_name = _get_instance_name(c, m, d)
                    spamwriter.writerow([flavor_name, c, m, d])

        for sf in SPECIAL_FLAVORS:
            c, m, d = sf
            flavor_name = _get_instance_name(c, m, d)
            spamwriter.writerow([flavor_name, c, m, d])


def generate_json(file):
    """
    Output a JSON
    """
    obj = dict()
    # all possible combinations
    for c in CPUs:
        for m in RAM:
            for d in Disk:
                flavor_name = _get_instance_name(c, m, d)
                obj[flavor_name] = {"core": c, "ram": m, "disk": d}

    for sf in SPECIAL_FLAVORS:
        c, m, d = sf
        flavor_name = _get_instance_name(c, m, d)
        obj[flavor_name] = {"core": c, "ram": m, "disk": d}

    with open(file, 'w+') as f:
        json.dump(obj, f)


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    # split into different mutually exclusive operations

    parser.add_argument("-f", "--file", action="store",
                        help="output CSV file")
    parser.add_argument("-o", "--format", action="store",
                        help="CSV, JSON, defaults to CSV",
                        default='csv')
    parser.add_argument("-d", "--delimiter", action="store",
                        help="Delimiter character to use for CSV format", default=',')
    parser.add_argument("-i", "--dialect", action="store",
                        help="CSV dialect (excel, unix), defaults to excel",
                        default="excel")

    args = parser.parse_args()

    if args.file is None:
        print('You must specify the file name')
        sys.exit(-1)

    if args.format.lower() == "csv":
        generate_csv(args.file, args.dialect, args.delimiter)
    elif args.format.lower() == "json":
        generate_json(args.file)
    else:
        print(f'Unknown format {args.format}, exiting')
        sys.exit(-1)

    print(f'Output written to {args.file}')


