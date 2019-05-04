from bc4py.config import C, V, P, BlockChainError
from bc4py.chain.checking import new_insert_block, check_tx, check_tx_time
from bc4py.user.network import BroadcastCmd
from p2p_python.client import ClientCmd
from bc4py.database.builder import tx_builder, builder
from bc4py.user.network.update import update_info_for_generate
from time import time
import queue
from logging import getLogger

log = getLogger('bc4py')


def mined_newblock(que, pc):
    # 新規採掘BlockをP2Pに公開
    while True:
        try:
            new_block = que.get(timeout=1)
            new_block.create_time = int(time())
            if P.F_NOW_BOOTING:
                log.debug("self reject, mined but now booting..")
                continue
            elif new_block.height != builder.best_block.height + 1:
                log.debug("self reject, mined but its old block...")
                continue
            else:
                log.debug("Mined block check success")
                if new_insert_block(new_block):
                    log.info("Mined new block {}".format(new_block.getinfo()))
                else:
                    log.debug("self reject, cannot new insert")
                    update_info_for_generate()
                    continue
            proof_tx = new_block.txs[0]
            txs_hash_list = [tx.hash for tx in new_block.txs]
            data = {
                'cmd': BroadcastCmd.NEW_BLOCK,
                'data': {
                    'binary': new_block.b,
                    'height': new_block.height,
                    'txs': txs_hash_list,
                    'proof': proof_tx,
                    'block_flag': new_block.flag,
                }
            }
            try:
                pc.send_command(cmd=ClientCmd.BROADCAST, data=data)
                log.info("Success broadcast new block {}".format(new_block))
                update_info_for_generate()
            except TimeoutError:
                log.warning("Failed broadcast new block, other nodes don\'t accept {}".format(new_block.getinfo()))
                # log.warning("47 Set booting mode.")
                # P.F_NOW_BOOTING = True
        except queue.Empty:
            if pc.f_stop:
                log.debug("Mined new block closed.")
                break
        except BlockChainError as e:
            log.error('Failed mined new block "{}"'.format(e))
        except Exception as e:
            log.error("mined_newblock()", exc_info=True)


def send_newtx(new_tx, outer_cur=None, exc_info=True):
    assert V.PC_OBJ, "PeerClient is None."
    try:
        check_tx_time(new_tx)
        check_tx(new_tx, include_block=None)
        data = {
            'cmd': BroadcastCmd.NEW_TX,
            'data': {
                'tx': new_tx
            }
        }
        V.PC_OBJ.send_command(cmd=ClientCmd.BROADCAST, data=data)
        if new_tx.type in (C.TX_VALIDATOR_EDIT, C.TX_CONCLUDE_CONTRACT):
            tx_builder.marge_signature(tx=new_tx)
        else:
            tx_builder.put_unconfirmed(tx=new_tx)
        log.info("Success broadcast new tx {}".format(new_tx))
        update_info_for_generate(u_block=False, u_unspent=True, u_unconfirmed=True)
        return True
    except Exception as e:
        log.warning("Failed broadcast new tx, other nodes don\'t accept {}".format(new_tx.getinfo()))
        log.warning("Reason is \"{}\"".format(e))
        log.debug("traceback,", exc_info=exc_info)
        return False


__all__ = [
    "mined_newblock",
    "send_newtx",
]
