from bc4py.config import C
import multiprocessing as mp
import threading
import logging
import yespower
# import yescryptr16
# import yescryptr64
# import zny_yescrypt
# import hmq_hash

generator = None
parent_conn = None
child_conn = None
lock = None


def _generator(pipe):
    while True:
        b = h = None
        try:
            b = pipe.recv_bytes()
            h = yespower.hash(b)
            pipe.send_bytes(h)
        except BaseException:
            logging.error("Hashing failed {}".format(b))


def start_work_hash():
    global parent_conn, child_conn, generator, lock
    if mp.cpu_count() < 2:
        logging.warning("Only one cpu you have. disabled hashing thread.")
    elif len(mp.active_children()) == 0:
        logging.debug("Hashing module start.")
        parent_conn, child_conn = mp.Pipe()
        generator = mp.Process(target=_generator, name="Hashing", args=(child_conn,))
        generator.daemon = True
        generator.start()
        lock = threading.Lock()
    else:
        raise BaseException('Some multiprocess already working.')


def update_work_hash(block):
    if block.flag == C.BLOCK_POS:
        proof_tx = block.txs[0]
        block.work_hash = proof_tx.get_pos_hash(block.previous_hash)
    elif block.flag == C.BLOCK_POW:
        if parent_conn is None:
            block.work_hash = yespower.hash(block.b)
        else:
            with lock:
                parent_conn.send_bytes(block.b)
                block.work_hash = parent_conn.recv_bytes()
    elif block.flag == C.BLOCK_GENESIS:
        block.work_hash = b'\xff' * 32


def close_work_hash():
    global generator, parent_conn, child_conn
    generator.terminate()
    parent_conn.close()
    child_conn.close()
    logging.debug("Close hashing process.")


__all__ = [
    "start_work_hash",
    "update_work_hash",
    "close_work_hash"
]
