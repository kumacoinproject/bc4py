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


"""
accounting methods
"""


def read_txhash2movelog(txhash, cur):
    """read MoveLog by txhash"""
    d = cur.execute("""
        SELECT `type`,`user`,`coin_id`,`amount`,`time` FROM `log` WHERE `hash`=?
    """, (txhash,)).fetchall()
    if len(d) == 0:
        return None
    movement = Accounting()
    ntype = ntime = None
    for ntype, user, coin_id, amount, ntime in d:
        movement[user][coin_id] += amount
    return MoveLog(txhash, ntype, movement, ntime)


def read_movelog_iter(cur, start=0):
    """iterate all MoveLogs"""
    d = cur.execute("SELECT DISTINCT `hash` FROM `log` ORDER BY `id` DESC").fetchall()
    c = 0
    for (txhash,) in d:
        if start <= c:
            yield read_txhash2movelog(txhash, cur)
        c += 1


def insert_movelog(movements, cur, ntype=None, ntime=None, txhash=None):
    """recode account balance movement"""
    assert isinstance(movements, Accounting), 'movements is Accounting'
    ntype = ntype or C.TX_INNER
    ntime = ntime or int(time() - V.BLOCK_GENESIS_TIME)
    txhash = txhash or (b'\x00' * 24 + ntime.to_bytes(4, 'big') + os.urandom(4))
    move = list()
    index = 0
    for user, coins in movements.items():
        for coin_id, amount in coins:
            move.append((txhash, index, ntype, user, coin_id, amount, ntime))
            index += 1
    cur.executemany(
        """INSERT INTO `log` (`hash`,`index`,`type`,`user`,`coin_id`,
    `amount`,`time`) VALUES (?,?,?,?,?,?,?)""", move)
    return txhash


def delete_movelog(txhash, cur):
    """delete account balance movement"""
    cur.execute("DELETE FROM `log` WHERE `hash`=?", (txhash,))


def read_address2keypair(address, cur):
    """get keypair by address or raise exception"""
    if V.EXTENDED_KEY_OBJ is None or V.EXTENDED_KEY_OBJ.secret is None:
        raise BlockChainError('You try to get keypair but secret extended key not found')
    d = cur.execute("""
        SELECT `id`,`sk`,`user`,`is_inner`,`index` FROM `pool` WHERE `ck`=?
    """, (address,)).fetchone()
    if d is None:
        raise BlockChainError('Not found address {}'.format(address))
    uuid, sk, user, is_inner, index = d
    if sk is None:
        bip = read_bip_from_path(user=user, is_inner=is_inner, index=index, cur=cur)
        sk = bip.get_private_key()
        path = bip.path
    else:
        sk = AESCipher.decrypt(key=V.EXTENDED_KEY_OBJ.get_secret_key(), enc=sk)
        path = None
    keypair: PyKeyPair = PyKeyPair.from_secret_key(sk)
    return uuid, keypair, path


def read_address2userid(address, cur):
    """get userid by address"""
    user = cur.execute("SELECT `user` FROM `pool` WHERE `ck`=?", (address,)).fetchone()
    if user is None:
        return None
    return user[0]


def insert_keypair_from_bip32(ck, user, is_inner, index, cur):
    """recode keypair by generated from BIP fnc"""
    assert isinstance(ck, str)
    assert isinstance(user, int)
    assert isinstance(is_inner, bool)
    assert isinstance(index, int)
    cur.execute(
        """
    INSERT OR IGNORE INTO `pool` (`ck`,`user`,`is_inner`,`index`,`time`) VALUES (?,?,?,?,?)
    """, (ck, user, int(is_inner), index, int(time())))


def insert_keypair_from_outside(sk, ck, user, cur):
    """recode keypair by generated from user's action"""
    assert isinstance(sk, bytes)
    assert isinstance(ck, str)
    assert isinstance(user, int)
    if V.EXTENDED_KEY_OBJ is None or V.EXTENDED_KEY_OBJ.secret is None:
        raise BlockChainError('You try to insert keypair but secret extended key not found')
    sk = AESCipher.encrypt(key=V.EXTENDED_KEY_OBJ.get_secret_key(), raw=sk)
    cur.execute("""
    INSERT OR IGNORE INTO `pool` (`sk`,`ck`,`user`,`time`) VALUES (?,?,?,?)
    """, (sk, ck, user, int(time())))


def read_keypair_last_index(user, is_inner, cur):
    """get last recoded address index"""
    assert isinstance(user, int) and isinstance(is_inner, bool)
    index = cur.execute("""
    SELECT MAX(`index`) FROM `pool` WHERE `user`=? AND `is_inner`=?
    """, (user, int(is_inner))).fetchone()
    if index is None:
        return 0
    elif index[0] is None:
        return 0
    else:
        return index[0] + 1


def read_account_info(user, cur):
    """read account info (username, description, time)"""
    d = cur.execute("""
        SELECT `name`,`description`,`time` FROM `account` WHERE `id`=?
    """, (user,)).fetchone()
    if d is None:
        return None
    name, description, ntime = d
    return name, description, ntime


def read_pooled_address_iter(cur):
    """iterate pooled addresses"""
    cur.execute("SELECT `id`,`ck`,`user` FROM `pool`")
    return cur


def read_address2account(address, cur):
    """read account by address or raise exception"""
    user = read_address2userid(address, cur)
    if user is None:
        raise BlockChainError('Not found account {}'.format(address))
    return read_account_info(user, cur)


def read_name2userid(name, cur):
    """read userid from name"""
    assert isinstance(name, str)
    d = cur.execute("SELECT `id` FROM `account` WHERE `name`=?", (name,)).fetchone()
    if d is None:
        return insert_new_account(name, cur)
    return d[0]


def read_userid2name(user, cur):
    """read name from userid"""
    assert isinstance(user, int)
    d = cur.execute("SELECT `name` FROM `account` WHERE `id`=?", (user,)).fetchone()
    if d is None:
        raise Exception('Not found user id. {}'.format(user))
    return d[0]


def insert_new_account(name, cur, description="", ntime=None):
    """create new account by name"""
    assert isinstance(name, str)
    if name.startswith('@'):
        raise BlockChainError('prefix"@" is root user, name={}'.format(name))
    ntime = ntime or int(time() - V.BLOCK_GENESIS_TIME)
    # get extend public key
    if V.EXTENDED_KEY_OBJ is None or V.EXTENDED_KEY_OBJ.secret is None:
        raise BlockChainError('you try to create account but not found secretKey')
    # get new account id
    last_id = cur.execute("SELECT MAX(`id`) FROM `account`").fetchone()
    new_id = 0 if (last_id is None or last_id[0] is None) else last_id[0] + 1
    # get extended public key
    extended_key = V.EXTENDED_KEY_OBJ.child_key(BIP32_HARDEN + new_id).extended_key(False)
    cur.execute("""
        INSERT INTO `account` (`name`,`extended_key`,`description`,`time`) VALUES (?,?,?,?)
    """, (name, extended_key, description, ntime))
    # check new inserted id
    insert_id = cur.execute("SELECT last_insert_rowid()").fetchone()[0]
    assert insert_id == new_id, "insert={} new={}".format(insert_id, new_id)
    return insert_id


def generate_new_address_by_userid(user, cur, is_inner=False):
    """insert new address by userid"""
    assert isinstance(user, int)
    assert isinstance(is_inner, bool)
    # raise if unknown user_id
    read_userid2name(user, cur)
    # get last_index
    last_index = read_keypair_last_index(user=user, is_inner=is_inner, cur=cur)
    bip = read_bip_from_path(user=user, is_inner=is_inner, index=last_index, cur=cur)
    ck = bip.get_address(hrp=V.BECH32_HRP, ver=C.ADDR_NORMAL_VER)
    insert_keypair_from_bip32(ck=ck, user=user, is_inner=is_inner, index=last_index, cur=cur)
    log.debug("generate new address {} path={}".format(ck, bip.path))
    return ck


def sign_message_by_address(raw, address):
    """sign raw bytes by address"""
    with create_db(V.DB_ACCOUNT_PATH) as db:
        cur = db.cursor()
        uuid, keypair, _ = read_address2keypair(address, cur)
    r, s = keypair.get_single_sign(raw)
    pk = keypair.get_public_key()
    return pk, r, s


def read_bip_from_path(user, is_inner, index, cur):
    """read bip from path (m/44'/CoinType'/user'/is_inner/index) """
    # change: 0=outer、1=inner
    assert isinstance(user, int)
    assert isinstance(is_inner, bool) or is_inner == 0 or is_inner == 1
    if V.EXTENDED_KEY_OBJ is None or V.EXTENDED_KEY_OBJ.secret is None:
        # cannot get child key from public extracted key
        d = cur.execute("SELECT `extended_key` FROM `account` WHERE `id`=?", user).fetchone()
        if d is None:
            raise BlockChainError('Not found user id={}'.format(user))
        bip = Bip32.from_extended_key(key=d[0], is_public=True)
    else:
        bip = V.EXTENDED_KEY_OBJ.child_key(user + BIP32_HARDEN)
    return bip.child_key(int(is_inner)).child_key(index)


class MoveLog(object):
    __slots__ = ("txhash", "type", "movement", "time", "tx_ref")

    def __init__(self, txhash, ntype, movement, ntime, tx=None):
        self.txhash = txhash
        self.type = ntype
        self.movement = movement
        self.time = ntime
        self.tx_ref = ref(tx) if tx else None

    def __repr__(self):
        return "<MoveLog {} {}>".format(C.txtype2name.get(self.type, None), self.txhash.hex())

    def __hash__(self):
        return hash(self.txhash)

    def get_dict_data(self, recode_flag, outer_cur=None):
        with create_db(V.DB_ACCOUNT_PATH) as db:
            cur = outer_cur or db.cursor()
            movement = {read_userid2name(user, cur): dict(balance) for user, balance in self.movement.items()}
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
    "read_txhash2movelog",
    "read_movelog_iter",
    "insert_movelog",
    "delete_movelog",
    "read_address2keypair",
    "read_address2userid",
    "insert_keypair_from_bip32",
    "insert_keypair_from_outside",
    "read_keypair_last_index",
    "read_account_info",
    "read_pooled_address_iter",
    "read_address2account",
    "read_name2userid",
    "read_userid2name",
    "insert_new_account",
    "generate_new_address_by_userid",
    "sign_message_by_address",
    "read_bip_from_path",
    "MoveLog",
]
