from bc4py.config import V
from bc4py.utils import set_database_path, set_blockchain_params
from bc4py.database.builder import builder
from bc4py.database.tools import get_contract_binary
from bc4py.contract.tools import *
from bc4py.contract.libs import __price__
from bc4py.contract import rpdb
from multiprocessing import Process, Queue
import logging
import socket
import traceback
import time
import os
import bjson
import io

CMD_ERROR = 0
CMD_SUCCESS = 1
CMD_MODULE = 3
CMD_PORT = 4

EMU_STEP = 'step'
EMU_NEXT = 'next'
EMU_QUIT = 'quit'
EMU_UNTIL = 'until'
EMU_RETURN = 'return'


def _work(params, start_tx, que):
    set_database_path(sub_dir=params["sub_dir"])
    set_blockchain_params(genesis_block=params['genesis_block'])
    try:
        virtual_machine = rpdb.Rpdb(port=0)
        que.put((CMD_PORT, virtual_machine.port))
        virtual_machine.server_start()
        c_obj = binary2contract(params['c_bin'])
        file_path = c_obj.__code__.co_filename
        module_name = os.path.split(file_path)[1]
        que.put((CMD_MODULE, module_name))
        # remote emulate
        virtual_machine.set_trace()
        result = exe(c_obj=c_obj, start_tx=start_tx, c_address=params['c_address'],
                     method=params['c_method'], args=params['args'])
        que.put((CMD_SUCCESS, result))
    except BaseException:
        tb = traceback.format_exc()
        que.put((CMD_ERROR, str(tb)))


def try_emulate(start_tx, gas_limit=None, out=None):
    start_time = time.time()
    que = Queue()
    out = out or io.StringIO()
    c_address, c_method, c_args, c_redeem = bjson.loads(start_tx.message)
    c_bin = get_contract_binary(c_address)
    assert c_bin, 'Not found c_bin of {}'.format(c_address)
    params = {
        'sub_dir': V.SUB_DIR, 'genesis_block': builder.get_block(builder.get_block_hash(0)),
        'c_bin': c_bin, 'c_address': c_address, 'c_method': c_method, 'args': c_args}
    p = Process(target=_work, args=(params, start_tx, que))
    p.start()
    que_cmd, port = que.get(timeout=10)
    if que_cmd != CMD_PORT:
        raise TypeError('Not correct command="{}" data="{}"'.format(que_cmd, port))
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("127.0.0.1", port))
    sock.settimeout(10)
    # Start emulation
    line = fee = 0
    cmd = EMU_STEP
    error = None
    que_cmd, module_name = que.get(timeout=10)
    if que_cmd != CMD_MODULE:
        raise TypeError('Not correct command="{}" data="{}"'.format(que_cmd, module_name))
    logging.debug("Start {} contract port={}.".format(module_name, port))
    while True:
        try:
            msg_list = sock.recv(8192).decode(errors='ignore').replace("\r", "").split("\n")
            if len(msg_list) <= 1:
                sock.close()
                break
            elif len(msg_list) < 3:
                pass
            elif gas_limit and fee > gas_limit:
                error = 'reached gas limit. [{}>{}]'.format(fee, gas_limit)
                break
            elif cmd in (EMU_STEP, EMU_NEXT, EMU_UNTIL, EMU_RETURN):
                msg_list, path, words = msg_list[:-3], msg_list[-3][2:], msg_list[-2][3:]
                file = os.path.split(path)[1]
                if file.startswith('exe.py') and file.endswith('work_field()'):
                    cmd = EMU_STEP  # Start!
                    print("start contract {}".format(module_name), file=out)
                elif file.startswith(module_name) and file.endswith('contract()'):
                    line += 1
                    fee += 1
                    cmd = EMU_STEP
                else:
                    cmd = EMU_NEXT
                # Add fee
                for func, gas in __price__.items():
                    if func in words and words.startswith('def ' + func + '('):
                        fee += gas
                print("{}:read [{}] {} >> {}".format(line, fee, cmd, words), file=out)
            else:
                msg = ', '.join(msg_list)
                print("msg [{}] >>".format(cmd), msg, file=out)
            # response to work field
            sock.send((cmd + "\n").encode())
        except ConnectionResetError:
            break
        except BaseException:
            error = str(traceback.format_exc())
            break
    logging.debug("Finish contract {}Sec error:{}".format(round(time.time() - start_time, 3), error))
    # Close emulation
    try:
        que_cmd, result = que.get_nowait()
        try: que.close()
        except: pass
        try: p.terminate()
        except: pass
        if que_cmd == CMD_ERROR:
            return False, result, fee, line
        elif que_cmd == CMD_SUCCESS:
            return True, result, fee, line
    except BaseException:
        return False, error, fee, line
