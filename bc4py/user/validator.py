from bc4py.config import C, P, BlockChainError
from bc4py.user.utils import im_a_validator, message2signature
from bc4py.contract.finishtx import finish_contract_tx
from bc4py.database.builder import tx_builder
import threading
import logging
import weakref
import time
import bjson


class Validator:
    def __init__(self):
        self.tx_unvalidated = weakref.WeakValueDictionary()
        self.tx_validated = weakref.WeakValueDictionary()
        self.tx_rejected = weakref.WeakValueDictionary()
        self.lock = threading.Lock()

    def __getitem__(self, item):
        if item in self.tx_unvalidated:
            return self.tx_unvalidated[item]
        elif item in self.tx_validated:
            return self.tx_validated[item]
        elif item in self.tx_rejected:
            return self.tx_rejected[item]
        else:
            return None

    def put_unvalidated(self, tx):
        if tx.hash in self.tx_validated:
            raise BlockChainError('Already validated tx {}'.format(tx))
        with self.lock:
            self.tx_unvalidated[tx.hash] = tx

    def put_validated(self, tx):
        with self.lock:
            self.tx_validated[tx.hash] = tx
            del self.tx_unvalidated[tx.hash]

    def put_rejected(self, tx):
        with self.lock:
            self.tx_rejected[tx.hash] = tx
            del self.tx_unvalidated[tx.hash]

    def get_unvalidated(self):
        return self.tx_unvalidated.copy().values()


def setup_as_validator():
    assert P.F_VALIDATOR is False, 'Already enabled Validator.'
    v_address = im_a_validator()
    if not v_address:
        logging.warning("You are not a validator.")
        return
    P.F_VALIDATOR = True
    P.VALIDATOR_QUE = Validator()
    threading.Thread(target=_loop, name='Validate', args=(v_address,)).start()


def _loop(v_address):
    while P.F_NOW_BOOTING:
        time.sleep(2)
    for tx in tx_builder.unconfirmed.values():
        if tx.type == C.TX_START_CONTRACT:
            P.VALIDATOR_QUE.put_unvalidated(tx)
    for tx in tx_builder.unconfirmed.values():
        if tx.type == C.TX_FINISH_CONTRACT:
            # TODO: 既にValidateしていないか
            c_result, start_hash, cs_diff = bjson.loads(tx.message)
            start_tx = P.VALIDATOR_QUE[start_hash]
            if start_tx:
                sign_pair = message2signature(tx.b, v_address)
                if sign_pair in tx.signature:
                    P.VALIDATOR_QUE.put_validated(tx)
                else:
                    # TODO:Validateして公開する
                    pass
    logging.info("Enabled validator mode [{}].".format(v_address))
    while True:
        for start_tx in P.VALIDATOR_QUE.get_unvalidated():
            finish_tx, estimate_gas = finish_contract_tx(start_tx)
            P.VALIDATOR_QUE.put_validated(start_tx)
            print(estimate_gas, finish_tx)
            time.sleep(1)


__all__ = [
    "setup_as_validator"
]
