from bc4py.config import C, V, P, BlockChainError
from bc4py.chain.block import Block
from bc4py.chain.tx import TX
from bc4py.chain.manage import insert_to_chain, global_chain_lock, check_tx, add_tx_as_new
from bc4py.database.create import create_db, closing
from bc4py.database.chain.read import max_block_height, read_best_block_on_chain, read_tx_object, read_tx_output
from bc4py.database.chain.flag import is_include_txhash, is_include_blockhash
from bc4py.user.utxo import add_utxo_user
from .directcmd import DirectCmd
import logging
import random
import collections
import time
from binascii import hexlify


def rebuild(chain_cur, account_cur):
    pass


def rebuild_chain_data():
    with closing(create_db(V.DB_BLOCKCHAIN_PATH, f_on_memory=True)) as chain_db:
        with closing(create_db(V.DB_ACCOUNT_PATH, f_on_memory=True)) as account_db:
            chain_cur = chain_db.cursor()
            account_cur = account_db.cursor()
            try:
                rebuild(chain_cur, account_cur)
                chain_db.commit()
                account_db.commit()
                logging.info("Rebuild blockchain success.")
            except BlockChainError as e:
                chain_db.rollback()
                account_db.rollback()
                logging.info("Rebuild blockchain failed.")
