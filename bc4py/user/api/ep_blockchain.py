from bc4py.database import obj
from bc4py.database.mintcoin import get_mintcoin_object
from bc4py.user.api.utils import error_response
from binascii import a2b_hex


async def get_block_by_height(height: int, txinfo: bool = False):
    """
    show block info from height
    * Arguments
        1. **height** :  block height
        2. **txinfo** :  show tx info if true, only txhash if false
    """
    blockhash = obj.chain_builder.get_block_hash(height)
    if blockhash is None:
        return error_response("Not found height")
    block = obj.chain_builder.get_block(blockhash)
    data = block.getinfo(txinfo)
    data['hex'] = block.b.hex()
    return data


async def get_block_by_hash(hash: str, txinfo: bool = False):
    """
    show block info by hash
    * Arguments
        1. **hash** :  block hash
        2. **txinfo** :  show tx info if true, only txhash if false
    """
    try:
        blockhash = a2b_hex(hash)
        block = obj.chain_builder.get_block(blockhash)
        if block is None:
            return error_response("Not found block")
        data = block.getinfo(txinfo)
        data['hex'] = block.b.hex()
        return data
    except Exception:
        return error_response()


async def get_tx_by_hash(hash: str):
    """
    show tx info by hash
    * Arguments
        1. **hash** : txhash
    """
    try:
        txhash = a2b_hex(hash)
        # if you cannot get TX, please check DB config `txindex`
        tx = obj.tx_builder.get_tx(txhash)
        if tx is None:
            if obj.tables.table_config['txindex']:
                return error_response("not found the tx in this chain")
            else:
                return error_response('not found the tx, please set `txindex` true if you want full indexed')
        data = tx.getinfo()
        data['hex'] = tx.b.hex()
        return data
    except Exception:
        return error_response()


async def get_mintcoin_info(mint_id: int = 0):
    """
    show mint coin info by coinId
    * Arguments
        1. **mint_id** : mint coin id
    * About
        * id 0 is base currency
    """
    try:
        m = get_mintcoin_object(coin_id=mint_id)
        return m.info
    except Exception:
        return error_response()


async def get_mintcoin_history(mint_id: int = 0):
    """
    show mint coin history by coinId
    * Arguments
        1. **mint_id** : mint coin id
    * About
        * caution! this show only database stored data, not memory not unconfirmed status.
    """
    try:
        data = list()
        # from only database
        for height, index, txhash, params, setting in obj.tables.read_coins_iter(coin_id=mint_id):
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
