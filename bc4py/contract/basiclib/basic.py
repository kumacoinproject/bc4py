from bc4py.user import Accounting
from requests import get, post
from base64 import b64decode
from binascii import b2a_hex
import pickle


API_BASE = 'http://127.0.0.1:3000/public/'


def calc_return_balance(start_tx, c_address, redeem_address):
    """ Calc redeem balance """
    balance = Accounting()
    for address, coin_id, amount in start_tx.outputs:
        if address == c_address:
            balance[redeem_address][coin_id] += amount
    return balance


def get_tx_obj(txhash):
    tx = api_get('gettxbyhash', hash=b2a_hex(txhash), pickle='true')
    return pickle.loads(b64decode(tx.encode()))


def get_contract_storage(c_address, stop_hash):
    """ get storage object """
    if stop_hash:
        stop_hash = b2a_hex(stop_hash)
    p_storage = api_get('contractstorage', c_address=c_address, pickle='true', stophash=stop_hash)
    return pickle.loads(b64decode(p_storage.encode()))


def calc_storage_diff(c_storage, new_storage):
    stop_hash = b2a_hex(c_storage.start_hash)
    p_storage = api_get('contractstorage', c_address=c_storage.c_address, pickle='true', stophash=b2a_hex(c_storage.stop_hash))
    c_storage = pickle.loads(b64decode(p_storage.encode()))
    return new_storage.export_diff(c_storage)


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
    "calc_return_balance": 10,
    "get_tx_obj": 200,
    "get_contract_storage": 500,
    "calc_storage_diff": 500,
    "api_get": 200,
    "api_post": 200,
}

__all__ = list(__price__)
