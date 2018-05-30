from bc4py.config import C, V, P, BlockChainError
from bc4py.database.chain.write import delete_tx,remove_tx_usedindex
from bc4py.database.chain.read import read_tx_object, max_block_height
from bc4py.user.utxo import remove_utxo_user
import time
from binascii import hexlify
import logging


def remove_unconfirmed_tx(tx, chain_cur, account_cur):
    # Outputsを辿って削除する
    if tx.height is not None:
        raise BlockChainError('It\'s not unconfirmed tx. {}'.format(hexlify(tx.hash).decode()))
    elif tx.type in (C.TX_POS_REWARD, C.TX_POW_REWARD):
        raise BlockChainError('It\'s proof tx. remove by cleaning. {}'.format(hexlify(tx.hash).decode()))
    logging.debug("try to delete {}".format(hexlify(tx.hash).decode()))
    # Inputs/Outputsに関連するUnconfirmedTXの削除
    removed = list()
    for unconfirmed_hash in P.UNCONFIRMED_TX.copy():
        if unconfirmed_hash not in P.UNCONFIRMED_TX:
            continue
        unconfirmed_tx = read_tx_object(txhash=unconfirmed_hash, cur=chain_cur)
        if unconfirmed_tx.height is not None:
            raise BlockChainError('The tx is unconfirmed, but include height{}'.format(unconfirmed_tx.height))
        for txhash, txindex in unconfirmed_tx.inputs:
            if txhash == tx.hash:
                removed += remove_unconfirmed_tx(tx=unconfirmed_tx, chain_cur=chain_cur, account_cur=account_cur)
                break

    # 削除実行
    # UnconfirmedTXキャッシュから削除
    if tx.hash in P.UNCONFIRMED_TX:
        P.UNCONFIRMED_TX.remove(tx.hash)
        delete_tx(txhash=tx.hash, cur=chain_cur)
        for txhash, txindex in tx.inputs:
            remove_tx_usedindex(txhash=txhash, usedindex=txindex, cur=chain_cur)
        remove_utxo_user(tx=tx, cur=account_cur)
        removed += [tx.hash]
        logging.debug("Removed unconfirmed ".format(tx))
    return removed


def update_unconfirmed_tx(chain_cur, account_cur):
    # 時間切れのUnconfirmedTXが無いか確認
    removed = list()
    for unconfirmed_hash in P.UNCONFIRMED_TX.copy():
        if unconfirmed_hash not in P.UNCONFIRMED_TX:
            continue
        unconfirmed_tx = read_tx_object(txhash=unconfirmed_hash, cur=chain_cur)
        now = int(time.time()) - V.BLOCK_GENESIS_TIME
        if len(removed) > 0:
            # 一度に大量に削除せず
            logging.debug("Update unconfirmed tx {}".format(len(removed)))
            break
        elif not (unconfirmed_tx.time < now < unconfirmed_tx.deadline + 3600):
            # 時間切れによる完全削除
            removed += remove_unconfirmed_tx(tx=unconfirmed_tx, chain_cur=chain_cur, account_cur=account_cur)
        elif unconfirmed_tx.height is not None:
            # 取り込まれたので一部削除
            P.UNCONFIRMED_TX.remove(unconfirmed_hash)
    return removed


def check_unconfirmed_tx(new_tx, chain_cur, account_cur):
    # Blockに取り込まれたNewTXで消すべきUnconfirmedTXは無いかチェック
    if new_tx.height is None:
        raise BlockChainError('NewTX is confirmed tx. {}'.format(hexlify(new_tx.hash).decode()))
    removed = list()
    for txhash, txindex in new_tx.inputs:
        if txhash in P.UNCONFIRMED_TX.copy():
            unconfirmed_tx = read_tx_object(txhash=txhash, cur=chain_cur)
            removed += remove_unconfirmed_tx(tx=unconfirmed_tx, chain_cur=chain_cur, account_cur=account_cur)
    return removed


def f_inputs_all_confirmed(tx, height, cur):
    for txhash, txindex in tx.inputs:
        input_tx = read_tx_object(txhash=txhash, cur=cur)
        if input_tx.height is None:
            return False
        elif input_tx.type in (C.TX_POW_REWARD, C.TX_POS_REWARD):
            # ProofTXで未成熟
            if input_tx.height > height - C.MATURE_HEIGHT:
                raise BlockChainError('Not allowed proof tx before mature. [{}>{}-{}]'
                                      .format(input_tx.height, height, C.MATURE_HEIGHT))
    return True


def get_unconfirmed_tx(cur):
    # Blockにすぐ取り込んでもOKなTXのみ取得
    tmp = set()
    max_height = max_block_height(cur=cur)
    now = int(time.time()) - V.BLOCK_GENESIS_TIME
    for _txhash in P.UNCONFIRMED_TX.copy():
        tx = read_tx_object(txhash=_txhash, cur=cur)
        if not (tx.time < now < tx.deadline):
            pass
        elif f_inputs_all_confirmed(tx=tx, height=max_height, cur=cur):
            tmp.add(tx)
    unconfirmed_tx = sorted(tmp, key=lambda x: x.gas_price, reverse=True)
    return unconfirmed_tx
