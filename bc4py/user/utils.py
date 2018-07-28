#!/user/env python3
# -*- coding: utf-8 -*-

from bc4py.config import V, BlockChainError
from bc4py.database.create import closing, create_db
from bc4py.database.account import read_address2keypair, read_address2user
from bc4py.database.tools import get_validator_info
from nem_ed25519.signature import sign


def message2signature(raw, address):
    # sign by address
    with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
        cur = db.cursor()
        uuid, sk, pk = read_address2keypair(address, cur)
    if sk is None:
        raise BlockChainError('Not found address {}'.format(address))
    return pk, sign(msg=raw, sk=sk, pk=pk)


def im_a_validator(best_block=None):
    validator_cks, required_num = get_validator_info(best_block)
    with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
        cur = db.cursor()
        for address in validator_cks:
            if read_address2user(address, cur):
                return address
    return None
