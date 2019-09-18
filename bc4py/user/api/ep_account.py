from bc4py.config import C, V
from bc4py.user import Balance
from bc4py.database.builder import chain_builder, user_account
from bc4py.database.create import create_db
from bc4py.database.account import *
from bc4py.database.tools import get_unspents_iter, get_my_unspents_iter
from bc4py.user.api.utils import auth, error_response
from fastapi import Depends
from fastapi.security import HTTPBasicCredentials
from pydantic import BaseModel
from bc4py_extension import PyAddress
from aioitertools import enumerate as aioenumerate
from typing import Dict


class MoveOne(BaseModel):
    amount: int
    sender: str = C.account2name[C.ANT_UNKNOWN]
    recipient: str
    coin_id: int = 0


class MoveMany(BaseModel):
    amount: int
    sender: str
    recipient: str = C.account2name[C.ANT_UNKNOWN]
    coins: Dict[int, int]


async def list_balance(confirm: int = 6, credentials: HTTPBasicCredentials = Depends(auth)):
    """
    This end-point show all user's account balances.
    * minimum confirmation height, default 6
    """
    data = dict()
    async with create_db(V.DB_ACCOUNT_PATH) as db:
        cur = await db.cursor()
        users = await user_account.get_balance(cur=cur, confirm=confirm)
        for user, balance in users.items():
            name = await read_userid2name(user, cur)
            data[name] = dict(balance)
    return data


async def list_transactions(page: int = 0, limit: int = 25, credentials: HTTPBasicCredentials = Depends(auth)):
    """
    This end-point show all account's recent transactions.
    * page number, default 0
    * page size limit, default 25
    """
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
    return {
        'txs': data,
        'next': f_next_page,
    }


async def list_unspents(address: str, page: int = 0, limit: int = 25):
    """
    This end-point show address related unspents.
    * some addresses joined with comma
    * page number, default 0
    * page size limit, default 25
    """
    if not chain_builder.db.db_config['addrindex']:
        return error_response('address isn\'t full indexed')
    try:
        best_height = chain_builder.best_block.height
        start = page * limit
        finish = (page+1) * limit - 1
        f_next_page = False
        target_address = set(map(lambda x: PyAddress.from_string(x), address.split(',')))
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
        return {
            'data': data,
            'next': f_next_page,
        }
    except Exception:
        return error_response()


async def list_private_unspents(credentials: HTTPBasicCredentials = Depends(auth)):
    """
    This end-point show all unspents of account have.
    """
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
    return data


async def list_account_address(account: str = C.account2name[C.ANT_UNKNOWN],
                               credentials: HTTPBasicCredentials = Depends(auth)):
    """
    This end-point show account all related addresses.
    * user name
    """
    async with create_db(V.DB_ACCOUNT_PATH) as db:
        cur = await db.cursor()
        user_id = await read_name2userid(account, cur)
        address_list = await read_pooled_address_list(user_id, cur)
    return {
        'account': account,
        'user_id': user_id,
        'address': [addr.string for addr in address_list],
    }


async def move_one(movement: MoveOne, credentials: HTTPBasicCredentials = Depends(auth)):
    """
    This end-point create inner transaction.
    * amount
    * recipient account name
    * sending account name
    * coinId
    """
    try:
        coins = Balance(movement.coin_id, movement.amount)
        async with create_db(V.DB_ACCOUNT_PATH, strict=True) as db:
            cur = await db.cursor()
            from_user = await read_name2userid(movement.sender, cur)
            to_user = await read_name2userid(movement.recipient, cur)
            txhash = await user_account.move_balance(cur, from_user, to_user, coins)
            await db.commit()
        return {
            'txhash': txhash.hex(),
            'from_id': from_user,
            'to_id': to_user,
        }
    except Exception:
        return error_response()


async def move_many(movement: MoveMany, credentials: HTTPBasicCredentials = Depends(auth)):
    """
    This end-point create inner transaction.
    """
    try:
        coins = Balance()
        for k, v in movement.coins.items():
            assert 0 <= k and 0 < v
            coins[k] += v
        async with create_db(V.DB_ACCOUNT_PATH, strict=True) as db:
            cur = await db.cursor()
            from_user = await read_name2userid(movement.sender, cur)
            to_user = await read_name2userid(movement.recipient, cur)
            txhash = await user_account.move_balance(cur, from_user, to_user, coins)
            await db.commit()
        return {
            'txhash': txhash.hex(),
            'from_id': from_user,
            'to_id': to_user,
        }
    except Exception:
        return error_response()


__all__ = [
    "list_balance",
    "list_transactions",
    "list_unspents",
    "list_private_unspents",
    "list_account_address",
    "move_one",
    "move_many",
]
