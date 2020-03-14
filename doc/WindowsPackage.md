how to setup windows package
====
Use embedded python because of sustainable work instead of Nuitka3.

prepare
----
* [python-3.7.6-embed-amd64.zip](https://www.python.org/ftp/python/3.7.6/python-3.7.6-embed-amd64.zip)
* [MSYS2 x86_64](https://www.msys2.org/)
* requirements-cp37

setup
----
open MSYS2 commandline
1. `cd python-3.X.X-embed-amd64`
2. `sed -i -e "s/\# import site/import site/" python37._pth`
3. install pip
    * `wget "https://bootstrap.pypa.io/get-pip.py" -O "get-pip.py"`
    * `./python.exe get-pip.py && rm get-pip.py`
4. setup bc4py
    * `git clone -b develop https://github.com/namuyan/bc4py`
    * `./python.exe -m pip install -r bc4py/requirements.txt`
    * `./python.exe -m pip install requirements-cp37/* && rm -r requirements-cp37`
    * `mv bc4py bc4py_old && mv "bc4py_old/bc4py" bc4py && mv "bc4py_old/publicnode.py" . && rm -rf bc4py_old`
5. check execute `./python.exe publicnode.py -h`
6. clear cache `find * \! -type f | grep "__pycache__" | xargs -d \\n rm -r`

build *requirements-cp37* by yourself
----
embedded python don't have compile function, so you install another normal python.  
check compile required libs [requirements-c.txt](https://github.com/kumacoinproject/bc4py/blob/develop/requirements-c.txt)

1. `mkdir requirements-cp37 && cd requirements-cp37`
2. `python.exe -m pip wheel -r ../bc4py/requirements-c.txt`

trouble shooting
----
* plyvel: https://github.com/ppolxda/plyvel/releases/tag/1.1.0.build-v0-win
* -lmsvcr140 not found: https://teratail.com/questions/238135
* fastecdsa cause coredump => https://pypi.org/project/fastecdsa-any/
