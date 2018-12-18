from bc4py.config import C, BlockChainError
from bc4py.database.builder import builder, tx_builder
from binascii import hexlify
from collections import OrderedDict
from threading import Lock
from copy import deepcopy
import bjson
import logging

F_ADD = 1
F_REMOVE = -1
F_NOP = 0

# cashe Validator, only store database side (not memory, not unconfirmed)
cashe = dict()
lock = Lock()


class Validator:
    __slots__ = ("c_address", "validators", "require", "db_index", "version", "txhash")

    def __init__(self, c_address):
        self.c_address = c_address
        self.validators = list()
        self.require = 0
        self.db_index = None
        self.version = -1
        self.txhash = None

    def __repr__(self):
        return "<Validator {} ver={} {}/{}>".format(
            self.c_address, self.version, self.require, len(self.validators))

    def copy(self):
        return deepcopy(self)

    def update(self, db_index, flag, address, sig_diff, txhash):
        # cosigner
        if flag == F_ADD:
            self.validators.append(address)
        elif flag == F_REMOVE:
            self.validators.remove(address)
        else:
            pass
        self.require += sig_diff
        self.db_index = db_index
        self.version += 1
        self.txhash = txhash

    @property
    def info(self):
        if self.version == -1:
            return None
        d = OrderedDict()
        d['db_index'] = self.db_index
        d['index'] = self.version
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
    # database
    v_iter =  builder.db.read_validator_iter(c_address=v.c_address, start_idx=v.db_index)
    for index, address, flag, txhash, sig_diff in v_iter:
        if txhash == stop_txhash:
            return
        v.update(db_index=index, flag=flag, address=address, sig_diff=sig_diff, txhash=txhash)
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
            index = validator_tx2index(tx=tx)
            v.update(db_index=index, flag=flag, address=address, sig_diff=sig_diff, txhash=tx.hash)
    # unconfirmed
    if best_block is None:
        for tx in sorted(tx_builder.unconfirmed.values(), key=lambda x: x.create_time):
            if tx.hash == stop_txhash:
                return
            if tx.type != C.TX_VALIDATOR_EDIT:
                continue
            c_address, address, flag, sig_diff = decode(tx.message)
            if c_address != v.c_address:
                continue
            if len(tx.signature) < v.require:
                continue
            index = validator_tx2index(tx=tx)
            v.update(db_index=index, flag=flag, address=address, sig_diff=sig_diff, txhash=tx.hash)


def get_validator_object(c_address, best_block=None, best_chain=None, stop_txhash=None):
    if c_address in cashe:
        with lock:
            v = cashe[c_address].copy()
    else:
        v = Validator(c_address=c_address)
    validator_fill(v=v, best_block=best_block, best_chain=best_chain, stop_txhash=stop_txhash)
    return v


def validator_tx2index(txhash=None, tx=None):
    if txhash:
        tx = tx_builder.get_tx(txhash=txhash)
    block = builder.get_block(blockhash=builder.get_block_hash(height=tx.height))
    if block is None:
        raise BlockChainError('Not found block of start_tx included? {}'.format(tx))
    if tx not in block.txs:
        raise BlockChainError('Not found start_tx in block? {}'.format(block))
    return tx.height * 0xffffffff + block.txs.index(tx)


def update_validator_cashe():
    # affect when new blocks inserted to database
    # TODO: when update? 後で考えるので今は触らない
    with lock:
        count = 0
        for c_address, c_validator in cashe.items():
            v_iter = builder.db.read_validator_iter(c_address=c_address, start_idx=c_validator.db_index)
            for index, address, flag, txhash, sig_diff in v_iter:
                c_validator.update(db_index=index, flag=flag,
                                   address=address, sig_diff=sig_diff, txhash=txhash)
                count += 1
    logging.debug("Validator cashe update {}tx".format(count))


__all__ = [
    "F_ADD", "F_REMOVE", "F_NOP",
    "Validator",
    "validator_fill",
    "get_validator_object",
    "validator_tx2index",
]
