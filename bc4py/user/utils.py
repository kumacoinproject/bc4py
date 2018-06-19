#!/user/env python3
# -*- coding: utf-8 -*-

from bc4py.config import V, BlockChainError
from bc4py.database.create import closing, create_db
from bc4py.database.account import read_address2keypair
from nem_ed25519.base import Encryption


def message2signature(raw, address):
    # sign by address
    with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
        cur = db.cursor()
        uuid, sk, pk = read_address2keypair(address, cur)
    if sk is None:
        raise BlockChainError('Not found address {}'.format(address))
    ecc = Encryption()
    ecc.sk, ecc.pk = sk, pk
    return pk, ecc.sign(msg=raw, encode='raw')
