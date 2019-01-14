Others
====
About Websocket.

websocket streaming
----
* API has `/public/ws` and `private/ws`.
* `private/ws` require Basic Authentication.
* Block and Transaction data stream in `/public/ws` and `private/ws`.
* User related contract data stream in `private/ws`.

Example of BasicAuth on WebSocket
----
```javascript
const uri = 'ws://user:password@127.0.0.1:3000/private/ws';
const ws = new WebSocket(uri);
ws.onmessage = function(event) {
  console.log('Get: '+event.data);
}
```

Block data (public)
----
```json
{
    "cmd": "Block",
    "data": {
        "hash": "b4074bfed1f62a585ad7619133e4632a581adf3b1f04c1193e494e6c34dea448",
        "work_hash": "701ee0e136cc4044f0a30f6aa0959334f1f21541f3da052a3f084a513f020000",
        "previous_hash": "30506abc7d9c702694838ee81f6727a84fcc7b05ba495a4e260e3afb072aa494",
        "next_hash": null,
        "f_orphan": null,
        "recode_flag": "memory",
        "height": 13257,
        "difficulty": 0.478193,
        "fixed_difficulty": 0.00304371,
        "flag": "POW_HMQ",
        "merkleroot": "ce91474559e39d7011ed9088817351863028f0d9d0bfdbde79ac5669140d694d",
        "time": 1543237143,
        "bits": 505615785,
        "bias": 157.10844019,
        "nonce": "00001cf3",
        "txs": [
            "ce91474559e39d7011ed9088817351863028f0d9d0bfdbde79ac5669140d694d"
        ]
    },
    "status": true
}
```

Transaction data (public)
----
```json
{
    "cmd": "TX",
    "data": {
        "hash": "ebb43d98a05e907c7d167b78ce06f6c49ce6ed62816a7f5b8a9d9f704e38294d",
        "pos_amount": null,
        "height": null,
        "version": 2,
        "type": "TRANSFER",
        "time": 1543237798,
        "deadline": 1543248598,
        "inputs": [
            ["68d59f2f605bfa6e86fd8426dbff83ca33715e6469cbab0fbf14aa79253e675e", 0]
        ],
        "outputs": [
            ["NAOR5JO7IIFXWGS3P2KL5ERG6ZGBHVJMA43FEQDI", 0, 20000000000],
            ["NC7HSCPFQCCVFF5LRWGH2Y3BXI6JEXHAOTYGTHVE", 0, 35540605063]
        ],
        "gas_price": 100,
        "gas_amount": 272,
        "message_type": "NONE",
        "message": "",
        "signature": [
            ["8a5d5754ebec76ec0cd53df3e4282f53eef71e510594bcdcb9be791b715f656d", "42a4954e205359296ae673761094e2ee88f259292b3f1ac9edfa4561dba77117a8f95edc1ca8b1dce665582e83d0853268327273289f2d4e288885263a94a20c"]
        ],
        "recode_flag": "memory"
    },
    "status": true
}
```

Validator (private)
----
New validator edit tx is coming/changed. check update signatures by *time*.
Validator users are required to sign **at own risk**.
```json
{
    "cmd": "Validator",
    "data": {
        "c_address": "CJ4QZ7FDEH5J7B2O3OLPASBHAFEDP6I7UKI2YMKF",
        "hash": "2df32ba39c162ef117ea02abf610055f3ea3fa9a5a156d9e76a04f595bd1a2e0",
        "time": 1543239114.1453898,
        "tx": {
            "hash": "2df32ba39c162ef117ea02abf610055f3ea3fa9a5a156d9e76a04f595bd1a2e0",
            "pos_amount": null,
            "height": null,
            "version": 2,
            "type": "VALIDATOR_EDIT",
            "time": 1543239114,
            "deadline": 1543249914,
            "inputs": [
                ["1c1b2a7a30631e39dafcee781139ea298f811932fee1b44234781f915b32253f", 0]
            ],
            "outputs": [
                ["CJ4QZ7FDEH5J7B2O3OLPASBHAFEDP6I7UKI2YMKF", 0, 20991726100]
            ],
            "gas_price": 100,
            "gas_amount": 10010315,
            "message_type": "BYTE",
            "message": "01020901040528434a34515a3746444548354a3742324f334f4c50415342484146454450364937554b4932594d4b4605284e414b5a5846415a544d4e55325553434d51323641544932534c555243494c4a36524b5633354b56010101010100",
            "signature": [
                ["c24b03f8de8614da079f6005bfb23943971635794ac051a448885943de513bd8", "0cb8e616a07c5a50dec2deb65052fc05c069898d62785a55e747c177498b7cc8403b919b935a751adca40c95457a3a7a994a0cd5ffa6c47a8ed63fdf26e9b300"]
            ],
            "recode_flag": "memory"
        },
        "related": [
            ["contract", "NA3OYCDZK5LXYGV63QYMO2KYMQNVOHUEQHC3NBLP"]
        ],
        "new_address": "NAKZXFAZTMNU2USCMQ26ATI2SLURCILJ6RKV35KV",
        "flag": 1,
        "sig_diff": 0
    },
    "status": true
}
```

FinishValidator (private)
----
Notice validator edit tx is include to Block.
```json
{
    "cmd": "FinishValidator",
    "data": {
        "hash": "2df32ba39c162ef117ea02abf610055f3ea3fa9a5a156d9e76a04f595bd1a2e0",
        "time": 1543239118.6326458,
        "tx": {
            "hash": "2df32ba39c162ef117ea02abf610055f3ea3fa9a5a156d9e76a04f595bd1a2e0",
            "pos_amount": null,
            "height": 13547,
            "version": 2,
            "type": "VALIDATOR_EDIT",
            "time": 1543239114,
            "deadline": 1543249914,
            "inputs": [
                ["1c1b2a7a30631e39dafcee781139ea298f811932fee1b44234781f915b32253f", 0]
            ],
            "outputs": [
                ["CJ4QZ7FDEH5J7B2O3OLPASBHAFEDP6I7UKI2YMKF", 0, 20991726100]
            ],
            "gas_price": 100,
            "gas_amount": 10010315,
            "message_type": "BYTE",
            "message": "01020901040528434a34515a3746444548354a3742324f334f4c50415342484146454450364937554b4932594d4b4605284e414b5a5846415a544d4e55325553434d51323641544932534c555243494c4a36524b5633354b56010101010100",
            "signature": [
                ["c24b03f8de8614da079f6005bfb23943971635794ac051a448885943de513bd8", "0cb8e616a07c5a50dec2deb65052fc05c069898d62785a55e747c177498b7cc8403b919b935a751adca40c95457a3a7a994a0cd5ffa6c47a8ed63fdf26e9b300"]
            ],
            "recode_flag": "memory"
        }
    },
    "status": true
}
```

RequestConclude (private)
---
New contract transfer tx is include to Block.
Validators are required to create conclude tx.
```json
{
    "cmd": "RequestConclude",
    "data": {
        "c_address": "CJ4QZ7FDEH5J7B2O3OLPASBHAFEDP6I7UKI2YMKF",
        "hash": "7503bf48b3218e28bf9b832cc117d9f098f859c41289713cbe557ea394037ad8",
        "time": 1543240023.2939832,
        "tx": {
            "hash": "7503bf48b3218e28bf9b832cc117d9f098f859c41289713cbe557ea394037ad8",
            "pos_amount": null,
            "height": 13621,
            "version": 2,
            "type": "TRANSFER",
            "time": 1543239999,
            "deadline": 1543250799,
            "inputs": [
                ["def4a910a58767c789fd6ba089662f93ff1b0a91d40936a276421292a90f4482", 0]
            ],
            "outputs": [
                ["CJ4QZ7FDEH5J7B2O3OLPASBHAFEDP6I7UKI2YMKF", 0, 100000000],
                ["NAHQO4WIJWKZXLQN3QJ4SKKPRP3MLBTPEH2UFTVT", 0, 55359437871]
            ],
            "gas_price": 100,
            "gas_amount": 761,
            "message_type": "BYTE",
            "message": "01020901030528434a34515a3746444548354a3742324f334f4c50415342484146454450364937554b4932594d4b460504696e6974090103070201ab800495a0010000000000008c0964696c6c2e64696c6c948c0c5f6372656174655f747970659493942868008c0a5f6c6f61645f747970659493948c047479706594859452948c08436f6e74726163749468048c066f626a656374948594529485947d94288c0a5f5f6d6f64756c655f5f948c085f5f6d61696e5f5f948c075f5f646f635f5f944e8c085f5f696e69745f5f9468008c105f6372656174655f66756e6374696f6e9493942868048c08436f6465547970659485945294284b034b004b034b024b4343107c017c005f007c027c005f0164005300944e85948c0873746172745f7478948c09635f616464726573739486948c0473656c66946819681a8794680868114b02430400010601942929749452946362633470792e636f6e74726163742e746f6f6c730a5f5f646963745f5f0a68114e4e7d94749452948c0474657374946813286816284b014b004b024b014b47430464005300944e859429681c8c0461726773948694680868244b0643020001942929749452946362633470792e636f6e74726163742e746f6f6c730a5f5f646963745f5f0a68244e4e7d947494529475749452942e0c0c",
            "signature": [
                ["d7b8d6460502b198f9e7bf4354236f3e7662a3bdf1ee67621c4b559325a6fa6b", "2c0c768648d610d0fa9f33b844f0c71d74ba26bba35c076cff64595aeb6e1c11fe92bfa6ce94def26d513bfcda2b5f0a9566c725e8a1649bfa4f1b42c670f60c"]
            ],
            "recode_flag": "memory"
        },
        "related": [
            ["contract", "NA3OYCDZK5LXYGV63QYMO2KYMQNVOHUEQHC3NBLP"]
        ],
        "c_method": "init",
        "c_args": [
            "0102030405...aa34",
            null,
            null
        ]
    },
    "status": true
}
```

Conclude (private)
----
New contract conclude tx is coming/changed. check update signatures by *time*.
Validators are required to sign **at own risk**.
```json
{
    "cmd": "Conclude",
    "data": {
        "c_address": "CJ4QZ7FDEH5J7B2O3OLPASBHAFEDP6I7UKI2YMKF",
        "hash": "9e08385766bc609cdd9a36416a9533da51072e3d74f874aabbf6ac562735e8b7",
        "time": 1543240403.2878294,
        "tx": {
            "hash": "9e08385766bc609cdd9a36416a9533da51072e3d74f874aabbf6ac562735e8b7",
            "pos_amount": null,
            "height": null,
            "version": 2,
            "type": "CONCLUDE_CONTRACT",
            "time": 1543240403,
            "deadline": 1543251203,
            "inputs": [
                ["ede5ad258db4fff07bdfa6cbadd0d0f00d6b656e999db40a192e613dade65b4a", 0]
            ],
            "outputs": [
                ["CJ4QZ7FDEH5J7B2O3OLPASBHAFEDP6I7UKI2YMKF", 0, 18987625700]
            ],
            "gas_price": 100,
            "gas_amount": 20415,
            "message_type": "BYTE",
            "message": "01020901030528434a34515a3746444548354a3742324f334f4c50415342484146454450364937554b4932594d4b460701207503bf48b3218e28bf9b832cc117d9f098f859c41289713cbe557ea394037ad80b0101050568656c6c6f0505776f726c64",
            "signature": [
                ["c24b03f8de8614da079f6005bfb23943971635794ac051a448885943de513bd8", "afc936c6d176930a9867bdef01141df321845cbf64784304959923d487d72304f64f88e6807065aef79e9fc8ed5fd52eb24fd310ee44641636b83556d965ed0f"]
            ],
            "recode_flag": "memory"
        },
        "related": [
            ["contract", "NA3OYCDZK5LXYGV63QYMO2KYMQNVOHUEQHC3NBLP"]
        ],
        "start_hash": "7503bf48b3218e28bf9b832cc117d9f098f859c41289713cbe557ea394037ad8",
        "c_storage": {
            "hello": "world"
        }
    },
    "status": true
}
```

FinishConclude  (private)
----
Notice conclude tx is include to Block.
```json
{
    "cmd": "FinishConclude",
    "data": {
        "hash": "9e08385766bc609cdd9a36416a9533da51072e3d74f874aabbf6ac562735e8b7",
        "time": 1543240899.144442,
        "tx": {
            "hash": "9e08385766bc609cdd9a36416a9533da51072e3d74f874aabbf6ac562735e8b7",
            "pos_amount": null,
            "height": 13686,
            "version": 2,
            "type": "CONCLUDE_CONTRACT",
            "time": 1543240403,
            "deadline": 1543251203,
            "inputs": [
                ["ede5ad258db4fff07bdfa6cbadd0d0f00d6b656e999db40a192e613dade65b4a", 0]
            ],
            "outputs": [
                ["CJ4QZ7FDEH5J7B2O3OLPASBHAFEDP6I7UKI2YMKF", 0, 18987625700]
            ],
            "gas_price": 100,
            "gas_amount": 20415,
            "message_type": "BYTE",
            "message": "01020901030528434a34515a3746444548354a3742324f334f4c50415342484146454450364937554b4932594d4b460701207503bf48b3218e28bf9b832cc117d9f098f859c41289713cbe557ea394037ad80b0101050568656c6c6f0505776f726c64",
            "signature": [
                ["8b29d3fff03cd8d2e6738def5f690747f9b15f77d7ba933a02a9b13b0904e98d", "55468fa7dc108ce829e59d1d0e01c4d198cf420e3a379dd90d151aeda891fa1d595e29b119b8b2f3e01de3924047f3ce9b738b3b1b9d01552c9d1bf890ff4d05"],
                ["c24b03f8de8614da079f6005bfb23943971635794ac051a448885943de513bd8", "afc936c6d176930a9867bdef01141df321845cbf64784304959923d487d72304f64f88e6807065aef79e9fc8ed5fd52eb24fd310ee44641636b83556d965ed0f"]
            ],
            "recode_flag": "memory"
        }
    },
    "status": true
}
```
