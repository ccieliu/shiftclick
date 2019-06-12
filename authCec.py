import requests
import urllib3
urllib3.disable_warnings()


class author(object):

    def __init__(self):
        self.auth_URL = "https://scripts.cisco.com/api/v2/auth/login"

    def authenticate(self, cec, password):
        self.cec = cec
        self.password = password
        self.s = requests.Session()
        self.auth = requests.auth.HTTPBasicAuth(self.cec, self.password)
        self.ret = self.s.get(self.auth_URL, auth=self.auth, verify=False)
        if self.ret.status_code == 200 or self.ret.status_code == 201:
            return True
        elif self.ret.status_code == 401:
            return False
        else:
            return (self.ret.status_code, self.ret.text)
