from bc4py import __chain_version__
from bc4py.config import C, V, BlockChainError
from bc4py.bip32 import ADDR_SIZE
from bc4py.database import obj
from bc4py_extension import sha256d_hash, PyAddress
from typing import Optional, List
from time import time
from logging import getLogger
from struct import Struct
import msgpack

log = getLogger('bc4py')
struct_tx_header = Struct('<IIIIQqBBBI')
struct_inputs = Struct('<32sB')
struct_outputs = Struct('<{}sIQ'.format(ADDR_SIZE))


class TX(object):
    __slots__ = (
        # transaction data
        "b",
        "hash",
        # transaction body
        "version",  # 4bytes int
        "type",  # 4bytes int
        "time",  # 4bytes int
        "deadline",  # 4bytes int
        "inputs",  # [(txhash: 32bytes bin, txindex: 1byte int),..]
        "outputs",  # [(address: 21bytes bin, coin_id: 4bytes int, amount: 8bytes int),..]
        "gas_price",  # fee
        "gas_amount",  # fee
        "message_type",  # 2bytes int
        "message",  # 0~256**4 bytes bin
        # for verify
        "signature",  # [(pk, r, s),.. ]
        "verified_list",  # [address: str, ..]
        "R",
        # meta info
        "height",
        "pos_amount",
        "create_time",
        "__weakref__",
    )

    def __eq__(self, other):
        if isinstance(other, TX):
            return self.hash == other.hash
        log.warning("compare with {} by {}".format(self, other))
        return False

    def __hash__(self):
        return hash(self.hash)

    def __repr__(self):
        return "<TX {} {} {}>".format(
            self.height, C.txtype2name.get(self.type, 'UNKNOWN'), self.hash.hex())

    def __init__(self):
        # data
        self.b = None
        # body
        self.version: Optional[int] = None
        self.type: Optional[int] = None
        self.time: Optional[int] = None
        self.deadline: Optional[int] = None
        self.inputs: Optional[List[(bytes, int)]] = None
        self.outputs: Optional[List[(PyAddress, int, int)]] = None
        self.gas_price: Optional[int] = None
        self.gas_amount: Optional[int] = None
        self.message_type: Optional[int] = None
        self.message: Optional[bytes] = None
        # verify
        self.signature = list()
        self.verified_list = list()
        self.R = b''
        # meta
        self.hash = None
        self.height = None
        self.pos_amount = None
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
            self.b += struct_outputs.pack(address.binary(), coin_id, amount)
        # message
        self.b += self.message
        # txhash
        self.hash = sha256d_hash(self.b)

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
            b_address, coin_id, amount = struct_outputs.unpack_from(self.b, pos)
            self.outputs.append((PyAddress.from_binary(V.BECH32_HRP, b_address), coin_id, amount))
            pos += struct_outputs.size
        # msg
        self.message = self.b[pos:pos + msg_len]
        pos += msg_len
        if len(self.b) != pos - first_pos:
            if f_raise:
                raise BlockChainError('Do not match len [{}!={}'.format(len(self.b), pos))
            else:
                self.b = self.b[first_pos:pos]
        self.hash = sha256d_hash(self.b)

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
        r['outputs'] = [(addr.string, ver, id) for addr, ver, id in self.outputs]
        r['gas_price'] = self.gas_price
        r['gas_amount'] = self.gas_amount
        r['message_type'] = C.msg_type2name.get(self.message_type) or self.message_type
        r['message'] = self.message.decode() if self.message_type == C.MSG_PLAIN else self.message.hex()
        r['signature'] = [(pk.hex(), r.hex(), s.hex()) for pk, r, s in self.signature]
        r['hash_locked'] = self.R.hex()
        r['recode_flag'] = self.recode_flag
        r['create_time'] = self.create_time
        r['size'] = self.size
        r['total_size'] = self.total_size
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

    @property
    def total_size(self):
        signature_size = 0
        for s in self.signature:
            signature_size = sum(len(x) for x in s)
        return self.size + len(self.R) + signature_size

    @property
    def recode_flag(self) -> str:
        """show which storage contained"""
        if obj.tx_builder.memory_pool.exist(self.hash):
            return "unconfirmed"
        elif self.hash in obj.tx_builder.chained_tx:
            return "memory"
        else:
            return "database"

    def update_time(self, retention=10800):
        if retention < 10800:
            raise BlockChainError('Retention time is too short')
        now = int(time())
        self.time = now - V.BLOCK_GENESIS_TIME
        self.deadline = now - V.BLOCK_GENESIS_TIME + retention
        self.serialize()


__all__ = [
    "TX",
]
