from bc4py.contract.libs import *
from bc4py.contract.libs import __all__ as all_libs
from bc4py.contract.dummy_module import contract
from importlib import import_module
import pickletools
import dill
import dis
import os
import sys
import io
import socket
from contextlib import closing


allow_globals = [
    '__name__', '__doc__', '__package__', '__loader__', '__spec__', '__builtins__'
]

allow_builtins = [
    'ArithmeticError', 'AssertionError', 'AttributeError', 'BaseException', 'BlockingIOError',
    'BrokenPipeError', 'BufferError', 'BytesWarning', 'ChildProcessError', 'ConnectionAbortedError',
    'ConnectionError', 'ConnectionRefusedError', 'ConnectionResetError', 'DeprecationWarning', 'EOFError',
    'Ellipsis', 'EnvironmentError', 'Exception', 'False', 'FileExistsError', 'FileNotFoundError',
    'FloatingPointError', 'FutureWarning', 'GeneratorExit', 'IOError', 'ImportError', 'ImportWarning',
    'IndentationError', 'IndexError', 'InterruptedError', 'IsADirectoryError', 'KeyError',
    'KeyboardInterrupt', 'LookupError', 'MemoryError', 'ModuleNotFoundError', 'NameError',
    'None', 'NotADirectoryError', 'NotImplemented', 'NotImplementedError', 'OSError', 'OverflowError',
    'PendingDeprecationWarning', 'PermissionError', 'ProcessLookupError', 'RecursionError',
    'ReferenceError', 'ResourceWarning', 'RuntimeError', 'RuntimeWarning', 'StopAsyncIteration',
    'StopIteration', 'SyntaxError', 'SyntaxWarning', 'SystemError', 'SystemExit', 'TabError',
    'TimeoutError', 'True', 'TypeError', 'UnboundLocalError', 'UnicodeDecodeError', 'UnicodeEncodeError',
    'UnicodeError', 'UnicodeTranslateError', 'UnicodeWarning', 'UserWarning', 'ValueError', 'Warning',
    'WindowsError', 'ZeroDivisionError',
    '_', '__name__', '__loader__', '__package__', '__spec__',
    'locals', 'globals', 'staticmethod', 'super', 'callable', 'classmethod',
    'issubclass', '__build_class__', '__debug__', '__doc__',
    'abs', 'all', 'any', 'ascii', 'bin', 'bool', 'bytearray', 'bytes', 'chr', 'complex', 'delattr', 'dict',
    'dir', 'divmod', 'enumerate', 'filter', 'float', 'format', 'frozenset', 'getattr', 'hasattr', 'hash',
    'hex', 'id', 'int', 'isinstance', 'iter', 'len', 'list', 'map', 'max', 'min', 'next', 'object', 'oct',
    'ord', 'pow', 'print', 'property', 'range', 'repr', 'reversed', 'round', 'set', 'setattr', 'slice',
    'sorted', 'str', 'sum', 'tuple', 'type', 'vars', 'zip']

deny_builtins = [
    '__import__',
    'memoryview', 'compile', 'copyright', 'credits', 'eval', 'exec', 'exit',
    'help', 'input', 'license', 'open', 'quit',
]


def get_limited_globals(extra=None):
    g = extra if extra else dict()
    for n in allow_globals:
        g[n] = globals()[n]
    if type(globals()['__builtins__']) == dict:
        builtins = globals()['__builtins__'].copy()
    else:
        builtins = globals()['__builtins__'].__dict__.copy()
    for deny in deny_builtins:
        try:
            del builtins[deny]
        except KeyError:
            pass
    g['__builtins__'] = builtins
    return g


def contract2binary(obj):
    obj.__module__ = None
    return dill.dumps(obj, protocol=4)


def contract2dis(obj):
    out = io.StringIO()
    dis.dis(obj, file=out)
    return out.getvalue()


def string2contract(s, fname, limited=True):
    code_obj = compile(s, fname, 'exec')
    fcode = code_obj.co_consts[0]
    fglobals = get_limited_globals({n: globals()[n] for n in all_libs}) if limited else globals()
    fdefaults = fclosure = None
    return dill.dill._create_function(
        fcode=fcode, fglobals=fglobals,
        fname=fname, fdefaults=fdefaults,
        fclosure=fclosure, fdict=None)


def binary2contract(binary):
    def dummy(*args):
        return args
    import_lack_modules(binary2opcode(binary))
    pointer_tmp = dill.dill._create_function
    dill.dill._create_function = dummy
    fcode, fglobals, fname, fdefaults, fclosure, fdict = dill.loads(binary)
    fglobals = get_limited_globals({n: globals()[n] for n in all_libs})
    dill.dill._create_function = pointer_tmp
    return dill.dill._create_function(
        fcode=fcode, fglobals=fglobals,
        fname=fname, fdefaults=fdefaults,
        fclosure=fclosure, fdict=fdict)


def binary2opcode(binary):
    # [(opcode, arg, pos), ..]
    # opcode.arg          opcode.doc          opcode.proto        opcode.stack_before
    # opcode.code         opcode.name         opcode.stack_after
    # o.arg.doc     o.arg.n       o.arg.name    o.arg.reader(
    return [a for a in pickletools.genops(binary)]


def binary2dis(binary):
    out = io.StringIO()
    pickletools.dis(binary, out=out, annotate=1)
    return out.getvalue()


def filepath2contract(path):
    # ソースを読み込んでObjectに変換
    if not os.path.isfile(path):
        raise TypeError('It\'s not file.')
    folder, file = os.path.split(path)
    module_name = file.split('.')[0]
    sys.path.insert(0, folder)
    contract_module = import_module(module_name)
    if 'contract' not in dir(contract_module):
        raise TypeError('module must contains "contract" function.')
    contract_obj = contract_module.contract
    if not callable(contract_obj):
        raise TypeError('is not callable.')
    # 再利用するもの
    # sys.path.remove(folder)
    return contract_obj


def import_lack_modules(opcodes):
    here = os.path.dirname(os.path.abspath(__file__))
    dummy_module = os.path.join(here, 'dummy_module.py')
    for opcode, arg, pos in opcodes:
        if opcode.name == 'GLOBAL':
            module, name = arg.split(' ')
            print(module, name)
            if '.' in module:
                continue
            elif module not in sys.modules:
                # import_module(name=here, package='dummy_module')
                sys.modules[module] = contract


def find_free_tcp_port():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


__all__ = [
    "allow_builtins", "deny_builtins",
    "string2contract", "contract2dis",
    "contract2binary", "binary2contract", "filepath2contract",
    "binary2opcode", "binary2dis",
    "find_free_tcp_port"
]
