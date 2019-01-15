from bc4py.config import V
from nem_ed25519.key import get_address
from nem_ed25519.signature import verify
from threading import Lock
from time import time, sleep
from pooled_multiprocessing import mp_map_async
from logging import getLogger

log = getLogger('bc4py')


verify_cashe = dict()  # {(pubkey, signature, txhash): address, ...}
limit_time = time()
limit_delete_set = set()
lock = Lock()


def _verify(pubkey, signature, txhash, tx_b, prefix):
    try:
        verify(msg=tx_b, sign=signature, pk=pubkey)
        address = get_address(pk=pubkey, prefix=prefix)
        return pubkey, signature, txhash, address
    except ValueError:
        error = "Failed verify tx {}".format(txhash.hex())
        log.debug(error)
    except Exception as e:
        error = 'Signature verification error. "{}"'.format(e)
        log.error(error)
    return pubkey, signature, txhash, error


def _callback(signed_list):
    try:
        with lock:
            for pubkey, signature, txhash, address in signed_list:
                verify_cashe[(pubkey, signature, txhash)] = address
    except Exception as e:
        log.error("{}: {}".format(e, signed_list))
    log.debug("Callback finish {}sign".format(len(signed_list)))


def _delete_cashe():
    global limit_time
    del_num = 0
    with lock:
        for item in limit_delete_set:
            if item in verify_cashe:
                del verify_cashe[item]
                del_num += 1
        log.debug("VerifyCash fleshed [{}/{}]".format(del_num, len(limit_delete_set)))
        limit_delete_set.clear()
        limit_delete_set.update(verify_cashe.keys())
        limit_time = time()


def batch_sign_cashe(txs):
    log.debug("Verify signature {}tx".format(len(txs)))
    for tx in txs:
        for sign in tx.signature:
            assert isinstance(sign, tuple), tx.getinfo()
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
            mp_map_async(_verify, generate_list, callback=_callback, prefix=V.BLOCK_PREFIX)
            log.debug("Put task {}sign to pool.".format(len(generate_list)))


def get_signed_cks(tx):
    failed = 200
    while failed > 0:
        try:
            signed_cks = set()
            for pubkey, signature, txhash in verify_cashe.keys():
                if txhash != tx.hash:
                    continue
                if (pubkey, signature) not in tx.signature:
                    continue
                address = verify_cashe[(pubkey, signature, txhash)]
                if address is None:
                    failed -= 1
                    sleep(0.02)
                    break  # retry
                signed_cks.add(address)
            else:
                if len(signed_cks) == len(tx.signature):
                    return signed_cks
                elif len(signed_cks) == 0:
                    batch_sign_cashe([tx])
                    failed -= 1
                    continue
                elif len(signed_cks) < len(tx.signature):
                    log.debug('Cannot get all signature, throw task. signed={}, include={}'
                                    .format(signed_cks, len(tx.signature)))
                    batch_sign_cashe([tx])
                    failed -= 1
                    sleep(0.02)
                    continue
                else:
                    raise Exception('Something wrong. signed={}, include={}'
                                    .format(signed_cks, len(tx.signature)))
        except RuntimeError:
            # dictionary changed size during iteration
            failed -= 1
            sleep(0.02)
    raise Exception("Too match failed get signed_cks.")


def delete_signed_cashe(txhash_set):
    want_delete_num = 0
    with lock:
        for pair in verify_cashe.copy():
            pubkey, signature, txhash = pair
            if txhash in txhash_set and pair in verify_cashe:
                del verify_cashe[pair]
                want_delete_num += 1
    if want_delete_num > 0:
        log.debug("VerifyCash delete [{}/{}]".format(want_delete_num, len(verify_cashe)))
    if limit_time < time() - 10800:
        _delete_cashe()


__all__ = [
    "batch_sign_cashe",
    "get_signed_cks",
    "delete_signed_cashe"
]
