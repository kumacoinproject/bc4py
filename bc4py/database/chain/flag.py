#!/user/env python3
# -*- coding: utf-8 -*-

"""
BlockChainに関して、boolのみ返す
"""

from bc4py.config import BlockChainError
from binascii import hexlify


def is_used_txindex(txhash, txindex, cur):
    d = cur.execute("""
        SELECT `used_index` FROM `tx` WHERE `hash`=?
        """, (txhash,)).fetchone()
    if d is None:
        raise BlockChainError('Not found tx {}'.format(hexlify(txhash).decode()))
    return txindex in d[0]


def is_include_txhash(txhash, cur):
    d = cur.execute("""
        SELECT `used_index` FROM `tx` WHERE `hash`=?
        """, (txhash,)).fetchone()
    if d is None:
        return False
    return True


def is_include_blockhash(blockhash, cur):
    d = cur.execute("""
        SELECT `hash` FROM `block` WHERE `hash`=?
        """, (blockhash,)).fetchone()
    if d is None:
        return False
    return True


def is_unconfirmed_tx(txhash, cur):
    d = cur.execute("""SELECT `height` FROM `tx` WHERE `hash`=?
        """, (txhash,)).fetchone()
    if d is None:
        raise BlockChainError('Not found tx {}'.format(hexlify(txhash).decode()))
    height = d[0]
    if height is None:
        return True
    return False
