#!/user/env python3
# -*- coding: utf-8 -*-

from bc4py.config import V
import sqlite3
from contextlib import closing
import re
import logging
import time


def create_db(path, f_debug=False, f_on_memory=False, f_wal_mode=False):
    assert isinstance(path, str), 'You need initialize by set_database_path() before.'
    conn = sqlite3.connect(path, timeout=120)
    conn.execute("PRAGMA cache_size=5000")
    if f_on_memory:
        conn.isolation_level = None
        conn.execute("PRAGMA journal_mode=MEMORY")
        conn.isolation_level = 'IMMEDIATE'
    elif f_wal_mode:
        conn.isolation_level = None
        conn.execute("PRAGMA journal_mode=WAL")
        conn.isolation_level = 'IMMEDIATE'
    else:
        conn.isolation_level = 'IMMEDIATE'

    if f_debug:
        conn.set_trace_callback(sql_info)
    return conn


def sql_info(data):
    # db.set_trace_callback()に最適
    logging.debug("SQL: {} {}".format(round(time.time()-V.BLOCK_GENESIS_TIME, 4), re.sub(r"\s+", " ", data)))


def make_blockchain_db():
    with closing(create_db(V.DB_BLOCKCHAIN_PATH)) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS `block` (
            `hash` BINARY PRIMARY KEY NOT NULL,
            `height` INTEGER,
            `work` BINARY,
            `bin` BINARY,
            `flag` INTEGER,
            `time` INTEGER,
            `txs` BINARY
            )""")
        db.execute("""
            CREATE TABLE IF NOT EXISTS `tx` (
            `hash` BINARY PRIMARY KEY NOT NULL,
            `height` INTEGER,
            `bin` BINARY,
            `sign` BINARY,
            `time` INTEGER,
            `used_index` BINARY
            )""")
        db.execute("""
            CREATE TABLE IF NOT EXISTS `coins` (
            `id` INTEGER PRIMARY KEY,
            `hash` BINARY,
            `coin_id` INTEGER,
            `bin` BINARY
            )""")
        # C.TX_CREATE_CONTRACT Contractの新規登録
        db.execute("""
            CREATE TABLE IF NOT EXISTS `contract_info` (
            `address` TEXT PRIMARY KEY,
            `hash` BINARY
            )""")
        # storageはDictで差分Updateしてゆく
        # utxoはused_indexより計算、Storageは
        db.execute("""
            CREATE TABLE IF NOT EXISTS `contract_history` (
            `start_hash` BINARY PRIMARY KEY,
            `finish_hash` BINARY,
            `address` TEXT
            )""")
        # CREATE INDEX IF NOT EXISTS 'null_idx' ON `tx` (`height`) WHERE `height` IS NULL
        sql = """
            CREATE INDEX IF NOT EXISTS 'height_idx' ON `block` (`height`)
            CREATE INDEX IF NOT EXISTS 'coins_idx' ON `coins` (`coin_id`)
            CREATE INDEX IF NOT EXISTS 'hash_idx' ON `contract_info` (`hash`)
            CREATE INDEX IF NOT EXISTS 'address_idx' ON `contract_history` (`address`)
            """.split("\n")
        for sql_ in sql:
            if len(sql_) > 10:
                db.execute(sql_)
        db.commit()


def make_account_db():
    with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS `pool` (
            `id` INTEGER PRIMARY KEY NOT NULL,
            `group` TEXT,
            `sk` BINARY,
            `pk` BINARY,
            `ck` TEXT )""")
        db.execute("""
            CREATE TABLE IF NOT EXISTS `log` (
            `id` INTEGER PRIMARY KEY NOT NULL,
            `hash` BINARY,
            `direction` INTEGER,
            `index` INTEGER,
            `from_group` TEXT,
            `to_group` TEXT,
            `coin_id` INTEGER,
            `amount` INTEGER,
            `time` INTEGER
            )""")
        db.execute("""
            CREATE TABLE IF NOT EXISTS `utxo` (
            `used` INTEGER,
            `hash` BINARY,
            `index` INTEGER
            )""")
        db.execute("""
            CREATE TABLE IF NOT EXISTS `balance` (
            `group` TEXT,
            `coin_id` INTEGER,
            `amount` INTEGER )""")
        sql = """
            CREATE INDEX IF NOT EXISTS 'ck_idx' ON `pool` (`ck`)
            CREATE INDEX IF NOT EXISTS 'hash_idx' ON `log` (`hash`)
            CREATE UNIQUE INDEX IF NOT EXISTS 'utxo_idx' ON `utxo` (`hash`,`index`)
            CREATE INDEX IF NOT EXISTS 'used_idx' ON `utxo` (`used`)
            CREATE UNIQUE INDEX IF NOT EXISTS 'pair_idx' ON `balance` (`group`,`coin_id`)
        """.split("\n")
        for sql_ in sql:
            if len(sql_) > 10:
                db.execute(sql_)
        db.commit()
