from bc4py.config import C, BlockChainError
from multiprocessing import get_context, current_process
import threading
import logging
from psutil import cpu_count
from os import urandom
from time import time, sleep
from yespower import hash as yespower_hash  # for CPU
from x11_hash import getPoWHash as x11_hash  # for ASIC
from hmq_hash import getPoWHash as hmq_hash  # for GPU
from pooled_multiprocessing import cpu_num


mp_generator = list()
mp_lock = threading.Lock()


def get_workhash_fnc(flag):
    if flag == C.BLOCK_YES_POW:
        return yespower_hash
    elif flag == C.BLOCK_X11_POW:
        return x11_hash
    elif flag == C.BLOCK_HMQ_POW:
        return hmq_hash
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
            address, coin_id, amount = output_tx.outputs[txindex]
            proof_tx.pos_amount = amount
        block.work_hash = proof_tx.get_pos_hash(block.previous_hash)
    else:
        # POW_???
        hash_fnc = get_workhash_fnc(block.flag)
        block.work_hash = hash_fnc(block.b)


def generate_many_hash(block, how_many):
    assert block.flag != C.BLOCK_POS and block.flag != C.BLOCK_GENESIS
    assert how_many > 0
    # hash generating with multi-core
    start = time()
    with mp_lock:
        while True:
            free_process = list()
            for hash_generator in mp_generator:
                if not hash_generator.lock.locked():
                    free_process.append(hash_generator)
            if len(free_process) > 0:
                break
            else:
                logging.debug("Wait for free_process...")
                sleep(0.1)
        request_num = how_many // len(free_process)
        # throw task
        for hash_generator in free_process:
            hash_generator.generate(block, request_num)
    block_b = None
    work_hash = None
    work_hash_int = 0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
    for hash_generator in free_process:
        tmp_block_b, check_hash = hash_generator.result()
        check_int = int.from_bytes(check_hash, 'big')
        if check_int < work_hash_int:
            block_b = tmp_block_b
            work_hash = check_hash
            work_hash_int = check_int
    block.b = block_b
    block.work_hash = work_hash
    block.deserialize()
    return time() - start


def start_work_hash(process=None):
    if current_process().name != 'MainProcess':
        raise Exception('Is not main process!')
    if len(mp_generator) != 0:
        raise Exception('Already mp_generator is filled.')
    if process is None:
        process = cpu_num
    for index in range(1, process + 1):
        # Want to use 1 core for main-thread
        hash_generator = HashGenerator(index=index)
        hash_generator.start()
        mp_generator.append(hash_generator)


def close_work_hash():
    for hash_generator in mp_generator:
        hash_generator.close()
    mp_generator.clear()
    logging.debug("Close hashing process.")


def _pow_generator(pipe):
    binary = None
    while True:
        try:
            binary, block_flag, how_many = pipe.recv()
            hash_fnc = get_workhash_fnc(block_flag)
            hashed = hash_fnc(binary)
            minimum_num = int.from_bytes(hashed, 'big')
            new_binary = binary
            for i in range(how_many):
                new_binary = new_binary[:-4] + urandom(4)
                new_hash = hash_fnc(new_binary)
                new_num = int.from_bytes(new_hash, 'big')
                if minimum_num > new_num:
                    binary = new_binary
                    hashed = new_hash
                    minimum_num = new_num
            pipe.send((binary, hashed))
        except Exception as e:
            msg = "Hashing failed {} by \"{}\"".format(binary, e)
            try:
                pipe.send(msg)
            except Exception as e:
                logging.info("Close by pipe error, {}".format(e))
                return


class HashGenerator:
    def __init__(self, index):
        self.index = index
        cxt = get_context('spawn')
        parent_conn, child_conn = cxt.Pipe()
        self.process = cxt.Process(
            target=_pow_generator, name="Hashing{}".format(index), args=(child_conn,))
        self.process.daemon = True
        self.parent_conn = parent_conn
        self.lock = threading.Lock()

    def start(self):
        self.process.start()
        logging.info("Start work hash gene {}".format(self.index))

    def close(self):
        if self.process.is_alive():
            self.process.terminate()
        self.parent_conn.close()

    def generate(self, block, how_many):
        self.lock.acquire()
        self.parent_conn.send((block.b, block.flag, how_many))

    def result(self):
        data = self.parent_conn.recv()
        self.lock.release()
        if isinstance(data, tuple):
            return data
        else:
            raise BlockChainError('Unknown status on pipe {}'.format(data))


__all__ = [
    "get_workhash_fnc",
    "start_work_hash",
    "update_work_hash",
    "generate_many_hash",
    "close_work_hash"
]
