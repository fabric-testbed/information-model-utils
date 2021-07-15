[![Requirements Status](https://requires.io/github/fabric-testbed/information-model-utils/requirements.svg?branch=main)](https://requires.io/github/fabric-testbed/information-model-utils/requirements/?branch=main)

![PyPI](https://img.shields.io/pypi/v/fim-utils?style=plastic)

# Information Model Utilities

There are a number of libraries and utilities in this repo that help convert 
information from various sources into FABRIC Information Models

## Utilities Library

This library uses different sources to extract necessary information to build
site and network advertisement models for FABRIC control framework:
- fimutil.ralph - uses Ralph inventory system REST API

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

## End-user utilities

Pip install the package. The utilities should be on PATH. Get a token from Ralph GUI for the API. 
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
what it finds.

Invocation:
```
$ scan_site.py -b https://hostname/api/ -s <site acronym> -t <token> -p
```
Prints information collected from Ralph

```
$ scan_site.py -b https://hostname/api/ -s <site acronym> -t <token> -m <model name>.graphml
```
Saves site model into a file in GraphML format. Both `-p` and `-m` could be used together. If neither is specified
the site is scanned however no extra output is produced. 

### scan_net.py

Similar to above, interrogates NSO, PCE (future work) to create a model of the inter-site network.

Invocation:
```
$ scan_net.py -n <nso url> -u <nso username> -p <nso password> -m <model name>.graphml
```

Saves the model into a file indicated with `-m` in GraphML format.

## Installation

Developed under Python 3.9. Using virtualenv, something like this should work:

```
$ mkvirtualenv -r requirements.txt fim-utils
$ cd utilities/
$ python scan_worker.py <options>
```
Note that to install PyJQ dependency  you need to have `automake` installed on your system. So
`yum install automake` or `brew install automake` or similar. 

### utilities/scan_worker.py



