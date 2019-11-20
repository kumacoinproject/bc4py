from bc4py.config import V, P, BlockChainError
from bc4py.user.network.directcmd import DirectCmd
from p2p_python.config import PeerToPeerError
from collections import Counter
from logging import getLogger
import random
import asyncio


loop = asyncio.get_event_loop()
log = getLogger('bc4py')
good_node = list()
bad_node = list()
best_hash_on_network = None
best_height_on_network = None


async def set_good_node():
    node = list()
    pc = V.P2P_OBJ
    status_counter = Counter()
    f_all_booting = True  # flag: there is no stable node
    for user in pc.core.user.copy():
        try:
            dummy, r = await pc.send_direct_cmd(cmd=DirectCmd.best_info, data=None, user=user)
            if isinstance(r, str):
                continue
        except (asyncio.TimeoutError, PeerToPeerError):
            continue
        # success get best-info
        if not isinstance(r['height'], int):
            continue
        if not isinstance(r['hash'], bytes):
            continue
        status_counter[(r['height'], r['hash'])] += 1
        if r['booting'] is False:
            f_all_booting = False
        node.append((user, r['hash'], r['height'], r['booting']))
    # check unstable?
    if f_all_booting and len(pc.core.user) < 3:
        raise UnstableNetworkError("unstable network: All connection booting")
    if len(status_counter) == 0:
        raise UnstableNetworkError("unstable network: No status count")
    # get best height and best hash
    global best_hash_on_network, best_height_on_network
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


async def ask_node(cmd, data=None, f_continue_asking=False):
    await check_network_connection()
    failed = 0
    pc = V.P2P_OBJ
    user_list = pc.core.user.copy()
    random.shuffle(user_list)
    while failed < 10:
        try:
            if len(user_list) == 0:
                break
            if len(good_node) == 0:
                await set_good_node()
            user = user_list.pop()
            if user in good_node:
                dummy, r = await pc.send_direct_cmd(cmd=cmd, data=data, user=user)
                if isinstance(r, str):
                    failed += 1
                    if f_continue_asking:
                        log.warning("Failed cmd={} to {} by \"{}\"".format(cmd, user.header.name, r))
                        continue
                return r
            elif user in bad_node:
                pass
            else:
                await set_good_node()
        except asyncio.TimeoutError:
            pass
        except (UnstableNetworkError, PeerToPeerError) as e:
            log.warning("{}, wait 30sec".format(e))
            await asyncio.sleep(30)
    raise BlockChainError('Too many retry ask_node. good={} bad={} failed={} cmd={}'.format(
        len(good_node), len(bad_node), failed, cmd))


async def ask_all_nodes(cmd, data=None):
    await check_network_connection()
    pc = V.P2P_OBJ
    user_list = pc.core.user.copy()
    random.shuffle(user_list)
    result = list()
    for user in pc.core.user.copy():
        try:
            if len(good_node) == 0:
                await set_good_node()
            # check both good and bad
            if user in good_node or user in bad_node:
                dummy, r = await pc.send_direct_cmd(cmd=cmd, data=data, user=user)
                if not isinstance(r, str):
                    result.append(r)
            else:
                await set_good_node()
        except asyncio.TimeoutError:
            pass
        except (UnstableNetworkError, PeerToPeerError) as e:
            log.warning("{}, wait 30sec".format(e))
            await asyncio.sleep(30)
    if len(result) > 0:
        return result
    raise BlockChainError('Cannot get any data. good={} bad={} cmd={}'
                          .format(len(good_node), len(bad_node), cmd.__name__))


async def ask_random_node(cmd, data=None):
    await check_network_connection()
    pc = V.P2P_OBJ
    user_list = pc.core.user.copy()
    random.shuffle(user_list)
    for user in user_list:
        try:
            if len(good_node) == 0:
                await set_good_node()
            # check both good and bad
            if user in good_node or user in bad_node:
                dummy, r = await pc.send_direct_cmd(cmd=cmd, data=data, user=user)
                if not isinstance(r, str):
                    return r
            else:
                await set_good_node()
        except asyncio.TimeoutError:
            pass
        except (UnstableNetworkError, PeerToPeerError) as e:
            log.warning("{}, wait 30sec".format(e))
            await asyncio.sleep(30)
    raise BlockChainError('Full seeked but cannot get any data. good={} bad={} cmd={}'
                          .format(len(good_node), len(bad_node), cmd.__name__))


async def get_best_conn_info():
    while best_height_on_network is None:
        await set_good_node()
        await asyncio.sleep(0.1)
    return best_height_on_network, best_hash_on_network


async def check_network_connection(minimum=None):
    count = 0
    need = minimum or 2
    while len(V.P2P_OBJ.core.user) <= need:
        count += 1
        if P.F_STOP:
            return  # skip
        elif count % 30 == 0:
            log.debug("{} connections, waiting for new.. {}Sec".format(len(V.P2P_OBJ.core.user), count))
        elif count % 123 == 1:
            log.info("connect {} nodes but unsatisfied required number {}".format(len(V.P2P_OBJ.core.user), need))
        else:
            await asyncio.sleep(1)


class UnstableNetworkError(Exception):
    pass


__all__ = [
    "set_good_node",
    "reset_good_node",
    "ask_node",
    "ask_all_nodes",
    "ask_random_node",
    "get_best_conn_info",
    "check_network_connection",
]
