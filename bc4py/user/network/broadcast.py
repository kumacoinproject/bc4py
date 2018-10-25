from bc4py.config import C, V, P, BlockChainError
from bc4py.chain.block import Block
from bc4py.chain.tx import TX
from bc4py.chain.checking import new_insert_block, check_tx, check_tx_time
from bc4py.database.builder import builder, tx_builder
from bc4py.user.network.update import update_mining_staking_all_info
from bc4py.user.network.directcmd import DirectCmd
from bc4py.user.network.connection import ask_node
import logging
from binascii import hexlify
from collections import deque
import time

failed_deque = deque([], maxlen=10)


def add_failed_mark(error=None):
    failed_deque.append(time.time())
    if min(failed_deque) < time.time() - 7200:
        return
    elif len(failed_deque) >= 10:
        builder.make_failemark(error)
        failed_deque.clear()
        P.F_NOW_BOOTING = True


class BroadcastCmd:
    NEW_BLOCK = 'cmd/new-block'
    NEW_TX = 'cmd/new-tx'

    @staticmethod
    def new_block(data):
        try:
            new_block = fill_newblock_info(data)
        except BlockChainError as e:
            warning = 'Do not accept block "{}"'.format(e)
            logging.warning(warning)
            return False
        except BaseException:
            error = "error on accept new block"
            logging.error(error, exc_info=True)
            add_failed_mark(error)
            return False
        try:
            if new_insert_block(new_block, time_check=True):
                update_mining_staking_all_info()
                logging.info("Accept new block {}".format(new_block))
                return True
            else:
                return False
        except BlockChainError as e:
            error = 'Failed accept new block "{}"'.format(e)
            logging.error(error, exc_info=True)
            return False
        except BaseException:
            error = "error on accept new block"
            logging.error(error, exc_info=True)
            add_failed_mark(error)
            return False

    @staticmethod
    def new_tx(data):
        try:
            new_tx = TX(binary=data['tx'])
            new_tx.signature = data['sign']
            check_tx(tx=new_tx, include_block=None)
            check_tx_time(new_tx)
            tx_builder.put_unconfirmed(new_tx)
            update_mining_staking_all_info()
            logging.info("Accept new tx {}".format(new_tx))
            return True
        except BlockChainError as e:
            error = 'Failed accept new tx "{}"'.format(e)
            logging.error(error)
            add_failed_mark(error)
            return False
        except BaseException:
            error = "Failed accept new tx"
            logging.error(error, exc_info=True)
            add_failed_mark(error)
            return False


def fill_newblock_info(data):
    new_block = Block(binary=data['block'])
    proof = TX(binary=data['proof'])
    new_block.txs.append(proof)
    new_block.flag = data.get('block_flag', proof.type)
    proof.signature = data['sign']
    # Check the block is correct info
    if not new_block.pow_check():
        raise BlockChainError('Proof of work is not satisfied.')
    if builder.get_block(new_block.hash):
        raise BlockChainError('Already inserted block.')
    before_block = builder.get_block(new_block.previous_hash)
    if before_block is None:
        raise BlockChainError('Not found beforeBlock {}.'.format(hexlify(new_block.previous_hash).decode()))
    new_height = before_block.height + 1
    proof.height = new_height
    new_block.height = new_height
    # Append general txs
    for txhash in data['txs'][1:]:
        tx = tx_builder.get_tx(txhash)
        if tx is None:
            logging.debug("Unknown tx, try to download.")
            r = ask_node(cmd=DirectCmd.TX_BY_HASH, data={'txhash': txhash}, f_continue_asking=True)
            if isinstance(r, str):
                raise BlockChainError('Failed unknown tx download "{}"'.format(r))
            tx = TX(binary=r['tx'])
            tx.signature = r['sign']
            check_tx(tx, include_block=None)
            tx_builder.put_unconfirmed(tx)
            logging.debug("Success unknown tx download {}".format(tx))
        tx.height = new_height
        new_block.txs.append(tx)
    return new_block


def broadcast_check(data):
    if P.F_NOW_BOOTING:
        return False
    elif BroadcastCmd.NEW_BLOCK == data['cmd']:
        return BroadcastCmd.new_block(data=data['data'])
    elif BroadcastCmd.NEW_TX == data['cmd']:
        return BroadcastCmd.new_tx(data=data['data'])
    else:
        return False
