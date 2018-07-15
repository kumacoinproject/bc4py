from bc4py.contract.params import allow_globals, deny_builtins
from bc4py.contract.c_dummy import Contract
from bc4py.contract.libs import *
from bc4py.contract.libs import __all__ as all_libs
from types import FunctionType, ModuleType
import dill
import io
import dis
import os
import pickletools
import sys
import logging


def _limited_globals(extra=None):
    g = extra if extra else dict()
    for n in allow_globals:
        g[n] = globals()[n]
    builtins = dict(globals()['__builtins__']).copy()
    for deny in deny_builtins:
        try: del builtins[deny]
        except KeyError: pass
    g['__builtins__'] = builtins
    return g


def _import_lack_modules(c_bin):
    for opcode, arg, pos in pickletools.genops(c_bin):
        if opcode.name == 'GLOBAL':
            module, name = arg.split(' ')
            logging.debug("_import_lack_modules => {}, {}".format(module, name))
            if '.' in module:
                continue
            elif module not in sys.modules:
                # import_module(name=here, package='dummy_module')
                sys.modules[module] = Contract


def binary2contract(c_bin, limit_global=True):
    f_globals = _limited_globals({n: globals()[n] for n in all_libs}) if limit_global else globals()

    def dummy_create_type(*args):
        return args

    def dummy_create_function(fcode, fglobals, fname=None, fdefaults=None, fclosure=None, fdict=None):
        return FunctionType(fcode, f_globals, fname, fdefaults, fclosure)

    _import_lack_modules(c_bin)
    create_type = dill.dill._create_type
    create_func = dill.dill._create_function
    dill.dill._create_type = dummy_create_type
    dill.dill._create_function = dummy_create_function
    f_type, f_name, f_obj, f_dict = dill.loads(c_bin)
    assert f_type == type(ModuleType), 'Not class module.'
    c_obj = create_type(f_type, f_name, f_obj, f_dict)
    dill.dill._create_type = create_type
    dill.dill._create_function = create_func
    return c_obj


def string2contract(string, limit_global=True):
    code_obj = compile(string, "Contract", 'exec')
    f_type = type(ModuleType)
    code_idx = code_obj.co_consts.index('Contract') - 1
    class_element = code_obj.co_consts[code_idx].co_consts
    f_name = class_element[0]
    f_obj = (object,)
    f_dict = {'__module__': '__main__', '__doc__': None}
    f_globals = _limited_globals({n: globals()[n] for n in all_libs}) if limit_global else globals()
    f_defaults = f_closure = None
    for code in class_element:
        if type(code_obj) == type(code):
            f_dict[code.co_name] = FunctionType(
                code, f_globals, code.co_name, f_defaults, f_closure)
    return f_type(f_name, f_obj, f_dict)


def path2contract(path, limit_global=True):
    if not os.path.exists(path):
        raise FileNotFoundError('Not found "{}"'.format(path))
    elif os.path.isdir(path):
        raise TypeError('Is not file "{}"'.format(path))
    with open(path, mode='r') as fp:
        string = fp.read()
    return string2contract(string, limit_global)


def contract2binary(obj):
    old_name = obj.__module__
    obj.__module__ = '__main__'
    c_bin = dill.dumps(obj, protocol=4)
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
