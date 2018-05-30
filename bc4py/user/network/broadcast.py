from bc4py.config import C, V, P, BlockChainError
from bc4py.chain.block import Block
from bc4py.chain.tx import TX
from bc4py.chain.manage import check_block, check_block_time, check_tx, add_tx_as_new, insert2chain_with_lock
from bc4py.database.create import closing, create_db
from bc4py.database.chain.read import read_tx_object, read_block_object, read_tx_output
from bc4py.user.utxo import add_utxo_user
from .update import update_mining_staking_all_info
import logging
from threading import Thread


class BroadcastCmd:
    NEW_BLOCK = 'cmd/new-block'
    NEW_TX = 'cmd/new-tx'

    @staticmethod
    def new_block(data):
        if P.F_NOW_BOOTING:
            return False
        with closing(create_db(V.DB_BLOCKCHAIN_PATH)) as chain_db:
            chain_cur = chain_db.cursor()
            try:
                new_block = fill_newblock_info(data=data, cur=chain_cur)
            except BlockChainError as e:
                logging.error('Failed accept new block1 "{}"'.format(e))
                P.F_NOW_BOOTING = True
                return False
            try:
                check_block_time(block=new_block)
                check_block(block=new_block, cur=chain_cur)
            except BlockChainError as e:
                logging.error('Failed accept new block2 "{}"'.format(e))
                return False
        Thread(target=recode_newblock, name='NewBlock', args=(new_block,), daemon=True).start()
        return True

    @staticmethod
    def new_tx(data):
        with closing(create_db(V.DB_BLOCKCHAIN_PATH)) as chain_db:
            chain_cur = chain_db.cursor()
            try:
                new_tx = TX(binary=data['tx'])
                new_tx.signature = data['sign']
                check_tx(tx=new_tx, include_block=None, cur=chain_cur)
            except BlockChainError as e:
                logging.error('Failed accept new block "{}"'.format(e))
                return False
        Thread(target=recode_newtx, name='NewTX', args=(new_tx,), daemon=True).start()
        return True


def fill_newblock_info(data, cur):
    new_block = Block(binary=data['block'])
    before_block = read_block_object(blockhash=new_block.previous_hash, cur=cur, f_fill_tx=False)
    new_height = before_block.height + 1
    # ProofTX
    proof = TX(binary=data['proof'])
    proof.signature = data['sign']
    proof.height = new_height
    if proof.type == C.TX_POS_REWARD:
        txhash, txindex = proof.inputs[0]
        address, coin_id, amount = read_tx_output(txhash=txhash, txindex=txindex, cur=cur)
        proof.pos_amount = amount
    # FinishTX
    finish_tx = dict()
    for tx_bin in data['finish_bin']:
        tx = TX(binary=tx_bin)
        tx.height = new_height
        if tx.type == C.TX_FINISH_CONTRACT:
            finish_tx[tx.hash] = tx
        else:
            raise BlockChainError('Non finishTX include finish_bin. {}'.format(tx))
    # Mined Block
    new_block.height = new_height
    new_block.flag = C.BLOCK_POS if proof.type == C.TX_POS_REWARD else C.BLOCK_POW
    new_block.txs.append(proof)
    for txhash in data['txs'][1:]:
        if txhash in finish_tx:
            tx = finish_tx[txhash]
        else:
            tx = read_tx_object(txhash=txhash, cur=cur)
        tx.height = new_height
        new_block.txs.append(tx)
    return new_block


def recode_newblock(new_block):
    if insert2chain_with_lock(new_block=new_block):
        update_mining_staking_all_info()


def recode_newtx(new_tx):
    with closing(create_db(V.DB_BLOCKCHAIN_PATH)) as chain_db:
        with closing(create_db(V.DB_ACCOUNT_PATH)) as account_db:
            chain_cur = chain_db.cursor()
            account_cur = account_db.cursor()
            try:
                add_tx_as_new(new_tx=new_tx, chain_cur=chain_cur, account_cur=account_cur)
                add_utxo_user(tx=new_tx, chain_cur=chain_cur, account_cur=account_cur)
                # P.UNCONFIRMED_TX同じスレッドでマニュアル的に加える必要がある
                P.UNCONFIRMED_TX.add(new_tx.hash)
                chain_db.commit()
                account_db.commit()
                logging.info("Accept new tx {}".format(new_tx))
            except BlockChainError as e:
                chain_db.rollback()
                account_db.rollback()
                logging.info("Reject new tx {}".format(new_tx))
                return
    update_mining_staking_all_info(u_block=False, u_unspent=False, u_unconfirmed=True)


def broadcast_check(data):
    if P.F_NOW_BOOTING:
        return False
    elif BroadcastCmd.NEW_BLOCK == data['cmd']:
        return BroadcastCmd.new_block(data=data['data'])
    elif BroadcastCmd.NEW_TX == data['cmd']:
        return BroadcastCmd.new_tx(data=data['data'])
    else:
        return False


def delete_block(block):
    if block is None:
        return
    for tx in block.txs:
        del tx
    block.txs.clear()
    del block
