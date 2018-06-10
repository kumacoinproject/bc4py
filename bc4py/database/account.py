from bc4py.config import C, V, BlockChainError
from bc4py.user import CoinObject
from bc4py.utils import AESCipher
from bc4py.database.create import closing, create_db
import time
import os
from binascii import hexlify, unhexlify


def read_txhash2log(txhash, cur):
    d = cur.execute("""
        SELECT `type`,`from`,`to`,`coin_id`,`amount`,`time` FROM `log` WHERE `hash`=?
    """, (txhash,)).fetchall()
    if len(d) == 0:
        raise BlockChainError('Not found txhash {}'.format(hexlify(txhash)))
    _type, _from, _to, coin_id, amount, _time = d[0]

    if _type in (C.LOG_MOVEMENT, C.LOG_TRANSACTION):
        coins = CoinObject()
        for _type, _from, _to, coin_id, amount, _time in d:
            coins[coin_id] += amount
        return {
            'type': _type,
            'from': _from,
            'to': _to,
            'coins': coins,
            'time': _time}

    elif _type in (C.LOG_COMPLEX_MOVEMENT, C.LOG_COMPLEX_TRANSACTION):
        movement = dict()
        for _type, _from, _to, coin_id, amount, _time in d:
            k = (_from, _to)
            if k in movement:
                movement[k][coin_id] += amount
            else:
                movement[k] = CoinObject(coin_id, amount)
        return {
            'type': _type,
            'movement': movement,
            'time': _time}
    else:
        raise TypeError('Unknown log type {}.'.format(_type))


def insert_simple_log(_from, _to, coins, cur, _time=None, txhash=None):
    assert isinstance(_from, int) and isinstance(_to, int), 'user id is int.'
    assert isinstance(coins, CoinObject), 'Is not CoinObject'
    assert _from != _to, 'Sender and Recipient is same {}'.format(_from)
    _type = C.LOG_TRANSACTION if txhash else C.LOG_MOVEMENT
    _time = _time or int(time.time() - V.BLOCK_GENESIS_TIME)
    txhash = txhash or (_time.to_bytes(24, 'big') + os.urandom(8))
    movements = list()
    for index, (coin_id, amount) in enumerate(coins.items()):
        movements.append((
            txhash, index, _type, _from, _to, coin_id, amount, _time))
    cur.executemany("INSERT INTO `log` VALUES (?,?,?,?,?,?,?,?)", movements)


def insert_complex_log(movements, cur, _time=None, txhash=None):
    _type = C.LOG_COMPLEX_TRANSACTION if txhash else C.LOG_COMPLEX_MOVEMENT
    _time = _time or int(time.time() - V.BLOCK_GENESIS_TIME)
    txhash = txhash or (_time.to_bytes(24, 'big') + os.urandom(8))
    move = list()
    index = 0
    for (_from, _to), coins in movements.items():
        assert _from != _to, 'Sender and Recipient is same {}'.format(_from)
        assert isinstance(_from, int) and isinstance(_to, int), 'user id is int.'
        assert isinstance(coins, CoinObject), 'Is not CoinObject'
        for coin_id, amount in coins.items():
            move.append((txhash, index, _type, _from, _to, coin_id, amount, _time))
            index += 1
    cur.executemany("INSERT INTO `log` VALUES (?,?,?,?,?,?,?,?)", move)


def read_address2keypair(address, cur):
    d = cur.execute("""
        SELECT `id`,`sk`,`pk` FROM `pool` WHERE `ck`=?
    """, (address,)).fetchone()
    if d is None:
        raise BlockChainError('Not found address {}'.format(address))
    uuid, sk, pk = d
    if len(sk) == 32:
        sk = hexlify(sk).decode()
    elif V.ENCRYPT_KEY:
        sk = AESCipher.decrypt(V.ENCRYPT_KEY, sk)
        if len(sk) != 32:
            raise BlockChainError('Failed decrypt SecretKey. {}'.format(address))
    else:
        raise BlockChainError('Encrypted account.dat but no EncryptKey.')
    sk = hexlify(sk).decode()
    pk = hexlify(pk).decode()
    return uuid, sk, pk


def read_address2user(address, cur):
    user = cur.execute("""
        SELECT `user` FROM `pool` WHERE `ck`=?
    """, (address,)).fetxhone()
    if user is None:
        return None
    return user[0]


def update_keypair_user(uuid, user, cur):
    cur.execute("UPDATE `pool` SET `user`=? WHERE `id`=?", (user, uuid))


def insert_keypairs(pairs, cur):
    sk, pk, ck, user, _time = pairs[0]
    assert isinstance(sk, str) and isinstance(pk, str) and isinstance(ck, str) and isinstance(user, int)
    pairs = [(unhexlify(sk.encode()), unhexlify(pk.encode()), ck, user, _time)
             for sk, pk, ck, user, _time in pairs]
    cur.executemany("""
    INSERT INTO `pool` (`sk`,`pk`,`ck`,`user`,`time`) VALUES (?,?,?,?,?)
    """, pairs)


def read_account_info(user, cur):
    d = cur.execute("""
        SELECT `name`,`description`,`time` FROM `account` WHERE `id`=?
    """, (user,)).fetchone()
    if d is None:
        return None
    name, description, _time = d
    return name, description, _time


def read_address2account(address, cur):
    user = read_address2user(address, cur)
    if user is None:
        raise BlockChainError('Not found account {}'.format(address))
    return read_account_info(user, cur)


def read_name2user(name, cur):
    d = cur.execute("""
        SELECT `id` FROM `account` WHERE `name`=?
    """, (name,)).fetchone()
    if d is None:
        return None
    return d[0]


def create_account(name, cur, description="", _time=None):
    _time = _time or int(time.time() - V.BLOCK_GENESIS_TIME)
    cur.execute("""
        INSERT INTO `account` VALUES (?,?,?)
    """, (name, description, _time))
    d = cur.execute("SELECT last_insert_rowid()").fetchone()
    return d[0]


def create_new_user_keypair(name, cur):
    # ReservedKeypairを１つ取得
    d = cur.execute("""
        SELECT `id`,`sk`,`pk`,`ck` FROM `pool` WHERE `user`=?
    """, (C.ANT_RESERVED,)).fetchone()
    uuid, sk, pk, ck = d
    user = read_name2user(name, cur)
    if user is None:
        # 新規にユーザー作成
        user = create_account(name, cur)
    update_keypair_user(uuid, user, cur)
    return ck


__all__ = (
    "read_txhash2log", "insert_simple_log", "insert_complex_log",
    "read_address2keypair", "read_address2user", "update_keypair_user", "insert_keypairs",
    "read_account_info", "read_address2account", "create_new_user_keypair"
)
