from bc4py.config import C, P, NewInfo, BlockChainError
from bc4py.contract.emulator.tools import *
from bc4py.contract.emulator.watching import *
from bc4py.database.builder import tx_builder
from bc4py.database.contract import *
from threading import Thread, Lock
import logging
from time import sleep, time
import bjson
from sys import version_info


emulators = list()
f_running = False
lock = Lock()


class Emulate:
    def __init__(self, c_address, f_claim_gas=True):
        self.c_address = c_address
        self.f_claim_gas = f_claim_gas
        for e in emulators:
            if c_address == e.c_address:
                raise Exception('Already registered c_address {}'.format(c_address))
        with lock:
            emulators.append(self)

    def __repr__(self):
        return "<Emulator {}>".format(self.c_address)

    def close(self):
        with lock:
            emulators.remove(self)


def start_emulators(genesis_block):
    """ start emulation listen, need close by close_emulators() """
    def run():
        global f_running
        with lock:
            f_running = True

        # wait for booting_mode finish
        while P.F_NOW_BOOTING:
            sleep(1)

        logging.info("Start emulators, check unconfirmed.")
        # TODO: check is this work reqiured?
        unconfirmed_data = list()
        for tx in sorted(tx_builder.unconfirmed.values(), key=lambda x: x.create_time):
            if tx.type != C.TX_CONCLUDE_CONTRACT:
                continue
            try:
                c_address, start_hash, c_storage = bjson.loads(tx.message)
                for em in emulators:
                    if c_address == em.c_address:
                        break
                else:
                    continue
                start_tx = tx_builder.get_tx(txhash=start_hash)
                c_address2, c_method, redeem_address, c_args = bjson.loads(start_tx.message)
                if c_address != c_address2:
                    continue
                is_public = False
                data_list = (time(), start_tx, 'dummy', c_address, c_method, redeem_address, c_args)
                data = (C_RequestConclude, is_public, data_list)
                unconfirmed_data.append(data)
            except Exception:
                logging.debug("Failed check unconfirmed ConcludeTX,", exc_info=True)

        logging.info("Start listening NewInfo, need to emulate {} txs.".format(len(unconfirmed_data)))
        while f_running:
            try:
                if len(unconfirmed_data) > 0:
                    data = unconfirmed_data.pop(0)
                else:
                    data = NewInfo.get(channel='emulator', timeout=1)
                if not isinstance(data, tuple) or len(data) != 3:
                    continue
                cmd, is_public, data_list = data
                if cmd == C_RequestConclude:
                    # c_transfer tx is confirmed, create conclude tx
                    _time, start_tx, related_list, c_address, c_method, redeem_address, c_args = data_list
                    for e in emulators:
                        if e.c_address != c_address:
                            continue
                        elif c_method == M_INIT:
                            logging.warning("No work on init.")
                        # elif c_method == M_UPDATE:
                        #    pass
                        else:
                            if e.f_claim_gas:
                                gas_limit = 0
                                for address, coin_id, amount in start_tx.outputs:
                                    if address == c_address and coin_id == 0:
                                        gas_limit += amount
                            else:
                                gas_limit = None  # No limit on gas consumption, turing-complete
                            result, emulate_gas = execute(
                                c_address=c_address, genesis_block=genesis_block, start_tx=start_tx, c_method=c_method,
                                redeem_address=redeem_address, c_args=c_args, gas_limit=gas_limit, f_show_log=True)
                            claim_emulate_gas = emulate_gas if e.f_claim_gas else 0
                            broadcast(c_address=c_address, start_tx=start_tx, redeem_address=redeem_address,
                                      emulate_gas=claim_emulate_gas, result=result, f_not_send=False)

                # elif cmd == C_Conclude:
                #    # sign already created conclude tx
                #    _time, tx, related_list, c_address, start_hash, c_storage = data_list
                else:
                    pass
            except NewInfo.empty:
                pass
            except BlockChainError:
                logging.warning("Emulator", exc_info=True)
            except Exception:
                logging.error("Emulator", exc_info=True)
    global f_running
    # version check, emulator require Python3.6 or more
    if version_info.major < 3 or version_info.minor < 6:
        raise Exception('Emulator require 3.6.0 or more.')
    Thread(target=run, name='Emulator', daemon=True).start()


def close_emulators():
    global f_running
    assert f_running is True
    with lock:
        f_running = False
        emulators.clear()
    logging.info("Close emulators.")


__all__ = [
    "Emulate",
    "start_emulators",
    "close_emulators",
]
