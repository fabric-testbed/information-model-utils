[![Requirements Status](https://requires.io/github/fabric-testbed/information-model-utils/requirements.svg?branch=main)](https://requires.io/github/fabric-testbed/information-model-utils/requirements/?branch=main)

[![PyPI](https://img.shields.io/pypi/v/fim-utils?style=plastic)](https://pypi.org/project/fim-utils/)

# Information Model Utilities

There are a number of libraries and utilities in this repo that help convert 
information from various sources into FABRIC Information Models

## Utilities Library

This library uses different sources to extract necessary information to build
site and network advertisement models for FABRIC control framework:
- fimutil.ralph - uses Ralph inventory system REST API to create site models
- fimutil.netam - uses NSO and other sources to create a network model

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
$ scan_site.py -b https://hostname/api/ -s <site acronym> -t <token> -a <street address string> -m <model name>.graphml
```
Saves site model into a file in GraphML format. Both `-p` and `-m` could be used together. If neither is specified
the site is scanned however no extra output is produced. 

Using `-a` is strongly advised (to support GIS-style visualizations of slices), the code automatically tests the
provided postal address to make sure it is resolvable into Lat/Lon coordinates.

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
The `sites_config` yaml file is generated priorly with `NetworkController/device-config/ansible/inventory/fabric_inventory.py --yaml`.

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



