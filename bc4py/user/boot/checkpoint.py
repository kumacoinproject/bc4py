from bc4py.config import C, P
from bc4py.database.chain.read import read_best_block_on_chain, max_block_height
from binascii import hexlify
import logging


def update_checkpoint(cur):
    if len(P.CHECK_POINTS) == 0:
        genesis_block = read_best_block_on_chain(height=0, cur=cur)
        P.CHECK_POINTS.clear()
        P.CHECK_POINTS[0] = genesis_block.hash
    while True:
        best_height = max(P.CHECK_POINTS)
        next_height = best_height + C.CHECKPOINT_SPAN
        top_height = max_block_height(cur=cur)
        if top_height - C.CHECKPOINT_SPAN < next_height:
            break
        elif top_height < next_height:
            break
        best_block = read_best_block_on_chain(height=next_height, cur=cur)
        if best_block.f_orphan:
            break
        P.CHECK_POINTS[next_height] = best_block.hash
        logging.info("Add new checkpoint {}={}".format(next_height, hexlify(best_block.hash).decode()))
