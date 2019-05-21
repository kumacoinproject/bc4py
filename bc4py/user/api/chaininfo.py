from bc4py.user.api import web_base
from bc4py.database.builder import chain_builder, tx_builder
from bc4py.database.mintcoin import get_mintcoin_object
from aiohttp import web
from binascii import a2b_hex
import pickle
from base64 import b64encode


async def get_block_by_height(request):
    f_pickled = request.query.get('pickle', False)
    with_tx_info = request.query.get('txinfo', 'false')
    try:
        height = int(request.query['height'])
    except Exception as e:
        return web.Response(text="Height is not specified", status=400)
    blockhash = chain_builder.get_block_hash(height)
    if blockhash is None:
        return web.Response(text="Not found height", status=400)
    block = chain_builder.get_block(blockhash)
    if f_pickled:
        block = pickle.dumps(block)
        return web_base.json_res(b64encode(block).decode())
    data = block.getinfo(with_tx_info == 'true')
    data['hex'] = block.b.hex()
    return web_base.json_res(data)


async def get_block_by_hash(request):
    try:
        f_pickled = request.query.get('pickle', False)
        with_tx_info = request.query.get('txinfo', 'false')
        blockhash = request.query.get('hash')
        if blockhash is None:
            return web.Response(text="Not found height", status=400)
        blockhash = a2b_hex(blockhash)
        block = chain_builder.get_block(blockhash)
        if block is None:
            return web.Response(text="Not found block", status=400)
        if f_pickled:
            block = pickle.dumps(block)
            return web_base.json_res(b64encode(block).decode())
        data = block.getinfo(with_tx_info == 'true')
        data['size'] = block.size
        data['hex'] = block.b.hex()
        return web_base.json_res(data)
    except Exception as e:
        return web_base.error_res()


async def get_tx_by_hash(request):
    try:
        f_pickled = request.query.get('pickle', False)
        txhash = request.query.get('hash')
        txhash = a2b_hex(txhash)
        tx = tx_builder.get_tx(txhash)
        if tx is None:
            return web.Response(text="Not found tx", status=400)
        if f_pickled:
            tx = pickle.dumps(tx)
            return web_base.json_res(b64encode(tx).decode())
        data = tx.getinfo()
        data['hex'] = tx.b.hex()
        return web_base.json_res(data)
    except Exception as e:
        return web_base.error_res()


async def get_mintcoin_info(request):
    try:
        mint_id = int(request.query.get('mint_id', 0))
        m = get_mintcoin_object(coin_id=mint_id)
        return web_base.json_res(m.info)
    except Exception:
        return web_base.error_res()


async def get_mintcoin_history(request):
    try:
        mint_id = int(request.query.get('mint_id', 0))
        data = list()
        for index, txhash, params, setting in chain_builder.db.read_coins_iter(coin_id=mint_id):
            data.append({'index': index, 'txhash': txhash.hex(), 'params': params, 'setting': setting})
        return web_base.json_res(data)
    except Exception:
        return web_base.error_res()


__all__ = [
    "get_block_by_height",
    "get_block_by_hash",
    "get_tx_by_hash",
    "get_mintcoin_info",
    "get_mintcoin_history",
]
