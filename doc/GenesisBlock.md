Create genesis block
====================
Open interactive console.

```python
from bc4py.config import C
from bc4py.utils import set_database_path, set_blockchain_params
from bc4py.chain.genesisblock import create_genesis_block
from bc4py.database.create import make_account_db
from bc4py.user.boot import create_boot_file, import_keystone
 
# setup database path and initialize database
set_database_path()
make_account_db()
import_keystone(passphrase='hello python')
 
# consensus
consensus = {
    C.BLOCK_POS: 10,  # Staking algo
    C.BLOCK_YES_POW: 30,  # Specified for CPU algo
    C.BLOCK_X11_POW: 30,  # Specified for ASIC algo
    C.BLOCK_HMQ_POW: 30}  # Specified for GPU algo
 
# create first block
genesis_block = create_genesis_block(
    all_supply=10000000000 * 100000000,  # 10 billion total supply
    block_span=20,  # block time
    prefix=b'\x68',  # normal address prefix "N"
    contract_prefix=b'\x12',  # contract address prefix "C"
    digit_number=8,  # base currency digit
    minimum_price=100,  # minimum gas price
    consensus=consensus,  # mining consensus, key is algo value is ratio
    premine=None)  # premine [(address, coin_id, amount), ...]
  
# check genesis block
set_blockchain_params(genesis_block)
print(genesis_block.getinfo())
create_boot_file(genesis_block)
```
