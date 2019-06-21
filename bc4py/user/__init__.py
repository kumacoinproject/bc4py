from bc4py.config import V, BlockChainError
from bc4py.bip32 import Bip32, BIP32_HARDEN
from collections import defaultdict


class Balance(defaultdict):
    __slots__ = tuple()

    def __init__(self, coin_id=None, amount=None, balance=None):
        super().__init__(int)
        if coin_id is not None and amount is not None:
            self[coin_id] = amount
        elif balance and isinstance(balance, dict):
            for k, v in balance.items():
                self[k] = v

    def __repr__(self):
        return "<Balance {}>".format(dict(self))

    def __iter__(self):
        yield from self.items()

    def copy(self):
        # don't remove zero balance pair, until copy
        # after copy, new obj don't include zero balance pair
        return Balance(balance=dict(self))

    def is_all_plus_amount(self):
        for v in self.values():
            if v < 0:
                return False
        return True

    def is_all_minus_amount(self):
        for v in self.values():
            if v > 0:
                return False
        return True

    def is_empty(self):
        for v in self.values():
            if v != 0:
                return False
        return True

    def cleanup(self):
        for k, v in list(self.items()):
            if v == 0:
                del self[k]

    def __add__(self, other):
        assert isinstance(other, Balance)
        b = self.copy()
        for k in other.keys():
            b[k] += other[k]
        return b

    def __sub__(self, other):
        assert isinstance(other, Balance)
        b = self.copy()
        for k in other.keys():
            b[k] -= other[k]
        return b


class Accounting(defaultdict):
    __slots__ = tuple()

    def __init__(self, users=None):
        super().__init__(Balance)
        if users and isinstance(users, dict):
            for k, v in users.items():
                self[k] = v.copy()

    def __repr__(self):
        return "<Accounting {}>".format(dict(self))

    def __iter__(self):
        yield from self.items()

    def copy(self):
        return Accounting(users=dict(self))

    def cleanup(self):
        for k, v in list(self.items()):
            v.cleanup()
            if v.is_empty():
                del self[k]

    def __add__(self, other):
        assert isinstance(other, Accounting)
        users = self.copy()
        for k, v in other.items():
            users[k] += v
        return users

    def __sub__(self, other):
        assert isinstance(other, Accounting)
        users = self.copy()
        for k, v in other.items():
            users[k] -= v
        return users


__all__ = [
    "Balance",
    "Accounting",
]
