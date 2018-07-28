

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

__all__ = [
    "allow_builtins", "allow_globals",
    "deny_builtins"
]
