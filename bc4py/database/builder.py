from bc4py.config import C, V, P, stream
from bc4py.chain.utils import signature2bin, bin2signature
from bc4py.chain.tx import TX
from bc4py.chain.block import Block
import bc4py.chain.msgpack as bc4py_msgpack
from bc4py.user import Balance, Accounting
from bc4py.database.account import *
from bc4py.database.create import closing, create_db
from msgpack import unpackb, packb
import struct
import weakref
import os
import threading
from time import time
from nem_ed25519.key import is_address
from logging import getLogger, INFO

log = getLogger('bc4py')

# http://blog.livedoor.jp/wolf200x/archives/53052954.html
# https://github.com/happynear/py-leveldb-windows
# https://tangerina.jp/blog/leveldb-1.20-build/


try:
    import plyvel
    is_plyvel = True
    create_level_db = plyvel.DB
    getLogger('plyvel').setLevel(INFO)
except ImportError:
    import leveldb
    is_plyvel = False
    create_level_db = leveldb.LevelDB
    getLogger('leveldb').setLevel(INFO)


struct_block = struct.Struct('>II32s80sBI')
struct_tx = struct.Struct('>4IB')
struct_address = struct.Struct('>40s32sB')
struct_address_idx = struct.Struct('>IQ?')
struct_coins = struct.Struct('>II')
struct_construct_key = struct.Struct('>40sQ')
struct_construct_value = struct.Struct('>32s32s')
struct_validator_key = struct.Struct('>40sQ')
struct_validator_value = struct.Struct('>40sb32sb')

# constant
ITER_ORDER = 'big'
DB_VERSION = 3  # increase if you change database structure
ZERO_FILLED_HASH = b'\x00' * 32
DUMMY_VALIDATOR_ADDRESS = b'\x00' * 40
database_tuple = ("_block", "_tx", "_used_index", "_block_index",
                  "_address_index", "_coins", "_contract", "_validator")
# basic config
db_config = {
    'full_address_index': True,  # all address index?
    'timeout': None,
    'sync': False
}


class DataBase:
    def __init__(self, f_dummy=False, **kwargs):
        if f_dummy:
            return
        dirs = os.path.join(V.DB_HOME_DIR, 'db-ver{}'.format(DB_VERSION))
        self.dirs = dirs
        db_config.update(kwargs)  # extra settings
        self.sync = db_config['sync']
        self.timeout = db_config['timeout']
        self.event = threading.Event()
        self.event.set()
        # already used => LevelDBError
        if os.path.exists(dirs):
            f_create = False
        else:
            log.debug('No database directory found.')
            os.mkdir(dirs)
            f_create = True
        self._block = create_level_db(os.path.join(dirs, 'block'), create_if_missing=f_create)
        self._tx = create_level_db(os.path.join(dirs, 'tx'), create_if_missing=f_create)
        self._used_index = create_level_db(os.path.join(dirs, 'used-index'), create_if_missing=f_create)
        self._block_index = create_level_db(os.path.join(dirs, 'block-index'), create_if_missing=f_create)
        self._address_index = create_level_db(os.path.join(dirs, 'address-index'), create_if_missing=f_create)
        self._coins = create_level_db(os.path.join(dirs, 'coins'), create_if_missing=f_create)
        self._contract = create_level_db(os.path.join(dirs, 'contract'), create_if_missing=f_create)
        self._validator = create_level_db(os.path.join(dirs, 'validator'), create_if_missing=f_create)
        self.batch = None
        self.batch_thread = None
        log.debug(':create database connect, plyvel={} path={}'.format(is_plyvel, dirs.replace("\\", "/")))

    def close(self):
        if is_plyvel:
            for name in database_tuple:
                getattr(self, name).close()
        # else:  # TODO: how to close?
        #    for name in database_tuple:
        #        print(getattr(self, name).GetStats())
        #        getattr(self, name).__dell__()
        log.info("close database connection.")

    def batch_create(self):
        assert self.batch is None, 'batch is already start.'
        if not self.event.wait(timeout=self.timeout):
            raise TimeoutError('batch_create timeout.')
        self.event.clear()
        self.batch = dict()
        for name in database_tuple:
            self.batch[name] = dict()
        self.batch_thread = threading.current_thread()
        log.debug(":Create database batch.")

    def batch_commit(self):
        assert self.batch, 'Not created batch.'
        if is_plyvel:
            for name, memory in self.batch.items():
                batch = getattr(self, name).write_batch(sync=self.sync)
                for k, v in memory.items():
                    batch.put(k, v)
                batch.write()
        else:
            for name, memory in self.batch.items():
                new_data = leveldb.WriteBatch()
                for k, v in memory.items():
                    new_data.Put(k, v)
                getattr(self, name).Write(new_data, sync=self.sync)
        self.batch = None
        self.batch_thread = None
        self.event.set()
        log.debug("Commit database.")

    def batch_rollback(self):
        self.batch = None
        self.batch_thread = None
        self.event.set()
        log.debug("Rollback database.")

    def is_batch_thread(self):
        return self.batch and self.batch_thread is threading.current_thread()

    def read_block(self, blockhash):
        if self.is_batch_thread() and blockhash in self.batch['_block']:
            b = self.batch['_block'][blockhash]
        elif is_plyvel:
            b = self._block.get(blockhash, default=None)
        else:
            b = self._block.Get(blockhash, default=None)
        if b is None:
            return None
        b = bytes(b)
        height, _time, work, b_block, flag, tx_len = struct_block.unpack_from(b)
        idx = struct_block.size
        assert len(b) == idx+tx_len, 'Not correct size. [{}={}]'.format(len(b), idx+tx_len)
        block = Block.from_binary(binary=b_block)
        block.height = height
        block.work_hash = work
        block.flag = flag
        # block.txs = [self.read_tx(b[idx+32*i:idx+32*i+32]) for i in range(tx_len//32)]
        block.txs = [tx_builder.get_tx(b[idx+32*i:idx+32*i+32]) for i in range(tx_len//32)]
        return block

    def read_block_hash(self, height):
        b_height = height.to_bytes(4, ITER_ORDER)
        if self.is_batch_thread() and b_height in self.batch['_block_index']:
            return self.batch['_block_index'][b_height]
        elif is_plyvel:
            b = self._block_index.get(b_height, default=None)
        else:
            b = self._block_index.Get(b_height, default=None)
        if b is None:
            return None
        else:
            return bytes(b)

    def read_block_hash_iter(self, start_height=0):
        f_batch = self.is_batch_thread()
        batch_copy = self.batch['_block_index'].copy() if self.batch else dict()
        start = start_height.to_bytes(4, ITER_ORDER)
        if is_plyvel:
            block_iter = self._block_index.iterator(start=start)
        else:
            block_iter = self._block_index.RangeIter(key_from=start)
        for b_height, blockhash in block_iter:
            # height, blockhash
            b_height = bytes(b_height)
            blockhash = bytes(blockhash)
            if f_batch and b_height in batch_copy:
                blockhash = batch_copy[b_height]
                del batch_copy[b_height]
            yield int.from_bytes(b_height, ITER_ORDER), blockhash
        if f_batch:
            for b_height, blockhash in sorted(batch_copy.items(), key=lambda x: x[0]):
                yield int.from_bytes(b_height, ITER_ORDER), blockhash

    def read_tx(self, txhash):
        if self.is_batch_thread() and txhash in self.batch['_tx']:
            b = self.batch['_tx'][txhash]
        elif is_plyvel:
            b = self._tx.get(txhash, default=None)
        else:
            b = self._tx.Get(txhash, default=None)
        if b is None:
            return None
        b = bytes(b)
        height, _time, bin_len, sign_len, r_len = struct_tx.unpack_from(b)
        assert struct_tx.size == 17
        b_tx = b[17:17+bin_len]
        b_sign = b[17+bin_len:17+bin_len+sign_len]
        R = b[17+bin_len+sign_len:17+bin_len+sign_len+r_len]
        assert len(b) == 17+bin_len+sign_len, 'Wrong len [{}={}]'\
            .format(len(b), 17+bin_len+sign_len)
        tx = TX.from_binary(binary=b_tx)
        tx.height = height
        tx.signature = bin2signature(b_sign)
        tx.R = R
        return tx

    def read_usedindex(self, txhash):
        if self.is_batch_thread() and txhash in self.batch['_used_index']:
            b = self.batch['_used_index'][txhash]
        elif is_plyvel:
            b = self._used_index.get(txhash, default=None)
        else:
            b = self._used_index.Get(txhash, default=None)
        if b is None:
            return set()
        else:
            return set(b)

    def read_address_idx(self, address, txhash, index):
        k = address.encode() + txhash + index.to_bytes(1, ITER_ORDER)
        if self.is_batch_thread() and k in self.batch['_address_index']:
            b = self.batch['_address_index'][k]
        elif is_plyvel:
            b = self._address_index.get(k, default=None)
        else:
            b = self._address_index.Get(k, default=None)
        if b is None:
            return None
        b = bytes(b)
        # coin_id, amount, f_used
        return struct_address_idx.unpack(b)

    def read_address_idx_iter(self, address):
        f_batch = self.is_batch_thread()
        batch_copy = self.batch['_address_index'].copy() if self.batch else dict()
        b_address = address.encode()
        start = b_address+b'\x00'*(32+1)
        stop = b_address+b'\xff'*(32+1)
        if is_plyvel:
            address_iter = self._address_index.iterator(start=start, stop=stop)
        else:
            address_iter = self._address_index.RangeIter(key_from=start, key_to=stop)
        for k, v in address_iter:
            k, v = bytes(k), bytes(v)
            # address, txhash, index, coin_id, amount, f_used
            if f_batch and k in batch_copy and start <= k <= stop:
                v = batch_copy[k]
                del batch_copy[k]
            yield struct_address.unpack(k) + struct_address_idx.unpack(v)
        if f_batch:
            for k, v in sorted(batch_copy.items(), key=lambda x: x[0]):
                if k.startswith(b_address) and start <= k <= stop:
                    yield struct_address.unpack(k) + struct_address_idx.unpack(v)

    def read_coins_iter(self, coin_id):
        f_batch = self.is_batch_thread()
        batch_copy = self.batch['_coins'].copy() if self.batch else dict()
        b_coin_id = coin_id.to_bytes(4, ITER_ORDER)
        start = b_coin_id + b'\x00'*4
        stop = b_coin_id + b'\xff'*4
        if is_plyvel:
            coins_iter = self._coins.iterator(start=start, stop=stop)
        else:
            coins_iter = self._coins.RangeIter(key_from=start, key_to=stop)
        for k, v in coins_iter:
            k, v = bytes(k), bytes(v)
            # coin_id, index, txhash
            if f_batch and k in batch_copy and start <= k <= stop:
                v = batch_copy[k]
                del batch_copy[k]
            dummy, index = struct_coins.unpack(k)
            txhash, (params, setting) = v[:32], unpackb(v[32:], raw=True, use_list=False, encoding='utf8')
            yield index, txhash, params, setting
        if f_batch:
            for k, v in sorted(batch_copy.items(), key=lambda x: x[0]):
                if k.startswith(b_coin_id) and start <= k <= stop:
                    dummy, index = struct_coins.unpack(k)
                    txhash, (params, setting) = v[:32], unpackb(v[32:], raw=True, use_list=False, encoding='utf8')
                    yield index, txhash, params, setting

    def read_contract_iter(self, c_address, start_idx=None):
        f_batch = self.is_batch_thread()
        batch_copy = self.batch['_contract'].copy() if self.batch else dict()
        b_c_address = c_address.encode()
        # caution: iterator/RangeIter's result include start and stop, need to add 1.
        start = b_c_address + ((start_idx+1).to_bytes(8, ITER_ORDER) if start_idx else b'\x00'*8)
        stop = b_c_address + b'\xff'*8
        if is_plyvel:
            contract_iter = self._contract.iterator(start=start, stop=stop)
        else:
            contract_iter = self._contract.RangeIter(key_from=start, key_to=stop)
        for k, v in contract_iter:
            k, v = bytes(k), bytes(v)
            # KEY: [c_address 40s]-[index uint8]
            # VALUE: [start_hash 32s]-[finish_hash 32s]-[msgpack(c_method, c_args, c_storage)]
            # c_address, index, start_hash, finish_hash, message
            if f_batch and k in batch_copy and start <= k <= stop:
                v = batch_copy[k]
                del batch_copy[k]
            dummy, index = struct_construct_key.unpack(k)
            start_hash, finish_hash, raw_message = v[0:32], v[32:64], v[64:]
            message = unpackb(raw_message, raw=True, use_list=False, encoding='utf8')
            yield index, start_hash, finish_hash, message
        if f_batch:
            for k, v in sorted(batch_copy.items(), key=lambda x: x[0]):
                if k.startswith(b_c_address) and start <= k <= stop:
                    dummy, index = struct_construct_key.unpack(k)
                    start_hash, finish_hash, raw_message = v[0:32], v[32:64], v[64:]
                    message = unpackb(raw_message, raw=True, use_list=False, encoding='utf8')
                    yield index, start_hash, finish_hash, message

    def read_validator_iter(self, v_address, start_idx=None):
        f_batch = self.is_batch_thread()
        batch_copy = self.batch['_validator'].copy() if self.batch else dict()
        b_v_address = v_address.encode()
        # caution: iterator/RangeIter's result include start and stop, need to add 1.
        start = b_v_address + ((start_idx+1).to_bytes(8, ITER_ORDER) if start_idx else b'\x00' * 8)
        stop = b_v_address + b'\xff'*8
        # from database
        if is_plyvel:
            validator_iter = self._validator.iterator(start=start, stop=stop)
        else:
            validator_iter = self._validator.RangeIter(key_from=start, key_to=stop)
        for k, v in validator_iter:
            k, v = bytes(k), bytes(v)
            # KEY [v_address 40s]-[index unit8]
            # VALUE [new_address 40s]-[flag int1]-[txhash 32s]-[sig_diff int1]
            if f_batch and k in batch_copy and start <= k <= stop:
                v = batch_copy[k]
                del batch_copy[k]
            dummy, index = struct_validator_key.unpack(k)
            new_address, flag, txhash, sig_diff = struct_validator_value.unpack(v)
            if new_address == DUMMY_VALIDATOR_ADDRESS:
                yield index, None, flag, txhash, sig_diff
            else:
                yield index, new_address.decode(), flag, txhash, sig_diff
        # from memory
        if f_batch:
            for k, v in sorted(batch_copy.items(), key=lambda x: x[0]):
                if k.startswith(b_v_address) and start <= k <= stop:
                    dummy, index = struct_validator_key.unpack(k)
                    new_address, flag, txhash, sig_diff = struct_validator_value.unpack(v)
                    if new_address == DUMMY_VALIDATOR_ADDRESS:
                        yield index, None, flag, txhash, sig_diff
                    else:
                        yield index, new_address.decode(), flag, txhash, sig_diff

    def write_block(self, block):
        assert self.is_batch_thread(), 'Not created batch.'
        b_tx = b''.join(tx.hash for tx in block.txs)
        tx_len = len(b_tx)
        if block.work_hash is None:
            block.update_pow()
        b = struct_block.pack(block.height, block.time, block.work_hash, block.b, block.flag, tx_len)
        b += b_tx
        self.batch['_block'][block.hash] = b
        b_height = block.height.to_bytes(4, ITER_ORDER)
        self.batch['_block_index'][b_height] = block.hash
        log.debug("Insert new block {}".format(block))

    def write_tx(self, tx):
        assert self.is_batch_thread(), 'Not created batch.'
        bin_len = len(tx.b)
        b_sign = signature2bin(tx.signature)
        sign_len = len(b_sign)
        r_len = len(tx.R)
        b = struct_tx.pack(tx.height, tx.time, bin_len, sign_len, r_len)
        b += tx.b + b_sign + tx.R
        self.batch['_tx'][tx.hash] = b
        log.debug("Insert new tx {}".format(tx))

    def write_usedindex(self, txhash, usedindex):
        assert self.is_batch_thread(), 'Not created batch.'
        assert isinstance(usedindex, set), 'Unsedindex is set.'
        self.batch['_used_index'][txhash] = bytes(sorted(usedindex))

    def write_address_idx(self, address, txhash, index, coin_id, amount, f_used):
        assert self.is_batch_thread(), 'Not created batch.'
        k = address.encode() + txhash + index.to_bytes(1, ITER_ORDER)
        v = struct_address_idx.pack(coin_id, amount, f_used)
        self.batch['_address_index'][k] = v
        log.debug("Insert new address idx {}".format(address))

    def write_coins(self, coin_id, txhash, params, setting):
        assert self.is_batch_thread(), 'Not created batch.'
        index = -1
        for index, *dummy in self.read_coins_iter(coin_id=coin_id): pass
        index += 1
        k = coin_id.to_bytes(4, ITER_ORDER) + index.to_bytes(4, ITER_ORDER)
        v = txhash + packb((params, setting), use_bin_type=True)
        self.batch['_coins'][k] = v
        log.debug("Insert new coins id={}".format(coin_id))

    def write_contract(self, c_address, start_tx, finish_hash, message):
        assert self.is_batch_thread(), 'Not created batch.'
        assert len(message) == 3
        include_block = self.read_block(blockhash=self.read_block_hash(height=start_tx.height))
        index = start_tx.height * 0xffffffff + include_block.txs.index(start_tx)
        # check newer index already inserted
        last_index = None
        for last_index, *dummy in self.read_contract_iter(c_address=c_address, start_idx=index):
            pass
        assert last_index is None, 'Not allow older ConcludeTX insert. my={} last={}'.format(index, last_index)
        k = c_address.encode() + index.to_bytes(8, ITER_ORDER)
        v = start_tx.hash + finish_hash + packb(message, use_bin_type=True)
        self.batch['_contract'][k] = v
        log.debug("Insert new contract {} {}".format(c_address, index))

    def write_validator(self, v_address, new_address, flag, tx, sign_diff):
        assert self.is_batch_thread(), 'Not created batch.'
        include_block = self.read_block(blockhash=self.read_block_hash(height=tx.height))
        index = tx.height * 0xffffffff + include_block.txs.index(tx)
        # check newer index already inserted
        last_index = None
        for last_index, *dummy in self.read_validator_iter(v_address=v_address, start_idx=index):
            pass
        assert last_index is None, 'Not allow older ValidatorEditTX insert. last={}'.format(last_index)
        if new_address is None:
            new_address = DUMMY_VALIDATOR_ADDRESS
        else:
            new_address = new_address.encode()
        k = v_address.encode() + index.to_bytes(8, ITER_ORDER)
        v = struct_validator_value.pack(new_address, flag, tx.hash, sign_diff)
        self.batch['_validator'][k] = v
        log.debug("Insert new validator {} {}".format(v_address, index))


class ChainBuilder:
    def __init__(self, cashe_limit=C.CASHE_LIMIT, batch_size=C.BATCH_SIZE):
        assert cashe_limit > batch_size, 'cashe_limit > batch_size.'
        self.cashe_limit = cashe_limit
        self.batch_size = batch_size
        self.chain = dict()
        # self.best_chain → [height=n+m]-[height=n+m-1]-....-[height=n+1]-[height=n]
        # self.root_block → [height=n-1] (self.chainに含まれず)
        # self.best_block → [height=n+m]
        self.best_chain = None
        self.root_block = None
        self.best_block = None
        self.db = DataBase(f_dummy=True)

    def close(self):
        self.db.batch_create()
        self.save_memory_file()
        self.db.close()

    def set_database_path(self, **kwargs):
        try:
            self.db = DataBase(f_dummy=False, **kwargs)
            log.info("connect database.")
        except leveldb.LevelDBError:
            log.warning("Already connect database.")
        except Exception as e:
            log.debug("Failed connect database, {}.".format(e))

    def init(self, genesis_block: Block, batch_size=None):
        assert self.db, 'Why database connection failed?'
        # return status
        # True  = Only genesisBlock, recommend to import bootstrap.dat first
        # False = Many blocks in LevelDB, sync by network
        if batch_size is None:
            batch_size = self.cashe_limit
        # GenesisBlockか確認
        t = time()
        try:
            if genesis_block.hash != self.db.read_block_hash(0):
                raise BlockBuilderError("Don't match genesis hash [{}!={}]".format(
                    genesis_block.hash.hex(), self.db.read_block_hash(0).hex()))
            elif genesis_block != self.db.read_block(genesis_block.hash):
                raise BlockBuilderError("Don't match genesis binary [{}!={}]".format(
                    genesis_block.b.hex(), self.db.read_block(genesis_block.hash).b.hex()))
        except Exception:
            # GenesisBlockしか無いのでDummyBlockを入れる処理
            self.root_block = Block()
            self.root_block.hash = b'\xff' * 32
            self.chain[genesis_block.hash] = genesis_block
            self.best_chain = [genesis_block]
            self.best_block = genesis_block
            log.info("Set dummy block, genesisBlock={}".format(genesis_block))
            user_account.init()
            return True

        with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
            cur = db.cursor()
            # 0HeightよりBlockを取得して確認
            before_block = genesis_block
            batch_blocks = list()
            for height, blockhash in self.db.read_block_hash_iter(start_height=1):
                block = self.db.read_block(blockhash)
                if block.previous_hash != before_block.hash:
                    raise BlockBuilderError("PreviousHash != BlockHash [{}!={}]"
                                            .format(block, before_block))
                elif block.height != height:
                    raise BlockBuilderError("BlockHeight != DBHeight [{}!={}]"
                                            .format(block.height, height))
                elif height != before_block.height+1:
                    raise BlockBuilderError("DBHeight != BeforeHeight+1 [{}!={}+1]"
                                            .format(height, before_block.height))
                for tx in block.txs:
                    if tx.height != height:
                        raise BlockBuilderError("TXHeight != BlockHeight [{}!{}]"
                                                .format(tx.height, height))
                    # inputs
                    for txhash, txindex in tx.inputs:
                        input_tx = self.db.read_tx(txhash)
                        address, coin_id, amount = input_tx.outputs[txindex]
                        _coin_id, _amount, f_used = self.db.read_address_idx(address, txhash, txindex)
                        usedindex = self.db.read_usedindex(txhash)
                        if coin_id != _coin_id or amount != _amount:
                            raise BlockBuilderError("Inputs, coin_id != _coin_id or amount != _amount [{}!{}] [{}!={}]"
                                                    .format(coin_id, _coin_id, amount, _amount))
                        elif txindex not in usedindex:
                            raise BlockBuilderError("Already used but unused. [{} not in {}]".format(txindex, usedindex))
                        elif not f_used:
                            raise BlockBuilderError("Already used but unused flag. [{}:{}]".format(input_tx, txindex))
                    # outputs
                    for index, (address, coin_id, amount) in enumerate(tx.outputs):
                        _coin_id, _amount, f_used = self.db.read_address_idx(address, tx.hash, index)
                        if coin_id != _coin_id or amount != _amount:
                            raise BlockBuilderError("Outputs, coin_id != _coin_id or amount != _amount [{}!{}] [{}!={}]"
                                                    .format(coin_id, _coin_id, amount, _amount))
                # Block確認終了
                before_block = block
                batch_blocks.append(block)
                if len(batch_blocks) >= batch_size:
                    user_account.new_batch_apply(batched_blocks=batch_blocks, outer_cur=cur)
                    batch_blocks.clear()
                    log.debug("UserAccount batched at {} height.".format(block.height))
            # load and rebuild memory section
            self.root_block = before_block
            memorized_blocks, self.best_block = self.load_memory_file(before_block)
            # Memory化されたChainを直接復元
            for block in memorized_blocks:
                batch_blocks.append(block)
                self.chain[block.hash] = block
                for tx in block.txs:
                    if tx.hash not in tx_builder.chained_tx:
                        tx_builder.chained_tx[tx.hash] = tx
                    if tx.hash in tx_builder.unconfirmed:
                        del tx_builder.unconfirmed[tx.hash]
            self.best_chain = list(reversed(memorized_blocks))
            # UserAccount update
            user_account.new_batch_apply(batched_blocks=batch_blocks, outer_cur=cur)
            user_account.init(outer_cur=cur)
            db.commit()
        log.info("Init finished, last block is {} {}Sec".format(before_block, round(time()-t, 3)))
        return False

    def save_memory_file(self):
        odd_path = os.path.join(self.db.dirs, 'memory.odd.dat')
        even_path = os.path.join(self.db.dirs, 'memory.even.dat')
        if not os.path.exists(odd_path):
            priority_tuple = odd_path, even_path
        elif not os.path.exists(even_path):
            priority_tuple = even_path, odd_path
        elif os.stat(odd_path).st_mtime > os.stat(even_path).st_mtime:
            priority_tuple = even_path, odd_path
        else:
            priority_tuple = odd_path, even_path
        for path in priority_tuple:
            try:
                with open(path, mode='bw') as fp:
                    bc4py_msgpack.dump(self.best_chain, fp)
                return
            except Exception as e:
                log.warning("Failed recode by '{}'".format(e))
        raise Exception("Cannot recode two memory files?")

    def load_memory_file(self, root_block):
        memorized_blocks = list()
        odd_path = os.path.join(self.db.dirs, 'memory.odd.dat')
        even_path = os.path.join(self.db.dirs, 'memory.even.dat')
        # load by file date order
        check_order = list()
        if os.path.exists(odd_path) and os.path.exists(even_path):
            if os.stat(odd_path).st_mtime < os.stat(even_path).st_mtime:
                check_order.extend([odd_path, even_path])
            else:
                check_order.extend([even_path, odd_path])
        elif os.path.exists(odd_path):
            check_order.append(odd_path)
        elif os.path.exists(even_path):
            check_order.append(even_path)
        else:
            raise Exception('Not found memory files.')
        # load by check_order
        for path in check_order:
            try:
                with open(path, mode='br') as fp:
                    for block in reversed(bc4py_msgpack.load(fp)):
                        if root_block.hash == block.previous_hash:
                            memorized_blocks.append(block)
                            root_block = block
            except Exception as e:
                log.error("Failed load, \"{}\"".format(e), exc_info=True)
        if len(memorized_blocks) > 0:
            log.debug("Load {} blocks, best={}".format(len(memorized_blocks), root_block))
            return memorized_blocks, root_block
        else:
            raise BlockBuilderError("Failed load memory files.")

    def get_best_chain(self, best_block=None):
        assert self.root_block, 'Do not init.'
        if best_block:
            best_chain = [best_block]
            previous_hash = best_block.previous_hash
            while self.root_block.hash != previous_hash:
                if previous_hash not in self.chain:
                    raise BlockBuilderError('Cannot find previousHash, may not main-chain. {}'
                                            .format(previous_hash.hex()))
                block = self.chain[previous_hash]
                previous_hash = block.previous_hash
                best_chain.append(block)
            return best_block, best_chain
        # BestBlockがchainにおける
        best_score = 0.0
        best_block = None
        best_chain = list()
        for block in list(self.chain.values()):
            if block in best_chain:
                continue
            tmp_best_score = block.score
            tmp_best_block = block
            tmp_best_chain = [block]
            while block.previous_hash in self.chain:
                block = self.chain[block.previous_hash]
                tmp_best_score += block.score
                tmp_best_chain.append(block)
            else:
                if self.root_block.hash != block.previous_hash:
                    continue
            if best_score > tmp_best_score:
                continue
            best_score = tmp_best_score
            best_block = tmp_best_block
            best_chain = tmp_best_chain
        # txのheightを揃える
        for block in best_chain:
            for tx in block.txs:
                tx.height = block.height
        assert best_block, 'Cannot find best_block on get_best_chain? chain={}'.format(list(self.chain))
        # best_chain = [<height=n>, <height=n-1>, ...]
        return best_block, best_chain

    def batch_apply(self):
        # 無チェックで挿入するから要注意
        if self.cashe_limit > len(self.chain):
            return list()
        # cashe許容量を上回っているので記録
        self.db.batch_create()
        log.debug("Start batch apply chain={}".format(len(self.chain)))
        best_chain = self.best_chain.copy()
        batch_count = self.batch_size
        batched_blocks = list()
        with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
            cur = db.cursor()
            try:
                block = None
                while batch_count > 0 and len(best_chain) > 0:
                    batch_count -= 1
                    block = best_chain.pop()  # 古いものから順に
                    batched_blocks.append(block)
                    self.db.write_block(block)  # Block
                    assert len(block.txs) > 0, "found no tx in {}".format(block)
                    for tx in block.txs:
                        self.db.write_tx(tx)  # TX
                        # inputs
                        for index, (txhash, txindex) in enumerate(tx.inputs):
                            # DataBase内でのみのUsedIndexを取得
                            usedindex = self.db.read_usedindex(txhash)
                            if txindex in usedindex:
                                raise BlockBuilderError('Already used index? {}:{}'
                                                        .format(txhash.hex(), txindex))
                            usedindex.add(txindex)
                            self.db.write_usedindex(txhash, usedindex)  # UsedIndex update
                            input_tx = tx_builder.get_tx(txhash)
                            address, coin_id, amount = input_tx.outputs[txindex]
                            if db_config['full_address_index'] or \
                                    is_address(ck=address, prefix=V.BLOCK_CONTRACT_PREFIX) or \
                                    read_address2user(address=address, cur=cur):
                                # 必要なAddressのみ
                                self.db.write_address_idx(address, txhash, txindex, coin_id, amount, True)
                        # outputs
                        for index, (address, coin_id, amount) in enumerate(tx.outputs):
                            if db_config['full_address_index'] or \
                                    is_address(ck=address, prefix=V.BLOCK_CONTRACT_PREFIX) or \
                                    read_address2user(address=address, cur=cur):
                                # 必要なAddressのみ
                                self.db.write_address_idx(address, tx.hash, index, coin_id, amount, False)
                        # TXの種類による追加操作
                        if tx.type == C.TX_GENESIS:
                            pass
                        elif tx.type == C.TX_TRANSFER:
                            pass
                        elif tx.type == C.TX_POW_REWARD:
                            pass
                        elif tx.type == C.TX_POS_REWARD:
                            pass
                        elif tx.type == C.TX_MINT_COIN:
                            mint_id, params, setting = tx.encoded_message()
                            self.db.write_coins(coin_id=mint_id, txhash=tx.hash, params=params, setting=setting)

                        elif tx.type == C.TX_VALIDATOR_EDIT:
                            v_address, new_address, flag, sig_diff = tx.encoded_message()
                            self.db.write_validator(v_address=v_address, new_address=new_address,
                                                    flag=flag, tx=tx, sign_diff=sig_diff)

                        elif tx.type == C.TX_CONCLUDE_CONTRACT:
                            v_address, start_hash, c_storage = tx.encoded_message()
                            start_tx = tx_builder.get_tx(txhash=start_hash)
                            dummy, c_method, redeem_address, c_args = start_tx.encoded_message()
                            self.db.write_contract(c_address=v_address, start_tx=start_tx,
                                                   finish_hash=tx.hash, message=(c_method, c_args, c_storage))

                # block挿入終了
                self.best_chain = best_chain
                self.root_block = block
                self.db.batch_commit()
                self.save_memory_file()
                # root_blockよりHeightの小さいBlockを消す
                for blockhash, block in self.chain.copy().items():
                    if self.root_block.height >= block.height:
                        del self.chain[blockhash]
                log.debug("Success batch {} blocks, root={}."
                              .format(len(batched_blocks), self.root_block))
                # アカウントへ反映↓
                user_account.new_batch_apply(batched_blocks=batched_blocks, outer_cur=cur)
                db.commit()
                return batched_blocks  # [<height=n>, <height=n+1>, .., <height=n+m>]
            except Exception as e:
                self.db.batch_rollback()
                log.warning("Failed batch block builder. '{}'".format(e), exc_info=True)
                return list()

    def new_block(self, block):
        # とりあえず新規に挿入
        self.chain[block.hash] = block
        # BestChainの変化を調べる
        new_best_block, new_best_chain = self.get_best_chain()
        if self.best_block and new_best_block == self.best_block:
            return  # 操作を加える必要は無い
        # tx heightを合わせる
        old_best_chain = self.best_chain.copy()
        commons = set(new_best_chain) & set(old_best_chain)
        for index, block in enumerate(old_best_chain):
            if block not in commons:
                try: old_best_chain[index+1].next_hash = None
                except IndexError: pass
                for tx in block.txs:
                    tx.height = None
                block.f_orphan = True
        for index, block in enumerate(new_best_chain):
            if block not in commons:
                try: new_best_chain[index+1].next_hash = block.hash
                except IndexError: pass
                for tx in block.txs:
                    tx.height = block.height
                block.f_orphan = False
        # 変化しているので反映する
        self.best_block, self.best_chain = new_best_block, new_best_chain
        tx_builder.affect_new_chain(
            new_best_chain=set(new_best_chain) - commons,
            old_best_chain=set(old_best_chain) - commons)

    def get_block(self, blockhash=None, height=None):
        if height is not None:
            blockhash = self.get_block_hash(height=height)
            if blockhash is None:
                return None
        # Get by blockhash
        if blockhash in self.chain:
            # Memory
            block = self.chain[blockhash]
            block.recode_flag = 'memory'
            block.f_orphan = bool(block not in self.best_chain)
        else:
            # DataBase
            block = self.db.read_block(blockhash)
            if block:
                block.recode_flag = 'database'
                block.f_orphan = False
            else:
                return None
        return block

    def get_block_hash(self, height):
        if height > self.best_block.height:
            return None
        elif height < 0:
            return None
        # Memory
        for block in self.best_chain:
            if height == block.height:
                return block.hash
        # DataBase
        return self.db.read_block_hash(height)


class TransactionBuilder:
    def __init__(self):
        # TXs that Blocks don't contain
        self.unconfirmed = dict()
        # Contract/Validator related tx
        # don't affect UTXO check. Ex, same inputs has or not enough signatures
        self.pre_unconfirmed = dict()
        # TXs that MAIN chain contains
        self.chained_tx = weakref.WeakValueDictionary()
        # DataBase contains TXs
        self.cashe = weakref.WeakValueDictionary()

    def put_unconfirmed(self, tx, outer_cur=None):
        assert tx.height is None, 'Not unconfirmed tx {}'.format(tx)
        assert tx.hash not in self.pre_unconfirmed
        if tx.type in (C.TX_POW_REWARD, C.TX_POS_REWARD):
            return  # It is Reword tx
        elif tx.hash in self.unconfirmed:
            log.debug('Already unconfirmed tx. {}'.format(tx))
            return
        tx.create_time = time()
        tx.recode_flag = 'unconfirmed'
        self.unconfirmed[tx.hash] = tx
        if tx.hash in self.chained_tx:
            log.debug('Already chained tx. {}'.format(tx))
            return
        user_account.affect_new_tx(tx, outer_cur)
        if not stream.is_disposed:
            stream.on_next(tx)

    def marge_signature(self, tx):
        # try to marge signature
        # check before signature manageable
        if tx.hash in self.unconfirmed:
            original_tx = self.unconfirmed[tx.hash]
            new_signature = list(set(tx.signature) | set(original_tx.signature))
            log.info("Marge unconfirmed TX's signature sign={}>{}"
                         .format(len(original_tx.signature), len(new_signature)))
            original_tx.signature = new_signature
        elif tx.hash in self.pre_unconfirmed:
            original_tx = self.pre_unconfirmed[tx.hash]
            new_signature = list(set(tx.signature) | set(original_tx.signature))
            log.info("Marge pre-unconfirmed TX's signature sign={}>{}"
                         .format(len(original_tx.signature), len(new_signature)))
            original_tx.signature = new_signature
        elif tx.hash in self.chained_tx:
            log.error("Try to marge already confirmed TX's signature {}".format(tx))
        else:
            # new pre-unconfirmed tx
            tx.recode_flag = 'pre-unconfirmed'
            self.pre_unconfirmed[tx.hash] = tx
            if not stream.is_disposed:
                stream.on_next(tx)
            log.info("Insert pre-unconfirmed TX")

    def get_tx(self, txhash, default=None):
        if txhash in self.cashe:
            try:
                return self.cashe[txhash]
            except KeyError:
                # flashed WeakValueDictionary, need to retry
                return self.get_tx(txhash=txhash, default=default)
        elif txhash in self.pre_unconfirmed:
            # pre-unconfirmedより
            tx = self.pre_unconfirmed[txhash]
            tx.recode_flag = 'pre-unconfirmed'
            if tx.height is not None: log.warning("Not unconfirmed. {}".format(tx))
        elif txhash in self.unconfirmed:
            # unconfirmedより
            tx = self.unconfirmed[txhash]
            tx.recode_flag = 'unconfirmed'
            if tx.height is not None: log.warning("Not unconfirmed. {}".format(tx))
        elif txhash in self.chained_tx:
            # Memoryより
            try:
                tx = self.chained_tx[txhash]
            except KeyError:
                # flashed WeakValueDictionary, need to retry
                return self.get_tx(txhash=txhash, default=default)
            tx.recode_flag = 'memory'
            if tx.height is None: log.warning("Is unconfirmed. {}".format(tx))
        else:
            # Databaseより
            tx = builder.db.read_tx(txhash)
            if tx:
                tx.recode_flag = 'database'
                self.cashe[txhash] = tx
            else:
                return default
        return tx

    def __contains__(self, item):
        return bool(self.get_tx(item.hash))

    def affect_new_chain(self, old_best_chain, new_best_chain):
        def input_check(_tx):
            for input_hash, input_index in _tx.inputs:
                if input_index in builder.db.read_usedindex(input_hash):
                    return True
            return False

        # 状態を戻す
        for block in old_best_chain:
            for tx in block.txs:
                if tx.hash not in self.unconfirmed and tx.type not in (C.TX_POW_REWARD, C.TX_POS_REWARD):
                    self.unconfirmed[tx.hash] = tx
                if tx.hash in self.chained_tx:
                    del self.chained_tx[tx.hash]
        # 新規に反映する
        for block in new_best_chain:
            for tx in block.txs:
                if tx.hash not in self.chained_tx:
                    self.chained_tx[tx.hash] = tx
                if tx.hash in self.unconfirmed:
                    del self.unconfirmed[tx.hash]

        # delete expired unconfirmed txs
        limit = int(time() - V.BLOCK_GENESIS_TIME - C.ACCEPT_MARGIN_TIME)
        before_num = len(self.unconfirmed)
        for txhash, tx in self.unconfirmed.copy().items():
            if P.F_NOW_BOOTING:
                break  # not delete on booting..
            # Remove expired unconfirmed tx
            if limit > tx.deadline:
                log.debug("Remove unconfirmed 'expired' {}".format(tx))
                del self.unconfirmed[txhash]
                continue
            # Remove tx include by both best_chain & unconfirmed
            if txhash in self.chained_tx:
                log.debug("Remove unconfirmed 'include on chain' {}".format(tx))
                del self.unconfirmed[txhash]
                continue
            # check inputs usedindex on database (not memory, not unconfirmed)
            if input_check(tx):
                log.debug("Remove unconfirmed 'use used inputs' {}".format(tx))
                del self.unconfirmed[txhash]
                continue
        if before_num != len(self.unconfirmed):
            log.warning("Removed {} unconfirmed txs".format(len(self.unconfirmed)-before_num))


class UserAccount:
    def __init__(self):
        self.db_balance = Accounting()
        # {txhash: (_type, movement, _time),..}
        self.memory_movement = dict()

    def init(self, f_delete=False, outer_cur=None):
        def _wrapper(cur):
            memory_sum = Accounting()
            for move_log in read_log_iter(cur):
                # logに記録されてもBlockに取り込まれていないならTXは存在せず
                if builder.db.read_tx(move_log.txhash):
                    memory_sum += move_log.movement
                else:
                    log.debug("It's unknown log {}".format(move_log))
                    if f_delete:
                        delete_log(move_log.txhash, cur)
            self.db_balance += memory_sum
        assert f_delete is False, 'Unsafe function!'
        if outer_cur:
            _wrapper(outer_cur)
        else:
            with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
                _wrapper(db.cursor())
                if f_delete:
                    log.warning("Delete user's old unconfirmed tx.")
                    db.commit()

    def get_balance(self, confirm=6, outer_cur=None):
        def _wrapper(cur):
            # DataBase
            account = self.db_balance.copy()
            # Memory
            limit_height = builder.best_block.height - confirm
            for block in builder.best_chain:
                for tx in block.txs:
                    move_log = read_txhash2log(tx.hash, cur)
                    if move_log is None:
                        if tx.hash in self.memory_movement:
                            move_log = self.memory_movement[tx.hash]
                    if move_log:
                        for user, coins in move_log.movement.items():
                            for coin_id, amount in coins:
                                if limit_height < block.height:
                                    if amount < 0:
                                        account[user][coin_id] += amount
                                else:
                                    # allow incoming balance
                                    account[user][coin_id] += amount
            # Unconfirmed
            for tx in list(tx_builder.unconfirmed.values()):
                move_log = read_txhash2log(tx.hash, cur)
                if move_log is None:
                    if tx.hash in self.memory_movement:
                        move_log = self.memory_movement[tx.hash]
                if move_log:
                    for user, coins in move_log.movement.items():
                        for coin_id, amount in coins:
                            if amount < 0:
                                account[user][coin_id] += amount
            return account
        assert confirm < builder.cashe_limit - builder.batch_size, 'Too few cashe size.'
        assert builder.best_block, 'Not DataBase init.'
        if outer_cur:
            return _wrapper(outer_cur)
        else:
            with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
                return _wrapper(db.cursor())

    def move_balance(self, _from, _to, coins, outer_cur=None):
        def _wrapper(cur):
            # DataBaseに即書き込む(Memoryに入れない)
            movements = Accounting()
            movements[_from] -= coins
            movements[_to] += coins
            txhash = insert_log(movements, cur)
            self.db_balance += movements
            return txhash
        assert isinstance(coins, Balance), 'coins is Balance.'
        if outer_cur:
            return _wrapper(outer_cur)
        else:
            with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
                r = _wrapper(db.cursor())
                db.commit()
                return r

    def get_movement_iter(self, start=0, f_dict=False, outer_cur=None):
        def _wrapper(cur):
            count = 0
            # Unconfirmed
            for tx in sorted(tx_builder.unconfirmed.values(), key=lambda x: x.create_time, reverse=True):
                move_log = read_txhash2log(tx.hash, cur)
                if move_log is None:
                    if tx.hash in self.memory_movement:
                        move_log = self.memory_movement[tx.hash]
                else:
                    if tx.hash in self.memory_movement:
                        move_log.tx_ref = self.memory_movement[tx.hash].tx_ref
                if move_log:
                    if count >= start:
                        if f_dict:
                            yield move_log.get_dict_data(recode_flag='unconfirmed', outer_cur=cur)
                        else:
                            yield move_log.get_tuple_data()
                    count += 1
            # Memory
            for block in reversed(builder.best_chain):
                for tx in block.txs:
                    move_log = read_txhash2log(tx.hash, cur)
                    if move_log is None:
                        if tx.hash in self.memory_movement:
                            move_log = self.memory_movement[tx.hash]
                    else:
                        if tx.hash in self.memory_movement:
                            move_log.tx_ref = self.memory_movement[tx.hash].tx_ref
                    if move_log:
                        if count >= start:
                            if f_dict:
                                yield move_log.get_dict_data(recode_flag='memory', outer_cur=cur)
                            else:
                                yield move_log.get_tuple_data()
                        count += 1
            # DataBase
            for move_log in read_log_iter(cur, start - count):
                # TRANSFERなど はDBとMemoryの両方に存在する
                if move_log.txhash in self.memory_movement:
                    continue
                elif f_dict:
                    yield move_log.get_dict_data(recode_flag='database', outer_cur=cur)
                else:
                    yield move_log.get_tuple_data()
        if outer_cur:
            yield from _wrapper(outer_cur)
        else:
            with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
                yield from _wrapper(db.cursor())

    def new_batch_apply(self, batched_blocks, outer_cur=None):
        def _wrapper(cur):
            for block in batched_blocks:
                for tx in block.txs:
                    move_log = read_txhash2log(tx.hash, cur)
                    if move_log:
                        # User操作の記録
                        self.db_balance += move_log.movement
                        if tx.hash in self.memory_movement:
                            del self.memory_movement[tx.hash]
                        # log.debug("Already recoded log {}".format(tx))
                    elif tx.hash in self.memory_movement:
                        # db_balanceに追加
                        _type, movement, _time = self.memory_movement[tx.hash].get_tuple_data()
                        self.db_balance += movement
                        # memory_movementから削除
                        del self.memory_movement[tx.hash]
                        # insert_log
                        insert_log(movement, cur, _type, _time, tx.hash)
        if outer_cur:
            _wrapper(outer_cur)
        else:
            with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
                _wrapper(db.cursor())
                db.commit()

    def affect_new_tx(self, tx, outer_cur=None):
        def _wrapper(cur):
            movement = Accounting()
            # send_from_applyで登録済み
            if tx.hash in self.memory_movement:
                return
            # memory_movementに追加
            for txhash, txindex in tx.inputs:
                input_tx = tx_builder.get_tx(txhash)
                address, coin_id, amount = input_tx.outputs[txindex]
                user = read_address2user(address, cur)
                if user is not None:
                    if tx.type == C.TX_POS_REWARD:
                        user = C.ANT_MINING
                    # throw staking reward to @Mining
                    movement[user][coin_id] -= amount
                    # movement[C.ANT_OUTSIDE] += balance
            for address, coin_id, amount in tx.outputs:
                user = read_address2user(address, cur)
                if user is not None:
                    if tx.type == C.TX_POS_REWARD:
                        user = C.ANT_MINING
                    # throw staking reward to @Mining
                    movement[user][coin_id] += amount
                    # movement[C.ANT_OUTSIDE] -= balance
            # check
            movement.cleanup()
            if len(movement) == 0:
                return  # 無関係である
            move_log = MoveLog(tx.hash, tx.type, movement, tx.time, tx)
            self.memory_movement[tx.hash] = move_log
            log.debug("Affect account new tx. {}".format(tx))
        if outer_cur:
            _wrapper(outer_cur)
        else:
            with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
                _wrapper(db.cursor())


class BlockBuilderError(Exception):
    pass


# ファイル読み込みと同時に作成
builder = ChainBuilder()
# TXの管理
tx_builder = TransactionBuilder()
# User情報
user_account = UserAccount()


__all__ = [
    "db_config",
    "builder",
    "tx_builder",
    "user_account"
]
