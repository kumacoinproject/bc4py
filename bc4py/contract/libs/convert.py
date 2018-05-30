from binascii import hexlify, unhexlify
import bjson
import json


def binary2hexstr(b):
    return hexlify(b).decode()


def hexstr2binary(s):
    return unhexlify(s.encode())


def bjson2obj(b):
    return bjson.loads(b)


def obj2bjson(o):
    return bjson.dumps(o)


def json2obj(j):
    return json.loads(j)


def obj2json(o):
    return json.dumps(o)


__price__ = {
    "binary2hexstr": 10,
    "hexstr2binary": 10,
    "bjson2obj": 10,
    "obj2bjson": 10,
    "json2obj": 10,
    "obj2json": 10,
}

__all__ = tuple(__price__)
