import hashlib
import sha3


def sha256(b):
    return hashlib.sha256(b).digest()


def sha3_256(b):
    return hashlib.sha3_256(b).digest()


def keccak_256(b):
    return sha3.keccak_256(b).digest()


__price__ = {
    "sha256": 200,
    "sha3_256": 200,
    "keccak_256": 200,
}


__all__ = tuple(__price__)
