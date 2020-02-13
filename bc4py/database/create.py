from bc4py.config import C, V
from bc4py.bip32 import BIP32_HARDEN
from aiocontext import async_contextmanager
from aiosqlite import connect, Connection, Cursor
from logging import getLogger, INFO
from time import time
import re
import os

log = getLogger('bc4py')
getLogger('aiosqlite').setLevel(INFO)


@async_contextmanager
async def create_db(path, strict=False) -> Connection:
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
    conn = await connect(path, timeout=120.0)

    # cache size, default 2000
    await conn.execute("PRAGMA cache_size = %d" % C.SQLITE_CACHE_SIZE)

    # journal mode
    await conn.execute("PRAGMA journal_mode = %s" % C.SQLITE_JOURNAL_MODE)

    # isolation level
    conn.isolation_level = 'EXCLUSIVE' if strict else 'IMMEDIATE'

    # synchronous mode
    await conn.execute("PRAGMA synchronous = %s" % C.SQLITE_SYNC_MODE)

    # manage close process with contextmanager
    try:
        yield conn
    finally:
        await conn.close()


def sql_info(data):
    # db.set_trace_callback()に最適
    log.debug("SQL: {} {}".format(round(time() - V.BLOCK_GENESIS_TIME, 4), re.sub(r"\s+", " ", data)))


async def check_account_db():
    if os.path.exists(V.DB_ACCOUNT_PATH):
        if V.EXTENDED_KEY_OBJ is None or V.EXTENDED_KEY_OBJ.secret is None:
            log.debug("already exist wallet without check")
        else:
            async with create_db(V.DB_ACCOUNT_PATH) as db:
                cur = await db.cursor()
                await cur.execute("SELECT `extended_key` FROM `account` WHERE `id`=0")
                data = await cur.fetchone()
                if data is None:
                    raise Exception('wallet is exist but not initialized')
            db_extended_key = data[0]
            stone_extended_key = V.EXTENDED_KEY_OBJ.child_key(0 + BIP32_HARDEN).extended_key(False)
            if db_extended_key == stone_extended_key:
                log.debug("already exist wallet, check success!")
            else:
                raise Exception('already exist wallet, check failed db={} stone={}'
                                .format(db_extended_key, stone_extended_key))
        # small update
        await affect_new_change()
    else:
        async with create_db(V.DB_ACCOUNT_PATH) as db:
            cur = await db.cursor()
            await generate_wallet_db(cur)
            await db.commit()
        log.info("generate wallet success")


async def generate_wallet_db(cur: Cursor):
    await cur.execute("""
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
    await cur.execute("""
    CREATE TABLE IF NOT EXISTS `account` (
    `id` INTEGER PRIMARY KEY,
    `extended_key` TEXT NOT NULL,
    `name` TEXT UNIQUE NOT NULL,
    `description` TEXT NOT NULL,
    `time` INTEGER NOT NULL
    )""")
    await cur.execute("""
    CREATE TABLE IF NOT EXISTS `pool` (
    `id` INTEGER PRIMARY KEY,
    `sk` BINARY,
    `ck` BLOB UNIQUE NOT NULL,
    `user` INTEGER NOT NULL,
    `is_inner` INTEGER,
    `index` INTEGER,
    `is_used` BINARY,
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
        await cur.execute(s)
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
    await cur.executemany("INSERT OR IGNORE INTO `account` VALUES (?,?,?,?,?)", accounts)


async def affect_new_change():
    """update differences when wallet format changed"""
    async with create_db(V.DB_ACCOUNT_PATH) as db:
        cur = await db.cursor()
        # rename @Mining to @Staked
        await cur.execute('SELECT `id` FROM `account` WHERE `name`=?', ('@Mining',))
        uuid = await cur.fetchone()
        if uuid is not None:
            uuid = uuid[0]
            await cur.execute('UPDATE `account` SET `name`=? WHERE `id`=?', (C.account2name[C.ANT_STAKED], uuid,))
            await db.commit()
            log.info("change user_name @Mining to @Staked")

        # addr format TEXT to BLOB
        await cur.execute("SELECT `ck` FROM `pool` LIMIT 1")
        sample = await cur.fetchone()
        if sample is not None and isinstance(sample[0], str):
            from bc4py_extension import PyAddress
            await cur.execute("SELECT * FROM `pool`")
            data_list = await cur.fetchall()
            await cur.execute("DROP TABLE `pool`")
            await generate_wallet_db(cur)
            for data in data_list:
                addr: PyAddress = PyAddress.from_string(data[2])
                await cur.execute("INSERT INTO `pool` VALUES (?,?,?,?,?,?,?)",
                                  data[:2] + (addr.binary(),) + data[3:])
            await db.commit()
            log.info("change address format TEXT to BLOB")

        # add is_used column
        need_fix = True
        await cur.execute("PRAGMA table_info(`pool`)")
        for data_list in await cur.fetchall():
            if 'is_used' in data_list[1]:
                need_fix = False
        if need_fix:
            await cur.execute("ALTER TABLE `pool` RENAME TO `pool_old`")
            await generate_wallet_db(cur)  # generate `pool`
            await cur.execute("SELECT * FROM `pool_old`")
            for data_list in await cur.fetchall():
                assert len(data_list) == 7
                await cur.execute("INSERT INTO `pool` VALUES (?,?,?,?,?,?,?,?)",
                                  (*data_list[:6], None, *data_list[6:]))
            await cur.execute("DROP TABLE `pool_old`")
            await db.commit()
            log.info("add `is_used` column to `pool` table")


async def recreate_wallet_db(db):
    raise NotImplemented


__all__ = [
    "create_db",
    "sql_info",
    "check_account_db",
    "recreate_wallet_db",
]
