Contract
====

get contract info
----
* Arguments
    1. c_address (string, required) Contract address
    2. confirmed (bool, optional, default=False)
* Request example
    * `curl -H "accept: application/json" "127.0.0.1:3000/public/getcontractinfo?c_address="`
* Response
```json
{
    "c_address": "CJ4QZ7FDEH5J7B2O3OLPASBHAFEDP6I7UKI2YMKF",
    "index": 0,
    "binary": "800495a0010000000000008c0964696c6c2e64696c6c948c0c5f6372656174655f747970659493942868008c0a5f6c6f61645f747970659493948c047479706594859452948c08436f6e74726163749468048c066f626a656374948594529485947d94288c0a5f5f6d6f64756c655f5f948c085f5f6d61696e5f5f948c075f5f646f635f5f944e8c085f5f696e69745f5f9468008c105f6372656174655f66756e6374696f6e9493942868048c08436f6465547970659485945294284b034b004b034b024b4343107c017c005f007c027c005f0164005300944e85948c0873746172745f7478948c09635f616464726573739486948c0473656c66946819681a8794680868114b02430400010601942929749452946362633470792e636f6e74726163742e746f6f6c730a5f5f646963745f5f0a68114e4e7d94749452948c0474657374946813286816284b014b004b024b014b47430464005300944e859429681c8c0461726773948694680868244b0643020001942929749452946362633470792e636f6e74726163742e746f6f6c730a5f5f646963745f5f0a68244e4e7d947494529475749452942e",
    "extra_imports": [],
    "storage_key": 1,
    "settings": {
        "update_binary": true,
        "update_extra_imports": true
    },
    "start_hash": "c6a350a6771343427eff7fbf276122eac1d242e03a9b26d654ede3b272eda1fe",
    "finish_hash": "1b9a9796bca2498f3b678506e6a82ea6416d2a321e4978516aff46598a6b73c3"
}
```
* About

get validator info
----
* Arguments
    1. c_address     (string, required)  Contract address
    2. confirmed     (bool, optional, default=False)
* Request example
    * `curl -H "accept: application/json" "127.0.0.1:3000/public/getvalidatorinfo?c_address=CJ4QZ7FDEH5J7B2O3OLPASBHAFEDP6I7UKI2YMKF"`
* Response
```json
{
    "index": 3,
    "c_address": "CJ4QZ7FDEH5J7B2O3OLPASBHAFEDP6I7UKI2YMKF",
    "txhash": "9e4306c13294d4fcfec0d20df3b5eaf73298bf306b8830807e706192772348bf",
    "validators": [
        "ND4BYUUA2UR73IPV5VSLJSMXDUB2EK3EYW5CDFUH",
        "NDI7ULZEZUWC6HFQUBUKPACSVYCDOBBD4AGYFHUC",
        "NAK4BSD64AGCTF3X7ZQWYQPHKGHE46SWEN2QZCZ3",
        "NBCJ4KQEDOK7HZ3LCMVXUPPIXXXYJMEXFNWC3RIR"
    ],
    "require": 2
}
```
* About
    * txhash is last validator edit txhash

get contract history
----
* Arguments
    1. c_address (string, required) Contract address
* Request example
    * `curl -H "accept: application/json" "127.0.0.1:3000/public/getcontracthistory?c_address="`
* Response
```json
[
    {
        "index": 0,
        "height": 5491,
        "start_hash": "84f93861468f4f6ef97dbfd858154a92be89630f567f13c30363417314a003c6",
        "finish_hash": "591a594d3aa2664972498f666708ab807c0a34ca5e63e355f6211a24baa830d3",
        "c_method": "init",
        "c_args": [
            "\u0004\u0001\u0000\u0000\u0000\u0000\u0000\u0000\tdill.dill\f_create_type(h\u0000\n_load_type\u0004typeR\bContracth\u0004\u0006objectR}(\n__module__\b__main__\u0007__doc__N\b__init__h\u0000\u0010_create_function(h\u0004\bCodeTypeR(K\u0003K\u0000K\u0003K\u0002KCC\u0010|\u0001|\u0000_\u0000|\u0002|\u0000_\u0001d\u0000S\u0000N\bstart_tx\tc_address\u0004selfh\u0019h\u001ah\bh\u0011K\u0002C\u0004\u0000\u0001\u0006\u0001))tRcbc4py.contract.tools\n__dict__\nh\u0011NN}tR\u0004testh\u0013(h\u0016(K\u0001K\u0000K\u0002K\u0001KGC\u0004d\u0000S\u0000N)h\u001c\u0004argsh\bh$K\u0006C\u0002\u0000\u0001))tRcbc4py.contract.tools\n__dict__\nh$NN}tRutR.",
            null,
            null
        ],
        "c_storage": {
            "hello": "world"
        }
    }
]
```
* About

get validator history
----
* Arguments
    1. c_address (string, required) Contract address
* Request example
    * `curl -H "accept: application/json" "127.0.0.1:3000/public/getvalidatorhistory?c_address="`
* Response
```json
[
    {
        "index": 0,
        "height": 5437,
        "new_address": "NDYV57BQ6QZAVETWEH2S6M3B7U4AZYK5RQNYWQQL",
        "flag": 1,
        "txhash": "2a1e1ef938b61ac2030f02b199381830254c02533940e55e2ad785bc4d11247a",
        "sig_diff": 1
    },
    {
        "index": 1,
        "height": 5475,
        "new_address": "NB6E2YDFCNTTX5RAM7AYMVU5476ZB2TIS6ELSX2Z",
        "flag": 1,
        "txhash": "4c58adc2f2d1a27e4f135119d0f41b70d0781d6745148f16b327e984265922a8",
        "sig_diff": 0
    }
]
```
* About

get contract storage
----
* Arguments
    1. c_address     (string, required)  Contract address
    2. confirmed     (bool, optional, default=False)
* Request example
    * `curl -H "accept: application/json" "127.0.0.1:3000/public/contractstorage?c_address=CJ4QZ7FDEH5J7B2O3OLPASBHAFEDP6I7UKI2YMKF"`
* Response
```json
{
    "hello": "world"
}
```
* About

get watching info
----
* Arguments
    1. pickle     (bool, optional, default=False) tx data by pickled
* Request example
    * `curl -H "accept: application/json" "127.0.0.1:3000/private/watchinginfo"`
* Response
```json
[
    {
        "hash": "5f5a501fdf78fdde11ed8dd3917af20afdc40df6244d8011e3c0f7df5819ba96",
        "type": 8,
        "tx": "<TX None VALIDATOR_EDIT 5f5a501fdf78fdde11ed8dd3917af20afdc40df6244d8011e3c0f7df5819ba96>",
        "time": 1542958260.0427983,
        "c_address": "CJ4QZ7FDEH5J7B2O3OLPASBHAFEDP6I7UKI2YMKF",
        "related": [
            [
                "@Unknown",
                "NDYV57BQ6QZAVETWEH2S6M3B7U4AZYK5RQNYWQQL"
            ]
        ],
        "args": [
            "NDYV57BQ6QZAVETWEH2S6M3B7U4AZYK5RQNYWQQL",
            -1,
            -1
        ]
    }
]
```
* About
    * Do not use pickle data from outside because of security risk. 
    * default disabled function. require `close_contract_watch()`
    * Your account related contract/validator tx displayed, check update by **time**.
    * If you want to sign, use **/private/validateunconfirmed** method.

source compile
----
dummy contract
```python
class Contract:
    def __init__(self, start_tx, c_address):
        self.start_tx = start_tx
        self.c_address = c_address
    
    def test(self, *args):
        return
```
disassembled source
```text
Disassembly of __init__:
  3           0 LOAD_FAST                1 (start_tx)
              2 LOAD_FAST                0 (self)
              4 STORE_ATTR               0 (start_tx)
    
  4           6 LOAD_FAST  2 (c_address)
              8 LOAD_FAST                0 (self)
             10 STORE_ATTR               1 (c_address)
             12 LOAD_CONST               0 (None)
             14 RETURN_VALUE
    
Disassembly of test:
  7   0 LOAD_CONST               0 (None)
              2 RETURN_VALUE
```

* Arguments
    1. source  (string, optional, default=None)  
    2. path    (file path, optional, default=None)
* Request example
    * by source `curl  --basic -u user:password "127.0.0.1:3000/private/sourcecompile" -H "Accept: application/json" -H "Content-Type: application/json" -d "{\"source\": \"class Contract:\n    def __init__(self, start_tx, c_address):\n        self.start_tx = start_tx\n        self.c_address = c_address\n\n    def test(self, *args):\n        return\n\"}"`
    * by filepath `curl  --basic -u user:password "127.0.0.1:3000/private/sourcecompile" -H "Accept: application/json" -H "Content-Type: application/json" -d "{\"path\": \"C:\\Users\\pycoin\\Source\\eample.py\"}"`
* Response
```json
{
    "hex": "800495a0010000000000008c0964696c6c2e64696c6c948c0c5f6372656174655f747970659493942868008c0a5f6c6f61645f747970659493948c047479706594859452948c08436f6e74726163749468048c066f626a656374948594529485947d94288c0a5f5f6d6f64756c655f5f948c085f5f6d61696e5f5f948c075f5f646f635f5f944e8c085f5f696e69745f5f9468008c105f6372656174655f66756e6374696f6e9493942868048c08436f6465547970659485945294284b034b004b034b024b4343107c017c005f007c027c005f0164005300944e85948c0873746172745f7478948c09635f616464726573739486948c0473656c66946819681a8794680868114b02430400010601942929749452946362633470792e636f6e74726163742e746f6f6c730a5f5f646963745f5f0a68114e4e7d94749452948c0474657374946813286816284b014b004b024b014b47430464005300944e859429681c8c0461726773948694680868244b0643020001942929749452946362633470792e636f6e74726163742e746f6f6c730a5f5f646963745f5f0a68244e4e7d947494529475749452942e",
    "dis": "Disassembly of __init__:\n  3           0 LOAD_FAST                1 (start_tx)\n              2 LOAD_FAST                0 (self)\n              4 STORE_ATTR               0 (start_tx)\n\n  4           6 LOAD_FAST                2 (c_address)\n              8 LOAD_FAST                0 (self)\n             10 STORE_ATTR               1 (c_address)\n             12 LOAD_CONST               0 (None)\n             14 RETURN_VALUE\n\nDisassembly of test:\n  7           0 LOAD_CONST               0 (None)\n              2 RETURN_VALUE\n\n"
}
```
* About
    * dummy contract, not work, no meanings. Just for example.
    * dis is disassembled source.
    * This tx is not special tx until conclude tx generated by validators.

contract init
----
* Arguments
    1. c_address      (string, required) Contract address
    2. hex            (hex string, required) Contract binary
    3. extra_imports  (list, optional, default=None)
    4. settings       (dict, optional, default=None)
    5. send_pairs     (list, optional, default=None)
    6. from           (string, optional, default="@Unknown")
* Request example
    * `curl  --basic -u user:password "127.0.0.1:3000/private/contractinit" -H "Accept: application/json" -H "Content-Type: application/json" -d "{\"c_address\": \"CJ4QZ7FDEH5J7B2O3OLPASBHAFEDP6I7UKI2YMKF\", \"hex\": \"800495a0010000000000008c0964696c6c2e64696c6c948c0c5f6372656174655f747970659493942868008c0a5f6c6f61645f747970659493948c047479706594859452948c08436f6e74726163749468048c066f626a656374948594529485947d94288c0a5f5f6d6f64756c655f5f948c085f5f6d61696e5f5f948c075f5f646f635f5f944e8c085f5f696e69745f5f9468008c105f6372656174655f66756e6374696f6e9493942868048c08436f6465547970659485945294284b034b004b034b024b4343107c017c005f007c027c005f0164005300944e85948c0873746172745f7478948c09635f616464726573739486948c0473656c66946819681a8794680868114b02430400010601942929749452946362633470792e636f6e74726163742e746f6f6c730a5f5f646963745f5f0a68114e4e7d94749452948c0474657374946813286816284b014b004b024b014b47430464005300944e859429681c8c0461726773948694680868244b0643020001942929749452946362633470792e636f6e74726163742e746f6f6c730a5f5f646963745f5f0a68244e4e7d947494529475749452942e\"}"`
* Response
```json
{
    "hash": "c6a350a6771343427eff7fbf276122eac1d242e03a9b26d654ede3b272eda1fe",
    "gas_amount": 761,
    "gas_price": 100,
    "fee": 76100,
    "time": 0.15
}
```
* About
    * validators need to create contract conclude tx to be confirmed.

contract update
----
* Arguments
    1. c_address      (string, required) Contract address
    2. hex            (hex string, optional, default=None) Contract binary
    3. extra_imports  (list, optional, default=None)
    4. settings       (dict, optional, default=None)
    5. send_pairs     (list, optional, default=None)
    6. from           (string, optional, default="@Unknown")
* Request example
    * `curl --basic -u user:password "127.0.0.1:3000/private/contractupdate" -H "Accept: application/json" -H "Content-Type: application/json" -d "{\"c_address\": \"CJ4QZ7FDEH5J7B2O3OLPASBHAFEDP6I7UKI2YMKF\", \"settings\": {\"update_extra_imports\": false}}"`
* Response
```json
{
    "hash": "a8162b82f8a8ac0eafbeaf092df347b353099fd16ed72fb6df3c682ca843d8e6",
    "gas_amount": 359,
    "gas_price": 100,
    "fee": 35900,
    "time": 0.083
}
```
* About

contract transfer
----
* Arguments
    1. c_address      (string, required) Contract address
    2. c_method       (string, required)
    3. c_args         (list, required) 
    4. send_pairs     (list, optional, default=None)
    5. from           (string, optional, default="@Unknown")
* Request example
    * `curl --basic -u user:password "127.0.0.1:3000/private/contracttransfer" -H "Accept: application/json" -H "Content-Type: application/json" -d "{\"c_address\": \"CJ4QZ7FDEH5J7B2O3OLPASBHAFEDP6I7UKI2YMKF\", \"c_method\": \"test\", \"c_args\": []}"`
* Response
```json
{
    "hash": "aad2397ed2bf9d85d99f992777cf6f94ff170df33b0b1c5d48576c81b8f70d62",
    "gas_amount": 328,
    "gas_price": 100,
    "fee": 32800,
    "time": 0.21
}
```
* About

conclude contract
----
* Arguments
    1. c_address     (string, required)  Contract address
    2. start_hash    (hex string, required)
    3. send_pairs    (list, optional, default=None)  `[(address, coin_id, amount),..]`
    4. storage       (dict, optional, default=None)
* Request example
    * `curl --basic -u user:password "127.0.0.1:3000/private/concludecontract" -H "Accept: application/json" -H "Content-Type: application/json" -d "{\"c_address\": \"CJ4QZ7FDEH5J7B2O3OLPASBHAFEDP6I7UKI2YMKF\", \"start_hash\": \"c6a350a6771343427eff7fbf276122eac1d242e03a9b26d654ede3b272eda1fe\", \"storage\": {\"hello\": \"world\"}}"`
* Response
```json
{
    "hash": "1b9a9796bca2498f3b678506e6a82ea6416d2a321e4978516aff46598a6b73c3",
    "gas_amount": 20415,
    "gas_price": 100,
    "fee": 2041500,
    "time": 0.13
}
```

validator edit
----
* Arguments
    1. c_address     (string, required)  Contract address
    2. new_address   (string, optional, default=None)  new/remove validator address
    3. flag          (numeric, optional, default=F_NOP)  validator address action
    4. sig_diff      (numeric, optional, default=0)  min require sign number edit
* Request example
    * init validator address `curl --basic -u user:password 127.0.0.1:3000/private/validatoredit -H "Accept: application/json" -H "Content-Type: application/json" -d "{\"c_address\": \"CJ4QZ7FDEH5J7B2O3OLPASBHAFEDP6I7UKI2YMKF\", \"new_address\": \"NAKZXFAZTMNU2USCMQ26ATI2SLURCILJ6RKV35KV\", \"flag\": 1, \"sig_diff\": 1}"`
    * change 1of2multisig `curl --basic -u user:password 127.0.0.1:3000/private/validatoredit -H "Accept: application/json" -H "Content-Type: application/json" -d "{\"c_address\": \"CJ4QZ7FDEH5J7B2O3OLPASBHAFEDP6I7UKI2YMKF\", \"new_address\": \"NCHKSVGZGGIQX6WMBAJBDNMRPNNHJ343MOFWOCDA\", \"flag\": 1, \"sig_diff\": 0}"`
* Response
```json
{
    "hash": "38eed24cbdd59c55c7f0ca459d5346256d36aec324d5ab46f2e9237c8ceba98e",
    "gas_amount": 10030507,
    "gas_price": 100,
    "fee": 1003050700,
    "time": 0.084
}
```
* About
    * Contract address's balance required, need to send ny initially.
    * new_address is normal address only.
    * flag is 0\(NOP), 1(ADD) or -1(REMOVE).
    * sig_diff is -255~+255, difference of cosigner number compared before stats.

validate unconfirmed tx
----
* Arguments
* Request example
    * `curl --basic -u user:password "127.0.0.1:3000/private/validateunconfirmed" -H "Accept: application/json" -H "Content-Type: application/json" -d "{\"hash\": \"1b9a9796bca2498f3b678506e6a82ea6416d2a321e4978516aff46598a6b73c3\"}"`
* Response
```json
{
    "hash": "1b9a9796bca2498f3b678506e6a82ea6416d2a321e4978516aff46598a6b73c3",
    "gas_amount": 20415,
    "gas_price": 100,
    "fee": 2041500,
    "time": 0.108
}
```
* About
