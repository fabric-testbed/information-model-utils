import urllib3
import json
import ssl
import logging


class RalphURI:
    """
    Load JSON file from a Ralph URI. Deal with authentication.
    """

    def __init__(self, *, token: str, base_uri: str, disable_ssl: False):
        self.token = token
        if not base_uri.endswith('/'):
            base_uri += '/'
        self.base_uri = base_uri
        if disable_ssl:
            logging.warning('Disabling server SSL certificate validation')
            cert_reqs = ssl.CERT_NONE
            urllib3.disable_warnings()
        else:
            cert_reqs = ssl.CERT_REQUIRED

        self.pool = urllib3.PoolManager(cert_reqs=cert_reqs)

    def get_json_object(self, uri: str):
        # avoid http->https redirects, just replace directly in uri
        uri = uri.replace('http:', 'https:')
        if not uri.startswith(self.base_uri):
            raise RalphURIError(msg=f'Provided uri {uri} does not match base uri {self.base_uri}')
        headers = {'Authorization': f'Token {self.token}', 'Content-Type': 'application/json'}
        r = self.pool.request("GET", uri, headers=headers)
        if r.status != 200:
            raise RuntimeError(f'Unable to contact {uri=} due to error {r.status=}')

        return json.loads(r.data.decode("utf-8"))


class RalphURIError(Exception):
    def __init__(self, msg: str):
        super().__init__(f"Ralph URI Error: {msg}")
