from bc4py.chain.block import Block
from bc4py.chain.tx import TX
import msgpack


def default_hook(obj):
    if isinstance(obj, Block):
        return {
            '_bc4py_class_': 'Block',
            'binary': obj.b,
            'height': obj.height,
            'flag': obj.flag,
            'txs': [default_hook(tx) for tx in obj.txs]
        }
    if isinstance(obj, TX):
        return {
            '_bc4py_class_': 'TX',
            'binary': obj.b,
            'height': obj.height,
            'signature': obj.signature,
            'R': obj.R
        }
    return obj


def object_hook(dct):
    if isinstance(dct, dict) and '_bc4py_class_' in dct:
        if dct['_bc4py_class_'] == 'Block':
            block = Block.from_binary(binary=dct['binary'])
            block.height = dct['height']
            block.flag = dct['flag']
            block.txs.extend(object_hook(tx) for tx in dct['txs'])
            for tx in block.txs:
                tx.height = block.height
            return block
        elif dct['_bc4py_class_'] == 'TX':
            tx = TX.from_binary(binary=dct['binary'])
            tx.height = dct['height']
            tx.signature.extend(tuple(sig) for sig in dct['signature'])
            tx.R = dct['R']
            return tx
        else:
            raise Exception('Not found class name "{}"'.format(dct['_bc4py_class_']))
    else:
        return dct


def dump(obj, fp, **kwargs):
    msgpack.pack(obj, fp, use_bin_type=True, default=default_hook, **kwargs)


def dumps(obj, **kwargs):
    return msgpack.packb(obj, use_bin_type=True, default=default_hook, **kwargs)


def load(fp):
    return msgpack.unpack(fp, object_hook=object_hook, raw=True, encoding='utf8')


def loads(b):
    return msgpack.unpackb(b, object_hook=object_hook, raw=True, encoding='utf8')


def stream_unpacker(fp):
    return msgpack.Unpacker(fp, object_hook=object_hook, raw=True, encoding='utf8')


__all__ = [
    "default_hook",
    "object_hook",
    "dump",
    "dumps",
    "load",
    "loads",
    "stream_unpacker",
]
