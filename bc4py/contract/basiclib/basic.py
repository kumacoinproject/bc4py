from bc4py.chain import TX
from requests import get, post


API_BASE = 'http://127.0.0.1:3000/public/'


def get_account_balance(start_tx: TX):
    pass


def api_get(method, **kwargs):
    r = get(url=API_BASE+method, params=kwargs, timeout=3.5)
    if not r.ok:
        raise Exception('Cannot use the method({})'.format(method))
    return r.json()


def api_post(method, **kwargs):
    r = post(url=API_BASE+method, json=kwargs)
    if not r.ok:
        raise Exception('Cannot use the method({})'.format(method))
    return r.json()


__price__ = {
    "get_account_balance": 100,
    "api_get": 200,
    "api_post": 200,
}

__all__ = list(__price__)
