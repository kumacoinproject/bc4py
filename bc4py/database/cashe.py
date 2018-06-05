import time
from threading import Lock
from bc4py.config import C
from sys import getsizeof
from weakref import WeakValueDictionary
import gc

IS_BLOCK = 0
IS_TX = 1


class ChainCashe:
    def __init__(self):
        self.hash2data = dict()
        self.lock = Lock()
        self.limit = C.CASHE_SIZE

    def put_block(self, block):
        with self.lock:
            self.hash2data[block.hash] = (time.time(), block, IS_BLOCK)
            if len(self.hash2data) > self.limit:
                self.__refresh()
                gc.collect()

    def put_tx(self, tx):
        with self.lock:
            self.hash2data[tx.hash] = (time.time(), tx, IS_TX)
            if len(self.hash2data) > self.limit:
                self.__refresh()
        raise Exception('Not allowed.')

    def __getitem__(self, item):
        if item in self.hash2data:
            _time, obj, flag = self.hash2data[item]
            return obj
        else:
            return None

    def __contains__(self, item):
        return item in self.hash2data

    def __refresh(self):
        print("before", len(self.hash2data))
        limit = self.limit * 3 // 4
        for hash_, (time_, obj_, flag_) in sorted(self.hash2data.items(), key=lambda a: a[1][0]):
            if flag_ == IS_BLOCK:
                obj_.delete_time = int(time.time())
                del self.hash2data[hash_]
                for tx in obj_.txs:
                    if tx.hash in self.hash2data:
                        del self.hash2data[tx.hash]
                obj_.txs.clear()
                del obj_
            elif flag_ == IS_TX and hash_ in self.hash2data:
                del self.hash2data[hash_]
                del obj_
            if len(self.hash2data) < limit:
                break
        print("after", len(self.hash2data))

    def getsize(self):
        size = 0
        for time_, obj_, flag_ in self.hash2data.values():
            size += obj_.getsize()
        return size

    def getinfo(self):
        # for debug
        return "\n".join("{}:{}".format(time_, obj_)
                         for hash_, (time_, obj_, flag_) in self.hash2data.items())

    @property
    def size(self):
        size = 0
        for time_, obj_, flag_ in self.hash2data.values():
            size += getsizeof(obj_)
        return size


class WeakrefCashe:
    def __init__(self):
        self.hash2data = WeakValueDictionary()
        self.lock = Lock()
        self.limit = C.CASHE_SIZE

    def put_block(self, block):
        with self.lock:
            self.hash2data[block.hash] = block
            for tx in block.txs:
                self.hash2data[tx.hash] = tx

    def put_tx(self, tx):
        with self.lock:
            self.hash2data[tx.hash] = tx

    def __getitem__(self, item):
        if item in self.hash2data:
            return self.hash2data[item]
        else:
            return None

    def __contains__(self, item):
        return item in self.hash2data

    def getsize(self):
        size = 0
        for obj_ in self.hash2data.values():
            size += obj_.getsize()
        return size

    def getinfo(self):
        # for debug
        return "\n".join(str(obj_) for obj_ in self.hash2data.values())

    @property
    def size(self):
        size = 0
        for obj_ in self.hash2data.values():
            size += getsizeof(obj_)
        return size
