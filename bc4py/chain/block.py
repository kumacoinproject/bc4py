from bc4py import __block_version__
from bc4py.config import C, V
from bc4py.chain.utils import DEFAULT_TARGET, bits2target
from bc4py_extension import sha256d_hash, merkleroot_hash
from logging import getLogger
from typing import NamedTuple, Optional
from struct import Struct
from time import time
from math import log2

log = getLogger('bc4py')
struct_block = Struct('<I32s32sII4s')


# low memory consumption object
class BlockHeader(NamedTuple):
    # meta
    height: int
    flag: int
    work: bytes
    # body
    version: int  # 4bytes int
    previous_hash: bytes  # 32bytes bin
    merkleroot: bytes  # 32bytes bin
    time: int  # 4bytes int
    bits: int  # 4bytes int
    nonce: bytes  # 4bytes bin


def get_block_header_from_bin(height, work, b_block, flag):
    """get block header from 80bytes binary"""
    return BlockHeader(height, flag, work, *struct_block.unpack(b_block))


class Block(object):
    __slots__ = (
        # data
        "b",
        # meta
        "hash",
        "next_hash",
        "target_hash",
        "work_hash",
        "height",
        "_difficulty",
        "_work_difficulty",
        "create_time",
        "flag",
        "f_orphan",
        "recode_flag",
        "_bias",
        "inner_score",
        # block header
        "version",  # 4bytes int
        "previous_hash",  # 32bytes bin
        "merkleroot",  # 32bytes bin
        "time",  # 4bytes int
        "bits",  # 4bytes int
        "nonce",  # 4bytes bin
        # block body
        "txs",
        "__weakref__",
    )

    def __eq__(self, other):
        if isinstance(other, Block):
            return self.hash == other.hash
        log.warning("compare with {} by {}".format(self, other))
        return False

    def __hash__(self):
        return hash(self.hash)

    def __repr__(self):
        return "<Block {} {} {} {} score={} txs={}>".format(
            self.height, C.consensus2name.get(self.flag, 'UNKNOWN'),
            "ORPHAN" if self.f_orphan else "",
            self.hash.hex(), round(self.score, 4), len(self.txs))

    def __init__(self):
        # data
        self.b = None
        # meta
        self.hash = None
        self.next_hash = None
        self.target_hash = None
        self.work_hash = None
        self.height = None
        self._difficulty = None
        self._work_difficulty = None
        self.create_time = time()  # Objectの生成日時
        self.flag = None  # mined consensus number
        self.f_orphan = None
        self.recode_flag = None
        self._bias = None  # bias 4bytes float
        self.inner_score = 1.0
        # block header
        self.version: Optional[int] = None
        self.previous_hash: Optional[bytes] = None
        self.merkleroot: Optional[bytes] = None
        self.time: Optional[int] = None
        self.bits: Optional[int] = None
        self.nonce: Optional[bytes] = None
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
        self.version = block.get('version', __block_version__)
        self.previous_hash = block['previous_hash']
        self.merkleroot = block['merkleroot']
        self.time = block['time']
        self.bits = block['bits']
        self.nonce = block['nonce']
        self.serialize()
        # extension
        self.height = block.get('height')
        self.flag = block.get('flag')
        return self

    def serialize(self):
        self.b = struct_block.pack(self.version, self.previous_hash, self.merkleroot, self.time, self.bits,
                                   self.nonce)
        self.hash = sha256d_hash(self.b)
        assert len(self.b) == 80, 'Not correct header size [{}!={}]'.format(len(self.b), 80)

    def deserialize(self):
        assert len(self.b) == 80, 'Not correct header size [{}!={}]'.format(len(self.b), 80)
        self.version, self.previous_hash, self.merkleroot, self.time, self.bits, \
            self.nonce = struct_block.unpack(self.b)
        self.hash = sha256d_hash(self.b)

    def getinfo(self, f_with_tx_info=False):
        r = dict()
        r['hash'] = self.hash.hex() if self.hash else None
        if self.work_hash is None:
            r['work_hash'] = None
        else:
            r['work_hash'] = self.work_hash.hex()
        r['previous_hash'] = self.previous_hash.hex() if self.previous_hash else None
        r['next_hash'] = self.next_hash.hex() if self.next_hash else None
        r['f_orphan'] = self.f_orphan
        r['recode_flag'] = self.recode_flag
        r['height'] = self.height
        r['difficulty'] = round(self.difficulty, 8)
        r['fixed_difficulty'] = round(self.difficulty / self.bias, 8)
        r['score'] = round(self.score, 8)
        r['flag'] = C.consensus2name[self.flag]
        r['merkleroot'] = self.merkleroot.hex() if self.merkleroot else None
        r['time'] = V.BLOCK_GENESIS_TIME + self.time
        r['bits'] = self.bits
        r['bias'] = round(self.bias, 8)
        r['nonce'] = self.nonce.hex() if self.nonce else None
        if f_with_tx_info:
            r['txs'] = [tx.getinfo() for tx in self.txs]
        else:
            r['txs'] = [tx.hash.hex() for tx in self.txs]
        r['create_time'] = self.create_time
        r['size'] = self.size
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
        return log2(max(1.0, self.inner_score * self.difficulty / self.bias))

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

    @property
    def size(self):
        """size on chain (Do not include signature)"""
        tx_sizes = sum(tx.size for tx in self.txs)
        header_size = len(self.b)
        return tx_sizes + header_size

    @property
    def total_size(self):
        """size on database (Include signature)"""
        tx_sizes = sum(tx.total_size for tx in self.txs)
        header_size = len(self.b)
        return tx_sizes + header_size

    def update_time(self, blocktime):
        self.time = blocktime
        self.serialize()

    def diff2targets(self, difficulty=None):
        difficulty = difficulty if difficulty else self.difficulty
        return int(DEFAULT_TARGET / difficulty).to_bytes(32, 'little')

    def target2diff(self):
        target = int.from_bytes(self.target_hash, 'little')
        self._difficulty = DEFAULT_TARGET / float(target)

    def bits2target(self):
        target = bits2target(self.bits)
        self.target_hash = target.to_bytes(32, 'little')

    def work2diff(self):
        work = int.from_bytes(self.work_hash, 'little')
        self._work_difficulty = DEFAULT_TARGET / float(work)

    def pow_check(self, extra_target=None):
        if extra_target:
            assert isinstance(extra_target, int)
            target_int = extra_target
        else:
            if not self.target_hash:
                self.bits2target()
            target_int = int.from_bytes(self.target_hash, 'little')
        assert self.work_hash
        return target_int > int.from_bytes(self.work_hash, 'little')

    def update_merkleroot(self):
        hash_list = [tx.hash for tx in self.txs]
        self.merkleroot = merkleroot_hash(hash_list)
        self.serialize()


__all__ = [
    "BlockHeader",
    "get_block_header_from_bin",
    "Block",
]
