import logging
from abc import ABC
from urllib.parse import urlencode
import pyjq
from typing import Dict
import json

from fimutil.ralph.p4_switch import P4Switch
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
        self.p4_switch = None
        self.ptp = False
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
        - PTP server: <site>-time.fabric-testbed.net
        """
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

        try:
            logging.info(f'Searching for P4 switch URL')
            query = {'hostname': f'{self.name.lower()}-p4-sw' + self.domain}
            results = self.ralph.get_json_object(self.ralph.base_uri + 'data-center-assets/?' +
                                                 urlencode(query))
            p4_switch_url = pyjq.one('[ .results[0].url ]', results)[0]
            if not p4_switch_url:
                raise ValueError
            logging.info(f'Identified P4 switch {p4_switch_url=}')
            self.p4_switch = P4Switch(uri=p4_switch_url, ralph=self.ralph)
            self.p4_switch.parse()
        except ValueError:
            logging.warning('Unable to find a p4 switch in site, continuing')

        query = {'hostname': f'{self.name.lower()}-time' + self.domain}
        results = self.ralph.get_json_object(self.ralph.base_uri + 'data-center-assets/?' +
                                             urlencode(query))

        if self.config and self.config.get(self.name) and self.config.get(self.name).get('ptp'):
            ptp_override = self.config.get(self.name).get('ptp')
            if not isinstance(ptp_override, bool):
                logging.error(f'Config file does not specify ptp override as a boolean for site {self.name}')
                raise RuntimeError('Unable to continue')
            logging.info(f'Overriding {self.name} PTP setting with {ptp_override} from static configuration file')
            self.ptp = ptp_override
        else:
            ptp_url = None
            try:
                ptp_url = pyjq.one('[ .results[0].url ]', results)[0]
                logging.info(f'Identified PTP server {ptp_url=}')
                if not ptp_url:
                    raise ValueError
                self.ptp = True
            except ValueError:
                logging.warning('Unable to find PTP server in site, continuing')

        #query = {'hostname__regex': f'{self.name.lower()}-w[0123456789]' + self.domain}
        query = {'hostname__startswith': f'{self.name.lower()}-w','limit': 100}
        results = self.ralph.get_json_object(self.ralph.base_uri + 'data-center-assets/?' +
                                             urlencode(query))

        worker_urls = list()
        worker_urls.extend(pyjq.one('[ .results[].url ]', results))

        # not sure why the regex doesn't work as expected, ({self.name.lower()}-w[0123456789]+)
        # so instead another simple regex to look for workers with two digit indexes

        #query = {'hostname__regex': f'{self.name.lower()}-w[0123456789][0123456789]' + self.domain}
        #results = self.ralph.get_json_object(self.ralph.base_uri + 'data-center-assets/?' +
        #                                     urlencode(query))

        #worker_urls.extend(pyjq.one('[ .results[].url ]', results))

        logging.info(f'Identified {len(worker_urls)} workers')

        for worker in worker_urls:
            logging.info(f'Parsing {worker=}')
            ralph_worker = WorkerNode(uri=worker, ralph=self.ralph, site=self.name,
                                      dp_switch=self.dp_switch, config=self.config, ptp=self.ptp)
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

    def __str__(self):
        assets = list()
        if self.storage:
            assets.append(str(self.storage))
        if self.dp_switch:
            assets.append(str(self.dp_switch))
        if self.p4_switch:
            assets.append(str(self.p4_switch))
        for w in self.workers:
            assets.append(str(w))
        return '\n'.join(assets)

    def to_json(self):
        ret = dict()
        if self.storage:
            ret["Storage"] = self.storage.fields.copy()
        if self.dp_switch:
            ret["DataPlane"] = self.dp_switch.fields.copy()
        if self.p4_switch:
            ret["P4"] = self.p4_switch.fields.copy()
            p4_dp_ports = self.p4_switch.get_dp_ports()
            p4_dp_ports = list(set(p4_dp_ports))
            p4_dp_ports.sort()
            ret["P4"]["Connected_ports"] = p4_dp_ports

        # collect port information from all workers
        dp_ports = list()
        for w in self.workers:
            dp_ports.extend(w.get_dp_ports())
        # see if any extra ports are mentioned in the config file
        if self.config and self.config.get(self.name) and self.config.get(self.name).get('connected_ports'):
            dp_ports.extend(self.config.get(self.name).get('connected_ports'))
        # uniquify and sort
        dp_ports = list(set(dp_ports))
        dp_ports.sort()
        ret["DataPlane"]["Connected_ports"] = dp_ports
        n = list()
        for w in self.workers:
            n.append(w.to_json())
        ret["Nodes"] = n
        return ret
