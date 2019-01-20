#!/user/env python3
# -*- coding: utf-8 -*-

from bc4py.config import C, V
from bc4py.chain.utils import MAX_256_INT, bits2target
from bc4py.chain.workhash import update_work_hash
from hashlib import sha256
import struct
from time import time
from math import log

struct_block = struct.Struct('<I32s32sII4s')


class Block:
    __slots__ = (
        "b", "hash", "next_hash", "target_hash", "work_hash",
        "height", "_difficulty", "_work_difficulty", "create_time",
        "flag", "f_orphan", "recode_flag", "_bias", "inner_score",
        "version", "previous_hash", "merkleroot", "time", "bits", "nonce", "txs",
        "__weakref__")

    def __eq__(self, other):
        return self.hash == other.hash

    def __hash__(self):
        return hash(self.hash)

    def __repr__(self):
        return "<Block {} {} {} {} score={} txs={}>".format(
            self.height, C.consensus2name[self.flag], "ORPHAN" if self.f_orphan else "",
            self.hash.hex(), round(self.score, 4), len(self.txs))

    def __init__(self):
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
        self.create_time = int(time())  # Objectの生成日時
        self.flag = None  # mined consensus number
        self.f_orphan = None
        self.recode_flag = None
        self._bias = None  # bias 4bytes float
        self.inner_score = 1.0
        # block header
        self.version = None  # ver 4bytes int
        self.previous_hash = None  # previous header sha256 hash
        self.merkleroot = None  # txs root hash 32bytes bin
        self.time = None  # time 4bytes int
        self.bits = None  # diff 4bytes int
        self.nonce = None  # nonce 4bytes bin
        # block body
        self.txs = list()  # tx object list

    @classmethod
    def from_binary(cls, binary):
        self = cls()
        self.b = binary
        self.deserialize()
        return self

    @classmethod
    def from_dict(cls, block):
        assert 'pos_bias' not in block
        self = cls()
        self.version = block.get('version', 0)
        self.previous_hash = block['previous_hash']
        self.merkleroot = block['merkleroot']
        self.time = block['time']
        self.bits = block['bits']
        self.nonce = block['nonce']
        self.serialize()
        # extension
        self.height = block.get('height', self.height)
        self.flag = block.get('flag', self.flag)
        return self

    def serialize(self):
        self.b = struct_block.pack(
            self.version,
            self.previous_hash,
            self.merkleroot,
            self.time,
            self.bits,
            self.nonce)
        self.hash = sha256(sha256(self.b).digest()).digest()
        assert len(self.b) == 80, 'Not correct header size [{}!={}]'.format(len(self.b), 80)

    def deserialize(self):
        assert len(self.b) == 80, 'Not correct header size [{}!={}]'.format(len(self.b), 80)
        self.version, self.previous_hash, self.merkleroot, self.time, self.bits, \
            self.nonce = struct_block.unpack(self.b)
        self.hash = sha256(sha256(self.b).digest()).digest()

    def getinfo(self):
        r = dict()
        r['hash'] = self.hash.hex() if self.hash else None
        try:
            if self.work_hash is None:
                update_work_hash(self)
            r['work_hash'] = self.work_hash.hex()
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(e)
            r['work_hash'] = None
        r['previous_hash'] = self.previous_hash.hex() if self.previous_hash else None
        r['next_hash'] = self.next_hash.hex() if self.next_hash else None
        r['f_orphan'] = self.f_orphan
        r['recode_flag'] = self.recode_flag
        r['height'] = self.height
        r['difficulty'] = self.difficulty
        r['fixed_difficulty'] = round(self.difficulty / self.bias, 8)
        r['score'] = round(self.score, 8)
        r['flag'] = C.consensus2name[self.flag]
        r['merkleroot'] = self.merkleroot.hex() if self.merkleroot else None
        r['time'] = V.BLOCK_GENESIS_TIME + self.time
        r['bits'] = self.bits
        r['bias'] = round(self.bias, 8)
        r['nonce'] = self.nonce.hex() if self.nonce else None
        r['txs'] = [tx.hash.hex() for tx in self.txs]
        r['create_time'] = self.create_time
        return r

    @property
    def bias(self):
        if not self._bias:
            from bc4py.chain.difficulty import get_bias_by_hash  # not good?
            self._bias = get_bias_by_hash(previous_hash=self.previous_hash, consensus=self.flag)
        return self._bias

    @property
    def score(self):
        # fixed_diff = difficulty / bias
        return log(max(1.0, self.inner_score * self.difficulty / self.bias * 1000000))

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
        tx_sizes = sum(tx.size + len(tx.signature) * 96 for tx in self.txs)
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
        self._difficulty = round((MAX_256_INT // int.from_bytes(self.target_hash, 'little')) / 1000000, 8)

    def bits2target(self):
        target = bits2target(self.bits)
        self.target_hash = target.to_bytes(32, 'little')

    def work2diff(self):
        self._work_difficulty = round((MAX_256_INT // int.from_bytes(self.work_hash, 'little')) / 1000000, 8)

    def pow_check(self, extra_target=None):
        if extra_target:
            assert isinstance(extra_target, int)
            target_int = extra_target
        else:
            if not self.target_hash:
                self.bits2target()
            target_int = int.from_bytes(self.target_hash, 'little')
        if not self.work_hash:
            update_work_hash(self)
        return target_int > int.from_bytes(self.work_hash, 'little')

    def update_merkleroot(self):
        hash_list = [tx.hash for tx in self.txs]
        while len(hash_list) > 1:
            if len(hash_list) % 2:
                hash_list.append(hash_list[-1])
            hash_list = [sha256(sha256(hash_list[i] + hash_list[i + 1]).digest()).digest()
                         for i in range(0, len(hash_list), 2)]
        self.merkleroot = hash_list[0]
        self.serialize()
