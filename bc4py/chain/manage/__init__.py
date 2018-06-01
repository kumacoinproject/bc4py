from bc4py.config import V, P, BlockChainError
from bc4py.chain.manage.checkblock import check_block, check_block_time
from bc4py.chain.manage.addblock import add_block, add_rollback_block
from bc4py.chain.manage.rollbackblock import rollback_block
from bc4py.chain.manage.addtx import add_tx_as_new
from bc4py.database.chain.read import read_best_block, max_block_height, read_block_object, fill_tx_objects
from bc4py.database.create import closing, create_db
from .checktx import check_tx
from binascii import hexlify
import logging
from threading import Lock
import time


# 同時にBlockデータを入力してはいけない
global_chain_lock = Lock()


def insert2chain_with_lock(new_block):
    start0 = time.time()
    with global_chain_lock:
        start1 = time.time()
        if 1 < start1 - start0:
            logging.warning("Long locking for NewBlock {}Sec".format(round(start1-start0, 3)))
        with closing(create_db(V.DB_BLOCKCHAIN_PATH, f_on_memory=True)) as chain_db:
            with closing(create_db(V.DB_ACCOUNT_PATH, f_on_memory=True)) as account_db:
                chain_cur = chain_db.cursor()
                account_cur = account_db.cursor()
                if insert_to_chain(new_block=new_block, chain_cur=chain_cur,
                                   account_cur=account_cur, f_check_time=True):
                    chain_db.commit()
                    account_db.commit()
                    logging.debug("AcceptNewBlock {}Sec {}".format(round(time.time()-start1, 3), new_block))
                    return True
                else:
                    chain_db.rollback()
                    account_db.rollback()
                    logging.debug("RejectNewBlock {}Sec {}".format(round(time.time()-start1, 3), new_block))
                    return False


def insert_to_chain(new_block, chain_cur, account_cur, f_check_time=True):
    try:
        global global_chain_lock
        assert new_block.height > 0, 'Do not add genesis block'
        assert global_chain_lock.locked_lock(), 'InsertChain is not locked.'
        logging.info("NewBlockInsert {}".format(new_block))
        if f_check_time:
            check_block_time(block=new_block)
        # MainChainのチェックがある為InsertしてからCheckする
        insert_block(new_block=new_block, chain_cur=chain_cur, account_cur=account_cur)
        check_block(block=new_block, cur=chain_cur)
        new_block.bits2target()
        new_block.target2diff()
        new_block.f_orphan = False
        # Websocket apiに通知
        if P.NEW_CHAIN_INFO_QUE:
            P.NEW_CHAIN_INFO_QUE.put_nowait(new_block.getinfo())
        return True
    except BlockChainError as e:
        logging.warning("Failed insert new block. '{}'".format(e), exc_info=V.F_DEBUG)
        return False


def insert_block(new_block, chain_cur, account_cur):
    # 新規にBlock・TXを加える操作
    # strict=True：入れるBlockがOrphanなら情報修正せずReturnする
    if len(new_block.txs) == 0:
        raise BlockChainError('No tx on block? {}'.format(hexlify(new_block.hash).decode()))

    # Block加える前にMainChainを調べる
    best_block_before = read_best_block(height=max_block_height(cur=chain_cur), cur=chain_cur)
    fill_tx_objects(block=best_block_before, cur=chain_cur)

    # 新規のBlockを記録する
    add_block(new_block=new_block, chain_cur=chain_cur, account_cur=account_cur)

    # Genesis block
    if new_block.height == 0:
        logging.debug("Add block to chain (genesis) {}".format(hexlify(new_block.hash).decode()))
        return

    # 追加後のBestBlockを調べる
    best_block = read_best_block(height=max_block_height(cur=chain_cur), cur=chain_cur)
    fill_tx_objects(block=best_block, cur=chain_cur)

    # フォークをチェック
    if best_block_before.hash == best_block.previous_hash:
        # 前のBestBlockと加えたBestBlockが繋がっている
        logging.debug("Add block to chain (strait) {}".format(hexlify(new_block.hash).decode()))
        return

    elif new_block.height < max(P.CHECK_POINTS):
        # CheckPoint以下のBlockでOrphanを挿入しようとした
        raise BlockChainError('You try to write block{} to area protected by checkpoint height{}.'
                              .format(new_block.height, max(P.CHECK_POINTS)))

    elif best_block_before.hash == best_block.hash:
        # フォークを確認、状態が変わらない＝挿入したBlock自体がOrphan
        main_chain = []
        folk_chain = [new_block]
        logging.debug("Folk info bb={} b={} n={}".format(best_block_before, best_block, new_block))

    else:
        # フォークを確認
        if new_block.hash == best_block.hash:
            # 挿入したBlockがMainChainだが別のLine
            main_chain = [new_block]
        else:
            main_chain = [best_block]
        folk_chain = [new_block, best_block_before]
        logging.debug("Folk info bb={} b={} n={}".format(best_block_before, best_block, new_block))

        # MainChain と FolkChain の最終Heightを揃える
        if folk_chain[-1].height > main_chain[-1].height:
            raise BlockChainError('New folk height is lower than old main chain. [{}>{}]'
                                  .format(best_block_before.height, best_block.height))
        elif folk_chain[-1].height < main_chain[-1].height:
            logging.debug("Add block to chain {}<{} (branch) {}"
                          .format(best_block_before.height, best_block.height, hexlify(new_block.hash).decode()))
            while folk_chain[-1].height != main_chain[-1].height:
                previous_block = read_block_object(blockhash=main_chain[-1].previous_hash, cur=chain_cur)
                main_chain.append(previous_block)
                logging.debug("{} : {}".format(main_chain[-1], folk_chain[-1]))
        else:
            logging.debug("Add block to chain (collision) {}".format(hexlify(new_block.hash).decode()))

        # previous_hashが同じになるまでBlockを取得する
        while main_chain[-1].previous_hash != folk_chain[-1].previous_hash:
            previous_block = read_block_object(blockhash=folk_chain[-1].previous_hash, cur=chain_cur)
            folk_chain.append(previous_block)
            previous_block = read_block_object(blockhash=main_chain[-1].previous_hash, cur=chain_cur)
            main_chain.append(previous_block)

    # folk_chain のデータをRollBackし main_chain で再構成する

    logging.debug("Folk chain\n{}".format("\n".join(str(block) for block in folk_chain)))
    logging.debug("Main chain\n{}".format("\n".join(str(block) for block in main_chain)))

    # フォーク前まで削除する
    rollback_block(folk_chain=folk_chain, chain_cur=chain_cur, account_cur=account_cur)

    # 再度記録する
    add_rollback_block(main_chain=main_chain, chain_cur=chain_cur, account_cur=account_cur)
    logging.debug("Finish adding new block to chain")
