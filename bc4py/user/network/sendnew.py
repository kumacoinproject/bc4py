from bc4py.config import V, P, BlockChainError
from bc4py.chain.checking import new_insert_block, check_tx, check_tx_time
from bc4py.user.network import BroadcastCmd
from p2p_python.server import Peer2PeerCmd
from p2p_python.config import PeerToPeerError
from bc4py.database.builder import tx_builder, chain_builder
from bc4py.user.network.update import update_info_for_generate
from logging import getLogger
from time import time
import asyncio

loop = asyncio.get_event_loop()
log = getLogger('bc4py')


async def mined_newblock(que):
    """new thread, broadcast mined block to network"""
    assert V.P2P_OBJ, "PeerClient is None"
    assert isinstance(que, asyncio.Queue)
    while not P.F_STOP:
        try:
            new_block = await asyncio.wait_for(que.get(), 1.0)
            new_block.create_time = int(time())
            if P.F_NOW_BOOTING:
                log.debug("self reject, mined but now booting")
                continue
            elif new_block.height != chain_builder.best_block.height + 1:
                log.debug("self reject, mined but its old block")
                continue
            else:
                log.debug("Mined block check success")
                if await new_insert_block(new_block):
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
                await V.P2P_OBJ.send_command(cmd=Peer2PeerCmd.BROADCAST, data=data)
                log.info("Success broadcast new block {}".format(new_block))
                update_info_for_generate()
            except PeerToPeerError as e:
                log.debug(f"unstable network '{e}'")
            except asyncio.TimeoutError:
                log.warning("Failed broadcast new block, other nodes don\'t accept {}".format(new_block.getinfo()))
        except asyncio.TimeoutError:
            if V.P2P_OBJ.f_stop:
                log.debug("Mined new block closed")
                break
        except BlockChainError as e:
            log.error('Failed mined new block "{}"'.format(e))
        except Exception:
            log.error("mined_newblock exception", exc_info=True)


async def send_newtx(new_tx, exc_info=True):
    assert V.P2P_OBJ, "PeerClient is None"
    try:
        check_tx_time(new_tx)
        check_tx(new_tx, include_block=None)
        data = {
            'cmd': BroadcastCmd.NEW_TX,
            'data': {
                'tx': new_tx
            }
        }
        await V.P2P_OBJ.send_command(cmd=Peer2PeerCmd.BROADCAST, data=data)
        await tx_builder.put_unconfirmed(tx=new_tx)
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
