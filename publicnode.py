#!/user/env python3
# -*- coding: utf-8 -*-

from bc4py.config import V
from bc4py.chain.block import pow_generator
from bc4py.utils import set_database_path, set_blockchain_params
from bc4py.user.mining import Mining
from bc4py.user.staking import Staking
from bc4py.user.boot import *
from bc4py.user.network import broadcast_check, mined_newblock, DirectCmd
from bc4py.user.api import create_rest_server
from bc4py.database.create import make_account_db, make_blockchain_db
from p2p_python.utils import setup_p2p_params
from p2p_python.client import PeerClient
from bc4py.for_debug import set_logger
from threading import Thread
import logging
import random


def work(port, sub_dir=None):
    # P2P network setup
    setup_p2p_params(network_ver=1000, p2p_port=port, sub_dir=sub_dir)
    pc = PeerClient()
    pc.event.addevent(cmd=DirectCmd.BEST_INFO, f=DirectCmd.best_info)
    pc.event.addevent(cmd=DirectCmd.BLOCK_BY_HASH, f=DirectCmd.block_by_hash)
    pc.event.addevent(cmd=DirectCmd.TX_BY_HASH, f=DirectCmd.tx_by_hash)
    pc.event.addevent(cmd=DirectCmd.UNCONFIRMED_TX, f=DirectCmd.unconfirmed_tx)
    pc.start()
    V.PC_OBJ = pc

    if pc.p2p.create_connection('tipnem.tk', 2000):
        logging.info("Connect!")

    # BlockChain setup
    set_database_path(sub_dir=sub_dir)
    make_account_db()
    make_blockchain_db()
    load_boot_file()
    set_blockchain_params()
    auto_save_boot_file()
    pow_generator.start()

    # BroadcastProcess setup
    pc.broadcast_check = broadcast_check

    # Update to newest blockchain
    vacuum_orphan_block()
    initialize_unconfirmed_tx()
    start_update_chain_data(f_wait_connection=True)

    # Mining/Staking setup
    mining = Mining()
    staking = Staking()
    mining.share_que(staking)
    V.F_MINING_POWER_SAVE = random.random() / 10 + 0.05
    Thread(target=mining.start, name='Mining', args=(1,), daemon=True).start()
    Thread(target=staking.start, name='Staking', daemon=True).start()
    Thread(target=mined_newblock, name='MinedBlock', args=(mining.que, pc), daemon=True).start()
    V.MINING_OBJ = mining
    V.STAKING_OBJ = staking
    V.F_DEBUG = True
    logging.info("Finished all initialize.")

    try:
        create_rest_server(f_local=True, port=port+1000)
    except KeyboardInterrupt:
        logging.debug("KeyboardInterrupt.")


if __name__ == '__main__':
    set_logger(level=logging.DEBUG)
    work(port=2000)
