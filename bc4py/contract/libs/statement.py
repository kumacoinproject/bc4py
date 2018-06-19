from bc4py.config import V
from bc4py.contract.storage import ContractStorage
import bjson


# TODO: ぺつプロセスからどのようにして取得するか？
def get_storage_by_address(address):
    pass


def get_storage_obj(key_value=None):
    return ContractStorage(key_value=key_value)


def get_tx_message_data(tx):
    return bjson.loads(tx.message)[1]


__price__ = {
    "get_storage_by_address": 1000,
    "get_storage_obj": 100,
    "get_tx_message_data": 100
}


__all__ = tuple(__price__)
