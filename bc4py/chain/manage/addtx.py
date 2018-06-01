from bc4py.config import C, V, P, BlockChainError
from bc4py.chain.mintcoin import MintCoinObject
from bc4py.database.chain.write import recode_tx, add_tx_usedindex, add_mint_coin,\
    recode_contract_code, recode_start_contract, recode_finish_contract
import logging
from binascii import hexlify
import bjson


def add_tx_as_new(new_tx, chain_cur, account_cur):
    # add_tx_as_newは一回のみしか実行してはいけない
    recode_tx(tx=new_tx, cur=chain_cur)

    # 各タイプ毎の追加の操作
    if new_tx.type == C.TX_GENESIS:
        pass
    elif new_tx.type == C.TX_TRANSFER:
        pass
    elif new_tx.type == C.TX_POS_REWARD:
        pass
    elif new_tx.type == C.TX_POW_REWARD:
        pass
    elif new_tx.type == C.TX_MINT_COIN:
        # 新規コインを鋳造
        mint_object = MintCoinObject(txhash=new_tx.hash, binary=new_tx.message)
        add_mint_coin(txhash=new_tx.hash, mint_object=mint_object, cur=chain_cur)
    elif new_tx.type == C.TX_CREATE_CONTRACT:
        # コントラクト生成
        c_address, contract = bjson.loads(new_tx.message)
        recode_contract_code(address=c_address, txhash=new_tx.hash, cur=chain_cur)
    elif new_tx.type == C.TX_START_CONTRACT:
        # 開始コントラクト
        c_address, c_data = bjson.loads(new_tx.message)
        recode_start_contract(start_hash=new_tx.hash, address=c_address, cur=chain_cur)
    elif new_tx.type == C.TX_FINISH_CONTRACT:
        # 終了コントラクト
        status, start_hash, c_cs = bjson.loads(new_tx.message)
        recode_finish_contract(start_hash=start_hash, finish_hash=new_tx.hash, cur=chain_cur)
    else:
        # その他？
        pass

    # Inputを使用済みとして記録する
    for txhash, txindex in new_tx.inputs:
        add_tx_usedindex(txhash=txhash, usedindex=txindex, cur=chain_cur)
    # unconfirmedTXに加える
    if new_tx.type not in (C.TX_POW_REWARD, C.TX_POS_REWARD, C.TX_FINISH_CONTRACT):
        P.UNCONFIRMED_TX.add(new_tx.hash)

    if V.F_DEBUG:
        logging.debug("Add new tx to chain {}".format(hexlify(new_tx.hash).decode()))

    # Websocket APIに送信
    if P.NEW_CHAIN_INFO_QUE:
        P.NEW_CHAIN_INFO_QUE.put_nowait(new_tx.getinfo())
