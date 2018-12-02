from bc4py.config import C
from bc4py.database.builder import builder, tx_builder
from expiringdict import ExpiringDict
import bjson
from binascii import hexlify
from collections import OrderedDict

F_ADD = 1
F_REMOVE = -1
F_NOP = 0

cashe = ExpiringDict(max_len=100, max_age_seconds=1800)


class Validator:
    def __init__(self, c_address):
        self.c_address = c_address
        self.validators = list()
        self.require = 0
        self.index = -1
        self.txhash = None

    def __repr__(self):
        return "<Validator {} ver={} {}/{}>".format(
            self.c_address, self.index, self.require, len(self.validators))

    def update(self, flag, address, sig_diff, txhash):
        # cosigner
        if flag == F_ADD:
            self.validators.append(address)
        elif flag == F_REMOVE:
            self.validators.remove(address)
        else:
            pass
        self.require += sig_diff
        self.index += 1
        self.txhash = txhash

    @property
    def info(self):
        if self.index == -1:
            return None
        d = OrderedDict()
        d['index'] = self.index
        d['c_address'] = self.c_address
        d['txhash'] = hexlify(self.txhash).decode()
        d['validators'] = self.validators
        d['require'] = self.require
        return d


def decode(msg):
    # [c_address]-[new_address]-[flag]-[sig_diff]
    return bjson.loads(msg)


def encode(*args):
    assert len(args) == 4
    return bjson.dumps(args, compress=False)


def validator_fill(v: Validator, best_block=None, best_chain=None, stop_txhash=None):
    assert v.index == -1, 'Already updated'
    # database
    for index, address, flag, txhash, sig_diff in builder.db.read_validator_iter(c_address=v.c_address):
        if txhash == stop_txhash:
            return
        v.update(flag=flag, address=address, sig_diff=sig_diff, txhash=txhash)
    # memory
    if best_chain:
        _best_chain = None
    elif best_block and best_block == builder.best_block:
        _best_chain = builder.best_chain
    else:
        dummy, _best_chain = builder.get_best_chain(best_block=best_block)
    for block in reversed(best_chain or _best_chain):
        for tx in block.txs:
            if tx.hash == stop_txhash:
                return
            if tx.type != C.TX_VALIDATOR_EDIT:
                continue
            c_address, address, flag, sig_diff = decode(tx.message)
            if c_address != v.c_address:
                continue
            v.update(flag=flag, address=address, sig_diff=sig_diff, txhash=tx.hash)
    # unconfirmed
    if best_block is None:
        for tx in sorted(tx_builder.unconfirmed.values(), key=lambda x: x.time):
            if tx.hash == stop_txhash:
                return
            if tx.type != C.TX_VALIDATOR_EDIT:
                continue
            c_address, address, flag, sig_diff = decode(tx.message)
            if c_address != v.c_address:
                continue
            v.update(flag=flag, address=address, sig_diff=sig_diff, txhash=tx.hash)


def get_validator_object(c_address, best_block=None, best_chain=None, stop_txhash=None):
    if best_block:
        key = (best_block.hash, stop_txhash)
        if key in cashe:
            return cashe[key]
    else:
        key = None
    v = Validator(c_address=c_address)
    validator_fill(v=v, best_block=best_block, best_chain=best_chain, stop_txhash=stop_txhash)
    if key:
        cashe[key] = v
    return v


__all__ = [
    "F_ADD", "F_REMOVE", "F_NOP",
    "Validator",
    "validator_fill",
    "get_validator_object",
]
