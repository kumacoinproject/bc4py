from bc4py.database.chain.read import read_block_object, fill_tx_objects
from binascii import hexlify


def fix_tx_height(cur):
    # TXのHeightをMainChainの記録を元に直す(Blockが正しいと考えて)
    need_fix = list()
    cur.execute("SELECT `hash` FROM `block` ORDER BY `height`")
    for (blockhash,) in cur.fetchall():
        block = read_block_object(blockhash=blockhash, cur=cur, f_fill_tx=False)
        if block.f_orphan:
            continue
        fill_tx_objects(block=block, cur=cur)
        for tx in block.txs:
            if block.height != tx.height:
                need_fix.append((block.height, tx.hash))
                print("wrong!", hexlify(tx.hash).decode(), block.height, tx.height)
    cur.executemany("""
        UPDATE `tx` SET `height`=? WHERE `hash`=?
        """, need_fix)
    return need_fix
