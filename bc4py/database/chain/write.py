#!/user/env python3
# -*- coding: utf-8 -*-

from bc4py.config import C, BlockChainError
from bc4py.chain.utils import signature2bin
from binascii import hexlify
import logging


def recode_block(block, cur):
    txs = b''.join(tx.hash for tx in block.txs)
    if block.flag == C.BLOCK_POW:
        if not block.work_hash:
            block.update_pow()
        work = block.work_hash
    else:
        work = None
    params = (block.hash, block.height, work, block.b, block.flag, block.time, txs)
    cur.execute("""
        INSERT INTO `block` (`hash`,`height`,`work`,`bin`,`flag`,`time`,`txs`)
        VALUES (?, ?, ?, ?, ?, ?, ?)""", params)


def remove_orphan_block(orphan_block, cur):
    cur.execute("DELETE FROM `block` WHERE `hash`=?", (orphan_block.hash,))
    proof_tx = orphan_block.txs[0]
    delete_tx(txhash=proof_tx.hash, cur=cur)
    logging.info("Remove orphan block {} {} proof={}".format(orphan_block.height, orphan_block, proof_tx))


def recode_tx(tx, cur):
    sign = signature2bin(tx.signature)
    params = (tx.hash, tx.height, tx.b, sign, tx.time, tx.used_index)
    cur.execute("""
        INSERT INTO `tx` (`hash`,`height`,`bin`,`sign`,`time`,`used_index`)
        VALUES (?, ?, ?, ?, ?, ?)""", params)


def delete_tx(txhash, cur):
    cur.execute("DELETE FROM `tx` WHERE `hash`=?", (txhash,))
    cur.execute("DELETE FROM `coins` WHERE `hash`=?", (txhash,))
    cur.execute("DELETE FROM `contract_info` WHERE `hash`=?", (txhash,))
    cur.execute("DELETE FROM `contract_history` WHERE `start_hash`=?", (txhash, ))


def update_tx_height(txhash, height, cur):
    # print("update tx height", hexlify(txhash).decode(), height)
    cur.execute("UPDATE `tx` SET `height`=? WHERE `hash`=?", (height, txhash))


def update_tx_usedindex(txhash, usedindex, cur):
    # usedindexはBytesでもListでもいい
    used = bytes(sorted(usedindex))
    cur.execute("""
        UPDATE `tx` SET `used_index`=? WHERE `hash`=?
        """, (used, txhash))


def add_tx_usedindex(txhash, usedindex, cur, f_raise=True):
    assert 0 <= usedindex < 256, '0 <= usedindex({}) < 256'.format(usedindex)
    d = cur.execute("""
            SELECT `used_index` FROM `tx` WHERE `hash`=?
            """, (txhash,)).fetchone()
    if d is None:
        raise BlockChainError('Not found tx {}'.format(hexlify(txhash).decode()))
    used_index = d[0]
    if usedindex in used_index:
        if f_raise:
            raise BlockChainError('Try to add, but already used index. {}:{}'
                                  .format(hexlify(txhash).decode(), usedindex))
        else:
            logging.warning('Try to add, but already used index. warming. {}:{}'
                            .format(hexlify(txhash).decode(), usedindex))
    else:
        update_tx_usedindex(txhash=txhash, usedindex=used_index + usedindex.to_bytes(1, 'big'), cur=cur)
        logging.debug("Add usedindex {}:{}".format(usedindex, hexlify(txhash).decode()))


def remove_tx_usedindex(txhash, usedindex, cur, f_raise=True):
    assert 0 <= usedindex < 256, '0 <= usedindex({}) < 256'.format(usedindex)
    d = cur.execute("""
            SELECT `used_index` FROM `tx` WHERE `hash`=?
            """, (txhash,)).fetchone()
    if d is None:
        raise BlockChainError('Not found tx {}'.format(hexlify(txhash).decode()))
    used_index = d[0]
    if usedindex not in used_index:
        if not f_raise:
            return
        raise BlockChainError('Try to remove used flag, but cannot find. [{} not in {}]'
                              .format(usedindex, used_index))
    update_tx_usedindex(txhash=txhash, usedindex=used_index.replace(usedindex.to_bytes(1, 'big'), b''), cur=cur)
    logging.debug("Remove usedindex {}:{}".format(usedindex, hexlify(txhash).decode()))


def add_mint_coin(txhash, mint_object, cur):
    cur.execute("""
        INSERT INTO `coins` (`hash`,`coin_id`,`bin`) VALUES (?,?,?)
        """, (txhash, mint_object.coin_id, mint_object.binary))


def recode_contract_code(address, txhash, cur):
    cur.execute("""
    INSERT INTO `contract_info` (`address`,`hash`) VALUES (?,?)
    """, (address, txhash))
    logging.debug("New contract code inserted. {}".format(hexlify(txhash).decode()))


def recode_start_contract(start_hash, address, cur):
    cur.execute("""
    INSERT INTO `contract_history` (`start_hash`,`address`) VALUES (?,?)
    """, (start_hash, address))


def recode_finish_contract(start_hash, finish_hash, cur):
    cur.execute("""
        UPDATE `contract_history` SET `finish_hash`=? WHERE `start_hash`=?
        """, (finish_hash, start_hash))
