from bc4py.config import C, V, P, BlockChainError
from bc4py.chain.block import Block
from bc4py.chain.tx import TX
from bc4py.chain.checking import new_insert_block, check_tx, check_tx_time
from bc4py.chain.signature import fill_verified_addr_tx
from bc4py.database.builder import chain_builder, tx_builder
from bc4py.user.network.update import update_info_for_generate
from bc4py.user.network.directcmd import DirectCmd
from bc4py.user.network.connection import ask_node, seek_nodes
from logging import getLogger

log = getLogger('bc4py')


class BroadcastCmd:
    NEW_BLOCK = 'cmd/new-block'
    NEW_TX = 'cmd/new-tx'
    fail = 0

    @staticmethod
    def new_block(data):
        try:
            new_block = fill_newblock_info(data)
        except BlockChainError as e:
            warning = 'Do not accept block "{}"'.format(e)
            log.warning(warning)
            return False
        except Exception:
            error = "error on accept new block"
            log.error(error, exc_info=True)
            return False
        try:
            if new_insert_block(new_block):
                update_info_for_generate()
                log.info("Accept new block {}".format(new_block))
                return True
            else:
                return False
        except BlockChainError as e:
            error = 'Failed accept new block "{}"'.format(e)
            log.error(error, exc_info=True)
            return False
        except Exception:
            error = "error on accept new block"
            log.error(error, exc_info=True)
            return False

    @staticmethod
    def new_tx(data):
        try:
            new_tx: TX = data['tx']
            check_tx_time(new_tx)
            fill_verified_addr_tx(new_tx)
            check_tx(tx=new_tx, include_block=None)
            tx_builder.put_unconfirmed(tx=new_tx)
            log.info("Accept new tx {}".format(new_tx))
            update_info_for_generate(u_block=False, u_unspent=False, u_unconfirmed=True)
            return True
        except BlockChainError as e:
            error = 'Failed accept new tx "{}"'.format(e)
            log.error(error, exc_info=True)
            return False
        except Exception:
            error = "Failed accept new tx"
            log.error(error, exc_info=True)
            return False


def fill_newblock_info(data):
    new_block: Block = Block.from_binary(binary=data['binary'])
    log.debug("fill newblock height={} newblock={}".format(data.get('height'), new_block.hash.hex()))
    proof: TX = data['proof']
    new_block.txs.append(proof)
    new_block.flag = data['block_flag']
    my_block = chain_builder.get_block(new_block.hash)
    if my_block:
        raise BlockChainError('Already inserted block {}'.format(my_block))
    before_block = chain_builder.get_block(new_block.previous_hash)
    if before_block is None:
        log.debug("Cannot find beforeBlock, try to ask outside node")
        # not found beforeBlock, need to check other node have the the block
        new_block.inner_score *= 0.70  # unknown previousBlock, score down
        before_block = make_block_by_node(blockhash=new_block.previous_hash, depth=0)
    new_height = before_block.height + 1
    proof.height = new_height
    new_block.height = new_height
    # work check
    # TODO: correct position?
    if not new_block.pow_check():
        raise BlockChainError('Proof of work is not satisfied')
    # Append general txs
    for txhash in data['txs'][1:]:
        tx = tx_builder.get_tx(txhash)
        if tx is None:
            new_block.inner_score *= 0.75  # unknown tx, score down
            log.debug("Unknown tx, try to download")
            r = ask_node(cmd=DirectCmd.TX_BY_HASH, data={'txhash': txhash}, f_continue_asking=True)
            if isinstance(r, str):
                raise BlockChainError('Failed unknown tx download "{}"'.format(r))
            tx: TX = r
            tx.height = None
            check_tx(tx, include_block=None)
            tx_builder.put_unconfirmed(tx)
            log.debug("Success unknown tx download {}".format(tx))
        tx.height = new_height
        new_block.txs.append(tx)
    return new_block


def broadcast_check(data):
    if P.F_NOW_BOOTING:
        return False
    elif BroadcastCmd.NEW_BLOCK == data['cmd']:
        result = BroadcastCmd.new_block(data=data['data'])
    elif BroadcastCmd.NEW_TX == data['cmd']:
        result = BroadcastCmd.new_tx(data=data['data'])
    else:
        return False
    # check failed count over
    if result:
        BroadcastCmd.fail = 0
    else:
        BroadcastCmd.fail += 1
    return result


def make_block_by_node(blockhash, depth):
    """ create Block by outside node """
    log.debug("make block by node depth={} hash={}".format(depth, blockhash.hex()))
    block: Block = seek_nodes(cmd=DirectCmd.BLOCK_BY_HASH, data={'blockhash': blockhash})
    before_block = chain_builder.get_block(blockhash=block.previous_hash)
    if before_block is None:
        if depth < C.MAX_RECURSIVE_BLOCK_DEPTH:
            before_block = make_block_by_node(blockhash=block.previous_hash, depth=depth+1)
        else:
            raise BlockChainError('Cannot recursive get block depth={} hash={}'
                                  .format(depth, block.previous_hash.hex()))
    height = before_block.height + 1
    block.height = height
    block.inner_score *= 0.70
    for tx in block.txs:
        tx.height = height
    if not new_insert_block(block=block, f_time=False, f_sign=True):
        raise BlockChainError('Failed insert beforeBlock {}'.format(before_block))
    return block
