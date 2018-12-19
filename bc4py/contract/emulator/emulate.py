from bc4py.config import C, P, NewInfo, BlockChainError
from bc4py.contract.emulator.tools import *
from bc4py.contract.emulator.watching import *
from bc4py.database.contract import *
from threading import Thread, Lock
import logging
from time import sleep
from sys import version_info


emulators = list()
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
        # wait for booting_mode finish
        logging.debug("waiting for BootingMode finish.")
        while P.F_NOW_BOOTING:
            sleep(1)

        logging.info("Start emulator.")
        while not P.F_STOP:
            try:
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

                elif cmd == C_FinishConclude:
                    pass  # TODO: close 処理
                else:
                    pass
            except NewInfo.empty:
                pass
            except BlockChainError:
                logging.warning("Emulator", exc_info=True)
            except Exception:
                logging.error("Emulator", exc_info=True)
        logging.debug("Close emulator listen.")
    # version check, emulator require Python3.6 or more
    if version_info.major < 3 or version_info.minor < 6:
        raise Exception('Emulator require 3.6.0 or more.')
    Thread(target=run, name='Emulator', daemon=True).start()


__all__ = [
    "Emulate",
    "start_emulators",
]
