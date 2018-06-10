#!/user/env python3
# -*- coding: utf-8 -*-

from bc4py.config import C, V
from bc4py.chain.utils import MAX_256_INT, bits2target
import yescryptr16
# import yescryptr64
# import zny_yescrypt
import multiprocessing
from hashlib import sha256
from os import urandom
from binascii import hexlify
import struct
import time


BLOCK_PACKING_FORMAT = '> 32s32sIII4s'


def generator_process(pipe):
    print("POW hash gene start.")
    while True:
        try:
            binary = pipe.recv()
            pow_hash = yescryptr16.getPoWHash(binary)
            pipe.send(pow_hash)
        except Exception as e:
            print("POW hash gene error:", e)
            break


class PowGenerator:
    # GCとyescryptr16の相性が悪くメモリリークする為
    def __init__(self):
        self.p = None
        self.pipe = None
        self.lock = None

    def start(self):
        pipe0, pipe1 = multiprocessing.Pipe()
        self.pipe = pipe1
        self.lock = multiprocessing.Lock()
        self.p = multiprocessing.Process(target=generator_process, args=(pipe0,))
        self.p.daemon = True
        self.p.start()

    def calc(self, binary):
        with self.lock:
            try:
                self.pipe.send(binary)
                pow_hash = self.pipe.recv()
                return pow_hash
            except BlockingIOError:
                self.start()
                self.pipe.send(binary)
                pow_hash = self.pipe.recv()
        return pow_hash

    def close(self):
        self.p.terminate()
        self.pipe.close()


# メモリリーク防止の為に別プロセスでハッシュ計算する
pow_generator = PowGenerator()


class Block:
    __slots__ = (
        "b", "hash", "next_hash", "target_hash", "work_hash",
        "height", "difficulty", "work_difficulty", "create_time", "delete_time",
        "flag", "f_orphan", "f_on_memory",
        "merkleroot", "time", "previous_hash", "bits", "pos_bias", "nonce", "txs",
        "__weakref__")

    def __eq__(self, other):
        return self.hash == other.hash

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
        self.difficulty = None
        self.work_difficulty = None
        self.create_time = None  # Objectの生成日時
        self.delete_time = None  # Objectの削除日時
        self.flag = None  # mined consensus number
        self.f_orphan = None
        self.f_on_memory = None
        # block header
        self.merkleroot = None  # txs root hash 32bytes bin
        self.time = None  # time 4bytes int
        self.previous_hash = None  # previous header sha256 hash
        self.bits = None  # diff 4bytes int
        self.pos_bias = None  # fix for POS 4bytes int
        self.nonce = None  # nonce 4bytes bin
        # block body
        self.txs = None  # tx object list

        if binary:
            self.b = binary
            self.deserialize()
        elif block:
            self.merkleroot = block['merkleroot']
            self.time = block['time']
            self.previous_hash = block['previous_hash']
            self.bits = block['bits']
            self.pos_bias = block['pos_bias']
            self.nonce = block['nonce']
            self.serialize()
        self.txs = list()
        self.create_time = int(time.time())

    def serialize(self):
        self.b = struct.pack(
            BLOCK_PACKING_FORMAT,
            self.merkleroot,
            self.previous_hash,
            self.bits,
            self.pos_bias,
            self.time,
            self.nonce)
        self.hash = sha256(self.b).digest()
        assert len(self.b) == 80, 'Not correct header size [{}!={}]'.format(len(self.b), 80)

    def deserialize(self):
        assert len(self.b) == 80, 'Not correct header size [{}!={}]'.format(len(self.b), 80)
        self.merkleroot, self.previous_hash, self.bits, self.pos_bias, self.time, \
            self.nonce = struct.unpack(BLOCK_PACKING_FORMAT, self.b)
        self.hash = sha256(self.b).digest()

    def getinfo(self):
        r = dict()
        r['hash'] = hexlify(self.hash).decode() if self.hash else None
        try:
            if self.work_hash is not None:
                r['work_hash'] = hexlify(self.work_hash).decode()
            elif self.flag == C.BLOCK_POW:
                self.update_pow()
                r['work_hash'] = hexlify(self.work_hash).decode()
            elif self.flag == C.BLOCK_POS:
                proof_tx = self.txs[0]
                self.work_hash = proof_tx.get_pos_hash(previous_hash=self.previous_hash, pos_bias=self.pos_bias)
                r['work_hash'] = hexlify(self.work_hash).decode()
            else:
                r['work_hash'] = None
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
        r['difficulty'] = self.difficulty if self.difficulty else None
        r['flag'] = C.consensus2name[self.flag]
        r['merkleroot'] = hexlify(self.merkleroot).decode() if self.merkleroot else None
        r['time'] = V.BLOCK_GENESIS_TIME + self.time
        r['bits'] = self.bits
        r['pos_bias'] = self.pos_bias
        r['nonce'] = hexlify(self.nonce).decode() if self.nonce else None
        r['txs'] = [hexlify(tx.hash).decode() for tx in self.txs]
        return r

    def getsize(self):
        tx_sizes = sum(tx.getsize() for tx in self.txs)
        header_size = len(self.b)
        return tx_sizes + header_size

    def update_nonce(self):
        self.nonce = urandom(4)
        self.serialize()

    def update_time(self, blocktime):
        self.time = blocktime
        self.serialize()

    def update_pow(self):
        # 80bytesでないと正しくハッシュが出ない模様
        if self.flag != C.BLOCK_POW:
            pass
        elif pow_generator.p is None:
            self.work_hash = yescryptr16.getPoWHash(self.b)
        else:
            self.work_hash = pow_generator.calc(self.b)

    def diff2targets(self, difficulty=None):
        difficulty = difficulty if difficulty else self.difficulty
        return int(MAX_256_INT / (difficulty*100000000)).to_bytes(32, 'big')

    def target2diff(self):
        self.difficulty = round((MAX_256_INT // int.from_bytes(self.target_hash, 'big')) / 1000000, 6)

    def bits2target(self):
        target = bits2target(self.bits)
        self.target_hash = target.to_bytes(32, 'big')

    def work2diff(self):
        self.work_difficulty = round((MAX_256_INT // int.from_bytes(self.work_hash, 'big')) / 1000000, 6)

    def pow_check(self):
        if not self.work_hash:
            self.update_pow()
        if not self.target_hash:
            self.bits2target()
        return int.from_bytes(self.target_hash, 'big') > int.from_bytes(self.work_hash, 'big')

    def update_merkleroot(self):
        h = sha256()
        for tx in self.txs:
            h.update(tx.hash)
        self.merkleroot = h.digest()
        self.serialize()
        self.hash = sha256(self.b).digest()
