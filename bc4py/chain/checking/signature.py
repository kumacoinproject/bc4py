from bc4py.config import V
from nem_ed25519.key import get_address
from nem_ed25519.signature import verify
from binascii import hexlify, unhexlify
from psutil import cpu_count
from threading import Event, Lock
from time import time
import pooled_multiprocessing
import logging


waiting = 0
event_waiting = Event()
verify_cashe = dict()  # {(pubkey, signature, txhash): address, ...}
limit_time = time()
limit_delete_set = set()
lock = Lock()
cpu_num = cpu_count(logical=False) or cpu_count(logical=True)


def _verify(pubkey, signature, txhash, tx_b, prefix):
    try:
        verify(msg=tx_b, sign=signature, pk=pubkey)
        address = get_address(pk=pubkey, prefix=prefix)
        return pubkey, signature, txhash, address
    except ValueError:
        error = "Failed verify tx {}".format(hexlify(txhash).decode())
        logging.debug(error)
    except BaseException as e:
        error = 'Signature verification error. "{}"'.format(e)
        logging.error(error)
    return pubkey, signature, txhash, error


def _callback(signed_list):
    global waiting
    try:
        with lock:
            for pubkey, signature, txhash, address in signed_list:
                verify_cashe[(pubkey, signature, txhash)] = address
            waiting -= 1
            event_waiting.set()
    except Exception as e:
        logging.error("{}: {}".format(e, signed_list))
    logging.debug("Callback finish {}sign".format(len(signed_list)))


def _delete_cashe():
    global limit_time
    del_num = 0
    with lock:
        for item in limit_delete_set:
            if item in verify_cashe:
                del verify_cashe[item]
                del_num += 1
        logging.debug("VerifyCash fleshed [{}/{}]".format(del_num, len(limit_delete_set)))
        limit_delete_set.clear()
        limit_delete_set.update(verify_cashe.keys())
        limit_time = time()


def batch_sign_cashe(txs):
    global waiting
    logging.debug("Verify signature {}tx".format(len(txs)))
    generate_list = list()
    # list need to verify
    with lock:
        for tx in txs:
            for pubkey, signature in tx.signature:
                if (pubkey, signature, tx.hash) not in verify_cashe:
                    generate_list.append((pubkey, signature, tx.hash, tx.b))
                    verify_cashe[(pubkey, signature, tx.hash)] = None
        # throw verify
        if len(generate_list) == 0:
            return
        elif len(generate_list) == 1:
            pubkey, signature, txhash, tx_b = generate_list[0]
            pubkey, signature, txhash, address = _verify(pubkey, signature, txhash, tx_b, V.BLOCK_PREFIX)
            verify_cashe[(pubkey, signature, txhash)] = address
        else:
            waiting += 1
            pooled_multiprocessing.mp_map_async(_verify, generate_list, callback=_callback, prefix=V.BLOCK_PREFIX)
            logging.debug("Put task {}sign to pool.".format(len(generate_list)))


def get_signed_cks(tx):
    signed_cks = set()
    for pubkey, signature, txhash in tuple(verify_cashe.keys()):
        if tx.hash == txhash:
            address = verify_cashe[(pubkey, signature, txhash)]
            if address is None:
                event_waiting.clear()
                event_waiting.wait(timeout=10)
                address = verify_cashe[(pubkey, signature, txhash)]
            if address is None:
                logging.debug("Retry get signature {} {}".format(address, tx))
                with lock:
                    del verify_cashe[(pubkey, signature, txhash)]
                batch_sign_cashe([tx])
                return get_signed_cks(tx)
            signed_cks.add(address)
    if len(signed_cks) > 0:
        return signed_cks
    else:
        batch_sign_cashe([tx])
        return get_signed_cks(tx)


def delete_signed_cashe(txhash_set):
    want_delete = set()
    for pubkey, signature, txhash in verify_cashe:
        if txhash in txhash_set:
            want_delete.add((pubkey, signature, txhash))
    with lock:
        for pairs in want_delete:
            del verify_cashe[pairs]
    if len(want_delete) > 0:
        logging.debug("VerifyCash delete [{}/{}]".format(len(want_delete), len(verify_cashe)))
    if limit_time < time() - 10800:
        _delete_cashe()


__all__ = [
    "batch_sign_cashe",
    "get_signed_cks",
    "delete_signed_cashe"
]
