from bc4py.config import C, V, NewInfo
from bc4py.chain import Block, TX
from bc4py.database.create import closing, create_db
from bc4py.database.account import read_address2user, read_user2name
from bc4py.database.validator import *
from expiringdict import ExpiringDict
from time import time
import bjson


watching_tx = ExpiringDict(max_len=1000, max_age_seconds=10800)


C_Conclude = 'Conclude'
C_Validator = 'Validator'
C_RequestConclude = 'RequestConclude'
C_FinishConclude = 'FinishConclude'
C_FinishValidator = 'FinishValidator'


def check_new_tx(tx: TX):
    if tx.height is not None:
        raise CheckWatchError('is not unconfirmed? {}'.format(tx))
    elif tx.message_type != C.MSG_BYTE:
        return
    elif tx.type == C.TX_CONCLUDE_CONTRACT:
        # 十分な署名が集まったら消す
        c_address, start_hash, c_storage = bjson.loads(tx.message)
        v = get_validator_object(c_address=c_address, stop_txhash=tx.hash)
        related_list = check_related_address(v.validators)
        if related_list:
            data = (time(), tx, related_list, c_address, start_hash, c_storage)
            watching_tx[tx.hash] = data
            NewInfo.put((C_Conclude, False, data))
    elif tx.type == C.TX_VALIDATOR_EDIT:
        # 十分な署名が集まったら消す
        c_address, new_address, flag, sig_diff = bjson.loads(tx.message)
        v = get_validator_object(c_address=c_address, stop_txhash=tx.hash)
        related_list = check_related_address(v.validators)
        if related_list:
            data = (time(), tx, related_list, c_address, new_address, flag, sig_diff)
            watching_tx[tx.hash] = data
            NewInfo.put((C_Validator, False, data))
    else:
        pass


def check_new_block(block: Block):
    for tx in block.txs:
        if tx.height is None:
            raise CheckWatchError('is not confirmed? {}'.format(tx))
        elif tx.message_type != C.MSG_BYTE:
            continue
        elif tx.type == C.TX_TRANSFER:
            # ConcludeTXを作成するべきフォーマットのTXを見つける
            c_address, c_method, c_args = bjson.loads(tx.message)
            v = get_validator_object(c_address=c_address)
            related_list = check_related_address(v.validators)
            if related_list:
                data = (time(), tx, related_list, c_address, c_method, c_args)
                watching_tx[tx.hash] = data
                NewInfo.put((C_RequestConclude, False, data))
        elif tx.type == C.TX_CONCLUDE_CONTRACT:
            if tx.hash in watching_tx:
                # try to delete c_transfer_tx and conclude_tx
                _time, _tx, _related_list, _c_address, start_hash, c_storage = watching_tx[tx.hash]
                if start_hash in watching_tx:
                    del watching_tx[start_hash]
                del watching_tx[tx.hash]
            data = (time(), tx)
            NewInfo.put((C_FinishConclude, False, data))
        elif tx.type == C.TX_VALIDATOR_EDIT:
            if tx.hash in watching_tx:
                del watching_tx[tx.hash]
            data = (time(), tx)
            NewInfo.put((C_FinishValidator, False, data))
        else:
            pass


def check_related_address(address_list):
    r = list()
    with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
        cur = db.cursor()
        for address in address_list:
            user = read_address2user(address=address, cur=cur)
            if user:
                r.append((read_user2name(user, cur), address))
    return r


class CheckWatchError(Exception):
    pass  # use for check fail


__all__ = [
    "C_Conclude",
    "C_Validator",
    "C_RequestConclude",
    "C_FinishConclude",
    "C_FinishValidator",
    "watching_tx",
    "check_new_tx",
    "check_new_block",
    "CheckWatchError"
]
