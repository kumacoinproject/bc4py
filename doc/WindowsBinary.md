how to build windows binary
====
**this is old, use []() instead!**  
use [Nuitka](https://nuitka.net/) and [MSYS2 x86_64](https://www.msys2.org/)

build by
----
* Windows10 64bit
* Python 3.6.7 :: Anaconda custom (64-bit)
* Nuitka 0.6.5
* gcc (Rev2, Built by MSYS2 project) 8.3.0

replace modified libs
----
Changes is simple, good to edit when new commits come.
```bash
pip install -U git+https://github.com/namuyan/fastapi
pip install -U git+https://github.com/namuyan/uvicorn
```

command
----
```bash
python -m nuitka --mingw64 -j 2 --show-progress  --show-scons --recurse-all --standalone --windows-icon=favicon.ico \
--nofollow-import-to=cryptography \
--nofollow-import-to=numpy \
--nofollow-import-to=gevent \
--nofollow-import-to=matplotlib \
--nofollow-import-to=IPython \
--nofollow-import-to=Cython \
--nofollow-import-to=setuptools \
--nofollow-import-to=distutils \
publicnode.py
rm -r publicnode.build
```

fix
----
* `OSError: Cannot load native module 'Cryptodome.Hash._RIPEMD160': Trying '_RIPEMD160.cp36-win_amd64.pyd'`
copy *site-packages/Cryptodome/Hash/_RIPEMD160.cp36-win_amd64.pyd* to *Cryptodome/Hash/_RIPEMD160.pyd*

* `ctypes.WinError` on `\lib\site-packages\nuitka\utils\WindowsResources.py`
[just add two lines](https://github.com/Nuitka/Nuitka/issues/468#issuecomment-532633902)
