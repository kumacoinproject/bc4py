from bc4py.config import C, V, P, BlockChainError
from bc4py.chain.block import Block
from bc4py.chain.tx import TX
from bc4py.chain.checking import new_insert_block, check_tx, check_tx_time
from bc4py.database.builder import builder, tx_builder
from bc4py.user.network.update import update_mining_staking_all_info
import logging
from threading import Thread
from binascii import hexlify


class BroadcastCmd:
    NEW_BLOCK = 'cmd/new-block'
    NEW_TX = 'cmd/new-tx'

    @staticmethod
    def new_block(data):
        if P.F_NOW_BOOTING:
            return False
        try:
            new_block = fill_newblock_info(data)
            if new_insert_block(new_block, time_check=True):
                update_mining_staking_all_info(f_force=True)
                logging.info("Accept new block {}".format(new_block))
                return True
            else:
                return False
        except BlockChainError as e:
            logging.error('Failed accept new block "{}"'.format(e))
            return False
        except BaseException:
            logging.error("Failed accept new block", exc_info=True)
            return False

    @staticmethod
    def new_tx(data):
        if P.F_NOW_BOOTING:
            return False
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
            logging.error('Failed accept new block "{}"'.format(e))
            return False
        except BaseException:
            logging.error("Failed accept new block", exc_info=True)
            return False


def fill_newblock_info(data):
    new_block = Block(binary=data['block'])
    if builder.get_block(new_block.hash):
        raise BlockChainError('Already inserted block.')
    before_block = builder.get_block(new_block.previous_hash)
    if before_block is None:
        raise BlockChainError('Not found beforeBlock {}.'.format(hexlify(new_block.previous_hash).decode()))
    new_height = before_block.height + 1
    # ProofTX
    proof = TX(binary=data['proof'])
    proof.signature = data['sign']
    proof.height = new_height
    if proof.type == C.TX_POS_REWARD:
        txhash, txindex = proof.inputs[0]
        output_tx = tx_builder.get_tx(txhash)
        address, coin_id, amount = output_tx.outputs[txindex]
        proof.pos_amount = amount
    # Mined Block
    new_block.height = new_height
    new_block.flag = proof.type
    new_block.txs.append(proof)
    for txhash in data['txs'][1:]:
        try:
            tx = tx_builder.get_tx(txhash)
            tx.height = new_height
            new_block.txs.append(tx)
        except KeyError:
            raise BlockChainError('Not found tx {}.'.format(hexlify(txhash).decode()))
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
