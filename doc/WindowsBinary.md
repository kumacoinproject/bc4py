how to build windows binary
====
use [Nuitka](https://nuitka.net/) and [MSYS2 x86_64](https://www.msys2.org/)

build by
----
* Windows10 64bit
* Python 3.6.7 :: Anaconda custom (64-bit)
* Nuitka 0.6.5
* gcc (Rev2, Built by MSYS2 project) 8.3.0

command
----
[nuitka args](https://gist.github.com/namuyan/9d76f3c288ef0f217ae342e2bde046fc)
```bash
# compile
python -m nuitka --mingw64 -j 2 --show-progress --recurse-all --standalone --windows-icon=favicon.ico publicnode.py
rm -r publicnode.build
```

fix
----
* `OSError: Cannot load native module 'Cryptodome.Hash._RIPEMD160': Trying '_RIPEMD160.cp36-win_amd64.pyd'`
copy *site-packages/Cryptodome/Hash/_RIPEMD160.cp36-win_amd64.pyd* to *Cryptodome/Hash/_RIPEMD160.pyd*
