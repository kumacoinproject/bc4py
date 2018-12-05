from bc4py.contract.params import *
from bc4py.contract.basiclib import *
from bc4py.contract.basiclib import __all__ as basiclibs
from bc4py.contract import dill
from types import FunctionType, ModuleType
from threading import Lock
import io
import dis
import os
import logging
import importlib

# Doc: restricting globals
# https://docs.python.jp/3/library/pickle.html#restricting-globals
PICKLE_PROTO_VER = 4
lock = Lock()


def get_limited_globals(extra_imports=None):
    g = {name: globals()[name] for name in basiclibs}
    if extra_imports:
        for name in extra_imports:
            logging.warning("Import an external library => {}".format(name))
            g[name] = importlib.import_module(name)
    for allow in allow_globals:
        if allow in globals():
            g[allow] = globals()[allow]
    for deny in deny_globals:
        if deny in g:
            del g[deny]
    __builtins__ = globals()['__builtins__']
    builtins = dict()
    for allow in allow_builtins:
        if allow in __builtins__:
            builtins[allow] = __builtins__[allow]
    for deny in deny_builtins:
        if deny in builtins:
            del builtins[deny]
    g['__builtins__'] = builtins
    return g


def binary2contract(c_bin, extra_imports=None):
    g = get_limited_globals(extra_imports)

    def dummy_create_function(fcode, fglobals, fname=None, fdefaults=None, fclosure=None, fdict=None):
        return FunctionType(fcode, g, fname, fdefaults, fclosure)

    with lock:
        create_fnc = dill._dill._create_function
        dill._dill._create_function = dummy_create_function
        c_obj = dill.loads(c_bin)
        dill._dill._create_function = create_fnc
    assert c_obj.__class__ is type, 'Is not a class.'
    c_obj.__module__ = 'bc4py.contract.dummy_template'
    c_obj.__name__ = 'contract'
    return c_obj


def string2contract(string, is_safe=False):
    assert is_safe, "Please check this security risk!"
    assert isinstance(string, str)
    code_obj = compile(string, "Contract", 'exec')
    f_type = type(ModuleType)
    if 'Contract' not in code_obj.co_consts:
        raise Exception('Not found "Contract" class.')
    code_idx = code_obj.co_consts.index('Contract') - 1
    class_element = code_obj.co_consts[code_idx].co_consts
    f_name = class_element[0]
    f_obj = (object,)
    f_dict = {'__module__': '__main__', '__doc__': None}
    f_defaults = f_closure = None
    for code in class_element:
        if type(code_obj) == type(code):
            f_dict[code.co_name] = FunctionType(code, globals(), code.co_name, f_defaults, f_closure)
    return f_type(f_name, f_obj, f_dict)


def path2contract(path, is_safe=False):
    if not os.path.exists(path):
        raise FileNotFoundError('Not found "{}"'.format(path))
    elif os.path.isdir(path):
        raise TypeError('Is not file "{}"'.format(path))
    with open(path, mode='r') as fp:
        string = fp.read()
    return string2contract(string, is_safe)


def contract2binary(obj):
    old_name = obj.__module__
    obj.__module__ = '__main__'
    c_bin = dill.dumps(obj,  protocol=4)
    obj.__module__ = old_name
    return c_bin


def contract2dis(obj):
    out = io.StringIO()
    dis.dis(obj, file=out)
    return out.getvalue()


__all__ = [
    "binary2contract", "string2contract", "path2contract",
    "contract2binary", "contract2dis"
]
