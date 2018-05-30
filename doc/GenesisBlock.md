Create genesis block
====================
Open interactive console.

```python
from bc4py.config import C, V
from bc4py.utils import set_database_path, set_blockchain_params
from bc4py.chain.genesisblock import create_genesis_block, set_genesis_block
from bc4py.database.create import create_db, closing, make_account_db, make_blockchain_db
from bc4py.user.boot import create_boot_file, update_checkpoint
 
# setup database path and initialize database
set_database_path()
make_blockchain_db()
make_account_db()
 
# create first block
genesis_block = create_genesis_block(
    all_supply=10000000000 * 100000000,  # 10 billion total supply
    halving_span=3*365*24*3600,  # nonsense
    block_span=120,  # block time
    prefix=b'\x68',  # normal address prefix "N"
    contract_prefix=b'\x12',  # contract address prefix "C"
    digit_number=8,  # base currency digit
    minimum_price=100,  # minimum gas price
    consensus=C.HYBRID,  # mining consensus POW/POS/HYBRID
    pow_ratio=50,  # POW mining ratio 0~100
    premine=None)  # premine [(address, coin_id, amount), ...]
 
# recode block
set_genesis_block(genesis_block)
 
# check genesis block
set_blockchain_params()
print(genesis_block.getinfo())
 
with closing(create_db(V.DB_BLOCKCHAIN_PATH, True)) as db:
    cur = db.cursor()
    update_checkpoint(cur)
    create_boot_file(cur)
```
