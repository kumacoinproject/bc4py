from nem_ed25519 import key, signature


def verify(msg, sign, pk):
    try:
        signature.verify(msg, sign, pk)
        return True
    except ValueError:
        return False


def pk2ck(pk, prefix=None):
    return key.get_address(pk, prefix)


__price__ = {
    "verify": 10000,
    "pk2ck": 500
}

__all__ = tuple(__price__)
