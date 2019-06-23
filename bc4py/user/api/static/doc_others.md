Others
====
About Websocket.

websocket streaming
----
* API has `/public/ws` and `private/ws`.
* `private/ws` require Basic Authentication.
* Block and Transaction data stream in `/public/ws` and `private/ws`.

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

