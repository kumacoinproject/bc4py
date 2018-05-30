from bc4py.config import C, P, BlockChainError
from bc4py.database.chain.write import update_tx_height, remove_tx_usedindex, recode_finish_contract
from bc4py.database.chain.read import fill_tx_objects
from bc4py.database.chain.flag import is_unconfirmed_tx
from bc4py.user.utxo import rollback_proof_utxo_user
from binascii import hexlify


def rollback_block(folk_chain, chain_cur, account_cur):
    # 一度記録したBlockのAccount情報をRollbackする
    for block in folk_chain:
        fill_tx_objects(block=block, cur=chain_cur)

        for tx in reversed(block.txs):
            # 通常送金TXは触らず
            # ProofTXはAccount操作を戻し、POSはUsedを戻す
            if tx.type == C.TX_POW_REWARD:
                rollback_proof_utxo_user(tx=tx, cur=account_cur)
            elif tx.type == C.TX_POS_REWARD:
                rollback_proof_utxo_user(tx=tx, cur=account_cur)
                txhash, txindex = tx.inputs[0]
                remove_tx_usedindex(txhash=txhash, usedindex=txindex, cur=chain_cur)
            elif tx.type == C.TX_FINISH_CONTRACT:
                for txhash, txindex in tx.inputs:
                    remove_tx_usedindex(txhash=txhash, usedindex=txindex, cur=chain_cur)
                update_tx_height(txhash=tx.hash, height=None, cur=chain_cur)
                recode_finish_contract(start_hash=tx.hash, finish_hash=None, cur=chain_cur)
            else:
                # 通常送金TXならHeightをNoneにするだけ
                if not is_unconfirmed_tx(txhash=tx.hash, cur=chain_cur):
                    update_tx_height(txhash=tx.hash, height=None, cur=chain_cur)
                P.UNCONFIRMED_TX.add(tx.hash)
