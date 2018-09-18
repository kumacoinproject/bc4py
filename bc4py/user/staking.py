from bc4py import __chain_version__
from bc4py.config import C, V, BlockChainError
from bc4py.utils import set_blockchain_params, set_database_path
from bc4py.chain.block import Block
from bc4py.chain.tx import TX
from bc4py.chain.difficulty import get_bits_by_hash
from bc4py.chain.utils import GompertzCurve
from bc4py.database.tools import get_unspents_iter
from bc4py.user import float2unit
from bc4py.user.utils import message2signature
from binascii import hexlify
from multiprocessing import Process, Queue
import time
import logging
from threading import Thread
import queue
from nem_ed25519.key import is_address


NEW_BLOCK = 0
NEW_UNCONFIRMED = 1
NEW_PROOF_TXS = 2


def staking_process(parent_que, child_que, params):
    def send(*args):
        parent_que.put(args)
    set_database_path(sub_dir=params.get("sub_dir"))
    set_blockchain_params(genesis_block=params.get('genesis_block'))
    staking_block = None
    unconfirmed = list()
    proof_txs = list()
    staking_time = 0
    while True:
        if not child_que.empty():
            cmd, obj = child_que.get()
            if cmd == NEW_BLOCK:
                staking_block = obj
            elif cmd == NEW_UNCONFIRMED:
                unconfirmed = obj
            elif cmd == NEW_PROOF_TXS:
                proof_txs = obj

        elif staking_block:
            if staking_block.time + V.BLOCK_GENESIS_TIME == staking_time:
                time.sleep(0.2)
                continue
            staking_time = int(time.time())
            start = time.time()
            for proof_tx in proof_txs:
                proof_tx.update_time()
                if not proof_tx.pos_check(
                        previous_hash=staking_block.previous_hash,
                        pos_target_hash=staking_block.target_hash):
                    continue
                proof_tx.signature = [message2signature(proof_tx.b, proof_tx.outputs[0][0])]
                staking_block.update_time(blocktime=proof_tx.time)
                staking_block.txs.clear()
                staking_block.txs.append(proof_tx)
                staking_block.txs.extend(unconfirmed)
                # unconfirmedのHeightを更新
                for tx in staking_block.txs:
                    tx.height = staking_block.height
                # Blockに入りきらないTXを除く
                while staking_block.getsize() > C.SIZE_BLOCK_LIMIT:
                    tx = staking_block.txs.pop()
                    if tx.type == C.TX_FINISH_CONTRACT:
                        staking_block.txs.pop()
                staking_block.update_merkleroot()
                for tx in staking_block.txs:
                    tx.height = staking_block.height
                info = "Staked yay!! Diff={} ({}hash/s)"\
                    .format(float2unit(staking_block.difficulty), len(proof_txs))
                send(True, staking_block, info)
                # Clear
                staking_block = None
                unconfirmed.clear()
                proof_txs.clear()
                break

            else:
                # 採掘したものの掘り当てられなかった場合
                remain = max(0.0,  1+start-time.time())
                time.sleep(remain)
                if staking_time % 300 == 0:
                    hashrate = len(proof_txs)
                    margin = round(remain * 100, 1)
                    info = "Generating(POS) now ..Diff={}, ({}hash/s, margin{}%)" \
                        .format(float2unit(staking_block.difficulty), hashrate, margin)
                    send(False, (hashrate, margin), info)
                elif staking_time % 10 == 0:
                    hashrate = len(proof_txs)
                    margin = round(remain * 100, 1)
                    send(False, (hashrate, margin), None)
        else:
            time.sleep(1)


class ProcessObject:
    def __init__(self, index, process, parent_que, child_que):
        self.index = index
        self.process = process
        self.parent_que = parent_que
        self.child_que = child_que
        self.hashrate = 0
        self.margin = 100

    def __repr__(self):
        return "<Staking {} {}h/s margin{}%>".format(self.index, self.hashrate, self.margin)

    def close(self):
        try:
            self.parent_que.close()
            self.child_que.close()
        except OSError as e:
            logging.error("Failed close Queue: {}".format(e))
        try:
            self.process.terminate()
        except OSError as e:
            logging.error("Failed close Process: {}".format(e))

    def check_mined_block(self):
        try:
            if not self.parent_que.empty():
                status, obj, info = self.parent_que.get()
                if status:
                    logging.info(info)
                    return status, obj
                elif info:
                    self.hashrate, self.margin = obj
                    logging.debug(info)
                    return status, None
                else:
                    self.hashrate, self.margin = obj
                    return status, None
            else:
                return None, None
        except OSError as e:
            logging.error("Error on pipe: {}".format(e))

    def update_new_block(self, new_block):
        self._send(NEW_BLOCK, new_block)

    def update_unconfirmed(self, unconfirmed):
        self._send(NEW_UNCONFIRMED, unconfirmed)

    def update_proof_txs(self, proof_txs):
        self._send(NEW_PROOF_TXS, proof_txs)

    def _send(self, *args):
        self.child_que.put(args)


class Staking:
    f_stop = False
    f_staking = False

    def __init__(self, genesis_block):
        assert V.BLOCK_CONSENSUS in (C.BLOCK_POS, C.HYBRID), 'Not pos mining chain.'
        self.thread_pool = list()
        self.que = queue.LifoQueue()
        self.previous_hash = None
        self.block_reward = None
        self.block_height = None
        self.genesis_block = genesis_block
        self.cores = 0

    def close(self):
        self.f_stop = True
        for po in self.thread_pool:
            po.close()
        self.thread_pool.clear()

    def getinfo(self):
        return [str(po) for po in self.thread_pool]

    def stop(self):
        self.f_stop = True
        for po in self.thread_pool:
            po.close()
        self.thread_pool.clear()
        self.f_staking = False

    def start(self, threads=1):
        if self.f_staking:
            raise BlockChainError('Already POS is running.')
        self.f_staking = True
        self.f_stop = False
        self.cores = threads
        for i in range(1, threads+1):
            try:
                parent_que, child_que = Queue(), Queue()
                params = dict(genesis_block=self.genesis_block, sub_dir=V.SUB_DIR)
                process = Process(
                    target=staking_process,
                    name="C-Staking {}".format(i),
                    args=(parent_que, child_que, params))
                process.daemon = True
                process.start()
                po = ProcessObject(index=i, process=process, parent_que=parent_que, child_que=child_que)
                self.thread_pool.append(po)
                logging.info("Staking process create number={}".format(i))
            except OSError as e:
                logging.error("Failed start mining process: {}".format(e))
                time.sleep(60)
        loop_thread = Thread(target=self.inner_check, name="P-Staking")
        loop_thread.start()

    def share_que(self, mining):
        self.que = mining.que

    def inner_check(self):
        while not self.f_stop:
            for po in self.thread_pool:
                status, new_block = po.check_mined_block()
                if status:
                    break
            else:
                time.sleep(0.5)
                continue
            logging.info("Staked block yay!! {}".format(new_block))
            # 処理
            if new_block is None:
                continue
            elif self.previous_hash != new_block.previous_hash:
                continue
            self.previous_hash = None
            self.que.put(new_block)

    def update_block(self, base_block):
        staking_block = Block(block={
            'merkleroot': b'\xff' * 32,
            'time': 0,
            'previous_hash': base_block.hash,
            'bits': get_bits_by_hash(previous_hash=base_block.hash, consensus=C.BLOCK_POS)[0],
            'nonce': b'\xff' * 4})
        staking_block.height = base_block.height + 1
        staking_block.flag = C.BLOCK_POS
        staking_block.bits2target()
        staking_block.target2diff()
        logging.debug("Update pos block Diff={} {}"
                      .format(float2unit(staking_block.difficulty), hexlify(staking_block.hash).decode()))
        while self.cores != len(self.thread_pool):
            time.sleep(1)
        for po in self.thread_pool:
            po.update_new_block(staking_block)
        # New block info
        self.previous_hash = base_block.hash
        self.block_reward = GompertzCurve.calc_block_reward(staking_block.height)
        self.block_height = staking_block.height

    def update_unconfirmed(self, unconfirmed):
        while self.cores != len(self.thread_pool):
            time.sleep(1)
        for po in self.thread_pool:
            po.update_unconfirmed(unconfirmed)

    def update_unspent(self):
        c = 50
        while 0 == len(self.thread_pool) and 0 < c:
            time.sleep(0.2)
            c -= 1
        while self.previous_hash is None and 0 < c:
            time.sleep(0.2)
            c -= 1
        assert 0 < len(self.thread_pool), "No staking thread found."
        assert self.previous_hash, "Setup block before."
        proof_txs = list()
        all_num = 0
        for address, height, txhash, txindex, coin_id, amount in get_unspents_iter():
            all_num += 1
            if height is None:
                continue
            if coin_id != 0:
                continue
            if not (self.block_height > height + C.MATURE_HEIGHT):
                continue
            if not is_address(address, prefix=V.BLOCK_PREFIX):
                continue
            if amount < 100000000:
                continue
            proof_tx = TX(tx={
                'version': __chain_version__,
                'type': C.TX_POS_REWARD,
                'time': 0, 'deadline': 0,
                'inputs': [(txhash, txindex)],
                'outputs': [(address, 0, amount + self.block_reward)],
                'gas_price': 0,
                'gas_amount': 0,
                'message_type': C.MSG_NONE,
                'message': b''})
            proof_tx.height = None
            proof_tx.pos_amount = amount
            proof_txs.append(proof_tx)
        n = len(proof_txs) // len(self.thread_pool) + 1
        for i, po in enumerate(self.thread_pool):
            po.update_proof_txs(proof_txs[i*n:i*n+n])
        return all_num, len(proof_txs)
