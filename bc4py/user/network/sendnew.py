from bc4py.config import C, V, P, BlockChainError
from bc4py.chain.manage import insert2chain_with_lock, check_tx, add_tx_as_new
from bc4py.user.network import BroadcastCmd
from bc4py.user.utxo import add_utxo_user
from p2p_python.client import ClientCmd
from .update import update_mining_staking_all_info
import logging
import time
from threading import Thread


def mined_newblock(que, pc):
    # 新規採掘BlockをP2Pに公開
    while True:
        try:
            new_block = que.get()
            new_block.create_time = int(time.time())
            if P.F_NOW_BOOTING:
                continue
            elif insert2chain_with_lock(new_block=new_block):
                logging.info("Mined new block {}".format(new_block.getinfo()))
            else:
                continue
            proof = new_block.txs[0]
            others = [tx.hash for tx in new_block.txs]
            finish_tx = [tx.b for tx in new_block.txs if tx.type == C.TX_FINISH_CONTRACT]
            data = {
                'cmd': BroadcastCmd.NEW_BLOCK,
                'data': {
                    'block': new_block.b,
                    'txs': others,
                    'proof': proof.b,
                    'finish_bin': finish_tx,
                    'sign': proof.signature}
            }
            try:
                pc.send_command(cmd=ClientCmd.BROADCAST, data=data)
                logging.info("Success broadcast new block {}".format(new_block))
                update_mining_staking_all_info()
            except TimeoutError:
                logging.warning("Failed broadcast new block, other nodes don\'t accept {}"
                                .format(new_block.getinfo()))
                P.F_NOW_BOOTING = True
        except BlockChainError as e:
            logging.error('Failed mined new block "{}"'.format(e))


def send_newtx(new_tx, chain_cur, account_cur):
    assert V.PC_OBJ, "PeerClient is None."
    check_tx(tx=new_tx, include_block=None, cur=chain_cur)
    add_tx_as_new(new_tx=new_tx, chain_cur=chain_cur, account_cur=account_cur)
    add_utxo_user(tx=new_tx, chain_cur=chain_cur, account_cur=account_cur)
    # P.UNCONFIRMED_TX同じスレッドでマニュアル的に加える必要がある
    P.UNCONFIRMED_TX.add(new_tx.hash)
    data = {
        'cmd': BroadcastCmd.NEW_TX,
        'data': {
            'tx': new_tx.b,
            'sign': new_tx.signature}
    }
    try:
        V.PC_OBJ.send_command(cmd=ClientCmd.BROADCAST, data=data)
        logging.info("Success broadcast new tx {}".format(new_tx))
        Thread(target=delay_update, name='Update', daemon=True).start()
        return True
    except BaseException as e:
        logging.warning("Failed broadcast new tx, other nodes don\'t accept {} {}"
                        .format(new_tx.getinfo(), e))
        P.UNCONFIRMED_TX.remove(new_tx.hash)
        return False


def delay_update():
    time.sleep(1)
    logging.debug("Delayed update start.")
    update_mining_staking_all_info(u_block=False, u_unspent=True, u_unconfirmed=True)
