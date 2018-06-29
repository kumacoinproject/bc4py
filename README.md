bc4py (blockchain-for-python)
=============================
It enable you to create application with blockchain on Python3.

Function
--------
* UTXO base
* Proof of work or/and proof of stake consensus
* Minting colored coin (Not token)
* Python interpreter based smart contract (PyContract)
* block containing result smart contract　(differ from Ethereum)

Requirement
----------
* Windows/Linux
* Python3 (3.5, 3.6~)
* [nem-ed25519](https://github.com/namuyan/nem-ed25519)
* [p2p-python](https://github.com/namuyan/p2p-python)

Install
-------
`python setup.py install`  
or  
`pip install git+https://github.com/namuyan/bc4py`  
and  
`pip install git+https://github.com/namuyan/yescryptR16-python.git`

Create genesis block
--------------------
* [Create genesis block](doc/GenesisBlock.md)


Build for windows
-----------------
`nuitka3 --mingw --recurse-none publicnode.py`

Author
------
[@namuyan_mine](http://twitter.com/namuyan_mine/)

Licence
-------
[MIT](LICENSE)
