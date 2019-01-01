Sending
====

create raw tx
----
* Arguments
    1. version  (numeric, optional, default=__chain_version__)
    2. type     (numeric, optional, default=TRANSFER)
    3. time     (numeric, optional, default=NOW)
    4. deadline (numeric, optional, default=NOW+10800)
    5. inputs         (list, optional, default=[])
    6. outputs        (list, optional, default=[])
    7. gas_price      (numeric, optional, default=MINIMUM_PRICE)
    8. gas_amount     (numeric, optional, default=tx_size())
    9. message_type   (numeric, optional, default=MSG_NONE)
    10. message        (numeric, optional, default=None)
* Request example
    * `curl -H "accept: application/json"  -H "Content-Type: application/json" "127.0.0.1:3000/public/createrawtx" -d "{\"version\": 2}"`
* Response
```json
{
    "tx": {
        "hash": "6d2439781672827d7d4a2e99a92453a4713dbf966f613d49dc36640aae62f392",
        "pos_amount": null,
        "height": null,
        "version": 2,
        "type": "TRANSFER",
        "time": 1542376289,
        "deadline": 1542387089,
        "inputs": [],
        "outputs": [],
        "gas_price": 100,
        "gas_amount": 39,
        "message_type": "NONE",
        "message": "",
        "signature": [],
        "recode_flag": "memory"
    },
    "hex": "020000000300000022fd0300522704006400000000000000270000000000000000000000000000"
}
```
* About
    * time is `unixtime - BLOCK_GENESIS_TIME`

sign raw tx
----
* Arguments
    * hex     (hex string, required)  Raw transaction binary.
    * pairs   (numeric, optional, default=[])  SecretKey hex string list.
* Request example
    * `curl --basic -u user:password -H "accept: application/json"  -H "Content-Type: application/json" "127.0.0.1:3000/private/signrawtx" -d "{\"hex\": \"020000000300000022fd03005227040064000000000000002700
00000000000000000000000000\"}"`
* Response
```json
{
    "hash": "6d2439781672827d7d4a2e99a92453a4713dbf966f613d49dc36640aae62f392",
    "signature": [
        ["eeadb99dfe647348818951c012c81f31f5337e07e8a9d398888a7239223237d7", "00ea86e44703d954d295cb706b481d5261e6df561e0a279acf94c35a956a66f92be38a4e34e6caffbdae367582f0aa916970387d7dacd28005021c0bb6c7e2c6"]
    ],
    "hex": "020000000300000022fd0300522704006400000000000000270000000000000000000000000000"
}
```
* About
    * signature is `[(ck, signature), ..]`.

broadcast tx
----
* Arguments
    1. hex        (hex string, required)  Raw transaction binary.
    2. signature  (list, required)  `[(ck, signature), ..]`
* Request example
    * `curl --basic -u user:password -H "accept: application/json"  -H "Content-Type: application/json" "127.0.0.1:3000/private/signrawtx" -d "{\"hex\": \"020000000300000022fd0300522704006400000000000000270000000000000000000000000000\", \"signature\": [[\"eeadb99dfe647348818951c012c81f31f5337e07e8a9d398888a7239223237d7\", \"00ea86e44703d954d295cb706b481d5261e6df561e0a279acf94c35a956a66f92be38a4e34e6caffbdae367582f0aa916970387d7dacd28005021c0bb6c7e2c6\"]]}"`
* Response
```json
{
    "hash": "6d2439781672827d7d4a2e99a92453a4713dbf966f613d49dc36640aae62f392",
    "gas_amount": 360,
    "gas_price": 100,
    "fee": 36000,
    "time": 0.21
}
```

send from
----
* Arguments
    1. from      (string, optional, default="@Unknown")  Account name.
    2. address   (string, required)
    3. coin_id   (numeric, optional, default=0)
    4. amount    (numeric, required)
    5. message   (string, optional, default=None)
    6. hex       (hex string, optional, default=None)
* Request example
    * `curl --basic -u user:password -H "accept: application/json"  -H "Content-Type: application/json" "127.0.0.1:3000/private/sendfrom" -d "{\"address\": \"NB2YGMP4ISW5ALNATGE7LCH3WM5OSJHURFBYM3MS\", \"amount\": 10000000000}"`
* Response
```json
{
    "hash": "c6c9d3d93e213edc9d6c9a15cdcb042f281ec47801d35cbc8de7968ab70e286c",
    "gas_amount": 272,
    "gas_price": 100,
    "fee": 27200,
    "time": 0.096
}
```

send many
----
* Arguments
    1. from      (string, optional, default="@Unknown")  Account name.
    2. pairs     (list, required) `[(address, coin_id, amount), ..]`
    3. message   (string, optional, default=None)
    4. hex       (hex string, optional, default=None)
* Request example
    * `curl --basic -u user:password -H "accept: application/json"  -H "Content-Type: application/json" "127.0.0.1:3000/private/sendmany" -d "{\"pairs\": [[\"NDVZY36JGIEEIX4A5R3Q6WQYRXUWNSKL3B2BEVOW\", 0, 100000], [\"NCMOZSSREWLEE4UDH5UQAT4HLEUQ66O5DJP3UHFM\", 0, 30000]]}"`
* Response
```json
{
    "hash": "677f966022f87a51a2077c01fc58fe6dde086f2e955358fa6855da58b5a52c9b",
    "gas_amount": 324,
    "gas_price": 100,
    "fee": 32400,
    "time": 0.08
}
```

issue mintcoin
----
* Arguments
    1. from          (string, optional, default="@Unknown")  Account name.
    2. name          (string, required)   Ex, PyCoin
    3. unit          (string, required)   Ex, PC
    5. digit         (numeric, optional, default=8)
    4. amount        (numeric, required)  minting amount
    6. description   (string, optional, default=None)
    7. image         (string, optional, default=None)  URL for image
    8. additional_issue  (string, optional, default=true)
* Request example
    * `curl --basic -u user:password -H "accept: application/json"  -H "Content-Type: application/json" "127.0.0.1:3000/private/issueminttx" -d "{\"name\": \"FriendCoin\", \"unit\": \"FC\", \"amount\": 100000000, \"description\": \"example for api.\"}"`
* Response
```json
{
    "hash": "d30e93d347da3c8eaa23fad7b1b3cbf0ce2e9eaf2b4f9e7a47a7df153932ddf2",
    "gas_amount": 10000551,
    "gas_price": 100,
    "fee": 1000055100,
    "time": 0.117,
    "mint_id": 3414534983
}
```
* About

change mintcoin status
----
* Arguments
    1. from      (string, optional, default="@Unknown")  Account name.
    2. mint_id   (numeric, required)  mintcoin's coin_id
    3. amount    (numeric, optional, default=0)  additional mint amount
    4. description   (string, optional, default=None)
    5. image     (string, optional, default=None)  URL for image
    6. setting  (string, optional, default=None)
    7. new_address  (string, optional, default=None)  New owner address
* Request example
    * `curl --basic -u user:password -H "accept: application/json"  -H "Content-Type: application/json" "127.0.0.1:3000/private/changeminttx" -d "{\"mint_id\": 4191737937, \"image\": \"https://i.imgur.com/fRJV4ps.png\"}"`
* Response
```json
{
    "hash": "19bb18862b913499c3f9d7e3d41bd0fab459436fb091d4d6bf2b7874e39fdef1",
    "gas_amount": 10000347,
    "gas_price": 100,
    "fee": 1000034700,
    "time": 0.149
}
```
