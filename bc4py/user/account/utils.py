from bc4py.config import V, BlockChainError
from bc4py.database.user.flag import is_locked_database, is_exist_group
from bc4py.database.user.write import new_group, new_keypair
import logging


def create_new_group_keypair(group, account_cur):
    if is_locked_database(cur=account_cur):
        raise BlockChainError('Database is locked.')
    if not is_exist_group(group=group, cur=account_cur):
        new_group(group=group, cur=account_cur)
        logging.debug("Create new group({}).".format(group))
    sk, pk, ck = new_keypair(group=group, cur=account_cur)
    logging.debug("Create keypair {}".format(ck))
    return ck

