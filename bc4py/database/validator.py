from bc4py.config import C, V, stream, BlockChainError
from bc4py.bip32 import is_address
from bc4py.chain.block import Block
from bc4py.database.builder import builder, tx_builder
from bc4py.database.cashe import Cashe
from copy import deepcopy
from logging import getLogger
from time import time
import msgpack

log = getLogger('bc4py')

F_ADD = 1
F_REMOVE = -1
F_NOP = 0


class Validator(object):
    __slots__ = ("v_address", "validators", "require", "db_index", "version", "txhash")

    def __init__(self, v_address):
        assert is_address(ck=v_address, hrp=V.BECH32_HRP, ver=C.ADDR_VALIDATOR_VER)
        self.v_address = v_address
        self.validators = list()
        self.require = 0
        self.db_index = None
        self.version = -1
        self.txhash = None

    def __repr__(self):
        return "<Validator {} ver={} {}/{}>".format(self.v_address, self.version, self.require,
                                                    len(self.validators))

    def copy(self):
        return deepcopy(self)

    def update(self, db_index, flag, address, sig_diff, txhash):
        # DO NOT RAISE ERROR
        # cosigner
        if flag == F_ADD:
            if address not in self.validators:
                self.validators.append(address)
        elif flag == F_REMOVE:
            if address in self.validators:
                self.validators.remove(address)
        else:
            pass
        # 0 < new_sig_diff =< len(validators)
        new_sig_diff = self.require + sig_diff
        self.require = max(1, min(len(self.validators), new_sig_diff))
        self.db_index = db_index
        self.version += 1
        self.txhash = txhash

    @property
    def info(self):
        if self.version == -1:
            return None
        else:
            return {
                'db_index': self.db_index,
                'index': self.version,
                'v_address': self.v_address,
                'txhash': self.txhash.hex(),
                'validators': self.validators,
                'require': self.require,
            }

    def serialize(self):
        return self.v_address, self.validators, self.require, self.db_index, self.version, self.txhash

    @classmethod
    def deserialize(cls, args):
        v_address, validators, require, db_index, version, txhash = args
        self = cls(v_address=v_address)
        self.validators = validators
        self.require = require
        self.db_index = db_index
        self.version = version
        self.txhash = txhash
        return self


# cashe Validator, only store database side (not memory, not unconfirmed)
cashe = Cashe(path='cashe.validator.dat', default=Validator)


def decode(b):
    # [v_address]-[new_address]-[flag]-[sig_diff]
    return msgpack.unpackb(b, raw=True, encoding='utf8')


def encode(*args):
    assert len(args) == 4
    return msgpack.packb(args, use_bin_type=True)


def validator_fill_iter(v: Validator, best_block=None, best_chain=None):
    # database
    v_iter = builder.db.read_validator_iter(v_address=v.v_address, start_idx=v.db_index)
    for index, address, flag, txhash, sig_diff in v_iter:
        yield index, flag, address, sig_diff, txhash
    # memory
    if best_chain:
        _best_chain = None
    elif best_block and best_block == builder.best_block:
        _best_chain = builder.best_chain
    else:
        dummy, _best_chain = builder.get_best_chain(best_block=best_block)
    for block in reversed(best_chain or _best_chain):
        for tx in block.txs:
            if tx.type != C.TX_VALIDATOR_EDIT:
                continue
            v_address, address, flag, sig_diff = decode(tx.message)
            if v_address != v.v_address:
                continue
            index = block.height * 0xffffffff + block.txs.index(tx)
            yield index, flag, address, sig_diff, tx.hash
    # unconfirmed
    if best_block is None:
        for tx in sorted(tx_builder.unconfirmed.values(), key=lambda x: x.create_time):
            if tx.type != C.TX_VALIDATOR_EDIT:
                continue
            v_address, address, flag, sig_diff = decode(tx.message)
            if v_address != v.v_address:
                continue
            if len(tx.signature) < v.require:
                continue
            yield None, flag, address, sig_diff, tx.hash


def get_validator_object(v_address, best_block=None, best_chain=None, stop_txhash=None, select_hash=None):
    v = cashe.get(v_address)
    for index, flag, address, sig_diff, txhash in validator_fill_iter(
            v=v, best_block=best_block, best_chain=best_chain):
        if txhash == stop_txhash:
            return v
        v.update(db_index=index, flag=flag, address=address, sig_diff=sig_diff, txhash=txhash)
        if txhash == select_hash:
            return v  # caution: select_hash works only on memory/unconfirmed!
    if select_hash:
        raise BlockChainError('Failed get Validator by select_hash {}'.format(select_hash.hex()))
    # elif stop_txhash:
    #    raise BlockChainError('Failed get Validator by stop_txhash {}'.format(hexlify(stop_txhash)))
    else:
        return v


def validator_tx2index(txhash=None, tx=None):
    if txhash:
        tx = tx_builder.get_tx(txhash=txhash)
    if tx is None:
        raise BlockChainError('Not found ValidatorTX {}'.format(tx))
    if tx.height is None:
        raise BlockChainError('Not confirmed ValidatorTX {}'.format(tx))
    block = builder.get_block(height=tx.height)
    if block is None:
        raise BlockChainError('Not found block of start_tx included? {}'.format(tx))
    if tx not in block.txs:
        raise BlockChainError('Not found start_tx in block? {}'.format(block))
    return tx.height * 0xffffffff + block.txs.index(tx)


def update_validator_cashe(*args):
    s = time()
    line = 0
    for v_address, v in cashe:
        v_iter = builder.db.read_validator_iter(v_address=v_address, start_idx=v.db_index)
        for index, address, flag, txhash, sig_diff in v_iter:
            v.update(db_index=index, flag=flag, address=address, sig_diff=sig_diff, txhash=txhash)
            line += 1
    log.debug("Validator cashe update {}line {}mSec".format(line, int((time() - s) * 1000)))


# when receive Block (101 x n height), update validator cashe
stream.filter(lambda obj: isinstance(obj, Block) and obj.height % 101 == 0).subscribe(
    on_next=update_validator_cashe, on_error=log.error)

__all__ = [
    "F_ADD",
    "F_REMOVE",
    "F_NOP",
    "Validator",
    "validator_fill_iter",
    "get_validator_object",
    "validator_tx2index",
]
