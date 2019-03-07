from bc4py.config import V, BlockChainError
from bc4py.database.contract import get_contract_object
from bc4py.utils import set_blockchain_params
from bc4py.contract.serializer import *
from bc4py.contract.basiclib import __price__, config
from bc4py.contract import rpdb
from multiprocessing import get_context
import socket
import traceback
from time import time
import os
import bdb
from logging import getLogger

log = getLogger('bc4py')

# inner commands
CMD_ERROR = 'CMD_ERROR'
CMD_SUCCESS = 'CMD_SUCCESS'
CMD_PORT = 'CMD_PORT'

# pdb commands
EMU_STEP = 'step'
EMU_NEXT = 'next'
EMU_QUIT = 'quit'
EMU_UNTIL = 'until'
EMU_RETURN = 'return'


def _vm(genesis_block, genesis_params, new_config, start_tx, que, c, c_address, c_method, redeem_address, c_args):
    if new_config:
        config.update(new_config)
    set_blockchain_params(genesis_block, genesis_params)
    c_args = c_args or list()
    virtual_machine = rpdb.Rpdb(port=0)
    try:
        # notify listen port
        que.put((CMD_PORT, virtual_machine.port))
        # setup emulator
        virtual_machine.server_start()
        args = (start_tx, c_address, c.storage, redeem_address)
        contract = binary2contract(b=c.binary, extra_imports=c.extra_imports, args=args)
        fnc = getattr(contract, c_method)
        # start emulation
        virtual_machine.set_trace()
        result = fnc(*c_args)
        virtual_machine.do_quit(EMU_QUIT)
        que.put((CMD_SUCCESS, result))
    except bdb.BdbQuit as e:
        virtual_machine.do_quit(EMU_QUIT)
        que.put((CMD_ERROR, str(e)))
    except Exception:
        virtual_machine.do_quit(EMU_QUIT)
        tb = traceback.format_exc()
        que.put((CMD_ERROR, str(tb)))
    # close port
    try:
        virtual_machine.shutdown()
    except Exception:
        pass


def emulate(start_tx, c_address, c_method,
            redeem_address, c_args, new_config=None, gas_limit=None, file=None):
    """
    emulate Contract code
    :param start_tx: emulate StartTX
    :param c_address: contract address
    :param c_method: contract method name
    :param redeem_address: to redeem address
    :param c_args: arguments list
    :param new_config: update new emulator params, dict
    :param gas_limit: gas limit to use, None is unlimited
    :param file: logging output file object
    :return: status, error, total_gas, work_line
    """
    start = time()
    cxt = get_context('spawn')
    que = cxt.Queue()
    # get ContractObject with database, memory and unconfirmed (not pre-unconfirmed)
    c = get_contract_object(c_address=c_address)
    if c.version == -1 or c.binary is None:
        raise BlockChainError('Need register contract binary first.')
    kwargs = dict(genesis_block=V.GENESIS_BLOCK, genesis_params=V.GENESIS_PARAMS,
                  new_config=new_config, start_tx=start_tx, que=que, c=c, c_address=c_address,
                  c_method=c_method, redeem_address=redeem_address, c_args=c_args)
    p = cxt.Process(target=_vm, kwargs=kwargs)
    p.start()
    log.debug('wait for notify of listen port.')
    cmd, port = que.get(timeout=10)
    if cmd != CMD_PORT:
        raise Exception('Not correct command="{}" data="{}"'.format(cmd, port))
    log.debug("Communication port={}.".format(port))
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("127.0.0.1", port))
    sock.settimeout(10)
    log.debug('Start emulation of {}'.format(start_tx))
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
                # logging for debug
                print("{} d={} {} >> type={} gas={} path={} code=\"{}\"".format(
                    work_line, code_depth, cmd, working_type, total_gas, working_file, working_code), file=file)

                # select action by code_depth
                if code_depth == 0:
                    # pre Contract code: _em()
                    cmd = EMU_STEP
                elif code_depth == 1:
                    # Contract code body: Contract()
                    cmd = EMU_STEP
                    total_gas += 1
                else:
                    # Deep in basiclib functions
                    cmd = EMU_NEXT

                # Calculate total_gas
                if code_depth == 2 and working_type == 'Call':
                    for func, gas in __price__.items():
                        if func in working_code and working_code.startswith('def ' + func + '('):
                            total_gas += gas
                # next work line
                work_line += 1
            else:
                print("NOP [{}] >> {}".format(cmd, ', '.join(msgs)), file=file)

            # send response
            sock.send((cmd + "\n").encode())
        except ConnectionResetError:
            break
        except Exception:
            error = str(traceback.format_exc())
            break
    # close socket
    sock.send((EMU_QUIT + "\n").encode())
    sock.close()
    # Close emulation
    log.debug("Finish {}Sec error:\"{}\"".format(round(time()-start, 3), error))
    try:
        cmd, result = que.get(timeout=10)
        # close connect
        try: que.close()
        except Exception: pass
        try: p.terminate()
        except Exception: pass

        return cmd == CMD_SUCCESS, result, total_gas, work_line
    except Exception:
        if error is None:
            error = str(traceback.format_exc())
        return False, error, total_gas, work_line


__all__ = [
    "emulate",
]
