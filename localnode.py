#!/user/env python3
# -*- coding: utf-8 -*-

from bc4py import __version__, __chain_version__, __message__, __logo__
from bc4py.config import C, V, P
from bc4py.utils import set_database_path, set_blockchain_params
# from bc4py.user.stratum import Stratum, start_stratum, close_stratum
from bc4py.user.generate import *
from bc4py.user.boot import *
from bc4py.user.network import *
from bc4py.user.api import create_rest_server
from bc4py.contract.emulator import start_emulators, Emulate
from bc4py.contract.emulator.watching import start_contract_watch
from bc4py.database.create import make_account_db
from bc4py.database.builder import builder
from bc4py.chain.workhash import start_work_hash, close_work_hash
from pooled_multiprocessing import cpu_num, add_pool_process
from p2p_python.utils import setup_p2p_params
from p2p_python.client import PeerClient
from bc4py.for_debug import set_logger, f_already_bind
from threading import Thread
import logging
import os


def copy_boot(port):
    if port == 2000:
        return
    else:
        original = os.path.join(os.path.split(V.DB_HOME_DIR)[0], '2000', 'boot.dat')
    destination = os.path.join(V.DB_HOME_DIR, 'boot.dat')
    if original == destination:
        return
    with open(original, mode='br') as ifp:
        with open(destination, mode='bw') as ofp:
            ofp.write(ifp.read())


def work(port, sub_dir):
    # BlockChain setup
    set_database_path(sub_dir=sub_dir)
    import_keystone(passphrase='hello python')
    builder.set_database_path()
    copy_boot(port)
    make_account_db()
    genesis_block, network_ver, connections = load_boot_file()
    logging.info("Start p2p network-ver{} .".format(network_ver))

    # P2P network setup
    setup_p2p_params(network_ver=network_ver, p2p_port=port, sub_dir=sub_dir)
    pc = PeerClient(f_local=True)
    pc.event.addevent(cmd=DirectCmd.BEST_INFO, f=DirectCmd.best_info)
    pc.event.addevent(cmd=DirectCmd.BLOCK_BY_HEIGHT, f=DirectCmd.block_by_height)
    pc.event.addevent(cmd=DirectCmd.BLOCK_BY_HASH, f=DirectCmd.block_by_hash)
    pc.event.addevent(cmd=DirectCmd.TX_BY_HASH, f=DirectCmd.tx_by_hash)
    pc.event.addevent(cmd=DirectCmd.UNCONFIRMED_TX, f=DirectCmd.unconfirmed_tx)
    pc.event.addevent(cmd=DirectCmd.BIG_BLOCKS, f=DirectCmd.big_blocks)
    pc.start()
    V.PC_OBJ = pc

    # for debug node
    if port != 2000 and pc.p2p.create_connection('127.0.0.1', 2000):
        logging.info("Connect!")
    else:
        pc.p2p.create_connection('127.0.0.1', 2001)

    # add pooled process
    add_pool_process(cpu_num)

    for host, port in connections:
        pc.p2p.create_connection(host, port)
    set_blockchain_params(genesis_block)

    # BroadcastProcess setup
    pc.broadcast_check = broadcast_check

    # Update to newest blockchain
    builder.init(genesis_block, batch_size=500)
    # builder.db.sync = False  # more fast
    sync_chain_loop()

    # Mining/Staking setup
    start_work_hash()
    # Debug.F_CONSTANT_DIFF = True
    # Debug.F_SHOW_DIFFICULTY = True
    # Debug.F_STICKY_TX_REJECTION = False  # for debug
    if port % 3 == 0:
        Generate(consensus=C.BLOCK_YES_POW, power_limit=0.01).start()
    if port % 3 == 1:
        Generate(consensus=C.BLOCK_HMQ_POW, power_limit=0.01).start()
    if port % 3 == 2:
        Generate(consensus=C.BLOCK_X11_POW, power_limit=0.01).start()
    Generate(consensus=C.BLOCK_POS, power_limit=0.3).start()
    # Contract watcher
    start_contract_watch()
    # Emulate(c_address='CJ4QZ7FDEH5J7B2O3OLPASBHAFEDP6I7UKI2YMKF')
    Emulate(c_address='CLBKXHOTXTLK3FENVTCH6YPM5MFZS4BNAXFYNWBD')
    start_emulators(genesis_block)
    # Stratum
    # Stratum(port=port+2000, consensus=C.BLOCK_HMQ_POW, first_difficulty=4)
    Thread(target=mined_newblock, name='GeneBlock', args=(output_que, pc)).start()
    logging.info("Finished all initialize.")

    try:
        # start_stratum(f_blocking=False)
        create_rest_server(f_local=True, port=port+1000, user='user', pwd='password')
        P.F_STOP = True
        builder.close()
        # close_stratum()
        pc.close()
        close_generate()
        close_work_hash()
    except KeyboardInterrupt:
        logging.debug("KeyboardInterrupt.")


def connection():
    port = 2000
    while True:
        if f_already_bind(port):
            port += 1
            continue
        set_logger(level=logging.DEBUG, prefix=port, f_file=bool(port == 2000), f_remove=True)
        logging.info("\n{}\n=====\n{}, chain-ver={}\n{}\n"
                     .format(__logo__, __version__, __chain_version__, __message__))
        work(port=port, sub_dir=str(port))
        break


if __name__ == '__main__':
    connection()
