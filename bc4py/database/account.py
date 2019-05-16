from bc4py.config import C, V, BlockChainError
from bc4py.bip32 import Bip32, BIP32_HARDEN
from bc4py.user import Accounting
from bc4py.database.create import create_db
from time import time
from bc4py.utils import AESCipher
from multi_party_schnorr import PyKeyPair
from weakref import ref
from logging import getLogger
import os


log = getLogger('bc4py')


def read_txhash2log(txhash, cur):
    d = cur.execute("""
        SELECT `type`,`user`,`coin_id`,`amount`,`time` FROM `log` WHERE `hash`=?
    """, (txhash,)).fetchall()
    if len(d) == 0:
        return None
    movement = Accounting()
    _type = _time = None
    for _type, user, coin_id, amount, _time in d:
        movement[user][coin_id] += amount
    return MoveLog(txhash, _type, movement, _time)


def read_log_iter(cur, start=0):
    d = cur.execute("SELECT DISTINCT `hash` FROM `log` ORDER BY `id` DESC").fetchall()
    c = 0
    for (txhash,) in d:
        if start <= c:
            yield read_txhash2log(txhash, cur)
        c += 1


def insert_log(movements, cur, _type=None, _time=None, txhash=None):
    assert isinstance(movements, Accounting), 'movements is Accounting'
    _type = _type or C.TX_INNER
    _time = _time or int(time() - V.BLOCK_GENESIS_TIME)
    txhash = txhash or (b'\x00'*24 + _time.to_bytes(4, 'big') + os.urandom(4))
    move = list()
    index = 0
    for user, coins in movements.items():
        for coin_id, amount in coins:
            move.append((txhash, index, _type, user, coin_id, amount, _time))
            index += 1
    cur.executemany(
        """INSERT INTO `log` (`hash`,`index`,`type`,`user`,`coin_id`,
    `amount`,`time`) VALUES (?,?,?,?,?,?,?)""", move)
    return txhash


def delete_log(txhash, cur):
    cur.execute("""DELETE FROM `log` WHERE `hash`=?
    """, (txhash,))


def read_address2keypair(address, cur):
    if V.EXTENDED_KEY_OBJ is None or V.EXTENDED_KEY_OBJ.secret is None:
        raise BlockChainError('You try to get keypair but secret extended key not found')
    d = cur.execute("""
        SELECT `id`,`sk`,`user`,`is_inner`,`index` FROM `pool` WHERE `ck`=?
    """, (address,)).fetchone()
    if d is None:
        raise BlockChainError('Not found address {}'.format(address))
    uuid, sk, user, is_inner, index = d
    if sk is None:
        bip = extract_keypair(user=user, is_inner=is_inner, index=index, cur=cur)
        sk = bip.get_private_key()
        path = bip.path
    else:
        sk = AESCipher.decrypt(key=V.EXTENDED_KEY_OBJ.get_secret_key(), enc=sk)
        path = None
    keypair: PyKeyPair = PyKeyPair.from_secret_key(sk)
    return uuid, keypair, path


def read_address2user(address, cur):
    user = cur.execute("""
        SELECT `user` FROM `pool` WHERE `ck`=?
    """, (address,)).fetchone()
    if user is None:
        return None
    return user[0]


def insert_keypair_from_bip(ck, user, is_inner, index, cur):
    assert isinstance(ck, str) and isinstance(user, int)\
           and isinstance(is_inner, bool) and isinstance(index, int)
    cur.execute(
        """
    INSERT OR IGNORE INTO `pool` (`ck`,`user`,`is_inner`,`index`,`time`) VALUES (?,?,?,?,?)
    """, (ck, user, int(is_inner), index, int(time())))


def insert_keypair_from_outside(sk, ck, user, cur):
    assert isinstance(sk, bytes) and isinstance(ck, str) and isinstance(user, int)
    if V.EXTENDED_KEY_OBJ is None or V.EXTENDED_KEY_OBJ.secret is None:
        raise BlockChainError('You try to insert keypair but secret extended key not found')
    sk = AESCipher.encrypt(key=V.EXTENDED_KEY_OBJ.get_secret_key(), raw=sk)
    cur.execute("""
    INSERT OR IGNORE INTO `pool` (`sk`,`ck`,`user`,`time`) VALUES (?,?,?,?)
    """, (sk, ck, user, int(time())))


def get_keypair_last_index(user, is_inner, cur):
    assert isinstance(user, int) and isinstance(is_inner, bool)
    cur.execute("""
    SELECT `index` FROM `pool` WHERE `user`=? AND `is_inner`=?
    """, (user, int(is_inner)))
    index = -1
    for (index,) in cur:
        pass
    index += 1
    return index


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
    _time = _time or int(time() - V.BLOCK_GENESIS_TIME)
    # get extend public key
    if V.EXTENDED_KEY_OBJ is None or V.EXTENDED_KEY_OBJ.secret is None:
        raise BlockChainError('you try to create account but not found secretKey')
    last_id = cur.execute("SELECT MAX(`id`) FROM `account`").fetchone()[0]
    extended_key = V.EXTENDED_KEY_OBJ.child_key(BIP32_HARDEN + last_id + 1).extended_key(False)
    cur.execute("""
        INSERT INTO `account` (`name`,`extended_key`,`description`,`time`) VALUES (?,?,?,?)
    """, (name, extended_key, description, _time))
    insert_id = cur.execute("SELECT last_insert_rowid()").fetchone()[0]
    assert insert_id == last_id + 1
    return insert_id


def create_new_user_keypair(user, cur, is_inner=False):
    assert isinstance(user, int)
    assert isinstance(is_inner, bool)
    # raise if unknown user_id
    read_user2name(user, cur)
    # get last_index
    last_index = get_keypair_last_index(user=user, is_inner=is_inner, cur=cur)
    bip = extract_keypair(user=user, is_inner=is_inner, index=last_index, cur=cur)
    ck = bip.get_address(hrp=V.BECH32_HRP, ver=C.ADDR_NORMAL_VER)
    insert_keypair_from_bip(ck=ck, user=user, is_inner=is_inner, index=last_index, cur=cur)
    log.debug("generate new address {} path={}".format(ck, bip.path))
    return ck


def message2signature(raw, address):
    # sign by address
    with create_db(V.DB_ACCOUNT_PATH) as db:
        cur = db.cursor()
        uuid, keypair, _ = read_address2keypair(address, cur)
    r, s = keypair.get_single_sign(raw)
    pk = keypair.get_public_key()
    return pk, r, s


def extract_keypair(user, is_inner, index, cur):
    # change: 0=outer、1=inner
    assert isinstance(user, int)
    if V.EXTENDED_KEY_OBJ is None or V.EXTENDED_KEY_OBJ.secret is None:
        # cannot get child key from public extracted key
        d = cur.execute("SELECT `extended_key` FROM `account` WHERE `id`=?", user).fetchone()
        if d is None:
            raise BlockChainError('Not found user id={}'.format(user))
        bip = Bip32.from_extended_key(key=d[0], is_public=True)
    else:
        bip = V.EXTENDED_KEY_OBJ
    return bip.child_key(user + BIP32_HARDEN).child_key(int(is_inner)).child_key(index)


class MoveLog(object):
    __slots__ = ("txhash", "type", "movement", "time", "tx_ref")

    def __init__(self, txhash, _type, movement, _time, tx=None):
        self.txhash = txhash
        self.type = _type
        self.movement = movement
        self.time = _time
        self.tx_ref = ref(tx) if tx else None

    def __repr__(self):
        return "<MoveLog {} {}>".format(C.txtype2name.get(self.type, None), self.txhash.hex())

    def __hash__(self):
        return hash(self.txhash)

    def get_dict_data(self, recode_flag, outer_cur=None):
        with create_db(V.DB_ACCOUNT_PATH) as db:
            cur = outer_cur or db.cursor()
            movement = {read_user2name(user, cur): dict(balance) for user, balance in self.movement.items()}
        return {
            'txhash': self.txhash.hex(),
            'height': self.height,
            'recode_flag': recode_flag,
            'type': C.txtype2name.get(self.type, None),
            'movement': movement,
            'time': self.time + V.BLOCK_GENESIS_TIME
        }

    def get_tuple_data(self):
        return self.type, self.movement, self.time

    @property
    def height(self):
        if not self.tx_ref:
            return None
        try:
            return self.tx_ref().height
        except Exception:
            return None


__all__ = [
    "read_txhash2log",
    "read_log_iter",
    "insert_log",
    "delete_log",
    "read_address2keypair",
    "read_address2user",
    "insert_keypair_from_bip",
    "insert_keypair_from_outside",
    "get_keypair_last_index",
    "read_account_info",
    "read_pooled_address_iter",
    "read_address2account",
    "read_name2user",
    "read_user2name",
    "create_account",
    "create_new_user_keypair",
    "message2signature",
    "extract_keypair",
    "MoveLog",
]
