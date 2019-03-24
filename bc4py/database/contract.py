from bc4py.config import C, V, stream, BlockChainError
from bc4py.chain.block import Block
from bc4py.database.builder import builder, tx_builder
from bc4py.database.validator import get_validator_object
from bc4py.database.cashe import Cashe
from copy import deepcopy
from logging import getLogger
from nem_ed25519 import is_address
from time import time
import msgpack

log = getLogger('bc4py')

M_INIT = 'init'
M_UPDATE = 'update'

# default setting of Storage
settings_template = {'update_binary': True, 'update_extra_imports': True}


class Storage(dict):
    __slots__ = ("c_address", "version")

    def __init__(self, c_address=None, init_storage=None):
        super().__init__()
        assert c_address is not None
        # check value is not None
        if init_storage:
            assert isinstance(init_storage, dict)
            self.update(init_storage)
            # check key type
            if len({type(k) for k in init_storage}) > 1:
                raise Exception("All key type is same {}".format([type(k) for k in init_storage]))
        self.c_address = c_address
        self.version = 0

    def __repr__(self):
        return "<Storage of {} ver={} {}>".\
            format(self.c_address, self.version, dict(self.items()))

    def copy(self):
        return deepcopy(self)

    def marge_diff(self, diff):
        if diff is None:
            return  # skip
        for k, v in diff.items():
            if v is None:
                del self[k]
            else:
                self[k] = v
        self.version += 1

    def export_diff(self, original_storage):
        # check value is not None
        for v in self.values():
            if v is None:
                raise Exception('Not allowed None value...')
        diff = dict()
        for key in original_storage.keys() | self.keys():
            if key in original_storage and key in self:
                if original_storage[key] != self[key]:
                    diff[key] = self[key]  # update
            elif key not in original_storage and key in self:
                diff[key] = self[key]  # insert
            elif key in original_storage and key not in self:
                diff[key] = None  # delete
        # check key type
        if len({type(k) for k in diff}) > 1:
            raise Exception("All key type is same {}".format([type(k) for k in diff]))
        return diff

    def serialize(self):
        return self.c_address, self.version, dict(self)

    @classmethod
    def deserialize(cls, args):
        c_address, version, init_storage = args
        self = cls(c_address=c_address, init_storage=init_storage)
        self.version = version
        return self


class Contract:
    __slots__ = ("c_address", "v_address", "version", "db_index", "binary", "extra_imports", "storage",
                 "settings", "start_hash", "finish_hash")

    def __init__(self, c_address):
        assert is_address(c_address, V.BLOCK_CONTRACT_PREFIX)
        self.c_address = c_address
        self.v_address = None
        self.version = -1
        self.db_index = None
        self.binary = None
        self.extra_imports = None
        self.storage = None
        self.settings = None
        self.start_hash = None
        self.finish_hash = None

    def __repr__(self):
        return "<Contract {} ver={} idx={}>" \
            .format(self.c_address, self.version, self.db_index)

    def copy(self):
        return deepcopy(self)

    @property
    def info(self):
        if self.version == -1:
            return None
        return {
            'c_address': self.c_address,
            'v_address': self.v_address,
            'db_index': self.db_index,
            'version': self.version,
            'binary': self.binary.hex(),
            'extra_imports': self.extra_imports,
            'storage_key': len(self.storage),
            'settings': self.settings,
            'start_hash': self.start_hash.hex(),
            'finish_hash': self.finish_hash.hex(),
        }

    def update(self, db_index, start_hash, finish_hash, c_method, c_args, c_storage):
        # DO NOT RAISE ERROR
        assert self.db_index is None or self.db_index < db_index, 'Tyr to put old index data.'
        if c_method == M_INIT:
            assert self.version == -1
            c_bin, v_address, c_extra_imports, c_settings = c_args
            self.binary = c_bin
            self.v_address = v_address
            self.extra_imports = c_extra_imports or list()
            self.settings = settings_template.copy()
            if c_settings:
                self.settings.update(c_settings)
            c_storage = c_storage or dict()
            self.storage = Storage(c_address=self.c_address, init_storage=c_storage)
        elif c_method == M_UPDATE:
            assert self.version != -1
            c_bin, c_extra_imports, c_settings = c_args
            if self.settings['update_binary']:
                self.binary = c_bin
                if c_settings and not c_settings.get('update_binary', False):
                    self.settings['update_binary'] = False
            if self.settings['update_extra_imports']:
                self.extra_imports = c_extra_imports
                if c_settings and not c_settings.get('update_extra_imports', False):
                    self.settings['update_extra_imports'] = False
        else:
            assert self.version != -1
            self.storage.marge_diff(c_storage)
        self.version += 1
        self.db_index = db_index
        self.start_hash = start_hash
        self.finish_hash = finish_hash

    def serialize(self):
        storage = self.storage.serialize() if self.storage else None
        return self.c_address, self.v_address, self.version, self.db_index, self.binary,\
            self.extra_imports, storage, self.settings, self.start_hash, self.finish_hash

    @classmethod
    def deserialize(cls, args):
        self = cls(c_address=args[0])
        self.c_address, self.v_address, self.version, self.db_index, self.binary, self.extra_imports, \
            storage, self.settings, self.start_hash, self.finish_hash = args
        if storage:
            self.storage = Storage.deserialize(storage)
        return self


# cashe Contract (Storage include Contract.storage)
# only store database side (not memory, not unconfirmed)
cashe = Cashe(path='cashe.contract.dat', default=Contract)


def encode(*args):
    assert len(args) == 3
    return msgpack.packb(args, use_bin_type=True)


def decode(b):
    # transfer: [c_address]-[c_method]-[redeem_address]-[c_args]
    # conclude: [c_address]-[start_hash]-[c_storage]
    return msgpack.unpackb(b, raw=True, encoding='utf8')


def contract_fill(c: Contract, best_block=None, best_chain=None, stop_txhash=None):
    # database
    c_iter = builder.db.read_contract_iter(c_address=c.c_address, start_idx=c.db_index)
    for index, start_hash, finish_hash, (c_method, c_args, c_storage) in c_iter:
        if start_hash == stop_txhash or finish_hash == stop_txhash:
            return
        c.update(
            db_index=index,
            start_hash=start_hash,
            finish_hash=finish_hash,
            c_method=c_method,
            c_args=c_args,
            c_storage=c_storage)
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
            if tx.type != C.TX_CONCLUDE_CONTRACT:
                continue
            c_address, start_hash, c_storage = decode(tx.message)
            if c_address != c.c_address:
                continue
            if start_hash == stop_txhash:
                return
            start_tx = tx_builder.get_tx(txhash=start_hash)
            dummy, c_method, redeem_address, c_args = decode(start_tx.message)
            index = start_tx2index(start_tx=start_tx)
            c.update(
                db_index=index,
                start_hash=start_hash,
                finish_hash=tx.hash,
                c_method=c_method,
                c_args=c_args,
                c_storage=c_storage)
    # unconfirmed
    if best_block is None:
        unconfirmed = list()
        for conclude_tx in tuple(tx_builder.unconfirmed.values()):
            if conclude_tx.type != C.TX_CONCLUDE_CONTRACT:
                continue
            c_address, start_hash, c_storage = decode(conclude_tx.message)
            if c_address != c.c_address:
                continue
            start_tx = tx_builder.get_tx(txhash=start_hash)
            if start_tx.height is None:
                continue
            sort_key = start_tx2index(start_tx=start_tx)
            unconfirmed.append((c_address, start_tx, conclude_tx, c_storage, sort_key))

        for c_address, start_tx, conclude_tx, c_storage, sort_key in sorted(unconfirmed, key=lambda x: x[4]):
            dummy, c_method, redeem_address, c_args = decode(start_tx.message)
            if start_tx.hash == stop_txhash:
                break
            if conclude_tx.hash == stop_txhash:
                break
            c.update(
                db_index=sort_key,
                start_hash=start_tx.hash,
                finish_hash=conclude_tx.hash,
                c_method=c_method,
                c_args=c_args,
                c_storage=c_storage)


def get_contract_object(c_address, best_block=None, best_chain=None, stop_txhash=None):
    # stop_txhash is StartHash or ConcludeHash. Don't include the hash.
    c = cashe.get(c_address)
    contract_fill(c=c, best_block=best_block, best_chain=best_chain, stop_txhash=stop_txhash)
    return c


def get_conclude_hash_from_start(c_address, start_hash, best_block=None, best_chain=None):
    """ return ConcludeTX's hash by start_hash """
    # database
    c_iter = builder.db.read_contract_iter(c_address=c_address)
    for index, _start_hash, conclude_hash, dummy in c_iter:
        if _start_hash == start_hash:
            return conclude_hash
    # memory
    if best_chain:
        _best_chain = None
    elif best_block and best_block == builder.best_block:
        _best_chain = builder.best_chain
    else:
        dummy, _best_chain = builder.get_best_chain(best_block=best_block)
    for block in reversed(best_chain or _best_chain):
        for tx in block.txs:
            if tx.type != C.TX_CONCLUDE_CONTRACT:
                continue
            _c_address, _start_hash, c_storage = decode(tx.message)
            if _c_address != c_address:
                continue
            if _start_hash == start_hash:
                return tx.hash
    # unconfirmed
    if best_block is None:
        for tx in sorted(tx_builder.unconfirmed.values(), key=lambda x: x.create_time):
            if tx.type != C.TX_CONCLUDE_CONTRACT:
                continue
            _c_address, _start_hash, c_storage = decode(tx.message)
            if _c_address != c_address:
                continue
            if _start_hash == start_hash:
                return tx.hash
    return None


def get_validator_by_contract_info(c_address,
                                   start_tx=None,
                                   start_hash=None,
                                   best_block=None,
                                   best_chain=None,
                                   stop_txhash=None):
    c = get_contract_object(
        c_address=c_address, best_block=best_block, best_chain=best_chain, stop_txhash=stop_txhash)
    if c.version > -1:
        v = get_validator_object(
            v_address=c.v_address, best_block=best_block, best_chain=best_chain, stop_txhash=stop_txhash)
        if v.version > -1:
            return v
        else:
            raise BlockChainError('ValidatorTX is not init. {}'.format(v.v_address))
    elif start_tx or start_hash:
        if start_tx is None:
            start_tx = tx_builder.get_tx(txhash=start_hash)
        raw_args = start_tx.encoded_message()
        if len(raw_args) != 4:
            raise BlockChainError('Not correct args count {}'.format(raw_args))
        c_address, c_method, redeem_address, c_args = raw_args
        if c_method != M_INIT:
            raise BlockChainError('StartTX method is not INIT')
        if len(c_args) != 4:
            raise BlockChainError('Not correct c_args count {}'.format(c_args))
        c_bin, v_address, c_extra_imports, c_settings = c_args
        return get_validator_object(
            v_address=v_address, best_block=best_block, best_chain=best_chain, stop_txhash=stop_txhash)
    else:
        raise BlockChainError('ContractTX is not init. {}'.format(c_address))


def start_tx2index(start_hash=None, start_tx=None):
    if start_hash:
        start_tx = tx_builder.get_tx(txhash=start_hash)
    if start_tx.height is None:
        raise BlockChainError('Not confirmed startTX {}'.format(start_tx))
    block = builder.get_block(height=start_tx.height)
    if block is None:
        raise BlockChainError('Not found block of start_tx included? {}'.format(start_tx))
    if start_tx not in block.txs:
        raise BlockChainError('Not found start_tx in block? {}'.format(block))
    return start_tx.height * 0xffffffff + block.txs.index(start_tx)


def update_contract_cashe(*args):
    s = time()
    line = 0
    for c_address, c_contract in cashe:
        c_iter = builder.db.read_contract_iter(c_address=c_address, start_idx=c_contract.db_index)
        for index, start_hash, finish_hash, (c_method, c_args, c_storage) in c_iter:
            c_contract.update(
                db_index=index,
                start_hash=start_hash,
                finish_hash=finish_hash,
                c_method=c_method,
                c_args=c_args,
                c_storage=c_storage)
            line += 1
    log.debug("Contract cashe update {}line {}mSec".format(line, int((time() - s) * 1000)))


# when receive Block (103 x n height), update contract cashe
stream.filter(lambda obj: isinstance(obj, Block) and obj.height % 103 == 0).subscribe(
    on_next=update_contract_cashe, on_error=log.error)

__all__ = [
    "M_INIT",
    "M_UPDATE",
    "Storage",
    "Contract",
    "contract_fill",
    "get_contract_object",
    "get_conclude_hash_from_start",
    "get_validator_by_contract_info",
    "start_tx2index",
    "update_contract_cashe",
]
