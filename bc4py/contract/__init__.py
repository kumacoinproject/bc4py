from bc4py.config import C, NewInfo
from bc4py.contract.watch import *
from bc4py.contract.em import *
from bc4py.database.contract import M_INIT, M_UPDATE
from bc4py.user.network.sendnew import *
from bc4py.user.txcreation.contract import create_conclude_tx
from threading import Thread, Lock
import logging
from io import StringIO


emulators = list()
f_running = False
lock = Lock()


class Emulate:
    def __init__(self, c_address):
        self.c_address = c_address
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


def execute(c_address, genesis_block, start_tx, c_method, c_args, f_debug=False):
    """ execute contract emulator """
    file = StringIO()
    gas_limit = 100000000 if f_debug else None
    is_success, result, emulate_gas, work_line = emulate(
        genesis_block=genesis_block, start_tx=start_tx, c_address=c_address,
        c_method=c_method, c_args=c_args, gas_limit=gas_limit, file=file)
    if is_success:
        logging.info('Success gas={} line={} result={}'.format(emulate_gas, work_line, result))
        if f_debug:
            logging.debug("#### Start log ####")
            for data in file.getvalue().split("\n"):
                logging.debug(data)
            logging.debug("#### Finish log ####")
    else:
        logging.error('Failed gas={} line={} result={} log={}'.format(
            emulate_gas, work_line, result, file.getvalue()))
    file.close()
    return result, emulate_gas


def broadcast(c_address, start_tx, emulate_gas, result, f_debug=False):
    """ broadcast conclude tx """
    if isinstance(result, tuple) and len(result) == 2:
        send_pairs, c_storage = result
    else:
        return
    # create conclude tx
    tx = create_conclude_tx(c_address=c_address, start_tx=start_tx,
                            send_pairs=send_pairs, c_storage=c_storage, emulate_gas=emulate_gas)
    # send tx
    if f_debug:
        logging.debug("Not broadcast, send_pairs={} c_storage={} tx={}"
                      .format(send_pairs, c_storage, tx.getinfo()))
    elif send_newtx(new_tx=tx):
        logging.info("Broadcast success {}".format(tx))
    else:
        logging.error("Failed broadcast, send_pairs={} c_storage={} tx={}"
                      .format(send_pairs, c_storage, tx.getinfo()))


def start_emulators(genesis_block, f_debug=False):
    def run():
        global f_running
        with lock:
            f_running = True
        logging.info("Start emulators debug={}".format(f_debug))
        while f_running:
            try:
                data = NewInfo.get(channel='emulator', timeout=1)
                if not isinstance(data, tuple) or len(data) != 3:
                    continue
                cmd, is_public, data_list = data
                if cmd == C_RequestConclude:
                    # c_transfer tx is confirmed, create conclude tx
                    _time, start_tx, related_list, c_address, c_method, c_args = data_list
                    for e in emulators:
                        if e.c_address != c_address:
                            continue
                        elif c_method == M_INIT:
                            # TODO:Not write function.
                            logging.warning("What work?")
                        # elif c_method == M_UPDATE:
                        #    pass
                        else:
                            result, emulate_gas = execute(
                                c_address=c_address, genesis_block=genesis_block, start_tx=start_tx,
                                c_method=c_method, c_args=c_args, f_debug=f_debug)
                            broadcast(c_address=c_address, start_tx=start_tx, emulate_gas=emulate_gas,
                                      result=result, f_debug=f_debug)

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
