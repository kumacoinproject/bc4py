from bc4py.config import C, P, stream, BlockChainError
from bc4py.contract.emulator.tools import *
from bc4py.contract.emulator.watching import *
from bc4py.database.builder import tx_builder
from bc4py.database.contract import *
from threading import Thread, Lock
from queue import Queue, Empty
from time import sleep
from sys import version_info
from logging import getLogger

log = getLogger('bc4py')

emulators = list()
lock = Lock()


class Emulate(object):

    def __init__(self, c_address, f_claim_gas=True):
        self.c_address = c_address
        self.f_claim_gas = f_claim_gas
        self.f_close = False
        self.que = Queue()
        for e in emulators:
            if c_address == e.c_address:
                raise Exception('Already registered c_address {}'.format(c_address))
        assert not lock.locked(), 'Already start emulator.'
        emulators.append(self)

    def __repr__(self):
        return "<Emulator {}>".format(self.c_address)

    def close(self):
        self.f_close = True
        emulators.remove(self)


def on_next(data):
    if not isinstance(data, tuple) or len(data) != 3:
        return
    for em in emulators:
        em.que.put(data)


def loop_emulator(index: int, em: Emulate):
    # wait for booting_mode finish
    if P.F_NOW_BOOTING:
        log.debug("waiting for booting finish.")
    while P.F_NOW_BOOTING:
        sleep(1)
    log.info("Start emulator {}".format(em))
    waiting_start_tx = None
    waiting_conclude_hash = None
    while not (P.F_STOP or em.f_close):
        try:
            cmd, is_public, data_list = em.que.get(timeout=1)
            if cmd == C_RequestConclude:
                # c_transfer tx is confirmed, create conclude tx
                _time, start_tx, related_list, c_address, c_method, redeem_address, c_args = data_list
                if em.c_address != c_address:
                    continue
                if waiting_start_tx and waiting_conclude_hash:
                    log.info("Wait for StartTX confirmed {}".format(waiting_start_tx))
                    while True:
                        if waiting_conclude_hash in tx_builder.chained_tx:
                            log.debug("Confirmed waiting StartTX(to chained)")
                            break  # confirmed!
                        elif waiting_conclude_hash in tx_builder.unconfirmed:
                            log.debug("Confirmed waiting StartTX(to unconfirmed)")
                            break  # put unconfirmed!
                        elif waiting_conclude_hash in tx_builder.pre_unconfirmed:
                            log.debug("Waiting before start_tx confirmed...")
                            sleep(5)
                        else:
                            # check another ConcludeTX confirmed/unconfirmed?
                            check_conclude_hash = get_conclude_hash_from_start(
                                c_address=c_address, start_hash=waiting_start_tx.hash)
                            if check_conclude_hash is None:
                                log.debug("Not confirmed waiting StartTX? ignore.")
                                break  # unconfirmed? next contract.
                            else:
                                log.debug("Another ConcludeTX is confirmed? next. ")
                                break
                    # reset waiting info
                    waiting_start_tx = None
                    waiting_conclude_hash = None
                # execute/broadcast
                if c_method == M_INIT:
                    log.warning("No work on init.")
                else:
                    if em.f_claim_gas:
                        gas_limit = 0
                        for address, coin_id, amount in start_tx.outputs:
                            if address == c_address and coin_id == 0:
                                gas_limit += amount
                    else:
                        gas_limit = None  # No limit on gas consumption, turing-complete
                    result, emulate_gas = execute(
                        c_address=c_address,
                        start_tx=start_tx,
                        c_method=c_method,
                        redeem_address=redeem_address,
                        c_args=c_args,
                        gas_limit=gas_limit,
                        f_show_log=True)
                    claim_emulate_gas = emulate_gas if em.f_claim_gas else 0
                    waiting_conclude_hash = broadcast(
                        c_address=c_address,
                        start_tx=start_tx,
                        redeem_address=redeem_address,
                        emulate_gas=claim_emulate_gas,
                        result=result,
                        f_not_send=False)
                    waiting_start_tx = start_tx

            # elif cmd == C_Conclude:
            #    # sign already created conclude tx
            #    _time, tx, related_list, c_address, start_hash, c_storage = data_list

            else:
                pass
        except Empty:
            pass
        except BlockChainError:
            log.warning("Emulator", exc_info=True)
        except Exception:
            log.error("Emulator", exc_info=True)
    log.debug("Close emulator listen {}".format(em))


def start_emulators():
    """ start emulation listen, need close by close_emulators() """
    # version check, emulator require Python3.6 or more
    if version_info.major < 3 or version_info.minor < 6:
        raise Exception('Emulator require 3.6.0 or more.')
    assert not lock.locked(), 'Already started emulator.'
    for index, em in enumerate(emulators):
        Thread(target=loop_emulator, name='Emulator{}'.format(index), args=(index, em), daemon=True).start()
    stream.subscribe(on_next=on_next, on_error=log.error)
    lock.acquire()


__all__ = [
    "Emulate",
    "start_emulators",
]
