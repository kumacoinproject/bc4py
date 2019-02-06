from bc4py.config import C, V
from bc4py.chain.pochash import poc_hash_iter
from bc4py.database.create import closing, create_db
from bc4py.database.builder import builder, tx_builder
from bc4py.database.account import *
from bc4py.user import *
from logging import getLogger
from time import time
import os

log = getLogger('bc4py')


class Search(dict):
    def __init__(self, gap_user, gap_limit, cur):
        super().__init__()
        self.gap_user = gap_user
        self.gap_limit = gap_limit
        self.cur = cur
        self.init()

    def init(self):
        user = 0
        gap_user = self.gap_user
        check = list()
        while gap_user > 0:
            for is_inner in (False, True):
                last_index = get_keypair_last_index(user=user, is_inner=is_inner, cur=self.cur)
                check.append((user, is_inner, last_index))
                if last_index == 0:
                    gap_user -= 1
            user += 1
        log.info("Finish check list {}".format(len(check)))
        index = None
        for user, is_inner, last_index in check:
            for index in range(last_index, last_index + self.gap_limit):
                sk, pk, ck = extract_keypair(user=user, is_inner=is_inner, index=index)
                self[ck] = (user, is_inner, index)
            log.info("Finish userID={} is_inner={} index={}".format(user, is_inner, index))

    def recode(self, ck):
        user, is_inner, index = self[ck]
        insert_keypair_from_bip(ck=ck, user=user, is_inner=is_inner, index=index, cur=self.cur)
        next_index = self.biggest_index(user=user, is_inner=is_inner) + 1
        sk, pk, ck = extract_keypair(user=user, is_inner=is_inner, index=next_index)
        self[ck] = (user, is_inner, next_index)
        log.info("Recode new userID={} is_inner={} index={} address={}"
                     .format(user, is_inner, index, ck))

    def biggest_index(self, user, is_inner):
        index = 0
        for _user, _is_inner, _index in self.values():
            if _user == user and _is_inner == is_inner and _index > index:
                index = _index
        return index


def repair_wallet(gap_user=10, gap_limit=20):
    if V.BIP44_BRANCH_SEC_KEY is None:
        raise PermissionError('You need unlock wallet')
    log.info("Wallet fix tool start now...")
    with closing(create_db(V.DB_ACCOUNT_PATH)) as db:
        cur = db.cursor()
        search = Search(gap_user=gap_user, gap_limit=gap_limit, cur=cur)
        for height, blockhash in builder.db.read_block_hash_iter(start_height=0):
            block = builder.get_block(blockhash=blockhash)
            for tx in block.txs:
                is_related = False
                for txhash, txindex in tx.inputs:
                    input_tx = tx_builder.get_tx(txhash)
                    address, coin_id, amount = input_tx.outputs[txindex]
                    if address in search:
                        search.recode(address)
                        is_related = True
                        break
                    elif read_address2user(address=address, cur=cur):
                        is_related = True
                        break
                if not is_related:
                    for address, coin_id, amount in tx.outputs:
                        if address in search:
                            search.recode(address)
                            is_related = True
                            break
                        elif read_address2user(address=address, cur=cur):
                            is_related = True
                            break
                # recode or ignore
                if is_related:
                    if read_txhash2log(txhash=tx.hash, cur=cur):
                        continue
                    movement = Accounting()
                    for txhash, txindex in tx.inputs:
                        input_tx = tx_builder.get_tx(txhash)
                        address, coin_id, amount = input_tx.outputs[txindex]
                        user = read_address2user(address=address, cur=cur)
                        if user is not None:
                            movement[user][coin_id] -= amount
                            # movement[C.ANT_OUTSIDE] += balance
                    for address, coin_id, amount in tx.outputs:
                        user = read_address2user(address, cur)
                        if user is not None:
                            movement[user][coin_id] += amount
                            # movement[C.ANT_OUTSIDE] -= balance
                    # check
                    movement.cleanup()
                    if len(movement) == 0:
                        continue
                    if read_txhash2log(txhash=tx.hash, cur=cur):
                        continue
                    insert_log(movements=movement, cur=cur, _type=tx.type, _time=tx.time, txhash=tx.hash)
                    log.info("Find not recoded transaction {}".format(tx))
            if height % 5000 == 0:
                log.info("Now height {} ...".format(height))
        db.commit()
    log.info("Finish wallet repair.")


def create_unoptimized_plots(address, start, end, path='plots'):
    # unoptimized file format
    # [hash0 #0]-[hash0 #1]-...-[hash0 #127]-  # nonce=0
    # [hash1 #0]-[hash1 #1]-...-[hash1 #127]-  # nonce=1
    # ....
    # [hashN #0]-[hashN #1]-...-[hashN #127]  # nonce=N
    assert 0 <= start < end <= 256**4
    s = time()
    if not os.path.exists(path):
        os.makedirs(path)
    file_path = os.path.join(path, 'unoptimized.{}-{}-{}.dat'.format(address.decode(), start, end))
    with open(file_path, mode='bw') as fp:
        for i in range(start, end):
            nonce = i.to_bytes(4, 'little')
            for h in poc_hash_iter(address, nonce):
                fp.write(h)
            if i % 10000 == 0:
                log.info('generate plot {} nonce...'.format(i))
    log.info("create unoptimized plot data, {}nonce {}Sec".format(end-start, round(time()-s, 3)))


def convert_optimize_plot(address, start, end, path='plots'):
    # file format
    # [address 40bytes]-[start 4bytes]-[end 4bytes]-
    # [hash0 #0]-[hash1 #0]-...-[hashN #0]-
    # [hash0 #1]-[hash1 #1]-...-[hashN #1]-
    # ...
    # [hash0 #127]-[hash1 #127]-...-[hashN #127]
    s = time()
    fix_str = '{}-{}-{}'.format(address.decode(), start, end)
    with open(os.path.join(path, 'optimized.{}.dat'.format(fix_str)), mode='bw') as wfp:
        with open(os.path.join(path, 'unoptimized.{}.dat'.format(fix_str)), mode='br') as rfp:
            wfp.write(address)
            wfp.write(start.to_bytes(4, 'little'))
            wfp.write(end.to_bytes(4, 'little'))
            for index in range(128):
                while True:
                    hashes_bin = rfp.read(32*128)
                    if len(hashes_bin) == 0:
                        break
                    if len(hashes_bin) != 32*128:
                        raise Exception('unoptimized file not correct len {}b'.format(len(hashes_bin)))
                    wfp.write(hashes_bin[index*32:(index+1)*32])
                rfp.seek(0)
                if index % 6 == 0:
                    log.info('converting {}/127...'.format(index))
    # remove unoptimized file
    os.remove(os.path.join(path, 'unoptimized.{}.dat'.format(fix_str)))
    log.info("create optimized plot data, {}-{} {}Sec".format(start, end, round(time()-s, 3)))


__all__ = [
    "repair_wallet",
    "create_unoptimized_plots",
    "convert_optimize_plot",
]
