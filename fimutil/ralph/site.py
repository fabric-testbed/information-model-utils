import logging
from abc import ABC
from urllib.parse import urlencode
import pyjq
from typing import Dict

from fimutil.ralph.ralph_uri import RalphURI
from fimutil.ralph.worker_node import WorkerNode
from fimutil.ralph.storage import Storage
from fimutil.ralph.dp_switch import DPSwitch


class Site:
    """
    As site consists of some number of assets - for information model purposes
    typically some number of worker nodes, a storage node and a dataplane switch.
    """
    def __init__(self, *, site_name: str, ralph: RalphURI, config: Dict = None, domain: str = '.fabric-testbed.net'):
        """
        Site name can be upper or lower case
        """
        self.workers = list()
        self.storage = None
        self.dp_switch = None
        self.name = site_name
        self.domain = domain
        self.ralph = ralph
        self.config = config

    def catalog(self):
        """
        Catalog what the site has by querying for regular expressions. Names of nodes
        are expected to conform to the following convention:
        - workers: <site>-w[\\d]+.fabric-testbed.net
        - storage: <site>-storage.fabric-testbed.net
        - dp switch: <site>-data-sw.fabric-testbed.net
        """
        query = {'hostname__regex': f'{self.name.lower()}-w[1234567890]+' + self.domain}

        results = self.ralph.get_json_object(self.ralph.base_uri + 'data-center-assets/?' +
                                             urlencode(query))
        worker_urls = pyjq.one('[ .results[].url ]', results)
        logging.info(f'Identified {len(worker_urls)} workers')

        for worker in worker_urls:
            logging.info(f'Parsing {worker=}')
            ralph_worker = WorkerNode(uri=worker, ralph=self.ralph, site=self.name, config=self.config)
            ralph_worker.parse()
            self.workers.append(ralph_worker)

        query = {'hostname': f'{self.name.lower()}-storage' + self.domain}
        results = self.ralph.get_json_object(self.ralph.base_uri + 'data-center-assets/?' +
                                             urlencode(query))
        storage_url = None
        try:
            storage_url = pyjq.one('[ .results[0].url ]', results)[0]
            logging.info(f'Identified storage {storage_url=}')
            if not storage_url:
                raise ValueError
            self.storage = Storage(uri=storage_url, ralph=self.ralph)
            self.storage.parse()
            if self.config and self.config.get(self.name) and self.config.get(self.name).get("storage"):
                storage_override = self.config.get(self.name).get("storage")
                self.storage.model.fields['Disk'] = storage_override['Disk']
        except ValueError:
            logging.warning('Unable to find storage node in site, continuing')

        query = {'hostname': f'{self.name.lower()}-data-sw' + self.domain}
        results = self.ralph.get_json_object(self.ralph.base_uri + 'data-center-assets/?' +
                                             urlencode(query))

        # config file can override dp switch URL
        dp_switch_url = None
        if self.config and self.config.get(self.name) and self.config.get(self.name).get('dpswitch'):
            dpswitch_override = self.config.get(self.name) and self.config.get(self.name).get('dpswitch')
            dp_switch_url = dpswitch_override.get('URL')
            if dp_switch_url:
                logging.info(f'Overriding {self.name} DP switch URL from static configuration file')
            else:
                logging.error(f'Config file does not specify a URL for alternate dp switch of site {self.name}')
                raise RuntimeError('Unable to continue')
        try:
            if not dp_switch_url:
                logging.info(f'Searching for DP switch URL')
                dp_switch_url = pyjq.one('[ .results[0].url ]', results)[0]
            logging.info(f'Identified DP switch {dp_switch_url=}')
            if not dp_switch_url:
                raise ValueError
            self.dp_switch = DPSwitch(uri=dp_switch_url, ralph=self.ralph)
            self.dp_switch.parse()
        except ValueError:
            logging.warning('Unable to find a dataplane switch in site, continuing')

    def __str__(self):
        assets = list()
        if self.storage:
            assets.append(str(self.storage))
        if self.dp_switch:
            assets.append(str(self.dp_switch))
        for w in self.workers:
            assets.append(str(w))
        return '\n'.join(assets)

    def to_json(self):
        ret = dict()
        if self.storage:
            ret["Storage"] = self.storage.fields
        if self.dp_switch:
            ret["DataPlane"] = self.dp_switch.fields
        n = list()
        for w in self.workers:
            n.append(w.to_json())
        ret["Nodes"] = n
        return ret