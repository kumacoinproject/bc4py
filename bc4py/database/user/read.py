#!/user/env python3
# -*- coding: utf-8 -*-

"""
accountDBへの読み込み操作のみ
"""

from bc4py.config import C, V
from bc4py.utils import AESCipher
from bc4py.user import CoinObject
from binascii import hexlify, unhexlify


def keypool_size(cur) ->int:
    d = cur.execute("""
        SELECT `id` FROM `pool` WHERE `group` = ?
        """, (C.ANT_RESERVED,))
    keys = d.fetchall()
    return len(keys)


def address2group(address, cur):
    d = cur.execute("""
            SELECT `group` FROM `pool` WHERE `ck`=?
            """, (address,)).fetchone()
    if d is None:
        return None
    return d[0]


def group2address(group, cur):
    d = cur.execute("""
        SELECT `id`,`ck` FROM `pool` WHERE `group`=?
        """, (group,)).fetchall()
    return d


def read_utxo(txhash, txindex, cur):
    d = cur.execute("""
        SELECT `used` FROM `utxo` WHERE `hash`=? AND `index`=?
        """, (txhash, txindex)).fetchone()
    if d is None:
        return None
    else:
        return bool(d[0])


def read_all_utxo(cur) ->[(bytes, int)]:
    d = cur.execute("""
        SELECT `hash`,`index` FROM `utxo` WHERE `used`=?
        """, (0,))
    # 古いものから出てくる
    return d.fetchall()


def read_balance(group, cur) ->CoinObject:
    d = cur.execute("""
        SELECT `coin_id`,`amount` FROM `balance` WHERE `group`=?
        """, (group,))
    coins = CoinObject()
    for coin_id, amount in d.fetchall():
        coins[coin_id] = amount
    return coins


def read_all_balance(cur):
    cur.execute("SELECT `group`,`coin_id`,`amount` FROM `balance`")
    groups = dict()
    for group, coin_id, amount in cur:
        if group in groups:
            groups[group] += CoinObject(coin_id=coin_id, amount=amount)
        else:
            groups[group] = CoinObject(coin_id=coin_id, amount=amount)
    return groups


def read_balance_from_log(group, cur) ->CoinObject:
    # 移動ログにより残高を取得(遅い)
    balance_plus = cur.execute("""
        SELECT `coin_id`,SUM(`amount`) FROM `log` WHERE `to_group`=? GROUP BY `coin_id`
        """, (group,)).fetchall()
    balance_minus = cur.execute("""
        SELECT `coin_id`,SUM(`amount`) FROM `log` WHERE `from_group`=? GROUP BY `coin_id`
        """, (group,)).fetchall()

    coins = CoinObject()
    for coin_id, amount in balance_plus:
        coins[coin_id] += amount
    for coin_id, amount in balance_minus:
        coins[coin_id] -= amount
    return coins


def address2keypair(address, cur):
    d = cur.execute("""
        SELECT `sk`,`pk` FROM `pool` WHERE `ck`=?
        """, (address,)).fetchone()
    if d is None:
        return None, None
    sk, pk = d
    sk = AESCipher.decrypt(V.ENCRYPT_KEY, sk) if V.ENCRYPT_KEY else sk
    return hexlify(sk).decode(), hexlify(pk).decode()


def public2keypair(pk, cur):
    print("It's slow function! public2keypair")
    d = cur.execute("""
            SELECT `sk`,`pk` FROM `pool` WHERE `pk`=?
            """, (unhexlify(pk.encode()),)).fetchone()
    if d is None:
        return None, None
    sk, pk = d
    sk = AESCipher.decrypt(V.ENCRYPT_KEY, sk) if V.ENCRYPT_KEY else sk
    return hexlify(sk).decode(), hexlify(pk).decode()


def raw_transaction(txhash, cur):
    cur.execute("""
        SELECT `direction`,`index`,`from_group`,`to_group`,`coin_id`,`amount`,`time` FROM `log`
        WHERE `hash`=?""", (txhash,))
    account = dict()
    time = None
    inputs = outputs = 0
    for direction, index, from_group, to_group, coin_id, amount, time in cur:
        if to_group in account:
            account[to_group][coin_id] += amount
        else:
            account[to_group] = CoinObject(coin_id=coin_id, amount=amount)
        if from_group in account:
            account[from_group][coin_id] -= amount
        else:
            account[from_group] = CoinObject(coin_id=coin_id, amount=amount * -1)
        if direction == 1:
            inputs += 1
        else:
            outputs += 1
    movement = dict()
    for name, coins in account.items():
        name = C.account2name[name] if name in C.account2name else name
        movement[name] = dict(coins)
    if len(movement) == 0:
        txtype = 'nonsense'
    elif C.ANT_OUTSIDE in account:
        v = movement[C.account2name[C.ANT_OUTSIDE]].values()
        vi = [i > 0 for i in v]
        if all(vi):
            txtype = 'outgoing'
        elif not any(vi):
            txtype = 'incoming'
        else:
            txtype = 'mix'
        del movement[C.account2name[C.ANT_OUTSIDE]]
    else:
        txtype = 'inner'
    tx = {
        'hash': txhash,
        'type': txtype,
        'movement': movement,
        'time': time}
    return tx


def get_transactions(page, limit, cur):
    d = cur.execute("""
    SELECT DISTINCT `hash` FROM `log` ORDER BY `id` DESC
    """).fetchall()
    start = page * limit
    stop = (page + 1) * limit
    count = 0
    txs = list()
    next_page = True
    for (txhash,) in d:
        if start <= count < stop:
            txs.append(raw_transaction(txhash=txhash, cur=cur))
        elif count == stop:
            break
        count += 1
    else:
        next_page = False
    return txs, next_page
