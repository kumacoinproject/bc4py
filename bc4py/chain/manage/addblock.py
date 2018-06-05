from bc4py.config import C, P
from bc4py.database.chain.write import recode_block, update_tx_height, add_tx_usedindex
from bc4py.database.chain.read import fill_tx_objects
from bc4py.database.chain.flag import is_include_txhash
from bc4py.user.utxo import add_utxo_user, add_rollback_utxo_user
from .addtx import add_tx_as_new
import logging
from binascii import hexlify


def add_block(new_block, chain_cur, account_cur):
    # 新規のBlockを記録する
    recode_block(block=new_block, cur=chain_cur)

    for tx in new_block.txs:
        if not is_include_txhash(txhash=tx.hash, cur=chain_cur):
            add_tx_as_new(new_tx=tx, chain_cur=chain_cur, account_cur=account_cur)
            f_raise = False if P.F_SYNC_DIRECT_IMPORT else True
            add_utxo_user(tx=tx, chain_cur=chain_cur, account_cur=account_cur, f_raise=f_raise)
        update_tx_height(txhash=tx.hash, height=new_block.height, cur=chain_cur)

        # ProofTXでないなら必ず除くが、Folk時に既にConfirmedになってる可能性に注意
        if tx.hash in P.UNCONFIRMED_TX:
            P.UNCONFIRMED_TX.remove(tx.hash)


def add_rollback_block(main_chain, chain_cur, account_cur):
    # 再度記録する
    for block in reversed(main_chain):
        logging.debug("add_rollback_block block {}".format(hexlify(block.hash).decode()))
        fill_tx_objects(block=block, cur=chain_cur)

        for tx in block.txs:
            if tx.type == C.TX_POW_REWARD:
                add_rollback_utxo_user(tx=tx, chain_cur=chain_cur, account_cur=account_cur)
            elif tx.type == C.TX_POS_REWARD:
                add_rollback_utxo_user(tx=tx, chain_cur=chain_cur, account_cur=account_cur)
                txhash, txindex = tx.inputs[0]
                add_tx_usedindex(txhash=txhash, usedindex=txindex, cur=chain_cur, f_raise=False)
            elif tx.type == C.TX_FINISH_CONTRACT:
                for txhash, txindex in tx.inputs:
                    add_tx_usedindex(txhash=txhash, usedindex=txindex, cur=chain_cur, f_raise=False)
            else:
                if tx.hash in P.UNCONFIRMED_TX:
                    P.UNCONFIRMED_TX.remove(tx.hash)
                update_tx_height(txhash=tx.hash, height=block.height, cur=chain_cur)
