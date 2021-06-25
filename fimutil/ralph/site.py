import logging
from abc import ABC
from urllib.parse import urlencode
import pyjq

from fimutil.ralph.ralph_uri import RalphURI
from fimutil.ralph.worker_node import WorkerNode
from fimutil.ralph.storage import Storage
from fimutil.ralph.dp_switch import DPSwitch


class Site:
    """
    As site consists of some number of assets - for information model purposes
    typically some number of worker nodes, a storage node and a dataplane switch.
    """
    def __init__(self, *, site_name: str, ralph: RalphURI, domain: str='.fabric-testbed.net'):
        """
        Site name can be upper or lower case
        """
        self.workers = list()
        self.storage = None
        self.dp_switch = None
        self.name = site_name
        self.domain = domain
        self.ralph = ralph

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
            ralph_worker = WorkerNode(uri=worker, ralph=self.ralph)
            ralph_worker.parse()
            self.workers.append(ralph_worker)

        query = {'hostname': f'{self.name.lower()}-storage' + self.domain}
        results = self.ralph.get_json_object(self.ralph.base_uri + 'data-center-assets/?' +
                                             urlencode(query))
        storage_url = None
        try:
            storage_url = pyjq.one('[ .results[0].url ]', results)[0]
            logging.info(f'Identified storage {storage_url=}')
        except ValueError:
            logging.warning('Unable to find storage node in site, continuing')

        self.storage = Storage(uri=storage_url, ralph=self.ralph)
        self.storage.parse()

        query = {'hostname': f'{self.name.lower()}-data-sw' + self.domain}
        results = self.ralph.get_json_object(self.ralph.base_uri + 'data-center-assets/?' +
                                             urlencode(query))
        dp_switch_url = None
        try:
            dp_switch_url = pyjq.one('[ .results[0].url ]', results)[0]
            logging.info(f'Identified DP switch {dp_switch_url=}')
        except ValueError:
            logging.warning('Unable to find a dataplane switch in site, continuing')
        self.dp_switch = DPSwitch(uri=dp_switch_url, ralph=self.ralph)
        self.dp_switch.parse()

    def __str__(self):
        assets = list()
        if self.storage is not None:
            assets.append(str(self.storage))
        if self.dp_switch is not None:
            assets.append(str(self.dp_switch))
        for w in self.workers:
            assets.append(str(w))
        return '\n'.join(assets)
