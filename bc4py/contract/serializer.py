from bc4py.contract.params import *
from bc4py.contract import basiclib
from types import FunctionType, CodeType, MethodType, ModuleType
from io import BytesIO, StringIO
from importlib import import_module
import importlib.util
from dis import dis
import os
import msgpack
from logging import getLogger

log = getLogger('bc4py')


# from A.B import C
# module = getattr(import_module('A.B'), 'C')

class_const_types = (int, str, bytes)
function_essential_attr = ("__code__", "__name__", "__defaults__", "__closure__")
function_optional_attr = ("__dict__", "__doc__", "__kwdefaults__")
code_attr_order = ("co_argcount", "co_kwonlyargcount", "co_nlocals", "co_stacksize", "co_flags",
                   "co_code", "co_consts", "co_names", "co_varnames", "co_filename", "co_name",
                   "co_firstlineno", "co_lnotab", "co_freevars", "co_cellvars")


def default_hook(obj):
    if isinstance(obj, CodeType):
        data = list()
        for name in code_attr_order:
            code_obj = getattr(obj, name)
            if name == 'co_filename':
                data.append('')
            elif name == 'co_consts':
                const = list()
                for o in code_obj:
                    if isinstance(o, CodeType):
                        const.append(default_hook(o))
                    else:
                        const.append(o)
                data.append(tuple(const))  # Important: detect by list type
            elif name.startswith('__'):
                continue
            else:
                data.append(code_obj)
        return {'_contract_': 'CodeType', 'data': data}

    if isinstance(obj, FunctionType):
        data = dict()
        for name in function_essential_attr + function_optional_attr:
            fnc_obj = getattr(obj, name)
            if name == '__code__':
                data[name] = default_hook(fnc_obj)
            else:
                data[name] = fnc_obj
        return {'_contract_': 'FunctionType', 'data': data}

    if isinstance(obj, type):
        name2fnc = dict()
        name2const = dict()
        for name in dir(obj):
            class_obj = getattr(obj, name)
            if name == '__doc__' and isinstance(class_obj, str):
                name2const[name] = class_obj
            elif name.startswith('__'):
                pass  # pass include __init__
            elif isinstance(class_obj, FunctionType):
                name2fnc[name] = default_hook(class_obj)
            elif type(class_obj) in class_const_types:
                name2const[name] = class_obj
            else:
                pass  # pass unknown type
        return {'_contract_': 'ContractType', 'name2fnc': name2fnc, 'name2const': name2const}

    return obj


class Unpacker(msgpack.Unpacker):
    def __init__(self, fp, global_dict, args_list):
        super().__init__(fp, use_list=False, raw=True,
                         object_hook=self.object_hook, encoding='utf8')
        self.global_dict = global_dict
        self.args = args_list

    def object_hook(self, dct):
        if isinstance(dct, dict) and '_contract_' in dct:
            if dct['_contract_'] == 'CodeType':
                code_dict = dict()
                for index, name in enumerate(code_attr_order):
                    code_dict[name] = dct['data'][index]
                co_consts = list()
                for const in code_dict['co_consts']:
                    if isinstance(const, dict):
                        co_consts.append(self.object_hook(const))
                    else:
                        co_consts.append(const)
                code_dict['co_consts'] = tuple(co_consts)
                return CodeType(
                    code_dict['co_argcount'], code_dict['co_kwonlyargcount'], code_dict['co_nlocals'],
                    code_dict['co_stacksize'], code_dict['co_flags'], code_dict['co_code'],
                    code_dict['co_consts'], code_dict['co_names'], code_dict['co_varnames'],
                    code_dict['co_filename'], code_dict['co_name'], code_dict['co_firstlineno'],
                    code_dict['co_lnotab'], code_dict['co_freevars'], code_dict['co_cellvars'])

            if dct['_contract_'] == 'FunctionType':
                fnc = FunctionType(
                    self.object_hook(dct['data']['__code__']),
                    self.global_dict,
                    name=dct['data']['__name__'],
                    argdefs=dct['data']['__defaults__'],
                    closure=dct['data']['__closure__'])
                for name in function_optional_attr:
                    setattr(fnc, name, dct['data'][name])
                return fnc

            if dct['_contract_'] == 'ContractType':
                contract = ContractTemplate(*self.args)
                for name, fnc in dct['name2fnc'].items():
                    fnc = self.object_hook(fnc)
                    setattr(contract, name, MethodType(fnc, contract))
                for name, const in dct['name2const'].items():
                    setattr(contract, name, const)
                contract.__module__ = None
                return contract
        return dct


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
            log.warning("Import an external library => 'from {} import {}'".format(path, name))
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
    if isinstance(__builtins__, ModuleType):
        __builtins__ = {name: getattr(__builtins__, name) for name in dir(__builtins__)}
    builtin_dict = dict()
    for allow in allow_builtins:
        if allow in __builtins__:
            builtin_dict[allow] = __builtins__[allow]
    for deny in deny_builtins:
        if deny in builtin_dict:
            del builtin_dict[deny]
    g['__builtins__'] = builtin_dict
    return g


def binary2contract(b, extra_imports=None, args=()):
    global_dict = get_limited_globals(extra_imports=extra_imports)
    bio = BytesIO(b)
    contract = Unpacker(fp=bio, global_dict=global_dict, args_list=args).unpack()
    bio.close()
    return contract


def contract2binary(pre):
    return msgpack.packb(pre, default=default_hook, use_bin_type=True)


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
            log.warning("Find class but don't hesitate ContractTemplate.")
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
