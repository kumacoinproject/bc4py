from bc4py.config import C, V, BlockChainError
from bc4py.user import UserCoins
from bc4py.utils import AESCipher
from bc4py.database.create import closing, create_db
import time
import os
from binascii import hexlify, unhexlify
from pooled_multiprocessing import mp_map_async
from nem_ed25519.key import secret_key, public_key, get_address
from weakref import ref
import logging


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


def delete_log(txhash, cur):
    cur.execute("""DELETE FROM `log` WHERE `hash`=?
    """, (txhash,))


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
    assert isinstance(name, str)
    d = cur.execute("""
        SELECT `id` FROM `account` WHERE `name`=?
    """, (name,)).fetchone()
    if d is None:
        return create_account(name, cur)
    return d[0]


def read_user2name(user, cur):
    assert isinstance(user, int)
    d = cur.execute("""
        SELECT `name` FROM `account` WHERE `id`=?
    """, (user,)).fetchone()
    if d is None:
        raise Exception('Not found user id. {}'.format(user))
    return d[0]


def create_account(name, cur, description="", _time=None, is_root=False):
    assert isinstance(name, str)
    if not (name.startswith('@') == is_root):
        raise BlockChainError('prefix"@" is root user, is_root={} name={}'.format(is_root, name))
    _time = _time or int(time.time() - V.BLOCK_GENESIS_TIME)
    cur.execute("""
        INSERT INTO `account` (`name`,`description`,`time`) VALUES (?,?,?)
    """, (name, description, _time))
    d = cur.execute("SELECT last_insert_rowid()").fetchone()
    return d[0]


def _single_generate(index, **kwargs):
    sk_hex = secret_key()
    sk = unhexlify(sk_hex.encode())
    if kwargs['encrypt_key']:
        sk = AESCipher.encrypt(key=kwargs['encrypt_key'], raw=sk)
    pk_hex = public_key(sk_hex)
    pk = unhexlify(pk_hex.encode())
    ck = get_address(pk=pk_hex, prefix=kwargs['prefix'])
    t = int(time.time() - kwargs['genesis_time'])
    return sk, pk, ck, C.ANT_RESERVED, t


def _callback(data_list):
    if isinstance(data_list[0], str):
        logging.error("Callback error, {}".format(data_list[0]))
        return
    with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
        insert_keypairs(data_list, db.cursor())
        db.commit()
    logging.debug("Generate {} keypairs.".format(len(data_list)))


def auto_insert_keypairs(num):
    kwards = {
        'encrypt_key': V.ENCRYPT_KEY,
        'prefix': V.BLOCK_PREFIX,
        'genesis_time': V.BLOCK_GENESIS_TIME}
    mp_map_async(_single_generate, range(num), callback=_callback, **kwards)


def create_new_user_keypair(name, cur):
    def get_all_keys():
        return cur.execute("""
            SELECT `id`,`sk`,`pk`,`ck` FROM `pool` WHERE `user`=?
        """, (C.ANT_RESERVED,)).fetchall()
    assert isinstance(name, str)
    # ReservedKeypairを１つ取得
    all_reserved_keys = get_all_keys()
    if len(all_reserved_keys) == 0:
        pairs = list()
        for i in range(5):
            pairs.append(_single_generate(i, encrypt_key=V.ENCRYPT_KEY,
                                          prefix=V.BLOCK_PREFIX, genesis_time=V.BLOCK_GENESIS_TIME))
        insert_keypairs(pairs, cur)
        all_reserved_keys = get_all_keys()
    elif len(all_reserved_keys) < 200:
        auto_insert_keypairs(250-len(all_reserved_keys))
    uuid, sk, pk, ck = all_reserved_keys[0]
    user = read_name2user(name, cur)
    if user is None:
        # 新規にユーザー作成
        user = create_account(name, cur)
    update_keypair_user(uuid, user, cur)
    return ck


class MoveLog:
    __slots__ = ("txhash", "type", "movement", "time", "on_memory", "pointer")

    def __init__(self, txhash, _type, movement, _time, on_memory, tx=None):
        self.txhash = txhash
        self.type = _type
        self.movement = movement
        self.time = _time
        self.on_memory = on_memory
        self.pointer = ref(tx) if tx else object()

    def __repr__(self):
        return "<MoveLog {} {}>".format(C.txtype2name.get(self.type, None), hexlify(self.txhash).decode())

    def __hash__(self):
        return hash(self.txhash)

    def get_dict_data(self, outer_cur=None):
        with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
            cur = outer_cur or db.cursor()
            movement = {read_user2name(user, cur): coins.coins for user, coins in self.movement.items()}
        return {
            'txhash': hexlify(self.txhash).decode(),
            'height':  self.height,
            'on_memory': self.on_memory,
            'type': C.txtype2name.get(self.type, None),
            'movement': movement,
            'time': self.time + V.BLOCK_GENESIS_TIME}

    def get_tuple_data(self):
        return self.type, self.movement, self.time

    @property
    def height(self):
        try:
            return self.pointer().height
        except Exception:
            return None


__all__ = [
    "read_txhash2log", "read_log_iter", "insert_log", "delete_log",
    "read_address2keypair", "read_address2user", "update_keypair_user", "insert_keypairs",
    "read_account_info", "read_pooled_address_iter", "read_address2account",
    "read_name2user", "read_user2name", "create_account", "create_new_user_keypair",
    "MoveLog"
]
