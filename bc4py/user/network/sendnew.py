from bc4py.config import C, V, P, BlockChainError
from bc4py.chain.checking import new_insert_block, check_tx
from bc4py.user.network import BroadcastCmd
from p2p_python.client import ClientCmd
from bc4py.database.builder import tx_builder
from bc4py.user.network.update import update_mining_staking_all_info
import logging
import time


def mined_newblock(que, pc):
    # 新規採掘BlockをP2Pに公開
    while True:
        try:
            new_block = que.get()
            new_block.create_time = int(time.time())
            if P.F_NOW_BOOTING:
                continue
            elif new_insert_block(new_block, time_check=True):
                logging.info("Mined new block {}".format(new_block.getinfo()))
            else:
                continue
            proof = new_block.txs[0]
            others = [tx.hash for tx in new_block.txs]
            data = {
                'cmd': BroadcastCmd.NEW_BLOCK,
                'data': {
                    'block': new_block.b,
                    'txs': others,
                    'proof': proof.b,
                    'sign': proof.signature}
            }
            try:
                pc.send_command(cmd=ClientCmd.BROADCAST, data=data)
                logging.info("Success broadcast new block {}".format(new_block))
                update_mining_staking_all_info(f_force=True)
            except TimeoutError:
                logging.warning("Failed broadcast new block, other nodes don\'t accept {}"
                                .format(new_block.getinfo()))
                P.F_NOW_BOOTING = True
        except BlockChainError as e:
            logging.error('Failed mined new block "{}"'.format(e))


def send_newtx(new_tx):
    assert V.PC_OBJ, "PeerClient is None."
    check_tx(new_tx, include_block=None)
    data = {
        'cmd': BroadcastCmd.NEW_TX,
        'data': {
            'tx': new_tx.b,
            'sign': new_tx.signature}}
    try:
        V.PC_OBJ.send_command(cmd=ClientCmd.BROADCAST, data=data)
        tx_builder.put_unconfirmed(new_tx)
        logging.info("Success broadcast new tx {}".format(new_tx))
        return True
    except BaseException as e:
        logging.warning("Failed broadcast new tx, other nodes don\'t accept {} {}"
                        .format(new_tx.getinfo(), e))
        return False
