from bc4py.user import CoinBalance
from requests import get, post
from base64 import b64decode
from binascii import b2a_hex
import pickle


API_BASE = 'http://127.0.0.1:3000/public/'


def get_address_inputs(start_tx, c_address):
    """ extract contract input balance """
    balance = CoinBalance()
    for address, coin_id, amount in start_tx.outputs:
        if address == c_address:
            balance[coin_id] += amount
    return balance


def calc_return_pairs(start_tx, inputs, used, send=None, f_safe=True, redeem_address=None):
    """ Calc redeem outputs pairs """
    if redeem_address is None:
        txhash, txindex = start_tx.inputs[0]
        tx = get_tx_obj(txhash)
        redeem_address, coin_id, amount = tx.outputs[txindex]
    pairs = list()
    outputs = inputs - used
    if send:
        outputs += send
    for coin_id, amount in outputs:
        if amount == 0:
            continue
        elif f_safe and amount < 0:
            raise Exception('Try to send more than received {}:{}'.format(coin_id, amount))
        else:
            pairs.append((redeem_address, coin_id, amount))
    return pairs


def get_tx_obj(txhash):
    tx = api_get('gettxbyhash', hash=b2a_hex(txhash), pickle='true')
    return pickle.loads(b64decode(tx.encode()))


def get_contract_storage(c_address):
    p_storage = api_get('contractstorage', c_address=c_address, pickle='true')
    return pickle.loads(b64decode(p_storage.encode()))


def calc_storage_diff(c_address, new_storage):
    p_storage = api_get('contractstorage', c_address=c_address, pickle='true')
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
    "get_address_inputs": 100,
    "calc_return_pairs": 200,
    "get_tx_obj": 200,
    "get_contract_storage": 500,
    "calc_storage_diff": 500,
    "api_get": 200,
    "api_post": 200,
}

__all__ = list(__price__)
