from bc4py.bip32.bech32 import decode_with_check, encode_with_check
import hashlib


def is_address(ck, hrp, ver):
    """check bech32 format and version"""
    try:
        addr_ver, addr_identifier = decode_with_check(hrp, ck)
        if addr_ver is None:
            return False
        if ver != addr_ver:
            return False
    except ValueError:
        return False
    return True


def get_address(pk, hrp, ver):
    """get address from public key"""
    identifier = hashlib.new('ripemd160', hashlib.sha256(pk).digest()).digest()
    return encode_with_check(hrp, ver, identifier)


def convert_address(ck, hrp, ver):
    """convert address's version"""
    _, identifier = decode_with_check(hrp, ck)
    if identifier is None:
        raise ValueError('Not correct format address hrp={} ck={}'.format(hrp, ck))
    return encode_with_check(hrp, ver, identifier)


def dummy_address(dummy_identifier):
    assert len(dummy_identifier) == 20
    return encode_with_check('dummy', 0, dummy_identifier)


def addr2bin(ck, hrp):
    if ck.startswith('dummy'):
        ver, identifier = decode_with_check('dummy', ck)
    else:
        ver, identifier = decode_with_check(hrp, ck)
    if ver is None:
        raise ValueError('Not correct format')
    return ver.to_bytes(1, 'big') + identifier


def bin2addr(b, hrp):
    ver, identifier = b[0], b[1:]
    return encode_with_check(hrp, ver, identifier)


__all__ = [
    "is_address",
    "get_address",
    "convert_address",
    "dummy_address",
    "addr2bin",
    "bin2addr",
]
