About Mining
====
We provide mining interface
[getwork](https://en.bitcoin.it/wiki/Getwork), 
[getblocktemplete](https://en.bitcoin.it/wiki/Getblocktemplate) and
[~~stratum~~ developing](/bc4py/user/stratum).
You can mine by cpuminer, ccminer, sgminer, cgminer with no modification.

important
----
* Miner notify server hashing algorithm by `password` integer, please select by [config.py](/bc4py/config.py).
* We mimic block header structure of Bitcoin, so you can use general mining tools with no modification.
But it depends on program, because coinbase transaction is differ from Bitcoin's.
* Please at your own risk about using a mining tool.

yespower
----
Yespower1.0 is anti GPU/ASIC hashing algorithm and next generation of yescrypt.
* [cpuminer-opt](https://github.com/bellflower2015/cpuminer-opt)
* [Binary](https://github.com/bellflower2015/cpuminer-opt/releases)

```commandline
cpuminer-sse2 -a yespower -o http://127.0.0.1:3000/json-rpc -u USERNAME -p 5 --no-getwork --no-longpoll --no-stratum
```

X11
----
You can mine by ASIC.
please look [PinIdea X11 USB ASIC Miner DU-1 Coming Soon](https://cryptomining-blog.com/tag/x11-miner-du-1/).
* [sgminer-nicehash for GPU](https://github.com/nicehash/sgminer)
* [X11-Miner binaries](https://github.com/stellawxo/X11-Miner)

```commandline
cgminer --x11 -o http://127.0.0.1:3000/json-rpc -u user -p 6 --dr1-clk 300 --dr1-fan LV1 -S //./COM5 --du1
```

```commandline
sgminer -k x11 -o http://127.0.0.1:3000/json-rpc -u user -p 6
```

HMQ1725
----
**HMQ1725** has been famous for [ESP](https://github.com/CryptoCoderz/Espers).
* [cpuminer-hmq1725](https://github.com/CryptoCoderz/cpuminer-hmq1725)
* [tpruvot-ccminer](https://github.com/tpruvot/ccminer).
* [HMQ1725 algorithm – List of HMQ1725 coins and mining software’s](https://coinguides.org/hmq1725-algorithm-coins-miner/)

I hear hmq1725 is suitable for AMD GPU.
```commandline
cpuminer -a hmq1725 -o http://127.0.0.1:3000/json-rpc -u user -p 7
```

X16R
----
* [avermore-miner](https://github.com/brian112358/avermore-miner)
```commandline
sgminer -k x16r -o http://127.0.0.1:3000/json-rpc -u user -p 9
```
