from bc4py.user import Accounting
from bc4py.contract.basiclib import config
from requests import get, post
from base64 import b64decode
from binascii import b2a_hex
import pickle


def calc_return_balance(start_tx, c_address, redeem_address):
    """ Calc redeem balance """
    balance = Accounting()
    for address, coin_id, amount in start_tx.outputs:
        if address == c_address:
            balance[redeem_address][coin_id] += amount
    return balance


def get_tx_obj(txhash):
    p_tx = api_get('gettxbyhash', hash=b2a_hex(txhash), pickle='true')
    return pickle.loads(b64decode(p_tx.encode()))


def get_block_obj(height=None, blockhash=None):
    if height is not None:
        p_block = api_get('getblockbyheight', height=height, pickle='true')
    elif blockhash is not None:
        p_block = api_get('getblockbyhash', hash=b2a_hex(blockhash), pickle='true')
    else:
        raise Exception('Both params are None.')
    return pickle.loads(b64decode(p_block.encode()))


def get_contract_storage(c_address, stop_hash=None):
    """ get storage object """
    if stop_hash:
        stop_hash = b2a_hex(stop_hash)
    p_storage = api_get('contractstorage', c_address=c_address, pickle='true', stophash=stop_hash)
    return pickle.loads(b64decode(p_storage.encode()))


def api_get(method, **kwargs):
    url = config['api-endpoint'] + method
    r = get(url=url, params=kwargs, timeout=5)
    if not r.ok:
        raise Exception('Cannot use the method({})'.format(method))
    return r.json()


def api_post(method, **kwargs):
    url = config['api-endpoint'] + method
    r = post(url=url, json=kwargs, timeout=5)
    if not r.ok:
        raise Exception('Cannot use the method({})'.format(method))
    return r.json()


__price__ = {
    "calc_return_balance": 10,
    "get_tx_obj": 200,
    "get_block_obj": 200,
    "get_contract_storage": 500,
    "api_get": 200,
    "api_post": 200,
}

__all__ = list(__price__)
