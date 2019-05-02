from bc4py.config import C, V
from bc4py.bip32 import BIP32_HARDEN
from contextlib import closing
from time import time
from logging import getLogger
import sqlite3
import re
import os

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
    log.debug("SQL: {} {}".format(round(time() - V.BLOCK_GENESIS_TIME, 4), re.sub(r"\s+", " ", data)))


def check_account_db():
    if os.path.exists(V.DB_ACCOUNT_PATH):
        log.debug("already exist wallet path=\"{}\"".format(V.DB_ACCOUNT_PATH))
    else:
        with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
            generate_wallet_db(db)
            db.commit()
        log.info("generate wallet success")


def generate_wallet_db(db):
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
                `extended_key` TEXT NOT NULL,
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
        "CREATE INDEX IF NOT EXISTS 'user_idx' ON `pool` (`user`)"
    ]
    for s in sql:
        db.execute(s)
    # default account
    if V.BIP32_SECRET_OBJ is None or V.BIP32_SECRET_OBJ.secret is None:
        raise Exception('Need to create root accounts first, do "import_keystone" before')
    accounts = [(
        account_id,
        V.BIP32_SECRET_OBJ.child_key(account_id + BIP32_HARDEN).extended_key(False),
        C.account2name[account_id],
        "",
        0,
    ) for account_id in (C.ANT_UNKNOWN, C.ANT_VALIDATOR, C.ANT_CONTRACT, C.ANT_MINING)]
    db.executemany("INSERT OR IGNORE INTO `account` VALUES (?,?,?,?,?)", accounts)


def recreate_wallet_db(db):
    pass


__all__ = [
    "closing",
    "create_db",
    "sql_info",
    "check_account_db",
]
