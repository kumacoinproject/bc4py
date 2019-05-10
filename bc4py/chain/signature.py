from bc4py.config import C, V
from bc4py.bip32 import get_address
from multi_party_schnorr import verify_auto_multi
from logging import getLogger
from os import cpu_count
from time import time

log = getLogger('bc4py')
n_workers = cpu_count()


def fill_verified_addr_single(block):
    # format check
    for tx in block.txs:
        for sign in tx.signature:
            assert isinstance(sign, tuple), tx.getinfo()
    # get data to verify
    tasks = get_verify_tasks(block)
    # throw task
    if len(tasks) == 0:
        return
    throw_tasks(tasks, V.BECH32_HRP, C.ADDR_NORMAL_VER)


def fill_verified_addr_many(blocks):
    s = time()
    # format check
    tasks = dict()
    for block in blocks:
        for tx in block.txs:
            for sign in tx.signature:
                assert isinstance(sign, tuple), tx.getinfo()
        # get data to verify
        tasks.update(get_verify_tasks(block))
    # throw task
    if len(tasks) == 0:
        return
    throw_tasks(tasks, V.BECH32_HRP, C.ADDR_NORMAL_VER)
    log.debug("verify {} signs by {}sec".format(len(tasks), round(time() - s, 3)))


def get_verify_tasks(block):
    tasks = dict()
    for tx in block.txs:
        if tx.type == C.TX_POS_REWARD:
            binary = block.b
        else:
            binary = tx.b
        if len(tx.verified_list) == len(tx.signature):
            continue
        for pk, r, s in tx.signature:
            tasks[(s, r, pk, binary)] = tx
    return tasks


def throw_tasks(tasks, hrp, ver):
    task_list = list(tasks.keys())
    result_list = verify_auto_multi(task_list, n_workers, False)
    # fill result
    for is_verify, key in zip(result_list, task_list):
        if not is_verify:
            continue
        if key not in tasks:
            continue
        s, r, pk, binary = key
        address = get_address(pk=pk, hrp=hrp, ver=ver)
        tasks[key].verified_list.append(address)


__all__ = [
    "fill_verified_addr_single",
    "fill_verified_addr_many",
]
