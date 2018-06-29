from bc4py.user.api import web_base
from bc4py.database.builder import builder, tx_builder
from bc4py.database.tools import get_mintcoin
from aiohttp import web
from binascii import hexlify, unhexlify


async def get_block_by_height(request):
    height = int(request.query.get('height', 0))
    blockhash = builder.get_block_hash(height)
    if blockhash is None:
        return web.Response(text="Not found height.", status=400)
    block = builder.get_block(blockhash)
    data = block.getinfo()
    data['size'] = block.getsize()
    data['hex'] = hexlify(block.b).decode()
    return web_base.json_res(data)


async def get_block_by_hash(request):
    try:
        blockhash = request.query.get('blockhash')
        blockhash = unhexlify(blockhash.encode())
        block = builder.get_block(blockhash)
        if block is None:
            return web.Response(text="Not found block.", status=400)
        data = block.getinfo()
        data['size'] = block.getsize()
        data['hex'] = hexlify(block.b).decode()
        return web_base.json_res(data)
    except Exception as e:
        return web_base.error_res()


async def get_tx_by_hash(request):
    try:
        txhash = request.query.get('txhash')
        txhash = unhexlify(txhash.encode())
        tx = tx_builder.get_tx(txhash)
        if tx is None:
            return web.Response(text="Not found tx.", status=400)
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
        mint = get_mintcoin(mint_id)
        if mint:
            return web_base.json_res(mint.getinfo())
        else:
            return web.Response(text='Not found mintcoin {}'.format(mint_id), status=400)
    except BaseException:
        return web_base.error_res()


__all__ = [
    "get_block_by_height",
    "get_block_by_hash",
    "get_tx_by_hash",
    "get_mintcoin_info"
]
