#!/user/env python3
# -*- coding: utf-8 -*-

from bc4py.config import Debug
from bc4py.utils import set_database_path, set_blockchain_params
from bc4py.user.mining import Mining
from bc4py.user.staking import Staking
from bc4py.user.boot import *
from bc4py.user.network import broadcast_check, mined_newblock, DirectCmd, sync_chain_loop
from bc4py.user.api import create_rest_server
from bc4py.database.create import make_account_db
from bc4py.database.builder import builder
from p2p_python.utils import setup_p2p_params
from p2p_python.client import PeerClient
from bc4py.for_debug import set_logger
from threading import Thread
import logging
import random


def work(port, sub_dir=None):
    # BlockChain setup
    set_database_path(sub_dir=sub_dir)
    builder.set_database_path()
    make_account_db()
    genesis_block, network_ver, connections = load_boot_file()
    logging.info("Start p2p network-ver{} .".format(network_ver))

    # P2P network setup
    setup_p2p_params(network_ver=network_ver, p2p_port=port, sub_dir=sub_dir)
    pc = PeerClient()
    pc.event.addevent(cmd=DirectCmd.BEST_INFO, f=DirectCmd.best_info)
    pc.event.addevent(cmd=DirectCmd.BLOCK_BY_HEIGHT, f=DirectCmd.block_by_height)
    pc.event.addevent(cmd=DirectCmd.BLOCK_BY_HASH, f=DirectCmd.block_by_hash)
    pc.event.addevent(cmd=DirectCmd.TX_BY_HASH, f=DirectCmd.tx_by_hash)
    pc.event.addevent(cmd=DirectCmd.UNCONFIRMED_TX, f=DirectCmd.unconfirmed_tx)
    pc.start()
    V.PC_OBJ = pc

    if pc.p2p.create_connection('tipnem.tk', 2000):
        logging.info("Connect!")

    for host, port in connections:
        pc.p2p.create_connection(host, port)
    set_blockchain_params(genesis_block)

    # BroadcastProcess setup
    pc.broadcast_check = broadcast_check

    # Update to newest blockchain
    builder.init(genesis_block)
    sync_chain_loop()

    # Mining/Staking setup
    mining = Mining(genesis_block)
    staking = Staking(genesis_block)
    mining.share_que(staking)
    Debug.F_WS_FULL_ERROR_MSG = True
    Debug.F_MINING_POWER_SAVE = random.random() / 5 + 0.05
    # core = 1 if port <= 2001 else 0
    Thread(target=mining.start, name='Mining', args=(1,)).start()
    Thread(target=staking.start, name='Staking').start()
    Thread(target=mined_newblock, name='MinedBlock', args=(mining.que, pc)).start()
    V.MINING_OBJ = mining
    V.STAKING_OBJ = staking
    logging.info("Finished all initialize.")

    try:
        create_rest_server(f_local=True, port=port + 1000)
    except KeyboardInterrupt:
        logging.debug("KeyboardInterrupt.")


if __name__ == '__main__':
    set_logger(level=logging.DEBUG)
    work(port=2000)
