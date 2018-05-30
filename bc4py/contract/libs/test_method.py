from bc4py.contract.libs.fix_builtins import builtins


def dummy_add(i):
    print(builtins.compile)
    return i + 1


def dummy_sub(i):
    return i - 1


__price__ = {
    "dummy_add": 100,
    "dummy_sub": 100
}

__all__ = tuple(__price__)
