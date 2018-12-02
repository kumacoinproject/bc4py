bc4py (blockchain-for-python)
=============================
It enable you to create application with blockchain on Python3.

Function
----
* UTXO base
* Proof of works or/and proof of stake multi-consensus
* Minting colored coin (Not token)
* Python interpreter based smart contract (PyContract)
* block containing result smart contract　(differ from Ethereum)

Requirement
----
* Windows/Linux
* Python3 (3.5, 3.6~)
* [nem-ed25519](https://github.com/namuyan/nem-ed25519) my encryption lib
* [p2p-python](https://github.com/namuyan/p2p-python) my peer2peer lib
* LevelDB
    * [plyvel](https://github.com/wbolster/plyvel) for linux and ARM
    * [python-leveldb](https://github.com/happynear/py-leveldb-windows) for linux and windows
* hash algorithm
    * [yespower-python](https://github.com/namuyan/yespower-python)  For CPU
    * [~~yescryptR64~~](https://github.com/namuyan/yescryptR64-python) CPU resistance?
    * [hmq-hash](https://github.com/namuyan/hmq-hash) for GPU
    * [x16s-hash](https://pypi.org/project/shield-x16s-hash/) for GPU
    * [x11_hash](https://pypi.org/project/x11_hash/) For ASIC
    * [litecoin_scrypt](https://pypi.org/project/litecoin_scrypt/) For ASIC

Install
----
```commandline
cd ~
git clone https://github.com/namuyan/bc4py
mv bc4py blockchain-py
cd blockchain-py
pip install --user -r reqirements.txt
pip install --user -r reqirements-c.txt
wget http://example.com/boot.dat
```

* install leveldb
    * For windows, please look [py-leveldb-windows](https://github.com/happynear/py-leveldb-windows)
    * For linux, `pip install plyvel` or `pip install leveldb`
    * For ARM, [leveldb-1.20-build](https://tangerina.jp/blog/leveldb-1.20-build/)

```text
# compile
wget https://github.com/google/leveldb/archive/v1.20.tar.gz
zcat v1.20.tar.gz | tar xf -
cd leveldb-1.20
make
make check
# copy source
sudo cp -r include/leveldb /usr/local/include/
sudo install -o root -m 644 -p out-shared/libleveldb.so.1.20 /usr/local/lib/
sudo cp -d out-shared/libleveldb.so out-shared/libleveldb.so.1 /usr/local/lib/
sudo install -o root -m 644 -p out-static/lib* /usr/local/lib/
# affect changes
sudo ldconfig
pip install plyvel
```

Start node
----
* `python localnode.py` Node working on local env, for debug.
* `python publicnode.py` Node with mining/staking.
* `python observenode.py` Node only accept blocks/txs.

Documents
----
* [Create genesis block](doc/GenesisBlock.md)
* [Ho to mining](doc/Mining.md)
* [API doc](bc4py/user/api/static/index.md)
* [Development Guidelines](doc/Development.md)

Build for windows
----
`nuitka3 --mingw --recurse-none publicnode.py`

Author
----
[@namuyan_mine](http://twitter.com/namuyan_mine/)

Licence
----
[MIT](https://opensource.org/licenses/MIT)
