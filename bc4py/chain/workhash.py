from bc4py.config import C, BlockChainError
import multiprocessing as mp
import threading
import logging
from psutil import cpu_count
from os import urandom
from time import time
from yespower import hash as yespower_hash  # for CPU
from x11_hash import getPoWHash as x11_hash  # for ASIC
from hmq_hash import getPoWHash as hmq_hash  # for GPU


mp_generator = list()
cpu_num = cpu_count(logical=False) or cpu_count(logical=True)


def proof_of_work_decoder(flag):
    if flag == C.BLOCK_YES_POW:
        return yespower_hash
    elif flag == C.BLOCK_X11_POW:
        return x11_hash
    elif flag == C.BLOCK_HMQ_POW:
        return hmq_hash
    elif flag in C.consensus2name:
        raise Exception('Not found block flag {}'.format(C.consensus2name[flag]))
    else:
        raise Exception('Not found block flag {}'.format(flag))


def update_work_hash(block, how_many=0):
    if block.flag == C.BLOCK_GENESIS:
        block.work_hash = b'\xff' * 32
    if block.flag == C.BLOCK_POS:
        proof_tx = block.txs[0]
        block.work_hash = proof_tx.get_pos_hash(block.previous_hash)
    elif len(mp_generator) == 0:
        # Only 1 CPU or subprocess
        hash_fnc = proof_of_work_decoder(block.flag)
        block.work_hash = hash_fnc(block.b)
    elif how_many == 0:
        # only one gene blockhash
        for hash_generator in mp_generator:
            if hash_generator.lock.locked():
                continue
            hash_generator.generate(block, how_many)
            dummy, block.work_hash = hash_generator.result()
            return
        else:
            hash_fnc = proof_of_work_decoder(block.flag)
            block.work_hash = hash_fnc(block.b)
    else:
        # hash generating with multi-core
        start = time()
        free_process = list()
        for hash_generator in mp_generator:
            if not hash_generator.lock.locked():
                free_process.append(hash_generator)
        request_num = how_many // max(1, len(free_process))
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
        logging.debug("{} mining... {}kh/S by {}Core".format(
            C.consensus2name[block.flag], round(how_many/(time()-start)/1000, 3), len(free_process)))


def start_work_hash():
    if cpu_num < 2:
        logging.warning("Only one cpu you have. disabled hashing thread.")
    elif mp.current_process().daemon is False:
        logging.debug("Hashing module start.")
        for index in range(1, cpu_num):
            # Want to use 1 core for main-thread
            hash_generator = HashGenerator(index)
            hash_generator.start()
            mp_generator.append(hash_generator)
    else:
        raise Exception('You try to create mp on subprocess.')


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
            hash_fnc = proof_of_work_decoder(block_flag)
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
        parent_conn, child_conn = mp.Pipe()
        self.process = mp.Process(target=_pow_generator,
                                  name="Hashing{}".format(index),
                                  args=(child_conn,))
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
    "proof_of_work_decoder",
    "start_work_hash",
    "update_work_hash",
    "close_work_hash"
]
