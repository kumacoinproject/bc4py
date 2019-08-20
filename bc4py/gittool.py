from os.path import join
import os.path
import hashlib


def get_original_branch():
    try:
        str_hash = read(join('.git', 'ORIG_HEAD'))
        for line in read(join('.git', 'packed-refs')).split("\n"):
            if line.startswith(str_hash):
                _, branch_path = line.split(" ")
                return branch_path.split("/")[-1]
    except Exception:
        return None


def get_current_branch():
    try:
        branch = read(join('.git', 'HEAD'))
        branch = branch.lstrip().rstrip()
        return branch.split('/')[-1]
    except Exception:
        return None


def read(path):
    with open(path, mode='r', errors='ignore') as fp:
        return fp.read().lstrip().rstrip()


def calc_python_source_hash(folder=None) -> str:
    """calculate sha1 of bc4py source"""
    h = hashlib.sha1()

    def calc(p):
        for path in sorted(os.listdir(p), key=lambda x: str(x)):
            full_path = join(p, path)
            if os.path.isdir(full_path):
                calc(full_path)
            elif full_path.endswith('.py'):
                with open(full_path, mode='br') as fp:
                    h.update(fp.read())
            else:
                pass

    if folder is None:
        folder = os.path.split(os.path.abspath(__file__))[0]
    calc(folder)
    return h.hexdigest()


__all__ = [
    "get_original_branch",
    "get_current_branch",
    "calc_python_source_hash",
]
