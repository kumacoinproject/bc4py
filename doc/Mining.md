About Mining
====
We provide mining interface
[getwork](https://en.bitcoin.it/wiki/Getwork), 
[getblocktemplete](https://en.bitcoin.it/wiki/Getblocktemplate) and
[stratum](https://github.com/namuyan/bc4py-stratum-pool).
You can mine by cpuminer, ccminer, sgminer, cgminer and stratum pool with no modification.

important
----
* Miner notify server hash algorithm by `password` integer, please select by [config.py](/bc4py/config.py).
* We mimic block header structure of Bitcoin, so you can use general mining tools with no modification.
But it depends on program, because coinbase transaction is differ from Bitcoin's.
* Please at your own risk about using a mining tool.

yespower
----
Yespower1.0 is anti GPU/ASIC hash algorithm and next generation of yescrypt.
* [cpuminer-opt](https://github.com/bellflower2015/cpuminer-opt)
* [Binary](https://github.com/bellflower2015/cpuminer-opt/releases)

```commandline
cpuminer-sse2 -a yespower -o http://127.0.0.1:3000 -u USERNAME -p 5 --no-getwork --no-longpoll --no-stratum
```

X11
----
You can mine by ASIC.
please look [PinIdea X11 USB ASIC Miner DU-1 Coming Soon](https://cryptomining-blog.com/tag/x11-miner-du-1/).
* [sgminer-nicehash for GPU](https://github.com/nicehash/sgminer)
* [X11-Miner binaries](https://github.com/stellawxo/X11-Miner)

```commandline
cgminer --x11 -o http://127.0.0.1:3000 -u user -p 6 --dr1-clk 300 --dr1-fan LV1 -S //./COM5 --du1
```

```commandline
sgminer -k x11 -o http://127.0.0.1:3000 -u user -p 6
```

X16S
----
* [avermore-miner](https://github.com/brian112358/avermore-miner)
* [sgminer-kl](https://github.com/KL0nLutiy/sgminer-kl)
```commandline
sgminer -k x16s -o http://127.0.0.1:3000 -u user -p 9
```
