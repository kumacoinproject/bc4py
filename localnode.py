#!/user/env python3
# -*- coding: utf-8 -*-

from bc4py import __version__, __chain_version__, __message__, __logo__
from bc4py.config import C, V, P
from bc4py.utils import set_database_path, set_blockchain_params, check_already_started
from bc4py.user.generate import *
from bc4py.user.boot import *
from bc4py.user.network import *
from bc4py.user.api import create_rest_server
from bc4py.database.create import check_account_db
from bc4py.database.builder import chain_builder
from bc4py.chain.msgpack import default_hook, object_hook
from p2p_python.utils import setup_p2p_params
from p2p_python.server import Peer2Peer
from bc4py.for_debug import set_logger, f_already_bind
from threading import Thread
import asyncio
import logging
import os


loop = asyncio.get_event_loop()


def copy_boot(port):
    if port == 2000:
        return
    else:
        original = os.path.join(os.path.split(V.DB_HOME_DIR)[0], '2000', 'boot.json')
    destination = os.path.join(V.DB_HOME_DIR, 'boot.json')
    if original == destination:
        return
    with open(original, mode='br') as ifp:
        with open(destination, mode='bw') as ofp:
            ofp.write(ifp.read())


def work(port, sub_dir):
    # BlockChain setup
    set_database_path(sub_dir=sub_dir)
    check_already_started()
    chain_builder.set_database_path()
    copy_boot(port)
    import_keystone(passphrase='hello python')
    check_account_db()
    genesis_block, genesis_params, network_ver, connections = load_boot_file()
    logging.info("Start p2p network-ver{} .".format(network_ver))

    # P2P network setup
    setup_p2p_params(network_ver=network_ver, p2p_port=port, sub_dir=sub_dir)
    p2p = Peer2Peer(f_local=True, default_hook=default_hook, object_hook=object_hook)
    p2p.event.addevent(cmd=DirectCmd.BEST_INFO, f=DirectCmd.best_info)
    p2p.event.addevent(cmd=DirectCmd.BLOCK_BY_HEIGHT, f=DirectCmd.block_by_height)
    p2p.event.addevent(cmd=DirectCmd.BLOCK_BY_HASH, f=DirectCmd.block_by_hash)
    p2p.event.addevent(cmd=DirectCmd.TX_BY_HASH, f=DirectCmd.tx_by_hash)
    p2p.event.addevent(cmd=DirectCmd.UNCONFIRMED_TX, f=DirectCmd.unconfirmed_tx)
    p2p.event.addevent(cmd=DirectCmd.BIG_BLOCKS, f=DirectCmd.big_blocks)
    p2p.start()
    V.P2P_OBJ = p2p

    # for debug node
    if port != 2000 and p2p.core.create_connection('127.0.0.1', 2000):
        logging.info("Connect!")
    else:
        p2p.core.create_connection('127.0.0.1', 2001)

    for host, port in connections:
        p2p.core.create_connection(host, port)
    set_blockchain_params(genesis_block, genesis_params)

    # BroadcastProcess setup
    p2p.broadcast_check = broadcast_check

    # Update to newest blockchain
    chain_builder.db.sync = False
    if chain_builder.init(genesis_block, batch_size=500):
        # only genesisBlock yoy have, try to import bootstrap.dat.gz
        load_bootstrap_file()
    sync_chain_loop()

    # Mining/Staking setup
    # Debug.F_CONSTANT_DIFF = True
    # Debug.F_SHOW_DIFFICULTY = True
    # Debug.F_STICKY_TX_REJECTION = False  # for debug
    if port == 2000:
        Generate(consensus=C.BLOCK_CAP_POS, power_limit=0.6, path='E:\\plots').start()
    elif port % 3 == 0:
        Generate(consensus=C.BLOCK_YES_POW, power_limit=0.03).start()
    elif port % 3 == 1:
        Generate(consensus=C.BLOCK_X16S_POW, power_limit=0.03).start()
    elif port % 3 == 2:
        Generate(consensus=C.BLOCK_X11_POW, power_limit=0.03).start()
    Generate(consensus=C.BLOCK_COIN_POS, power_limit=0.3).start()
    Thread(target=mined_newblock, name='GeneBlock', args=(output_que,)).start()
    logging.info("Finished all initialize.")

    try:
        create_rest_server(user='user', pwd='password', port=port+1000)
        loop.run_forever()
    except Exception as e:
        logging.debug(e)
    P.F_STOP = True
    chain_builder.close()
    p2p.close()


def connection():
    port = 2000
    while True:
        if f_already_bind(port):
            port += 1
            continue
        path = 'debug.2000.log' if port == 2000 else None
        set_logger(level=logging.DEBUG, path=path, f_remove=True)
        logging.info("\n{}\n=====\n{}, chain-ver={}\n{}\n"
                     .format(__logo__, __version__, __chain_version__, __message__))
        work(port=port, sub_dir=str(port))
        break


if __name__ == '__main__':
    connection()
