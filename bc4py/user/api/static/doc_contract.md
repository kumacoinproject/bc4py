Contract
====

get contract info
----
* Arguments
    1. c_address (string, required)
    2. v_address (string, required) 
    3. confirmed (bool, optional, default=False)
    4. stophash  (hex, optional, default=False)
* Request example
    * `curl -H "accept: application/json" "127.0.0.1:3000/public/getcontractinfo?c_address="`
* Response
```json
{
    "c_address": "CJ4QZ7FDEH5J7B2O3OLPASBHAFEDP6I7UKI2YMKF",
    "v_address": "VRYXNX2RRHBJIMUYGVU473FFZ6IFAHNBUBBZANDB",
    "db_index": 3474628541656,
    "version": 0,
    "binary": "83aa5f636f6e74726163745fac436f6e747261637454797065a86e616d6532666e6382a467616d6582aa5f636f6e74726163745fac46756e6374696f6e54797065a46461746187a85f5f636f64655f5f82aa5f636f6e74726163745fa8436f646554797065a4646174619f0100090447c4da74007c016401190083017d027c006a016a0283007d0374037c006a046a0564028d017d0474066a077c046a0864038302640416007d0574097c006a047c006a0a7c006a0b83037d067c067c006a0b19006401190064051a007d077c02726664067c056b0073747c020c00729e64067c056b05729e7c006a016407050019006408370003003c007c067c006a0b19006401050019007c07370003003c006e287c006a016409050019006408370003003c007c067c006a0b19006401050019007c07380003003c007c006a016a0c7c0383017d087c067c08660253009ac00091a6686569676874a3626967cd010002cc80a377696e01a46c6f73659da4626f6f6ca9635f73746f72616765a4636f7079ad6765745f626c6f636b5f6f626aa873746172745f7478a6686569676874a3696e74aa66726f6d5f6279746573a468617368b363616c635f72657475726e5f62616c616e6365a9635f61646472657373ae72656465656d5f61646472657373ab6578706f72745f6469666699a473656c66a461726773a6665f68696768aa635f6f726967696e616ca5626c6f636ba8686173685f696e74a772657475726e73aa77696e5f616d6f756e74a6635f64696666a0a467616d6523c41a00020c020a040e011204120312021a0212011803120116030c049090a85f5f6e616d655f5fa467616d65ac5f5f64656661756c74735f5fc0ab5f5f636c6f737572655f5fc0a85f5f646963745f5f80a75f5f646f635f5fc0ae5f5f6b7764656661756c74735f5fc0a675706461746582aa5f636f6e74726163745fac46756e6374696f6e54797065a46461746187a85f5f636f64655f5f82aa5f636f6e74726163745fa8436f646554797065a4646174619f0100020247c40c74006401830182016400530092c0b94d616e75616c6c79207570646174652072657175697265642e91a9457863657074696f6e92a473656c66a461726773a0a6757064617465cc86c40200019090a85f5f6e616d655f5fa6757064617465ac5f5f64656661756c74735f5fc0ab5f5f636c6f737572655f5fc0a85f5f646963745f5f80a75f5f646f635f5fc0ae5f5f6b7764656661756c74735f5fc0aa6e616d6532636f6e737480",
    "extra_imports": [],
    "storage_key": 2,
    "settings": {
        "update_binary": true,
        "update_extra_imports": true
    },
    "start_hash": "3cf3349611b49848277a0c521508282010e0a49f5148df144e9da1c17de39ba3",
    "finish_hash": "7900ace4bb8a94ebc7d4e5aa32172c764a0758373b1f223e97255d46ed0c1fbe"
}
```
* About

get validator info
----
* Arguments
    1. v_address     (string, required)  Contract address
    2. confirmed     (bool, optional, default=False)
    3. stophash  (hex, optional, default=False)
* Request example
    * `curl -H "accept: application/json" "127.0.0.1:3000/public/getvalidatorinfo?v_address=VRYXNX2RRHBJIMUYGVU473FFZ6IFAHNBUBBZANDB"`
* Response
```json
{
    "db_index": 2435246456266,
    "index": 1,
    "v_address": "VRYXNX2RRHBJIMUYGVU473FFZ6IFAHNBUBBZANDB",
    "txhash": "8f1ce28d94624a9b008a58777e6b137b5d8705c6a923e7f4b6fdc5615381b105",
    "validators": [
        "NC5C2YP4RIF7XEYZC5UE2OHEAC45KSAPAICO2WQQ",
        "NCEROED7J5AGEO5SBXHARZNUWPVCCIZ4AER7HSV5"
    ],
    "require": 1
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
        "index": 3474628541656,
        "height": 839,
        "status": "memory",
        "start_hash": "3cf3349611b49848277a0c521508282010e0a49f5148df144e9da1c17de39ba3",
        "finish_hash": "7900ace4bb8a94ebc7d4e5aa32172c764a0758373b1f223e97255d46ed0c1fbe",
        "c_method": "init",
        "c_args": [
            "83aa5f636f6e74726163745fac436f6e747261637454797065a86e616d6532666e6382a467616d6582aa5f636f6e74726163745fac46756e6374696f6e54797065a46461746187a85f5f636f64655f5f82aa5f636f6e74726163745fa8436f646554797065a4646174619f0100090447c4da74007c016401190083017d027c006a016a0283007d0374037c006a046a0564028d017d0474066a077c046a0864038302640416007d0574097c006a047c006a0a7c006a0b83037d067c067c006a0b19006401190064051a007d077c02726664067c056b0073747c020c00729e64067c056b05729e7c006a016407050019006408370003003c007c067c006a0b19006401050019007c07370003003c006e287c006a016409050019006408370003003c007c067c006a0b19006401050019007c07380003003c007c006a016a0c7c0383017d087c067c08660253009ac00091a6686569676874a3626967cd010002cc80a377696e01a46c6f73659da4626f6f6ca9635f73746f72616765a4636f7079ad6765745f626c6f636b5f6f626aa873746172745f7478a6686569676874a3696e74aa66726f6d5f6279746573a468617368b363616c635f72657475726e5f62616c616e6365a9635f61646472657373ae72656465656d5f61646472657373ab6578706f72745f6469666699a473656c66a461726773a6665f68696768aa635f6f726967696e616ca5626c6f636ba8686173685f696e74a772657475726e73aa77696e5f616d6f756e74a6635f64696666a0a467616d6523c41a00020c020a040e011204120312021a0212011803120116030c049090a85f5f6e616d655f5fa467616d65ac5f5f64656661756c74735f5fc0ab5f5f636c6f737572655f5fc0a85f5f646963745f5f80a75f5f646f635f5fc0ae5f5f6b7764656661756c74735f5fc0a675706461746582aa5f636f6e74726163745fac46756e6374696f6e54797065a46461746187a85f5f636f64655f5f82aa5f636f6e74726163745fa8436f646554797065a4646174619f0100020247c40c74006401830182016400530092c0b94d616e75616c6c79207570646174652072657175697265642e91a9457863657074696f6e92a473656c66a461726773a0a6757064617465cc86c40200019090a85f5f6e616d655f5fa6757064617465ac5f5f64656661756c74735f5fc0ab5f5f636c6f737572655f5fc0a85f5f646963745f5f80a75f5f646f635f5fc0ae5f5f6b7764656661756c74735f5fc0aa6e616d6532636f6e737480",
            "VRYXNX2RRHBJIMUYGVU473FFZ6IFAHNBUBBZANDB",
            null,
            null
        ],
        "c_storage": {
            "win": 0,
            "lose": 0
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
    * `curl -H "accept: application/json" "127.0.0.1:3000/public/getvalidatorhistory?v_address=VRYXNX2RRHBJIMUYGVU473FFZ6IFAHNBUBBZANDB"`
* Response
```json
[
    {
        "index": 2177548418566,
        "height": 507,
        "new_address": "NC5C2YP4RIF7XEYZC5UE2OHEAC45KSAPAICO2WQQ",
        "flag": 1,
        "txhash": "53aa062c7069e351767c3c19837254fdcaffd46c733e3a60ecd1c5f560429991",
        "sig_diff": 1
    },
    {
        "index": 2435246456266,
        "height": 567,
        "new_address": "NCEROED7J5AGEO5SBXHARZNUWPVCCIZ4AER7HSV5",
        "flag": 1,
        "txhash": "8f1ce28d94624a9b008a58777e6b137b5d8705c6a923e7f4b6fdc5615381b105",
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
    3. stophash      (hex, optional, default=False)
    4. pickle        (bool, optional, default=False)
* Request example
    * `curl -H "accept: application/json" "127.0.0.1:3000/public/contractstorage?c_address=CJ4QZ7FDEH5J7B2O3OLPASBHAFEDP6I7UKI2YMKF"`
* Response
```json
{
    "win": 0,
    "lose": 0
}
```
* About

get watching info
----
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
        "address": "CJ4QZ7FDEH5J7B2O3OLPASBHAFEDP6I7UKI2YMKF",
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
    * Your account related contract/validator tx displayed, check update by **time**.
    * If you want to sign, use **/private/validateunconfirmed** method.

source compile
----
* Arguments
    1. path    (file path, optional, default=None)
* Request example
    * `curl  --basic -u user:password "127.0.0.1:3000/private/sourcecompile" -H "Accept: application/json" -H "Content-Type: application/json" -d "{\"path\": \"C:\\Users\\pycoin\\Source\\eample.py\"}"`
* Response
```json
{
    "hex": "800495a0010000000000008c0964696c6c2e64696c6c948c0c5f6372656174655f747970659493942868008c0a5f6c6f61645f747970659493948c047479706594859452948c08436f6e74726163749468048c066f626a656374948594529485947d94288c0a5f5f6d6f64756c655f5f948c085f5f6d61696e5f5f948c075f5f646f635f5f944e8c085f5f696e69745f5f9468008c105f6372656174655f66756e6374696f6e9493942868048c08436f6465547970659485945294284b034b004b034b024b4343107c017c005f007c027c005f0164005300944e85948c0873746172745f7478948c09635f616464726573739486948c0473656c66946819681a8794680868114b02430400010601942929749452946362633470792e636f6e74726163742e746f6f6c730a5f5f646963745f5f0a68114e4e7d94749452948c0474657374946813286816284b014b004b024b014b47430464005300944e859429681c8c0461726773948694680868244b0643020001942929749452946362633470792e636f6e74726163742e746f6f6c730a5f5f646963745f5f0a68244e4e7d947494529475749452942e",
    "dis": "Disassembly of __init__:\n  3           0 LOAD_FAST                1 (start_tx)\n              2 LOAD_FAST                0 (self)\n              4 STORE_ATTR               0 (start_tx)\n\n  4           6 LOAD_FAST                2 (c_address)\n              8 LOAD_FAST                0 (self)\n             10 STORE_ATTR               1 (c_address)\n             12 LOAD_CONST               0 (None)\n             14 RETURN_VALUE\n\nDisassembly of test:\n  7           0 LOAD_CONST               0 (None)\n              2 RETURN_VALUE\n\n"
}
```

contract init
----
* Arguments
    1. c_address      (string, required) Contract address
    2. v_address      (string, required) Validator address
    3. hex            (hex string, required) Contract binary
    4. extra_imports  (list, optional, default=None)
    5. settings       (dict, optional, default=None)
    6. send_pairs     (list, optional, default=None)
    7. from           (string, optional, default="@Unknown")
* Request example
    * `curl  --basic -u user:password "127.0.0.1:3000/private/contractinit" -H "Accept: application/json" -H "Content-Type: application/json" -d "{\"c_address\": \"CJ4QZ7FDEH5J7B2O3OLPASBHAFEDP6I7UKI2YMKF\", \"v_address\": \"VRYXNX2RRHBJIMUYGVU473FFZ6IFAHNBUBBZANDB\", \"hex\": \"83aa5f636f6e74726163745fac436f6e747261637454797065a86e616d6532666e6382a467616d6582aa5f636f6e74726163745fac46756e6374696f6e54797065a46461746187a85f5f636f64655f5f82aa5f636f6e74726163745fa8436f646554797065a4646174619f0100090447c4da74007
c016401190083017d027c006a016a0283007d0374037c006a046a0564028d017d0474066a077c046a0864038302640416007d0574097c006a047c006a0a7c006a0b83037d067c067c006a0b19006401190064051a007d077c02726664067c056b0073747c020c00729e64067c056b05729e7c006a016407050019
006408370003003c007c067c006a0b19006401050019007c07370003003c006e287c006a016409050019006408370003003c007c067c006a0b19006401050019007c07380003003c007c006a016a0c7c0383017d087c067c08660253009ac00091a6686569676874a3626967cd010002cc80a377696e01a46c6f7
3659da4626f6f6ca9635f73746f72616765a4636f7079ad6765745f626c6f636b5f6f626aa873746172745f7478a6686569676874a3696e74aa66726f6d5f6279746573a468617368b363616c635f72657475726e5f62616c616e6365a9635f61646472657373ae72656465656d5f61646472657373ab6578706f
72745f6469666699a473656c66a461726773a6665f68696768aa635f6f726967696e616ca5626c6f636ba8686173685f696e74a772657475726e73aa77696e5f616d6f756e74a6635f64696666a0a467616d6523c41a00020c020a040e011204120312021a0212011803120116030c049090a85f5f6e616d655f5
fa467616d65ac5f5f64656661756c74735f5fc0ab5f5f636c6f737572655f5fc0a85f5f646963745f5f80a75f5f646f635f5fc0ae5f5f6b7764656661756c74735f5fc0a675706461746582aa5f636f6e74726163745fac46756e6374696f6e54797065a46461746187a85f5f636f64655f5f82aa5f636f6e7472
6163745fa8436f646554797065a4646174619f0100020247c40c74006401830182016400530092c0b94d616e75616c6c79207570646174652072657175697265642e91a9457863657074696f6e92a473656c66a461726773a0a6757064617465cc86c40200019090a85f5f6e616d655f5fa6757064617465ac5f5
f64656661756c74735f5fc0ab5f5f636c6f737572655f5fc0a85f5f646963745f5f80a75f5f646f635f5fc0ae5f5f6b7764656661756c74735f5fc0aa6e616d6532636f6e737480\"}"`
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
    1. start_hash    (hex string, required)
    2. send_pairs    (list, optional, default=None)  `[(address, coin_id, amount),..]`
    3. storage       (dict, optional, default=None)
* Request example
    * `curl --basic -u user:password "127.0.0.1:3000/private/concludecontract" -H "Accept: application/json" -H "Content-Type: application/json" -d "{\"start_hash\": \"c6a350a6771343427eff7fbf276122eac1d242e03a9b26d654ede3b272eda1fe\", \"storage\": {\"hello\": \"world\"}}"`
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
    1. v_address     (string, required)
    2. new_address   (string, optional, default=None)  new/remove validator address
    3. flag          (numeric, optional, default=F_NOP)  validator address action
    4. sig_diff      (numeric, optional, default=0)  min require sign number edit
* Request example
    * init validator address `curl --basic -u user:password 127.0.0.1:3000/private/validatoredit -H "Accept: application/json" -H "Content-Type: application/json" -d "{\"v_address\": \"VRYXNX2RRHBJIMUYGVU473FFZ6IFAHNBUBBZANDB\", \"new_address\": \"NC5C2YP4RIF7XEYZC5UE2OHEAC45KSAPAICO2WQQ\", \"flag\": 1, \"sig_diff\": 1}"`
    * change 1of2multisig `curl --basic -u user:password 127.0.0.1:3000/private/validatoredit -H "Accept: application/json" -H "Content-Type: application/json" -d "{\"v_address\": \"VRYXNX2RRHBJIMUYGVU473FFZ6IFAHNBUBBZANDB\", \"new_address\": \"NC5C2YP4RIF7XEYZC5UE2OHEAC45KSAPAICO2WQQ\", \"flag\": 1, \"sig_diff\": 0}"`
* Response
```json
{
    "hash": "8f1ce28d94624a9b008a58777e6b137b5d8705c6a923e7f4b6fdc5615381b105",
    "gas_amount": 10010211,
    "gas_price": 100,
    "fee": 1001021100,
    "time": 0.56
}
```
* About
    * Basically, transaction creator provide fees, but user can use Validator's inner funds.
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
