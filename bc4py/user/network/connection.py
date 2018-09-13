from bc4py.config import C, V, BlockChainError
from bc4py.user.network.directcmd import DirectCmd
import logging
import random
import collections
import time


good_node = list()
bad_node = list()
best_hash_on_network = None
best_height_on_network = None


def set_good_node():
    _node = list()
    pc = V.PC_OBJ
    blockhash = collections.Counter()
    blockheight = collections.Counter()
    for _user in pc.p2p.user:
        try:
            dummy, r = pc.send_direct_cmd(cmd=DirectCmd.BEST_INFO, data=None, user=_user)
            if isinstance(r, str):
                continue
        except TimeoutError:
            logging.debug("timeout", exc_info=True)
            continue
        blockhash[r['hash']] += 1
        blockheight[r['height']] += 1
        _node.append((_user, r['hash'], r['height'], r['booting']))
    global best_hash_on_network, best_height_on_network
    best_hash_on_network, num0 = blockhash.most_common()[0]
    best_height_on_network, num1 = blockheight.most_common()[0]
    good_node.clear()
    bad_node.clear()
    if num0 <= 1 or num1 <= 1:
        good_node.extend(_user for _user, _hash, _height, _booting in _node)
    else:
        for _user, _hash, _height, _booting in _node:
            if _hash == best_hash_on_network or _height == best_height_on_network:
                good_node.append(_user)
            else:
                bad_node.append(_user)


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
                    logging.warning("Failed DirectCmd:{} to {} by \"{}\"".format(cmd, user, r))
                    count -= 1
                    continue
                else:
                    raise BlockChainError('Node return error "{}"'.format(r))
        except TimeoutError:
            continue
        except IndexError:
            raise BlockChainError('No node found.', exc_info=True)
        return r
    raise BlockChainError('Too many retry ask_node.')


def get_best_conn_info():
    return best_height_on_network, best_hash_on_network


def check_connection(f_3_conn=3):
    c, need = 0,  3 if f_3_conn else 1
    while len(V.PC_OBJ.p2p.user) < need:
        if c % 90 == 0:
            logging.debug("Waiting for new connections.. {}".format(len(V.PC_OBJ.p2p.user)))
        time.sleep(1)
        c += 1


__all__ = [
    "set_good_node", "reset_good_node", "ask_node",
    "get_best_conn_info", "check_connection"
]
