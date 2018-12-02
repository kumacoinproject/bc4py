from collections import defaultdict


# TODO: replace CoinObject to CoinBalance


class CoinBalance(defaultdict):
    def __init__(self, coin_id=None, amount=None, balance=None):
        super().__init__(int)
        if coin_id and amount:
            self[coin_id] = amount
        elif balance:
            for k, v in balance.items():
                if v != 0:
                    self[k] = v

    def __repr__(self):
        return "<CoinBalance {}>".format(dict(self))

    def copy(self):
        return CoinBalance(balance=dict(self))

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

    def __add__(self, other):
        b = self.copy()
        for k in other.keys():
            b[k] += other[k]
        return b

    def __sub__(self, other):
        b = self.copy()
        for k in other.keys():
            b[k] -= other[k]
        return b


class CoinObject:
    # スレッドセーフでない事に注意

    def __init__(self, coin_id=None, amount=None, coins=None):
        if amount:
            self.coins = {coin_id: amount}
        elif coins:
            self.coins = coins
        else:
            self.coins = dict()

    def __repr__(self):
        coin = ", ".join("{}={}".format(coin_id, amount) for coin_id, amount in self.coins.items())
        return "<Coins {}>".format(coin)

    def __iter__(self):
        yield from self.coins.items()

    def is_all_plus_amount(self):
        for v in self.coins.values():
            if v < 0:
                return False
        return True

    def is_all_minus_amount(self):
        for v in self.coins.values():
            if v > 0:
                return False
        return True

    def copy(self):
        coins = CoinObject()
        coins.coins = self.coins.copy()
        return coins

    def reverse_amount(self):
        for coin_id, amount in self.coins.items():
            self.coins[coin_id] = -1 * amount

    def __setitem__(self, key, value):
        self.coins[key] = value

    def __getitem__(self, item):
        if item in self.coins:
            return self.coins[item]
        return 0

    def __delitem__(self, key):
        if key in self.coins:
            del self.coins[key]

    def __add__(self, other):
        coin = self.coins.copy()
        for coin_id, amount in other:
            if coin_id in coin:
                coin[coin_id] += amount
            else:
                coin[coin_id] = amount
            if coin[coin_id] == 0:
                del coin[coin_id]
        coin_object = CoinObject()
        coin_object.coins = coin
        return coin_object

    def __sub__(self, other):
        coin = self.coins.copy()
        for coin_id, amount in other:
            if coin_id in coin:
                coin[coin_id] -= amount
            else:
                coin[coin_id] = -1 * amount
            if coin[coin_id] == 0:
                del coin[coin_id]
        coin_object = CoinObject()
        coin_object.coins = coin
        return coin_object

    def __dict__(self):
        return self.coins.copy()

    def __contains__(self, item):
        return item in self.coins

    def keys(self):
        return self.coins.keys()

    def values(self):
        return self.coins.values()

    def items(self):
        return self.coins.items()


class UserCoins:
    def __repr__(self):
        return "<UserCoins {}>".format(self.users)

    def __init__(self, users=None):
        self.users = users or dict()

    def copy(self):
        users = {user: coins.copy() for user, coins in self.users.items()}
        return UserCoins(users)

    def items(self):
        return self.users.items()

    def add_coins(self, user, coin_id, amount):
        if user in self.users:
            self.users[user][coin_id] += amount
        else:
            self.users[user] = CoinObject(coin_id, amount)

    def __contains__(self, item):
        return item in self.users

    def __getitem__(self, item):
        if item in self.users:
            return self.users[item]
        return CoinObject()

    def __setitem__(self, key, value):
        self.users[key] = value

    def __add__(self, other):
        new = dict()
        for u in set(self.users) | set(other.users):
            new[u] = CoinObject()
            if u in self.users:
                new[u] += self.users[u]
            if u in other:
                new[u] += other[u]
        return UserCoins(new)

    def __sub__(self, other):
        new = dict()
        for u in set(self.users) | set(other.users):
            new[u] = CoinObject()
            if u in self.users:
                new[u] += self.users[u]
            if u in other:
                new[u] -= other[u]
        return UserCoins(new)