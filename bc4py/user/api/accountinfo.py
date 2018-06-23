from bc4py.config import C, V, BlockChainError
from bc4py.user import CoinObject
from bc4py.user.api import web_base
from bc4py.database.builder import builder, tx_builder, user_account
from bc4py.database.create import closing, create_db
from bc4py.database.account import *
from bc4py.database.tools import get_unspents_iter
from aiohttp import web
from binascii import hexlify


async def list_balance(request):
    confirm = int(request.query.get('confirm', 6))
    users = user_account.get_balance(confirm)
    data = dict()
    with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
        cur = db.cursor()
        for user, balance in users.items():
            data[read_user2name(user, cur)] = balance.coins
    return web_base.json_res(data)


async def list_transactions(request):
    with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
        cur = db.cursor()
        page = int(request.query.get('page', 0))
        limit = int(request.query.get('limit', 25))
        data = list()
        f_next_page = False
        for tx_dict in read_log_iter(cur, start=page, f_dict=True):
            if limit == 0:
                f_next_page = True
                break
            data.append(tx_dict)
            limit -= 1
    return web_base.json_res({'txs': data, 'next': f_next_page})


async def list_unspents(request):
    data = list()
    best_height = builder.best_block.height
    for address, height, txhash, txindex, coin_id, amount in get_unspents_iter():
        data.append({
            'address': address,
            'height': height,
            'confirmed': best_height - height,
            'txhash': hexlify(txhash).decode(),
            'txindex': txindex,
            'coin_id': coin_id,
            'amount': amount})
    return web_base.json_res(data)


async def list_account_address(request):
    with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
        cur = db.cursor()
        user_name = request.query.get('account', C.ANT_NAME_UNKNOWN)
        user_id = read_name2user(user_name, cur)
        address_list = list()
        for uuid, address, user in read_pooled_address_iter(cur):
            if user_id == user:
                address_list.append(address)
    return web_base.json_res({
        'account': user_name, 'user_id': user_id, 'address': address_list})


async def move_one(request):
    try:
        post = await web_base.content_type_json_check(request)
        ant_from = post.get('from', C.ANT_NAME_UNKNOWN)
        ant_to = post['to']
        coin_id = int(post.get('coin_id', 0))
        amount = int(post['amount'])
        coins = CoinObject(coin_id, amount)
        with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
            cur = db.cursor()
            _from = read_name2user(ant_from, cur)
            _to = read_name2user(ant_to, cur)
            txhash = user_account.move_balance(_from, _to, coins)
            db.commit()
        return web_base.json_res({'txhash': hexlify(txhash).decode()})
    except Exception as e:
        return web.Response(text=str(e), status=400)


async def move_many(request):
    try:
        post = await web_base.content_type_json_check(request)
        ant_from = post.get('from', C.ANT_NAME_UNKNOWN)
        ant_to = post['to']
        coins = CoinObject()
        for k, v in post['coins'].items():
            coins[int(k)] += int(v)
        with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
            cur = db.cursor()
            _from = read_name2user(ant_from, cur)
            _to = read_name2user(ant_to, cur)
            txhash = user_account.move_balance(_from, _to, coins)
            db.commit()
        return web_base.json_res({'txhash': hexlify(txhash).decode()})
    except Exception as e:
        return web.Response(text=str(e), status=400)


async def new_address(request):
    with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
        cur = db.cursor()
        user_name = request.query.get('account', C.ANT_NAME_UNKNOWN)
        user_id = read_name2user(user_name, cur)
        address = create_new_user_keypair(user_name, cur)
        db.commit()
    return web_base.json_res({'account': user_name, 'user_id': user_id, 'address': address})


__all__ = [
    "list_balance",
    "list_transactions",
    "list_unspents",
    "list_account_address",
    "move_one",
    "move_many",
    "new_address"
]
