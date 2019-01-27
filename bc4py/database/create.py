#!/user/env python3
# -*- coding: utf-8 -*-

from bc4py.config import C, V
import sqlite3
from contextlib import closing
import re
from time import time
from logging import getLogger

log = getLogger('bc4py')


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
    log.debug("SQL: {} {}".format(round(time()-V.BLOCK_GENESIS_TIME, 4), re.sub(r"\s+", " ", data)))


def make_account_db():
    with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS `log` (
            `id` INTEGER PRIMARY KEY,
            `hash` BINARY,
            `index` INTEGER,
            `type` INTEGER NOT NULL,
            `user` INTEGER NOT NULL,
            `coin_id` INTEGER NOT NULL,
            `amount` INTEGER NOT NULL,
            `time` INTEGER NOT NULL
        )""")
        db.execute("""
            CREATE TABLE IF NOT EXISTS `account` (
            `id` INTEGER PRIMARY KEY,
            `name` TEXT UNIQUE NOT NULL,
            `description` TEXT NOT NULL,
            `time` INTEGER NOT NULL
        )""")
        db.execute("""
            CREATE TABLE IF NOT EXISTS `pool` (
            `id` INTEGER PRIMARY KEY,
            `sk` BINARY,
            `ck` TEXT UNIQUE NOT NULL,
            `user` INTEGER NOT NULL,
            `is_inner` INTEGER,
            `index` INTEGER,
            `time` INTEGER NOT NULL
        )""")
        # index
        sql = [
            "CREATE INDEX IF NOT EXISTS 'hash_idx' ON `log` (`hash`,`index`)",
            "CREATE INDEX IF NOT EXISTS 'name_idx' ON `account` (`name`)",
            "CREATE INDEX IF NOT EXISTS 'ck_idx' ON `pool` (`ck`)",
            "CREATE INDEX IF NOT EXISTS 'user_idx' ON `pool` (`user`)"]
        for sql_ in sql:
            db.execute(sql_)
        # default account
        accounts = [
            (C.ANT_RESERVED, C.account2name[C.ANT_RESERVED], "Reserved and update to other accounts", 0),
            (C.ANT_UNKNOWN, C.account2name[C.ANT_UNKNOWN], "Not user binding address, for change", 0),
            (C.ANT_OUTSIDE, C.account2name[C.ANT_OUTSIDE], "Address used for movement with outside", 0),
            (C.ANT_VALIDATOR, C.account2name[C.ANT_VALIDATOR], "Validator bind address", 0),
            (C.ANT_CONTRACT, C.account2name[C.ANT_CONTRACT], "Contract bind address", 0)]
        db.executemany("INSERT OR IGNORE INTO `account` VALUES (?,?,?,?)", accounts)
        db.commit()


# add last_index to account
# "ALTER TABLE `account` ADD COLUMN 'last_index' INTEGER NOT NULL AFTER `description`"
