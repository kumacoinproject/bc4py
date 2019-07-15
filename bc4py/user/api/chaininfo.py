from bc4py.user.api import utils
from bc4py.database.builder import chain_builder, tx_builder
from bc4py.database.mintcoin import get_mintcoin_object
from aiohttp import web
from binascii import a2b_hex


async def get_block_by_height(request):
    with_tx_info = request.query.get('txinfo', 'false')
    try:
        height = int(request.query['height'])
    except Exception:
        return web.Response(text="Height is not specified", status=400)
    blockhash = chain_builder.get_block_hash(height)
    if blockhash is None:
        return web.Response(text="Not found height", status=400)
    block = chain_builder.get_block(blockhash)
    data = block.getinfo(with_tx_info == 'true')
    data['hex'] = block.b.hex()
    return utils.json_res(data)


async def get_block_by_hash(request):
    try:
        with_tx_info = request.query.get('txinfo', 'false')
        blockhash = request.query.get('hash')
        if blockhash is None:
            return web.Response(text="Not found height", status=400)
        blockhash = a2b_hex(blockhash)
        block = chain_builder.get_block(blockhash)
        if block is None:
            return web.Response(text="Not found block", status=400)
        data = block.getinfo(with_tx_info == 'true')
        data['size'] = block.size
        data['hex'] = block.b.hex()
        return utils.json_res(data)
    except Exception as e:
        return utils.error_res()


async def get_tx_by_hash(request):
    try:
        txhash = request.query.get('hash')
        txhash = a2b_hex(txhash)
        # if you cannot get TX, please check DB config `txindex`
        tx = tx_builder.get_tx(txhash)
        if tx is None:
            if chain_builder.db.db_config['txindex']:
                return web.Response(text="not found tx", status=400)
            else:
                return web.Response(
                    text='not found tx, please set `txindex` true if you want full indexed',
                    status=400)
        data = tx.getinfo()
        data['hex'] = tx.b.hex()
        return utils.json_res(data)
    except Exception as e:
        return utils.error_res()


async def get_mintcoin_info(request):
    try:
        mint_id = int(request.query.get('mint_id', 0))
        m = get_mintcoin_object(coin_id=mint_id)
        return utils.json_res(m.info)
    except Exception:
        return utils.error_res()


async def get_mintcoin_history(request):
    try:
        mint_id = int(request.query.get('mint_id', 0))
        data = list()
        # from only database
        for height, index, txhash, params, setting in chain_builder.db.read_coins_iter(coin_id=mint_id):
            data.append({
                'height': height,
                'index': index,
                'txhash': txhash.hex(),
                'params': params,
                'setting': setting,
            })
        return utils.json_res(data)
    except Exception:
        return utils.error_res()


__all__ = [
    "get_block_by_height",
    "get_block_by_hash",
    "get_tx_by_hash",
    "get_mintcoin_info",
    "get_mintcoin_history",
]
