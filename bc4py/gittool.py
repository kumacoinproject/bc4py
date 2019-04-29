from os.path import join


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


__all__ = [
    "get_original_branch",
    "get_current_branch",
]
