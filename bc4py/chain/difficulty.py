from bc4py.config import C, V, Debug, BlockChainError
from bc4py.database.builder import builder
from bc4py.chain.utils import bits2target, target2bits
from math import log2
import time
from binascii import hexlify

# https://github.com/zawy12/difficulty-algorithms/issues/3

# // LWMA-2 difficulty algorithm (commented version)
# // Copyright (c) 2017-2018 Zawy, MIT License
# // https://github.com/zawy12/difficulty-algorithms/issues/3
# // Bitcoin clones must lower their FTL.
# // Cryptonote et al coins must make the following changes:
# // #define BLOCKCHAIN_TIMESTAMP_CHECK_WINDOW    11
# // #define CRYPTONOTE_BLOCK_FUTURE_TIME_LIMIT        3 * DIFFICULTY_TARGET
# // #define DIFFICULTY_WINDOW                      60 //  45, 60, & 90 for T=600, 120, & 60.
# // Bytecoin / Karbo clones may not have the following
# // #define DIFFICULTY_BLOCKS_COUNT       DIFFICULTY_WINDOW+1
# // The BLOCKS_COUNT is to make timestamps & cumulative_difficulty vectors size N+1
# // Do not sort timestamps.
# // CN coins (but not Monero >= 12.3) must deploy the Jagerman MTP Patch. See:
# // https://github.com/loki-project/loki/pull/26   or
# // https://github.com/graft-project/GraftNetwork/pull/118/files


def params(block_span=600):
    # T=<target solvetime(s)>
    T = block_span

    # height -1 = most recently solved block number
    # target  = 1/difficulty/2^x where x is leading zeros in coin's max_target, I believe
    # Recommended N:
    N = int(45*(600/T) ** 0.3)

    # To get a more accurate solvetime to within +/- ~0.2%, use an adjustment factor.
    # This technique has been shown to be accurate in 4 coins.
    # In a formula:
    # [edit by zawy: since he's using target method, adjust should be 0.998. This was my mistake. ]
    adjust = 0.9989 ** (500/N)
    K = int((N+1)/2 * adjust * T)

    # Bitcoin_gold T=600, N=45, K=13632
    return N, K


def best_block_span():
    # POS, POWブロック間隔
    pow_ratio, pos_ratio = V.BLOCK_POW_RATIO, 100 - V.BLOCK_POW_RATIO
    pow_target = round(V.BLOCK_TIME_SPAN / max(1, pow_ratio) * 100)
    pos_target = round(V.BLOCK_TIME_SPAN / max(1, pos_ratio) * 100)
    return pow_target, pos_target


class Cashe:
    def __init__(self):
        self.data = dict()
        self.limit = 300

    def __setitem__(self, key, value):
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
MAX_BITS = 0x1f0fffff
MAX_TARGET = bits2target(MAX_BITS)
GENESIS_PREVIOUS_HASH = b'\xff'*32


def get_bits_by_hash(previous_hash, consensus):
    if Debug.F_CONSTANT_DIFF:
        return MAX_BITS, MAX_TARGET
    elif previous_hash == GENESIS_PREVIOUS_HASH:
        return MAX_BITS, MAX_TARGET
    elif (previous_hash, consensus) in cashe:
        return cashe[(previous_hash, consensus)]

    pow_target, pos_target = best_block_span()
    N, K = params(pow_target if consensus == C.BLOCK_POW else pos_target)

    # Loop through N most recent blocks.  "< height", not "<=".
    # height-1 = most recently solved rblock
    target_hash = previous_hash
    timestamp = list()
    target = list()
    j = 0
    while True:
        target_block = builder.get_block(target_hash)
        if target_block is None:
            return MAX_BITS, MAX_TARGET
        if target_block.flag != consensus:
            target_hash = target_block.previous_hash
            continue
        if j == N + 1:
            break
        j += 1
        timestamp.insert(0, target_block.time)
        target.insert(0, bits2target(target_block.bits))
        target_hash = target_block.previous_hash
        if target_hash == GENESIS_PREVIOUS_HASH:
            return MAX_BITS, MAX_TARGET

    sum_target = t = j = 0
    for i in range(N):
        solve_time = timestamp[i+1] - timestamp[i]
        j += 1
        t += solve_time * j
        sum_target += target[i+1]

    # Keep t reasonable in case strange solvetimes occurred.
    if t < N * K // 3:
        t = N * K // 3

    new_target = t * sum_target // K // N // N

    # convert new target to bits
    new_bits = target2bits(new_target)
    if Debug.F_SHOW_DIFFICULTY:
        print("ratio", C.consensus2name[consensus], new_bits, hexlify(previous_hash).decode())
    cashe[(previous_hash, consensus)] = (new_bits, new_target)
    return new_bits, new_target


MAX_BIAS_TARGET = 0xffffffffffffffff
MAX_BIAS_BITS = target2bits(MAX_BIAS_TARGET)
MIN_BIAS_TARGET = 0x5f5e100
MIN_BIAS_BITS = target2bits(MIN_BIAS_TARGET)


def get_pos_bias_by_hash(previous_hash):
    if previous_hash in cashe:
        return cashe[previous_hash]
    if previous_hash == GENESIS_PREVIOUS_HASH:
        return MIN_BIAS_BITS, MIN_BIAS_TARGET
    # POSのDiffが高すぎる→pos target は小さい→bias を大きくしたい→
    if V.BLOCK_CONSENSUS != C.HYBRID:
        return MIN_BIAS_BITS, MIN_BIAS_TARGET

    # pow pos の target が小さいほど掘りにくい
    pow_target = get_bits_by_hash(previous_hash=previous_hash, consensus=C.BLOCK_POW)[1]
    pos_target = get_bits_by_hash(previous_hash=previous_hash, consensus=C.BLOCK_POS)[1]

    previous_block = builder.get_block(previous_hash)
    bias_target = bits2target(bits=previous_block.pos_bias)

    # POSのDiffが大きすぎるとBiasが1より大きくになる
    # new_target が大きくなりCoinの評価が小さくなる
    # 急激な変化はDifficultyに任せる為、変化は0.8％以内
    bias = log2(pow_target) / log2(pos_target)
    # 他に移植しやすくする為、全ての型は Double
    new_target = int(float(bias_target) * min(1.01, max(0.99, bias)))

    if Debug.F_SHOW_DIFFICULTY:
        print("Bias", bias_target, new_target, bias, min(1.01, max(0.99, bias)))

    # 範囲を調整
    new_target = max(MIN_BIAS_TARGET, min(MAX_BIAS_TARGET, new_target))
    new_bias = target2bits(target=new_target)
    cashe[previous_hash] = (new_bias, new_target)
    return new_bias, new_target
