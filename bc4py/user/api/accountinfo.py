from bc4py.config import C, V, BlockChainError
from bc4py.user import Balance
from bc4py.user.api import utils
from bc4py.database.builder import chain_builder, user_account
from bc4py.database.create import create_db
from bc4py.database.account import *
from bc4py.database.tools import get_unspents_iter, get_my_unspents_iter
from bc4py_extension import PyAddress
from aioitertools import enumerate as aioenumerate
from aiohttp import web


async def list_balance(request):
    confirm = int(request.query.get('confirm', 6))
    data = dict()
    async with create_db(V.DB_ACCOUNT_PATH) as db:
        cur = await db.cursor()
        users = await user_account.get_balance(cur=cur, confirm=confirm)
        for user, balance in users.items():
            name = await read_userid2name(user, cur)
            data[name] = dict(balance)
    return utils.json_res(data)


async def list_transactions(request):
    page = int(request.query.get('page', 0))
    limit = int(request.query.get('limit', 25))
    data = list()
    f_next_page = False
    start = page * limit
    async for tx_dict in user_account.get_movement_iter(start=page, f_dict=True):
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
        target_address = request.query.get('address')
        if target_address is None:
            return utils.error_res('not found key "address"')
        target_address = set(map(lambda x: PyAddress.from_string(x), target_address.split(',')))
        unspents_iter = get_unspents_iter(target_address=target_address)
        data = list()
        async for index, (address, height, txhash, txindex, coin_id, amount) in aioenumerate(unspents_iter):
            if finish < index:
                f_next_page = True
                break
            if index < start:
                continue
            data.append({
                'address': address.string,
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
    async with create_db(V.DB_ACCOUNT_PATH) as db:
        cur = await db.cursor()
        unspent_iter = await get_my_unspents_iter(cur)
        async for address, height, txhash, txindex, coin_id, amount in unspent_iter:
            data.append({
                'address': address.string,
                'height': height,
                'confirmed': None if height is None else best_height - height,
                'txhash': txhash.hex(),
                'txindex': txindex,
                'coin_id': coin_id,
                'amount': amount
            })
    return utils.json_res(data)


async def list_account_address(request):
    async with create_db(V.DB_ACCOUNT_PATH) as db:
        cur = await db.cursor()
        user_name = request.query.get('account', C.account2name[C.ANT_UNKNOWN])
        user_id = await read_name2userid(user_name, cur)
        address_list = await read_pooled_address_list(user_id, cur)
    return utils.json_res({
        'account': user_name,
        'user_id': user_id,
        'address': [addr.string for addr in address_list],
    })


async def move_one(request):
    try:
        post = await utils.content_type_json_check(request)
        ant_from = post.get('from', C.account2name[C.ANT_UNKNOWN])
        ant_to = post['to']
        coin_id = int(post.get('coin_id', 0))
        amount = int(post['amount'])
        coins = Balance(coin_id, amount)
        async with create_db(V.DB_ACCOUNT_PATH, strict=True) as db:
            cur = await db.cursor()
            from_user = await read_name2userid(ant_from, cur)
            to_user = await read_name2userid(ant_to, cur)
            txhash = await user_account.move_balance(cur, from_user, to_user, coins)
            await db.commit()
        return utils.json_res({
            'txhash': txhash.hex(),
            'from_id': from_user,
            'to_id': to_user,
        })
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
        async with create_db(V.DB_ACCOUNT_PATH, strict=True) as db:
            cur = await db.cursor()
            from_user = await read_name2userid(ant_from, cur)
            to_user = await read_name2userid(ant_to, cur)
            txhash = await user_account.move_balance(cur, from_user, to_user, coins)
            await db.commit()
        return utils.json_res({
            'txhash': txhash.hex(),
            'from_id': from_user,
            'to_id': to_user,
        })
    except Exception as e:
        return web.Response(text=str(e), status=400)


async def new_address(request):
    async with create_db(V.DB_ACCOUNT_PATH) as db:
        cur = await db.cursor()
        user_name = request.query.get('account', C.account2name[C.ANT_UNKNOWN])
        user_id = await read_name2userid(user_name, cur)
        addr: PyAddress = await generate_new_address_by_userid(user_id, cur)
        await db.commit()
    return utils.json_res({
        'account': user_name,
        'user_id': user_id,
        'address': addr.string,
        'version': addr.version,
        'identifier': addr.identifier().hex(),
    })


async def get_keypair(request):
    try:
        async with create_db(V.DB_ACCOUNT_PATH) as db:
            cur = await db.cursor()
            address = request.query.get('address')
            if address is None:
                return utils.error_res('not foud key "address"')
            uuid, keypair, path = await read_address2keypair(PyAddress.from_string(address), cur)
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
