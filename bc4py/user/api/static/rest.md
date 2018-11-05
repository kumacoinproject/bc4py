REST
====

Get system info
----
1. Endpoint [/api/getsysteminfo](./api/getsysteminfo)
2. Method `GET`
3. Params None
4. Response example
```json
{
    "system_ver": "0.0.10-alpha",
    "api_ver": "0.0.1",
    "chain_ver": 2,
    "message": "This is alpha version - use at your own risk, do not use for merchant applications.",
    "booting": false,
    "connections": 6,
    "unconfirmed": [],
    "directory": "C:\\Users\\jkdfh\\blockchain-py",
    "encryption": null,
    "generate": {
        "address": null,
        "message": null,
        "threads": [
            "<Generate POW_YES 232.0hash/s limit=0.05>",
            "<Generate POW_HMQ 31.55kh/s limit=0.05>",
            "<Generate POW_X11 13.93kh/s limit=0.05>",
            "<Generate POS 434hash/s limit=0.3>"
        ]
    },
    "locked": false,
    "access_time": 1541149719,
    "start_time": 1541147807
}
```

Get chain info
----
1. Endpoint [/api/getchaininfo](./api/getchaininfo)
2. Method `GET`
3. Params None
4. Response example
```json
{
    "best": {
        "hash": "a4c11bda42ec49192ab2317b051f311e427050ed88695f18725c628fe82ee364",
        "work_hash": "bf3745e0accb98898caf36f8a7ad2810f55dbf851407f19a8400f1cf1b150000",
        "previous_hash": "82f60ce3195856a997e7347bd9b74657d74a6a8d5c8f32c3253fea4220c421a7",
        "next_hash": null,
        "f_orphan": false,
        "f_on_memory": true,
        "height": 12734,
        "difficulty": 0.781534,
        "fixed_difficulty": 0.00507082,
        "flag": "POW_X11",
        "merkleroot": "62f85da1ba610827a6a36ee689838f502d09648cc89afb7df8c9c4a9208853b2",
        "time": 1541152173,
        "bits": 504723343,
        "bias": 154.12377023,
        "nonce": "fde3d9bd",
        "txs": ["62f85da1ba610827a6a36ee689838f502d09648cc89afb7df8c9c4a9208853b2"]
    },
    "mining": {
        "POW_YES": {
            "number": 1,
            "diff": 0.0,
            "bias": 1e-08,
            "fixed_diff": 5.439e-05,
            "hashrate(kh/s)": 0.081,
            "is_base": true
        },
        "POS": {
            "number": 2,
            "diff": 1.2e-07,
            "bias": 0.00219081,
            "fixed_diff": 5.341e-05,
            "hashrate(kh/s)": 5850.242,
            "is_base": false
        },
        "POW_X11": {
            "number": 4,
            "diff": 0.0,
            "bias": 1.54e-06,
            "fixed_diff": 5.138e-05,
            "hashrate(kh/s)": 11.82,
            "is_base": false
        },
        "POW_HMQ": {
            "number": 5,
            "diff": 0.0,
            "bias": 9.7e-07,
            "fixed_diff": 6.082e-05,
            "hashrate(kh/s)": 8.805,
            "is_base": false
        }
    },
    "size": 171,
    "checkpoint": {
        "height": 12733,
        "blockhash": "82f60ce3195856a997e7347bd9b74657d74a6a8d5c8f32c3253fea4220c421a7"
    },
    "money_supply": 707128112396122,
    "total_supply": 1000000000000000000
}
```

Get network info
----
1. Endpoint [/api/getnetworkinfo](./api/getnetworkinfo)
2. Method `GET`
3. Params None
4. Response example
```json
{
    "p2p_ver": "1.0.14",
    "status": {
        "name": "Bee:21845",
        "client_ver": "1.0.14",
        "network_ver": 2875757819,
        "p2p_accept": true,
        "p2p_udp_accept": true,
        "p2p_port": 2000,
        "start_time": 1541151685
    },
    "networks": [
        {
            "header": {
                "name": "Match:41259",
                "client_ver": "1.0.14",
                "network_ver": 2875757819,
                "p2p_accept": true,
                "p2p_udp_accept": false,
                "p2p_port": 2000,
                "start_time": 1540915740
            },
            "neers": [
                "111.22.333.444:2000",
                "123.456.567.789:2000",
                "321.654.765.098:2000"
            ],
            "number": 0,
            "host_port": "100.200.300.400:2000",
            "sock_type": "type/client"
        },
        {
            "header": {
                "name": "Tooth:53089",
                "client_ver": "1.0.14",
                "network_ver": 2875757819,
                "p2p_accept": true,
                "p2p_udp_accept": true,
                "p2p_port": 2000,
                "start_time": 1540915841
            },
            "neers": [
                "000.000.000.000:2000",
                "000.000.000.001:2000",
                "000.000.000.002:2000"
            ],
            "number": 1,
            "host_port": "111.222.333.444:2000",
            "sock_type": "type/client"
        }
    ]
}
```

Stop client
----
1. Endpoint [/api/stop](./api/stop)
2. Method `GET`
3. Params None
4. Response None

Set resync
----
1. Endpoint [/api/resync](./api/resync)
2. Method `GET`
3. Params None
4. Response None

List account balance
----
1. Endpoint [/api/listbalance](./api/listbalance)
2. Method `GET`
3. Params `confirm=6`
4. Response example
```json
{
    "@Unknown": {
        "0": 43726744578700
    },
    "@AccountName": {
      "0": 100000000
    }
}
```

List account related transactions
----
1. Endpoint [/api/listtransactions](./api/listtransactions)
2. Method `GET`
3. Params `page=0 limit=25`
4. Response example
```json
{
    "txs": [
        {
            "txhash": "e1fa282835285860f3aded4cf108b474ac54f2137289f0f8577d0d6ff6381812",
            "height": 12745,
            "on_memory": true,
            "type": "POW_REWARD",
            "movement": {
                "@Unknown": {"0": 55800706751}
            },
            "time": 1541152369
        },
        {
            "txhash": "b2e4d8b70e8c285cc37c6c61af79851bae4c535264121023fc4f220d33743766",
            "height": 12763,
            "on_memory": true,
            "type": "POW_REWARD",
            "movement": {
                "@Unknown": {"0": 55801481646}
            },
            "time": 1541152751
        }
    ],
    "next": true
}
```

List unspents
----
1. Endpoint [/api/listunspents](./api/listunspents)
2. Method `GET`
3. Params None
4. Response example
```json
[
    {
        "address": "NBFNRVBWNTEHVT57DF6LNWXCC5D6XJ6WUAPVGSYT",
        "height": 1671,
        "confirmed": 11168,
        "txhash": "e980030acf820744d533380892acc52e4b4e08366aa1a2ddb48c785bacee0364",
        "txindex": 0,
        "coin_id": 0,
        "amount": 55324516353
    },
    {
        "address": "NACUJOZSAWCS2OBRQ5HJ3S24RI4CVW4HFA54USDZ",
        "height": 9320,
        "confirmed": 3519,
        "txhash": "de75ea9981718920368c0cf30563cb022f60b4b5cef70cd680166264c7243709",
        "txindex": 0,
        "coin_id": 0,
        "amount": 55653313146
    }
]
```

List account all address
----
1. Endpoint [/api/listaccountaddress](./api/listaccountaddress)
2. Method `GET`
3. Params `account=@Unknown`
4. Response example
```json
{
    "account": "@Unknown",
    "user_id": 1,
    "address": [
        "NBDHODOFPGJORMB5YUTPTDD3W56CMGK34VSQJHCC",
        "NA5URXLAAPBBE3QRRWZ37S2VXU4KNJ325AAAAKK6",
        "NAYCWY4GKK4NEK6ZL55JCFF72XS35TCG6RCJFLPL",
        "NDSR74USLFR4BFIHGAA45IZP5MMONYMXPEC6RD4T",
        "NCBL3UKFPRB6BSJO5W4IYHRLW63XFWCMJJNSW2DM",
        "NANSKODDAB6QZNE2TKN2PSKWR4OO5K6VI7PGB3ED",
        "NDHYRVYVZUMP3C3HRFS4S3SBT46ITNVXGJYPAWTH"
        ]
}
```

Move account balance
----
1. Endpoint [/api/move](./api/move)
2. Method `POST`
3. Params `[from=Unknown] [to] [coin_id=0] [amount]`
4. Request example
```commandline
curl user:password@127.0.0.1:3000/api/move -v -H "Accept: application/json" -H "Content-Type: application/json" -d "{\"to\": \"friend\", \"amount\": 1000000}"
```
5. Response example
```json
{
    "txhash": "00000000000000000000000000000000000000000000000081ac03007a38a13c",
    "from_id": 1,
    "to_id": 5
}
```

Move many account balance
----
1. Endpoint [/api/movemany](./api/movemany)
2. Method `POST`
3. Params `[from=Unknown] [to] [coins]`
4. Request example
```commandline
curl user:password@127.0.0.1:3000/api/movemany -v -H "Accept: application/json" -H "Content-Type: application/json" -d "{\"to\": \"friend2\", \"coins\": {\"0\": 50000}}"
```
5. Response example
```json
{
    "txhash": "00000000000000000000000000000000000000000000000018b00300b818517a",
    "from_id": 1,
    "to_id": 6
}
```

Send from account
----
1. Endpoint [/api/sendfrom](./api/sendfrom)
2. Method `POST`
3. Params `[from=Unknown] [address] [coin_id=0] [amount] [message=None]`
4. Request example
```commandline
curl user:password@127.0.0.1:3000/api/sendfrom -v -H "Accept: application/json" -H "Content-Type: application/json" -d "{\"address\": \"NB2YGMP4ISW5ALNATGE7LCH3WM5OSJHURFBYM3MS\", \"amount\": 10
00000000000}"
```
5. Response example
```json
{
    "txhash": "64ea1172a26b563f87e91c07d34208a2dfe354ee968f5dd4f0f1d0e3b07e724b",
    "time": 0.42
}
```

Send to many accounts
----
1. Endpoint [/api/sendmany](./api/sendmany)
2. Method `POST`
3. Params `[from=Unknown] [pairs:list(address,coin_id,amount)] [message=None]`
4. Request example
```commandline
curl user:password@127.0.0.1:3000/api/sendmany -v -H "Accept: application/json" -H "Content-Type: application/json" -d "{\"pairs\": [[\"NB2YGMP4ISW5ALNATGE7LCH3WM5OSJHURFBYM3MS\", 0, 10000000], [
\"NBEWMUZKLYQN3YC26RIGFM7O6GPER7ONNU7Q6DCY\", 0, 2000000]]}"
```
5. Response example
```json
{
    "txhash": "b798cc04c290c188d322d0acf2d05fc9e8324d12970d0b7ef691ecf4cd95e4a2",
    "time": 0.032
}
```

Issue mint coin
----
1. Endpoint [/api/issueminttx](./api/issueminttx)
2. Method `POST`
3. Params `[name] [unit] [amount] [digit=0] [message=None] [image=None] [additional_issue=True] [account=Unknown]`
4. Request example
```commandline
curl user:password@127.0.0.1:3000/api/issueminttx -v -H "Accept: application/json" -H "Content-Type: application/json" -d "{\"name\": \"NewExampleCoin\", \"unit\": \"NEC\", \"amount\": 10000000000}"
```
5. Response example
```json
{
    "txhash": "3376185778ef58ef7ea0e0f52ae72b766106f2ff0653e0431e59f41163b93b50",
    "mintcoin": {
        "version": 0,
        "hash": null,
        "coin_id": 4110208126,
        "name": "NewExampleCoin",
        "unit": "NEC",
        "digit": 0,
        "amount": 10000000000,
        "supply": 10000000000,
        "additional_issue": true,
        "owner": "8150123d925edec9b38702c0c621ad3a45f3fe8f8ba10843205b980e95f6256f",
        "image": null,
        "message": null
    }
}
```

Change mintcoin info
----
1. Endpoint [/api/changeminttx](./api/changeminttx)
2. Method `POST`
3. Params `[mint_id] [amount=0] [message=None] [image=None] [additional_issue=None] [group=Unknown]`
4. Request example
```commandline
curl user:password@127.0.0.1:3000/api/changeminttx -v -H "Accept: application/json" -H "Content-Type: application/json" -d "{\"mint_id\": 4110208
126, \"amount\": 500000}"
```
5. Response example
```json
{
    "txhash": "c5d4302f9525ebc68d342c55ad73aa25234c56353f2c581f940bd78095c06669",
    "mintcoin": {
        "version": 1,
        "hash": null,
        "coin_id": 4110208126,
        "name": "NewExampleCoin",
        "unit": "NEC",
        "digit": 0,
        "amount": 500000,
        "supply": 10000500000,
        "additional_issue": true,
        "owner": "8150123d925edec9b38702c0c621ad3a45f3fe8f8ba10843205b980e95f6256f",
        "image": null,
        "message": null
    }
}
```

Create new address by account
----
1. Endpoint [/api/newaddress](./api/newaddress)
2. Method `POST`
3. Params `[account=Unknown]`
4. Response example
```json
{
    "account": "@Unknown",
    "user_id": 1,
    "address": "NBU2RUL4GVHJDOTWPYXJO4MR4WUCVCG5UUTKVBL6"
}
```

Get keypair by address
----
1. Endpoint [/api/getkeypair](./api/getkeypair)
2. Method `GET`
3. Params `address`
4. Response example
```json
{
    "uuid": 620,
    "address": "NBU2RUL4GVHJDOTWPYXJO4MR4WUCVCG5UUTKVBL6",
    "private_key": "58e54399bd8a5369d29600cd5c263805c48347afb001a0f920eca6e7dba7456e",
    "public_key": "25f0285b39e365572aaf4229cfe94afee935ce01496e0751fcf2d7f7fa79d669"
}
```

Create raw tx
----
1. Endpoint [/api/createrawtx](./api/createrawtx)
2. Method `POST`
3. Params `[version=1] [type=TRANSFER] [time=now] [deadline=now+10800] [inputs:list((txhash, txindex),..)]
[outputs:list((address, coin_id, amount),..)] [gas_price=MINIMUM_PRICE] [gas_amount=MINIMUM_AMOUNT]
[message_type=None] [message=None]`
4. Request example
```commandline
curl user:password@127.0.0.1:3000/api/createrawtx -v -H "Accept: application/json" -H "Content-Type: application/json" -d "{\"inputs\": [[\"b7a6c499595bfb409e35cd8e0cab59d404fa6a3305dde9e6db16e2dc25c9c272\", 0]], \"outputs\": [[\"NBXQATE66Z5AXBLQNGMBR5WWZGZUGUX3GTOWWDUY\", 0, 10000]]}"
```
5. Response example
```json
{
    "tx": {
        "hash": "20174c01acb2b948bf019c4f2f235a71894b836013b2ed24bd3ff6f00eb5ff56",
        "pos_amount": null,
        "height": null,
        "version": 2,
        "type": "TRANSFER",
        "time": 1541160923,
        "deadline": 1541171723,
        "inputs": [
            ["b7a6c499595bfb409e35cd8e0cab59d404fa6a3305dde9e6db16e2dc25c9c272", 0]
        ],
        "outputs": [
            ["NBXQATE66Z5AXBLQNGMBR5WWZGZUGUX3GTOWWDUY", 0, 10000]
        ],
        "gas_price": 100,
        "gas_amount": 220,
        "message_type": "NONE",
        "message": "",
        "signature": [],
        "meta": {},
        "f_on_memory": null
    },
    "hex": "020000000300000018c5030048ef03006400000000000000dc0000000000000000010100000000b7a6c499595bfb409e35cd8e0cab59d404fa6a3305dde9e6db16e2dc25c9c272004e42585141544536365a354158424c514e474d42523557575a475a554755583347544f5757445559000000001027000000000000"
}
```

Sign raw tx
----
1. Endpoint [/api/signrawtx](./api/signrawtx)
2. Method `POST`
3. Params `	[hex] [pk=list(sk,..)]`
4. Response example
```json
{
    "txhash": "bcfd777fce9a4b08e2026b05ea690b383fca6f6166e06b719d7bcfebff2c7914",
    "signature": [
        ["a201c9e8387ef33fe7c5014faea6710cbfad74b5d4fe7af01e4aaf9448c2c8d4", "66604214dfde21747eec03e344a76a692df8e58e56146151fe0121ee0e14000066604214dfde21747eec03e344a76a692df8e58e56146151fe0121ee0e140000"]
    ],
    "hex": "020000000300000018c5030048ef03006400000000000000dc0000000000000000010100000000b7a6c499595bfb409e35cd8e0cab59d404fa6a3305dde9e6db16e2dc25c9c272004e42585141544536365a354158424c514e474d42523557575a475a554755583347544f5757445559000000001027000000000000"
}
```

Broadcast tx
----
1. Endpoint [/api/broadcasttx](./api/broadcasttx)
2. Method `POST`
3. Params `[hex] [signature:list([pk, sign],..)]`
4. Request example
5. Response example
```json
{
    "txhash": "66ce2e605006960fedbccdd3bf8c38f30ff85b9f33b26ff865a2e0c83e63da99"
}
```

Get block by height
----
1. Endpoint [/api/getblockbyheight](./api/getblockbyheight)
2. Method `GET`
3. Params `height`
4. Response example
```json
{
    "hash": "b8344ed058ff777db3491afdad3f93f6b98172281d1b1efe222692cfd2ad1fa2",
    "work_hash": "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
    "previous_hash": "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
    "next_hash": null,
    "f_orphan": false,
    "f_on_memory": false,
    "height": 0,
    "difficulty": 0.004096,
    "fixed_difficulty": 0.004096,
    "flag": "GENESIS",
    "merkleroot": "1ec3c85db86f11b4abde87b07cac41fd02e7efd60fa1cab324c5f56be9fa8184",
    "time": 1540913859,
    "bits": 521142271,
    "bias": 1.0,
    "nonce": "ffffffff",
    "txs": [
        "90b29546e4631bd78192ece8e6859b27dc1866c500aed000d3df8ec6c4a56c35",
        "d86560f1ac4d9d3676eefe3dc19d32d281fddd6fec93d53fff1a5a5af18af69b"
    ],
    "size": 1409,
    "hex": "00000000ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff1ec3c85db86f11b4abde87b07cac41fd02e7efd60fa1cab324c5f56be9fa818400000000ffff0f1fffffffff"
}
```

Get block by hash
----
1. Endpoint [/api/getblockbyhash](./api/getblockbyhash)
2. Method `GET`
3. Params `hash`

Get tx by hash
----
1. Endpoint [/api/gettxbyhash](./api/gettxbyhash)
2. Method `GET`
3. Params `hash`
4. Response example
```json
{
    "hash": "90b29546e4631bd78192ece8e6859b27dc1866c500aed000d3df8ec6c4a56c35",
    "pos_amount": null,
    "height": 0,
    "version": 2,
    "type": "GENESIS",
    "time": 1540913859,
    "deadline": 1540924659,
    "inputs": [],
    "outputs": [],
    "gas_price": 0,
    "gas_amount": 0,
    "message_type": "BYTE",
    "message": "01020b010a050a616c6c5f737570706c7901080de0b6b3a7640000050a626c6f636b5f7370616e0101140509636f6e73656e7375730b010401010101011e01010201010a01010401011e01010501011e0517636f6e74726163745f6d696e696d756d5f616d6f756e74010405f5e100050f636f6e74726163745f70726566697807010112050c64696769745f6e756d626572010108050c67656e657369735f74696d6501045bd87ac3050d6d696e696d756d5f7072696365010164050670726566697807010168051176616c696461746f725f616464726573730528434a585141544536365a354158424c514e474d42523557575a475a554755583347544434584a364a",
    "signature": [],
    "meta": {},
    "f_on_memory": false,
    "size": 299,
    "hex": "020000000000000000000000302a0000000000000000000000000000000000000200000401000001020b010a050a616c6c5f737570706c7901080de0b6b3a7640000050a626c6f636b5f7370616e0101140509636f6e73656e7375730b010401010101011e01010201010a01010401011e01010501011e0517636f6e74726163745f6d696e696d756d5f616d6f756e74010405f5e100050f636f6e74726163745f70726566697807010112050c64696769745f6e756d626572010108050c67656e657369735f74696d6501045bd87ac3050d6d696e696d756d5f7072696365010164050670726566697807010168051176616c696461746f725f616464726573730528434a585141544536365a354158424c514e474d42523557575a475a554755583347544434584a364a"
}
```

Get mintcoin info
----
1. Endpoint [/api/getmintinfo](./api/getmintinfo)
2. Method `GET`
3. Params `mint_id=0`
4. Response example
```json
{
    "version": 0,
    "hash": null,
    "coin_id": 0,
    "name": "PyCoin",
    "unit": "PC",
    "digit": 8,
    "amount": 0,
    "supply": 1000000000000000000,
    "additional_issue": false,
    "owner": null,
    "image": null,
    "message": "Base currency."
}
```