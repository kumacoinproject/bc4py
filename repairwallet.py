#!/user/env python3
# -*- coding: utf-8 -*-

from bc4py import __version__, __chain_version__, __message__, __logo__
from bc4py.config import C, V, P
from bc4py.utils import set_database_path, set_blockchain_params, check_already_started
from bc4py.user.tools import repair_wallet
from bc4py.user.boot import *
from bc4py.user.network import *
from bc4py.database.create import check_account_db
from bc4py.database.builder import chain_builder
from bc4py.chain.msgpack import default_hook, object_hook
from p2p_python.utils import setup_p2p_params
from p2p_python.server import Peer2Peer
from bc4py.for_debug import set_logger
import logging
import asyncio


loop = asyncio.get_event_loop()


def work(port, sub_dir=None):
    # BlockChain setup
    set_database_path(sub_dir=sub_dir)
    check_already_started()
    chain_builder.set_database_object()
    import_keystone(passphrase='hello python')
    loop.run_until_complete(check_account_db())
    genesis_block, genesis_params, network_ver, connections = load_boot_file()
    set_blockchain_params(genesis_block, genesis_params)
    logging.info("Start p2p network-ver{} .".format(network_ver))

    # P2P network setup
    setup_p2p_params(network_ver=network_ver, p2p_port=port, sub_dir=sub_dir)
    p2p = Peer2Peer(default_hook=default_hook, object_hook=object_hook)
    p2p.event.setup_events_from_class(DirectCmd)
    p2p.setup()
    V.P2P_OBJ = p2p
    loop.run_until_complete(setup_chain(p2p, connections))


async def setup_chain(p2p, connections):
    if await p2p.core.create_connection('tipnem.tk', 2000):
        logging.info("1Connect!")
    elif await p2p.core.create_connection('nekopeg.tk', 2000):
        logging.info("2Connect!")

    for host, port in connections:
        await p2p.core.create_connection(host, port)

    # BroadcastProcess setup
    p2p.broadcast_check = broadcast_check

    # Update to newest blockchain
    if await chain_builder.init(V.GENESIS_BLOCK, batch_size=500):
        # only genesisBlock yoy have, try to import bootstrap.dat.gz
        await load_bootstrap_file()
    await sync_chain_loop()
    logging.info("Finished all initialize.")

    while P.F_NOW_BOOTING:
        await asyncio.sleep(5)

    # repair
    await repair_wallet()

    # close
    P.F_STOP = True
    await chain_builder.close()
    p2p.close()
    logging.info("Finish repair wallet.")


if __name__ == '__main__':
    set_logger(level=logging.DEBUG, path='debug.repair.log', f_remove=True)
    logging.info("\n{}\n====\n{}, chain-ver={}\n{}\n"
                 .format(__logo__, __version__, __chain_version__, __message__))
    work(port=2000)
