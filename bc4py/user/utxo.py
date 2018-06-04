from bc4py.config import C, V, BlockChainError
from bc4py.user import CoinObject
from bc4py.database.user.flag import is_include_to_log, is_include_utxo
from bc4py.database.user.read import read_all_utxo, read_utxo, address2group
from bc4py.database.user.write import update_utxo_used, update_utxo_unused, rollback_account_balance, recode_utxo, \
    delete_utxo, move_account_balance
from bc4py.database.chain.read import \
    read_tx_object, read_best_block_on_chain, max_block_height, fill_tx_objects, read_tx_output
from binascii import hexlify
import logging
import time


def get_unspent(chain_cur, account_cur):
    unspent_pairs = list()
    orphan_pairs = list()
    now = int(time.time()) - V.BLOCK_GENESIS_TIME
    top_height = max_block_height(cur=chain_cur)
    for txhash, txindex in read_all_utxo(cur=account_cur):
        try:
            tx = read_tx_object(txhash=txhash, cur=chain_cur)
        except BlockChainError as e:
            logging.warning('ignore error "{}"'.format(e))
            continue
        if tx.b is None:
            logging.warning("Need fix chan data. Not found tx {}".format(hexlify(txhash).decode()))
            continue

        elif tx.type in (C.TX_POW_REWARD, C.TX_POS_REWARD):
            # ProofTXはMainChainに含まれ、かつ採掘してからMATURE_HEIGHT Block経過する事
            if tx.height is None:
                continue
            elif tx.height > top_height - C.MATURE_HEIGHT:
                continue
            main_block = read_best_block_on_chain(height=tx.height, cur=chain_cur)
            fill_tx_objects(block=main_block, cur=chain_cur)
            if tx in main_block.txs:
                unspent_pairs.append((txhash, txindex))
            else:
                for main_tx in main_block.txs:
                    if main_tx.hash == tx.hash:
                        unspent_pairs.append((txhash, txindex))
                        break
                else:
                    # Orphan blockのProofTXなので無視
                    orphan_pairs.append((txhash, txindex))

        elif tx.height:
            # Blockに取り込まれている
            unspent_pairs.append((txhash, txindex))
        else:
            # 通常のTX or Blockにまだ収容されていない未承認TX
            if tx.time <= now <= tx.deadline:
                unspent_pairs.append((txhash, txindex))
            else:
                orphan_pairs.append((txhash, txindex))  # 収容可能時間切れ
    # Notice
    if len(orphan_pairs) > 10:
        logging.warning("Read account tx, unspent={} orphan={}.".format(len(unspent_pairs), len(orphan_pairs)))
    elif V.F_DEBUG:
        logging.debug("Read account tx, unspent={} orphan={}.".format(len(unspent_pairs), len(orphan_pairs)))

    # print("\n".join(str(read_tx_object(txhash, chain_cur)) for txhash, txindex in unspent_pairs))
    # print("\n".join(str(read_tx_object(txhash, chain_cur)) for txhash, txindex in orphan_pairs))
    # exit(0)
    return unspent_pairs, orphan_pairs


def full_unspents(unspent_pairs, chain_cur):
    # {
    #   "txhash": "7e815deb82d5adac873305f332f712b77f139397946999c5eef1e208b190a7c1",
    #   "txindex": 1,
    #   "address": "NAMIROQ4ZVQYTZ6TQPS7SHBIWT3J6IRS7HT344YA",
    #   "coin_id": 0,
    #   "amount": 8498908000,
    #   "height": 20123
    # }
    unspents = list()
    for txhash, txindex in unspent_pairs:
        tx = read_tx_object(txhash=txhash, cur=chain_cur)
        address, coin_id, amount = tx.outputs[txindex]
        unspents.append({
            "txhash": txhash,
            "txindex": txindex,
            "address": address,
            "coin_id": coin_id,
            "amount": amount,
            "height": tx.height,
            "type": C.txtype2name[tx.type]})
    return unspents


def get_utxo_user(cur):
    return read_all_utxo(cur)


def add_utxo_user(tx, chain_cur, account_cur, f_raise=True):
    # Balanceの操作、UTXO追加、UsedIndexの操作

    input_index = 0
    for txhash, txindex in tx.inputs:
        # Indexの操作
        used = read_utxo(txhash=txhash, txindex=txindex, cur=account_cur)
        if used is None:
            pass  # 無関係TX
        elif used:
            # 既に使用済みのUTXOなのに別のに使用しようとしている
            if f_raise:
                raise BlockChainError('This input is already used! {}:{}'
                                      .format(hexlify(txhash).decode(), txindex))
        else:
            update_utxo_used(txhash=txhash, txindex=txindex, cur=account_cur)
            # Balanceの操作
            if not is_include_to_log(txhash=tx.hash, direction=1, txindex=input_index, cur=account_cur):
                address, coin_id, amount = read_tx_output(txhash=txhash, txindex=txindex, cur=chain_cur)
                coins = CoinObject(coin_id, amount)
                from_group = address2group(address=address, cur=account_cur)
                from_group = from_group if from_group else C.ANT_UNKNOWN
                move_account_balance(from_group=from_group, to_group=C.ANT_OUTSIDE, coins=coins, cur=account_cur,
                                     txhash=tx.hash, direction=1, txindex=input_index, f_allow_minus=True)
                if tx.type != C.TX_POS_REWARD:
                    logging.warning('Cannot detect who input the coins, {}:{}:{}'
                                    .format(hexlify(tx.hash).decode(), 1, input_index))
        input_index += 1

    output_index = 0
    for address, coin_id, amount in tx.outputs:
        # UTXOの操作
        to_group = address2group(address=address, cur=account_cur)
        if to_group and not is_include_to_log(txhash=tx.hash, direction=0, txindex=output_index, cur=account_cur):
            coins = CoinObject(coin_id, amount)
            move_account_balance(from_group=C.ANT_OUTSIDE, to_group=to_group, coins=coins, cur=account_cur,
                                 txhash=tx.hash, direction=0, txindex=output_index, f_allow_minus=True)
            logging.debug("Add utxo {} to {}".format(coins, to_group))
        # Ifに含めるとTransferが記録されないような気がする
        # だがRollBackしたBlockを再度記録する時にダブるね
        if to_group:
            if not is_include_utxo(txhash=tx.hash, txindex=output_index, cur=account_cur):
                recode_utxo(txhash=tx.hash, txindex=output_index, cur=account_cur)
        output_index += 1


def add_rollback_utxo_user(tx, chain_cur, account_cur, f_raise=True):
    # Balanceの操作、UTXO追加、UsedIndexの操作

    input_index = 0
    for txhash, txindex in tx.inputs:
        # Indexの操作
        used = read_utxo(txhash=txhash, txindex=txindex, cur=account_cur)
        if used is None:
            pass  # 無関係TX
        elif used:
            # 既に使用済みのUTXOなのに別のに使用しようとしている
            if f_raise:
                raise BlockChainError('This input is already used! {}:{}'
                                    .format(hexlify(txhash).decode(), txindex))
        else:
            update_utxo_used(txhash=txhash, txindex=txindex, cur=account_cur)
            # Balanceの操作
            if not is_include_to_log(txhash=tx.hash, direction=1, txindex=input_index, cur=account_cur):
                address, coin_id, amount = read_tx_output(txhash=txhash, txindex=txindex, cur=chain_cur)
                coins = CoinObject(coin_id, amount)
                from_group = address2group(address=address, cur=account_cur)
                from_group = from_group if from_group else C.ANT_UNKNOWN
                move_account_balance(from_group=from_group, to_group=C.ANT_OUTSIDE, coins=coins, cur=account_cur,
                                     txhash=tx.hash, direction=1, txindex=input_index, f_allow_minus=True)
                if tx.type != C.TX_POS_REWARD:
                    logging.warning('Cannot detect who input the coins, {}:{}:{}'
                                    .format(hexlify(tx.hash).decode(), 1, input_index))
        input_index += 1

    output_index = 0
    for address, coin_id, amount in tx.outputs:
        # UTXOの操作
        to_group = address2group(address=address, cur=account_cur)
        if to_group and not is_include_to_log(txhash=tx.hash, direction=0, txindex=output_index, cur=account_cur):
            coins = CoinObject(coin_id, amount)
            move_account_balance(from_group=C.ANT_OUTSIDE, to_group=to_group, coins=coins, cur=account_cur,
                                 txhash=tx.hash, direction=0, txindex=output_index, f_allow_minus=True)
            logging.debug("Add utxo {} to {}".format(coins, to_group))
            # Ifに含めるとTransferが記録されないような気がする
            # だがRollBackしたBlockを再度記録する時にダブるね
            recode_utxo(txhash=tx.hash, txindex=output_index, cur=account_cur)
        output_index += 1


def remove_utxo_user(tx, cur, f_raise=True):
    # 期限がきても取り込まれず削除されるTXなど用
    if tx.type in (C.TX_POW_REWARD, C.TX_POS_REWARD):
        raise BlockChainError('It\'s proof tx. {}'.format(hexlify(tx.hash).decode()))

    # Inputs
    for txhash, txindex in tx.inputs:
        used = read_utxo(txhash=txhash, txindex=txindex, cur=cur)
        if used is None:
            pass
        elif used:
            # 未使用にする
            update_utxo_unused(txhash=txhash, txindex=txindex, cur=cur)
        else:
            # 未使用にしなければいけないのに既に未使用
            # 先に消すべきTXが存在するかチェーンに矛盾
            if f_raise:
                raise BlockChainError('This input unused, but used by rollback block. {}:{}'
                                      .format(hexlify(txhash), txindex))
    # Outputs
    txindex = 0
    for address, coin_id, amount in tx.outputs:
        to_group = address2group(address=address, cur=cur)
        if to_group:
            used = read_utxo(txhash=tx.hash, txindex=txindex, cur=cur)
            if used is None:
                pass  # 削除予定UTXOが存在しない
            elif used:
                # 消そうとしているOutputが使用されている
                # 先に消すべきTXが存在するかチェーンに矛盾
                raise BlockChainError('Try to delete utxo, but output is used. {}:{}'
                                      .format(hexlify(tx.hash).decode(), txindex))
            else:
                delete_utxo(txhash=tx.hash, txindex=txindex, cur=cur)
        txindex += 1

    # Account
    if is_include_to_log(txhash=tx.hash, direction=None, txindex=None, cur=cur):
        rollback_account_balance(txhash=tx.hash, cur=cur, f_allow_minus=True)


def rollback_proof_utxo_user(tx, cur, f_raise=True):
    # 新規Block挿入により記録, proof txのみRollback
    if tx.type not in (C.TX_POW_REWARD, C.TX_POS_REWARD):
        raise BlockChainError('It\'s not proof tx. {}'.format(hexlify(tx.hash).decode()))

    # Inputs
    for txhash, txindex in tx.inputs:
        used = read_utxo(txhash=txhash, txindex=txindex, cur=cur)
        if used is None:
            pass
        elif used:
            # 未使用にする
            update_utxo_unused(txhash=txhash, txindex=txindex, cur=cur)
        else:
            # 未使用にしなければいけないのに既に未使用
            # これは一つ一つ消す場合、フォーク時に一気消しは不要
            raise BlockChainError('This input unused, but used by rollback block. {}:{}'
                                  .format(hexlify(txhash), txindex))
    # Outputs
    output_index = 0
    for address, coin_id, amount in tx.outputs:
        to_group = address2group(address=address, cur=cur)
        if to_group:
            used = read_utxo(txhash=tx.hash, txindex=output_index, cur=cur)
            if used is None:
                raise BlockChainError('Related output, but do not recoded utxo. to={} {}:{}'
                                      .format(to_group, hexlify(tx.hash).decode(), output_index))
                # 削除予定UTXOが存在しない
            elif used:
                # 消そうとしているOutputが使用されている
                if f_raise:
                    raise BlockChainError('Try to delete utxo, but used. {}:{}'
                                          .format(hexlify(tx.hash).decode(), output_index))
            else:
                delete_utxo(txhash=tx.hash, txindex=output_index, cur=cur)
        output_index += 1

    # Account
    if is_include_to_log(txhash=tx.hash, direction=None, txindex=None, cur=cur):
        rollback_account_balance(tx.hash, cur, f_allow_minus=True)
    logging.debug("Remove from utxo {}".format(hexlify(tx.hash).decode()))
