from bc4py import __chain_version__
from bc4py.config import C, V, P
from bc4py.user.api import web_base
from bc4py.database.builder import builder, tx_builder
from bc4py.user.generate import create_mining_block, confirmed_generating_block
from bc4py.chain.block import Block
from bc4py.chain.tx import TX
from binascii import a2b_hex
from aiohttp import web
from base64 import b64decode
import json
from time import time
from expiringdict import ExpiringDict
import asyncio
import traceback
from logging import getLogger

log = getLogger('bc4py')

# about "coinbasetxn"
# https://bitcoin.stackexchange.com/questions/13438/difference-between-coinbaseaux-flags-vs-coinbasetxn-data
# https://github.com/bitcoin/bips/blob/master/bip-0022.mediawiki


getwork_cashe = ExpiringDict(max_len=100, max_age_seconds=300)
extra_target = None  # 0x00000000ffff0000000000000000000000000000000000000000000000000000


async def json_rpc(request):
    # JSON-RPC require BasicAuth
    if 'Authorization' not in request.headers:
        return res_failed("Not found Authorization", None)
    authorization = request.headers['Authorization']
    auth_type, auth_data = authorization.split()
    if auth_type != 'Basic':
        return res_failed("Not Basic Authorization", None)

    # user     => no meaning
    # password => mining consensus number by confing.py
    user, password = b64decode(auth_data.encode()).decode().split(':')
    post = await web_base.content_type_json_check(request)
    if P.F_NOW_BOOTING:
        return res_failed("Busy status", post.get('id'))

    try:
        # post format => {"id": id, "method": method, "params": [params]}
        method = post['method']
        params = post.get('params', list())  # sgminer don't have
        log.debug("RpcRequest: method={} params={}".format(method, params))
        if not isinstance(params, list):
            return res_failed("Params is list. not {}".format(type(params)), post.get('id'))

        # find method function and throw task
        fnc = globals().get(method)
        if fnc is None:
            return res_failed("not found method {}".format(method), post.get('id'))
        result = await fnc(*params, user=user, password=password)
        log.debug("RpcResponse: {}".format(result))
        return res_success(result, post.get('id'))
    except Exception as e:
        tb = traceback.format_exc()
        log.debug("JsonRpcError: {}".format(e))
        return res_failed(str(tb), post.get('id'))


def res_failed(error, uuid):
    return web.Response(
        text=json.dumps({
            'id': uuid,
            'result': None,
            'error': error
        }), content_type='application/json')


def res_success(result, uuid):
    return web.Response(
        text=json.dumps({
            'id': uuid,
            'result': result,
            'error': None
        }), content_type='application/json')


async def get_mining_block(**kwargs):
    """create raw mining block"""
    s = time()
    while True:
        try:
            return create_mining_block(consensus=int(kwargs['password']))
        except Exception as e:
            if time() - s > 5:
                raise TimeoutError("Mining block creation failed by '{}'".format(e))
            await asyncio.sleep(0.1)


async def getwork(*args, **kwargs):
    """
    duplicated method "getwork"
    https://en.bitcoin.it/wiki/Getwork
    """
    if len(args) == 0:
        now = int(time() - V.BLOCK_GENESIS_TIME)
        for block in getwork_cashe.values():
            if block.previous_hash != builder.best_block.hash:
                continue
            if now - block.time < 10:
                mining_block = block
                break
        else:
            mining_block = await get_mining_block(**kwargs)
            getwork_cashe[mining_block.merkleroot] = mining_block
            mining_block.bits2target()
        # Pre-processed SHA-2 input chunks
        data = mining_block.b  # 80 bytes
        data += a2b_hex('800000000000000000000000000000000000000000000000'
                        '000000000000000000000000000000000000000000000280')  # 48+80=128bytes
        new_data = b''
        for i in range(0, 128, 4):
            new_data += data[i:i + 4][::-1]
        if extra_target:
            return {"data": new_data.hex(), "target": extra_target.to_bytes(32, 'big').hex()}
        else:
            return {"data": new_data.hex(), "target": mining_block.target_hash.hex()}
    else:
        data = a2b_hex(args[0])
        new_data = b''
        for i in range(0, 128, 4):
            new_data += data[i:i + 4][::-1]
        block = Block.from_binary(binary=new_data[:80])
        if block.previous_hash != builder.best_block.hash:
            return 'PreviousHash don\'t match'
        if block.merkleroot in getwork_cashe:
            block.txs.extend(getwork_cashe[block.merkleroot].txs)
            result = await submitblock(block, **kwargs)
            if result is None:
                return True
            elif extra_target and block.pow_check(extra_target=extra_target):
                return True
            else:
                log.debug("GetWorkReject by \"{}\"".format(result))
                return result
        else:
            log.debug("GetWorkReject by \"Not found merkleroot.\"")
            return 'Not found merkleroot'


async def getblocktemplate(*args, **kwargs):
    """
    default method "getblocktemplate"
    https://en.bitcoin.it/wiki/Getblocktemplate
    For full specification, see BIPs 22, 23, 9, and 145:
        https://github.com/bitcoin/bips/blob/master/bip-0022.mediawiki
        https://github.com/bitcoin/bips/blob/master/bip-0023.mediawiki
        https://github.com/bitcoin/bips/blob/master/bip-0009.mediawiki#getblocktemplate_changes
        https://github.com/bitcoin/bips/blob/master/bip-0145.mediawiki
    """
    # capabilities = {"capabilities": ["coinbasetxn", "workid", "coinbase/append"]}
    mining_block = await get_mining_block(**kwargs)
    mining_block.bits2target()
    template = {
        "version": mining_block.version,
        "previousblockhash": bin2hex(mining_block.previous_hash),
        "coinbasetxn": {
            # sgminer say, FAILED to decipher work from 127.0.0.1
            "data": mining_block.txs[0].b.hex()
        },  # 採掘報酬TX
        "target": bin2hex(mining_block.target_hash),
        "mutable": ["time", "transactions", "prevblock"],
        "noncerange": "00000000ffffffff",
        "sigoplimit": 20000,
        "sizelimit": C.SIZE_BLOCK_LIMIT,
        "curtime": mining_block.time,  # block time
        "bits": mining_block.bits.to_bytes(4, 'big').hex(),
        "height": mining_block.height
    }
    transactions = list()
    for tx in mining_block.txs[1:]:
        transactions.append({
            "data": tx.b.hex(),
            "hash": bin2hex(tx.hash),
            "depends": list(),
            "fee": 0,
            "sigops": len(mining_block.txs) - 1
        })
    template['transactions'] = transactions
    return template


async def submitblock(*args, **kwargs):
    """
    method "submitblock"
    Attempts to submit new block to network
    """
    if len(args) == 0:
        return 'no argument found'
    block_hex_or_obj = args[0]
    if isinstance(block_hex_or_obj, str):
        block_bin = a2b_hex(block_hex_or_obj)
        # Block
        mined_block = Block.from_binary(binary=block_bin[:80])
        if mined_block.previous_hash != builder.best_block.hash:
            return 'PreviousHash don\'t match'
        previous_block = builder.get_block(mined_block.previous_hash)
        mined_block.height = previous_block.height + 1
        mined_block.flag = int(kwargs['password'])
        # tx length
        storage_flag = int.from_bytes(block_bin[80:81], 'little')
        if storage_flag < 0xfd:
            tx_len = storage_flag
            pos = 81
        elif storage_flag == 0xfd:
            tx_len = int.from_bytes(block_bin[81:83], 'little')
            pos = 83
        elif storage_flag == 0xfe:
            tx_len = int.from_bytes(block_bin[81:85], 'little')
            pos = 85
        else:  # == 0xff
            tx_len = int.from_bytes(block_bin[81:89], 'little')
            pos = 89
        log.debug("RpcSubmit block: pos={}, tx_len={}".format(pos, tx_len))
        # correct txs
        while len(block_bin) > pos:
            tx = TX()
            tx.b = block_bin
            tx.deserialize(first_pos=pos, f_raise=False)
            if tx.version != __chain_version__:
                return 'tx_ver do not match [{}!={}]'.format(tx.version, __chain_version__)
            pos += len(tx.b)
            mined_block.txs.append(tx_builder.get_tx(txhash=tx.hash, default=tx))
            # check
            if tx_len != len(mined_block.txs):
                return 'Do not match txlen [{}!={}]'.format(tx_len, len(mined_block.txs))
            if pos != len(block_bin):
                return 'Do not match pos [{}!={}]'.format(pos, len(block_bin))
    elif isinstance(block_hex_or_obj, Block):
        mined_block = block_hex_or_obj
        previous_block = builder.get_block(mined_block.previous_hash)
        mined_block.height = previous_block.height + 1
        mined_block.flag = int(kwargs['password'])
    else:
        return 'Unknown input? -> {}'.format(block_hex_or_obj)
    mined_block.update_pow()
    if mined_block.pow_check():
        confirmed_generating_block(mined_block)
        return None  # accepted
    else:
        return 'not satisfied work'


async def getmininginfo(*args, **kwargs):
    return None  # dummy


def bin2hex(b):
    return b[::-1].hex()


__all__ = [
    "json_rpc",
]
