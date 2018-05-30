from bc4py.config import BlockChainError
from bc4py.database.chain.read import read_block_object, read_tx_object
from binascii import hexlify


def fix_usedindex(cur):
    # Usedindexを直す
    usedindex = dict()
    d = cur.execute("SELECT `hash` FROM `block` WHERE `height`=0").fetchone()
    if d is None:
        raise BlockChainError('Not found any block.')
    next_hash = d[0]
    while next_hash:
        block = read_block_object(blockhash=next_hash, cur=cur)
        for tx in block.txs:
            if tx.hash not in usedindex:
                usedindex[tx.hash] = list()
            for txhash, txindex in tx.inputs:
                if txhash in usedindex:
                    usedindex[txhash].append(txindex)
                else:
                    usedindex[txhash] = [txindex]
        next_hash = block.next_hash
    # unconfirmedTX
    cur.execute("SELECT `hash` FROM `tx` WHERE `height` IS NULL")
    for (_txhash,) in cur:
        tx = read_tx_object(txhash=_txhash, cur=cur)
        if tx.hash not in usedindex:
            usedindex[tx.hash] = list()
        for txhash, txindex in tx.inputs:
            usedindex[txhash].append(txindex)
    # 全てのUsedIndex取得
    need_fix = list()
    for txhash, index in usedindex.items():
        byte_index = bytes(sorted(index))
        check_tx = read_tx_object(txhash=txhash, cur=cur)
        db_index = check_tx.used_index
        if check_tx.height and db_index != byte_index:
            need_fix.append((byte_index, txhash))
            print("wrong!", check_tx, "DB=", db_index, "Calc=", byte_index)
    cur.executemany("""
        UPDATE `tx` SET `used_index`=? WHERE `hash`=?
        """, need_fix)
    return need_fix
