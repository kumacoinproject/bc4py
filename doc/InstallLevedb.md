Install levelDB
====
two libraries
* [plyvel](https://github.com/wbolster/plyvel) for linux and ARM
* [python-leveldb](https://github.com/happynear/py-leveldb-windows) for linux and windows

For windows
----
please look [py-leveldb-windows](https://github.com/happynear/py-leveldb-windows)

For linux
----
`pip install plyvel` or `pip install leveldb`

For ARMs
----
[leveldb-1.20-build](https://tangerina.jp/blog/leveldb-1.20-build/)

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