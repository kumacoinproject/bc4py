from bc4py.config import C, V, P, BlockChainError
from bc4py.bip32 import is_address
from bc4py.chain.block import Block
from bc4py.chain.tx import TX
from bc4py.chain.workhash import generate_many_hash, get_executor_object, update_work_hash
from bc4py.chain.difficulty import get_bits_by_hash
from bc4py.chain.utils import GompertzCurve
from bc4py.chain.checking.utils import stake_coin_check
from bc4py.database.create import create_db
from bc4py.database.account import sign_message_by_address, generate_new_address_by_userid
from bc4py.database.tools import get_my_unspents_iter
from bc4py_extension import multi_seek, PyAddress
from concurrent.futures import ProcessPoolExecutor
from time import time
from collections import deque
from random import random
from logging import getLogger
from typing import Optional, List, AnyStr
import traceback
import asyncio
import os
import re

loop = asyncio.get_event_loop()
log = getLogger('bc4py')
generating_threads: List['Generate'] = list()
output_que = asyncio.Queue(maxsize=1)
# mining share info
mining_address: Optional[PyAddress] = None
mining_address_lock = asyncio.Lock()
previous_block: Optional[Block] = None
unconfirmed_txs: Optional[List] = None
unspents_txs: Optional[List] = None
staking_limit = 500
optimize_file_name_re = re.compile("^optimized\\.([a-z0-9]+)\\-([0-9]+)\\-([0-9]+)\\.dat$")
executor: Optional['ProcessPoolExecutor'] = None


class Generate(object):

    def __init__(self, consensus, power_limit=1.0, **kwargs):
        assert consensus in V.BLOCK_CONSENSUSES
        assert 0.0 < power_limit <= 1.0
        self.consensus = consensus
        self.power_limit = min(1.0, max(0.01, power_limit))
        self.hashrate = (0, 0.0)  # [hash/s, update_time]
        self.f_enable = True
        self.config = kwargs
        # generate process executor
        global executor
        if executor is None:
            executor = get_executor_object()
        generating_threads.append(self)
        # self.task = asyncio.ensure_future(self.start_loop())
        self.task = asyncio.run_coroutine_threadsafe(self.start_loop(), loop)
        log.info(f"setup generating {C.consensus2name[consensus]}")

    def __repr__(self):
        hashrate, ntime = self.hashrate
        if time() - ntime > 120:
            data = "NotActive ({}minutes before updated)".format(round((time() - ntime) / 60, 1))
        elif hashrate < 1000 * 10:
            data = "{}hash/s".format(hashrate)
        elif hashrate < 1000 * 1000 * 10:
            data = "{}kh/s".format(round(hashrate / 1000, 2))
        else:
            data = "{}Mh/s".format(round(hashrate / 1000000, 3))
        return "<Generate {} {} limit={}>".format(C.consensus2name[self.consensus], data, self.power_limit)

    def close(self):
        self.f_enable = False
        self.task.cancel()

    async def start_loop(self):
        while self.f_enable:
            while P.F_NOW_BOOTING:
                # wait for booting finish
                await asyncio.sleep(1)
            log.info(f"start generating {C.consensus2name[self.consensus]}!")
            try:
                if self.consensus == C.BLOCK_COIN_POS:
                    await self.proof_of_stake()
                elif self.consensus == C.BLOCK_CAP_POS:
                    await self.proof_of_capacity()
                elif self.consensus == C.BLOCK_FLK_POS:
                    raise BlockChainError("unimplemented")
                else:
                    await self.proof_of_work()
            except FailedGenerateWarning as e:
                log.debug("skip by \"{}\"".format(e))
            except BlockChainError as e:
                log.warning(e)
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                log.info(f"generate task canceled {C.consensus2name[self.consensus]}")
                break
            except AttributeError:
                if 'previous_block.' in str(traceback.format_exc()):
                    log.debug("attribute error of previous_block, passed")
                    await asyncio.sleep(1)
                else:
                    log.error("Unknown error, wait 60s", exc_info=True)
                    await asyncio.sleep(60)
            except KeyError as e:
                log.debug("Key error by lru_cache bug wait 5s... \"{}\"".format(e))
                await asyncio.sleep(5)
            except Exception:
                log.error("GeneratingError, wait60s", exc_info=True)
                await asyncio.sleep(60)

    async def proof_of_work(self):
        global mining_address
        spans_deque = deque(maxlen=8)
        request_num = 100
        base_span = 10
        work_span = base_span * self.power_limit
        sleep_span = base_span * (1.0 - self.power_limit)
        while self.f_enable:
            # check start mining
            if previous_block is None or unconfirmed_txs is None:
                await asyncio.sleep(0.1)
                continue
            mining_block = await create_mining_block(self.consensus)
            # throw task
            new_span = await generate_many_hash(executor, mining_block, request_num)
            spans_deque.append(new_span)
            # check block
            update_work_hash(mining_block)
            if previous_block is None or unconfirmed_txs is None:
                log.debug("Not confirmed new block by \"nothing params\"")
            elif previous_block.hash != mining_block.previous_hash:
                log.debug("Not confirmed new block by \"Don't match previous_hash\"")
            elif not mining_block.pow_check():
                if int(time()) % 90 == 0:
                    log.debug("Not confirmed new block by \"proof of work unsatisfied\"")
            else:
                # Mined yay!!!
                await confirmed_generating_block(mining_block)
                mining_address = None
            # generate next mining request_num
            try:
                self.hashrate = (request_num * len(spans_deque) // sum(spans_deque), time())
                bias = sum(work_span * i for i, span in enumerate(spans_deque))
                bias /= sum(span * i for i, span in enumerate(spans_deque))
                bias = min(2.0, max(0.5, bias))
                request_num = max(100, int(request_num * bias))
                if int(time()) % 90 == 0:
                    log.info("Mining... Next target request_num is {} {}".format(request_num,
                                                                              "Up" if bias > 1 else "Down"))
            except ZeroDivisionError:
                pass
            await asyncio.sleep(sleep_span + random() - 0.5)
        log.info("Close signal")

    async def proof_of_stake(self):
        global staking_limit
        limit_deque = deque(maxlen=10)
        while self.f_enable:
            # check start mining
            if previous_block is None or unconfirmed_txs is None or unspents_txs is None:
                await asyncio.sleep(0.1)
                continue
            if len(unspents_txs) == 0:
                log.info("No unspents for staking, wait 180s")
                await asyncio.sleep(180)
                continue
            start = time()
            # create staking block
            bits, target = get_bits_by_hash(previous_hash=previous_block.hash, consensus=C.BLOCK_COIN_POS)
            reward = GompertzCurve.calc_block_reward(previous_block.height + 1)
            staking_block = Block.from_dict(
                block={
                    'version': 0,  # always 0
                    'merkleroot': b'\xff' * 32,
                    'time': 0,
                    'previous_hash': previous_block.hash,
                    'bits': bits,
                    'nonce': b'\xff\xff\xff\xff'
                })
            staking_block.height = previous_block.height + 1
            staking_block.flag = C.BLOCK_COIN_POS
            staking_block.bits2target()
            staking_block.txs.append(None)  # Dummy proof tx
            if unconfirmed_txs is None:
                raise FailedGenerateWarning('unconfirmed_txs is None')
            staking_block.txs.extend(unconfirmed_txs)
            calculate_nam = 0
            for proof_tx in unspents_txs.copy():
                address = proof_tx.outputs[0][0]
                proof_tx.outputs[0] = (address, 0, proof_tx.pos_amount + reward)
                proof_tx.update_time()
                calculate_nam += 1
                # next check block
                if previous_block is None or unconfirmed_txs is None or unspents_txs is None:
                    log.debug("Reset by \"nothing params found\"")
                    await asyncio.sleep(1)
                    break
                elif previous_block.hash != staking_block.previous_hash:
                    log.debug("Reset by \"Don't match previous_hash\"")
                    await asyncio.sleep(1)
                    break
                elif not stake_coin_check(
                        tx=proof_tx, previous_hash=previous_block.hash, target_hash=staking_block.target_hash):
                    continue
                else:
                    # Staked yay!!
                    proof_tx.height = staking_block.height
                    staking_block.txs[0] = proof_tx
                    # Fit block size
                    while staking_block.size > C.SIZE_BLOCK_LIMIT:
                        staking_block.txs.pop()
                    staking_block.update_time(proof_tx.time)
                    staking_block.update_merkleroot()
                    async with create_db(V.DB_ACCOUNT_PATH) as db:
                        cur = await db.cursor()
                        signature = await sign_message_by_address(
                            raw=staking_block.b, address=address, cur=cur)
                    proof_tx.signature.append(signature)
                    update_work_hash(staking_block)
                    await confirmed_generating_block(staking_block)
                    break
            else:
                # check time
                used = time() - start
                remain = 1.0 - used
                max_limit = max(50, int(calculate_nam / max(0.0001, used)))
                limit_deque.append(int(max_limit * self.power_limit))
                staking_limit = sum(limit_deque) // len(limit_deque)
                if int(time()) % 90 == 0:
                    log.info("Staking... margin={}% limit={}".format(round(remain * 100, 1), staking_limit))
                self.hashrate = (calculate_nam, time())
                await asyncio.sleep(max(0.0, remain + random() - 0.5))
        log.info("Close signal")

    async def proof_of_capacity(self):
        dir_path: str = self.config.get('path', os.path.join(V.DB_HOME_DIR, 'plots'))
        while self.f_enable:
            # check start mining
            if previous_block is None or unconfirmed_txs is None:
                await asyncio.sleep(0.1)
                continue
            if not os.path.exists(dir_path):
                await asyncio.sleep(30)
                continue
            s = time()
            previous_hash = previous_block.hash
            height = previous_block.height + 1
            block_time = int(s - V.BLOCK_GENESIS_TIME)
            bits, target = get_bits_by_hash(previous_hash=previous_hash, consensus=C.BLOCK_CAP_POS)
            reward = GompertzCurve.calc_block_reward(height)

            # start staking by capacity
            count = 0
            for file_name in os.listdir(dir_path):
                m = optimize_file_name_re.match(file_name)
                if m is None:
                    continue
                count += int(m.group(3)) - int(m.group(2))
            if count < 1:
                log.debug("not found plot file, wait 60 sec")
                await asyncio.sleep(60)
                continue

            # let's seek files
            future: asyncio.Future = loop.run_in_executor(
                None, multi_seek,
                dir_path, previous_hash, target.to_bytes(32, 'little'), block_time, os.cpu_count())
            await asyncio.wait_for(future, 60.0)
            nonce, work_hash, address = future.result()
            if work_hash is None:
                # return failed => (None, None, err-msg)
                if int(s) % 300 == 0:
                    log.debug("PoC mining info by \"{}\"".format(address))
            else:
                # return success => (nonce, workhash, address)
                address: PyAddress = PyAddress.from_string(address)
                if previous_block is None or unconfirmed_txs is None:
                    continue
                if previous_block.hash != previous_hash:
                    continue
                # Staked by capacity yay!!
                total_fee = sum(tx.gas_price * tx.gas_amount for tx in unconfirmed_txs)
                staked_block = Block.from_dict(
                    block={
                        'version': 0,  # always 0
                        'previous_hash': previous_hash,
                        'merkleroot': b'\x00' * 32,
                        'time': 0,
                        'bits': bits,
                        'nonce': nonce,
                        'height': height,
                        'flag': C.BLOCK_CAP_POS
                    })
                staked_proof_tx = TX.from_dict(
                    tx={
                        'type': C.TX_POS_REWARD,
                        'time': block_time,
                        'deadline': block_time + 10800,
                        'gas_price': 0,
                        'gas_amount': 0,
                        'outputs': [(address, 0, reward + total_fee)]
                    })
                staked_block.txs.append(staked_proof_tx)
                staked_block.txs.extend(unconfirmed_txs)
                while staked_block.size > C.SIZE_BLOCK_LIMIT:
                    staked_block.txs.pop()
                staked_block.update_time(staked_proof_tx.time)
                staked_block.update_merkleroot()
                staked_block.work_hash = work_hash
                async with create_db(V.DB_ACCOUNT_PATH) as db:
                    cur = await db.cursor()
                    signature = await sign_message_by_address(
                        raw=staked_block.b, address=address, cur=cur)
                staked_proof_tx.signature.append(signature)
                await confirmed_generating_block(staked_block)

            # finish all
            used_time = time() - s
            self.hashrate = (count, time())
            await asyncio.sleep(max(1 - used_time, 0))
        log.info("Close signal")


async def create_mining_block(consensus):
    global mining_address
    # setup mining address for PoW
    async with mining_address_lock:
        if mining_address is None:
            if V.MINING_ADDRESS is None:
                async with create_db(V.DB_ACCOUNT_PATH) as db:
                    cur = await db.cursor()
                    mining_address = await generate_new_address_by_userid(C.ANT_UNKNOWN, cur)
                    await db.commit()
            else:
                mining_address = V.MINING_ADDRESS
    if unconfirmed_txs is None:
        raise FailedGenerateWarning('unconfirmed_txs is None')
    if previous_block is None:
        raise FailedGenerateWarning('previous_block is None')
    # create proof_tx
    reward = GompertzCurve.calc_block_reward(previous_block.height + 1)
    fees = sum(tx.gas_amount * tx.gas_price for tx in unconfirmed_txs)
    proof_tx = TX.from_dict(
        tx={
            'type': C.TX_POW_REWARD,
            'inputs': list(),
            'outputs': [(mining_address, 0, reward + fees)],
            'gas_price': 0,
            'gas_amount': 0,
            'message_type': C.MSG_NONE,
            'message': b''
        })
    proof_tx.update_time()
    # create mining block
    bits, target = get_bits_by_hash(previous_hash=previous_block.hash, consensus=consensus)
    mining_block = Block.from_dict(
        block={
            'merkleroot': b'\xff' * 32,
            'time': 0,
            'previous_hash': previous_block.hash,
            'bits': bits,
            'nonce': b'\xff\xff\xff\xff'
        })
    proof_tx.height = previous_block.height + 1
    mining_block.height = proof_tx.height
    mining_block.flag = consensus
    mining_block.bits2target()
    mining_block.txs.append(proof_tx)
    if unconfirmed_txs is None:
        raise FailedGenerateWarning('unconfirmed_txs is None')
    mining_block.txs.extend(unconfirmed_txs)
    mining_block.update_merkleroot()
    mining_block.update_time(proof_tx.time)
    return mining_block


async def confirmed_generating_block(new_block):
    assert new_block.work_hash is not None, new_block
    log.info("Generate block yey!! {}".format(new_block))
    global previous_block, unconfirmed_txs, unspents_txs
    previous_block = None
    unconfirmed_txs = None
    unspents_txs = None
    # timeout: GeneBlock thread do not start?
    await asyncio.wait_for(output_que.put(new_block), 30.0)


def update_previous_block(new_previous_block):
    global previous_block
    previous_block = new_previous_block


def update_unconfirmed_txs(new_unconfirmed_txs):
    global unconfirmed_txs
    unconfirmed_txs = new_unconfirmed_txs


async def update_unspents_txs():
    global unspents_txs
    while previous_block is None:
        await asyncio.sleep(0.1)
    previous_height = previous_block.height
    proof_txs = list()
    all_num = 0
    async with create_db(V.DB_ACCOUNT_PATH) as db:
        cur = await db.cursor()
        unspent_iter = await get_my_unspents_iter(cur)
        async for address, height, txhash, txindex, coin_id, amount in unspent_iter:
            all_num += 1
            if previous_block is None:
                proof_txs.clear()
                break  # new block detected
            if previous_height != previous_block.height:
                proof_txs.clear()
                break  # new block detected
            if height is None:
                continue
            if coin_id != 0:
                continue
            if not (previous_height + 1 > height + C.MATURE_HEIGHT):
                continue
            if not is_address(ck=address, hrp=V.BECH32_HRP, ver=C.ADDR_NORMAL_VER):
                continue
            if amount < 100000000:
                continue
            if staking_limit < len(proof_txs):
                log.debug("Unspents limit reached, skip by {} limits".format(staking_limit))
                break
            proof_tx = TX.from_dict(
                tx={
                    'type': C.TX_POS_REWARD,
                    'inputs': [(txhash, txindex)],
                    'outputs': [(address, 0, 0)],
                    'gas_price': 0,
                    'gas_amount': 0,
                    'message_type': C.MSG_NONE,
                    'message': b''
                })
            proof_tx.height = previous_height + 1
            proof_tx.pos_amount = amount
            proof_txs.append(proof_tx)
    unspents_txs = proof_txs
    return all_num, len(proof_txs)


class FailedGenerateWarning(Exception):
    pass  # skip this exception


def close_generate():
    for t in generating_threads:
        t.close()
    if 0 < len(generating_threads):
        log.info("close generate thread")


__all__ = [
    "generating_threads",
    "output_que",
    "Generate",
    "create_mining_block",
    "confirmed_generating_block",
    "update_previous_block",
    "update_unconfirmed_txs",
    "update_unspents_txs",
    "FailedGenerateWarning",
    "close_generate",
]
