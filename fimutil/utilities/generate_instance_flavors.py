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

"""
# 2000 flavors
CPUs = [x for x in range(4, 66, 2)]
Disk = [10, 100, 500, 2000]
RAM = [4, 8, 16, 24, 32, 64, 96, 128, 160, 192, 224, 256, 288, 320, 352, 384]

SPECIAL_FLAVORS = [
    [1, 2, 10],
    [1, 4, 10],
    [1, 4, 100],
    [1, 4, 500],
    [1, 4, 2000],
    [2, 2, 10],
    [2, 2, 100],
    [2, 4, 10],
    [2, 4, 100],
    [2, 8, 10],
    [2, 8, 100],
    [2, 8, 500],
    [2, 8, 2000],
    [64, 384, 4000]
]
"""

# 987 flavors
CPUs = [x for x in range(4, 64, 2)]
Disk = [10, 100, 500, 1000]
RAM = [4, 8, 16, 32, 64, 128, 256, 384]

SPECIAL_FLAVORS = [
    [1, 2, 10],
    [1, 4, 10],
    [1, 4, 100],
    [1, 4, 500],
    [1, 8, 10],
    [1, 8, 50],
    [1, 16, 10],
    [1, 16, 50],
    [1, 32, 50],
    [2, 2, 10],
    [2, 2, 100],
    [2, 4, 10],
    [2, 4, 100],
    [2, 8, 10],
    [2, 8, 100],
    [2, 8, 500],
    [2, 8, 1000],
    [64, 384, 1000]
]


def _get_instance_name(c, m, d):
    """
    Generate an instance name from core, memory and disk sizes
    """
    return ".".join(['fabric', 'c' + str(c), 'm' + str(m), 'd' + str(d)])


def generate_csv(file, dialect, delimiter) -> int:
    """
    Output a CSV
    """
    flavors = set()
    with open(file, 'w+', newline='') as f:
        spamwriter = csv.writer(f, delimiter=delimiter, dialect=dialect,
                                quotechar='|', quoting=csv.QUOTE_MINIMAL)
        spamwriter.writerow(['Flavor Name', 'CPUs', 'RAM', 'Disk'])
        # all possible combinations
        cnt = 0
        for c in CPUs:
            for m in RAM:
                for d in Disk:
                    flavor_name = _get_instance_name(c, m, d)
                    if flavor_name not in flavors:
                        spamwriter.writerow([flavor_name, c, m, d])
                        cnt += 1
                        flavors.add(flavor_name)
                    else:
                        raise Exception(f'Flavor {flavor_name} already defined')

        for sf in SPECIAL_FLAVORS:
            c, m, d = sf
            flavor_name = _get_instance_name(c, m, d)
            if flavor_name not in flavors:
                spamwriter.writerow([flavor_name, c, m, d])
                cnt += 1
                flavors.add(flavor_name)
            else:
                raise Exception(f'Flavor {flavor_name} already defined')

    return cnt


def generate_json(file) -> int:
    """
    Output a JSON file in a format consumable by FIM
    """
    obj = dict()
    flavors = set()
    # all possible combinations
    cnt = 0
    for c in CPUs:
        for m in RAM:
            for d in Disk:
                flavor_name = _get_instance_name(c, m, d)
                if flavor_name not in flavors:
                    obj[flavor_name] = {"core": c, "ram": m, "disk": d}
                    cnt += 1
                    flavors.add(flavor_name)
                else:
                    raise Exception(f'Flavor {flavor_name} already defined')
    for sf in SPECIAL_FLAVORS:
        c, m, d = sf
        flavor_name = _get_instance_name(c, m, d)
        if flavor_name not in flavors:
            obj[flavor_name] = {"core": c, "ram": m, "disk": d}
            cnt += 1
            flavors.add(flavor_name)
        else:
            raise Exception(f'Flavor {flavor_name} already defined')
    with open(file, 'w+') as f:
        json.dump(obj, f)

    return cnt


def generate_json_ansible(file, starting_id=10) -> int:
    """
    Generate JSON in a format consumable by ansible tasks
    """
    flavors = dict()
    obj = {'flavors': flavors}
    flavorset = set()

    # all possible combinations
    cnt = 0
    flavor_id = starting_id
    for c in CPUs:
        for m in RAM:
            for d in Disk:
                flavor_name = _get_instance_name(c, m, d)
                if flavor_name not in flavorset:
                    flavor_key = 'flavor' + str(flavor_id)
                    flavors[flavor_key] = {"vcpu": c, "ram": m*1024, "disk": d, "name": flavor_name, "id": flavor_id}
                    cnt += 1
                    flavor_id += 1
                    flavorset.add(flavor_name)
                else:
                    raise Exception(f'Flavor {flavor_name} already defined')

    for sf in SPECIAL_FLAVORS:
        c, m, d = sf
        flavor_name = _get_instance_name(c, m, d)
        if flavor_name not in flavorset:
            flavor_key = 'flavor' + str(flavor_id)
            flavors[flavor_key] = {"vcpu": c, "ram": m*1024, "disk": d, "name": flavor_name, "id": flavor_id}
            cnt += 1
            flavor_id += 1
            flavorset.add(flavor_name)
        else:
            raise Exception(f'Flavor {flavor_name} already defined')
    with open(file, 'w+') as f:
        json.dump(obj, f)

    return cnt


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    # split into different mutually exclusive operations

    parser.add_argument("-f", "--file", action="store",
                        help="output to a file")
    parser.add_argument("-o", "--format", action="store",
                        help="CSV, JSON, JSONA (JSON for Ansible), defaults to CSV",
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
        cnt = generate_csv(args.file, args.dialect, args.delimiter)
    elif args.format.lower() == "json":
        cnt = generate_json(args.file)
    elif args.format.lower() == "jsona":
        cnt = generate_json_ansible(args.file, 10)
    else:
        print(f'Unknown format {args.format}, exiting')
        sys.exit(-1)

    print(f'Output of {cnt} entries written to {args.file}')


