import urllib3
import json


class RalphURI:
    """
    Load JSON file from a Ralph URI. Deal with authentication.
    """

    def __init__(self, *, token: str, base_uri: str):
        self.token = token
        self.base_uri = base_uri
        self.pool = urllib3.PoolManager()

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
