from bc4py.config import C, V, P
from bc4py.chain.utils import signature2bin, bin2signature
from bc4py.chain.tx import TX
from bc4py.chain.block import Block
from bc4py.user import CoinObject, UserCoins
from bc4py.database.account import *
from bc4py.database.create import closing, create_db
import leveldb
import struct
import weakref
import os
import logging
import threading
import bjson
from binascii import hexlify, unhexlify
import time
import pickle

# http://blog.livedoor.jp/wolf200x/archives/53052954.html
# https://github.com/happynear/py-leveldb-windows

struct_block = struct.Struct('>II32s80sBI')
struct_tx = struct.Struct('>4I')
struct_address = struct.Struct('>40s32sB')
struct_address_idx = struct.Struct('>IQ?')


ZERO_FILLED_HASH = b'\x00' * 32


class DataBase:
    # 直接読み出さない
    def __init__(self, dirs, sync=True, timeout=None):
        self.dirs = dirs
        self.sync = sync
        self.timeout = timeout
        self.event = threading.Event()
        self.event.set()
        # already used => LevelDBError
        if not os.path.exists(dirs):
            os.mkdir(dirs)
        self._block = leveldb.LevelDB(os.path.join(dirs, 'block'), create_if_missing=True)
        self._tx = leveldb.LevelDB(os.path.join(dirs, 'tx'), create_if_missing=True)
        self._used_index = leveldb.LevelDB(os.path.join(dirs, 'used-index'), create_if_missing=True)
        self._block_index = leveldb.LevelDB(os.path.join(dirs, 'block-index'), create_if_missing=True)
        self._address_index = leveldb.LevelDB(os.path.join(dirs, 'address-index'), create_if_missing=True)
        self._coins = leveldb.LevelDB(os.path.join(dirs, 'coins'), create_if_missing=True)
        self._contract = leveldb.LevelDB(os.path.join(dirs, 'contract'), create_if_missing=True)
        self.batch = None
        self.batch_thread = None
        logging.debug('Create database connection. {}'.format(dirs))

    def __del__(self):
        del self._block, self._tx, self._used_index, self._block_index, self._address_index,\
            self._coins, self._contract, self.batch, self.batch_thread
        logging.info("Close database connection.")

    def batch_create(self):
        assert self.batch is None, 'batch is already start.'
        self.event.wait(timeout=self.timeout)
        self.event.clear()
        self.batch = {
            '_block': dict(),
            '_tx': dict(),
            '_used_index': dict(),
            '_block_index': dict(),
            '_address_index': dict(),
            '_coins': dict(),
            '_contract': dict()}
        self.batch_thread = threading.current_thread()
        logging.debug("Create database batch.")

    def batch_commit(self):
        assert self.batch, 'Not created batch.'
        for name, memory in self.batch.items():
            new_data = leveldb.WriteBatch()
            for k, v in memory.items():
                new_data.Put(k, v)
            getattr(self, name).Write(new_data, sync=self.sync)
        self.batch = None
        self.batch_thread = None
        self.event.set()
        logging.debug("Commit database.")

    def batch_rollback(self):
        self.batch = None
        self.batch_thread = None
        self.event.set()
        logging.debug("Rollback database.")

    def is_batch_thread(self):
        return self.batch and self.batch_thread is threading.current_thread()

    def read_block(self, blockhash):
        if self.is_batch_thread() and blockhash in self.batch['_block']:
            b = self.batch['_block'][blockhash]
        else:
            b = self._block.Get(blockhash, default=None)
        if b is None:
            return None
        b = bytes(b)
        height, _time, work, b_block, flag, tx_len = struct_block.unpack_from(b)
        idx = struct_block.size
        assert len(b) == idx+tx_len, 'Not correct size. [{}={}]'.format(len(b), idx+tx_len)
        block = Block(binary=b_block)
        block.height = height
        block.work_hash = work
        block.flag = flag
        block.txs = [self.read_tx(b[idx+32*i:idx+32*i+32]) for i in range(tx_len//32)]
        return block

    def read_block_hash(self, height):
        b_height = height.to_bytes(4, 'big')
        if self.is_batch_thread() and b_height in self.batch['_block_index']:
            return self.batch['_block_index'][b_height]
        else:
            b = self._block_index.Get(b_height, default=None)
            if b is None:
                return None
            return bytes(b)

    def read_block_hash_iter(self, start_height=0):
        f_batch = self.is_batch_thread()
        batch_copy = self.batch['_block_index'].copy() if self.batch else dict()
        for b_height, blockhash in self._block_index.RangeIter(key_from=start_height.to_bytes(4, 'big')):
            # height, blockhash
            b_height = bytes(b_height)
            blockhash = bytes(blockhash)
            if f_batch and b_height in batch_copy:
                yield int.from_bytes(b_height, 'big'), batch_copy[b_height]
                del batch_copy[b_height]
            else:
                yield int.from_bytes(b_height, 'big'), blockhash
        if f_batch:
            for b_height, blockhash in sorted(batch_copy.items(), key=lambda x: x[0]):
                yield int.from_bytes(b_height, 'big'), blockhash

    def read_tx(self, txhash):
        if self.is_batch_thread() and txhash in self.batch['_tx']:
            b = self.batch['_tx'][txhash]
        else:
            b = self._tx.Get(txhash, default=None)
        if b is None:
            return None
        b = bytes(b)
        height, _time, bin_len, sign_len = struct_tx.unpack_from(b)
        b_tx = b[16:16+bin_len]
        b_sign = b[16+bin_len:16+bin_len+sign_len]
        assert len(b) == 16+bin_len+sign_len, 'Wrong len [{}={}]'\
            .format(len(b), 16+bin_len+sign_len)
        tx = TX(binary=b_tx)
        tx.height = height
        tx.signature = bin2signature(b_sign)
        return tx

    def read_usedindex(self, txhash):
        if self.is_batch_thread() and txhash in self.batch['_used_index']:
            b = self.batch['_used_index'][txhash]
        else:
            d = self._used_index.Get(txhash, default=None)
            if d is None:
                return set()
            return bytes(d)

    def read_address_idx(self, address, txhash, index):
        k = address.encode() + txhash + index.to_bytes(1, 'big')
        if self.is_batch_thread() and k in self.batch['_address_index']:
            b = self.batch['_address_index'][k]
        else:
            b = self._address_index.Get(k)
        if b is None:
            return None
        b = bytes(b)
        # coin_id, amount, f_used
        return struct_address_idx.unpack(b)

    def read_address_idx_iter(self, address):
        f_batch = self.is_batch_thread()
        batch_copy = self.batch['_address_index'].copy() if self.batch else dict()
        b_address = address.encode()
        for k, v in self._address_index.RangeIter(
                key_from=b_address+b'\x00'*(32+1),
                key_to=b_address+b'\xff'*(32+1)):
            k, v = bytes(k), bytes(v)
            # address, txhash, index, coin_id, amount, f_used
            if f_batch and k in batch_copy:
                yield struct_address.unpack(k) + struct_address_idx.unpack(batch_copy[k])
                del batch_copy[k]
            else:
                yield struct_address.unpack(k) + struct_address_idx.unpack(v)
        if f_batch:
            for k, v in sorted(batch_copy.items(), key=lambda x: x[0]):
                if k.startswith(b_address):
                    yield struct_address.unpack(k) + struct_address_idx.unpack(v)

    def read_coins_iter(self, coin_id):
        f_batch = self.is_batch_thread()
        batch_copy = self.batch['_coins'].copy() if self.batch else dict()
        b_coin_id = coin_id.to_bytes(4, 'big')
        struct_coins = struct.Struct('>II')
        for k, v in self._coins.RangeIter(
                key_from=b_coin_id+b'\x00'*4,
                key_to=b_coin_id+b'\xff'*4):
            k, v = bytes(k), bytes(v)
            # coin_id, index, txhash
            if f_batch and k in batch_copy:
                yield struct_coins.unpack(k) + (batch_copy[k],)
                del batch_copy[k]
            else:
                yield struct_coins.unpack(k) + (v,)
        if f_batch:
            for k, v in sorted(batch_copy.items(), key=lambda x: x[0]):
                if k.startswith(b_coin_id):
                    yield struct_coins.unpack(k) + (v,)

    def read_contract_iter(self, c_address):
        f_batch = self.is_batch_thread()
        batch_copy = self.batch['_contract'].copy() if self.batch else dict()
        b_c_address = c_address.encode()
        struct_construct_key = struct.Struct('>40sI')
        struct_construct_value = struct.Struct('>32s32s')
        for k, v in self._contract.RangeIter(
                key_from=b_c_address+b'\x00'*4,
                key_to=b_c_address+b'\xff'*4):
            k, v = bytes(k), bytes(v)
            # c_address, index, start_hash, finish_hash
            if f_batch and k in batch_copy:
                yield struct_construct_key.unpack(k) + struct_construct_value.unpack(batch_copy[k])
                del batch_copy[k]
            else:
                yield struct_construct_key.unpack(k) + struct_construct_value.unpack(v)
        if f_batch:
            for k, v in sorted(batch_copy.items(), key=lambda x: x[0]):
                if k.startswith(b_c_address):
                    yield struct_construct_key.unpack(k) + struct_construct_value.unpack(v)

    def write_block(self, block):
        assert self.is_batch_thread(), 'Not created batch.'
        b_tx = b''.join(tx.hash for tx in block.txs)
        tx_len = len(b_tx)
        if block.work_hash is None:
            block.update_pow()
        b = struct_block.pack(block.height, block.time, block.work_hash, block.b, block.flag, tx_len)
        b += b_tx
        self.batch['_block'][block.hash] = b
        b_height = block.height.to_bytes(4, 'big')
        self.batch['_block_index'][b_height] = block.hash
        logging.debug("Insert new block {}".format(block))

    def write_tx(self, tx):
        assert self.is_batch_thread(), 'Not created batch.'
        bin_len = len(tx.b)
        b_sign = signature2bin(tx.signature)
        sign_len = len(b_sign)
        b = struct_tx.pack(tx.height, tx.time, bin_len, sign_len)
        b += tx.b + b_sign
        self.batch['_tx'][tx.hash] = b
        logging.debug("Insert new tx {}".format(tx))

    def write_usedindex(self, txhash, usedindex):
        assert self.is_batch_thread(), 'Not created batch.'
        assert isinstance(usedindex, set), 'Unsedindex is set.'
        self.batch['_used_index'][txhash] = bytes(sorted(usedindex))

    def write_address_idx(self, address, txhash, index, coin_id, amount, f_used):
        assert self.is_batch_thread(), 'Not created batch.'
        k = address.encode() + txhash + index.to_bytes(1, 'big')
        v = struct_address_idx.pack(coin_id, amount, f_used)
        self.batch['_address_index'][k] = v
        logging.debug("Insert new address idx {}".format(address))

    def write_coins(self, coin_id, index, txhash):
        assert self.is_batch_thread(), 'Not created batch.'
        k = coin_id.to_bytes(4, 'big') + index.to_bytes(4, 'big')
        self.batch['_coins'][k] = txhash
        logging.debug("Insert new coins id={}".format(coin_id))

    def write_contract(self, c_address, index, start_hash, finish_hash):
        assert self.is_batch_thread(), 'Not created batch.'
        k = c_address.encode() + index.to_bytes(4, 'big')
        v = start_hash + finish_hash
        self.batch['_contract'][k] = v
        logging.debug("Insert new contract {} {}".format(c_address, index))


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
        self.db = None
        try:
            self.db = DataBase(os.path.join(V.DB_HOME_DIR, 'db'))
        except BaseException:
            pass
        # levelDBのStreamHandlerを削除
        logging.getLogger().handlers.clear()

    def set_database_path(self):
        try:
            self.db = DataBase(os.path.join(V.DB_HOME_DIR, 'db'))
            logging.info("Connect database.")
        except leveldb.LevelDBError:
            logging.warning("Already connect database.")
        except BaseException as e:
            logging.debug("Failed connect database, {}.".format(e))

    def init(self, genesis_block: Block):
        assert self.db, 'Why database connection failed?'
        # GenesisBlockか確認
        t = time.time()
        try:
            if genesis_block.hash != self.db.read_block_hash(0):
                raise BlockBuilderError("Don't match genesis hash [{}!={}]".format(
                    hexlify(genesis_block.hash).decode(), hexlify(self.db.read_block_hash(0).decode())))
            elif genesis_block != self.db.read_block(genesis_block.hash):
                raise BlockBuilderError("Don't match genesis binary [{}!={}]".format(
                    hexlify(genesis_block.b).decode(), hexlify(self.db.read_block(genesis_block.hash).b).decode()))
        except BaseException:
            # GenesisBlockしか無いのでDummyBlockを入れる処理
            self.root_block = Block()
            self.root_block.hash = b'\xff' * 32
            self.chain[genesis_block.hash] = genesis_block
            self.best_chain = [genesis_block]
            self.best_block = genesis_block
            logging.info("Set dummy block. GenesisBlock={}".format(genesis_block))
            user_account.init()
            return

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
            if len(batch_blocks) > self.cashe_limit:
                user_account.new_batch_apply(batch_blocks)
                batch_blocks.clear()
                logging.debug("UserAccount batched at {} height.".format(block.height))
        # import from starter.dat
        self.root_block = before_block
        self.load_starter()
        batch_blocks.append(self.best_block)
        self.chain[self.best_block.hash] = self.best_block
        self.best_chain = [self.best_block]
        # UserAccount update
        user_account.new_batch_apply(batch_blocks)
        user_account.init()
        logging.info("Init finished, last block is {} {}Sec"
                     .format(before_block, round(time.time()-t, 3)))

    def save_starter(self):
        with open(os.path.join(V.DB_HOME_DIR, 'db', 'starter.dat'), mode='bw') as fp:
            pickle.dump(self.best_chain, fp, protocol=4)

    def load_starter(self):
        try:
            with open(os.path.join(V.DB_HOME_DIR, 'db', 'starter.dat'), mode='br') as fp:
                for block in pickle.load(fp):
                    if self.root_block.hash == block.previous_hash:
                        self.best_block = block
                        break
                else:
                    raise Exception('Cannot init, not found next block. root={}'.format(self.root_block))
        except FileNotFoundError:
            return list()

    def get_best_chain(self, best_block=None):
        assert self.root_block, 'Do not init.'
        if best_block:
            best_chain = [best_block]
            previous_hash = best_block.previous_hash
            while self.root_block.hash != previous_hash:
                if previous_hash not in self.chain:
                    raise BlockBuilderError('Cannot find previousHash, may not main-chain. {}'
                                            .format(hexlify(previous_hash).decode()))
                block = self.chain[previous_hash]
                previous_hash = block.previous_hash
                best_chain.append(block)
            return best_block, best_chain
        # BestBlockがchainにおける
        best_diff = 0.0
        best_block = None
        best_chain = list()
        for block in self.chain.values():
            if block in best_chain:
                continue
            if not block.difficulty:
                block.bits2target()
                block.target2diff()
            tmp_best_diff = block.difficulty
            tmp_best_block = block
            tmp_best_chain = [block]
            while block.previous_hash in self.chain:
                block = self.chain[block.previous_hash]
                if not block.difficulty:
                    block.bits2target()
                    block.target2diff()
                tmp_best_diff += block.difficulty
                tmp_best_chain.append(block)
            else:
                if self.root_block.hash != block.previous_hash:
                    continue
            if best_diff > tmp_best_diff:
                continue
            best_diff = tmp_best_diff
            best_block = tmp_best_block
            best_chain = tmp_best_chain
        # txのheightを揃える
        for block in best_chain:
            for tx in block.txs:
                tx.height = block.height
        # best_chain = [<height=n>, <height=n-1>, ...]
        return best_block, best_chain

    def batch_apply(self, force=False):
        # 無チェックで挿入するから要注意
        if not force and self.cashe_limit > len(self.chain):
            return
        # cashe許容量を上回っているので記録
        self.db.batch_create()
        logging.debug("Start batch apply. chain={} force={}".format(len(self.chain), force))
        best_chain = self.best_chain # .copy()
        batch_count = self.batch_size
        batched_blocks = list()
        try:
            block = None
            while batch_count > 0 and len(best_chain) > 0:
                batch_count -= 1
                block = best_chain.pop()  # 古いものから順に
                batched_blocks.append(block)
                self.db.write_block(block)  # Block
                for tx in block.txs:
                    self.db.write_tx(tx)  # TX
                    # inputs
                    for index, (txhash, txindex) in enumerate(tx.inputs):
                        # DataBase内でのみのUsedIndexを取得
                        usedindex = self.db.read_usedindex(txhash)
                        if txindex in usedindex:
                            raise BlockBuilderError('Already used index? {}:{}'
                                                    .format(hexlify(txhash).decode(), txindex))
                        usedindex.add(txindex)
                        self.db.write_usedindex(txhash, usedindex)  # UsedIndex update
                        input_tx = tx_builder.get_tx(txhash)
                        address, coin_id, amount = input_tx.outputs[txindex]
                        # TODO: 必要なAddressだけにしたい
                        self.db.write_address_idx(address, txhash, txindex, coin_id, amount, True)  # address
                    # outputs
                    for index, (address, coin_id, amount) in enumerate(tx.outputs):
                        # TODO: 必要なAddressだけにしたい
                        self.db.write_address_idx(address, tx.hash, index, coin_id, amount, False)  # Address
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
                        address, mint_id, amount = tx.outputs[0]
                        assert mint_id != 0, 'Mint_id is not 0. {}'.format(mint_id)
                        next_index = 0
                        for dummy in self.db.read_coins_iter(mint_id):
                            next_index += 1
                        self.db.write_coins(mint_id, next_index, tx.hash)

                    elif tx.type == C.TX_CREATE_CONTRACT:
                        c_address, c_bin, c_cs = bjson.loads(tx.message)
                        start_hash, finish_hash = tx.hash, ZERO_FILLED_HASH
                        self.db.write_contract(c_address, 0, start_hash, finish_hash)

                    elif tx.type == C.TX_START_CONTRACT:
                        c_address, c_data = bjson.loads(tx.message)
                        next_index = 0
                        for dummy in self.db.read_contract_iter(c_address):
                            next_index += 1
                        assert next_index > 0, 'Not created contract.'
                        start_hash, finish_hash = tx.hash, ZERO_FILLED_HASH
                        self.db.write_contract(c_address, next_index, start_hash, finish_hash)

                    elif tx.type == C.TX_FINISH_CONTRACT:
                        c_status, start_hash, cs_diff = bjson.loads(tx.message)
                        # 同一BlockからStartTXを探し..
                        for start_tx in block.txs:
                            if start_tx.hash == start_hash:
                                break
                        else:
                            raise BlockBuilderError('Not found start tx. {}'.format(tx))
                        c_address, c_data, c_redeem = bjson.loads(start_tx.message)
                        # 次のIndexを取得する
                        for c_address, index, _start_hash, finish_hash in self.db.read_contract_iter(c_address):
                            if start_hash == _start_hash and finish_hash == ZERO_FILLED_HASH:
                                break  # STARTで既に挿入されているはず
                        else:
                            raise BlockBuilderError('Not found start tx on db. {}'.format(tx))
                        self.db.write_contract(c_address, index, start_hash, tx.hash)
            # block挿入終了
            self.root_block = block
            self.db.batch_commit()
            self.save_starter()
            # root_blockよりHeightの小さいBlockを消す
            for blockhash, block in self.chain.copy().items():
                if self.root_block.height >= block.height:
                    del self.chain[blockhash]
            logging.debug("Success batch {} blocks, root={}."
                          .format(len(batched_blocks), self.root_block))
            # アカウントへ反映↓
            user_account.new_batch_apply(batched_blocks)
            return batched_blocks  # [<height=n>, <height=n+1>, .., <height=n+m>]
        except BaseException as e:
            self.db.batch_rollback()
            import traceback
            traceback.print_exc()
            logging.warning("Failed batch block builder. '{}'".format(e))
            return None

    def new_block(self, block):
        # とりあえず新規に挿入
        self.chain[block.hash] = block
        # BestChainの変化を調べる
        new_best_block, new_best_chain = self.get_best_chain()
        if new_best_block == self.best_block:
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
        for index, block in enumerate(new_best_chain):
            if block not in commons:
                try: new_best_chain[index+1].next_hash = block.hash
                except IndexError: pass
                for tx in block.txs:
                    tx.height = block.height
        # 変化しているので反映する
        self.best_block, self.best_chain = new_best_block, new_best_chain
        tx_builder.affect_new_chain(
            new_best_chain=set(new_best_chain) - commons,
            old_best_chain=set(old_best_chain) - commons)

    def get_block(self, blockhash):
        if blockhash in self.chain:
            # Memoryより
            block = self.chain[blockhash]
            block.f_on_memory = True
            block.f_orphan = bool(block not in self.best_chain)
        else:
            # DataBaseより
            block = self.db.read_block(blockhash)
            if block:
                block.f_on_memory = False
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
        # BLockに存在するTXのみ保持すればよい
        self.unconfirmed = dict()  # Blockに取り込まれた事のないTX、参照保持用
        self.chained_tx = weakref.WeakValueDictionary()  # 一度でもBlockに取り込まれた事のあるTX
        self.tmp = weakref.WeakValueDictionary()  # 一時的

    def put_unconfirmed(self, tx, outer_cur=None):
        assert tx.height is None, 'Not unconfirmed tx {}'.format(tx)
        if tx.type in (C.TX_POW_REWARD, C.TX_POS_REWARD):
            return  # It is Reword tx
        elif tx.hash in self.unconfirmed:
            logging.debug('Already unconfirmed tx. {}'.format(tx))
            return
        self.unconfirmed[tx.hash] = tx
        if tx.hash in self.chained_tx:
            logging.debug('Already chained tx. {}'.format(tx))
            return
        user_account.affect_new_tx(tx, outer_cur)
        # WebSocket apiに通知
        if P.NEW_CHAIN_INFO_QUE:
            P.NEW_CHAIN_INFO_QUE.put_nowait(('tx', tx.getinfo()))

    def get_tx(self, txhash, default=None):
        if txhash in self.tmp:
            return self.tmp[txhash]
        elif txhash in self.unconfirmed:
            # unconfirmedより
            tx = self.unconfirmed[txhash]
            tx.f_on_memory = True
            assert tx.height is None, "Not unconfirmed. {}".format(tx)
        elif txhash in self.chained_tx:
            # Memoryより
            tx = self.chained_tx[txhash]
            tx.f_on_memory = True
            assert tx.height is not None, "Is unconfirmed. {}".format(tx)
        else:
            # Databaseより
            tx = builder.db.read_tx(txhash)
            if tx:
                tx.f_on_memory = False
                self.tmp[txhash] = tx
            else:
                return default
        return tx

    def __contains__(self, item):
        return bool(self.get_tx(item.hash))

    def affect_new_chain(self, old_best_chain, new_best_chain):
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
        # 時間切れを起こしたUnconfirmedを消す
        limit = int(time.time() - V.BLOCK_GENESIS_TIME - C.ACCEPT_MARGIN_TIME)
        for txhash, tx in self.unconfirmed.copy().items():
            if limit > tx.deadline:
                del self.unconfirmed[txhash]


class UserAccount:
    def __init__(self):
        self.db_balance = UserCoins()
        # {txhash: (_type, movement, _time),..}
        self.memory_movement = dict()

    def init(self):
        with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
            cur = db.cursor()
            memory_sum = UserCoins()
            for move_log in read_log_iter(cur):
                memory_sum += move_log.movement
            self.db_balance += memory_sum

    def get_balance(self, confirm=6):
        assert confirm < builder.cashe_limit - builder.batch_size, 'Too few cashe size.'
        assert builder.best_block, 'Not DataBase init.'
        # DataBase
        balance = self.db_balance.copy()
        with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
            cur = db.cursor()
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
                                        balance.add_coins(user, coin_id, amount)
                                else:
                                    balance.add_coins(user, coin_id, amount)
            # Unconfirmed
            for tx in tx_builder.unconfirmed.values():
                move_log = read_txhash2log(tx.hash, cur)
                if move_log is None:
                    if tx.hash in self.memory_movement:
                        move_log = self.memory_movement[tx.hash]
                if move_log:
                    for user, coins in move_log.movement.items():
                        for coin_id, amount in coins:
                            if amount < 0:
                                balance.add_coins(user, coin_id, amount)
        return balance

    def move_balance(self, _from, _to, coins, outer_cur=None):
        assert isinstance(coins, CoinObject),  'coins is CoinObject.'
        with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
            cur = outer_cur or db.cursor()
            try:
                # DataBaseに即書き込む(Memoryに入れない)
                movements = UserCoins()
                movements[_from] -= coins
                movements[_to] += coins
                txhash = insert_log(movements, cur)
                if outer_cur is None:
                    db.commit()
                self.db_balance += movements
                return txhash
            except BaseException:
                db.rollback()

    def get_movement_iter(self, start=0, f_dict=False):
        count = 0
        with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
            cur = db.cursor()
            # Unconfirmed
            for tx in sorted(tx_builder.unconfirmed.values(), key=lambda x: x.time, reverse=True):
                move_log = read_txhash2log(tx.hash, cur)
                if move_log is None:
                    if tx.hash in self.memory_movement:
                        move_log = self.memory_movement[tx.hash]
                else:
                    if tx.hash in self.memory_movement:
                        move_log.pointer = self.memory_movement[tx.hash].pointer
                if move_log:
                    if count >= start:
                        if f_dict:
                            yield move_log.get_dict_data(cur)
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
                            move_log.pointer = self.memory_movement[tx.hash].pointer
                    if move_log:
                        if count >= start:
                            if f_dict:
                                yield move_log.get_dict_data(cur)
                            else:
                                yield move_log.get_tuple_data()
                        count += 1
            # DataBase
            for move_log in read_log_iter(cur, start - count):
                # TRANSFERなど はDBとMemoryの両方に存在する
                if move_log.txhash in self.memory_movement:
                    continue
                elif f_dict:
                    yield move_log.get_dict_data(cur)
                else:
                    yield move_log.get_tuple_data()

    def new_batch_apply(self, batched_blocks):
        with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
            cur = db.cursor()
            for block in batched_blocks:
                for tx in block.txs:
                    move_log = read_txhash2log(tx.hash, cur)
                    if move_log:
                        # User操作の記録
                        self.db_balance += move_log.movement
                        if tx.hash in self.memory_movement:
                            del self.memory_movement[tx.hash]
                        logging.debug("Already recoded log {}".format(tx))
                    elif tx.hash in self.memory_movement:
                        # db_balanceに追加
                        _type, movement, _time = self.memory_movement[tx.hash].get_tuple_data()
                        self.db_balance += movement
                        # memory_movementから削除
                        del self.memory_movement[tx.hash]
                        # insert_log
                        insert_log(movement, cur, _type, _time, tx.hash)
            db.commit()

    def affect_new_tx(self, tx, outer_cur=None):
        with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
            cur = outer_cur or db.cursor()
            movement = UserCoins()
            # send_from_applyで登録済み
            if tx.hash in self.memory_movement:
                return
            # memory_movementに追加
            for txhash, txindex in tx.inputs:
                input_tx = tx_builder.get_tx(txhash)
                address, coin_id, amount = input_tx.outputs[txindex]
                user = read_address2user(address, cur)
                if user is not None:
                    movement.add_coins(user, coin_id, -1 * amount)
            for address, coin_id, amount in tx.outputs:
                user = read_address2user(address, cur)
                if user is not None:
                    movement.add_coins(user, coin_id, amount)
            # check
            if len(movement.users) == 0:
                return  # 無関係である
            move_log = MoveLog(tx.hash, tx.type, movement, tx.time, True, tx)
            self.memory_movement[tx.hash] = move_log
            logging.debug("Affect account new tx. {}".format(tx))


class BlockBuilderError(BaseException):
    pass


# ファイル読み込みと同時に作成
builder = ChainBuilder()
# TXの管理
tx_builder = TransactionBuilder()
# User情報
user_account = UserAccount()
