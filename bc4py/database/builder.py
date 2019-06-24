from bc4py.config import C, V, P, stream
from bc4py.bip32 import addr2bin, ADDR_SIZE
from bc4py.chain.utils import signature2bin, bin2signature
from bc4py.chain.tx import TX
from bc4py.chain.block import Block
import bc4py.chain.msgpack as bc4py_msgpack
from bc4py.user import Balance, Accounting
from bc4py.database.account import *
from bc4py.database.create import create_db
from bc4py_extension import sha256d_hash
from msgpack import unpackb, packb
from typing import Optional, Dict, List, MutableMapping
from weakref import WeakValueDictionary
from logging import getLogger, INFO
from time import time
import struct
import os
import plyvel
import asyncio


loop = asyncio.get_event_loop()
log = getLogger('bc4py')
getLogger('plyvel').setLevel(INFO)

struct_block = struct.Struct('>I32s80sBI')
struct_tx = struct.Struct('>2IB')
struct_address = struct.Struct('>{}s32sB'.format(ADDR_SIZE))
struct_address_idx = struct.Struct('>IQ?')
struct_coins = struct.Struct('>II')

# constant
ITER_ORDER = 'big'
DB_VERSION = 0  # increase if you change database structure


class DataBase(object):
    db_config = {
        'txindex': True,
        'addrindex': True,
        'timeout': None,
        'sync': False,
    }
    database_list = [
        "_block",  # [blockhash] -> [height, time, work, b_block, flag, tx_len][txhash0]..[txhashN]
        "_tx_index",  # [txhash] -> [height][offset]
        "_used_index",  # [txhash] -> [used_bin]
        "_block_index",  # [height] -> [blockhash]
        "_address_index",  # [address][txhash][index] -> [coin_id, amount, f_used]
        "_coins",  # [coin_id][index] -> [txhash][params, setting]
    ]

    def __init__(self, **kwargs):
        dirs = os.path.join(V.DB_HOME_DIR, 'db-ver{}'.format(DB_VERSION))
        self.dirs = dirs
        self.db_config.update(kwargs)  # extra settings
        self.event = asyncio.Event()
        self.event.set()
        # already used => LevelDBError
        if os.path.exists(dirs):
            f_create = False
        else:
            log.debug('No database directory found')
            os.mkdir(dirs)
            f_create = True
        self._block = plyvel.DB(os.path.join(dirs, 'block'), create_if_missing=f_create)
        if self.db_config['txindex']:
            self._tx_index = plyvel.DB(os.path.join(dirs, 'tx_index'), create_if_missing=f_create)
        self._used_index = plyvel.DB(os.path.join(dirs, 'used_index'), create_if_missing=f_create)
        self._block_index = plyvel.DB(os.path.join(dirs, 'block_index'), create_if_missing=f_create)
        self._address_index = plyvel.DB(os.path.join(dirs, 'address_index'), create_if_missing=f_create)
        self._coins = plyvel.DB(os.path.join(dirs, 'coins'), create_if_missing=f_create)
        self.batch: Optional[Dict[str, dict]] = None
        self.batch_task: Optional[asyncio.Task] = None
        log.debug(':create database connect path={}'.format(dirs.replace("\\", "/")))

    def close(self):
        for name in self.database_list:
            getattr(self, name).close()
        log.info("close database connection")

    async def batch_create(self):
        assert self.batch is None, 'batch is already start'
        await asyncio.wait_for(self.event.wait(), self.db_config['timeout'])
        self.event.clear()
        self.batch = dict()
        for name in self.database_list:
            self.batch[name] = dict()
        self.batch_task = asyncio.current_task()
        log.debug(":Create database batch")

    async def batch_commit(self):
        assert self.batch, 'Not created batch'
        for name, memory in self.batch.items():
            batch = getattr(self, name).write_batch(sync=self.db_config['sync'])
            for k, v in memory.items():
                batch.put(k, v)
            batch.write()
        self.batch = None
        self.batch_task = None
        self.event.set()
        log.debug("Commit database")

    def batch_rollback(self):
        self.batch = None
        self.batch_task = None
        self.event.set()
        log.debug("Rollback database")

    def is_batch_thread(self):
        return self.batch and self.batch_task is asyncio.current_task()

    def read_block(self, blockhash):
        if self.is_batch_thread() and blockhash in self.batch['_block']:
            b = self.batch['_block'][blockhash]
        else:
            b = self._block.get(blockhash, default=None)
        if b is None:
            return None
        b = bytes(b)
        offset = 0
        height, work, b_block, flag, tx_len = struct_block.unpack_from(b, offset)
        offset += struct_block.size
        block = Block.from_binary(binary=b_block)
        block.height = height
        block.work_hash = work
        block.flag = flag
        for _ in range(tx_len):
            bin_len, sign_len, r_len = struct_tx.unpack_from(b, offset)
            offset += struct_tx.size
            b_tx = b[offset:offset+bin_len]
            offset += bin_len
            b_sign = b[offset:offset+sign_len]
            offset += sign_len
            R = b[offset:offset+r_len]
            offset += r_len
            tx = TX.from_binary(binary=b_tx)
            tx.height = height
            tx.signature = bin2signature(b_sign)
            tx.R = R
            block.txs.append(tx)
        assert offset == len(b), "Block size on database is not match {}={}".format(offset, len(b))
        return block

    def read_block_hash(self, height):
        b_height = height.to_bytes(4, ITER_ORDER)
        if self.is_batch_thread() and b_height in self.batch['_block_index']:
            return self.batch['_block_index'][b_height]
        b = self._block_index.get(b_height, default=None)
        if b is None:
            return None
        else:
            return bytes(b)

    def read_block_hash_iter(self, start_height=0):
        f_batch = self.is_batch_thread()
        batch_copy = self.batch['_block_index'].copy() if self.batch else dict()
        start = start_height.to_bytes(4, ITER_ORDER)
        block_iter = self._block_index.iterator(start=start)
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
        if not self.db_config['txindex']:
            raise BlockBuilderError('"txindex" is false, you cannot find tx by hash')
        # txhash -> height
        if self.is_batch_thread() and txhash in self.batch['_tx_index']:
            b = self.batch['_tx_index'][txhash]
        else:
            b = self._tx_index.get(txhash, default=None)
        if b is None:
            return None
        b_height, offset = struct.unpack('>4sI', b)
        # height -> blockhash
        if self.is_batch_thread() and b_height in self.batch['_block_index']:
            blockhash = self.batch['_block_index'][b_height]
        else:
            blockhash = self._block_index.get(b_height, default=None)
        if blockhash is None:
            return None
        # blockhash -> block_bin
        if self.is_batch_thread() and blockhash in self.batch['_block']:
            b = self.batch['_block'][blockhash]
        else:
            b = self._block.get(blockhash, default=None)
        if b is None:
            return None
        # block_bin -> tx
        bin_len, sign_len, r_len = struct_tx.unpack_from(b, offset)
        offset += struct_tx.size
        b_tx = b[offset:offset + bin_len]
        offset += bin_len
        b_sign = b[offset:offset + sign_len]
        offset += sign_len
        R = b[offset:offset + r_len]
        offset += r_len
        if txhash != sha256d_hash(b_tx):
            return None  # will be forked
        tx = TX.from_binary(binary=b_tx)
        tx.height = int.from_bytes(b_height, ITER_ORDER)
        tx.signature = bin2signature(b_sign)
        tx.R = R
        return tx

    def read_usedindex(self, txhash):
        if self.is_batch_thread() and txhash in self.batch['_used_index']:
            b = self.batch['_used_index'][txhash]
        else:
            b = self._used_index.get(txhash, default=None)
        if b is None:
            return set()
        else:
            return set(b)

    def read_address_idx(self, address, txhash, index):
        k = addr2bin(ck=address, hrp=V.BECH32_HRP) + txhash + index.to_bytes(1, ITER_ORDER)
        if self.is_batch_thread() and k in self.batch['_address_index']:
            b = self.batch['_address_index'][k]
        else:
            b = self._address_index.get(k, default=None)
        if b is None:
            return None
        b = bytes(b)
        # coin_id, amount, f_used
        return struct_address_idx.unpack(b)

    def read_address_idx_iter(self, address):
        f_batch = self.is_batch_thread()
        batch_copy = self.batch['_address_index'].copy() if self.batch else dict()
        b_address = addr2bin(ck=address, hrp=V.BECH32_HRP)
        start = b_address + b'\x00' * (32+1)
        stop = b_address + b'\xff' * (32+1)
        address_iter = self._address_index.iterator(start=start, stop=stop)
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
        coins_iter = self._coins.iterator(start=start, stop=stop)
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

    def write_block(self, block):
        assert self.is_batch_thread(), 'Not created batch'
        tx_len = len(block.txs)
        if block.work_hash is None:
            block.update_pow()
        # write static block data
        b = struct_block.pack(block.height, block.work_hash, block.b, block.flag, tx_len)
        # write txs data
        b_height = block.height.to_bytes(4, ITER_ORDER)
        for tx in block.txs:
            if self.db_config['txindex']:
                self.batch['_tx_index'][tx.hash] = b_height + len(b).to_bytes(4, ITER_ORDER)
            bin_len = len(tx.b)
            b_sign = signature2bin(tx.signature)
            sign_len = len(b_sign)
            r_len = len(tx.R)
            b += struct_tx.pack(bin_len, sign_len, r_len)
            b += tx.b
            b += b_sign
            b += tx.R
            log.debug("Insert new tx {}".format(tx))
        self.batch['_block'][block.hash] = b
        self.batch['_block_index'][b_height] = block.hash
        log.debug("Insert new block {}".format(block))

    def write_usedindex(self, txhash, usedindex):
        assert self.is_batch_thread(), 'Not created batch'
        assert isinstance(usedindex, set), 'Unsedindex is set'
        self.batch['_used_index'][txhash] = bytes(sorted(usedindex))

    def write_address_idx(self, address, txhash, index, coin_id, amount, f_used):
        assert self.is_batch_thread(), 'Not created batch'
        k = addr2bin(ck=address, hrp=V.BECH32_HRP) + txhash + index.to_bytes(1, ITER_ORDER)
        v = struct_address_idx.pack(coin_id, amount, f_used)
        self.batch['_address_index'][k] = v
        log.debug("Insert new address idx {}".format(address))

    def write_coins(self, coin_id, txhash, params, setting):
        assert self.is_batch_thread(), 'Not created batch'
        index = -1
        for index, *dummy in self.read_coins_iter(coin_id=coin_id):
            pass
        index += 1
        k = coin_id.to_bytes(4, ITER_ORDER) + index.to_bytes(4, ITER_ORDER)
        v = txhash + packb((params, setting), use_bin_type=True)
        self.batch['_coins'][k] = v
        log.debug("Insert new coins id={}".format(coin_id))


class ChainBuilder(object):

    def __init__(self, cashe_limit=C.MEMORY_CASHE_LIMIT, batch_size=C.MEMORY_BATCH_SIZE):
        """
        chain builder class

        +------ on database --------+   +------- on memory ---------+
        | block(0) -...- block(n-1) | - | block(n) -...- block(n+m) |
        +---------------------------+   +---------------------------+

        "chain" include all block objects including forks of height n or more
        "best_chain" is list  [block(n+m) -....- block(n+1) - block(n)]
        "root_block" is block(n-1), best block on database
        "best_block" is block(n+m), best block on memory
        """
        assert cashe_limit > batch_size, 'cashe_limit > batch_size'
        self.cashe_limit = cashe_limit
        self.batch_size = batch_size
        self.chain: Dict[bytes, Block] = dict()
        self.best_chain: Optional[List[Block]] = None
        self.root_block: Optional[Block] = None
        self.best_block: Optional[Block] = None
        self.db: Optional[DataBase] = None

    async def close(self):
        # require manual close
        await self.db.batch_task
        self.db.close()

    def set_database_path(self, **kwargs):
        try:
            self.db = DataBase(**kwargs)
            log.info("Connect database")
        except plyvel.Error as e:
            log.warning("database connect error, {}".format(e))
        except Exception:
            log.fatal("Failed connect database", exc_info=True)

    async def init(self, genesis_block: Block, batch_size=None):
        assert self.db, 'Why database connection failed?'
        # return status
        # True  = Only genesisBlock, recommend to import bootstrap.dat.gz first
        # False = Many blocks in LevelDB, sync by network
        if batch_size is None:
            batch_size = self.cashe_limit
        # GenesisBlockか確認
        t = time()
        try:
            if genesis_block.hash != self.db.read_block_hash(0):
                raise BlockBuilderError("Don't match genesis hash [{}!={}]".format(
                    genesis_block.hash.hex(),
                    self.db.read_block_hash(0).hex()))
            elif genesis_block != self.db.read_block(genesis_block.hash):
                raise BlockBuilderError("Don't match genesis binary [{}!={}]".format(
                    genesis_block.b.hex(),
                    self.db.read_block(genesis_block.hash).b.hex()))
        except Exception:
            # GenesisBlockしか無いのでDummyBlockを入れる処理
            self.root_block = Block()
            self.root_block.hash = b'\xff' * 32
            self.chain[genesis_block.hash] = genesis_block
            self.best_chain = [genesis_block]
            self.best_block = genesis_block
            log.info("Set dummy block, genesisBlock={}".format(genesis_block))
            await user_account.init()
            return True

        async with create_db(V.DB_ACCOUNT_PATH) as db:
            cur = await db.cursor()
            # 0HeightよりBlockを取得して確認
            before_block = genesis_block
            batch_blocks = list()
            for height, blockhash in self.db.read_block_hash_iter(start_height=1):
                block = self.db.read_block(blockhash)
                if block.previous_hash != before_block.hash:
                    raise BlockBuilderError("PreviousHash != BlockHash [{}!={}]".format(block, before_block))
                elif block.height != height:
                    raise BlockBuilderError("BlockHeight != DBHeight [{}!={}]".format(block.height, height))
                elif height != before_block.height + 1:
                    raise BlockBuilderError("DBHeight != BeforeHeight+1 [{}!={}+1]".format(
                        height, before_block.height))
                for tx in block.txs:
                    if tx.height != height:
                        raise BlockBuilderError("TXHeight != BlockHeight [{}!{}]".format(tx.height, height))
                    # inputs
                    for txhash, txindex in tx.inputs:
                        input_tx = self.db.read_tx(txhash)
                        address, coin_id, amount = input_tx.outputs[txindex]
                        _coin_id, _amount, f_used = self.db.read_address_idx(address, txhash, txindex)
                        usedindex = self.db.read_usedindex(txhash)
                        if coin_id != _coin_id or amount != _amount:
                            raise BlockBuilderError(
                                "Inputs, coin_id != _coin_id or amount != _amount [{}!{}] [{}!={}]".format(
                                    coin_id, _coin_id, amount, _amount))
                        elif txindex not in usedindex:
                            raise BlockBuilderError("Already used but unused. [{} not in {}]".format(
                                txindex, usedindex))
                        elif not f_used:
                            raise BlockBuilderError("Already used but unused flag. [{}:{}]".format(
                                input_tx, txindex))
                    # outputs
                    for index, (address, coin_id, amount) in enumerate(tx.outputs):
                        _coin_id, _amount, f_used = self.db.read_address_idx(address, tx.hash, index)
                        if coin_id != _coin_id or amount != _amount:
                            raise BlockBuilderError(
                                "Outputs, coin_id != _coin_id or amount != _amount [{}!{}] [{}!={}]".format(
                                    coin_id, _coin_id, amount, _amount))
                # Block確認終了
                before_block = block
                batch_blocks.append(block)
                if len(batch_blocks) >= batch_size:
                    await user_account.new_batch_apply(batched_blocks=batch_blocks, outer_cur=cur)
                    batch_blocks.clear()
                    log.debug("UserAccount batched at {} height".format(block.height))
            # load and rebuild memory section
            self.root_block = before_block
            memorized_blocks, self.best_block = self.recover_from_memory_file(before_block)
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
            await user_account.new_batch_apply(batched_blocks=batch_blocks, outer_cur=cur)
            await user_account.init(outer_cur=cur)
            await db.commit()
        log.info("Init finished, last block is {} {}Sec".format(before_block, round(time() - t, 3)))
        return False

    def write_to_memory_file(self, new_block: Block):
        """add new block to memory_file"""
        path = os.path.join(self.db.dirs, 'memory.mpac')
        try:
            if new_block.height % C.MEMORY_FILE_REFRESH_SPAN == 0:
                # clear
                with open(path, mode='bw') as fp:
                    for block in reversed(self.best_chain):
                        bc4py_msgpack.dump(block, fp)
                log.debug(f"refresh memory_file height={new_block.height}")
            else:
                # append
                with open(path, mode='ba') as fp:
                    bc4py_msgpack.dump(new_block, fp)
        except Exception as e:
            log.warning(f"failed to recode memory block by '{str(e)}'")

    def recover_from_memory_file(self, root_block: Block) -> (List[Block], Block):
        """recover memory from memory_file"""
        path = os.path.join(self.db.dirs, 'memory.mpac')
        memorized_blocks = list()
        if not os.path.exists(path):
            log.debug("no memory file found")
            return memorized_blocks, root_block
        try:
            with open(path, mode='br') as fp:
                block_list: List[Block] = list()
                for block in reversed(tuple(bc4py_msgpack.stream_unpacker(fp))):
                    if len(block_list) == 0 or block.hash == block_list[0].previous_hash:
                        block_list.insert(0, block)
                for block in block_list:
                    if root_block.hash == block.previous_hash:
                        memorized_blocks.append(block)
                        root_block = block
        except Exception:
            log.warning(f"failed to recover from memory_file", exc_info=True)
        return memorized_blocks, root_block

    def get_best_chain(self, best_block=None):
        assert self.root_block, 'Do not init'
        if best_block:
            best_sets = {best_block}
            previous_hash = best_block.previous_hash
            while self.root_block.hash != previous_hash:
                if previous_hash not in self.chain:
                    raise BlockBuilderError('Cannot find previousHash, may not main-chain. {}'.format(
                        previous_hash.hex()))
                block = self.chain[previous_hash]
                previous_hash = block.previous_hash
                best_sets.add(block)
            # best_chain = [<height=n>, <height=n-1>, ...]
            best_chain = sorted(best_sets, key=lambda x: x.height, reverse=True)
            return best_block, best_chain
        # BestBlockがchainにおける
        best_score = 0.0
        best_block = None
        best_sets = set()
        for block in sorted(self.chain.values(), key=lambda x: x.create_time, reverse=True):
            if block in best_sets:
                continue
            tmp_best_score = block.score
            tmp_best_block = block
            tmp_best_sets = {block}
            while block.previous_hash in self.chain:
                block = self.chain[block.previous_hash]
                tmp_best_score += block.score
                tmp_best_sets.add(block)
            else:
                if self.root_block.hash != block.previous_hash:
                    continue
            if best_score > tmp_best_score:
                continue
            best_score = tmp_best_score
            best_block = tmp_best_block
            best_sets = tmp_best_sets
        # txのheightを揃える
        for block in best_sets:
            for tx in block.txs:
                tx.height = block.height
        assert best_block, 'Cannot find best_block on get_best_chain? chain={}'.format(list(self.chain))
        # best_chain = [<height=n>, <height=n-1>, ...]
        best_chain = sorted(best_sets, key=lambda x: x.height, reverse=True)
        return best_block, best_chain

    async def batch_apply(self):
        # 無チェックで挿入するから要注意
        if self.cashe_limit > len(self.chain):
            return list()
        # cashe許容量を上回っているので記録
        await self.db.batch_create()
        log.debug("Start batch apply chain={}".format(len(self.chain)))
        best_chain = self.best_chain.copy()
        batch_count = self.batch_size
        batched_blocks = list()
        async with create_db(V.DB_ACCOUNT_PATH) as db:
            cur = await db.cursor()
            try:
                block = None
                while batch_count > 0 and len(best_chain) > 0:
                    batch_count -= 1
                    block = best_chain.pop()  # 古いものから順に
                    batched_blocks.append(block)
                    self.db.write_block(block)  # Block
                    assert len(block.txs) > 0, "found no tx in {}".format(block)
                    for tx in block.txs:
                        # inputs
                        for index, (txhash, txindex) in enumerate(tx.inputs):
                            # DataBase内でのみのUsedIndexを取得
                            usedindex = self.db.read_usedindex(txhash)
                            if txindex in usedindex:
                                raise BlockBuilderError('Already used index? {}:{}'.format(txhash.hex(), txindex))
                            usedindex.add(txindex)
                            self.db.write_usedindex(txhash, usedindex)  # UsedIndex update
                            input_tx = tx_builder.get_tx(txhash)
                            address, coin_id, amount = input_tx.outputs[txindex]
                            if chain_builder.db.db_config['addrindex'] or \
                                    await read_address2userid(address=address, cur=cur):
                                # 必要なAddressのみ
                                self.db.write_address_idx(address, txhash, txindex, coin_id, amount, True)
                        # outputs
                        for index, (address, coin_id, amount) in enumerate(tx.outputs):
                            if chain_builder.db.db_config['addrindex'] or \
                                    await read_address2userid(address=address, cur=cur):
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

                # block挿入終了
                self.best_chain = best_chain
                self.root_block = block
                await self.db.batch_commit()
                # root_blockよりHeightの小さいBlockを消す
                for blockhash, block in self.chain.copy().items():
                    if self.root_block.height >= block.height:
                        del self.chain[blockhash]
                log.debug("Success batch {} blocks, root={}".format(len(batched_blocks), self.root_block))
                # アカウントへ反映↓
                await user_account.new_batch_apply(batched_blocks=batched_blocks, outer_cur=cur)
                await db.commit()
                return batched_blocks  # [<height=n>, <height=n+1>, .., <height=n+m>]
            except Exception as e:
                self.db.batch_rollback()
                log.warning("Failed batch block builder. '{}'".format(e), exc_info=True)
                return list()

    def new_block(self, new_block):
        """insert new block, Block/TX format is already checked"""
        if new_block.height <= self.root_block.height:
            return
        # meet chain order: root_block < new_block
        self.chain[new_block.hash] = new_block
        # BestChainの変化を調べる
        new_best_block, new_best_chain = self.get_best_chain()
        if self.best_block and new_best_block == self.best_block:
            return  # 操作を加える必要は無い
        # tx heightを合わせる
        old_best_chain = self.best_chain.copy()
        new_best_sets = set(new_best_chain) - set(old_best_chain)
        old_best_sets = set(old_best_chain) - set(new_best_chain)
        for index, block in enumerate(old_best_sets):
            try:
                old_best_chain[index + 1].next_hash = None
            except IndexError:
                pass
            for tx in block.txs:
                tx.height = None
            block.f_orphan = True
        for index, block in enumerate(new_best_sets):
            try:
                new_best_chain[index + 1].next_hash = block.hash
            except IndexError:
                pass
            for tx in block.txs:
                tx.height = block.height
            block.f_orphan = False
        # 変化しているので反映する
        self.best_block, self.best_chain = new_best_block, new_best_chain
        tx_builder.affect_new_chain(new_best_sets=new_best_sets, old_best_sets=old_best_sets)
        self.write_to_memory_file(new_block)

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


class TransactionBuilder(object):

    def __init__(self):
        # TXs that Blocks don't contain
        self.unconfirmed: Dict[bytes, TX] = dict()
        # TXs that MAIN chain contains
        self.chained_tx: MutableMapping[bytes, TX] = WeakValueDictionary()
        # DataBase contains TXs
        self.cashe: MutableMapping[bytes, TX] = WeakValueDictionary()

    async def put_unconfirmed(self, tx, outer_cur=None):
        assert tx.height is None, 'Not unconfirmed tx {}'.format(tx)
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
        await user_account.affect_new_tx(tx, outer_cur)
        if not stream.is_disposed:
            stream.on_next(tx)

    def get_tx(self, txhash, default=None):
        if txhash in self.cashe:
            try:
                return self.cashe[txhash]
            except KeyError:
                # flashed WeakValueDictionary, need to retry
                return self.get_tx(txhash=txhash, default=default)
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
            tx = chain_builder.db.read_tx(txhash)
            if tx:
                tx.recode_flag = 'database'
                self.cashe[txhash] = tx
            else:
                return default
        return tx

    def __contains__(self, item):
        return bool(self.get_tx(item.hash))

    def affect_new_chain(self, old_best_sets, new_best_sets):

        def input_check(_tx):
            for input_hash, input_index in _tx.inputs:
                if input_index in chain_builder.db.read_usedindex(input_hash):
                    return True
            return False

        # 状態を戻す
        for block in old_best_sets:
            for tx in block.txs:
                if tx.hash not in self.unconfirmed and tx.type not in (C.TX_POW_REWARD, C.TX_POS_REWARD):
                    self.unconfirmed[tx.hash] = tx
                if tx.hash in self.chained_tx:
                    del self.chained_tx[tx.hash]
        # 新規に反映する
        for block in new_best_sets:
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
            log.warning("Removed {} unconfirmed txs".format(len(self.unconfirmed) - before_num))


class UserAccount(object):

    def __init__(self):
        self.db_balance = Accounting()
        # {txhash: (ntype, movement, ntime),..}
        self.memory_movement = dict()

    async def init(self, f_delete=False, outer_cur=None):

        async def _wrapper(cur):
            memory_sum = Accounting()
            for move_log in await read_movelog_iter(cur):
                # logに記録されてもBlockに取り込まれていないならTXは存在せず
                if chain_builder.db.read_tx(move_log.txhash):
                    memory_sum += move_log.movement
                elif move_log.type == C.TX_INNER:
                    continue
                else:
                    log.debug("It's unknown log {}".format(move_log))
                    if f_delete:
                        await delete_movelog(move_log.txhash, cur)
            self.db_balance += memory_sum

        assert f_delete is False, 'Unsafe function!'
        if outer_cur:
            await _wrapper(outer_cur)
        else:
            async with create_db(V.DB_ACCOUNT_PATH) as db:
                await _wrapper(await db.cursor())
                await db.commit()
                log.warning(f"Delete user's old unconfirmed tx")

    async def get_balance(self, confirm=6, outer_cur=None):

        async def _wrapper(cur):
            # DataBase
            account = self.db_balance.copy()
            # Memory
            limit_height = chain_builder.best_block.height - confirm
            for block in chain_builder.best_chain:
                for tx in block.txs:
                    move_log = await read_txhash2movelog(tx.hash, cur)
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
                move_log = await read_txhash2movelog(tx.hash, cur)
                if move_log is None:
                    if tx.hash in self.memory_movement:
                        move_log = self.memory_movement[tx.hash]
                if move_log:
                    for user, coins in move_log.movement.items():
                        for coin_id, amount in coins:
                            if amount < 0:
                                account[user][coin_id] += amount
            return account

        assert confirm < chain_builder.cashe_limit - chain_builder.batch_size
        assert chain_builder.best_block, 'Not DataBase init'
        if outer_cur:
            return await _wrapper(outer_cur)
        else:
            async with create_db(V.DB_ACCOUNT_PATH) as db:
                return await _wrapper(await db.cursor())

    async def move_balance(self, _from, _to, coins, outer_cur=None):

        async def _wrapper(cur):
            # DataBaseに即書き込む(Memoryに入れない)
            movements = Accounting()
            movements[_from] -= coins
            movements[_to] += coins
            txhash = await insert_movelog(movements, cur)
            self.db_balance += movements
            return txhash

        assert isinstance(coins, Balance), 'coins is Balance'
        if outer_cur:
            return await _wrapper(outer_cur)
        else:
            async with create_db(V.DB_ACCOUNT_PATH) as db:
                r = await _wrapper(await db.cursor())
                await db.commit()
            return r

    async def get_movement_iter(self, start=0, f_dict=False, outer_cur=None):

        async def _wrapper(cur):
            count = 0
            # Unconfirmed
            for tx in sorted(tx_builder.unconfirmed.values(), key=lambda x: x.create_time, reverse=True):
                move_log = await read_txhash2movelog(tx.hash, cur)
                if move_log is None:
                    if tx.hash in self.memory_movement:
                        move_log = self.memory_movement[tx.hash]
                else:
                    if tx.hash in self.memory_movement:
                        move_log.tx_ref = self.memory_movement[tx.hash].tx_ref
                if move_log:
                    if count >= start:
                        if f_dict:
                            yield await move_log.get_dict_data(recode_flag='unconfirmed', cur=cur)
                        else:
                            yield move_log.get_tuple_data()
                    count += 1
            # Memory
            for block in reversed(chain_builder.best_chain):
                for tx in block.txs:
                    move_log = await read_txhash2movelog(tx.hash, cur)
                    if move_log is None:
                        if tx.hash in self.memory_movement:
                            move_log = self.memory_movement[tx.hash]
                    else:
                        if tx.hash in self.memory_movement:
                            move_log.tx_ref = self.memory_movement[tx.hash].tx_ref
                    if move_log:
                        if count >= start:
                            if f_dict:
                                yield await move_log.get_dict_data(recode_flag='memory', cur=cur)
                            else:
                                yield move_log.get_tuple_data()
                        count += 1
            # DataBase
            for move_log in await read_movelog_iter(cur, start - count):
                # TRANSFERなど はDBとMemoryの両方に存在する
                if move_log.txhash in self.memory_movement:
                    continue
                elif f_dict:
                    yield await move_log.get_dict_data(recode_flag='database', cur=cur)
                else:
                    yield move_log.get_tuple_data()

        if outer_cur:
            return _wrapper(outer_cur)
        else:
            async with create_db(V.DB_ACCOUNT_PATH) as db:
                return _wrapper(await db.cursor())

    async def new_batch_apply(self, batched_blocks, outer_cur=None):

        async def _wrapper(cur):
            for block in batched_blocks:
                for tx in block.txs:
                    move_log = await read_txhash2movelog(tx.hash, cur)
                    if move_log:
                        # User操作の記録
                        self.db_balance += move_log.movement
                        if tx.hash in self.memory_movement:
                            del self.memory_movement[tx.hash]
                        # log.debug("Already recoded log {}".format(tx))
                    elif tx.hash in self.memory_movement:
                        # db_balanceに追加
                        ntype, movement, ntime = self.memory_movement[tx.hash].get_tuple_data()
                        self.db_balance += movement
                        # memory_movementから削除
                        del self.memory_movement[tx.hash]
                        # insert_log
                        await insert_movelog(movement, cur, ntype, ntime, tx.hash)

        if outer_cur:
            await _wrapper(outer_cur)
        else:
            async with create_db(V.DB_ACCOUNT_PATH) as db:
                await _wrapper(await db.cursor())
                await db.commit()

    async def affect_new_tx(self, tx, outer_cur=None):

        async def _wrapper(cur):
            movement = Accounting()
            # already registered by send_from_apply method
            if tx.hash in self.memory_movement:
                return
            # add to memory_movement dict
            for txhash, txindex in tx.inputs:
                input_tx = tx_builder.get_tx(txhash)
                address, coin_id, amount = input_tx.outputs[txindex]
                user = await read_address2userid(address, cur)
                if user is not None:
                    if tx.type == C.TX_POS_REWARD:
                        # subtract staking reward from @Staked
                        user = C.ANT_STAKED
                    movement[user][coin_id] -= amount
                    # movement[C.ANT_OUTSIDE] += balance
            for address, coin_id, amount in tx.outputs:
                user = await read_address2userid(address, cur)
                if user is not None:
                    if tx.type == C.TX_POS_REWARD:
                        # add staking reward to @Staked
                        user = C.ANT_STAKED
                    movement[user][coin_id] += amount
                    # movement[C.ANT_OUTSIDE] -= balance
            # check
            movement.cleanup()
            if len(movement) == 0:
                return  # cannot find no movement to recode, skip
            move_log = MoveLog(tx.hash, tx.type, movement, tx.time, tx)
            self.memory_movement[tx.hash] = move_log
            log.info("affected account by {}".format(tx))

        if outer_cur:
            await _wrapper(outer_cur)
        else:
            async with create_db(V.DB_ACCOUNT_PATH) as db:
                await _wrapper(await db.cursor())


class BlockBuilderError(Exception):
    pass


# global object
chain_builder = ChainBuilder()
tx_builder = TransactionBuilder()
user_account = UserAccount()

__all__ = [
    "chain_builder",
    "tx_builder",
    "user_account",
]
