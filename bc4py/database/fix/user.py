from bc4py.config import V
from bc4py.utils import set_database_path, set_blockchain_params
from bc4py.database.create import create_db, closing
from bc4py.database.fix import fix_tx_height, fix_usedindex
from bc4py.database.user.read import read_all_utxo
from bc4py.database.user.write import rollback_account_balance
from bc4py.database.chain.read import read_tx_object
from bc4py.database.chain.flag import is_include_txhash
from binascii import hexlify


def fix_utxo(chain_cur, account_cur):
    # MainChainを元にutxoのUsedをチェックする
    need_fix = list()
    account_cur.execute("SELECT `hash`,`index`,`used` FROM `utxo`")
    for txhash, txindex, used in account_cur:
        tx = read_tx_object(txhash=txhash, cur=chain_cur)
        if used and txindex in tx.used_index:
            continue
        elif not used and txindex not in tx.used_index:
            continue
        else:
            unused = 0 if used else 1
            need_fix.append((unused, txhash, txindex))
            print("wrong!", hexlify(txhash).decode(), txindex, bool(used), ">>", bool(unused))
    account_cur.executemany("""
        UPDATE `utxo` SET `used`=? WHERE `hash`=? AND `index`=?
        """, need_fix)
    return need_fix


def fix_log(chain_cur, account_cur):
    # logのTxhashがTXに含まれるかチェックする
    need_fix = list()
    account_cur.execute("SELECT `hash` FROM `log`")
    for (txhash,) in account_cur:
        if not is_include_txhash(txhash=txhash, cur=chain_cur):
            need_fix.append((txhash,))
            rollback_account_balance(txhash=txhash, cur=account_cur, f_allow_minus=True)
            print("wrong!", hexlify(txhash).decode())
    return need_fix
