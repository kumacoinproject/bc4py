from bc4py.contract.params import *
from bc4py.contract import basiclib
from types import FunctionType, CodeType, MethodType
from io import BytesIO, StringIO
from importlib import import_module
import importlib.util
from dis import dis
import pickle
import builtins
import os
import logging


# from A.B import C
# module = getattr(import_module('A.B'), 'C')

class_const_types = (int, str, bytes)
function_essential_attr = ("__code__", "__name__", "__defaults__", "__closure__")
function_optional_attr = ("__annotations__", "__dict__", "__doc__", "__kwdefaults__")
code_attr_order = ("co_argcount", "co_kwonlyargcount", "co_nlocals", "co_stacksize", "co_flags",
                   "co_code", "co_consts", "co_names", "co_varnames", "co_filename", "co_name",
                   "co_firstlineno", "co_lnotab", "co_freevars", "co_cellvars")


class ControlledUnpickler(pickle.Unpickler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args)
        self.safe_builtins = kwargs['safe_builtins'] or list()

    def find_class(self, module, name):
        # Only allow safe classes from builtins.
        if module == "builtins":
            if name in self.safe_builtins:
                return getattr(builtins, name)
        # Forbid everything else.
        raise pickle.UnpicklingError("global '{}.{}' is forbidden".format(module, name))


class ContractTemplate(object):
    def __init__(self, *args):
        self.start_tx = args[0]
        self.c_address = args[1]
        self.c_storage = args[2]
        self.redeem_address = args[3]

    def update(self, *args):
        raise Exception('Manually update required.')


def get_limited_globals(extra_imports=None):
    g = {name: getattr(basiclib, name) for name in basiclib.__all__}
    if extra_imports:
        for path, name in extra_imports:
            logging.warning("Import an external library => 'from {} import {}'".format(path, name))
            if name == "*":
                module = import_module(path)
                for module_name in module.__all__:
                    g[module_name] = getattr(module, module_name)
            else:
                g[name] = getattr(import_module(path), name)
    for allow in allow_globals:
        if allow in globals():
            g[allow] = globals()[allow]
    for deny in deny_globals:
        if deny in g:
            del g[deny]
    __builtins__ = globals()['__builtins__']
    builtin_dict = dict()
    for allow in allow_builtins:
        if allow in __builtins__:
            builtin_dict[allow] = __builtins__[allow]
    for deny in deny_builtins:
        if deny in builtin_dict:
            del builtin_dict[deny]
    g['__builtins__'] = builtin_dict
    return g


def code2pre(code):
    assert isinstance(code, CodeType)
    data = list()
    for name in code_attr_order:
        obj = getattr(code, name)
        if name == 'co_filename':
            data.append('')
        elif name == 'co_consts':
            const = list()
            for o in obj:
                if isinstance(o, CodeType):
                    const.append(code2pre(o))
                else:
                    const.append(o)
            data.append(const)  # Important: detect by list type
        else:
            data.append(obj)
    return data


def pre2code(pre):
    co_argcount, co_kwonlyargcount, co_nlocals, co_stacksize, co_flags, co_code, co_consts, co_names,\
    co_varnames, co_filename, co_name, co_firstlineno, co_lnotab, co_freevars, co_cellvars = pre
    const = list()
    for o in co_consts:
        if isinstance(o, list):
            const.append(pre2code(o))
        else:
            const.append(o)
    co_consts = tuple(const)
    code = CodeType(
        co_argcount, co_kwonlyargcount, co_nlocals, co_stacksize,
        co_flags, co_code, co_consts,
        co_names, co_varnames, co_filename,
        co_name, co_firstlineno, co_lnotab,
        co_freevars, co_cellvars)
    return code


def function2pre(fnc):
    assert isinstance(fnc, FunctionType)
    data = dict()
    for name in function_essential_attr + function_optional_attr:
        obj = getattr(fnc, name)
        if name == '__code__':
            data[name] = code2pre(obj)
        else:
            data[name] = obj
    return data


def pre2function(pre, global_dict):
    fnc = FunctionType(
        pre2code(pre['__code__']),
        global_dict,
        name=pre['__name__'],
        argdefs=pre['__defaults__'],
        closure=pre['__closure__'])
    for name in function_optional_attr:
        setattr(fnc, name, pre[name])
    return fnc


def contract2pre(contract):
    isinstance(contract, type)
    name2fnc = dict()
    name2const = dict()
    for name in dir(contract):
        obj = getattr(contract, name)
        if name == '__doc__' and isinstance(obj, str):
            name2const[name] = obj
            continue
        if name.startswith('__'):
            continue  # pass include __init__
        if isinstance(obj, FunctionType):
            name2fnc[name] = function2pre(obj)
        elif type(obj) in class_const_types:
            name2const[name] = obj
        else:
            continue  # pass unknown type
    return name2fnc, name2const


def pre2contract(name2fnc, name2const, global_dict, *args):
    contract = ContractTemplate(*args)
    for name, fnc in name2fnc.items():
        fnc = pre2function(fnc, global_dict)
        setattr(contract, name, MethodType(fnc, contract))
    for name, const in name2const.items():
        setattr(contract, name, const)
    contract.__module__ = None
    return contract


def binary2pre(b, safe_builtins=None):
    bio = BytesIO(b)
    pre = ControlledUnpickler(bio, safe_builtins=safe_builtins).load()
    bio.close()
    return pre


def pre2binary(pre):
    return pickle.dumps(obj=pre, protocol=4, fix_imports=False)


def contract2binary(contract):
    pre = contract2pre(contract)
    return pre2binary(pre)


def binary2contract(b, extra_imports, args):
    pre = binary2pre(b=b, safe_builtins=None)
    global_dict = get_limited_globals(extra_imports)
    return pre2contract(*pre, global_dict, *args)


""" note: will delete
def string2contract(string, global_dict, doc=''):
    def create_cell(contents):
        return (lambda y: contents).__closure__[0]
    code_obj = compile(string, "Contract", 'exec')
    for const in reversed(code_obj.co_consts):
        if const and isinstance(const, CodeType):
            code_obj = const
            break
    else:
        raise Exception('Not found contract code object.')
    f_name = code_obj.co_name
    f_obj = (object,)
    f_dict = {'__module__': '__main__', '__doc__': doc}
    defaults = None
    for code in code_obj.co_consts:
        if isinstance(code, CodeType):
            # ExampleContractTemplate.__init__.__closure__[0].cell_contents is ExampleContractTemplate
            for name in dir(code):
                print(name, getattr(code, name))
            closure = tuple(create_cell(getattr(code_obj, name)) for name in code.co_freevars)
            f_dict[code.co_name] = FunctionType(
                code, global_dict, name=code.co_name, argdefs=defaults, closure=closure)
        # elif type(code) in class_const_types:
        #    f_dict[code.co_name] = code
        else:
            logging.debug("Ignore code => {}".format(code))
    return type(f_name, f_obj, f_dict)
"""


def path2contract(path):
    # https://stackoverflow.com/questions/67631/how-to-import-a-module-given-the-full-path
    if not os.path.exists(path):
        raise FileNotFoundError('Not found "{}"'.format(path))
    elif os.path.isdir(path):
        raise TypeError('Is not file "{}"'.format(path))
    spec = importlib.util.spec_from_file_location("Contract", path)
    foo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(foo)
    for name in dir(foo):
        obj = getattr(foo, name)
        if obj.__class__ != type:
            continue
        elif obj.__module__ != 'Contract':
            continue
        elif len(obj.__init__.__closure__) != 1:
            logging.warning("Find class but don't hesitate ContractTemplate.")
            continue
        else:
            return obj
    raise Exception('Not found contract object.')


def contract2dis(obj):
    out = StringIO()
    dis(obj, file=out)
    return out.getvalue()


class ExampleContractTemplate(ContractTemplate):
    nice = 'nice!'
    coin_id = 11122

    def __init__(self, *args):
        super().__init__(*args)

    def game(self, *args):
        def dummy_func(d):
            return str(d)
        a = 'hello world'
        a += dummy_func('ww!')
        return a + ' -> Nice name ' + self.nice

    def why(self, *args):
        q = args[0]
        q += 342342342
        q -= self.coin_id
        return q


__all__ = [
    "ContractTemplate",
    "contract2binary",
    "binary2contract",
    "path2contract",
    "contract2dis",
]
