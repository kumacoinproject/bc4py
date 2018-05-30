#!/user/env python3
# -*- coding: utf-8 -*-

"""
Accountに関して、boolのみ返す
"""

from bc4py.config import V
from bc4py.utils import AESCipher
from nem_ed25519.key import public_key
from binascii import hexlify


def is_my_address(address, cur):
    d = cur.execute("""
            SELECT `group` FROM `pool` WHERE `ck`=?
            """, (address,)).fetchone()
    if d is None:
        return False
    return True


def is_include_to_log(txhash, direction, txindex, cur):
    d = cur.execute("""
        SELECT `direction`,`index` FROM `log` WHERE `hash`=?
        """, (txhash,))
    if direction is None and txindex is None:
        if d.fetchone() is None:
            return False
        return True

    for _direction, _index in d:
        if direction == _direction and txindex == _index:
            return True
    return False


def is_include_utxo(txhash, txindex, cur):
    d = cur.execute("""
    SELECT `used` FROM `utxo` WHERE `hash`=? AND `index`=?
    """, (txhash, txindex)).fetchone()
    if d is None:
        return False
    return True


def is_exist_group(group, cur):
    d = cur.execute("""
        SELECT `group` FROM `balance` WHERE `group`=?
        """, (group,)).fetchone()
    if d is None:
        return False
    return True


def is_locked_database(cur):
    d = cur.execute("SELECT `sk`,`pk` FROM `pool` LIMIT 1").fetchone()
    if d is None:
        return False  # Unlocked
    sk, pk = d
    try:
        sk = AESCipher.decrypt(V.ENCRYPT_KEY, sk) if V.ENCRYPT_KEY else sk
        sk = hexlify(sk).decode()
    except ValueError:
        return True
    if len(sk) != 64:
        return True
    elif public_key(sk) == hexlify(pk).decode():
        return False  # Unlocked
    else:
        return True
