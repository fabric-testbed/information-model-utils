import requests as req


class RalphURI:
    """
    Load JSON file from a Ralph URI. Deal with authentication.
    """

    def __init__(self, *, token: str, base_uri: str):
        self.token = token
        self.base_uri = base_uri

    def get_json_object(self, uri: str):
        #if not uri.startswith(self.base_uri):
        #    raise RalphURIError(msg=f'Provided uri {uri} does not match base uri {self.base_uri}')
        headers = {'Authorization': f'Token {self.token}'}
        r = req.get(uri, headers=headers)
        if r.status_code != 200:
            r.raise_for_status()
        return r.json()


class RalphURIError(Exception):
    def __init__(self, msg: str):
        super().__init__(f"Ralph URI Error: {msg}")
