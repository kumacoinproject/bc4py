#!/user/env python3
# -*- coding: utf-8 -*-


"""

"""

from bc4py.utils import set_database_path, set_blockchain_params, make_pid_file, delete_pid_file
from bc4py.config import C, V, BlockChainError
from bc4py.database.create import create_db, closing, make_account_db, make_blockchain_db, sql_info
from bc4py.database.chain.read import read_blocks_by_height
from bc4py.chain.block import Block
from bc4py.chain.tx import TX
from p2p_python.utils import setup_p2p_params
from p2p_python.client import PeerClient, ClientCmd
import logging
import os
import queue
import bjson
from threading import Thread
from binascii import unhexlify
import time


def _debug(sql, path, explain=True):
    with closing(create_db(path)) as db:
        db.set_trace_callback(sql_info)
        cur = db.cursor()
        f = cur.execute(('explain query plan ' if explain else '') + sql)
        if explain:
            print(f.fetchone()[-1])
        else:
            c = 0
            for d in f.fetchall():
                print(c, ':', ', '.join(map(str, d)))
                c += 1


def debug_chain(sql, explain=True):
    _debug(sql=sql, path=V.DB_BLOCKCHAIN_PATH, explain=explain)


def debug_account(sql, explain=True):
    _debug(sql=sql, path=V.DB_ACCOUNT_PATH, explain=explain)


class BlockChain:
    f_stop = False
    f_finish = False
    f_running = False

    def __init__(self, command=None, port=5323, net_ver=5323):
        setup_p2p_params()
        self.pc = PeerClient()
        # database path 設定
        set_database_path()

        if command is None:
            # genesis block を読み込み
            logging.info("Load genesis block")
            set_blockchain_params()
        elif command == 'reindex':
            logging.info("Execute \"{}\"".format(command))
            if os.path.exists(V.DB_BLOCKCHAIN_PATH):
                os.remove(V.DB_BLOCKCHAIN_PATH)
        else:
            raise BlockChainError('Command() not found.'.format(command))
        # create table if not exist
        make_blockchain_db()
        make_account_db()

    def close(self):
        if not self.f_running:
            raise BlockChainError('Not running yet.')
        self.f_stop = True
        while not self.f_finish:
            time.sleep(1)
        self.f_stop = self.f_finish = self.f_running = False
        self.pc.p2p.close_server()
        delete_pid_file()
        logging.info("Close network module.")

    def start(self, f_server=True):
        make_pid_file()

        # Networkへのコネクト
        broadcast_que = self.pc.broadcast_que.create()
        direct_que = self.pc.direct_cmd_que.create()
        Thread(target=self.broadcast_loop, name='BroadcastLP', args=(broadcast_que,), daemon=True).start()
        Thread(target=self.directcmd_loop, name='DirectLP', args=(direct_que,), daemon=True).start()

        # Peer環境
        self.pc.broadcast_check = self.broadcast_check
        self.pc.start(f_server=f_server)

    def broadcast_check(self, pc, data):
        return True

    def broadcast_loop(self, broadcast_que):
        while not self.f_stop:
            try:
                client, item = broadcast_que.get(timeout=5)
            except queue.Empty:
                continue
