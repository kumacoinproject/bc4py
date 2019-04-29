from bc4py.config import executor, executor_lock, C, V
from bc4py.bip32 import get_address
from multi_party_schnorr import verify_auto
from threading import Lock
from time import time, sleep
from logging import getLogger
from more_itertools import chunked

log = getLogger('bc4py')

verify_cashe = dict()  # {(pk, r, s, txhash): address, ...}
limit_time = time()
limit_delete_set = set()
lock = Lock()


def _verify(task_list, hrp, ver):
    signed_list = list()
    for pk, r, s, txhash, binary in task_list:
        try:
            if verify_auto(s, r, pk, binary):
                address = get_address(pk=pk, hrp=hrp, ver=ver)
                signed_list.append((pk, r, s, txhash, address))
                # log.warning('verification success\n pk={}\n r={}\n s={}\n hash={}\n binary={}'
                #            .format(pk.hex(), r.hex(), s.hex(), txhash.hex(), binary.hex()))
            else:
                log.warning('verification failed\n pk={}\n r={}\n s={}\n hash={}\n binary={}'
                            .format(pk.hex(), r.hex(), s.hex(), txhash.hex(), binary.hex()))
        except Exception as e:
            log.error('Signature verification error. "{}"'.format(e))
    return signed_list


def _callback(future):
    signed_list = future.result()
    try:
        with lock:
            for pk, r, s, txhash, address in signed_list:
                verify_cashe[(pk, r, s, txhash)] = address
    except Exception as e:
        log.error("{}: {}".format(e, signed_list))
    log.debug("finish verify signature num={}".format(len(signed_list)))


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


def batch_sign_cashe(txs, b_block=None):
    for tx in txs:
        for sign in tx.signature:
            assert isinstance(sign, tuple), tx.getinfo()
    task_list = list()
    # list need to verify
    with lock:
        for tx in txs:
            if tx.type == C.TX_POS_REWARD:
                assert b_block is not None, 'PoS TX but no block binary input'
                binary = b_block
            else:
                binary = tx.b
            for pk, r, s in tx.signature:
                if (pk, r, s, tx.hash) not in verify_cashe:
                    task_list.append((pk, r, s, tx.hash, binary))
                    verify_cashe[(pk, r, s, tx.hash)] = None
    # throw verify
    if len(task_list) == 0:
        return
    else:
        log.debug("try to verify signature num={}".format(len(task_list)))
        with executor_lock:
            for task in chunked(task_list, 25):
                executor.submit(_verify, task, hrp=V.BECH32_HRP, ver=C.ADDR_NORMAL_VER).add_done_callback(_callback)


def get_signed_cks(tx):
    failed = 200
    while failed > 0:
        try:
            signed_cks = set()
            for pk, r, s, txhash in verify_cashe.keys():
                if txhash != tx.hash:
                    continue
                if (pk, r, s) not in tx.signature:
                    continue
                address = verify_cashe[(pk, r, s, txhash)]
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
                    log.debug('Cannot get all signature, throw task. signed={}, include={}'.format(
                        signed_cks, len(tx.signature)))
                    batch_sign_cashe([tx])
                    failed -= 1
                    sleep(0.02)
                    continue
                else:
                    raise Exception('Something wrong. signed={}, include={}'.format(signed_cks, len(tx.signature)))
        except RuntimeError:
            # dictionary changed size during iteration
            failed -= 1
            sleep(0.02)
    raise Exception("Too match failed get signed_cks.")


def delete_signed_cashe(txhash_set):
    want_delete_num = 0
    with lock:
        for pair in verify_cashe.copy():
            pk, r, s, txhash = pair
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
    "delete_signed_cashe",
]
