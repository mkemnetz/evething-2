import requests
import json

from base64 import b64encode

from thing.models.esitoken import ESIToken
from evething import local_settings


# ESI Api wrapper
class ESI():
    url = local_settings.ESI_URL
    datasource = local_settings.ESI_DATASOURCE
    client_id = local_settings.ESI_CLIENT_ID
    secret_key = local_settings.ESI_SECRET_KEY
    token = None


    # Wrapper for GET
    def get(self, url, data=None, debug=True):
        return self.request(url, data=data, method=requests.get, debug=debug)

    # Wrapper for POST
    def post(self, url, data=None, debug=False):
        return self.request(url, data=data, method=requests.post, debug=debug)


    def request(self, url, data=None, method=requests.get, retries=0, debug=False):
        # Do replacements
        full_url = self._replacements(url)

        # Try request
        full_url = "%s%s?datasource=%s" % (self.url, full_url, self.datasource)
        if debug:
            print full_url
        r = method(full_url, data=data, headers=self._bearer_header())

        # If we got a 403 error its an invalid token, try to refresh the token and try again
        if r.status_code == 403:
            if self._refresh_access_token():
                r = method(full_url, data=data, headers=self._bearer_header())
            else:
                return None

        # ESI is buggy, so lets give it up to 10 retries for 500 error
        if r.status_code in [500, 502]:
            if retries < 10:
                return self.request(url, data=data, method=method, retries=retries)
            else:
                return None

        # Load json and return
        if r.status_code == 200:
            return json.loads(r.text)
        else:
            return None


    # Takes an ESIToken object as the constructor
    def __init__(self, token=None):
        self.token = token


    # Replaces url $variables with their values
    def _replacements(self, url):
        if self.token != None:
            url = url.replace("$id", str(self.token.characterID))

        return url


    def _bearer_header(self):
        if self.token == None:
            headers = {}
        else:
            headers = {
                "Authorization": "Bearer %s" % self.token.access_token
            }
        return headers


    # Refreshes the access token using the refresh token
    def _refresh_access_token(self):
        # Get the new access token
        auth = b64encode("%s:%s" % (self.client_id, self.secret_key))
        headers = {
            "Authorization": "Basic %s" % auth
        }
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.token.refresh_token
        }
        r = requests.post("https://login.eveonline.com/oauth/token", data=data, headers=headers)

        # If we get a 400 code, then the key has been deleted
        if r.status_code == 400:
            self.token.status = False
            self.token.save()
            return False

        # Update the ESI token
        r = json.loads(r.text)
        self.token.access_token = r['access_token']
        self.token.save()

        return True