from bc4py_extension import bech2address, address2bech
import hashlib


def is_address(ck, hrp, ver):
    """check bech32 format and version"""
    try:
        n_hrp, n_ver, n_id = address2bech(ck)
        if n_hrp != hrp:
            return False
        if n_ver != ver:
            return False
    except ValueError:
        return False
    return True


def get_address(pk, hrp, ver):
    """get address from public key"""
    identifier = hashlib.new('ripemd160', hashlib.sha256(pk).digest()).digest()
    return bech2address(hrp, ver, identifier)


def convert_address(ck, hrp, ver):
    """convert address's version"""
    n_hrp, n_ver, n_id = address2bech(ck)
    return bech2address(hrp, ver, n_id)


def dummy_address(dummy_identifier):
    assert len(dummy_identifier) == 20
    return bech2address('dummy', 0, dummy_identifier)


def addr2bin(ck, hrp):
    n_hrp, n_ver, n_id = address2bech(ck)
    assert n_hrp == 'dummy' or n_hrp == hrp
    return n_ver.to_bytes(1, 'big') + n_id


def bin2addr(b, hrp):
    ver, identifier = b[0], b[1:]
    return bech2address(hrp, ver, identifier)


__all__ = [
    "is_address",
    "get_address",
    "convert_address",
    "dummy_address",
    "addr2bin",
    "bin2addr",
]
