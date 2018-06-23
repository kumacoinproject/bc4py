from bc4py.config import C, V, BlockChainError
from bc4py.user import UserCoins
from bc4py.utils import AESCipher
from bc4py.database.create import closing, create_db
import time
import os
from binascii import hexlify, unhexlify
import multiprocessing
from nem_ed25519.base import Encryption


def read_txhash2log(txhash, cur):
    d = cur.execute("""
        SELECT `type`,`user`,`coin_id`,`amount`,`time` FROM `log` WHERE `hash`=?
    """, (txhash,)).fetchall()
    if len(d) == 0:
        return None
    movement = UserCoins()
    _type = _time = None
    for _type, user, coin_id, amount, _time in d:
        movement.add_coins(user, coin_id, amount)
    return MoveLog(txhash, _type, movement, _time, False)


def read_log_iter(cur, start=0):
    d = cur.execute("SELECT DISTINCT `hash` FROM `log` ORDER BY `id` DESC").fetchall()
    c = 0
    for (txhash,) in d:
        if start <= c:
            yield read_txhash2log(txhash, cur)
        c += 1


def insert_log(movements, cur, _type=None, _time=None, txhash=None):
    assert isinstance(movements, UserCoins), 'movements is UserCoin.'
    _type = _type or C.TX_INNER
    _time = _time or int(time.time() - V.BLOCK_GENESIS_TIME)
    txhash = txhash or (b'\x00' * 24 + _time.to_bytes(4, 'big') + os.urandom(4))
    move = list()
    index = 0
    for user, coins in movements.items():
        for coin_id, amount in coins:
            move.append((txhash, index, _type, user, coin_id, amount, _time))
            index += 1
    cur.executemany("""INSERT INTO `log` (`hash`,`index`,`type`,`user`,`coin_id`,
    `amount`,`time`) VALUES (?,?,?,?,?,?,?)""", move)
    return txhash


def read_address2keypair(address, cur):
    d = cur.execute("""
        SELECT `id`,`sk`,`pk` FROM `pool` WHERE `ck`=?
    """, (address,)).fetchone()
    if d is None:
        raise BlockChainError('Not found address {}'.format(address))
    uuid, sk, pk = d
    if len(sk) == 32:
        pass
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
    """, (address,)).fetchone()
    if user is None:
        return None
    return user[0]


def update_keypair_user(uuid, user, cur):
    cur.execute("UPDATE `pool` SET `user`=? WHERE `id`=?", (user, uuid))


def _insert(limit, encrypt_key, prefix, account_path, genesis_time, _cur=None):
    pairs = list()
    ecc = Encryption(prefix=prefix)
    while len(pairs) < limit:
        sk = unhexlify(ecc.secret_key().encode())
        if encrypt_key:
            sk = AESCipher.encrypt(key=encrypt_key, raw=sk)
        pk = unhexlify(ecc.public_key().encode())
        ck = ecc.get_address()
        pairs.append((sk, pk, ck, C.ANT_RESERVED, int(time.time() - genesis_time)))
    with closing(create_db(account_path)) as db:
        insert_keypairs(pairs, _cur or db.cursor())
        db.commit()


def auto_insert_keypairs(cur):
    multiprocessing.Process(
        target=_insert, args=(5, V.ENCRYPT_KEY, V.BLOCK_PREFIX, V.DB_ACCOUNT_PATH, V.BLOCK_GENESIS_TIME)
    ).start()
    _insert(1, V.ENCRYPT_KEY, V.BLOCK_PREFIX, V.DB_ACCOUNT_PATH, V.BLOCK_GENESIS_TIME, cur)


def insert_keypairs(pairs, cur):
    sk, pk, ck, user, _time = pairs[0]
    assert isinstance(sk, bytes) and isinstance(pk, bytes) and isinstance(ck, str) and isinstance(user, int)
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


def read_pooled_address_iter(cur):
    cur.execute("SELECT `id`,`ck`,`user` FROM `pool`")
    return cur


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
        return create_account(name, cur)
    return d[0]


def read_user2name(user, cur):
    d = cur.execute("""
        SELECT `name` FROM `account` WHERE `id`=?
    """, (user,)).fetchone()
    if d is None:
        raise Exception('Not found user id. {}'.format(user))
    return d[0]


def create_account(name, cur, description="", _time=None):
    _time = _time or int(time.time() - V.BLOCK_GENESIS_TIME)
    cur.execute("""
        INSERT INTO `account` (`name`,`description`,`time`) VALUES (?,?,?)
    """, (name, description, _time))
    d = cur.execute("SELECT last_insert_rowid()").fetchone()
    return d[0]


def create_new_user_keypair(name, cur):
    def get_pairs():
        return cur.execute("""
            SELECT `id`,`sk`,`pk`,`ck` FROM `pool` WHERE `user`=?
        """, (C.ANT_RESERVED,)).fetchall()
    # ReservedKeypairを１つ取得
    d = get_pairs()
    if len(d) < 100:
        auto_insert_keypairs(cur)
        d = get_pairs()
    uuid, sk, pk, ck = d[0]
    user = read_name2user(name, cur)
    if user is None:
        # 新規にユーザー作成
        user = create_account(name, cur)
    update_keypair_user(uuid, user, cur)
    return ck


class MoveLog:
    __slots__ = ("txhash", "type", "movement", "time", "on_memory")

    def __init__(self, txhash, _type, movement, _time, on_memory):
        self.txhash = txhash
        self.type = _type
        self.movement = movement
        self.time = _time
        self.on_memory = on_memory

    def __repr__(self):
        return "<MoveLog {} {}>".format(C.txtype2name[self.type], hexlify(self.txhash).decode())

    def __hash__(self):
        return hash(self.txhash)

    def get_dict_data(self, outer_cur=None):
        with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
            cur = outer_cur or db.cursor()
            movement = {read_user2name(user, cur): coins.coins for user, coins in self.movement.items()}
        return {
            'txhash': hexlify(self.txhash).decode(),
            'on_memory': self.on_memory,
            'type': C.txtype2name[self.type],
            'movement': movement,
            'time': self.time + V.BLOCK_GENESIS_TIME}

    def get_tuple_data(self):
        return self.type, self.movement, self.time


__all__ = [
    "read_txhash2log", "read_log_iter", "insert_log",
    "read_address2keypair", "read_address2user", "update_keypair_user", "insert_keypairs",
    "read_account_info", "read_pooled_address_iter", "read_address2account", "read_name2user", "read_user2name",
    "create_account", "create_new_user_keypair",
    "MoveLog"
]
