from bc4py.config import max_workers, executor, C, BlockChainError
from os import urandom
from time import time
from threading import BoundedSemaphore
from yespower import hash as yespower_hash  # for CPU
from x11_hash import getPoWHash as x11_hash  # for ASIC
from hmq_hash import getPoWHash as hmq_hash  # for GPU
from litecoin_scrypt import getPoWHash as ltc_hash  # for ASIC
from shield_x16s_hash import getPoWHash as x16s_hash  # for GPU
from logging import getLogger

log = getLogger('bc4py')
semaphore = BoundedSemaphore(value=max(1, max_workers-1))


def self_check_hash_fnc():
    check_hash = b'\x00' * 80
    check_list = [
        (yespower_hash, b'z\x1b\xde\x0c\x01\xec\xc1\xd3\xdf\x86{\xb2;\x97>\xee\xbc\x96\xfd'
                        b'\x83[\x14sv\xca\xe9\xf9\xa7\x04t\xe0F'),
        (x11_hash, b'\x83(\x84a\x80\x96[\xceV\xf6\x1e\x01]\xb6*\xf5b\xa6\x11\xd8^^r\x1d\x85L\x8d\x97\xe4z>\xa3'),
        (hmq_hash, b'\xf9\xf2~\xbc\x96=\xe0\xed\xff\xd0\xd3&\xe5\xab&\xea\xe1\xec'
                   b'\x0f\x031\n\xdf\x12\xf1b zT\xeb\xd6\x86'),
        (ltc_hash, b'\x16\x1d\x08v\xf3\xb9;\x10H\xcd\xa1\xbd\xea\xa73.\xe2\x10\xf7'
                   b'\x13\x1bB\x01<\xb49\x13\xa6U:Ki'),
        (x16s_hash, b'\xcc\xa6\x1bVE\xd4\xcez3\x9b\xbf\xba\x80\x05\xeb\xd3\xa5\x86\x9bW'
                    b'\x01\xf8\xb6\xe5a\xc3\x9e\xd9\x8c\xca\x02\x1a')]
    for hash_fnc, correct_hash in check_list:
        if hash_fnc(check_hash) != correct_hash:
            raise Exception('self check failed, hash module "{}".'.format(hash_fnc.__module__))


def get_workhash_fnc(flag):
    if flag == C.BLOCK_YES_POW:
        return yespower_hash
    elif flag == C.BLOCK_X11_POW:
        return x11_hash
    elif flag == C.BLOCK_HMQ_POW:
        return hmq_hash
    elif flag == C.BLOCK_LTC_POW:
        return ltc_hash
    elif flag == C.BLOCK_X16R_POW:
        return x16s_hash
    elif flag in C.consensus2name:
        raise Exception('Not found block flag {}'.format(C.consensus2name[flag]))
    else:
        raise Exception('Not found block flag {}?'.format(flag))


def update_work_hash(block):
    if block.flag == C.BLOCK_GENESIS:
        block.work_hash = b'\xff' * 32
    elif block.flag == C.BLOCK_POS:
        proof_tx = block.txs[0]
        if proof_tx.pos_amount is None:
            from bc4py.database.builder import tx_builder
            txhash, txindex = proof_tx.inputs[0]
            output_tx = tx_builder.get_tx(txhash)
            if output_tx is None:
                raise BlockChainError('Not found output {} of {}'.format(proof_tx, block))
            address, coin_id, amount = output_tx.outputs[txindex]
            proof_tx.pos_amount = amount
        block.work_hash = proof_tx.get_pos_hash(block.previous_hash)
    else:
        # POW_???
        hash_fnc = get_workhash_fnc(block.flag)
        block.work_hash = hash_fnc(block.b)


def generate_many_hash(block, how_many):
    # CAUTION: mining by one core!
    assert block.flag != C.BLOCK_POS and block.flag != C.BLOCK_GENESIS
    assert how_many > 0
    # hash generating with multi-core
    with semaphore:
        start = time()
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


self_check_hash_fnc()


__all__ = [
    "get_workhash_fnc",
    "update_work_hash",
    "generate_many_hash",
]
