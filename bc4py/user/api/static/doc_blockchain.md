Blockchain
====

get block by height
----
* Arguments
    1. height   (numeric, required)
    2. txinfo   (string, optional, default=false)
* Request example
    * `curl -H "accept: application/json" -H "Content-Type: application/json" "127.0.0.1:3000/public/getblockbyheight?height=10"`
* Response
```json
{
    "hash": "347e856bd7f0f74011d0ae796367cc54f5a061676c21fc4457bddcdc8e501cfc",
    "work_hash": "b5dc24f1298a59d5768575c90b1bd9a9a399587c5a2a04c042d887d5b12a0000",
    "previous_hash": "539b2ef5debdfb6b09a84717d7f69a9d52c247ab624250e01c7ebad82a4b1878",
    "next_hash": null,
    "f_orphan": false,
    "recode_flag": "database",
    "height": 10,
    "difficulty": 0.004096,
    "fixed_difficulty": 0.004096,
    "flag": "POW_X11",
    "merkleroot": "f051b246a4d50c2404fc5248d1561b24280896d114aa2cf05c480a6244dba4b1",
    "time": 1542117137,
    "bits": 521142271,
    "bias": 1.0,
    "nonce": "fde47077",
    "txs": [
        "f051b246a4d50c2404fc5248d1561b24280896d114aa2cf05c480a6244dba4b1"
    ],
    "size": 171,
    "hex": "00000000539b2ef5debdfb6b09a84717d7f69a9d52c247ab624250e01c7ebad82a4b1878f051b246a4d50c2404fc5248d1561b24280896d114aa2cf05c480a6244dba4b1d2080000ffff0f1ffde47077"
}
```

get block by hash
----
* Arguments
    1. hash     (hex string, required)
    2. txinfo   (string, optional, default=false)
* Request example
    * `curl -H "accept: application/json" -H "Content-Type: application/json" "127.0.0.1:3000/public/getblockbyhash?hash=347e856bd7f0f74011d0ae796367cc54f5a061676c21fc4457bddcdc8e501cfc"`

get tx by hash
----
* Arguments
    1. hash     (hex string, required)
* Request example
    * `curl -H "accept: application/json" -H "Content-Type: application/json" "127.0.0.1:3000/public/gettxbyhash?hash=f051b246a4d50c2404fc5248d1561b24280896d114aa2cf05c480a6244dba4b1"`
* Response
```json
{
    "hash": "f051b246a4d50c2404fc5248d1561b24280896d114aa2cf05c480a6244dba4b1",
    "pos_amount": null,
    "height": 10,
    "version": 2,
    "type": "POW_REWARD",
    "time": 1542117137,
    "deadline": 1542127937,
    "inputs": [],
    "outputs": [
        [
            "NC4YNWQQG3IFNJIXHFO66BU6KGU5EHLROK6MPQIY",
            0,
            55253186470
        ]
    ],
    "gas_price": 0,
    "gas_amount": 0,
    "message_type": "NONE",
    "message": "",
    "signature": [],
    "recode_flag": "database",
    "size": 91,
    "hex": "0200000001000000d20800000233000000000000000000000000000000000000000001000000004e4334594e575151473349464e4a495848464f36364255364b47553545484c524f4b364d5051495900000000a6b758dd0c000000"
}
```

get mintcoin info
----
* Arguments
    1. mint_id   (numeric, optional, default=0)
* Request example
    * `curl -H "accept: application/json" -H "Content-Type: application/json" "127.0.0.1:3000/public/getmintinfo?mint_id=3414534983"`
* Response
```json
{
    "version": 4,
    "coin_id": 3414534983,
    "name": "FriendCoin",
    "unit": "FC",
    "digit": 8,
    "description": "example for api",
    "image": "https://i.imgur.com/fRJV4ps.png",
    "txhash": "2a8e3d48b7ee5287a80884c041805113d99f7663d227772da242325b357231ff",
    "address": "NAC65KCG5B5J55T7TV6PZ2BHPHBQKMUJOXXT4PDV",
    "setting": {
        "additional_issue": false,
        "change_description": true,
        "change_image": false,
        "change_address": true
    }
}
```

get mintcoin history
----
* Arguments
    1. mint_id   (numeric, required)
* Request example
    * `curl -H "accept: application/json" -H "Content-Type: application/json" "127.0.0.1:3000/public/getminthistory?mint_id=3414534983"`
* Response
```json
[
    {
        "index": 0,
        "txhash": "d30e93d347da3c8eaa23fad7b1b3cbf0ce2e9eaf2b4f9e7a47a7df153932ddf2",
        "params": {
            "address": "NAC65KCG5B5J55T7TV6PZ2BHPHBQKMUJOXXT4PDV",
            "description": "example for api",
            "digit": 8,
            "image": null,
            "name": "FriendCoin",
            "unit": "FC"
        },
        "setting": {
            "additional_issue": true,
            "change_address": true
        }
    },
    {
        "index": 1,
        "txhash": "42b6ab256586d27715cf19f53b11814f0d5fd93e1ac8fbf8f2ceeadba8ec8310",
        "params": {
            "image": "https://i.imgur.com/fRJV4ps.png"
        },
        "setting": null
    },
    {
        "index": 2,
        "txhash": "19bb18862b913499c3f9d7e3d41bd0fab459436fb091d4d6bf2b7874e39fdef1",
        "params": null,
        "setting": {
            "change_image": false
        }
    },
    {
        "index": 3,
        "txhash": "23edb55d49e2f4b9a960935db066657129eb3e0bed775ea2cc07460802eef399",
        "params": null,
        "setting": null
    },
    {
        "index": 4,
        "txhash": "2a8e3d48b7ee5287a80884c041805113d99f7663d227772da242325b357231ff",
        "params": null,
        "setting": {
            "additional_issue": false
        }
    }
]
```
