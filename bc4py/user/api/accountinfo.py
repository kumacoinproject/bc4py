from bc4py.config import C, V, BlockChainError
from bc4py.bip32 import convert_address, addr2bin
from bc4py.user import Balance
from bc4py.user.api import utils
from bc4py.database.builder import chain_builder, user_account
from bc4py.database.create import create_db
from bc4py.database.account import *
from bc4py.database.tools import get_unspents_iter, get_my_unspents_iter
from aiohttp import web


async def list_balance(request):
    confirm = int(request.query.get('confirm', 6))
    data = dict()
    with create_db(V.DB_ACCOUNT_PATH) as db:
        cur = db.cursor()
        users = user_account.get_balance(confirm=confirm, outer_cur=cur)
        for user, balance in users.items():
            data[read_userid2name(user, cur)] = dict(balance)
    return utils.json_res(data)


async def list_transactions(request):
    page = int(request.query.get('page', 0))
    limit = int(request.query.get('limit', 25))
    data = list()
    f_next_page = False
    start = page * limit
    for tx_dict in user_account.get_movement_iter(start=page, f_dict=True):
        if limit == 0:
            f_next_page = True
            break
        tx_dict['index'] = start
        data.append(tx_dict)
        start += 1
        limit -= 1
    return utils.json_res({'txs': data, 'next': f_next_page})


async def list_unspents(request):
    if not chain_builder.db.db_config['addrindex']:
        return utils.error_res('address isn\'t full indexed')
    try:
        best_height = chain_builder.best_block.height
        page = int(request.query.get('page', 0))
        limit = min(100, int(request.query.get('limit', 25)))
        start = page * limit
        finish = (page+1) * limit - 1
        f_next_page = False
        target_address = request.query['address']
        unspents_iter = get_unspents_iter(target_address=set(target_address.split(',')))
        data = list()
        for index, (address, height, txhash, txindex, coin_id, amount) in enumerate(unspents_iter):
            if finish < index:
                f_next_page = True
                break
            if index < start:
                continue
            data.append({
                'address': address,
                'height': height,
                'confirmed': None if height is None else best_height - height,
                'txhash': txhash.hex(),
                'txindex': txindex,
                'coin_id': coin_id,
                'amount': amount
            })
        return utils.json_res({'data': data, 'next': f_next_page})
    except Exception:
        return utils.error_res()


async def list_private_unspents(request):
    data = list()
    best_height = chain_builder.best_block.height
    with create_db(V.DB_ACCOUNT_PATH) as db:
        cur = db.cursor()
        for address, height, txhash, txindex, coin_id, amount in get_my_unspents_iter(cur):
            data.append({
                'address': address,
                'height': height,
                'confirmed': None if height is None else best_height - height,
                'txhash': txhash.hex(),
                'txindex': txindex,
                'coin_id': coin_id,
                'amount': amount
            })
    return utils.json_res(data)


async def list_account_address(request):
    with create_db(V.DB_ACCOUNT_PATH) as db:
        cur = db.cursor()
        user_name = request.query.get('account', C.account2name[C.ANT_UNKNOWN])
        user_id = read_name2userid(user_name, cur)
        address_list = list()
        for uuid, address, user in read_pooled_address_iter(cur):
            if user_id == user:
                address_list.append(address)
    return utils.json_res({'account': user_name, 'user_id': user_id, 'address': address_list})


async def move_one(request):
    try:
        post = await utils.content_type_json_check(request)
        ant_from = post.get('from', C.account2name[C.ANT_UNKNOWN])
        ant_to = post['to']
        coin_id = int(post.get('coin_id', 0))
        amount = int(post['amount'])
        coins = Balance(coin_id, amount)
        with create_db(V.DB_ACCOUNT_PATH, f_strict=True) as db:
            cur = db.cursor()
            _from = read_name2userid(ant_from, cur)
            _to = read_name2userid(ant_to, cur)
            txhash = user_account.move_balance(_from, _to, coins, cur)
            db.commit()
        return utils.json_res({'txhash': txhash.hex(), 'from_id': _from, 'to_id': _to})
    except Exception:
        return utils.error_res()


async def move_many(request):
    try:
        post = await utils.content_type_json_check(request)
        ant_from = post.get('from', C.account2name[C.ANT_UNKNOWN])
        ant_to = post['to']
        coins = Balance()
        for k, v in post['coins'].items():
            coins[int(k)] += int(v)
        with create_db(V.DB_ACCOUNT_PATH, f_strict=True) as db:
            cur = db.cursor()
            _from = read_name2userid(ant_from, cur)
            _to = read_name2userid(ant_to, cur)
            txhash = user_account.move_balance(_from, _to, coins, cur)
            db.commit()
        return utils.json_res({'txhash': txhash.hex(), 'from_id': _from, 'to_id': _to})
    except Exception as e:
        return web.Response(text=str(e), status=400)


async def new_address(request):
    with create_db(V.DB_ACCOUNT_PATH) as db:
        cur = db.cursor()
        user_name = request.query.get('account', C.account2name[C.ANT_UNKNOWN])
        user_id = read_name2userid(user_name, cur)
        address = generate_new_address_by_userid(user_id, cur)
        db.commit()
        ver_identifier = addr2bin(hrp=V.BECH32_HRP, ck=address)
    return utils.json_res({
        'account': user_name,
        'user_id': user_id,
        'address': address,
        'version': ver_identifier[0],
        'identifier': ver_identifier[1:].hex(),
    })


async def get_keypair(request):
    try:
        with create_db(V.DB_ACCOUNT_PATH) as db:
            cur = db.cursor()
            address = request.query['address']
            uuid, keypair, path = read_address2keypair(address, cur)
            return utils.json_res({
                'uuid': uuid,
                'address': address,
                'private_key': keypair.get_secret_key().hex(),
                'public_key': keypair.get_public_key().hex(),
                'path': path
            })
    except Exception:
        return utils.error_res()


__all__ = [
    "list_balance",
    "list_transactions",
    "list_unspents",
    "list_private_unspents",
    "list_account_address",
    "move_one",
    "move_many",
    "new_address",
    "get_keypair",
]
