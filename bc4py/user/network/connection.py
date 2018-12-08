from bc4py.config import V, P, BlockChainError
from bc4py.user.network.directcmd import DirectCmd
import logging
import random
from collections import Counter
import time


good_node = list()
bad_node = list()
best_hash_on_network = None
best_height_on_network = None


def set_good_node():
    node = list()
    pc = V.PC_OBJ
    status_counter = Counter()
    f_all_booting = True  # flag: there is no stable node
    for user in pc.p2p.user:
        try:
            dummy, r = pc.send_direct_cmd(cmd=DirectCmd.BEST_INFO, data=None, user=user)
            if isinstance(r, str):
                continue
        except TimeoutError:
            logging.debug("timeout", exc_info=True)
            continue
        status_counter[(r['height'], r['hash'])] += 1
        if r['booting'] is False:
            f_all_booting = False
        node.append((user, r['hash'], r['height'], r['booting']))
    global best_hash_on_network, best_height_on_network
    # get best height and best hash
    (best_height, best_hash), count = status_counter.most_common()[0]
    if count == 1:
        best_height, best_hash = sorted(status_counter, key=lambda x: x[0], reverse=True)[0]
    best_hash_on_network = best_hash
    best_height_on_network = best_height
    good_node.clear()
    bad_node.clear()
    for user, blockhash, height, f_booting in node:
        if blockhash == best_hash_on_network and height == best_height_on_network:
            good_node.append(user)
        else:
            bad_node.append(user)


def reset_good_node():
    good_node.clear()
    global best_hash_on_network, best_height_on_network
    best_hash_on_network = None
    best_height_on_network = None


def ask_node(cmd, data=None, f_continue_asking=False):
    check_connection()
    count = 10
    pc = V.PC_OBJ
    user_list = pc.p2p.user.copy()
    random.shuffle(user_list)
    while 0 < count:
        try:
            if len(user_list) == 0:
                raise BlockChainError('Asked all nodes, no node to ask.')
            user = user_list.pop()
            if user in bad_node:
                count -= 1
                continue
            elif user not in good_node:
                set_good_node()
                if len(good_node) == 0:
                    raise BlockChainError('No good node found.')
                else:
                    logging.debug("Get good node {}".format(len(good_node)))
                    continue
            dummy, r = pc.send_direct_cmd(cmd=cmd, data=data, user=user)
            if f_continue_asking and isinstance(r, str):
                if count > 0:
                    logging.warning("Failed DirectCmd:{} to {} by \"{}\"".format(cmd, user.name, r))
                    count -= 1
                    continue
                else:
                    raise BlockChainError('Node return error "{}"'.format(r))
        except TimeoutError:
            continue
        return r
    raise BlockChainError('Too many retry ask_node.')


def get_best_conn_info():
    return best_height_on_network, best_hash_on_network


def check_connection(f_3_conn=3):
    c, need = 0,  3 if f_3_conn else 1
    while not P.F_STOP and len(V.PC_OBJ.p2p.user) < need:
        if c % 90 == 0:
            logging.debug("Waiting for new connections.. {}".format(len(V.PC_OBJ.p2p.user)))
        time.sleep(1)
        c += 1


__all__ = [
    "set_good_node", "reset_good_node", "ask_node",
    "get_best_conn_info", "check_connection"
]
