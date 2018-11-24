from bc4py.config import P, NewInfo
from bc4py.chain import Block, TX
from bc4py.contract.watch.checdata import *
import logging
from threading import Thread


def start_contract_watch():
    assert P.F_WATCH_CONTRACT is False
    P.F_WATCH_CONTRACT = True
    Thread(target=loop, name='Watch', daemon=True).start()


def loop():
    logging.info("Watching contract start.")
    while not P.F_STOP and P.F_WATCH_CONTRACT:
        try:
            obj = NewInfo.get(channel='watch contract', timeout=2)
            if isinstance(obj, TX):
                check_new_tx(tx=obj)
            elif isinstance(obj, Block):
                check_new_block(block=obj)
            else:
                pass
        except NewInfo.empty:
            pass
        except CheckWatchError as e:
            logging.error(e)
        except Exception as e:
            logging.error(e, exc_info=True)
    logging.info("Close watching contract.")


def close_contract_watch():
    assert P.F_WATCH_CONTRACT is True
    P.F_WATCH_CONTRACT = False


__all__ = [
    "watching_tx",
    "start_contract_watch",
    "close_contract_watch",
    "CheckWatchError",
]
