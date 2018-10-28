#!/user/env python3
# -*- coding: utf-8 -*-

from bc4py.config import C, V
from bc4py.chain.utils import MAX_256_INT, bits2target
from bc4py.chain.workhash import update_work_hash
from hashlib import sha256
from os import urandom
from binascii import hexlify
import struct
import time


struct_block = struct.Struct('>I32s32sII4s')


class Block:
    __slots__ = (
        "b", "hash", "next_hash", "target_hash", "work_hash",
        "height", "_difficulty", "_work_difficulty", "create_time", "delete_time",
        "flag", "f_orphan", "f_on_memory", "_bias",
        "version", "previous_hash", "merkleroot", "time", "bits", "nonce", "txs",
        "__weakref__")

    def __eq__(self, other):
        return self.hash == other.hash

    def __hash__(self):
        return hash(self.hash)

    def __repr__(self):
        name = 'DeleteBlock' if self.delete_time else 'Block'
        return "<{} {} {} {} {} txs={}>".format(
            name, self.height, C.consensus2name[self.flag], "ORPHAN" if self.f_orphan else "",
            hexlify(self.hash).decode(), len(self.txs))

    def __init__(self, binary=None, block=None):
        self.b = None
        # block id
        self.hash = None  # header sha256 hash
        self.next_hash = None  # next header sha256 hash
        self.target_hash = None  # target hash
        self.work_hash = None  # proof of work hash
        # block params
        self.height = None
        self._difficulty = None
        self._work_difficulty = None
        self.create_time = None  # Objectの生成日時
        self.delete_time = None  # Objectの削除日時
        self.flag = None  # mined consensus number
        self.f_orphan = None
        self.f_on_memory = None
        self._bias = None  # bias 4bytes float
        # block header
        self.version = None  # ver 4bytes int
        self.previous_hash = None  # previous header sha256 hash
        self.merkleroot = None  # txs root hash 32bytes bin
        self.time = None  # time 4bytes int
        self.bits = None  # diff 4bytes int
        self.nonce = None  # nonce 4bytes bin
        # block body
        self.txs = None  # tx object list

        if binary:
            self.b = binary
            self.deserialize()
        elif block:
            self.version = block.get('version', 0)
            self.previous_hash = block['previous_hash']
            self.merkleroot = block['merkleroot']
            self.time = block['time']
            self.bits = block['bits']
            assert 'pos_bias' not in block, "'pos_bias' include!"
            self.nonce = block['nonce']
            self.serialize()
        self.txs = list()
        self.create_time = int(time.time())

    def serialize(self):
        self.b = struct_block.pack(
            self.version,
            self.previous_hash,
            self.merkleroot,
            self.bits,
            self.time,
            self.nonce)
        self.hash = sha256(sha256(self.b).digest()).digest()
        assert len(self.b) == 80, 'Not correct header size [{}!={}]'.format(len(self.b), 80)

    def deserialize(self):
        assert len(self.b) == 80, 'Not correct header size [{}!={}]'.format(len(self.b), 80)
        self.version, self.previous_hash, self.merkleroot, self.bits, self.time, \
            self.nonce = struct_block.unpack(self.b)
        self.hash = sha256(sha256(self.b).digest()).digest()

    def getinfo(self):
        r = dict()
        r['hash'] = hexlify(self.hash).decode() if self.hash else None
        try:
            if self.work_hash is None:
                update_work_hash(self)
            r['work_hash'] = hexlify(self.work_hash).decode()
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(e)
            r['work_hash'] = None
        r['previous_hash'] = hexlify(self.previous_hash).decode() if self.previous_hash else None
        r['next_hash'] = hexlify(self.next_hash).decode() if self.next_hash else None
        r['f_orphan'] = self.f_orphan
        r['f_on_memory'] = self.f_on_memory
        r['height'] = self.height
        r['difficulty'] = self.difficulty
        r['flag'] = C.consensus2name[self.flag]
        r['merkleroot'] = hexlify(self.merkleroot).decode() if self.merkleroot else None
        r['time'] = V.BLOCK_GENESIS_TIME + self.time
        r['bits'] = self.bits
        r['bias'] = self.bias
        r['nonce'] = hexlify(self.nonce).decode() if self.nonce else None
        r['txs'] = [hexlify(tx.hash).decode() for tx in self.txs]
        return r

    @property
    def bias(self):
        if not self._bias:
            from bc4py.chain.difficulty import get_bias_by_hash  # not good?
            self._bias = get_bias_by_hash(self.previous_hash, self.flag)
        return self._bias

    @property
    def difficulty(self):
        if self._difficulty is None:
            self.bits2target()
            self.target2diff()
        return self._difficulty

    @property
    def work_difficulty(self):
        if self._work_difficulty is None:
            self.work2diff()
        return self._work_difficulty

    def getsize(self):
        tx_sizes = sum(tx.getsize() for tx in self.txs)
        header_size = len(self.b)
        return tx_sizes + header_size

    def update_time(self, blocktime):
        self.time = blocktime
        self.serialize()

    def update_pow(self):
        update_work_hash(self)

    def diff2targets(self, difficulty=None):
        difficulty = difficulty if difficulty else self.difficulty
        return int(MAX_256_INT / (difficulty*100000000)).to_bytes(32, 'little')

    def target2diff(self):
        self._difficulty = round((MAX_256_INT // int.from_bytes(self.target_hash, 'little')) / 1000000, 6)

    def bits2target(self):
        target = bits2target(self.bits)
        self.target_hash = target.to_bytes(32, 'little')

    def work2diff(self):
        self._work_difficulty = round((MAX_256_INT // int.from_bytes(self.work_hash, 'little')) / 1000000, 6)

    def pow_check(self):
        if not self.work_hash:
            update_work_hash(self)
        if not self.target_hash:
            self.bits2target()
        return int.from_bytes(self.target_hash, 'little') > int.from_bytes(self.work_hash, 'little')

    def update_merkleroot(self):
        hash_list = [tx.hash for tx in self.txs]
        while len(hash_list) > 1:
            if len(hash_list) % 2:
                hash_list.append(hash_list[-1])
            hash_list = [sha256(sha256(hash_list[i] + hash_list[i + 1]).digest()).digest()
                         for i in range(0, len(hash_list), 2)]
        self.merkleroot = hash_list[0]
        self.serialize()
