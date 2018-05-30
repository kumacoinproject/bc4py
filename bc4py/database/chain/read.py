from bc4py.config import C, V, P, BlockChainError
from bc4py.contract.storage import ContractStorage
from bc4py.chain.block import Block
from bc4py.chain.tx import TX
from bc4py.chain.utils import bin2signature
from bc4py.chain.mintcoin import MintCoinObject, setup_base_currency_mint
from bc4py.database.cashe import ChainCashe, WeakrefCashe
from binascii import hexlify
import bjson

"""
BlockchainDBへの読み込み操作のみ
"""

# Cashe
cashe_block = ChainCashe()
cashe_tx = WeakrefCashe()
# cashe_mint = dict()


def cashe_info():
    return len(cashe_block.hash2data), len(cashe_tx.hash2data)


def read_block_header(blockhash, cur):
    # Blockのヘッダー情報のみ渡す
    if blockhash in cashe_block:
        block = cashe_block[blockhash]
    else:
        d = cur.execute("""
            SELECT `height`,`work`,`bin`,`flag` FROM `block` WHERE `hash`=?
            """, (blockhash,)).fetchone()
        if d is None:
            raise BlockChainError('Not found block {}'.format(hexlify(blockhash).decode()))
        height, work, binary, flag = d
        block = Block(binary=binary)
        block.height = height
        block.work_hash = work
        block.flag = flag  # Orphanかもしれない、わからない
        block.bits2target()
        block.target2diff()
        cashe_block.put_block(block=block)
    return block


def fill_tx_objects(block, cur):
    try:
        if len(block.txs) == 0:
            txs = cur.execute("""
                SELECT `txs` FROM `block` WHERE `hash`=?
                """, (block.hash,)).fetchone()[0]
            block.txs = [read_tx_object(txhash=txs[i*32:i*32+32], cur=cur) for i in range(len(txs)//32)]
    except BlockChainError as e:
        raise BlockChainError('Cannot fill txinfo to {} "{}"'.format(block, e))


def read_txhash_of_block(blockhash, cur):
    d = cur.execute("""
            SELECT `txs` FROM `block` WHERE `hash`=?
            """, (blockhash,)).fetchone()
    if d is None:
        raise BlockChainError('Not found block {}'.format(hexlify(blockhash).decode()))
    txs = d[0]
    return [txs[i*32:i*32+32] for i in range(len(txs)//32)]


def read_block_object(blockhash, cur, f_fill_tx=True):
    # Blockの完全な状態で渡す(Folk判定、NextHash)
    block = read_block_header(blockhash=blockhash, cur=cur)

    # block body
    if f_fill_tx:
        fill_tx_objects(block=block, cur=cur)

    # 次のBlockを探す
    next_blocks = read_blocks_by_height(height=block.height+1, cur=cur)

    if len(next_blocks) == 0:
        # 最新のBlockであったので累積Diffで判定
        best_block = read_best_block(height=block.height, cur=cur)
        if block.hash == best_block.hash:
            block.f_orphan = False
            block.next_hash = None
        else:
            block.f_orphan = True
            block.next_hash = None
        return block

    elif len(next_blocks) == 1:
        # 次のBlockは一つなので次のBlockはMainChain
        next_best_block = next_blocks[0]
        if block.hash == next_best_block.previous_hash:
            block.f_orphan = False
            block.next_hash = next_best_block.hash
        else:
            block.f_orphan = True
            block.next_hash = None
        return block
    else:
        # 次のBlockは複数あるので次につながるBlockを調べる
        for next_block in next_blocks:
            if block.hash == next_block.previous_hash:
                if next_block.hash in P.CHECK_POINTS.values():
                    block.f_orphan = False
                    block.next_hash = next_block.hash
                    return block
                # f_orphan による判定(再計算する)
                next_block.f_orphan = None
                next_block = read_block_object(blockhash=next_block.hash, cur=cur, f_fill_tx=False)
                if next_block.f_orphan is False:
                    block.f_orphan = False
                    block.next_hash = next_block.hash
                    return block
        else:
            # 次につながるBlockが無かったという事
            block.f_orphan = True
            block.next_hash = None
            return block


def read_blocks_by_height(height, cur):
    d = cur.execute("""
        SELECT `hash` FROM `block` WHERE `height`=?
        """, (height,)).fetchall()
    return [read_block_header(blockhash=blockhash, cur=cur) for (blockhash,) in d]


def __tx_header(txhash, cur):
    d = cur.execute("""
        SELECT `height`,`bin`,`sign`,`used_index` FROM `tx` WHERE `hash`=?
        """, (txhash,)).fetchone()
    if d is None:
        raise BlockChainError('Not found tx {}'.format(hexlify(txhash).decode()))
    height, binary, sign, used_index = d
    if txhash in cashe_tx:
        tx = cashe_tx[txhash]
    else:
        tx = TX(binary=binary)
        tx.signature = bin2signature(b=sign)
    tx.height = height
    tx.used_index = used_index
    cashe_tx.put_tx(tx=tx)
    return tx


def read_tx_output(txhash, txindex, cur)-> (str, int, int):
    if txhash in cashe_tx:
        return cashe_tx[txhash].outputs[txindex]
    tx = __tx_header(txhash=txhash, cur=cur)
    if not (0 <= txindex <= len(tx.outputs) - 1):
        raise BlockChainError('Overflow txindex. [0<={}<={}]'.format(txindex, len(tx.outputs)-1))
    return tx.outputs[txindex]


def read_tx_object(txhash, cur):
    tx = __tx_header(txhash=txhash, cur=cur)
    # add meta data
    if tx.type == C.TX_GENESIS:
        pass
    elif tx.type == C.TX_POS_REWARD:
        if tx.pos_amount is None:
            hash_, index_ = tx.inputs[0]
            address, coin_id, amount = read_tx_output(txhash=hash_, txindex=index_, cur=cur)
            tx.pos_amount = amount

    elif tx.type == C.TX_POW_REWARD:
        pass
    elif tx.type == C.TX_TRANSFER:
        pass
    elif tx.type == C.TX_MINT_COIN:
        pass
    elif tx.type == C.TX_CREATE_CONTRACT:
        if 'c_address' not in tx.meta:
            c_address, c_bin = bjson.loads(tx.message)
            tx.meta.update({
                'c_address': c_address,
                'contract': hexlify(c_bin).decode()})
    elif tx.type == C.TX_START_CONTRACT:
        if 'finish_hash' not in tx.meta:
            finish_hash = read_finish_hash_by_start_hash(start_hash=tx.hash, cur=cur)
            if finish_hash:
                tx.meta['finish_hash'] = hexlify(finish_hash).decode()
    elif tx.type == C.TX_FINISH_CONTRACT:
        if 'start_hash' not in tx.meta:
            status, start_hash, cs_diff = bjson.loads(tx.message)
            tx.meta.update({
                'status': status,
                'start_hash': hexlify(start_hash).decode()})
    else:
        raise BlockChainError('Unknown type tx {}'.format(tx.type))
    return tx


def read_tx_height(txhash, cur):
    height = cur.execute('SELECT `height` FROM `tx` WHERE `hash`=?', (txhash,)).fetchone()
    if height:
        return height[0]
    else:
        raise BlockChainError('Not found txhash {}'.format(hexlify(txhash).decode()))


def max_block_height(cur):
    d = cur.execute("SELECT MAX(`height`) FROM `block`").fetchone()
    if d is None:
        raise BlockChainError('No block data found.')
    return d[0]


def read_folk_chains(height, cur):
    """
    あるHeightからRootまでの一連のBlockを取得する
    Orphanかどうかはわからない
    :return: {hash0: [Block(n),Block(n-1),..., Block(root)],
                    hash1: [Block'(n),Block'(n-1),..,Block(root)],...}
    """
    the_height_blocks = read_blocks_by_height(height, cur=cur)
    if len(the_height_blocks) == 0:
        # Blockが存在しない
        raise BlockChainError('No block found.')

    elif len(the_height_blocks) == 1:
        # Blockが１つだけで分岐は無し
        best_block = the_height_blocks[0]
        return {best_block.hash: [best_block]}

    # そのHeightのBlockが複数ある場合
    folks = dict()
    for block in the_height_blocks:
        folks[block.hash] = [block]

    # 共通の分岐の根本までBlockを積み上げる
    while True:
        for block_list in folks.values():
            previous_hash = block_list[-1].previous_hash
            previous_block = read_block_header(blockhash=previous_hash, cur=cur)
            block_list.append(previous_block)
        # 同一RootHashチェック
        root_hash = set(block_list[-1].hash for block_list in folks.values())
        if len(root_hash) == 1:
            return folks
    else:
        raise BlockChainError('Overflow limit on read_folk_chains.')


def read_best_block(height, cur):
    """
    指定のHeightまでのBestBlockを返す、ただしMainChainとは限らない
    共通のRootまでたどり累積Diffの一番大きいものを正当とする
    """
    folks = read_folk_chains(height=height, cur=cur)

    # 累積Diffを計算
    diff_sum = dict()
    for blockhash, block_list in folks.items():
        diff_sum[blockhash] = 0
        for block in block_list:
            if block.work_hash is None:
                if block.flag == C.BLOCK_POW:
                    block.update_pow()
                elif block.flag == C.BLOCK_POS:
                    fill_tx_objects(block=block, cur=cur)
                    proof_tx = block.txs[0]
                    block.work_hash = proof_tx.get_pos_hash(
                        previous_hash=block.previous_hash, pos_bias=block.pos_bias)
                else:
                    block.work_difficulty = 100000000
            if block.work_difficulty is None:
                block.work2diff()
            diff_sum[blockhash] += block.work_difficulty
    # BestBlock
    best_block_hash = sorted(diff_sum, key=lambda k: diff_sum[k], reverse=True)[0]
    return folks[best_block_hash][0]


def read_best_block_on_chain(height, cur):
    # BlockChain上のHeightのBlockを取得
    top_height = max_block_height(cur=cur)
    if top_height is None:
        raise BlockChainError('Cannot find any block.')
    elif height == top_height:
        block = read_best_block(height=height, cur=cur)
    elif 0 <= height < top_height:
        for block in read_blocks_by_height(height=height, cur=cur):
            if height in P.CHECK_POINTS:
                if block.hash == P.CHECK_POINTS[height]:
                    break
                else:
                    continue
            block = read_block_object(blockhash=block.hash, cur=cur, f_fill_tx=False)
            if block.f_orphan is False:
                break
        else:
            raise BlockChainError('Cannot find best block on height {}. Known block is {}'
                                  .format(height, read_blocks_by_height(height=height, cur=cur)))
    else:
        raise BlockChainError('Input over top height{}, max={}.'.format(height, top_height))
    return block


def read_mint_coin(coin_id, cur):
    if coin_id < 0:
        raise BlockChainError('coinID is more than 0.')
    elif coin_id == 0:
        return setup_base_currency_mint()

    all_coins = cur.execute("""
        SELECT `hash`,`bin` FROM `coins` WHERE `coin_id`=?
        ORDER BY `id` ASC""", (coin_id,)).fetchall()
    if len(all_coins) == 0:
        return None

    mint_coin_old = None
    for txhash, binary in all_coins:
        height = cur.execute("SELECT `height` FROM `tx` WHERE `hash`=?", (txhash,)).fetchone()
        if height is None:
            continue
        mint_coin_new = MintCoinObject(txhash=txhash, binary=binary)
        mint_coin_new.marge(mint_coin_old)
        mint_coin_new.check_param()
        mint_coin_new.check_sign()
        mint_coin_old = mint_coin_new
    return mint_coin_old


def mint_coin_history(coin_id, cur):
    if coin_id < 0:
        raise BlockChainError('coinID is more than 0.')
    elif coin_id == 0:
        return list()
    d = cur.execute("""
            SELECT `hash`,`bin` FROM `coins` WHERE `coin_id`=?
            ORDER BY `id` ASC""", (coin_id,)).fetchall()

    his = list()
    mint_coin_old = None
    for txhash, binary in d:
        height = cur.execute("SELECT `height` FROM `tx` WHERE `hash`=?", (txhash,)).fetchone()
        if height is None:
            continue
        mint_coin_new = MintCoinObject(txhash=txhash, binary=binary)
        mint_coin_new.marge(mint_coin_old)
        mint_coin_new.check_param()
        mint_coin_new.check_sign()
        mint_coin_old = mint_coin_new
        data = mint_coin_new.getinfo()
        data['height'] = height[0]
        his.append(data)
    return his


def read_unconfirmed_txs(cur):
    # Blockに取り込まれていないTXを取得
    cur.execute("SELECT `hash` FROM `tx` WHERE `height` IS NULL ORDER BY `time` DESC")
    return tuple(txhash for (txhash,) in cur)


def read_contract_list(cur):
    cur.execute("SELECT `address`,`hash` FROM `contract_info`")
    return {c_address: hexlify(txhash).decode() for c_address, txhash in cur}


def read_contract_tx(c_address, cur):
    txhash = cur.execute("""
        SELECT `hash` FROM `contract_info` WHERE `address`=?
        """, (c_address,)).fetchone()
    if txhash is None:
        raise BlockChainError('Not found contract address.')
    txhash = txhash[0]
    return read_tx_object(txhash=txhash, cur=cur)


def read_contract_utxo(c_address, cur):
    begin_finish_pairs = cur.execute("""
        SELECT `start_hash`,`finish_hash` FROM `contract_history` WHERE `address`=?
        """, (c_address,)).fetchall()
    for start_hash, finish_hash in begin_finish_pairs:
        if start_hash:
            tx = __tx_header(txhash=start_hash, cur=cur)
            for index, (output_address, coin_id, amount) in enumerate(tx.outputs):
                if index in tx.used_index:
                    continue
                elif output_address != c_address:
                    continue
                elif tx.height is None:
                    continue
                yield tx.hash, index, coin_id, amount
        if finish_hash:
            tx = __tx_header(txhash=finish_hash, cur=cur)
            for index, (output_address, coin_id, amount) in enumerate(tx.outputs):
                if index in tx.used_index:
                    continue
                elif output_address != c_address:
                    continue
                elif tx.height is None:
                    continue
                yield tx.hash, index, coin_id, amount


def read_contract_history(address, cur):
    d = cur.execute("""
        SELECT `start_hash`,`finish_hash` FROM `contract_history` WHERE `address`=?
        """, (address,)).fetchall()
    return d


def read_contract_storage(address, cur, stop_hash=None):
    finish_hash_list = cur.execute("""
        SELECT `finish_hash` FROM `contract_history` WHERE `address`=?
        """, (address,)).fetchall()
    cs = ContractStorage()
    for (finish_hash,) in finish_hash_list:
        if finish_hash is None:
            continue
        finish_tx = __tx_header(txhash=finish_hash, cur=cur)
        if finish_tx.type != C.TX_FINISH_CONTRACT:
            raise BlockChainError('Not TX_FINISH_CONTRACT? {}'.format(finish_tx))
        elif finish_tx.height is None:
            continue
        status, start_hash, cs_diff = bjson.loads(finish_tx.message)
        if start_hash == stop_hash:
            return cs
        elif not status:
            continue
        elif isinstance(cs_diff, tuple):
            cs.marge(cs_diff)
    return cs


def read_finish_hash_by_start_hash(start_hash, cur):
    d = cur.execute("""
        SELECT `finish_hash` FROM `contract_history` WHERE `start_hash`=?
        """, (start_hash,)).fetchone()
    if d is None:
        return None
    return d[0]
