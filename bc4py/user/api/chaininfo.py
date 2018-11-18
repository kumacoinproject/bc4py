from bc4py.user.api import web_base
from bc4py.database.builder import builder, tx_builder
from bc4py.database.mintcoin import get_mintcoin_object
from aiohttp import web
from binascii import hexlify, unhexlify
import pickle
from base64 import b64encode


async def get_block_by_height(request):
    f_pickled = request.query.get('pickle', False)
    height = int(request.query.get('height', 0))
    blockhash = builder.get_block_hash(height)
    if blockhash is None:
        return web.Response(text="Not found height.", status=400)
    block = builder.get_block(blockhash)
    if f_pickled:
        block = pickle.dumps(block)
        return web.Response(text=b64encode(block).decode())
    data = block.getinfo()
    data['size'] = block.getsize()
    data['hex'] = hexlify(block.b).decode()
    return web_base.json_res(data)


async def get_block_by_hash(request):
    try:
        f_pickled = request.query.get('pickle', False)
        blockhash = request.query.get('hash')
        blockhash = unhexlify(blockhash.encode())
        block = builder.get_block(blockhash)
        if block is None:
            return web.Response(text="Not found block.", status=400)
        if f_pickled:
            block = pickle.dumps(block)
            return web.Response(text=b64encode(block).decode())
        data = block.getinfo()
        data['size'] = block.getsize()
        data['hex'] = hexlify(block.b).decode()
        return web_base.json_res(data)
    except Exception as e:
        return web_base.error_res()


async def get_tx_by_hash(request):
    try:
        f_pickled = request.query.get('pickle', False)
        txhash = request.query.get('hash')
        txhash = unhexlify(txhash.encode())
        tx = tx_builder.get_tx(txhash)
        if tx is None:
            return web.Response(text="Not found tx.", status=400)
        if f_pickled:
            tx = pickle.dumps(tx)
            return web.Response(text=b64encode(tx).decode())
        data = tx.getinfo()
        data['size'] = tx.getsize()
        data['hex'] = hexlify(tx.b).decode()
        data['signature'] = [(pubkey, hexlify(sign).decode()) for pubkey, sign in tx.signature]
        return web_base.json_res(data)
    except Exception as e:
        return web_base.error_res()


async def get_mintcoin_info(request):
    try:
        mint_id = int(request.query.get('mint_id', 0))
        m = get_mintcoin_object(coin_id=mint_id)
        return web_base.json_res(m.info)
    except BaseException:
        return web_base.error_res()


__all__ = [
    "get_block_by_height",
    "get_block_by_hash",
    "get_tx_by_hash",
    "get_mintcoin_info"
]
