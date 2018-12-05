from bc4py.config import BlockChainError
from bc4py.database.contract import get_contract_object
from bc4py.utils import set_blockchain_params
from bc4py.contract.tools import *
from bc4py.contract.basiclib import __price__
from bc4py.contract import rpdb
from multiprocessing import get_context
import logging
import socket
import traceback
from time import time
import os
import bdb


CMD_ERROR = 'CMD_ERROR'
CMD_SUCCESS = 'CMD_SUCCESS'
CMD_PORT = 'CMD_PORT'

EMU_STEP = 'step'
EMU_NEXT = 'next'
EMU_QUIT = 'quit'
EMU_UNTIL = 'until'
EMU_RETURN = 'return'

WORKING_FILE_NAME = 'em.py'

cxt = get_context('spawn')


def _vm(genesis_block, start_tx, que, binary, extra_imports, c_address, c_method, c_args):
    set_blockchain_params(genesis_block)
    c_args = c_args or list()
    virtual_machine = rpdb.Rpdb(port=0)
    try:
        c_obj = binary2contract(c_bin=binary, extra_imports=extra_imports)
        # notify listen port
        que.put((CMD_PORT, virtual_machine.port))
        # start emulate
        virtual_machine.server_start()
        virtual_machine.set_trace()
        # get method
        obj = c_obj(start_tx, c_address)
        fnc = getattr(obj, c_method)
        result = fnc(*c_args)
        virtual_machine.do_quit(EMU_QUIT)
        que.put((CMD_SUCCESS, result))
    except bdb.BdbQuit:
        pass
    except Exception:
        virtual_machine.do_quit(EMU_QUIT)
        tb = traceback.format_exc()
        que.put((CMD_ERROR, str(tb)))
    # close port
    try:
        virtual_machine.shutdown()
    except Exception:
        pass


def emulate(genesis_block, start_tx, c_address, c_method, c_args, gas_limit=None, file=None):
    start = time()
    que = cxt.Queue()
    c = get_contract_object(c_address=c_address, stop_txhash=start_tx.hash)
    if c.index == -1 or c.binary is None:
        raise BlockChainError('Need register contract binary first.')
    kwargs = dict(genesis_block=genesis_block, start_tx=start_tx, que=que, binary=c.binary,
                  extra_imports=c.extra_imports, c_address=c_address, c_method=c_method, c_args=c_args)
    p = cxt.Process(target=_vm, kwargs=kwargs)
    p.start()
    logging.debug('wait for notify of listen port.')
    cmd, port = que.get(timeout=5)
    if cmd != CMD_PORT:
        raise Exception('Not correct command="{}" data="{}"'.format(cmd, port))
    logging.debug("Communication port={}.".format(port))
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("127.0.0.1", port))
    sock.settimeout(10)
    logging.debug('Start emulation of {}'.format(start_tx))
    work_line = total_gas = code_depth = 0
    cmd, error = EMU_STEP, None
    data = b''
    while True:
        try:
            new_data = sock.recv(8192)
            if len(new_data) == 0:
                break
            data += new_data
            if data.endswith(b'(Pdb) '):
                msgs = data.decode(errors='ignore').replace("\r", "").split("\n")
                if data.startswith(b'> ') and len(msgs) == 2:
                    working_type = 'Normal_1'
                    working_path = msgs[0][2:]
                    working_code = ''
                elif data.startswith(b'> ') and len(msgs) == 3:
                    working_type = 'Normal_2'
                    working_path = msgs[0][2:]
                    working_code = msgs[-2][3:]
                elif data.startswith(b'--Call--'):
                    working_type = 'Call'
                    working_path = msgs[1][2:]
                    working_code = msgs[-2][3:]
                    code_depth += 1
                elif data.startswith(b'--Return--'):
                    working_type = 'Return'
                    working_path = msgs[1][2:]
                    working_code = msgs[-2][3:]
                    code_depth -= 1
                elif data.startswith(b'Internal StopIteration'):
                    working_type = 'StopIter'
                    working_path = msgs[1][2:]
                    working_code = msgs[-2][3:]
                else:
                    working_type = 'Exception'
                    working_path = msgs[1][2:]
                    working_code = msgs[-2][3:] if len(msgs) >= 4 else ''
                    print("{} >> Unexpected em data?: {}".format(work_line, msgs), file=file)
                data = b''
            else:
                continue
            if gas_limit and gas_limit < total_gas:
                error = 'Reach gas_limit. [{}<{}]'.format(gas_limit, total_gas)
                break
            elif cmd in (EMU_STEP, EMU_NEXT, EMU_UNTIL, EMU_RETURN):
                working_file = os.path.split(working_path)[1]
                if working_file.startswith('contract('):
                    total_gas += 1
                    cmd = EMU_STEP
                elif working_file.startswith(WORKING_FILE_NAME):
                    cmd = EMU_STEP
                else:
                    cmd = EMU_NEXT
                # Calculate total_gas
                for func, gas in __price__.items():
                    if func in working_code and working_code.startswith('def ' + func + '('):
                        total_gas += gas
                print("{} d={} {} >> type={} gas={} path={} code=\"{}\"".format(
                    work_line, code_depth, cmd, working_type, total_gas, working_file, working_code), file=file)
                work_line += 1
            else:
                print("NOP [{}] >> {}".format(cmd, ', '.join(msgs)), file=file)

            # send response
            sock.send((cmd + "\n").encode())
        except ConnectionResetError:
            break
        except Exception:
            import itertools
            error = str(traceback.format_exc())
            break
    # close socket
    sock.send((EMU_QUIT + "\n").encode())
    sock.close()
    # Close emulation
    logging.debug("Finish {}Sec error:\"{}\"".format(round(time()-start, 3), error))
    try:
        cmd, result = que.get(timeout=10)
        # close connect
        try: que.close()
        except Exception: pass
        try: p.terminate()
        except Exception: pass

        return cmd == CMD_SUCCESS, result, total_gas, work_line
    except Exception as e:
        if error is None:
            error = str(e)
        return False, error, total_gas, work_line
