from bc4py.config import C, BlockChainError
from bc4py.database.builder import builder, tx_builder
from expiringdict import ExpiringDict
from binascii import hexlify
import bjson
from collections import defaultdict, OrderedDict


M_INIT = 'init'
M_UPDATE = 'update'


cashe = ExpiringDict(max_len=100, max_age_seconds=1800)

settings_template = {
    'update_binary': True,
    'update_extra_imports': True}


class Storage(dict):
    __slots__ = ("c_address", "version")

    def __init__(self, c_address=None, init_storage=None):
        super().__init__()
        assert c_address is not None
        init_storage = init_storage or dict()
        # check value is not None
        for k, v in init_storage.items():
            if v is None:
                raise Exception('Not allowed None value...')
            self[k] = v
        # check key type
        if len({type(k) for k in init_storage}) > 1:
            raise Exception("All key type is same {}".format([type(k) for k in init_storage]))
        self.c_address = c_address
        self.version = 0

    def __repr__(self):
        return "<Storage of {} ver={} {}>".\
            format(self.c_address, self.version, dict(self.items()))

    def copy(self):
        s = Storage(c_address=self.c_address, init_storage=dict(self))
        s.version = self.version
        return s

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


class Contract:
    __slots__ = ("c_address", "version", "binary", "extra_imports",
                 "storage", "settings", "start_hash", "finish_hash")

    def __init__(self, c_address):
        self.c_address = c_address
        self.version = -1
        self.binary = None
        self.extra_imports = None
        self.storage = None
        self.settings = None
        self.start_hash = None
        self.finish_hash = None

    def __repr__(self):
        return "<Contract {} ver={}>".format(self.c_address, self.version)

    @property
    def info(self):
        if self.version == -1:
            return None
        d = OrderedDict()
        d['c_address'] = self.c_address
        d['version'] = self.version
        d['binary'] = hexlify(self.binary).decode()
        d['extra_imports'] = self.extra_imports
        d['storage_key'] = len(self.storage)
        d['settings'] = self.settings
        d['start_hash'] = hexlify(self.start_hash).decode()
        d['finish_hash'] = hexlify(self.finish_hash).decode()
        return d

    def update(self, start_hash, finish_hash, c_method, c_args, c_storage):
        if c_method == M_INIT:
            assert self.version == -1
            c_bin, c_extra_imports, c_settings = c_args
            self.binary = c_bin
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
        self.start_hash = start_hash
        self.finish_hash = finish_hash


def decode(b):
    # transfer: [c_address]-[c_method]-[redeem_address]-[c_args]
    # conclude: [c_address]-[start_hash]-[c_storage]
    return bjson.loads(b)


def encode(*args):
    assert len(args) == 3
    return bjson.dumps(args, compress=False)


def contract_fill(c: Contract, best_block=None, best_chain=None, stop_txhash=None):
    assert c.version == -1, 'Already updated'
    # database
    c_iter = builder.db.read_contract_iter(c_address=c.c_address)
    for index, start_hash, finish_hash, (c_method, c_args, c_storage) in c_iter:
        if start_hash == stop_txhash or finish_hash == stop_txhash:
            return
        c.update(start_hash=start_hash, finish_hash=finish_hash,
                 c_method=c_method, c_args=c_args, c_storage=c_storage)
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
            c.update(start_hash=start_hash, finish_hash=tx.hash,
                     c_method=c_method, c_args=c_args, c_storage=c_storage)
    # unconfirmed
    if best_block is None:
        unconfirmed = list()
        for conclude_tx in tuple(tx_builder.unconfirmed.values()):
            if conclude_tx.hash == stop_txhash:
                break
            if conclude_tx.type != C.TX_CONCLUDE_CONTRACT:
                continue
            c_address, start_hash, c_storage = decode(conclude_tx.message)
            if c_address != c.c_address:
                continue
            if start_hash == stop_txhash:
                break
            start_tx = tx_builder.get_tx(txhash=start_hash)
            if start_tx.height is None:
                continue
            include_block = builder.get_block(blockhash=builder.get_block_hash(height=start_tx.height))
            sort_key = start_tx.height * 0xffffffff + include_block.txs.index(start_tx)
            unconfirmed.append((c_address, start_tx, conclude_tx, c_storage, sort_key))

        for c_address, start_tx, conclude_tx, c_storage, sort_key in sorted(unconfirmed, key=lambda x: x[4]):
            dummy, c_method, redeem_address, c_args = decode(start_tx.message)
            c.update(start_hash=start_tx.hash, finish_hash=conclude_tx.hash,
                     c_method=c_method, c_args=c_args, c_storage=c_storage)


def get_contract_object(c_address, best_block=None, best_chain=None, stop_txhash=None):
    # stop_txhash is StartHash or ConcludeHash. Don't include the hash.
    if best_block:
        key = (best_block.hash, stop_txhash)
        if key in cashe:
            return cashe[key]
    else:
        key = None
    c = Contract(c_address=c_address)
    contract_fill(c=c, best_block=best_block, best_chain=best_chain, stop_txhash=stop_txhash)
    if key:
        cashe[key] = c
    return c


def get_conclude_by_start_iter(c_address, start_hash, best_block=None, best_chain=None, stop_txhash=None):
    """ return ConcludeTX's hashes by start_hash iter """
    # database
    c_iter = builder.db.read_contract_iter(c_address=c_address)
    for index, _start_hash, finish_hash, (c_method, c_args, c_storage) in c_iter:
        if finish_hash == stop_txhash:
            raise StopIteration
        if _start_hash == start_hash:
            yield finish_hash
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
                raise StopIteration
            if tx.type != C.TX_CONCLUDE_CONTRACT:
                continue
            _c_address, _start_hash, c_storage = decode(tx.message)
            if _c_address != c_address:
                continue
            if _start_hash == start_hash:
                yield tx.hash
    # unconfirmed
    if best_block is None:
        for tx in sorted(tx_builder.unconfirmed.values(), key=lambda x: x.time):
            if tx.hash == stop_txhash:
                raise StopIteration
            if tx.type != C.TX_CONCLUDE_CONTRACT:
                continue
            _c_address, _start_hash, c_storage = decode(tx.message)
            if _c_address != c_address:
                continue
            if _start_hash == start_hash:
                yield tx.hash
    raise StopIteration


def start_tx2index(start_hash=None, start_tx=None):
    if start_hash:
        start_tx = tx_builder.get_tx(txhash=start_hash)
    block = builder.get_block(blockhash=builder.get_block_hash(height=start_tx.height))
    if block is None:
        raise BlockChainError('Not found block of start_tx included? {}'.format(start_tx))
    if start_tx not in block.txs:
        raise BlockChainError('Not found start_tx in block? {}'.format(block))
    return start_tx.height * 0xffffffff + block.txs.index(start_tx)


__all__ = [
    "M_INIT", "M_UPDATE",
    "Storage",
    "Contract",
    "contract_fill",
    "get_contract_object",
    "get_conclude_by_start_iter",
    "start_tx2index",
]
