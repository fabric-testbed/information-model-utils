[![PyPI](https://img.shields.io/pypi/v/fim-utils?style=plastic)](https://pypi.org/project/fim-utils/)

# Information Model Utilities

There are a number of libraries and utilities in this repo that help convert 
information from various sources into FABRIC Information Models

## Utilities Library

This library uses different sources to extract necessary information to build
site and network advertisement models for FABRIC control framework:
- fimutil.ralph - uses Ralph inventory system REST API to create site models
- fimutil.netam - uses NSO and other sources to create a network model
- fimutil.al2s - uses Internet2 Virtual Networks API to create a network model

### Ralph REST
Since Ralph presents information in the form of nested dictionaries, the library
uses a [PyJQ](https://pypi.org/project/pyjq/) to map the necessary properties. For example,
a model name of a server can be found as `.results[0].model.category.name`, meaning
'results' dictionary, then take the first element of the list (index 0), then
follow dictionary hierarchy ['model']['category']['name']. It throws
`RalphJSONError` if the indicated field cannot be found. Each class has its own
map of fields that it can get from a JSON document. 

When needed more REST calls are made to additional URLs found in the initial document to
determine the details of specific resource assets.

The library defines multiple classes of assets (all children of a base Asset class),
each of which knows how to parse itself and its own possible subcomponents.
It also defines a class that helps invoke Ralph REST API.
Thus getting information about a single worker can be done as simple as
```
ralph = RalphURI(token=args.token, base_uri=args.base_uri)
worker = WorkerNode(uri=worker_search_uri, ralph=ralph)
worker.parse()
print(worker)
```
*NOTE: We have created a number of conventions for how the information is stored in Ralph
to support FABRIC hardware. Ansible scripts scrape information from hardware into Ralph
following those conventions. The way someone else may decide to store the same information
in Ralph may not conform to those conventions and make utilities in this package useless.*


## End-user utilities

Pip install the package (see Installation section). The utilities should be on PATH. 
Get a token from Ralph GUI for the Ralph API and username/password for NSO. 

### scan_worker.py

Scans an individual worker node based on its FQDN and returns information about
it and its components. 

Invocation:
```
$ scan_worker.py -w <worker FQDN> -t <Ralph API Token> -b https://hostname/api/
```

The utility is smart enough to try and discard components that don't need to
be reflected in the information model (internal worker disks, iDrac or 
disconnected ports etc)

You can find your Ralph API token in your profile page in Ralph.

### scan_site.py

Similar to above, searches for all usable components of a site (workers nodes, data switch, storage) and prints out
what it finds or saves to a model.

Invocation:
```
$ scan_site.py -b https://hostname/api/ -s <site acronym> -t <token> -p
```
Prints information collected from Ralph

```
$ scan_site.py -b https://hostname/api/ -s <site acronym> -t <token> -a <street address string> -m <model name>.graphml -c <config file>
```
Saves site model into a file in GraphML format. 

Using `-a` is strongly advised (to support GIS-style visualizations of slices), the code automatically tests the
provided postal address to make sure it is resolvable into Lat/Lon coordinates.

You can also use `--brief` option with `-p` to have a shorter printout. 

To produce a site JSON file, use `-j` or `--json` followed by a filename.

Options`-p`, `-m` and `-j` could be used together (i.e. to produce a model, a printout and a JSON file). If none is specified
the site is scanned however no extra output is produced. 

The config file (by default `.scan-config.json` allows to statically override certain scanned details:
- Allows for site to say it is using some other site's DP switch

The general format example of the file is as follows (SITE1, SITE2 are all-caps site names):
```
{
  "ram_offset": 24
  "SITE1": {
    "dpswitch": {
      "URL": <URL of SITE2's dp switch in Ralph>,
      "Site": "SITE2"
    },
    "ptp": true,
    "storage": {
      "Disk": "500TB"
    },
    "workers": {
      <worker FQDN>: {
        "Disk": "100TB",
        "Core": "15",
        "RAM": "2TB",
        "CPU": "4",
        "cpu_allocation_ratio": 1
      }
    },
    "mac_offset": "f2:ab"
    "connected_ports": [ "HundredGigE0/0/0/15" ]
  }
}
```
`ram_offset` specifies an offset to subtract from the actual RAM value. This is adjustment needed to for RAM allocated to NOVA on the workers.
`mac_offset` intended to be used with OpenStack sites to aid unique MAC generation for vNICs. Note
that the first octet of mac_offset must be [even](https://github.com/openstack/neutron-lib/blob/cf494c8be10b36daf238fa12cf7c615656e6640d/neutron_lib/api/validators/__init__.py#L40).

`connected_ports` are only effective for generating JSON files (do not affect ARMs) which are then used to put other ports
(not include uplinks and facility ports) into admin DOWN state.

`cpu_allocation_ratio` intended to be used when enabling over subscription for a site. 
By default, this is set to 1 implying no over subscription. 
For EDC/EDUKY, this may be set to 16 indicating the total core count would be multiplied with this number in the model. 

### scan_net.py

Similar to above, interrogates NSO, PCE (future work) to create a model of the inter-site network.

Invocation:
```
$ scan_net.py -c config_file -m <model name>.graphml --isis-link-validation
```

Saves the model into a file indicated with `-m` in GraphML format.

Optional `--isis-link-validation` enables verification and validation of active links via checking with SR-PCE for IS-IS adjacency in IPv4 topology. Without it, the model generation will only rely on NSO information.

Optional `-c` points to a YAML configure file with NSO and SR-PCE REST authentication parameters. Without it, default location is $HOME/.netam.conf or /etc/netam.conf. Example below:
```
nso_url: https://192.168.11.222/restconf/data
nso_user: admin
nso_pass: xxxxx
sr_pce_url: http://192.168.13.3:8080/topo/subscribe/txt
sr_pce_user: admin
sr_pce_pass: xxxxx
sites_config: ...NetworkController/device-config/ansible/inventory/sites.yaml
```
The `sites_config` yaml file is generated priorly with `NetworkController/device-config/ansible/inventory/fabric-cisco-dev.py --yaml`.

### scan_al2s.py

Similar to above, interrogates NSO, PCE (future work) to create a model of the inter-site network.

Invocation:
```
$ scan_al2s.py  -c config_file -m <model name>.graphml
```

Saves the model into a file indicated with `-m` in GraphML format.

Optional `-c` points to a YAML configure file with NSO and SR-PCE REST authentication parameters. Without it, default location is $HOME/al2s.conf or /etc/al2s.conf. Example below:
```
api_base_url: https://api.ns.internet2.edu
api_access_key: xxx-xxx-xxx
```

### generate_instance_flavors.py

A utility to generate a list of OpenStack VM flavors based on permutations of CPU, RAM and disk.

Can output the results in 3 flavors: CSV, JSON for FIM (usable as part of FIM catalog datafile)
and JSON Ansible usable for Ansible tasks that load flavors into OpenStack. 
```
usage: generate_instance_flavors.py [-h] [-f FILE] [-o FORMAT] [-d DELIMITER] [-i DIALECT]

optional arguments:
  -h, --help            show this help message and exit
  -f FILE, --file FILE  output CSV file
  -o FORMAT, --format FORMAT
                        CSV, JSON, JSONA (JSON for Ansible), defaults to CSV
  -d DELIMITER, --delimiter DELIMITER
                        Delimiter character to use for CSV format
  -i DIALECT, --dialect DIALECT
                        CSV dialect (excel, unix), defaults to excel
```
Typical usage is
```
$ generate_instance_flavors.py -o JSONA -f flavors.json
```
## Installation

### For use

You can use a virtualenv or install directly:
```
$ pip install fim-utils
```

### For development

Developed under Python 3.9. Using virtualenv, something like this should work:

```
$ git clone https://github.com/fabric-testbed/information-model-utils.git
$ mkvirtualenv -r requirements.txt fim-utils
$ cd information-model-utils/utilities/
$ python scan_worker.py <options>
```
Note that to install PyJQ dependency as part of requirements you need to have `automake` installed on your system. So
`yum install automake` or `brew install automake` or similar. 

### Building and packaging 

Use (make sure to `pip install flit` first):
```
$ flit build
$ flit publish
```
