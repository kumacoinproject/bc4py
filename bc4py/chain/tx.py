from bc4py import __chain_version__
from bc4py.config import C, V, BlockChainError
from hashlib import sha256
from time import time
from logging import getLogger
import struct
import msgpack

log = getLogger('bc4py')
struct_tx_header = struct.Struct('<IIIIQqBBBI')
struct_inputs = struct.Struct('<32sB')
struct_outputs = struct.Struct('<40sIQ')


class TX:
    __slots__ = ("b", "hash", "height", "pos_amount", "version", "type", "time", "deadline", "inputs", "outputs",
                 "gas_price", "gas_amount", "message_type", "message", "signature", "R", "recode_flag",
                 "create_time", "__weakref__")

    def __eq__(self, other):
        if isinstance(other, TX):
            return self.hash == other.hash
        log.warning("compare with {} by {}".format(self, other), exc_info=True)
        return False

    def __hash__(self):
        return hash(self.hash)

    def __repr__(self):
        return "<TX {} {} {}>".format(self.height, C.txtype2name.get(self.type, None), self.hash.hex())

    def __init__(self):
        self.b = None
        # tx id
        self.hash = None
        self.height = None
        # pos
        self.pos_amount = None
        # tx body
        self.version = None  # 4bytes int
        self.type = None  # 4bytes int
        self.time = None  # 4bytes int
        self.deadline = None  # 4bytes int
        self.inputs = None  # [(txhash, txindex),..]
        self.outputs = None  # [(address, coin_id, amount),..]
        self.gas_price = None  # fee
        self.gas_amount = None  # fee
        self.message_type = None  # 2bytes int
        self.message = None  # 0~256**4 bytes bin
        # for validation
        self.signature = list()  # [(pubkey, signature),.. ]
        self.R = b''  # use for hash-locked
        # don't use for process
        self.recode_flag = None
        self.create_time = time()

    @classmethod
    def from_binary(cls, binary):
        self = cls()
        self.b = binary
        self.deserialize()
        return self

    @classmethod
    def from_dict(cls, tx):
        self = cls()
        self.version = tx.get('version', __chain_version__)
        self.type = tx['type']
        self.time = tx.get('time', 0)
        self.deadline = tx.get('deadline', 0)
        self.inputs = tx.get('inputs', list())
        self.outputs = tx.get('outputs', list())
        self.gas_price = tx.get('gas_price', V.COIN_MINIMUM_PRICE)
        self.gas_amount = tx.get('gas_amount', 0)
        self.message_type = tx.get('message_type', C.MSG_NONE)
        self.message = tx.get('message', b'')
        self.serialize()
        # extension
        self.signature = tx.get('signature', self.signature)
        self.R = tx.get('R', self.R)
        return self

    def serialize(self):
        # 構造
        # [version I]-[type I]-[time I]-[deadline I]-[gas_price Q]-[gas_amount q]-[msg_type B]-
        # -[input_len B]-[output_len B]-[msg_len I]-[inputs]-[outputs]-[msg]
        self.b = struct_tx_header.pack(self.version, self.type, self.time, self.deadline, self.gas_price,
                                       self.gas_amount, self.message_type, len(self.inputs), len(self.outputs),
                                       len(self.message))
        # inputs
        for txhash, txindex in self.inputs:
            self.b += struct_inputs.pack(txhash, txindex)
        # outputs
        for address, coin_id, amount in self.outputs:
            self.b += struct_outputs.pack(address.encode(), coin_id, amount)
        # message
        self.b += self.message
        # txhash
        self.hash = sha256(sha256(self.b).digest()).digest()

    def deserialize(self, first_pos=0, f_raise=True):
        self.version, self.type, self.time, self.deadline, self.gas_price, self.gas_amount,\
            self.message_type, input_len, outputs_len, msg_len = struct_tx_header.unpack_from(self.b, first_pos)
        # inputs
        pos = first_pos + struct_tx_header.size
        self.inputs = list()
        for i in range(input_len):
            self.inputs.append(struct_inputs.unpack_from(self.b, pos))
            pos += struct_inputs.size
        # outputs
        self.outputs = list()
        for i in range(outputs_len):
            address, coin_id, amount = struct_outputs.unpack_from(self.b, pos)
            self.outputs.append((address.decode(), coin_id, amount))
            pos += struct_outputs.size
        # msg
        self.message = self.b[pos:pos + msg_len]
        pos += msg_len
        if len(self.b) != pos - first_pos:
            if f_raise:
                raise BlockChainError('Do not match len [{}!={}'.format(len(self.b), pos))
            else:
                self.b = self.b[first_pos:pos]
        self.hash = sha256(sha256(self.b).digest()).digest()

    def getinfo(self):
        r = dict()
        r['hash'] = self.hash.hex()
        r['pos_amount'] = self.pos_amount
        r['height'] = self.height
        r['version'] = self.version
        r['type'] = C.txtype2name.get(self.type, None)
        r['time'] = self.time + V.BLOCK_GENESIS_TIME
        r['deadline'] = self.deadline + V.BLOCK_GENESIS_TIME
        r['inputs'] = [(txhash.hex(), txindex) for txhash, txindex in self.inputs]
        r['outputs'] = self.outputs
        r['gas_price'] = self.gas_price
        r['gas_amount'] = self.gas_amount
        r['message_type'] = C.msg_type2name.get(self.message_type) or self.message_type
        r['message'] = self.message.decode() if self.message_type == C.MSG_PLAIN else self.message.hex()
        r['signature'] = [(pubkey, signature.hex()) for pubkey, signature in self.signature]
        r['hash_locked'] = self.R.hex()
        r['recode_flag'] = self.recode_flag
        r['create_time'] = self.create_time
        r['size'] = self.size
        r['total_size'] = self.total_size()
        return r

    def encoded_message(self):
        if self.message_type == C.MSG_NONE:
            return None
        elif self.message_type == C.MSG_PLAIN:
            return self.message.decode()
        elif self.message_type == C.MSG_BYTE:
            return self.message.hex()
        elif self.message_type == C.MSG_MSGPACK:
            return msgpack.unpackb(self.message, raw=True, encoding='utf8')
        elif self.message_type == C.MSG_HASHLOCKED:
            return self.message.hex()
        else:
            raise BlockChainError('Unknown message type {}'.format(self.message_type))

    @property
    def size(self):
        # Do not include signature size
        return len(self.b)

    def total_size(self):
        signature_size = sum(len(x) for x in self.signature)
        return len(self.b) + len(self.R) + signature_size

    def get_pos_hash(self, previous_hash):
        # staked => sha256(txhash + previous_hash) / amount < 256^32 / diff
        pos_work_hash = sha256(self.hash + previous_hash).digest()
        work = int.from_bytes(pos_work_hash, 'little')
        work //= (self.pos_amount // 100000000)
        return work.to_bytes(32, 'little')

    def pos_check(self, previous_hash, pos_target_hash):
        # staked => sha256(txhash + previous_hash) / amount < 256^32 / diff
        pos_work_hash = sha256(self.hash + previous_hash).digest()
        work = int.from_bytes(pos_work_hash, 'little')
        work //= (self.pos_amount // 100000000)
        return work < int.from_bytes(pos_target_hash, 'little')

    def update_time(self, retention=10800):
        if retention < 10800:
            raise BlockChainError('Retention time is too short.')
        now = int(time())
        self.time = now - V.BLOCK_GENESIS_TIME
        self.deadline = now - V.BLOCK_GENESIS_TIME + retention
        self.serialize()
