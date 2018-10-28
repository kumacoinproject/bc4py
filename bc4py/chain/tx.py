#!/user/env python3
# -*- coding: utf-8 -*-

from bc4py import __chain_version__
from bc4py.config import C, V, BlockChainError
from hashlib import sha256
from binascii import hexlify
import time
import struct


struct_block = struct.Struct('>IIIIQqBBBI')
struct_inputs = struct.Struct('>32sB')
struct_outputs = struct.Struct('>40sIQ')


class TX:
    __slots__ = (
        "b", "hash", "height", "pos_amount",
        "version", "type", "time", "deadline", "inputs", "outputs",
        "gas_price", "gas_amount", "message_type", "message",
        "signature", "meta", "inner_params", "f_on_memory",
        "__weakref__")

    def __eq__(self, other):
        return self.hash == other.hash

    def __hash__(self):
        return hash(self.hash)

    def __repr__(self):
        return "<TX {} {} {} >"\
            .format(self.height, C.txtype2name[self.type], hexlify(self.hash).decode())

    def __init__(self, binary=None, tx=None):
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
        # proof
        self.signature = None  # [(pubkey, signature),.. ]
        # 処理には使わないが有用なデータ
        self.meta = dict()
        self.inner_params = dict()
        self.f_on_memory = None

        if binary:
            self.b = binary
            self.deserialize()
        elif tx:
            self.version = tx.get('version', __chain_version__)
            self.type = tx['type']
            self.time = tx.get('time', 0)
            self.deadline = tx.get('deadline', 0)
            self.inputs = tx.get('inputs', list())
            self.outputs = tx.get('outputs', list())
            self.gas_price = tx.get('gas_price', V.COIN_MINIMUM_PRICE)
            self.gas_amount = tx['gas_amount']
            self.message_type = tx.get('message_type', C.MSG_NONE)
            self.message = tx.get('message', b'')
            self.serialize()
        self.signature = list()

    def serialize(self):
        # 構造
        # [version I]-[type I]-[time I]-[deadline I]-[gas_price Q]-[gas_amount q]-[msg_type B]-
        # -[input_len B]-[output_len B]-[msg_len I]-[inputs]-[outputs]-[msg]
        self.b = struct_block.pack(
            self.version, self.type, self.time, self.deadline, self.gas_price, self.gas_amount,
            self.message_type, len(self.inputs), len(self.outputs), len(self.message))
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

    def deserialize(self):
        self.version, self.type, self.time, self.deadline, self.gas_price, self.gas_amount,\
            self.message_type, input_len, outputs_len, msg_len = struct_block.unpack_from(self.b, first_pos)
        # inputs
        pos = struct_block.size
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
        self.message = self.b[pos:pos+msg_len]
        pos += msg_len
        if len(self.b) != pos:
            raise BlockChainError('Do not match len [{}!={}'.format(len(self.b), pos))
        self.hash = sha256(self.b).digest()

    def getinfo(self):
        r = dict()
        r['hash'] = hexlify(self.hash).decode()
        r['pos_amount'] = self.pos_amount
        r['height'] = self.height
        r['version'] = self.version
        r['type'] = C.txtype2name[self.type]
        r['time'] = self.time + V.BLOCK_GENESIS_TIME
        r['deadline'] = self.deadline + V.BLOCK_GENESIS_TIME
        r['inputs'] = [(hexlify(txhash).decode(), txindex) for txhash, txindex in self.inputs]
        r['outputs'] = self.outputs
        r['gas_price'] = self.gas_price
        r['gas_amount'] = self.gas_amount
        r['message_type'] = C.msg_type2name.get(self.message_type) or self.message_type
        r['message'] = self.message.decode() if self.message_type == C.MSG_PLAIN else hexlify(self.message).decode()
        r['signature'] = [(pubkey, hexlify(signature).decode()) for pubkey, signature in self.signature]
        r['meta'] = self.meta
        r['f_on_memory'] = self.f_on_memory
        return r

    def getsize(self):
        s = len(self.b)
        for pk, sign in self.signature:
            assert isinstance(pk, str), 'pk is str.'
            assert isinstance(sign, bytes), 'sign is bytes'
            s += len(pk) // 2 + len(sign)
        return s

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
        now = int(time.time())
        self.time = now - V.BLOCK_GENESIS_TIME
        self.deadline = now - V.BLOCK_GENESIS_TIME + retention
        self.serialize()

"""
'version'
'type'
'time'
'deadline'
'inputs'
'outputs'
'gas_price'
'gas_amount'
'message_type'
'message'
"""