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
    except Exception:
        virtual_machine.do_quit(EMU_QUIT)
        tb = traceback.format_exc()
        que.put((CMD_ERROR, str(tb)))


def emulate(genesis_block, start_tx, c_address, c_method, c_args, gas_limit=None, timeout=None, file=None):
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
    if timeout:
        sock.settimeout(timeout)
    logging.debug('Start emulation of {}'.format(start_tx))
    work_line = total_gas = 0
    cmd, error = EMU_STEP, None
    while True:
        try:
            msgs = sock.recv(8192).decode(errors='ignore').replace("\r", "").split("\n")
            if len(msgs) <= 1:
                sock.close()
                break
            elif len(msgs) < 3:
                pass
            elif gas_limit and gas_limit < total_gas:
                error = 'Reach gas_limit. [{}<{}]'.format(gas_limit, total_gas)
                break
            elif cmd in (EMU_STEP, EMU_NEXT, EMU_UNTIL, EMU_RETURN):
                msgs, working_path, words = msgs[:-3], msgs[-3][2:], msgs[-2][3:]
                working_file = os.path.split(working_path)[1]
                if working_file.startswith('contract('):
                    work_line += 1
                    total_gas += 1
                    cmd = EMU_STEP
                elif working_file.startswith(WORKING_FILE_NAME):
                    cmd = EMU_STEP
                else:
                    cmd = EMU_NEXT
                # Calculate total_gas
                for func, gas in __price__.items():
                    if func in words and words.startswith('def ' + func + '('):
                        total_gas += gas
                print("file={}, path={}".format(working_file, working_path.replace('\\', '/')), file=file)
                print(" {}: gas={} cmd={} >> {}".format(work_line, total_gas, cmd, words), file=file)
            else:
                print("NOP [{}] >> {}".format(cmd, ', '.join(msgs)), file=file)

            # send response
            sock.send((cmd + "\n").encode())
        except ConnectionResetError:
            break
        except Exception:
            error = str(traceback.format_exc())
            break
    # Close emulation
    logging.debug("Finish {}Sec error:{}".format(round(time()-start, 3), error))
    try:
        cmd, result = que.get(timeout=10)
        # close connect
        try: que.close()
        except: pass
        try: p.terminate()
        except: pass

        return cmd == CMD_SUCCESS, result, total_gas, work_line
    except Exception as e:
        if error is None:
            error = str(e)
        return False, error, total_gas, work_line
