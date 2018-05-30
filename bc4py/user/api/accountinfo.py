from bc4py.config import C, V, BlockChainError
from bc4py.user import CoinObject
from bc4py.user.account import create_new_group_keypair
from bc4py.database.create import closing, create_db
from bc4py.database.chain.read import read_tx_object
from bc4py.database.user.read import read_all_balance, get_transactions, group2address, read_balance_from_log
from bc4py.database.user.write import move_account_balance
from bc4py.user.utxo import get_unspent, full_unspents
from bc4py.user.api import web_base
from aiohttp import web
from binascii import hexlify


async def list_balance(request):
    with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
        cur = db.cursor()
        data = dict()
        f_from_log = bool(request.query.get('from_log', False))
        for group, coins in read_all_balance(cur=cur).items():
            if f_from_log:
                coins = read_balance_from_log(group=group, cur=cur)
            if group in C.account2name:
                group = C.account2name[group]
            data[group] = dict(coins)
    return web_base.json_res(data)


async def list_transactions(request):
    with closing(create_db(V.DB_BLOCKCHAIN_PATH)) as chain_db:
        with closing(create_db(V.DB_ACCOUNT_PATH)) as account_db:
            chain_cur = chain_db.cursor()
            account_cur = account_db.cursor()
            page = int(request.query.get('page', 0))
            limit = int(request.query.get('limit', 25))
            txs, f_next_page = get_transactions(page=page, limit=limit, cur=account_cur)
            for tx in txs:
                try:
                    data = read_tx_object(txhash=tx['hash'], cur=chain_cur).getinfo()
                except BlockChainError:
                    data = dict()
                tx['height'] = data.get('height')
                tx['txtype'] = data.get('type')
                tx['message_type'] = data.get('message_type')
                tx['message'] = data.get('message')
                tx['hash'] = hexlify(tx['hash']).decode()
    return web_base.json_res({'txs': txs, 'next': f_next_page})


async def list_unspents(request):
    with closing(create_db(V.DB_BLOCKCHAIN_PATH)) as chain_db:
        with closing(create_db(V.DB_ACCOUNT_PATH)) as account_db:
            chain_cur = chain_db.cursor()
            account_cur = account_db.cursor()
            unspent_pairs, orphan_pairs = get_unspent(chain_cur=chain_cur, account_cur=account_cur)
            unspents = full_unspents(unspent_pairs, chain_cur)
    orphan_pairs = [(hexlify(txhash).decode(), txindex) for txhash, txindex in orphan_pairs]
    for utxo in unspents:
        utxo['txhash'] = hexlify(utxo['txhash']).decode()
    return web_base.json_res({'unspents': unspents, 'orphans': orphan_pairs})


async def list_account_address(request):
    with closing(create_db(V.DB_ACCOUNT_PATH)) as account_db:
        cur = account_db.cursor()
        group = request.query.get('account', C.ANT_UNKNOWN)
        cks = group2address(group=group, cur=cur)
        account = C.account2name[group] if group in C.account2name else group
    return web_base.json_res({'account': account, 'address': [ck for uuid, ck in cks]})


async def move_one(request):
    try:
        post = await web_base.content_type_json_check(request)
        ant_from = post.get('from', C.ANT_UNKNOWN)
        ant_to = post['to']
        coin_id = int(post.get('coin_id', 0))
        amount = int(post['amount'])
        with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
            txhash = move_account_balance(from_group=ant_from, to_group=ant_to,
                                          coins=CoinObject(coin_id=coin_id, amount=amount), cur=db.cursor())
            db.commit()
        return web_base.json_res({'txhash': hexlify(txhash).decode()})
    except Exception as e:
        return web.Response(text=str(e), status=400)


async def move_many(request):
    try:
        post = await web_base.content_type_json_check(request)
        ant_from = post.get('from', C.ANT_UNKNOWN)
        ant_to = post['to']
        coins = CoinObject()
        for k, v in post['coins'].items():
            k = int(k)
            v = int(v)
            coins[k] += v
        with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
            txhash = move_account_balance(from_group=ant_from, to_group=ant_to, coins=coins, cur=db.cursor())
            db.commit()
        return web_base.json_res({'txhash': hexlify(txhash).decode()})
    except Exception as e:
        return web.Response(text=str(e), status=400)


async def new_address(request):
    with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
        cur = db.cursor()
        group = request.query.get('account', C.ANT_UNKNOWN)
        address = create_new_group_keypair(group=group, account_cur=cur)
        db.commit()
        account = C.account2name[group] if group in C.account2name else group
    return web_base.json_res({'address': address, 'account': account})


__all__ = [
    "list_balance",
    "list_transactions",
    "list_unspents",
    "list_account_address",
    "move_one",
    "move_many",
    "new_address"
]
