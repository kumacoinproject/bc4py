from bc4py.config import C, V
from bc4py.user.api import web_base
from bc4py.database.create import closing, create_db
from bc4py.database.chain.read import read_best_block, read_block_object, read_tx_object,\
    read_mint_coin, mint_coin_history
from aiohttp import web
from binascii import hexlify, unhexlify


async def get_block_by_height(request):
    with closing(create_db(V.DB_BLOCKCHAIN_PATH)) as db:
        cur = db.cursor()
        try:
            height = request.query.get('height')
            if height is None:
                return web.Response(text="Not found height.", status=400)
            best_block = read_best_block(height=height, cur=cur)
            block = read_block_object(blockhash=best_block.hash, cur=cur, f_fill_tx=True)
            data = block.getinfo()
            data['size'] = block.getsize()
            data['binary'] = hexlify(block.b).decode()
            return web_base.json_res(data)
        except Exception as e:
            return web.Response(text=str(e), status=400)


async def get_block_by_hash(request):
    with closing(create_db(V.DB_BLOCKCHAIN_PATH)) as db:
        cur = db.cursor()
        try:
            blockhash = request.query.get('blockhash')
            block = read_block_object(blockhash=unhexlify(blockhash.encode()), cur=cur, f_fill_tx=True)
            data = block.getinfo()
            data['size'] = block.getsize()
            data['binary'] = hexlify(block.b).decode()
            return web_base.json_res(data)
        except Exception as e:
            return web.Response(text=str(e), status=400)


async def get_tx_by_hash(request):
    with closing(create_db(V.DB_BLOCKCHAIN_PATH)) as db:
        cur = db.cursor()
        try:
            txhash = request.query.get('txhash')
            tx = read_tx_object(txhash=unhexlify(txhash.encode()), cur=cur)
            data = tx.getinfo()
            data['size'] = tx.getsize()
            data['binary'] = hexlify(tx.b).decode()
            data['signature'] = [(pubkey, hexlify(sign).decode()) for pubkey, sign in tx.signature]
            return web_base.json_res(data)
        except Exception as e:
            return web.Response(text=str(e), status=400)


async def get_mintinfo_by_id(request):
    with closing(create_db(V.DB_BLOCKCHAIN_PATH)) as db:
        cur = db.cursor()
        try:
            mint_id = int(request.query.get('mint_id', 0))
            mint = read_mint_coin(mint_id, cur)
            if mint:
                return web_base.json_res(mint.getinfo())
            else:
                return web.Response(text='Not found mintcoin {}'.format(mint_id), status=400)
        except BaseException:
            return web_base.error_res()


async def get_mint_history_by_id(request):
    with closing(create_db(V.DB_BLOCKCHAIN_PATH)) as db:
        cur = db.cursor()
        try:
            mint_id = int(request.query.get('mint_id', 0))
            mint_list = mint_coin_history(mint_id, cur)
            return web_base.json_res(mint_list)
        except BaseException:
            return web_base.error_res()

__all__ = [
    "get_block_by_height",
    "get_block_by_hash",
    "get_tx_by_hash",
    "get_mintinfo_by_id",
    "get_mint_history_by_id"
]
