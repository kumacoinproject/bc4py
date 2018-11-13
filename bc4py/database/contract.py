from bc4py.config import C, BlockChainError
from bc4py.database.builder import builder, tx_builder
from bc4py.contract.storage import Storage
from expiringdict import ExpiringDict
from binascii import hexlify
import bjson


M_INIT = 'init'
M_UPDATE = 'update'


cashe = ExpiringDict(max_len=100, max_age_seconds=1800)

settings_template = {
    'update_binary': True,
    'update_extra_imports': True}


class Contract:
    def __init__(self, c_address):
        self.c_address = c_address
        self.index = -1
        self.binary = None
        self.extra_imports = None
        self.storage = None
        self.settings = None
        self.start_hash = None
        self.finish_hash = None

    def __repr__(self):
        return "<Contract {} ver={}>".format(self.c_address, self.index)

    @property
    def info(self):
        if self.index == -1:
            return None
        return {
            'c_address': self.c_address,
            'index': self.index,
            'binary': hexlify(self.binary).decode(),
            'extra_imports': self.extra_imports,
            'storage_key': len(self.storage),
            'settings': self.settings,
            'start_hash': hexlify(self.start_hash).decode(),
            'finish_hash': hexlify(self.finish_hash).decode()}

    def update(self, start_hash, finish_hash, c_method, c_args, c_storage):
        if c_method == M_INIT:
            assert self.index == -1
            c_bin, c_extra_imports, c_settings = c_args
            self.binary = c_bin
            self.extra_imports = c_extra_imports or list()
            self.settings = settings_template.copy()
            if c_settings:
                self.settings.update(c_settings)
            self.storage = Storage(c_address=self.c_address, **c_storage)
        elif c_method == M_UPDATE:
            assert self.index != -1
            c_bin, c_extra_imports, c_settings = c_args
            if self.settings['update_binary']:
                self.binary = c_bin
                if not c_settings.get('update_binary', False):
                    self.settings['update_binary'] = False
            if self.settings['update_extra_imports']:
                self.extra_imports = c_extra_imports
                if not c_settings.get('update_extra_imports', False):
                    self.settings['update_extra_imports'] = False
        else:
            assert self.index != -1
            self.storage.marge_diff(c_storage)
        self.index += 1
        self.start_hash = start_hash
        self.finish_hash = finish_hash


def decode(b):
    # transfer: [c_address]-[c_method]-[c_args]
    # conclude: [c_address]-[start_hash]-[c_storage]
    return bjson.loads(b)


def encode(*args):
    assert len(args) == 3
    return bjson.dumps(args, compress=False)


def contract_fill(c: Contract, best_block=None, best_chain=None, stop_txhash=None):
    assert c.index == -1, 'Already updated'
    # database
    c_iter = builder.db.read_contract_iter(c_address=c.c_address)
    for index, start_hash, finish_hash, (c_method, c_args, c_storage) in c_iter:
        if finish_hash == stop_txhash:
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
            start_tx = tx_builder.get_tx(txhash=start_hash)
            dummy, c_method, c_args = decode(start_tx.message)
            c.update(start_hash=start_hash, finish_hash=tx.hash,
                     c_method=c_method, c_args=c_args, c_storage=c_storage)
    # unconfirmed
    if best_block is None:
        for tx in sorted(tx_builder.unconfirmed.values(), key=lambda x: x.time):
            if tx.hash == stop_txhash:
                return
            if tx.type != C.TX_CONCLUDE_CONTRACT:
                continue
            c_address, start_hash, c_storage = decode(tx.message)
            if c_address != c.c_address:
                continue
            start_tx = tx_builder.get_tx(txhash=start_hash)
            dummy, c_method, c_args = decode(start_tx.message)
            c.update(start_hash=start_hash, finish_hash=tx.hash,
                     c_method=c_method, c_args=c_args, c_storage=c_storage)


def get_contract_object(c_address, best_block=None, best_chain=None, stop_txhash=None):
    c = Contract(c_address=c_address)
    contract_fill(c=c, best_block=best_block, best_chain=best_chain, stop_txhash=stop_txhash)
    return c


__all__ = [
    "M_INIT", "M_UPDATE",
    "Contract",
    "contract_fill",
    "get_contract_object"
]
