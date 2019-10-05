from bc4py.config import C, BlockChainError
from bc4py_extension import poc_hash, poc_work, scope_index
from bc4py.database.tools import get_output_from_input
from concurrent.futures import ProcessPoolExecutor
from bell_yespower import getPoWHash as yespower_hash  # for CPU
from x11_hash import getPoWHash as x11_hash  # for ASIC
from shield_x16s_hash import getPoWHash as x16s_hash  # for GPU
from logging import getLogger
from hashlib import sha256
from os import urandom
from time import time
import asyncio
import psutil
import atexit


loop = asyncio.get_event_loop()
log = getLogger('bc4py')


def get_workhash_fnc(flag):
    if flag == C.BLOCK_YES_POW:
        return yespower_hash
    elif flag == C.BLOCK_X11_POW:
        return x11_hash
    elif flag == C.BLOCK_HMQ_POW:
        raise NotImplementedError
    elif flag == C.BLOCK_LTC_POW:
        raise NotImplementedError
    elif flag == C.BLOCK_X16S_POW:
        return x16s_hash
    elif flag in C.consensus2name:
        raise Exception('Not found block flag {}'.format(C.consensus2name[flag]))
    else:
        raise Exception('Not found block flag {}?'.format(flag))


def get_stake_coin_hash(tx, previous_hash):
    # stake_hash => sha256(txhash + previous_hash) / amount
    assert tx.pos_amount is not None
    pos_work_hash = sha256(tx.hash + previous_hash).digest()
    work = int.from_bytes(pos_work_hash, 'little')
    work //= (tx.pos_amount // 100000000)
    return work.to_bytes(32, 'little')


def update_work_hash(block):
    if block.flag == C.BLOCK_GENESIS:
        block.work_hash = b'\xff' * 32
    elif block.flag == C.BLOCK_COIN_POS:
        proof_tx = block.txs[0]
        if proof_tx.pos_amount is None:
            txhash, txindex = proof_tx.inputs[0]
            pair = get_output_from_input(input_hash=txhash, input_index=txindex, best_block=block)
            if pair is None:
                raise BlockChainError('Not found output {} of {}'.format(proof_tx, block))
            address, coin_id, amount = pair
            proof_tx.pos_amount = amount
        block.work_hash = get_stake_coin_hash(tx=proof_tx, previous_hash=block.previous_hash)
    elif block.flag == C.BLOCK_CAP_POS:
        proof_tx = block.txs[0]
        address, coin_id, amount = proof_tx.outputs[0]
        scope_hash = poc_hash(address=address.string, nonce=block.nonce)
        index = scope_index(block.previous_hash)
        block.work_hash = poc_work(
            time=block.time, scope_hash=scope_hash[index * 32:index*32 + 32], previous_hash=block.previous_hash)
    elif block.flag == C.BLOCK_FLK_POS:
        raise BlockChainError("unimplemented")
    else:
        # POW_???
        hash_fnc = get_workhash_fnc(block.flag)
        block.work_hash = hash_fnc(block.b)


async def generate_many_hash(executor: ProcessPoolExecutor, block, request_num):
    assert request_num > 0
    # hash generating with multi-core
    future: asyncio.Future = loop.run_in_executor(
        executor, pow_generator, block.b, block.flag, request_num)
    await asyncio.wait_for(future, 120.0)
    binary, hashed, start = future.result()
    if binary is None:
        raise Exception(hashed)
    block.b = binary
    block.work_hash = hashed
    block.deserialize()
    return time() - start


def pow_generator(binary, block_flag, request_num):
    start = time()
    try:
        hash_fnc = get_workhash_fnc(block_flag)
        hashed = hash_fnc(binary)
        minimum_num = int.from_bytes(hashed, 'little')
        new_binary = binary
        for _ in range(request_num):
            new_binary = new_binary[:-4] + urandom(4)
            new_hash = hash_fnc(new_binary)
            new_num = int.from_bytes(new_hash, 'little')
            if minimum_num > new_num:
                binary = new_binary
                hashed = new_hash
                minimum_num = new_num
        return binary, hashed, start
    except Exception as e:
        error = "Hashing failed {} by \"{}\"".format(binary, e)
        return None, error, start


def get_executor_object(max_workers=None):
    """PoW mining process generator"""
    if max_workers is None:
        max_process_num = 4
        logical_cpu_num = psutil.cpu_count(logical=True) or max_process_num
        physical_cpu_nam = psutil.cpu_count(logical=False) or max_process_num
        max_workers = min(logical_cpu_num, physical_cpu_nam)
    executor = ProcessPoolExecutor(max_workers)
    atexit.register(executor.shutdown, wait=True)
    return executor


__all__ = [
    "get_workhash_fnc",
    "update_work_hash",
    "generate_many_hash",
    "get_executor_object",
]
