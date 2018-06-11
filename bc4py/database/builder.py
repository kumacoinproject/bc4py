from bc4py.config import C, V
from bc4py.chain.utils import signature2bin, bin2signature
from bc4py.chain.tx import TX
from bc4py.chain.block import Block
from bc4py.user import CoinObject
from bc4py.database.account import *
from bc4py.database.create import closing, create_db
import leveldb
import struct
import weakref
import os
import logging
import threading
import bjson
from binascii import hexlify
import time
from copy import deepcopy

# http://blog.livedoor.jp/wolf200x/archives/53052954.html
# https://github.com/happynear/py-leveldb-windows

struct_block = struct.Struct('>II32s80sBI')
struct_tx = struct.Struct('>4I')
struct_address = struct.Struct('>40s32sB')
struct_address_idx = struct.Struct('>IQ?')


ADDRESS_INDEX = True
ZERO_FILLED_HASH = b'\x00' * 32


class DataBase:
    # 直接読み出さない
    def __init__(self, dirs, sync=True, timeout=None):
        self.dirs = dirs
        self.sync = sync
        self.timeout = timeout
        self.event = threading.Event()
        # already used => LevelDBError
        self._block = leveldb.LevelDB(os.path.join(dirs, 'block'))
        self._tx = leveldb.LevelDB(os.path.join(dirs, 'tx'))
        self._used_index = leveldb.LevelDB(os.path.join(dirs, 'used-index'))
        self._block_index = leveldb.LevelDB(os.path.join(dirs, 'block-index'))
        self._address_index = leveldb.LevelDB(os.path.join(dirs, 'address-index'))
        self._coins = leveldb.LevelDB(os.path.join(dirs, 'coins'))
        self._contract = leveldb.LevelDB(os.path.join(dirs, 'contract'))
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
            b = self._block.Get(blockhash)
        height, _time, work, b_block, flag, tx_len = struct_block.unpack_from(b)
        idx = struct_block.size
        assert len(b) == idx+tx_len, 'Not correct size. [{}={}]'.format(len(b), idx+tx_len)
        block = Block(binary=b_block)
        block.height = height
        block.work_hash = work
        block.flag = flag
        for i in range(tx_len//32):
            txhash = b[idx+32*i:idx+32*i+32]
            block.txs = self.read_tx(txhash)
        return block

    def read_block_hash(self, height):
        if self.is_batch_thread() and height in self.batch['_block_index']:
            return self.batch['_block_index'][height.to_bytes(4, 'big')]
        else:
            return self._block_index.Get(height.to_bytes(4, 'big'))

    def read_block_hash_iter(self, start_height=0):
        f_batch = self.is_batch_thread()
        batch_copy = self.batch['_block_index'].copy() if self.batch else dict()
        for b_height, blockhash in self._block_index.RangeIter(key_from=start_height.to_bytes(4, 'big')):
            # height, blockhash
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
            b = self._tx.Get(txhash)
        height, _time, bin_len, sign_len = struct_tx.unpack_from(b)
        b_tx = b[20:20+bin_len]
        b_sign = b[20+bin_len:20+bin_len+sign_len]
        assert len(b) == 20+bin_len+sign_len, 'Wrong len [{}={}]'\
            .format(len(b), 20+bin_len+sign_len)
        tx = TX(binary=b_tx)
        tx.height = height
        tx.signature = bin2signature(b_sign)
        return tx

    def read_usedindex(self, txhash):
        if self.is_batch_thread() and txhash in self.batch['_used_index']:
            b = self.batch['_used_index'][txhash]
        else:
            b = self._used_index.Get(txhash)
        return set(b)

    def read_address_idx(self, address, txhash, index):
        k = address.encode() + txhash + index.to_bytes(1, 'big')
        if self.is_batch_thread() and k in self.batch['_address_index']:
            b = self.batch['_address_index'][k]
        else:
            b = self._address_index.Get(k)
        # coin_id, amount, f_used
        return struct_address_idx.unpack(b)

    def read_address_idx_iter(self, address):
        f_batch = self.is_batch_thread()
        batch_copy = self.batch['_address_index'].copy() if self.batch else dict()
        b_address = address.encode()
        for k, v in self._address_index.RangeIter(
                key_from=b_address+b'\x00'*(32+1),
                key_to=b_address+b'\xff'*(32+1)):
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
    def __init__(self, cashe_limit=100, batch_size=20):
        assert cashe_limit > batch_size, 'cashe_limit > batch_size.'
        self.chain = dict()
        self.root_block = None  # 最後に挿入されたBlock
        self.cashe_limit = cashe_limit
        self.batch_size = batch_size
        self.best_chain_cashe = None
        self.get_chained_txs_cashe = None
        self.db = None
        try:
            self.db = DataBase(os.path.join(V.DB_HOME_DIR, 'db'))
        except leveldb.LevelDBError:
            logging.warning("Already connect database.")
        except BaseException:
            pass

    def init(self, genesis_block: Block):
        # GenesisBlockか確認
        t = time.time()
        try:
            if genesis_block.hash != self.db.read_block_hash(0):
                raise BlockBuilderError("Don't match genesis hash [{}!={}]".format(
                    hexlify(genesis_block.hash), hexlify(self.db.read_block_hash(0))))
            elif genesis_block != self.db.read_block(genesis_block.hash):
                raise BlockBuilderError("Don't match genesis binary [{}!={}]".format(
                    hexlify(genesis_block.b), hexlify(self.db.read_block(genesis_block.hash).b)))
        except KeyError:
            # GenesisBlockしか無いのでDummyBlockを入れる処理
            self.root_block = Block()
            self.root_block.hash = b'\xff' * 32
            self.chain[genesis_block.hash] = genesis_block
            logging.info("Set dummy block. GenesisBlock={}".format(genesis_block))
            return

        # 0HeightよりBlockを取得して確認
        before_block = genesis_block
        batch_blocks = list()
        for height, blockhash in self.db.read_block_hash_iter():
            block = self.db.read_block(blockhash)
            if block.previous_hash != before_block.hash:
                raise BlockBuilderError("PreviousHash != BlockHash [{}!={}]".format(block, before_block))
            elif block.height != height:
                raise BlockBuilderError("BlockHeight != DBHeight [{}!={}]".format(block.height, height))
            elif height != before_block.height+1:
                raise BlockBuilderError("DBHeight != BeforeHeight+1 [{}!={}+1]".format(height, before_block.height))
            for tx in block.txs:
                if tx.height != height:
                    raise BlockBuilderError("TXHeight != BlockHeight [{}!{}]".format(tx.height, height))
                # inputs
                for txhash, txindex in tx.inputs:
                    input_tx = self.db.read_tx(txhash)
                    address, coin_id, amount = input_tx.outputs[txindex]
                    _coin_id, _amount, f_used = self.db.read_address_idx(address, txhash, txindex)
                    if coin_id != _coin_id or amount != _amount:
                        raise BlockBuilderError("Inputs, coin_id != _coin_id or amount != _amount [{}!{}] [{}!={}]"
                                                .format(coin_id, _coin_id, amount, _amount))
                    elif txindex not in input_tx.used_index:
                        raise BlockBuilderError("TXIndex in InputIndex [{} not in {}]"
                                                .format(txindex, input_tx.used_index))
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
            if block.height % 100 == 1:
                user_account.update(batch_blocks)
                batch_blocks.clear()
                logging.debug("UserAccount batched at {} height.".format(block.height))
        # UserAccount update
        user_account.update(batch_blocks)
        batch_blocks.clear()
        self.root_block = before_block
        # ここまでにErrorがあったらFixしてみる
        # それでもダメなら削除して再同期すること
        logging.info("Init finished, last block is {} {}Sec"
                     .format(before_block, round(time.time()-t, 3)))

    def get_best_chain(self):
        assert self.root_block, 'Do not init.'
        if self.best_chain_cashe:
            return self.best_chain_cashe
        best_diff = 0.0
        best_block = None
        best_chain = list()
        for blockhash, block in self.chain.items():
            if block in best_chain:
                continue
            tmp_best_diff = block.difficulty
            tmp_best_block = block
            tmp_best_chain = [block]
            while block.previous_hash in self.chain:
                block = self.chain[block.previous_hash]
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
            for tx in block:
                tx.height = block.height
        # best_chain = [<height=n>, <height=n-1>, ...]
        self.best_chain_cashe = (best_block, best_chain)
        return best_block, best_chain

    def get_chained_txs(self):
        if self.get_chained_txs_cashe:
            return self.get_chained_txs_cashe
        chained_txs = set()
        best_chain = self.get_best_chain()[1]
        for block in best_chain:
            chained_txs.difference_update(tx for tx in block.txs)
        self.get_chained_txs_cashe = chained_txs
        return chained_txs

    def batch_apply(self, force=False):
        # 無チェックで挿入するから要注意
        if not force and self.cashe_limit > len(self.chain):
            return
        # cashe許容量を上回っているので記録
        self.db.batch_create()
        logging.debug("Start batch apply. chain={} force={}".format(len(self.chain), force))
        best_block, best_chain = self.get_best_chain()
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
                    tx.height = block.height
                    self.db.write_tx(tx)  # TX
                    # inputs
                    for index, (txhash, txindex) in enumerate(tx.inputs):
                        # DataBase内でのみのUsedIndexｗｐ取得
                        input_tx_tmp = self.db.read_tx(txhash)
                        used = set(input_tx_tmp.used_index)
                        if txindex in used:
                            raise BlockBuilderError('Already used index? {}:{}'
                                                    .format(hexlify(txhash).decode(), txindex))
                        used.add(txindex)
                        input_tx = tx_box.get_tx(txhash)
                        input_tx.used_index = bytes(sorted(used))
                        self.db.write_tx(input_tx)  # UsedIndex update
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
            # root_blockよりHeightの小さいBlockを消す
            for blockhash, block in self.chain.items():
                if self.root_block.height >= block.height:
                    del self.chain[blockhash]
            logging.debug("Success batch {} blocks, root={}."
                          .format(len(batched_blocks), self.root_block))
            # アカウントへ反映↓
            user_account.update(batched_blocks)
            return batched_blocks  # [<height=n>, <height=n+1>, .., <height=n+m>]
        except BaseException as e:
            self.db.batch_rollback()
            import traceback
            traceback.print_exc()
            logging.warning("Failed batch block builder. '{}'".format(e))
            return None

    def new_block(self, block):
        self.chain[block.hash] = block
        self.best_chain_cashe = None
        self.get_chained_txs_cashe = None
        for tx in block.txs:
            tx.height = block.height
        tx_box.affect_new_block(block)

    def get_block(self, blockhash):
        # memoryに無いか調べる
        if blockhash in self.chain:
            best_block, best_chain = self.get_best_chain()
            block = self.chain[blockhash]
            block.f_on_memory = True
            block.f_orphan = False if block in best_chain else True
        else:
            block = self.db.read_block(blockhash)
            block.f_on_memory = False
            block.f_orphan = False
        return block


class UserCoins:
    def __repr__(self):
        return "<User {}>".format(self.users)

    def __init__(self, users=None):
        self.users = users or dict()

    def copy(self):
        return UserCoins(deepcopy(self.users))

    def add_coins(self, user, coin_id, amount):
        if user in self.users:
            self.users[user][coin_id] += amount
        else:
            self.users[user] = CoinObject(coin_id, amount)

    def __getitem__(self, item):
        if item in self.users:
            return self.users[item]
        return None

    def __add__(self, other):
        new = dict()
        for u in set(self.users) | set(other.users):
            new[u] = CoinObject()
            if u in self.users:
                new[u] += self.users[u]
            if u in other:
                new[u] += other[u]
        return UserCoins(new)


class UserAccount:
    def __init__(self):
        # ユーザーと関係あるAddress
        self.db_balance = UserCoins()
        self.db_movement = list()  # [<height=n>, <height=n+1>, ..,<height=n+m>]

    def get_balance(self, confirm=6):
        assert confirm < builder.cashe_limit - builder.batch_size, 'Too thin cashe size.'
        # database分の残高取得
        balance = self.db_balance.copy()
        # memory分の残高取得
        best_block, best_chain = builder.get_best_chain()
        if best_block is None:
            return balance
        with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
            cur = db.cursor()
            for block in best_chain:
                if best_block.heigt - confirm < block.height:
                    continue
                for tx in block.txs:
                    for txhash, txindex in tx.inputs:
                        input_tx = tx_box.get_tx(txhash)
                        address, coin_id, amount = input_tx.outputs[txindex]
                        user = read_address2user(address, cur)
                        if user is not None:
                            balance.add_coins(user, coin_id, -1 * amount)
                    for address, coin_id, amount in tx.outputs:
                        user = read_address2user(address, cur)
                        if user is not None:
                            balance.add_coins(user, coin_id, amount)
        return balance

    def move_balance(self, _from, _to, coins, _txhash=None, _time=None):

        # TODO: move, sendfromなどどうするか、
        pass

    def get_movement_iter(self, start=0):
        # 内部の残高移動は含まない
        best_block, best_chain = builder.get_best_chain()
        db_movement = self.db_movement.copy()
        count = -1
        # on memory
        with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
            cur = db.cursor()
            for block in best_chain:
                for tx in block.txs:
                    count += 1
                    for txhash, txindex in tx.inputs:
                        input_tx = tx_box.get_tx(txhash)
                        address, coin_id, amount = input_tx.outputs[txindex]
                        user = read_address2user(address, cur)
                        if user is not None:
                            if start <= count:
                                yield tx  # TODO: 何を出すか？
                            continue
                    for address, coin_id, amount in tx.outputs:
                        user = read_address2user(address, cur)
                        if user is not None:
                            if start <= count:
                                yield tx  # TODO: 何を出すか？
                            continue
        # on database
        for txhash in reversed(db_movement):
            if start <= count:
                yield tx_box.get_tx(txhash)  # TODO: 何を出すか？
            count += 1

    def update(self, batched_blocks):
        db_movement = list()
        with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
            cur = db.cursor()
            for block in batched_blocks:
                for tx in block.txs:
                    f_movement = False
                    # db_balanceを更新
                    for txhash, txindex in tx.inputs:
                        input_tx = tx_box.get_tx(txhash)
                        address, coin_id, amount = input_tx.outputs[txindex]
                        user = read_address2user(address, cur)
                        if user is not None:
                            self.db_balance.add_coins(user, coin_id, -1 * amount)
                            f_movement = True
                    for address, coin_id, amount in tx.outputs:
                        user = read_address2user(address, cur)
                        if user is not None:
                            self.db_balance.add_coins(user, coin_id, amount)
                            f_movement = True
                    # db_movementを更新
                    if f_movement:
                        db_movement.append(tx.hash)
        # 最後にbatchされた結果を格納
        self.db_movement += db_movement


class TransactionBox:
    def __init__(self):
        # BLockに存在するTXのみ保持すればよい
        self.temporary = dict()  # Blockに取り込まれた事のないTX、参照保持用
        self.cashed = weakref.WeakValueDictionary()  # 一度でもBlockに取り込まれた事のあるTX
        self.unconfirmed_cashe = None

    def put_unconfirmed_tx(self, tx):
        assert tx.height is None, 'Not unconfirmed tx {}'.format(tx)
        assert tx.type not in (C.TX_POW_REWARD, C.TX_POS_REWARD), 'It is Reword tx. {}'.format(tx)
        self.unconfirmed_cashe = None
        self.temporary[tx.hash] = tx
        self.cashed[tx.hash] = tx

    def get_tx(self, txhash, default=None):
        if txhash in self.temporary:
            tx = self.temporary[txhash]
            tx.f_on_memory = True
            assert tx.height is None, "Tx height is null. {}".format(tx)
            return tx
        elif txhash in self.cashed:
            tx = self.cashed[txhash]
            tx.f_on_memory = True
            return tx
        try:
            tx = builder.db.read_tx(txhash)
            tx.f_on_memory = False
            return tx
        except KeyError:
            return default

    def __contains__(self, item):
        for tx in self.cashed.values():
            if tx == item:
                return True
        return False

    @property
    def unconfirmed(self):
        if self.unconfirmed_cashe:
            return self.unconfirmed_cashe
        chained_tx = builder.get_chained_txs()
        # MainChainに含まれないTXを取得
        unconfirmed = set(tx for tx in self.temporary.values() if tx not in chained_tx)
        unconfirmed.update(tx for tx in self.cashed.values() if tx not in chained_tx)
        # 時間切れを起こしていないTXのみ
        limit = int(time.time() - V.BLOCK_GENESIS_TIME - C.ACCEPT_MARGIN_TIME)
        for tx in unconfirmed.copy():
            if limit < tx.deadline:
                unconfirmed.remove(tx)
                del self.temporary[tx.hash]
            tx.height = None
        self.unconfirmed_cashe = unconfirmed
        return unconfirmed

    def affect_new_block(self, block):
        for tx in block.txs:
            tx.height = block.height
            if tx.type in (C.TX_POS_REWARD, C.TX_POW_REWARD):
                continue
            if tx.hash in self.temporary:
                del self.temporary[tx.hash]
                self.unconfirmed_cashe = None


class BlockBuilderError(BaseException):
    pass


# ファイル読み込みと同時に作成
builder = ChainBuilder()
# TXの管理
tx_box = TransactionBox()
# User情報
user_account = UserAccount()
