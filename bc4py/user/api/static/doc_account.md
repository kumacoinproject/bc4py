Account
====
Get account info, edit account.

list balance
----
* Arguments
    1. confirm    (numeric, optional, default=6) Confirmation height.
* Request example
    * `curl --basic -u user:password -H "accept: application/json" 127.0.0.1:3000/private/listbalance`
* Response
```json
{
    "@Unknown": {
        "0": 122888541957145,
        "22454": 10000
    },
    "@Outside": {
        "0": 40000054400
    },
    "username": {
        "Coin_id": "amount"
    }
}
```
* About
    * Get all account balance.
    * Coin_id `0` is base currency.

list transactions
----
* Arguments
    1. page   (numeric, optional, default=0) Page number.
    2. limit    (numeric, optional, default=25)  Number of TX included in Page.
* Request example
    * `curl --basic -u user:password -H "accept: application/json" "127.0.0.1:3000/private/listtransactions?page=5&limit=10"`
* Response
```json
{
    "txs": [
        {
            "txhash": "00000000000000000000000000000000000000000000000045ec03009dd522a7",
            "height": null,
            "recode_flag": "memory",
            "type": "TX_INNER",
            "movement": {
                "@Unknown": {
                    "0": -100000000
                },
                "Friends": {
                    "0": 100000000
                }
            },
            "time": 1542371972
        },
        {
            "txhash": "1f1d271207b51bb7cd5eb6a08fdf0310249b07ef20c3ef9c33875d3a7310132f",
            "height": 5227,
            "recode_flag": "memory",
            "type": "POW_REWARD",
            "movement": {
                "@Unknown": {
                    "0": 55477308273
                }
            },
            "time": 1542369658
        },
        {
            "txhash": "bb6fc3e23ee2cc6b816d5667f9074ab6115d68564b8491310743e06c77bdb122",
            "height": 5228,
            "recode_flag": "memory",
            "type": "POW_REWARD",
            "movement": {
                "@Unknown": {
                    "0": 55477351257
                }
            },
            "time": 1542369678
        },
        {
            "txhash": "e25a964be8ae41bfaec5ee3e1348e4520997a04de1891bec86a4dd1a89311857",
            "height": 5229,
            "recode_flag": "memory",
            "type": "POW_REWARD",
            "movement": {
                "@Unknown": {
                    "0": 55477394240
                }
            },
            "time": 1542369698
        },
        {
            "txhash": "04a8752e11a0d250f9ae6d1de48cf361d522fc91d64941223ac8573741cbdab1",
            "height": 5233,
            "recode_flag": "memory",
            "type": "POS_REWARD",
            "movement": {
                "@Unknown": {
                    "0": 55477566173
                }
            },
            "time": 1542369780
        },
        {
            "txhash": "61718d7a48b047380bdd15fb5714cb87143624b7e631a436c221710d015127a3",
            "height": 5236,
            "recode_flag": "memory",
            "type": "POW_REWARD",
            "movement": {
                "@Unknown": {
                    "0": 55477695123
                }
            },
            "time": 1542369868
        },
        {
            "txhash": "54bcdd3e5b3888126d0065de0b3e6db286a9c8a5f1f86c6ec2bbb21a605668d8",
            "height": 5244,
            "recode_flag": "memory",
            "type": "POW_REWARD",
            "movement": {
                "@Unknown": {
                    "0": 55478038990
                }
            },
            "time": 1542369978
        },
        {
            "txhash": "997d37dc67ed505f3dec52dc11577fd905705771991e08d5c3a2d868e0ac4433",
            "height": 5247,
            "recode_flag": "memory",
            "type": "POW_REWARD",
            "movement": {
                "@Unknown": {
                    "0": 55478167940
                }
            },
            "time": 1542369998
        },
        {
            "txhash": "a365d5129cfda174aeee086377b2c913c67944b2793bea5edd36a7dec329ab92",
            "height": 5249,
            "recode_flag": "memory",
            "type": "POW_REWARD",
            "movement": {
                "@Unknown": {
                    "0": 55478253907
                }
            },
            "time": 1542370008
        },
        {
            "txhash": "b0a284411a30db18f71960782a0ebf94512745948cbd4c6093bf6c13f103be2d",
            "height": 5264,
            "recode_flag": "memory",
            "type": "POW_REWARD",
            "movement": {
                "@Unknown": {
                    "0": 55478898660
                }
            },
            "time": 1542370129
        }
    ],
    "next": true
}
```
* About
    * `movement` inner account balance movement.
    * `next` next page exists.
    * If `height` is null, TX is on memory.
    * null height TX is older than recode limit or unconfirmed.

list unspents (public)
----
* Arguments
    1. address   (string , required) request more than one by comma.
    2. page      (numeric, optional, default=0)
    3. limit     (numeric, optional, default=25) page size, maxlimit 100
* Request example
    * `curl -H "accept: application/json" "127.0.0.1:3000/public/listunspents?address=NCSL6UQ4PU7PDWIHCTKGNA5WYO542T2H66DEHTRI,NA3UBTHRXMW7ZSZL2UA5V2TQC2UJLYGEVXVWZVQJ"`
* Response
```json
{
    "data": [
        {
            "address": "NCSL6UQ4PU7PDWIHCTKGNA5WYO542T2H66DEHTRI",
            "height": 2482,
            "confirmed": 2842,
            "txhash": "562b9f023ba2389b97ae76c9f2aed45bae474e67dc3c9f7e2af2f855e805e6d9",
            "txindex": 0,
            "coin_id": 0,
            "amount": 55359352906
        },
        {
            "address": "NA3UBTHRXMW7ZSZL2UA5V2TQC2UJLYGEVXVWZVQJ",
            "height": 5268,
            "confirmed": 56,
            "txhash": "274cf71bef7b499e10d3c77d5d7ee8d49a9472e7ef0d825ddaf1d76e0968fa6f",
            "txindex": 0,
            "coin_id": 0,
            "amount": 608524360733
        },
        {
            "address": "NCSL6UQ4PU7PDWIHCTKGNA5WYO542T2H66DEHTRI",
            "height": null,
            "confirmed": null,
            "txhash": "bae474e67dc3c9f7e2af2f855e805e6d9562b9f023ba2389b97ae76c9f2aed45",
            "txindex": 0,
            "coin_id": 0,
            "amount": 1000000000
        }
    ],
    "next": false
}
```
* About
    * extract data from Database->Memory->Unconfirmed

list unspents (private)
----
* Request example
    * `curl --basic -u user:password -H "accept: application/json" "127.0.0.1:3000/private/listunspents"`
* Response
```json
[
    {
        "address": "NCSL6UQ4PU7PDWIHCTKGNA5WYO542T2H66DEHTRI",
        "height": 2482,
        "confirmed": 2842,
        "txhash": "562b9f023ba2389b97ae76c9f2aed45bae474e67dc3c9f7e2af2f855e805e6d9",
        "txindex": 0,
        "coin_id": 0,
        "amount": 55359352906
    },
    {
        "address": "NA3UBTHRXMW7ZSZL2UA5V2TQC2UJLYGEVXVWZVQJ",
        "height": 5268,
        "confirmed": 56,
        "txhash": "274cf71bef7b499e10d3c77d5d7ee8d49a9472e7ef0d825ddaf1d76e0968fa6f",
        "txindex": 0,
        "coin_id": 0,
        "amount": 608524360733
    },
    {
        "address": "NB74K3UCQFB4HE3MM33A2SHL53WOZE6I7Y3DHDOJ",
        "height": 5279,
        "confirmed": 45,
        "txhash": "1d8acdbec154e48e6346b3fdd71db9fd4aaeb98d77f759dd912bd3bc32da4d80",
        "txindex": 0,
        "coin_id": 0,
        "amount": 55479543415
    },
    {
        "address": "NB5UEP7WQKDILPJJKEDRROSSA6JM7FOX7VX3QCRL",
        "height": 5291,
        "confirmed": 33,
        "txhash": "136ae65598afa78e366f1941cf7039473df05bf364b5668c7cbba031bb84294f",
        "txindex": 0,
        "coin_id": 0,
        "amount": 55480059220
    }
]
```
* About
    * ALL unspents export.

list account address
----
* Arguments
    1. account      (string, optional, default="@Unknown")  Account name.
* Request example
    * `curl --basic -u user:password -H "accept: application/json" "127.0.0.1:3000/private/listaccountaddress?account=@Unknown"`
* Response
```json
{
    "account": "@Unknown",
    "user_id": 1,
    "address": [
        "NCB56TCBTALDEN7DBY4NCLHEUK3HYA6Q3RCYHHBN",
        "NDTL7N6UYKZ5ZZKVEOQZYBILSSRMU2JRMG7BHWRE",
        "NDNEZO35JQZMGUQ7U2HO6D43JTGPO744CEWM2F7O",
        "NCF2I574RUIMBD53AJV5WGFFDLV4I6KVSGHEQYCL",
        "NACX6PEO27PN37HYRWUTE4HOT7Z34P2OZFULNLIA",
        "NBYIDW3R5XBROJVFRNZYTM2DIEX7JFIJYE5LAIE5",
        "NCGPBBQBTJ7X3KPS2S42PA4OPJCA74CGIBWQLQ2S",
        "NBHUR4WD3ESZ6SL6HNNKHQIK75T3Q5MONI7JAGEV"
    ]
}
```

lock wallet
----
* Request example
    * `curl --basic -u user:password -H "accept: application/json" "127.0.0.1:3000/private/lockwallet"`
* Response
```json
{"status":  true}
```

unlock wallet
----
* Arguments
    1. passphrase      (string, optional, default="")  Encrypt root private key.
    2. timeout         (numeric, optional, default=60) Auto delete inner private key, disabled by -1.
* Request example
    * `curl --basic -u user:password -H "accept: application/json" "127.0.0.1:3000/private/unlockwallet"`
* Response
```json
{"status": true, "timeout": 60}
```

create wallet
----
* Arguments
    1. passphrase      (string, optional, default="")  Encrypted by the passphrase
    2. strength        (numeric, optional, default=12) mnemonic words number [12, 15, 18, 21, 24]
* Request example
    * `curl --basic -u user:password -H "accept: application/json" "127.0.0.1:3000/private/createwallet"`
* Response
```json
{
    "mnemonic": "blossom whisper daughter together gospel lava pledge pretty post valley erode ritual",
    "encrypted": false,
    "private_key": "xprv9s21ZrQH143K3K72TX1eLipb8bUHMC2V88QniZfWmakDtA8B4PBFNQwSEWHtLj56wczor9iwvYbXY6vGemtyjaweiv5vrcTSAX2TqGnGnAv",
    "public_key": "xpub661MyMwAqRbcFoBVZYYehrmKgdJmkekLVMLPWx58KvHCkxTKbvVVvDFv5o8GoNsXUGcq7qcwYcs56oTPvWFtCSPfpGHYLVVCEGgLqV1D2tL"
}
```

import private key
----
* Arguments
    1. private_key      (hexstring, required)
    2. address          (string, required)   Check with this compressedAddress
    3. account          (string, optional, default="@Unknown")
* Request example
    * `curl --basic -u user:password -H "accept: application/json" -H "Content-Type: application/json" "127.0.0.1:3000/private/importprivatekey" -d "{\"private_key\": \"681e2c26d6b80eea4b8c68084549e869096ed3237b8d2aa7d687789142733156\", \"address\": \"NC6KDMR3PYPCZQPXGWGIQBLF7IBHET2Z5J7KCVSB\"}"`
* Response
```json
{"status": true}
```
* About
    * It takes many time.
    * You need repair wallet after to reflect transaction history.

move account balance
----
* Arguments
    1. from      (string, optional, default="@Unknown")  Account name.
    2. to        (string, required)  Account name.
    3. coin_id   (numeric, optional, default=0)
    4. amount    (numeric, required)
* Request example
    * `curl --basic -u user:password -H "accept: application/json" -H "Content-Type: application/json" "127.0.0.1:3000/private/move" -d "{\"to\": \"Friends\", \"amount\": 100000000}"`
* Response
```json
{
    "txhash": "00000000000000000000000000000000000000000000000045ec03009dd522a7",
    "from_id": 1,
    "to_id": 5
}
```
* About
    * txhash = (zerofill 24bytes) + (time big endian 4bytes) + (random 4bytes)
    * balance move, from_id => to_id
    * minus amount is allowed.

move many coins
----
* Arguments
    1. from      (string, optional, default="@Unknown")  Account name.
    2. to        (string, required)  Account name.
    3. coins      (object, required) 
* Request example
    * `curl --basic -u user:password -H "accept: application/json" -H "Content-Type: application/json" "127.0.0.1:3000/private/movemany" -d "{\"to\": \"Friends\", \"coins\": {\"0\": 1000}}"`
* Response
```json
{
    "txhash": "00000000000000000000000000000000000000000000000012f40300e190e3e9",
    "from_id": 1,
    "to_id": 5
}
```
* About
    * coins is dictionary, key=coin_id, value=amount.
    * minus amount is allowed, zero is not allowed.

get new address
----
* Arguments
    1. account      (string, optional, default="@Unknown")  Account name.
* Request example
    * `curl --basic -u user:password -H "accept: application/json" -H "Content-Type: application/json" "127.0.0.1:3000/private/newaddress?account=Friend"`
* Response
```json
{
    "account": "Friend",
    "user_id": 6,
    "address": "NBDEHOYV2ZX7CGAXI77IH3DXUDBJA2HFB25FTMAS"
}
```

get keypair
----
* Arguments
    1. address (string, required)
* Request example
    * `curl --basic -u user:password -H "accept: application/json" -H "Content-Type: application/json" "127.0.0.1:3000/private/getkeypair?address=NBDEHOYV2ZX7CGAXI77IH3DXUDBJA2HFB25FTMAS"`
* Response
```json
{
    "uuid": 1262,
    "address": "NBDEHOYV2ZX7CGAXI77IH3DXUDBJA2HFB25FTMAS",
    "private_key": "109145d8e35f51d8de5961f4d151e6c050a6c5e50baed105bfb28bf60b95ac47",
    "public_key": "24475ec3fd3f7a91d1db5301396a6bfbaf13d8c58c19bf8ce8fccab5adb98a92"
}
```
