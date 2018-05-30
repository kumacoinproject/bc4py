#!/user/env python3
# -*- coding: utf-8 -*-

from bc4py.config import C, V
from bc4py.database.create import create_db, closing
from bc4py.database.chain.read import read_block_header
from bc4py.chain.utils import bits2target, target2bits
from math import log2
import time
from threading import Lock

"""
https://github.com/fujicoin/electrum-fjc-3.0.5/blob/master/lib/blockchain.py#L266
Kimoto Gravity Well
"""


MAX_BITS = 0x1f2fffff
MAX_TARGET = bits2target(MAX_BITS)
GENESIS_PREVIOUS_HASH = b'\xff'*32
F_DEBUG = False


class Cashe:
    def __init__(self):
        self.data = dict()
        self.limit = 50
        self.lock = Lock()

    def __setitem__(self, key, value):
        with self.lock:
            self.data[key] = (time.time(), value)
            if len(self.data) > self.limit:
                self.__refresh()

    def __getitem__(self, item):
        if item in self.data:
            return self.data[item][1]

    def __contains__(self, item):
        return item in self.data

    def __refresh(self):
        limit = self.limit * 4 // 5
        for k, v in sorted(self.data.items(), key=lambda x: x[1][0]):
            del self.data[k]
            if len(self.data) < limit:
                break


cashe = Cashe()


def best_block_span():
    # POS, POWブロック間隔
    pow_ratio, pos_ratio = V.BLOCK_POW_RATIO, 100 - V.BLOCK_POW_RATIO
    pow_target = round(V.BLOCK_TIME_SPAN / max(1, pow_ratio) * 100)
    pos_target = round(V.BLOCK_TIME_SPAN / max(1, pos_ratio) * 100)
    return pow_target, pos_target


def get_bits_by_hash(previous_hash, consensus):
    if (previous_hash, consensus) in cashe:
        return cashe[(previous_hash, consensus)]
    elif previous_hash == GENESIS_PREVIOUS_HASH:
        return MAX_BITS, MAX_TARGET

    pow_target, pos_target = best_block_span()
    block_span = pow_target if consensus == C.BLOCK_POW else pos_target

    # Block読み込み
    count = 0
    with closing(create_db(V.DB_BLOCKCHAIN_PATH)) as db:
        cur = db.cursor()
        check_previous_hash = previous_hash
        block = read_block_header(blockhash=check_previous_hash, cur=cur)
        new_block_time = block.time
        new_block_bits = None
        while True:
            block = read_block_header(blockhash=check_previous_hash, cur=cur)
            check_previous_hash = block.previous_hash
            if block.flag == C.BLOCK_GENESIS:
                cashe[(previous_hash, consensus)] = (MAX_BITS, MAX_TARGET)
                return MAX_BITS, MAX_TARGET
            elif block.flag != consensus:
                continue
            else:
                count += 1
            # set block
            if count == 1:
                new_block_bits = block.bits  # new
            if count == C.DIFF_RETARGET:
                old_block_time = block.time  # old
                break

    # bits to target
    target = bits2target(bits=new_block_bits)
    # new target
    n_actual_timespan = new_block_time - old_block_time
    n_target_timespan = block_span * C.DIFF_RETARGET
    if F_DEBUG and V.F_DEBUG:
        print("ratio1", n_actual_timespan, n_target_timespan)
    n_actual_timespan = max(n_actual_timespan, n_target_timespan // C.DIFF_MULTIPLY)
    n_actual_timespan = min(n_actual_timespan, n_target_timespan * C.DIFF_MULTIPLY)
    new_target = min(MAX_TARGET, (target * n_actual_timespan) // n_target_timespan)  # target が小さいほど掘りにくい
    if F_DEBUG and V.F_DEBUG:
        print("ratio2", n_actual_timespan, n_target_timespan, round(log2(target), 3),
              round(log2(new_target), 3), 'Diff↑' if target > new_target else 'Diff↓')

    # convert new target to bits
    new_bits = target2bits(target=new_target)
    cashe[(previous_hash, consensus)] = (new_bits, new_target)
    return new_bits, new_target


MAX_BIAS_TARGET = 0xffffffffffffffff
MAX_BIAS_BITS = target2bits(MAX_BIAS_TARGET)
MIN_BIAS_TARGET = 0x5f5e100
MIN_BIAS_BITS = target2bits(MIN_BIAS_TARGET)


def get_pos_bias_by_hash(previous_hash):
    if previous_hash in cashe:
        return cashe[previous_hash]
    elif previous_hash == GENESIS_PREVIOUS_HASH:
        return MIN_BIAS_BITS, MIN_BIAS_TARGET
    # POSのDiffが高すぎる→pos target は小さい→bias を大きくしたい→
    if V.BLOCK_CONSENSUS != C.HYBRID:
        return MIN_BIAS_BITS, MIN_BIAS_TARGET

    # pow pos の target が小さいほど掘りにくい
    pow_target = get_bits_by_hash(previous_hash=previous_hash, consensus=C.BLOCK_POW)[1]
    pos_target = get_bits_by_hash(previous_hash=previous_hash, consensus=C.BLOCK_POS)[1]

    with closing(create_db(V.DB_BLOCKCHAIN_PATH)) as db:
        cur = db.cursor()
        previous_block = read_block_header(blockhash=previous_hash, cur=cur)
        bias_target = bits2target(bits=previous_block.pos_bias)

    # POSのDiffが大きすぎるとBiasが1より大きくになる
    # new_target が大きくなりCoinの評価が小さくなる
    # 急激な変化はDifficultyに任せる為、変化は0.8％以内
    bias = log2(pow_target) / log2(pos_target)
    # 他に移植しやすくする為、全ての型は Double
    new_target = int(float(bias_target) * min(1.01, max(0.99, bias)))

    if F_DEBUG and V.F_DEBUG:
        print("Bias", bias_target, new_target, bias, min(1.01, max(0.99, bias)))

    # 範囲を調整
    new_target = max(MIN_BIAS_TARGET, min(MAX_BIAS_TARGET, new_target))
    new_bias = target2bits(target=new_target)
    cashe[previous_hash] = (new_bias, new_target)
    return new_bias, new_target
