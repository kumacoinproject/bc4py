About Mining
====
* mining interface
    * [getwork](https://en.bitcoin.it/wiki/Getwork)
    * [getblocktemplete](https://en.bitcoin.it/wiki/Getblocktemplate)
    * [~~stratum~~](https://en.bitcoin.it/wiki/Stratum_mining_protocol) not work...
* mining software
    * cpuminer (for CPU)
    * ccminer (for GPU nvidia)
    * sgminer (for GPU AMD)
    * cgminer (for ASIC)
    * and etc..
* **important**
    * Miner notify server algo by `password` integer, please check [config.py](/bc4py/config.py).
    * Please at your own risk about using binaries.

Example for Yespower
----
Yespoer's version is `0.9` or `1.0`, so can't use Bitzeny7s miner. 
You need to use [cpuminer-opt](https://github.com/bellflower2015/cpuminer-opt),
[Binary](https://github.com/bellflower2015/cpuminer-opt/releases).
Thank to bellflower2015!

```commandline
cpuminer-sse2 -a yespower -o http://127.0.0.1:3000/json-rpc -u USERNAME -p 1 --no-getwork --no-longpoll --no-stratum
pause
```

Example for HMQ1725
----
**HMQ1725** has been famous for [ESP](https://github.com/CryptoCoderz/Espers).
You can mine by [cpuminer-hmq1725](https://github.com/CryptoCoderz/cpuminer-hmq1725) or
[sgminer_HMQ1725](https://github.com/CryptoCoderz/sgminer_HMQ1725),
please look [HMQ1725 algorithm – List of HMQ1725 coins and mining software’s](https://coinguides.org/hmq1725-algorithm-coins-miner/)

For cpuminer-hmq1725, hmq1725 is suitable for AMD GPU, I hear.
```commandline
cpuminer -a hmq1725 -o http://127.0.0.1:3000/json-rpc -u user -p 5
pause
```

Example for X11
----
You can mine **X11** by DU-1, D1, D2 and D3, It's suitable for ASIC,
please look [PinIdea X11 USB ASIC Miner DU-1 Coming Soon](https://cryptomining-blog.com/tag/x11-miner-du-1/).
Note: PinIdea deleted modified **ASIC-X11-Miner**,
you can download from [Dash forum](https://www.dash.org/forum/threads/pinidea-asic-x11-miner-du-1-usb-version-hashrate-9-mh-s-releasing-in-mid-may-2016.8624/page-6),
but it many be very unsafe.

```commandline
cgminer --x11 -o http://127.0.0.1:3000/json-rpc -u user -p 4 --dr1-clk 300 --dr1-fan LV1 -S //./COM5 --du1
pause
```
