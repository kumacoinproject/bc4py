from bc4py import __chain_version__
from bc4py.config import C, V, BlockChainError
from bc4py.chain.block import Block
from bc4py.chain.tx import TX
from bc4py.chain.workhash import generate_many_hash
from bc4py.chain.difficulty import get_bits_by_hash
from bc4py.chain.utils import GompertzCurve
from bc4py.database.create import create_db, closing
from bc4py.database.account import create_new_user_keypair
from bc4py.database.tools import get_unspents_iter
from threading import Thread, Event
from time import time, sleep
import logging
import queue
from binascii import hexlify
from collections import deque
from nem_ed25519.key import is_address


generating_threads = list()
output_que = queue.LifoQueue()
# mining share info
mining_address = None
previous_block = None
unconfirmed_txs = None
unspents_txs = None


def new_key():
    with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
        cur = db.cursor()
        ck = create_new_user_keypair(C.ANT_NAME_UNKNOWN, cur)
        db.commit()
    return ck


class Generate(Thread):
    def __init__(self, consensus, power_limit=1.0):
        super(Generate, self).__init__(
            name="Gene-{}".format(C.consensus2name[consensus]),
            daemon=True)
        self.consensus = consensus
        self.power_limit = min(1.0, max(0.01, power_limit))
        self.hashrate = (0, time())  # [hash/s, update_time]
        self.event_close = Event()
        generating_threads.append(self)

    def __repr__(self):
        hashrate, _time = self.hashrate
        if time()-_time > 120:
            data = "NotActive"
        elif hashrate < 1000 * 10:
            data = "{}hash/s".format(self.hashrate)
        elif hashrate < 1000 * 1000 * 10:
            data = "{}kh/s".format(round(hashrate // 1000, 1))
        else:
            data = "{}Mh/s".format(round(hashrate // 1000000, 3))
        return "<Generate {} {}>".format(C.consensus2name[self.consensus], data)

    def close(self, timeout=120):
        self.event_close.clear()
        return self.event_close.wait(timeout)

    def run(self):
        if self.consensus == C.BLOCK_POS:
            self.proof_of_stake()
        else:
            self.proof_of_work()

    def proof_of_work(self):
        global mining_address
        spans_deque = deque(maxlen=8)
        how_many = 100
        base_span = 10
        work_span = base_span * self.power_limit
        sleep_span = base_span * (1.0 - self.power_limit)
        self.event_close.set()
        while self.event_close.is_set():
            # check start mining
            if not (previous_block and unconfirmed_txs):
                sleep(0.1)
                continue
            now = int(time() - V.BLOCK_GENESIS_TIME)
            # create proof_tx
            mining_address = mining_address or V.MINING_ADDRESS or new_key()
            reward = GompertzCurve.calc_block_reward(previous_block.height + 1)
            fees = sum(tx.gas_amount * tx.gas_price for tx in unconfirmed_txs.txs)
            proof_tx = TX(tx={
                'version': __chain_version__,
                'type': C.TX_POW_REWARD,
                'time': now,
                'deadline': now + 10800,
                'inputs': list(),
                'outputs': [(mining_address, 0, reward + fees)],
                'gas_price': 0,
                'gas_amount': 0,
                'message_type': C.MSG_PLAIN if V.MINING_MESSAGE else C.MSG_NONE,
                'message': V.MINING_MESSAGE if V.MINING_MESSAGE else b''})
            # create mining block
            bits, target = get_bits_by_hash(
                previous_hash=previous_block.hash, consensus=self.consensus)
            mining_block = Block()
            mining_block.height = previous_block.height + 1
            mining_block.previous_hash = previous_block.hash
            mining_block.bits = bits
            mining_block.nonce = b'\xff' * 4
            mining_block.txs.append(proof_tx)
            mining_block.txs.extend(unconfirmed_txs)
            mining_block.update_merkleroot()
            mining_block.update_time(proof_tx.time)
            # throw task
            new_span = generate_many_hash(mining_block, how_many)
            spans_deque.append(new_span)
            # check block
            if not (previous_block and unconfirmed_txs):
                logging.debug("Not confirmed new block by \"nothing params\"")
            elif previous_block.hash != mining_block.previous_hash:
                logging.debug("Not confirmed new block by \"no match previous hash\"")
            elif not mining_block.pow_check():
                logging.debug("Not confirmed new block by \"proof of work\"")
            else:
                # Mined yay!!!
                confirmed_generating_block(mining_block)
            # generate next mining how_many
            self.hashrate = (how_many * len(spans_deque) // sum(spans_deque), time())
            bias = (len(spans_deque) * work_span) / sum(spans_deque)
            bias = min(2.0, max(0.5, bias))
            how_many = max(100, int(how_many * bias))
            sleep(sleep_span)
        self.event_close.set()
        logging.info("Close signal")

    def proof_of_stake(self):
        self.event_close.set()
        while self.event_close.is_set():
            # check start mining
            if not (previous_block and unconfirmed_txs and unspents_txs):
                sleep(0.1)
                continue
            assert previous_block.next_hash is not None, "previous_block.next_hash needed!"
            start = time()
            now = int(start - V.BLOCK_GENESIS_TIME)
            # create staking block
            bits, target = get_bits_by_hash(
                previous_hash=previous_block.next_hash, consensus=C.BLOCK_POS)
            staking_block = Block()
            staking_block.previous_hash = previous_block.next_hash
            staking_block.bits = bits
            staking_block.nonce = b'\xff' * 4
            staking_block.height = previous_block.height + 2
            staking_block.flag = C.BLOCK_POS
            staking_block.bits2target()
            staking_block.txs.append(None)  # Dummy proof tx
            staking_block.txs.extend(unconfirmed_txs)
            for proof_tx in unspents_txs.copy():
                proof_tx.update_time()
                if not proof_tx.pos_check(
                        previous_hash=previous_block.next_hash,
                        pos_target_hash=staking_block.target_hash):
                    continue
                # next check block
                if not (previous_block and unconfirmed_txs and unspents_txs):
                    logging.debug("Not confirmed new block by \"nothing params\"")
                elif previous_block.next_hash != staking_block.previous_hash:
                    logging.debug("Not confirmed new block by \"no match previous hash\"")
                else:
                    # Staked yay!!
                    staking_block.txs[0] = proof_tx
                    staking_block.update_time(proof_tx.time)
                    staking_block.update_merkleroot()
                    confirmed_generating_block(staking_block)
                    break
            # check time
            remain = 1.0 - (time() - start)
            sleep(max(0.0, remain))
        self.event_close.set()
        logging.info("Close signal")


def confirmed_generating_block(new_block):
    logging.info("Generate yey!! {}".format(new_block))
    global mining_address, previous_block, unconfirmed_txs, unspents_txs
    mining_address = None
    previous_block = None
    unconfirmed_txs = None
    unspents_txs = None
    output_que.put(new_block)


def update_previous_block(new_previous_block):
    global previous_block
    previous_block = new_previous_block


def update_unconfirmed_txs(new_unconfirmed_txs):
    global unconfirmed_txs
    unconfirmed_txs = new_unconfirmed_txs


def update_unspents_txs(limit=2000):
    global unspents_txs
    c = 50
    while previous_block is None and 0 < c:
        sleep(0.2)
        c -= 1
    proof_txs = list()
    reward = GompertzCurve.calc_block_reward(previous_block.height + 1)
    all_num = 0
    for address, height, txhash, txindex, coin_id, amount in get_unspents_iter():
        all_num += 1
        if height is None:
            continue
        if coin_id != 0:
            continue
        if not (previous_block.height + 1 > height + C.MATURE_HEIGHT):
            continue
        if not is_address(address, prefix=V.BLOCK_PREFIX):
            continue
        if amount < 100000000:
            continue
        if limit < all_num:
            continue
        proof_tx = TX(tx={
            'version': __chain_version__,
            'type': C.TX_POS_REWARD,
            'time': 0, 'deadline': 0,
            'inputs': [(txhash, txindex)],
            'outputs': [(address, 0, amount + reward)],
            'gas_price': 0,
            'gas_amount': 0,
            'message_type': C.MSG_NONE,
            'message': b''})
        proof_tx.height = previous_block.height + 1
        proof_tx.pos_amount = amount
        proof_txs.append(proof_tx)
    unspents_txs = proof_txs
    return all_num, len(proof_txs)
