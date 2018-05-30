#!/user/env python3
# -*- coding: utf-8 -*-

"""
accountDBへの書き込み操作のみ
"""

from bc4py.config import C, V, BlockChainError
from bc4py.utils import AESCipher
from bc4py.user import CoinObject
from nem_ed25519.base import Encryption
from nem_ed25519.key import convert_address
from binascii import unhexlify, hexlify
from .flag import is_locked_database
import logging
import os
import time


def fill_keypool(n, cur):
    if is_locked_database(cur):
        raise BlockChainError('Locked database.')
    d = cur.execute("""
            SELECT `id`,`sk` FROM `pool` WHERE `group` = ?
            """, (C.ANT_RESERVED,)).fetchall()
    size = len(d)
    if size > 200:
        return
    ecc = Encryption(prefix=V.BLOCK_PREFIX)
    # Key生成には時間がかかるので10個ずつ(1Sec)
    for i in range(n):
        sk = unhexlify(ecc.secret_key().encode())
        pk = unhexlify(ecc.public_key().encode())
        ck = ecc.get_address()
        params = (C.ANT_RESERVED, AESCipher.encrypt(V.ENCRYPT_KEY, sk) if V.ENCRYPT_KEY else sk, pk, ck)
        cur.execute("""
        INSERT INTO `pool` (`group`, `sk`, `pk`, `ck`) VALUES (?, ?, ?, ?)
        """, params)
    logging.debug("Fill key pool ({}=>{})".format(size, size + n))


def new_keypair(group, cur):
    """
    Keypairを取得しGroupを書き換える
    :return: (sk hex str, pk hex str, ck str)
    """
    fill_keypool(n=3, cur=cur)
    d = cur.execute("""
    SELECT `id`, `sk`, `pk`, `ck` FROM `pool`
    WHERE `group` = ? ORDER BY `id` ASC
    """, (C.ANT_RESERVED,)).fetchone()
    uuid, sk, pk, ck = d
    cur.execute("""
    UPDATE `pool` SET `group`=? WHERE `id`=?
    """, (group, uuid))
    sk = AESCipher.decrypt(V.ENCRYPT_KEY, sk) if V.ENCRYPT_KEY else sk
    return sk, pk, ck


def new_contract_keypair(cur):
    fill_keypool(n=3, cur=cur)
    d = cur.execute("""
        SELECT `id`, `sk`, `pk`, `ck` FROM `pool`
        WHERE `group` = ? ORDER BY `id` ASC
        """, (C.ANT_RESERVED,)).fetchone()
    uuid, sk, pk, ck = d
    # アカウントに反映されるのも面倒なのでAddressをContractに変えない
    # NormalアドレスよりContracのPKを取得する事を考える
    # 参考：from nem_ed25519.key import convert_address
    contract_ck = convert_address(ck=ck, prefix=V.BLOCK_CONTRACT_PREFIX)
    if V.BLOCK_PREFIX == V.BLOCK_CONTRACT_PREFIX or V.BLOCK_CONTRACT_PREFIX is None:
        raise BlockChainError('Do not setup contract prefix or same with normal prefix.')
    cur.execute("""
        UPDATE `pool` SET `group`=? WHERE `id`=?
        """, (C.ANT_CONTRACT, uuid))
    return contract_ck


def change_encrypt_key(new_key, cur):
    # SecretKeyの鍵を変更する、Noneの場合は非暗号化
    d = cur.execute("""
        SELECT `id`, `sk`, `pk` FROM `pool`""")
    updates = list()
    ecc = Encryption(prefix=V.BLOCK_PREFIX)
    for uuid, sk, pk in d.fetchall():
        sk = AESCipher.decrypt(V.ENCRYPT_KEY, sk) if V.ENCRYPT_KEY else sk
        ecc.public_key(sk=sk)
        if ecc.pk != hexlify(pk).decode():
            raise BlockChainError('Decryption error! wrong key. [{}=>{}]'
                                  .format(hexlify(ecc.pk).decode(), hexlify(pk).decode()))
        new_sk = sk if new_key is None else AESCipher.encrypt(key=new_key, raw=sk)
        updates.append((uuid, new_sk))
    cur.executemany("""
        UPDATE `pool` SET `sk`=? WHERE `id`=?
        """, updates)


def new_group(group, cur):
    cur.execute("""
    INSERT INTO `balance` VALUES (?, ?, ?)
    """, (group, 0, 0))


def recode_utxo(txhash, txindex, cur):
    d = cur.execute("""
            SELECT `used` FROM `utxo` WHERE `hash`=? AND `index`=?
            """, (txhash, txindex)).fetchone()
    if d is not None:
        raise BlockChainError('Already recoded utxo {}:{}'.format(hexlify(txhash).decode(), txindex))
    cur.execute("""
        INSERT INTO `utxo` (`hash`,`index`,`used`) VALUES (?, ?, ?)
        """, (txhash, txindex, 0))


def delete_utxo(txhash, txindex, cur):
    d = cur.execute("""
        SELECT `used` FROM `utxo` WHERE `hash`=? AND `index`=?
        """, (txhash, txindex)).fetchone()
    if d is None:
        raise BlockChainError('Not found utxo {}:{}'.format(hexlify(txhash).decode(), txindex))
    cur.execute("""
        DELETE FROM `utxo` WHERE `hash`=? AND `index`=?
        """, (txhash, txindex))


def update_utxo_used(txhash, txindex, cur):
    # UTXOを使用済みに変更する
    d = cur.execute("""
        SELECT `used` FROM `utxo` WHERE `hash`=? AND `index`=?
        """, (txhash, txindex)).fetchone()
    if d is None:
        raise BlockChainError('Not found tx [{}:{}]'.format(hexlify(txhash).decode(), txindex))
    elif d[0] == 1:
        raise BlockChainError('Already used tx [{}:{}]'.format(hexlify(txhash).decode(), txindex))
    cur.execute("""
        UPDATE `utxo` SET `used`=? WHERE `hash`=? AND `index`=?
        """, (1, txhash, txindex))
    logging.debug('Update used {}:{}'.format(hexlify(txhash).decode(), txindex))


def update_utxo_unused(txhash, txindex, cur):
    # UTXOを未使用に変更する
    d = cur.execute("""
            SELECT `used` FROM `utxo` WHERE `hash`=? AND `index`=?
            """, (txhash, txindex)).fetchone()
    if d is None:
        raise BlockChainError('Not found tx [{}:{}]'.format(hexlify(txhash).decode(), txindex))
    elif d[0] == 0:
        raise BlockChainError('Unused tx [{}:{}]'.format(hexlify(txhash).decode(), txindex))
    cur.execute("""
        UPDATE `utxo` SET `used`=? WHERE `hash`=? AND `index`=?
        """, (0, txhash, txindex))
    logging.debug('Update unused {}:{}'.format(hexlify(txhash).decode(), txindex))


def move_account_balance(from_group, to_group, coins, cur,
                         txhash=None, direction=None, txindex=None, time_=None, f_allow_minus=False):
    assert isinstance(coins, CoinObject), 'coins is CoinObject.'
    assert txhash is None or len(coins.keys()) == 1, 'coinID is only one when sending.'
    # from_group => to_groupの残高移動
    txhash = os.urandom(20) if txhash is None else txhash
    time_ = time_ if time_ else int(time.time())
    insert_log = [(txhash, direction, txindex, from_group, to_group, coin_id, amount, time_)
                  for coin_id, amount in coins.items()]
    cur.executemany("""
        INSERT INTO `log` (`hash`,`direction`,`index`,`from_group`,`to_group`,`coin_id`,
        `amount`,`time`) VALUES (?,?,?,?,?,?,?,?)
        """, insert_log)
    # 引かれる方の残高を取得
    from_balance = {coin_id: amount for coin_id, amount in cur.execute("""
        SELECT `coin_id`,`amount` FROM `balance` WHERE `group`=?
        """, (from_group,)).fetchall()}
    # 加えられる方の残高を取得
    to_balance = {coin_id: amount for coin_id, amount in cur.execute("""
        SELECT `coin_id`,`amount` FROM `balance` WHERE `group`=?
        """, (to_group,)).fetchall()}
    # 引かれる方の新たな残高は
    group_new_balance = list()
    for coin_id, amount in coins.items():
        new_balance = (from_balance[coin_id] if coin_id in from_balance else 0) - amount
        group_new_balance.append((from_group, coin_id, new_balance))
        if not f_allow_minus and new_balance < 0:
            raise BlockChainError('Minus balance detected (from={},{}:{},new={})'
                                  .format(from_group, coin_id, amount, new_balance))
    # 加えられる方の新たな残高は
    for coin_id, amount in coins.items():
        new_balance = (to_balance[coin_id] if coin_id in to_balance else 0) + amount
        group_new_balance.append((to_group, coin_id, new_balance))
    # Databaseへ反映
    cur.executemany("""
        INSERT OR REPLACE INTO `balance` (`group`,`coin_id`,`amount`)
        VALUES (?,?,?)""", group_new_balance)
    logging.debug("Move account balance {}=>{} {} {}:{}"
                  .format(from_group, to_group, coins, hexlify(txhash).decode(), txindex))
    return txhash


def rollback_account_balance(txhash, cur, f_allow_minus=True):
    # txhashで行った残高移動を解除
    move_log = cur.execute("""
            SELECT `from_group`,`to_group`,`coin_id`,`amount` FROM `log` WHERE `hash`=?
            """, (txhash,)).fetchall()
    if len(move_log) == 0:
        raise BlockChainError('Not found log hash {}'.format(hexlify(txhash).decode()))

    movement = dict()
    for from_group, to_group, coin_id, amount in move_log:
        # 差し引かれた側なので加える
        if from_group in movement:
            movement[from_group][coin_id] += amount
        else:
            movement[from_group] = CoinObject(coin_id=coin_id, amount=amount)
        # 加えられた側なので引く
        if to_group in movement:
            movement[to_group][coin_id] -= amount
        else:
            movement[to_group] = CoinObject(coin_id=coin_id, amount=-1*amount)

    # 各ユーザーに残高をBaseにする
    for group in movement:
        cur.execute("""
            SELECT `coin_id`,`amount` FROM `balance` WHERE `group`=?
            """, (group,))
        for coin_id, amount in cur:
            coins = movement[group]
            if coin_id in coins:
                movement[group][coin_id] += amount
        if not f_allow_minus and movement[group].is_all_plus_amount():
            raise BlockChainError('Minus balance detected ({} {})'
                                  .format(group, movement[group]))

    # DataBaseに反映する
    group_new_balance = list()
    for group, coins in movement.items():
        for coin_id, amount in coins.items():
            group_new_balance.append((group, coin_id, amount))
    cur.executemany("""
        INSERT OR REPLACE INTO `balance` (`group`,`coin_id`,`amount`)
        VALUES (?,?,?)""", group_new_balance)
    cur.execute("""
         DELETE FROM `log` WHERE `hash`=?
        """, (txhash,))
    logging.debug("Rollback account balance {} {}".format(movement, hexlify(txhash).decode()))
