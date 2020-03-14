bc4py
=============================
[bc4py](https://github.com/kumacoinproject/bc4py)\(blockchain-for-python) enables you to
create blockchain application by Python3.

Function
----
* UTXO base
* PoW, PoS and PoC multi-consensus
* Minting colored coin

Requirement
----
* Windows/Linux
* **Python3.6+**
* **Rust nightly**
* [p2p-python](https://github.com/namuyan/p2p-python)
* LevelDB
* hash function
    * [yespower-python](https://github.com/namuyan/yespower-python)  For CPU
    * [x16s-hash](https://pypi.org/project/shield-x16s-hash/) for GPU
    * [x11_hash](https://pypi.org/project/x11_hash/) For ASIC
* Python extension [bc4py-extension](https://github.com/namuyan/bc4py_extension)
* plotting tool [bc4py-plotter](https://github.com/namuyan/bc4py_plotter)

Install
----
```commandline
cd ~
git clone https://github.com/kumacoinproject/bc4py
rm -r doc tests
mv bc4py blockchain-py
cd blockchain-py
pip3 install --user -r requirements.txt
pip3 install --user -r requirements-c.txt
wget http://example.com/boot.json
```

Start node
----
* `python3 localnode.py` Node working on local env, for debug.
* `python3 publicnode.py` Node with mining/staking.

Documents
----
* [Create genesis block](doc/GenesisBlock.md)
* [How to mining](doc/Mining.md)
* [testnet API document](https://testnet.kumacoin.dev/docs)
* [About development](doc/Development.md)
* [About new offer about program](doc/AboutPullrequest.md)
* [HTTPS proxy introduction](doc/Proxy.md)
* [Proof of capacity](doc/AboutPoC.md)
* [Install LevelDB](doc/InstallLevedb.md)
* [how to build windows binary](doc/WindowsBinary.md)

Licence
----
MIT

Author
----
[@namuyan_mine](http://twitter.com/namuyan_mine/)
