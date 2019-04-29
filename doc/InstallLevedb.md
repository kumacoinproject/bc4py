Install levelDB
====
You can use [plyvel](https://github.com/wbolster/plyvel for Linux, Winodws and arm.

For windows
----
* Do yourself (recommend) [How to install plyvel on wondows](https://gist.github.com/namuyan/1a8aef3482fa17c6b206ff028efc9807)
* Use binary [plyvel-1.0.5-cp36-cp36m-win_amd64.whl](https://mega.nz/#!q1tziQoK!ehA-iCtkQukh1-AEgk0yLb4CJAfqRYr8VeE0UtdOFus)
* Use binary [plyvel-1.0.5-cp37-cp37m-win_amd64.whl](https://mega.nz/#!uldTCCYK!ctwUgfggBVskKvm5ePS_Q6lFK9RyGiqLKA473dQo2vY)

For linux
----
`pip3 install --user plyvel`

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
