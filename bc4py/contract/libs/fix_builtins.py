import builtins


def setup_builtins() -> builtins:
    class Builtin:
        pass
    _builtins = Builtin()
    for k, v in builtins.__dict__.items():
        _builtins.__setattr__(k, v)
    return _builtins


builtins = setup_builtins()
