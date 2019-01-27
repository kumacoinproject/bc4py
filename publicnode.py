#!/user/env python3
# -*- coding: utf-8 -*-

from bc4py import __version__, __chain_version__, __message__, __logo__
from bc4py.config import C, V, P
from bc4py.utils import set_database_path, set_blockchain_params
from bc4py.user.generate import *
from bc4py.user.boot import *
from bc4py.user.network import *
from bc4py.user.api import create_rest_server
from bc4py.database.create import make_account_db
from bc4py.database.builder import builder
from bc4py.chain.msgpack import default_hook, object_hook
from p2p_python.utils import setup_p2p_params
from p2p_python.client import PeerClient
from bc4py.for_debug import set_logger
from threading import Thread
import logging


def work(port, sub_dir=None):
    # BlockChain setup
    set_database_path(sub_dir=sub_dir)
    builder.set_database_path()
    make_account_db()
    import_keystone(passphrase='hello python')
    genesis_block, network_ver, connections = load_boot_file()
    logging.info("Start p2p network-ver{} .".format(network_ver))

    # P2P network setup
    setup_p2p_params(network_ver=network_ver, p2p_port=port, sub_dir=sub_dir)
    pc = PeerClient(default_hook=default_hook, object_hook=object_hook)
    pc.event.addevent(cmd=DirectCmd.BEST_INFO, f=DirectCmd.best_info)
    pc.event.addevent(cmd=DirectCmd.BLOCK_BY_HEIGHT, f=DirectCmd.block_by_height)
    pc.event.addevent(cmd=DirectCmd.BLOCK_BY_HASH, f=DirectCmd.block_by_hash)
    pc.event.addevent(cmd=DirectCmd.TX_BY_HASH, f=DirectCmd.tx_by_hash)
    pc.event.addevent(cmd=DirectCmd.UNCONFIRMED_TX, f=DirectCmd.unconfirmed_tx)
    pc.event.addevent(cmd=DirectCmd.BIG_BLOCKS, f=DirectCmd.big_blocks)
    pc.start()
    V.PC_OBJ = pc

    if pc.p2p.create_connection('tipnem.tk', 2000):
        logging.info("1Connect!")
    elif pc.p2p.create_connection('nekopeg.tk', 2000):
        logging.info("2Connect!")

    for host, port in connections:
        pc.p2p.create_connection(host, port)
    set_blockchain_params(genesis_block)

    # BroadcastProcess setup
    pc.broadcast_check = broadcast_check

    # Update to newest blockchain
    builder.db.sync = False
    if builder.init(genesis_block, batch_size=500):
        # only genesisBlock yoy have, try to import bootstrap.dat
        log = logging.getLogger('bc4py')
        old_level = log.level
        log.setLevel(logging.WARNING)
        load_bootstrap_file()
        log.setLevel(old_level)
    sync_chain_loop()

    # Mining/Staking setup
    # Debug.F_CONSTANT_DIFF = True
    # Debug.F_SHOW_DIFFICULTY = True
    # Debug.F_STICKY_TX_REJECTION = False  # for debug
    Generate(consensus=C.BLOCK_YES_POW, power_limit=0.1).start()
    Generate(consensus=C.BLOCK_X16R_POW, power_limit=0.1).start()
    Generate(consensus=C.BLOCK_X11_POW, power_limit=0.1).start()
    Generate(consensus=C.BLOCK_POS, power_limit=0.3).start()
    Thread(target=mined_newblock, name='GeneBlock', args=(output_que, pc)).start()
    logging.info("Finished all initialize.")

    try:
        create_rest_server(f_local=False, user='user', pwd='password', port=port+1000)
        if P.F_NOW_BOOTING is False:
            create_bootstrap_file()
        P.F_STOP = True
        builder.close()
        pc.close()
        close_generate()
    except KeyboardInterrupt:
        logging.debug("KeyboardInterrupt.")


if __name__ == '__main__':
    set_logger(level=logging.DEBUG, f_file=True, f_remove=True)
    logging.info("\n{}\n====\n{}, chain-ver={}\n{}\n"
                 .format(__logo__, __version__, __chain_version__, __message__))
    work(port=2000)
