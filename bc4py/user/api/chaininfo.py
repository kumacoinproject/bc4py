from bc4py.database.builder import chain_builder, tx_builder
from bc4py.database.mintcoin import get_mintcoin_object
from bc4py.user.api.utils import error_response
from binascii import a2b_hex


async def get_block_by_height(height: int, txinfo: bool = False):
    blockhash = chain_builder.get_block_hash(height)
    if blockhash is None:
        return error_response("Not found height")
    block = chain_builder.get_block(blockhash)
    data = block.getinfo(txinfo)
    data['hex'] = block.b.hex()
    return data


async def get_block_by_hash(hash: str, txinfo: bool = False):
    try:
        blockhash = a2b_hex(hash)
        block = chain_builder.get_block(blockhash)
        if block is None:
            return error_response("Not found block")
        data = block.getinfo(txinfo)
        data['hex'] = block.b.hex()
        return data
    except Exception:
        return error_response()


async def get_tx_by_hash(hash: str):
    try:
        txhash = a2b_hex(hash)
        # if you cannot get TX, please check DB config `txindex`
        tx = tx_builder.get_tx(txhash)
        if tx is None:
            if chain_builder.db.db_config['txindex']:
                return error_response("not found tx")
            else:
                return error_response('not found tx, please set `txindex` true if you want full indexed')
        data = tx.getinfo()
        data['hex'] = tx.b.hex()
        return data
    except Exception:
        return error_response()


async def get_mintcoin_info(mint_id: int = 0):
    try:
        m = get_mintcoin_object(coin_id=mint_id)
        return m.info
    except Exception:
        return error_response()


async def get_mintcoin_history(mint_id: int = 0):
    try:
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
        return data
    except Exception:
        return error_response()


__all__ = [
    "get_block_by_height",
    "get_block_by_hash",
    "get_tx_by_hash",
    "get_mintcoin_info",
    "get_mintcoin_history",
]
