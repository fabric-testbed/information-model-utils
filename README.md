# Information Model Utilities

There are a number of libraries and utilities in this repo that help convert 
information from various sources into FABRIC Information Models

## Utilities Library

This libry use different sources to extract necessary information to build
site and network models:
- fimutil.ralph - uses Ralph inventory system REST API

### Ralph REST
Since Ralph presents information in the form of nested dictionaries, the library
uses a trivial XPath-like syntax to map out properties it needs. For example,
a model name of a server can be found as `results/0.model.category.name`, meaning
'results' dictionary, then take the first element of the list (index 0), then
follow dictionary hierarchy ['model']['category']['name']. It throws
`RalphJSONError` if the indicated field cannot be found. 

It defines multiple classes of assets (all children of a base Asset class),
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

### utilities/scan_worker.py

Scans an individual worker node based on its FQDN and returns information about
it and its components. 

Invocation:
```
python scan_worker.py -w <worker FQDN> -t <Ralph API Token> -b https://hostname/api/data-center-assets/
```

The utility is smart enough to try and discard components that don't need to
be reflected in the information model (internal worker disks, iDrac or 
disconnected ports etc)

You can find your Ralph API token in your profile page in Ralph.

