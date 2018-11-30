from bc4py.config import C, NewInfo
from bc4py.chain import TX
from bc4py.contract.watch import *
from bc4py.contract.em import *
from bc4py.user.network.sendnew import *
from threading import Thread
import logging
from io import StringIO


emulators = list()
f_running = False


class Emulate:
    def __init__(self, c_address):
        self.c_address = c_address
        for e in emulators:
            if c_address == e.c_address:
                raise Exception('Already registered c_address {}'.format(c_address))
        emulators.append(self)

    def __repr__(self):
        return "<Emulator {}>".format(self.c_address)

    def close(self):
        emulators.remove(self)

    def emulate(self, start_tx, c_method, c_args, f_debug=False):
        file = StringIO()
        gas_limit = 100000000 if f_debug else None
        is_success, result, total_gas, work_line = emulate(
            start_tx=start_tx, c_address=self.c_address, c_method=c_method,
            c_args=c_args, gas_limit=gas_limit, file=file)
        if is_success:
            logging.info('Success gas={} line={} result={}'.format(
                total_gas, work_line, result))
        else:
            logging.error('Failed gas={} line={} result={} log={}'.format(
                total_gas, work_line, result, file.getvalue()))
        file.close()
        if isinstance(result, TX) and result.type == C.TX_CONCLUDE_CONTRACT:
            if f_debug:
                logging.debug("Not broadcast, {}".format(result.getinfo()))
            elif send_newtx(new_tx=result):
                logging.info("Success {}".format(result))
            else:
                logging.error("Failed broadcast {}".format(result.getinfo()))
        else:
            return result


def start_emulators():
    def run():
        global f_running
        f_running = True
        logging.info("Start emulators.")
        while f_running:
            try:
                data = NewInfo.get(channel='emulator', timeout=1)
                if not isinstance(data, tuple) and len(data) != 3:
                    continue
                cmd, is_public, data_list = data
                if cmd == C_RequestConclude:
                    # c_transfer tx is confirmed, create conclude tx
                    _time, start_tx, related_list, c_address, c_method, c_args = data_list
                    for e in emulators:
                        if e.c_address != c_address:
                            continue
                        e.emulate(start_tx, c_method, c_args, f_debug=False)

                # elif cmd == C_Conclude:
                #    # sign already created conclude tx
                #    _time, tx, related_list, c_address, start_hash, c_storage = data_list
                else:
                    pass
            except NewInfo.empty:
                pass
            except Exception:
                logging.error("Emulator", exc_info=True)
    global f_running
    Thread(target=run, name='Emulator', daemon=True).start()


def close_emulators():
    global f_running
    assert f_running is True
    f_running = False
    emulators.clear()
    logging.info("Close emulators.")


__all__ = [
    "Emulate",
    "start_emulators",
    "close_emulators",
]
