from bc4py.config import max_workers, executor, executor_lock, C, BlockChainError
from bc4py_extension import poc_hash, poc_work, scope_index
from os import urandom
from time import time
from threading import BoundedSemaphore
from yespower import hash as yespower_hash  # for CPU
from x11_hash import getPoWHash as x11_hash  # for ASIC
from hmq_hash import getPoWHash as hmq_hash  # for GPU
from litecoin_scrypt import getPoWHash as ltc_hash  # for ASIC
from shield_x16s_hash import getPoWHash as x16s_hash  # for GPU
from logging import getLogger
from hashlib import sha256

log = getLogger('bc4py')
semaphore = BoundedSemaphore(value=max(1, max_workers - 1))


def get_workhash_fnc(flag):
    if flag == C.BLOCK_YES_POW:
        return yespower_hash
    elif flag == C.BLOCK_X11_POW:
        return x11_hash
    elif flag == C.BLOCK_HMQ_POW:
        return hmq_hash
    elif flag == C.BLOCK_LTC_POW:
        return ltc_hash
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
            from bc4py.database.builder import tx_builder
            txhash, txindex = proof_tx.inputs[0]
            output_tx = tx_builder.get_tx(txhash)
            if output_tx is None:
                raise BlockChainError('Not found output {} of {}'.format(proof_tx, block))
            address, coin_id, amount = output_tx.outputs[txindex]
            proof_tx.pos_amount = amount
        block.work_hash = get_stake_coin_hash(tx=proof_tx, previous_hash=block.previous_hash)
    elif block.flag == C.BLOCK_CAP_POS:
        proof_tx = block.txs[0]
        address, coin_id, amount = proof_tx.outputs[0]
        scope_hash = poc_hash(address=address, nonce=block.nonce)
        index = scope_index(block.previous_hash)
        block.work_hash = poc_work(
            time=block.time, scope_hash=scope_hash[index * 32:index*32 + 32], previous_hash=block.previous_hash)
    elif block.flag == C.BLOCK_FLK_POS:
        raise BlockChainError("unimplemented")
    else:
        # POW_???
        hash_fnc = get_workhash_fnc(block.flag)
        block.work_hash = hash_fnc(block.b)


def generate_many_hash(block, how_many):
    # CAUTION: mining by one core!
    assert how_many > 0
    # hash generating with multi-core
    with semaphore:
        start = time()
        with executor_lock:
            future = executor.submit(_pow_generator, block.b, block.flag, how_many)
        binary, hashed = future.result(timeout=120)
    if binary is None:
        raise Exception(hashed)
    block.b = binary
    block.work_hash = hashed
    block.deserialize()
    return time() - start


def _pow_generator(binary, block_flag, how_many):
    try:
        hash_fnc = get_workhash_fnc(block_flag)
        hashed = hash_fnc(binary)
        minimum_num = int.from_bytes(hashed, 'little')
        new_binary = binary
        for i in range(how_many):
            new_binary = new_binary[:-4] + urandom(4)
            new_hash = hash_fnc(new_binary)
            new_num = int.from_bytes(new_hash, 'little')
            if minimum_num > new_num:
                binary = new_binary
                hashed = new_hash
                minimum_num = new_num
        return binary, hashed
    except Exception as e:
        error = "Hashing failed {} by \"{}\"".format(binary, e)
        return None, error


__all__ = [
    "get_workhash_fnc",
    "update_work_hash",
    "generate_many_hash",
]
