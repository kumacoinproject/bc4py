from bc4py.config import C, V, BlockChainError
from bc4py.user import Balance
from bc4py.user.api import web_base
from bc4py.database.builder import builder, user_account
from bc4py.database.create import closing, create_db
from bc4py.database.account import *
from bc4py.database.tools import get_unspents_iter
from aiohttp import web
from binascii import hexlify
from nem_ed25519.key import convert_address


async def list_balance(request):
    confirm = int(request.query.get('confirm', 6))
    users = user_account.get_balance(confirm)
    data = dict()
    with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
        cur = db.cursor()
        for user, balance in users.items():
            data[read_user2name(user, cur)] = dict(balance)
    return web_base.json_res(data)


async def list_transactions(request):
    page = int(request.query.get('page', 0))
    limit = int(request.query.get('limit', 25))
    data = list()
    f_next_page = False
    for tx_dict in user_account.get_movement_iter(start=page, f_dict=True):
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
            'confirmed': None if height is None else best_height - height,
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
                if user == C.ANT_CONTRACT:
                    address_list.append(convert_address(ck=address, prefix=V.BLOCK_CONTRACT_PREFIX))
                else:
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
        coins = Balance(coin_id, amount)
        with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
            cur = db.cursor()
            _from = read_name2user(ant_from, cur)
            _to = read_name2user(ant_to, cur)
            txhash = user_account.move_balance(_from, _to, coins, cur)
            db.commit()
        return web_base.json_res({
            'txhash': hexlify(txhash).decode(),
            'from_id': _from, 'to_id': _to})
    except Exception as e:
        return web.Response(text=str(e), status=400)


async def move_many(request):
    try:
        post = await web_base.content_type_json_check(request)
        ant_from = post.get('from', C.ANT_NAME_UNKNOWN)
        ant_to = post['to']
        coins = Balance()
        for k, v in post['coins'].items():
            coins[int(k)] += int(v)
        with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
            cur = db.cursor()
            _from = read_name2user(ant_from, cur)
            _to = read_name2user(ant_to, cur)
            txhash = user_account.move_balance(_from, _to, coins, cur)
            db.commit()
        return web_base.json_res({
            'txhash': hexlify(txhash).decode(),
            'from_id': _from, 'to_id': _to})
    except Exception as e:
        return web.Response(text=str(e), status=400)


async def new_address(request):
    with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
        cur = db.cursor()
        user_name = request.query.get('account', C.ANT_NAME_UNKNOWN)
        user_id = read_name2user(user_name, cur)
        address = create_new_user_keypair(user_name, cur)
        db.commit()
        if user_id == C.ANT_CONTRACT:
            address = convert_address(address, V.BLOCK_CONTRACT_PREFIX)
    return web_base.json_res({'account': user_name, 'user_id': user_id, 'address': address})


async def get_keypair(request):
    try:
        with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
            cur = db.cursor()
            address = request.query['address']
            uuid, sk, pk = read_address2keypair(address, cur)
            return web_base.json_res({
                'uuid': uuid,
                'address': address,
                'private_key': sk,
                'public_key': pk})
    except BlockChainError as e:
        return web.Response(text=str(e), status=400)
    except Exception:
        return web_base.error_res()


__all__ = [
    "list_balance",
    "list_transactions",
    "list_unspents",
    "list_account_address",
    "move_one",
    "move_many",
    "new_address",
    "get_keypair"
]
