from bc4py import __chain_version__
from bc4py.config import C, V, P
from bc4py.user.api import web_base
from bc4py.database.builder import builder, tx_builder
from bc4py.user.generate import create_mining_block, confirmed_generating_block
from bc4py.chain.block import Block
from bc4py.chain.tx import TX
from binascii import hexlify, unhexlify
from aiohttp import web
from base64 import b64decode
import json
from time import time
from expiringdict import ExpiringDict
import logging
import asyncio


# about "coinbasetxn"
# https://bitcoin.stackexchange.com/questions/13438/difference-between-coinbaseaux-flags-vs-coinbasetxn-data
# https://github.com/bitcoin/bips/blob/master/bip-0022.mediawiki


F_HEAVY_DEBUG = False
getwork_cashe = ExpiringDict(max_len=10000, max_age_seconds=1800)


async def json_rpc(request):
    if 'Authorization' not in request.headers:
        return '"Not found Authorization."', 400
    authorization = request.headers['Authorization']
    auth_type, auth_data = authorization.split()
    if auth_type != 'Basic':
        return '"Not Basic Authorization."', 400
    if P.F_NOW_BOOTING:
        return '"Busy status."', 400
    user, password = b64decode(auth_data.encode()).decode().split(':')
    # user_agent = request.headers['User-Agent']
    post = await web_base.content_type_json_check(request)
    try:
        if F_HEAVY_DEBUG: logging.debug("PostRequest: {}".format(post))
        method, params = post['method'], post.get('params', list())
        if F_HEAVY_DEBUG: logging.debug("RpcRequest: {}".format(params))
        if not isinstance(params, list):
            return '"Params is list. not {}"'.format(type(params)), 400
        kwords = dict(user=user, password=password)
        result = await globals().get(method)(*params, **kwords)
        if F_HEAVY_DEBUG: logging.debug("RpcResponse: {}".format(result))
        return web_base.json_res(
            data={'error': None, 'result': result, 'id': post['id']}, indent=None)
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logging.debug("JsonRpcError: {}".format(e))
        return web_base.error_res(
            json.dumps({'error': str(tb), 'result': None, 'id': post['id']}))


async def get_mining_block(**kwargs):
    while True:
        try:
            return create_mining_block(consensus=int(kwargs['password']))
        except Exception as e:
            if int(time()) % 30 == 0:
                logging.debug("Mining block creation failed by \"{}\"".format(e))
            await asyncio.sleep(2)


async def getwork(*args, **kwargs):
    # https://en.bitcoin.it/wiki/Getwork
    if len(args) == 0:
        now = int(time() - V.BLOCK_GENESIS_TIME)
        for block in getwork_cashe.values():
            if now - block.time < 10:
                mining_block = block
                break
        else:
            mining_block = await get_mining_block(**kwargs)
            getwork_cashe[mining_block.merkleroot] = mining_block
            mining_block.bits2target()
        # Pre-processed SHA-2 input chunks
        data = mining_block.b  # 80 bytes
        data += unhexlify(b'800000000000000000000000000000000000000000000000'
                          b'000000000000000000000000000000000000000000000280')  # 48+80=128bytes
        new_data = b''
        for i in range(0, 128, 4):
            new_data += data[i:i+4][::-1]
        return {
            "data": hexlify(new_data).decode(),
            "target": hexlify(mining_block.target_hash).decode()}
    else:
        data = unhexlify(args[0].encode())
        new_data = b''
        for i in range(0, 128, 4):
            new_data += data[i:i+4][::-1]
        block = Block(binary=new_data[:80])
        if block.merkleroot in getwork_cashe:
            if F_HEAVY_DEBUG:
                logging.debug("GetWorkCashe {}Sec ago.".format(block.time - getwork_cashe[block.merkleroot].time))
            block.txs.extend(getwork_cashe[block.merkleroot].txs)
            result = await submitblock(block, **kwargs)
            if result is None:
                return True
            logging.debug("GetWorkReject by \"{}\"".format(result))
            return result
        else:
            logging.debug("GetWorkReject by \"Not found merkleroot.\"")
            return 'Not found merkleroot.'


async def getblocktemplate(*args, **kwargs):
    # capabilities = {"capabilities": ["coinbasetxn", "workid", "coinbase/append"]}
    mining_block = await get_mining_block(**kwargs)
    mining_block.bits2target()
    template = {
        "version": mining_block.version,
        "previousblockhash": bin2hex(mining_block.previous_hash),
        "coinbasetxn": {
            # sgminer say, FAILED to decipher work from 127.0.0.1
            "data": hexlify(mining_block.txs[0].b).decode()
        },  # 採掘報酬TX
        "target": bin2hex(mining_block.target_hash),
        "mutable": [
            "time",
            "transactions",
            "prevblock"
        ],
        "noncerange": "00000000ffffffff",
        "sigoplimit": 20000,
        "sizelimit": C.SIZE_BLOCK_LIMIT,
        "curtime": mining_block.time,  # block time
        "bits": hexlify(mining_block.bits.to_bytes(4, 'big')).decode(),
        "height": mining_block.height
    }
    transactions = list()
    for tx in mining_block.txs[1:]:
        transactions.append({
            "data": hexlify(tx.b).decode(),
            "hash": bin2hex(tx.hash),
            "depends": list(),
            "fee": 0,
            "sigops": len(mining_block.txs) - 1})
    template['transactions'] = transactions
    return template


async def submitblock(block_hex_or_obj, **kwargs):
    if isinstance(block_hex_or_obj, str):
        block_bin = unhexlify(block_hex_or_obj.encode())
        # Block
        mined_block = Block(binary=block_bin[:80])
        if mined_block.previous_hash != builder.best_block.hash:
            return 'PreviousHash don\'t match.'
        mined_block.height = builder.best_block.height + 1
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
        if F_HEAVY_DEBUG: logging.debug("RpcSubmit block: pos={}, tx_len={}".format(pos, tx_len))
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
        mined_block.height = builder.best_block.height + 1
        mined_block.flag = int(kwargs['password'])
    else:
        return 'Unknown input? -> {}'.format(block_hex_or_obj)
    mined_block.update_pow()
    if not mined_block.pow_check():
        return 'not satisfied work.'
    confirmed_generating_block(mined_block)
    return None  # accepted


async def getmininginfo(*args, **kwargs):
    return None  # dummy


def bin2hex(b):
    return hexlify(b[::-1]).decode()
