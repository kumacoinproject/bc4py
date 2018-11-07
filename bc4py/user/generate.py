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
from bc4py.user.utils import message2signature
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
staking_limit = 500


def new_key(user=C.ANT_NAME_UNKNOWN):
    with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
        cur = db.cursor()
        ck = create_new_user_keypair(user, cur)
        db.commit()
    return ck


class Generate(Thread):
    def __init__(self, consensus, power_limit=1.0):
        assert consensus in V.BLOCK_CONSENSUS, \
            "{} is not used by blockchain.".format(C.consensus2name[consensus])
        super(Generate, self).__init__(
            name="Gene-{}".format(C.consensus2name[consensus]),
            daemon=True)
        self.consensus = consensus
        self.power_limit = min(1.0, max(0.01, power_limit))
        self.hashrate = (0, 0.0)  # [hash/s, update_time]
        self.event_close = Event()
        generating_threads.append(self)

    def __repr__(self):
        hashrate, _time = self.hashrate
        if time()-_time > 120:
            data = "NotActive ({}minutes before updated)".format(round((time()-_time)/60, 1))
        elif hashrate < 1000 * 10:
            data = "{}hash/s".format(hashrate)
        elif hashrate < 1000 * 1000 * 10:
            data = "{}kh/s".format(round(hashrate / 1000, 2))
        else:
            data = "{}Mh/s".format(round(hashrate / 1000000, 3))
        return "<Generate {} {} limit={}>".format(C.consensus2name[self.consensus], data, self.power_limit)

    def close(self, timeout=120):
        self.event_close.clear()

    def run(self):
        self.event_close.set()
        while self.event_close.is_set():
            logging.info("Start {} generating!".format(C.consensus2name[self.consensus]))
            try:
                if self.consensus == C.BLOCK_POS:
                    self.proof_of_stake()
                else:
                    self.proof_of_work()
            except BlockChainError as e:
                logging.warning(e)
            except Exception:
                logging.error("GeneratingError wait60s...", exc_info=True)
                sleep(60)

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
            if previous_block is None or unconfirmed_txs is None:
                sleep(0.1)
                continue
            mining_block = create_mining_block(self.consensus)
            # throw task
            new_span = generate_many_hash(mining_block, how_many)
            spans_deque.append(new_span)
            # check block
            if previous_block is None or unconfirmed_txs is None:
                logging.debug("Not confirmed new block by \"nothing params\"")
            elif previous_block.hash != mining_block.previous_hash:
                logging.debug("Not confirmed new block by \"Don't match previous_hash\"")
            elif not mining_block.pow_check():
                if int(time()) % 90 == 0:
                    logging.debug("Not confirmed new block by \"proof of work unsatisfied\"")
            else:
                # Mined yay!!!
                confirmed_generating_block(mining_block)
            # generate next mining how_many
            try:
                self.hashrate = (how_many * len(spans_deque) // sum(spans_deque), time())
                bias = sum(work_span * i for i, span in enumerate(spans_deque))
                bias /= sum(span * i for i, span in enumerate(spans_deque))
                bias = min(2.0, max(0.5, bias))
                how_many = max(100, int(how_many * bias))
                if int(time()) % 90 == 0:
                    logging.info("Mining... Next target how_many is {} {}"
                                 .format(how_many, "Up" if bias > 1 else "Down"))
            except ZeroDivisionError:
                pass
            sleep(sleep_span)
        logging.info("Close signal")

    def proof_of_stake(self):
        global staking_limit
        limit_deque = deque(maxlen=10)
        self.event_close.set()
        while self.event_close.is_set():
            # check start mining
            if previous_block is None or unconfirmed_txs is None or unspents_txs is None:
                sleep(0.1)
                continue
            if len(unspents_txs) == 0:
                logging.info("No unspents for staking, wait 180s..")
                sleep(180)
                continue
            start = time()
            # create staking block
            bits, target = get_bits_by_hash(
                previous_hash=previous_block.hash, consensus=C.BLOCK_POS)
            reward = GompertzCurve.calc_block_reward(previous_block.height + 1)
            staking_block = Block(block={
                'merkleroot': b'\xff' * 32,
                'time': 0,
                'previous_hash': previous_block.hash,
                'bits': bits,
                'nonce': b'\xff\xff\xff\xff'})
            staking_block.height = previous_block.height + 1
            staking_block.flag = C.BLOCK_POS
            staking_block.bits2target()
            staking_block.txs.append(None)  # Dummy proof tx
            staking_block.txs.extend(unconfirmed_txs)
            calculate_nam = 0
            for proof_tx in unspents_txs.copy():
                address = proof_tx.outputs[0][0]
                proof_tx.outputs[0] = (address, 0, proof_tx.pos_amount + reward)
                proof_tx.update_time()
                calculate_nam += 1
                # next check block
                if previous_block is None or unconfirmed_txs is None or unspents_txs is None:
                    logging.debug("Reset by \"nothing params found\"")
                    sleep(1)
                    break
                elif previous_block.hash != staking_block.previous_hash:
                    logging.debug("Reset by \"Don't match previous_hash\"")
                    sleep(1)
                    break
                elif not proof_tx.pos_check(
                        previous_hash=previous_block.hash,
                        pos_target_hash=staking_block.target_hash):
                    continue
                else:
                    # Staked yay!!
                    proof_tx.height = staking_block.height
                    proof_tx.signature = [message2signature(proof_tx.b, proof_tx.outputs[0][0])]
                    staking_block.txs[0] = proof_tx
                    # Fit block size
                    while staking_block.getsize() > C.SIZE_BLOCK_LIMIT:
                        tx = staking_block.txs.pop()
                        if tx.type == C.TX_FINISH_CONTRACT:
                            staking_block.txs.pop()
                    staking_block.update_time(proof_tx.time)
                    staking_block.update_merkleroot()
                    confirmed_generating_block(staking_block)
                    break
            else:
                # check time
                used = time() - start
                remain = 1.0 - used
                max_limit = max(50, int(calculate_nam / max(0.0001, used)))
                limit_deque.append(int(max_limit * self.power_limit))
                staking_limit = sum(limit_deque) // len(limit_deque)
                if int(time()) % 90 == 0:
                    logging.info("Staking... margin={}% limit={}".format(round(remain*100, 1), staking_limit))
                self.hashrate = (calculate_nam, time())
                sleep(max(0.0, remain))
        logging.info("Close signal")


def create_mining_block(consensus):
    global mining_address
    # create proof_tx
    mining_address = mining_address or V.MINING_ADDRESS or new_key()
    reward = GompertzCurve.calc_block_reward(previous_block.height + 1)
    fees = sum(tx.gas_amount * tx.gas_price for tx in unconfirmed_txs)
    proof_tx = TX(tx={
        'type': C.TX_POW_REWARD,
        'inputs': list(),
        'outputs': [(mining_address, 0, reward + fees)],
        'gas_price': 0,
        'gas_amount': 0,
        'message_type': C.MSG_PLAIN if V.MINING_MESSAGE else C.MSG_NONE,
        'message': V.MINING_MESSAGE if V.MINING_MESSAGE else b''})
    proof_tx.update_time()
    # create mining block
    bits, target = get_bits_by_hash(
        previous_hash=previous_block.hash, consensus=consensus)
    mining_block = Block(block={
        'merkleroot': b'\xff' * 32,
        'time': 0,
        'previous_hash': previous_block.hash,
        'bits': bits,
        'nonce': b'\xff\xff\xff\xff'})
    mining_block.height = previous_block.height + 1
    mining_block.flag = consensus
    mining_block.bits2target()
    mining_block.txs.append(proof_tx)
    mining_block.txs.extend(unconfirmed_txs)
    mining_block.update_merkleroot()
    mining_block.update_time(proof_tx.time)
    return mining_block


def confirmed_generating_block(new_block):
    logging.info("Generate block yey!! {}".format(new_block))
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


def update_unspents_txs():
    global unspents_txs
    c = 50
    while previous_block is None and 0 < c:
        sleep(0.2)
        c -= 1
    previous_height = previous_block.height
    proof_txs = list()
    all_num = 0
    for address, height, txhash, txindex, coin_id, amount in get_unspents_iter():
        if height is None:
            continue
        if coin_id != 0:
            continue
        if not (previous_height + 1 > height + C.MATURE_HEIGHT):
            continue
        if not is_address(address, prefix=V.BLOCK_PREFIX):
            continue
        if amount < 100000000:
            continue
        if staking_limit < all_num:
            logging.debug("Unspents limit reached, skip by {} limits.".format(staking_limit))
            break
        all_num += 1
        proof_tx = TX(tx={
            'type': C.TX_POS_REWARD,
            'inputs': [(txhash, txindex)],
            'outputs': [(address, 0, 0)],
            'gas_price': 0,
            'gas_amount': 0,
            'message_type': C.MSG_NONE,
            'message': b''})
        proof_tx.height = previous_height + 1
        proof_tx.pos_amount = amount
        proof_txs.append(proof_tx)
    unspents_txs = proof_txs
    return all_num, len(proof_txs)


def close_generate():
    for t in generating_threads:
        t.close()


__all__ = [
    "generating_threads",
    "output_que",
    "Generate",
    "create_mining_block",
    "confirmed_generating_block",
    "update_previous_block",
    "update_unconfirmed_txs",
    "update_unspents_txs",
    "close_generate"
]
