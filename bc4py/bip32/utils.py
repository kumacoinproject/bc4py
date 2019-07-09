from bc4py_extension import PyAddress
import hashlib


def is_address(ck: PyAddress, hrp, ver):
    """check bech32 format and version"""
    try:
        if ck.hrp != hrp:
            return False
        if ck.version != ver:
            return False
    except ValueError:
        return False
    return True


def get_address(pk, hrp, ver) -> PyAddress:
    """get address from public key"""
    identifier = hashlib.new('ripemd160', hashlib.sha256(pk).digest()).digest()
    return PyAddress.from_param(hrp, ver, identifier)


def convert_address(ck: PyAddress, hrp, ver) -> PyAddress:
    """convert address's version"""
    return PyAddress.from_param(hrp, ver, ck.identifier())


def dummy_address(dummy_identifier) -> PyAddress:
    assert len(dummy_identifier) == 20
    return PyAddress.from_param('dummy', 0, dummy_identifier)


__all__ = [
    "is_address",
    "get_address",
    "convert_address",
    "dummy_address",
]
