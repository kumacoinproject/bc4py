Create genesis block
====================
Open interactive console.

```python
from bc4py.config import C
from bc4py.utils import set_database_path, set_blockchain_params
from bc4py.chain.genesisblock import create_genesis_block
from bc4py.database.create import check_account_db
from bc4py.user.boot import create_boot_file, import_keystone
import asyncio
 
loop = asyncio.get_event_loop()
 
# setup database path and initialize database
set_database_path()
import_keystone(passphrase='hello python')
loop.run_until_complete(check_account_db())
 
# consensus
consensus = {
    C.BLOCK_COIN_POS: 6,  # Coin staking
    C.BLOCK_CAP_POS: 6,  # Capacity staking
    C.BLOCK_FLK_POS: 7,  # fund-lock staking
    C.BLOCK_YES_POW: 27,  # Yespower mining
    C.BLOCK_X11_POW: 27,  # X11 mining
    C.BLOCK_X16S_POW: 27}  # X16S mining
 
# create first block
genesis_block, genesis_params = create_genesis_block(
    hrp='test',
    mining_supply=100000000 * 100000000,  # one hundred million mining supply
    block_span=120,  # block time
    digit_number=8,  # base currency digit
    minimum_price=100,  # minimum gas price
    consensus=consensus,  # mining consensus, key is algo value is ratio
    genesis_msg="for test params",  # genesis message
    premine=None)  # premine [(address, coin_id, amount), ...]
  
# check genesis block
set_blockchain_params(genesis_block, genesis_params)
print(genesis_block.getinfo())
create_boot_file(genesis_block, genesis_params)
```
