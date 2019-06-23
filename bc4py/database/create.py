from bc4py.config import C, V
from bc4py.bip32 import BIP32_HARDEN
from contextlib import contextmanager
from logging import getLogger
from time import time
import sqlite3
import re
import os

log = getLogger('bc4py')


@contextmanager
def create_db(path, f_strict=False, f_debug=False):
    """
    account database connector

    f_strict:
        Phantom read sometimes occur on IMMEDIATE, avoid it by EXCLUSIVE.

    journal_mode: (Do not use OFF mode)
        DELETE: delete journal file at end of transaction
        TRUNCATE: set journal file size to 0 at the end of transaction
        PERSIST: disable headers at end of transaction
        MEMORY: save journal file on memory
        WAL: use a write-ahead log instead of a rollback journal

    synchronous:
        FULL: ensure that all content is safely written to the disk.
        EXTRA: provides additional durability if the commit is followed closely by a power loss.
        NORMAL: sync at the most critical moments, but less often than in FULL mode.
        OFF: without syncing as soon as it has handed data off to the operating system.
    """
    assert isinstance(path, str), 'You need initialize by set_database_path() before'
    conn = sqlite3.connect(path, timeout=120)

    # cashe size, default 2000
    if isinstance(C.SQLITE_CASHE_SIZE, int):
        conn.execute("PRAGMA cache_size = {}".format(C.SQLITE_CASHE_SIZE))

    # journal mode, default DELETE
    if isinstance(C.SQLITE_JOURNAL_MODE, str):
        conn.isolation_level = None
        conn.execute("PRAGMA journal_mode = {}".format(C.SQLITE_JOURNAL_MODE))
        conn.isolation_level = 'EXCLUSIVE' if f_strict else 'IMMEDIATE'
    else:
        conn.isolation_level = 'EXCLUSIVE' if f_strict else 'IMMEDIATE'

    # synchronous mode, default FULL
    if isinstance(C.SQLITE_SYNC_MODE, str):
        conn.execute("PRAGMA synchronous = {}".format(C.SQLITE_SYNC_MODE))

    if f_debug:
        conn.set_trace_callback(sql_info)

    # manage close process with contextmanager
    try:
        yield conn
    finally:
        conn.close()


def sql_info(data):
    # db.set_trace_callback()に最適
    log.debug("SQL: {} {}".format(round(time() - V.BLOCK_GENESIS_TIME, 4), re.sub(r"\s+", " ", data)))


def check_account_db():
    if os.path.exists(V.DB_ACCOUNT_PATH):
        if V.EXTENDED_KEY_OBJ is None or V.EXTENDED_KEY_OBJ.secret is None:
            log.debug("already exist wallet without check")
        else:
            with create_db(V.DB_ACCOUNT_PATH) as db:
                cur = db.cursor()
                d = cur.execute("SELECT `extended_key` FROM `account` WHERE `id`=0").fetchone()
                if d is None:
                    raise Exception('wallet is exist but not initialized')
            db_extended_key = d[0]
            stone_extended_key = V.EXTENDED_KEY_OBJ.child_key(0 + BIP32_HARDEN).extended_key(False)
            if db_extended_key == stone_extended_key:
                log.debug("already exist wallet, check success!")
            else:
                raise Exception('already exist wallet, check failed db={} stone={}'
                                .format(db_extended_key, stone_extended_key))
    else:
        with create_db(V.DB_ACCOUNT_PATH) as db:
            generate_wallet_db(db)
            db.commit()
        log.info("generate wallet success")
    # small update
    affect_new_change()


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
    if V.EXTENDED_KEY_OBJ is None or V.EXTENDED_KEY_OBJ.secret is None:
        raise Exception('Need to create root accounts first, do "import_keystone" before')
    accounts = [(
        account_id,
        V.EXTENDED_KEY_OBJ.child_key(account_id + BIP32_HARDEN).extended_key(False),
        C.account2name[account_id],
        "",
        0,
    ) for account_id in (C.ANT_UNKNOWN, C.ANT_STAKED)]
    db.executemany("INSERT OR IGNORE INTO `account` VALUES (?,?,?,?,?)", accounts)


def affect_new_change():
    """update differences when wallet format changed"""
    with create_db(V.DB_ACCOUNT_PATH) as db:
        cur = db.cursor()
        # rename @Mining to @Staked
        cur.execute('SELECT `id` FROM `account` WHERE `name`=?', ('@Mining',))
        uuid = cur.fetchone()
        if uuid is not None:
            uuid = uuid[0]
            cur.execute('UPDATE `account` SET `name`=? WHERE `id`=?', (C.account2name[C.ANT_STAKED], uuid,))
            db.commit()
            log.info("change user_name @Mining to @Staked")


def recreate_wallet_db(db):
    raise Exception('unimplemented')


__all__ = [
    "create_db",
    "sql_info",
    "check_account_db",
    "recreate_wallet_db",
]
