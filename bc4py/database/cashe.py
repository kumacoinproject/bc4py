from bc4py.database.builder import chain_builder
from threading import Lock
import os.path
import atexit
import msgpack


class Cashe(object):

    def __init__(self, path, default):
        self.path = path
        self.default = default
        self.data = dict()
        self.lock = Lock()
        self.f_init_finish = False
        atexit.register(self.write)

    def _init(self):
        try:
            self._read()
        except Exception:
            self.data.clear()
        self.path = os.path.join(chain_builder.db.dirs, self.path)
        self.f_init_finish = True

    def _read(self):
        with open(self.path, mode='br') as fp:
            for address, args in msgpack.Unpacker(fp, raw=True, encoding='utf8'):
                self.data[address] = self.default.deserialize(args)

    def write(self):
        with self.lock:
            with open(self.path, mode='bw') as fp:
                for address, obj in self.data.items():
                    msgpack.pack((address, obj.serialize()), fp, use_bin_type=True)

    def get(self, address):
        with self.lock:
            if not self.f_init_finish: self._init()
            if address in self.data:
                return self.data[address].copy()
            else:
                self.data[address] = self.default(address)
                return self.default(address)

    def __iter__(self):
        with self.lock:
            # for only update
            yield from self.data.items()
