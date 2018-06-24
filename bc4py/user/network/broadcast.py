from bc4py.config import C, V, P, BlockChainError
from bc4py.chain.block import Block
from bc4py.chain.tx import TX
from bc4py.chain.checking import new_insert_block, check_tx, check_tx_time
from bc4py.database.builder import builder, tx_builder
from bc4py.user.network.update import update_mining_staking_all_info
from bc4py.user.network.directcmd import DirectCmd
import logging
from threading import Thread
from binascii import hexlify
import random


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
        tx = tx_builder.get_tx(txhash)
        if tx is None:
            logging.debug("Unknown tx, try to download.")
            r = ask_node(cmd=DirectCmd.TX_BY_HASH, data={'txhash': txhash})
            # 一度で取得できないようなTXは取り込まない
            if isinstance(r, str):
                raise BlockChainError('Failed unknown tx download "{}"'.format(r))
            tx = TX(binary=r['tx'])
            tx.signature = r['sign']
            check_tx(tx, include_block=None)
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


def ask_node(cmd, data=None, f_continue_asking=False):
    count = 10
    pc = V.PC_OBJ
    while 0 < count:
        try:
            user = random.choice(pc.p2p.user)
            dummy, r = pc.send_direct_cmd(cmd=cmd, data=data, user=user)
            if f_continue_asking and isinstance(r, str):
                if count > 0:
                    count -= 1
                    continue
                else:
                    raise BlockChainError('Node return error "{}"'.format(r))
        except TimeoutError:
            continue
        except IndexError:
            raise BlockChainError('No node found.')
        return r
    raise BlockChainError('Too many retry ask_node.')