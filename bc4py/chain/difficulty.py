from bc4py.config import C, V, Debug, BlockChainError
from bc4py.database.builder import builder
from bc4py.chain.utils import bits2target, target2bits
from binascii import hexlify
from functools import lru_cache

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


@lru_cache(maxsize=256)
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


MAX_BITS = 0x1f0fffff
MAX_TARGET = bits2target(MAX_BITS)
GENESIS_PREVIOUS_HASH = b'\xff'*32


@lru_cache(maxsize=512)
def get_bits_by_hash(previous_hash, consensus):
    if Debug.F_CONSTANT_DIFF:
        return MAX_BITS, MAX_TARGET
    elif previous_hash == GENESIS_PREVIOUS_HASH:
        return MAX_BITS, MAX_TARGET

    # Get best block time
    block_time = round(V.BLOCK_TIME_SPAN / V.BLOCK_CONSENSUSES[consensus] * 100)
    # Get N, K params
    N, K = params(block_time)

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
    return new_bits, new_target


@lru_cache(maxsize=256)
def get_bias_by_hash(previous_hash, consensus):
    N = 30  # target blocks

    if consensus == C.BLOCK_GENESIS:
        return 1.0
    elif previous_hash == GENESIS_PREVIOUS_HASH:
        return 1.0

    base_difficulty_sum = MAX_TARGET * N
    target_diffs = list()
    target_hash = previous_hash
    while True:
        target_block = builder.get_block(target_hash)
        if target_block is None:
            return 1.0
        target_hash = target_block.previous_hash
        if target_hash == GENESIS_PREVIOUS_HASH:
            return 1.0
        elif target_block.flag == consensus and N > len(target_diffs):
            target_diffs.append(bits2target(target_block.bits) * (N-len(target_diffs)))
        elif len(target_diffs) >= N:
            break

    bias = base_difficulty_sum / sum(target_diffs)
    if Debug.F_SHOW_DIFFICULTY:
        print("bias", bias, hexlify(previous_hash).decode())
    return bias
