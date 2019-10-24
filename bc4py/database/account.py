from bc4py.config import C, V, BlockChainError
from bc4py.bip32 import Bip32, BIP32_HARDEN
from bc4py.user import Accounting
from bc4py.utils import AESCipher
from bc4py_extension import PyAddress
from multi_party_schnorr import PyKeyPair
from typing import List, Set
from weakref import ref
from logging import getLogger
from aiosqlite import Cursor
from time import time
import os


log = getLogger('bc4py')


"""
accounting methods
"""


async def read_txhash2movelog(txhash, cur: Cursor):
    """read MoveLog by txhash"""
    await cur.execute("""
        SELECT `type`,`user`,`coin_id`,`amount`,`time` FROM `log` WHERE `hash`=?
    """, (txhash,))
    data = tuple(await cur.fetchall())
    if len(data) == 0:
        return None
    movement = Accounting()
    ntype = ntime = None
    for ntype, user, coin_id, amount, ntime in data:
        movement[user][coin_id] += amount
    return MoveLog(txhash, ntype, movement, ntime)


async def read_movelog_iter(cur: Cursor, start=0):
    """iterate all MoveLogs"""
    await cur.execute("SELECT DISTINCT `hash` FROM `log` ORDER BY `id` DESC")
    c = 0
    for (txhash,) in await cur.fetchall():
        if start <= c:
            yield await read_txhash2movelog(txhash, cur)
        c += 1


async def insert_movelog(movements, cur: Cursor, ntype=None, ntime=None, txhash=None):
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
    await cur.executemany(
        """INSERT INTO `log` (`hash`,`index`,`type`,`user`,`coin_id`,
    `amount`,`time`) VALUES (?,?,?,?,?,?,?)""", move)
    return txhash


async def delete_movelog(txhash, cur: Cursor):
    """delete account balance movement"""
    await cur.execute("DELETE FROM `log` WHERE `hash`=?", (txhash,))


async def read_address2keypair(address: PyAddress, cur: Cursor):
    """get keypair by address or raise exception"""
    if V.EXTENDED_KEY_OBJ is None or V.EXTENDED_KEY_OBJ.secret is None:
        raise BlockChainError('You try to get keypair but secret extended key not found')
    await cur.execute("""
        SELECT `id`,`sk`,`user`,`is_inner`,`index` FROM `pool` WHERE `ck`=?
    """, (address.binary(),))
    data = await cur.fetchone()
    if data is None:
        raise BlockChainError('Not found address {}'.format(address))
    uuid, sk, user, is_inner, index = data
    if sk is None:
        bip = await read_bip_from_path(user=user, is_inner=is_inner, index=index, cur=cur)
        sk = bip.get_private_key()
        path = bip.path
    else:
        sk = AESCipher.decrypt(key=V.EXTENDED_KEY_OBJ.get_private_key(), enc=sk)
        path = None
    keypair: PyKeyPair = PyKeyPair.from_secret_key(sk)
    return uuid, keypair, path


async def read_address2userid(address: PyAddress, cur: Cursor):
    """get userid by address"""
    await cur.execute("SELECT `user` FROM `pool` WHERE `ck`=?",
                      (address.binary(),))
    user = await cur.fetchone()
    if user is None:
        return None
    return user[0]


async def insert_keypair_from_bip32(ck, user, is_inner, index, cur: Cursor):
    """recode keypair by generated from BIP fnc"""
    assert isinstance(ck, PyAddress)
    assert isinstance(user, int)
    assert isinstance(is_inner, bool)
    assert isinstance(index, int)
    await cur.execute("""
    INSERT OR IGNORE INTO `pool`
    (`ck`,`user`,`is_inner`,`index`,`time`) VALUES (?,?,?,?,?)
    """, (ck.binary(), user, int(is_inner), index, int(time())))


async def insert_keypair_from_outside(sk, ck, user, cur: Cursor):
    """recode keypair by generated from user's action"""
    assert isinstance(sk, bytes)
    assert isinstance(ck, PyAddress)
    assert isinstance(user, int)
    if V.EXTENDED_KEY_OBJ is None or V.EXTENDED_KEY_OBJ.secret is None:
        raise BlockChainError('You try to insert keypair but secret extended key not found')
    sk = AESCipher.encrypt(key=V.EXTENDED_KEY_OBJ.get_private_key(), raw=sk)
    await cur.execute("""
    INSERT OR IGNORE INTO `pool`
    (`sk`,`ck`,`user`,`time`) VALUES (?,?,?,?)
    """, (sk, ck.binary(), user, int(time())))


async def read_keypair_last_index(user, is_inner, cur: Cursor):
    """get last recoded address index"""
    assert isinstance(user, int) and isinstance(is_inner, bool)
    await cur.execute("""
    SELECT MAX(`index`) FROM `pool` WHERE `user`=? AND `is_inner`=?
    """, (user, int(is_inner)))
    index = (await cur.fetchone())[0]
    if index is None:
        return 0
    else:
        return index + 1


async def read_account_info(user, cur: Cursor):
    """read account info (username, description, time)"""
    await cur.execute("""
        SELECT `name`,`description`,`time` FROM `account` WHERE `id`=?
    """, (user,))
    data = await cur.fetchone()
    if data is None:
        return None
    name, description, ntime = data
    return name, description, ntime


async def read_pooled_address_list(user, cur: Cursor) -> List[PyAddress]:
    """get pooled address list"""
    assert isinstance(user, int)
    await cur.execute("SELECT `ck` FROM `pool` WHERE `user`=?", (user,))
    return [PyAddress.from_binary(V.BECH32_HRP, ck) for (ck,) in await cur.fetchall()]


async def read_all_pooled_address_set(cur: Cursor, last_uuid=0) -> Set[PyAddress]:
    """get all pooled address"""
    await cur.execute("SELECT `ck` FROM `pool` WHERE ?<`id`", (last_uuid,))
    return {PyAddress.from_binary(V.BECH32_HRP, ck) for (ck,) in await cur.fetchall()}


async def read_address2account(address: PyAddress, cur: Cursor):
    """read account by address or raise exception"""
    user = await read_address2userid(address, cur)
    if user is None:
        raise BlockChainError('Not found account {}'.format(address))
    return await read_account_info(user, cur)


async def read_name2userid(name, cur: Cursor):
    """read userid from name"""
    assert isinstance(name, str)
    await cur.execute("SELECT `id` FROM `account` WHERE `name`=?", (name,))
    data = await cur.fetchone()
    if data is None:
        return await insert_new_account(name, cur)
    return data[0]


async def read_userid2name(user, cur: Cursor):
    """read name from userid"""
    assert isinstance(user, int)
    await cur.execute("SELECT `name` FROM `account` WHERE `id`=?", (user,))
    data = await cur.fetchone()
    if data is None:
        raise Exception('Not found user id. {}'.format(user))
    return data[0]


async def insert_new_account(name, cur: Cursor, description="", ntime=None):
    """create new account by name"""
    assert isinstance(name, str)
    if name.startswith('@'):
        raise BlockChainError('prefix"@" is root user, name={}'.format(name))
    ntime = ntime or int(time() - V.BLOCK_GENESIS_TIME)
    # get extend public key
    if V.EXTENDED_KEY_OBJ is None or V.EXTENDED_KEY_OBJ.secret is None:
        raise BlockChainError('you try to create account but not found secretKey')
    # get new account id
    await cur.execute("SELECT MAX(`id`) FROM `account`")
    last_id = (await cur.fetchone())[0]
    new_id = 0 if last_id is None else last_id + 1
    # get extended public key
    extended_key = V.EXTENDED_KEY_OBJ.child_key(BIP32_HARDEN + new_id).extended_key(False)
    await cur.execute("""
        INSERT INTO `account`
        (`name`,`extended_key`,`description`,`time`) VALUES (?,?,?,?)
    """, (name, extended_key, description, ntime))
    # check new inserted id
    insert_id = cur.lastrowid
    assert insert_id == new_id, "insert={} new={}".format(insert_id, new_id)
    return insert_id


async def generate_new_address_by_userid(user, cur: Cursor, is_inner=False) -> PyAddress:
    """insert new address by userid"""
    assert isinstance(user, int)
    assert isinstance(is_inner, bool)
    # raise if unknown user_id
    await read_userid2name(user, cur)
    # get last_index
    last_index = await read_keypair_last_index(user=user, is_inner=is_inner, cur=cur)
    bip = await read_bip_from_path(user=user, is_inner=is_inner, index=last_index, cur=cur)
    ck = bip.get_address(hrp=V.BECH32_HRP, ver=C.ADDR_NORMAL_VER)
    await insert_keypair_from_bip32(ck=ck, user=user, is_inner=is_inner, index=last_index, cur=cur)
    log.debug("generate new address {} path={}".format(ck, bip.path))
    return ck


async def read_account_address(user, cur: Cursor, is_inner=False) -> PyAddress:
    """get newest address of account (don't care about used/unused)"""
    assert isinstance(user, int) and isinstance(is_inner, bool)
    # raise if unknown user_id
    await read_userid2name(user, cur)
    # get last_index
    await cur.execute("""
        SELECT MAX(`index`) FROM `pool` WHERE `user`=? AND `is_inner`=?
        """, (user, int(is_inner)))
    index = (await cur.fetchone())[0]
    if index is None:
        return await generate_new_address_by_userid(user=user, cur=cur, is_inner=is_inner)
    else:
        bip = await read_bip_from_path(user=user, is_inner=is_inner, index=index, cur=cur)
        return bip.get_address(hrp=V.BECH32_HRP, ver=C.ADDR_NORMAL_VER)


async def sign_message_by_address(raw, address: PyAddress, cur: Cursor):
    """sign raw bytes by address"""
    uuid, keypair, _ = await read_address2keypair(address, cur)
    r, s = keypair.get_single_sign(raw)
    pk = keypair.get_public_key()
    return pk, r, s


async def read_bip_from_path(user, is_inner, index, cur: Cursor):
    """read bip from path (m/44'/CoinType'/user'/is_inner/index) """
    # change: 0=outer、1=inner
    assert isinstance(user, int)
    assert isinstance(is_inner, bool) or is_inner == 0 or is_inner == 1
    if V.EXTENDED_KEY_OBJ is None or V.EXTENDED_KEY_OBJ.secret is None:
        # cannot get child key from public extracted key
        await cur.execute("SELECT `extended_key` FROM `account` WHERE `id`=?", user)
        data = await cur.fetchone()
        if data is None:
            raise BlockChainError('Not found user id={}'.format(user))
        bip = Bip32.from_extended_key(key=data[0], is_public=True)
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

    async def get_dict_data(self, cur: Cursor, recode_flag=None):
        movement = {
            await read_userid2name(user, cur): dict(balance)
            for user, balance in self.movement.items()
        }
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
    "read_pooled_address_list",
    "read_all_pooled_address_set",
    "read_address2account",
    "read_name2userid",
    "read_userid2name",
    "insert_new_account",
    "generate_new_address_by_userid",
    "read_account_address",
    "sign_message_by_address",
    "read_bip_from_path",
    "MoveLog",
]
