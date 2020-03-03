#!/user/env python3
# -*- coding: utf-8 -*-

from bc4py import __version__, __chain_version__, __message__, __logo__
from bc4py.config import C, V
from bc4py.utils import set_database_path, set_blockchain_params, check_already_started
from bc4py.exit import blocking_run
from bc4py.user.generate import *
from bc4py.user.boot import *
from bc4py.user.network import *
from bc4py.user.api import setup_rest_server
from bc4py.database.create import check_account_db
from bc4py.database.builder import chain_builder
from bc4py.chain.msgpack import default_hook, object_hook
from p2p_python.utils import setup_p2p_params
from p2p_python.server import Peer2Peer
from bc4py.for_debug import set_logger, f_already_bind
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


def setup_client(port, sub_dir):
    # BlockChain setup
    set_database_path(sub_dir=sub_dir)
    check_already_started()
    chain_builder.set_database_object()
    copy_boot(port)
    import_keystone(passphrase='hello python')
    loop.run_until_complete(check_account_db())
    genesis_block, genesis_params, network_ver, connections = load_boot_file()
    set_blockchain_params(genesis_block, genesis_params)
    logging.info("Start p2p network-ver{} .".format(network_ver))

    # P2P network setup
    setup_p2p_params(network_ver=network_ver, p2p_port=port,
                     p2p_accept=True, p2p_udp_accept=True, sub_dir=sub_dir)
    p2p = Peer2Peer(f_local=True, default_hook=default_hook, object_hook=object_hook)
    p2p.event.setup_events_from_class(DirectCmd)
    p2p.setup()
    V.P2P_OBJ = p2p
    return connections


async def setup_chain(port, connections):
    p2p = V.P2P_OBJ
    # for debug node
    if port != 2000 and await p2p.core.create_connection('127.0.0.1', 2000):
        logging.info("Connect!")
    else:
        await p2p.core.create_connection('127.0.0.1', 2001)

    # BroadcastProcess setup
    p2p.broadcast_check = broadcast_check

    # Update to newest blockchain
    if await chain_builder.init(V.GENESIS_BLOCK, batch_size=500):
        # only genesisBlock yoy have, try to import bootstrap.dat.gz
        await load_bootstrap_file()
    await sync_chain_loop()

    # Mining/Staking setup
    # Debug.F_CONSTANT_DIFF = True
    # Debug.F_SHOW_DIFFICULTY = True
    # Debug.F_STICKY_TX_REJECTION = False  # for debug
    if port == 2000:
        Generate(consensus=C.BLOCK_CAP_POS, power_limit=0.6)
    elif port % 3 == 0:
        Generate(consensus=C.BLOCK_YES_POW, power_limit=0.03)
    elif port % 3 == 1:
        Generate(consensus=C.BLOCK_X16S_POW, power_limit=0.03)
    elif port % 3 == 2:
        Generate(consensus=C.BLOCK_X11_POW, power_limit=0.03)
    Generate(consensus=C.BLOCK_COIN_POS, power_limit=0.3)
    asyncio.ensure_future(mined_newblock(mined_block_que))
    logging.info("finished all initialization")


def main():
    port = 2000
    while True:
        if f_already_bind(port):
            port += 1
            continue
        else:
            break
    connections = setup_client(port=port, sub_dir=str(port))
    loop.run_until_complete(setup_rest_server(port=port + 1000))
    loop.run_until_complete(setup_chain(port, connections))

    path = 'debug.2000.log' if port == 2000 else None
    set_logger(level=logging.DEBUG, path=path, f_remove=True)
    logging.info("\n{}\n=====\n{}, chain-ver={}\n{}\n"
                 .format(__logo__, __version__, __chain_version__, __message__))

    import aiomonitor
    aiomonitor.start_monitor(loop, port=port+2000, console_port=port+3000)
    logging.warning(f"aiomonitor working! use by console `nc 127.0.0.1 {port+2000}`")
    blocking_run()


if __name__ == '__main__':
    main()
