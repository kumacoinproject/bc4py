System
====
Get system info. Control system.

get system info (public)
----
* Request example
    * `curl -H "accept: application/json" 127.0.0.1:3000/private/getsysteminfo`
* Response
```json
{
    "system_ver": "0.0.11-alpha",
    "api_ver": "0.0.2",
    "chain_ver": 2,
    "booting": false,
    "connections": 3,
    "unconfirmed": [],
    "access_time": 1542367031,
    "start_time": 1542366351
}
```

get system info (private)
----
* Request example
    * `curl --basic -u user:password -H "accept: application/json" 127.0.0.1:3000/private/getsysteminfo`
* Response
```json
{
    "system_ver": "0.0.11-alpha",
    "api_ver": "0.0.2",
    "chain_ver": 2,
    "message": "This is alpha version - use at your own risk, do not use for merchant applications.",
    "booting": false,
    "connections": 3,
    "unconfirmed": [],
    "directory": "C:\\Users\\pycoin\\blockchain-py\\2000",
    "encryption": null,
    "generate": {
        "address": null,
        "message": null,
        "threads": [
            "<Generate POW_X11 54.88kh/s limit=0.01>",
            "<Generate POS 843hash/s limit=0.3>"
        ]
    },
    "locked": false,
    "access_time": 1542367267,
    "start_time": 1542366351
}
```

get chain info (public)
----
* Request example
    * `curl -H "accept: application/json" 127.0.0.1:3000/public/getchaininfo`
* Response
```json
{
    "best": {
        "hash": "d50a3896ab6e02829bc8f1e34d9ea106c56aa5a68a42d7080b2c850dc65973d3",
        "work_hash": "6e5c2480c4958d4b7a11a9c14b67d2c3083266f82090f693e19404ef10890400",
        "previous_hash": "52190675da80ab77f7593ac64d0fccf5c983205deebee0c71d6c459bca2bd73a",
        "next_hash": null,
        "f_orphan": false,
        "recode_flag": "memory",
        "height": 117860,
        "difficulty": 0.003388,
        "fixed_difficulty": 0.06406275,
        "score": 11.0676183,
        "flag": "POW_YES",
        "merkleroot": "d0ac7a141e7d7d0051fc94ba62a2291c0a04f20e40852afafc19ca0c0824ce67",
        "time": 1546750370,
        "bits": 521361167,
        "bias": 0.05288565,
        "nonce": "b48ca04e",
        "txs": [
            "d0ac7a141e7d7d0051fc94ba62a2291c0a04f20e40852afafc19ca0c0824ce67"
        ],
        "create_time": 1546750373
    },
    "mining": {
        "POW_YES": {
            "number": 1,
            "bits": "1f135d2f",
            "diff": 3.384e-05,
            "bias": 0.05288565,
            "fixed_diff": 0.00063987,
            "hashrate(kh/s)": 0.051
        },
        "POS": {
            "number": 2,
            "bits": "1d00f325",
            "diff": 45.22041795,
            "bias": 79901.15735973,
            "fixed_diff": 0.00056595,
            "hashrate(kh/s)": 22610.209
        },
        "POW_X11": {
            "number": 4,
            "bits": "1e35c4ad",
            "diff": 0.00312028,
            "bias": 4.57213647,
            "fixed_diff": 0.00068246,
            "hashrate(kh/s)": 4.657
        },
        "POW_HMQ": {
            "number": 5,
            "bits": "1e7700d7",
            "diff": 0.00140981,
            "bias": 1.97356957,
            "fixed_diff": 0.00071435,
            "hashrate(kh/s)": 2.104
        }
    },
    "size": 171,
    "checkpoint": {
        "height": 117859,
        "blockhash": "52190675da80ab77f7593ac64d0fccf5c983205deebee0c71d6c459bca2bd73a"
    },
    "money_supply": 6812647294965298,
    "total_supply": 1000000000000000000
}
```

get chain info (private)
----
* Request example
    * `curl --basic -u user:password -H "accept: application/json" 127.0.0.1:3000/private/getchaininfo`
* Response
```json
{
    "main": [
        {
            "hash": "94614fa1dac80b486e358fe052299958737d18cad1d314b3d629d903002e301f",
            "work_hash": "fa5e59d0590656773a9a67cb88c6db77f347ffac2752ef1c3c0b9f9375580000",
            "previous_hash": "8309e21b5c132a74cd37a9fd0019086d57de22b166e569c38e2c2b394391398a",
            "next_hash": "6fc77422e0381f0d8064c685330987d45e376c39db01a4895e4d31f7fa446fb1",
            "f_orphan": false,
            "recode_flag": "memory",
            "height": 1009,
            "difficulty": 0.150522,
            "fixed_difficulty": 0.00406894,
            "score": 0.0,
            "flag": "POW_X11",
            "merkleroot": "a1da6ea859c66610a8e3b0a34cb5a904ae4176b0ff73f8522520bb6fb0bec804",
            "time": 1544269730,
            "bits": 510621101,
            "bias": 36.99294305,
            "nonce": "b995be71",
            "txs": [
                "a1da6ea859c66610a8e3b0a34cb5a904ae4176b0ff73f8522520bb6fb0bec804"
            ]
        },
        {
            "hash": "8309e21b5c132a74cd37a9fd0019086d57de22b166e569c38e2c2b394391398a",
            "work_hash": "b046fbe2080e44716b9e339e85fc3a7821e1fa375583e641877935c150000000",
            "previous_hash": "9da1b37e36545b565a68964c4b64b669b686385c3a59a40ad506a32c45ef4fd3",
            "next_hash": "94614fa1dac80b486e358fe052299958737d18cad1d314b3d629d903002e301f",
            "f_orphan": false,
            "recode_flag": "memory",
            "height": 1008,
            "difficulty": 41.612413,
            "fixed_difficulty": 0.0052823,
            "score": 0.0,
            "flag": "POS",
            "merkleroot": "9135d3f7703666746caa80565183f69378fd4f79ac7d9037cf58b85c86e8010a",
            "time": 1544269712,
            "bits": 493303471,
            "bias": 7877.70366096,
            "nonce": "ffffffff",
            "txs": [
                "9135d3f7703666746caa80565183f69378fd4f79ac7d9037cf58b85c86e8010a"
            ]
        },
        {
            "hash": "9da1b37e36545b565a68964c4b64b669b686385c3a59a40ad506a32c45ef4fd3",
            "work_hash": "4e7a3c53c6c43ddc34239c4a8c7b5a37a4f11e82084db62d21b77004ea290000",
            "previous_hash": "a45ad86b44b785731143dda6cd379ead3fa10a3599cf9ae97b499721e680f9cd",
            "next_hash": "8309e21b5c132a74cd37a9fd0019086d57de22b166e569c38e2c2b394391398a",
            "f_orphan": false,
            "recode_flag": "memory",
            "height": 1007,
            "difficulty": 0.093574,
            "fixed_difficulty": 0.00448548,
            "score": 0.0,
            "flag": "POW_HMQ",
            "merkleroot": "d28599fb8694b906fbef53b6327398c9fb0c5728f77ab25e0c7e541611d3e19d",
            "time": 1544269711,
            "bits": 520139595,
            "bias": 20.86152522,
            "nonce": "43ffda78",
            "txs": [
                "d28599fb8694b906fbef53b6327398c9fb0c5728f77ab25e0c7e541611d3e19d"
            ]
        },
        {
            "hash": "a45ad86b44b785731143dda6cd379ead3fa10a3599cf9ae97b499721e680f9cd",
            "work_hash": "0a939e0ec74ed074d981190c40546c74d419a6f7e89a61039af3745d077b0000",
            "previous_hash": "987f832b19c26c422342f5fa3bbec35564a69402be9766305d3a791d9bd70294",
            "next_hash": "9da1b37e36545b565a68964c4b64b669b686385c3a59a40ad506a32c45ef4fd3",
            "f_orphan": false,
            "recode_flag": "memory",
            "height": 1006,
            "difficulty": 0.092354,
            "fixed_difficulty": 0.00446185,
            "score": 0.0,
            "flag": "POW_HMQ",
            "merkleroot": "1ff8b11940e6d0ae3209b0438e9bb17072e3161c13641fd0608db22cf8a2d0b0",
            "time": 1544269660,
            "bits": 520140201,
            "bias": 20.69857351,
            "nonce": "44adf660",
            "txs": [
                "1ff8b11940e6d0ae3209b0438e9bb17072e3161c13641fd0608db22cf8a2d0b0"
            ]
        },
        {
            "hash": "987f832b19c26c422342f5fa3bbec35564a69402be9766305d3a791d9bd70294",
            "work_hash": "fe2950d94eb7391902abe601f7fa0301fae651c892e996fc07d782b21d360000",
            "previous_hash": "3c802d5b4c739b5579f26950d5c946f561be85fde190ab155d336bd24532eafa",
            "next_hash": "a45ad86b44b785731143dda6cd379ead3fa10a3599cf9ae97b499721e680f9cd",
            "f_orphan": false,
            "recode_flag": "memory",
            "height": 1005,
            "difficulty": 0.004096,
            "fixed_difficulty": 0.004096,
            "score": 0.0,
            "flag": "POW_YES",
            "merkleroot": "7a2049a55d669c7dccc6cb9aaa88a87b7b9d360a80b8ced06544eba5c8b361e6",
            "time": 1544269658,
            "bits": 521142271,
            "bias": 1.0,
            "nonce": "9320ee85",
            "txs": [
                "7a2049a55d669c7dccc6cb9aaa88a87b7b9d360a80b8ced06544eba5c8b361e6"
            ]
        }
    ],
    "orphan": [
        {
            "hash": "28730213f087e99229875ebeea19f769ea9d529345c15dd40696aa5afdaa8dde",
            "work_hash": "3fd55a6e8796446210ed5870235edcd9e371ccfbd7595c90727f16f1e0b90600",
            "previous_hash": "a45ad86b44b785731143dda6cd379ead3fa10a3599cf9ae97b499721e680f9cd",
            "next_hash": null,
            "f_orphan": true,
            "recode_flag": "memory",
            "height": 1007,
            "difficulty": 0.004096,
            "fixed_difficulty": 0.004096,
            "score": 0.0,
            "flag": "POW_YES",
            "merkleroot": "2b2ad1c4709cab9785a018e9428128120af49dfb24e8289ef89ae7da19a782ac",
            "time": 1544269695,
            "bits": 521142271,
            "bias": 1.0,
            "nonce": "c3e4dd78",
            "txs": [
                "2b2ad1c4709cab9785a018e9428128120af49dfb24e8289ef89ae7da19a782ac"
            ]
        }
    ],
    "root": {
        "hash": "3c802d5b4c739b5579f26950d5c946f561be85fde190ab155d336bd24532eafa",
        "work_hash": "813a48595762ccf244872405cdd759ca68a2b8dba26662b63f6cf8a103000000",
        "previous_hash": "bb545eab008d5f6d6771af5672af90ffa99f8b7d93189cf2ac751a47bbb3d2dc",
        "next_hash": null,
        "f_orphan": null,
        "recode_flag": "memory",
        "height": 1004,
        "difficulty": 25.360664,
        "fixed_difficulty": 0.00362913,
        "score": 0.0,
        "flag": "POS",
        "merkleroot": "5a8d5fd83e408016873754d3b6edbfc312d1540275149da5a8fc3e59a43652d0",
        "time": 1544268285,
        "bits": 503359835,
        "bias": 6988.08277163,
        "nonce": "ffffffff",
        "txs": [
            "5a8d5fd83e408016873754d3b6edbfc312d1540275149da5a8fc3e59a43652d0"
        ]
    }
}
```

get network info
----
* Request example
    * `curl -H "accept: application/json" 127.0.0.1:3000/public/getnetworkinfo`
* Response
```json
{
    "p2p_ver": "1.0.14",
    "status": {
        "name": "Hook:44873",
        "client_ver": "1.0.14",
        "network_ver": 2079627318,
        "p2p_accept": true,
        "p2p_udp_accept": true,
        "p2p_port": 2000,
        "start_time": 1542366352
    },
    "networks": [
        {
            "header": {
                "name": "Cow:27992",
                "client_ver": "1.0.14",
                "network_ver": 2079627318,
                "p2p_accept": true,
                "p2p_udp_accept": true,
                "p2p_port": 2001,
                "start_time": 1542366361
            },
            "neers": [
                "127.0.0.1:2000",
                "127.0.0.1:2002",
                "127.0.0.1:2003"
            ],
            "number": 0,
            "host_port": "127.0.0.1:51204",
            "sock_type": "type/server"
        },
        {
            "header": {
                "name": "Match:77637",
                "client_ver": "1.0.14",
                "network_ver": 2079627318,
                "p2p_accept": true,
                "p2p_udp_accept": true,
                "p2p_port": 2002,
                "start_time": 1542366367
            },
            "neers": [
                "127.0.0.1:2000",
                "127.0.0.1:2001",
                "127.0.0.1:2003"
            ],
            "number": 1,
            "host_port": "127.0.0.1:51232",
            "sock_type": "type/server"
        },
        {
            "header": {
                "name": "Boat:88005",
                "client_ver": "1.0.14",
                "network_ver": 2079627318,
                "p2p_accept": true,
                "p2p_udp_accept": true,
                "p2p_port": 2003,
                "start_time": 1542366374
            },
            "neers": [
                "127.0.0.1:2000",
                "127.0.0.1:2001",
                "127.0.0.1:2002"
            ],
            "number": 3,
            "host_port": "127.0.0.1:51261",
            "sock_type": "type/server"
        }
    ]
}
```

resync
----
* Request example
    * `curl --basic -u user:password -H "accept: application/json" 127.0.0.1:3000/private/resync`
* Response
```text
Resync
```
* About
    * set resync flag, `booting` is `true`.
    * check finish by `booting` is `false`.

stop
----
* Request example
    * `curl --basic -u user:password -H "accept: application/json" 127.0.0.1:3000/private/stop`
* Response
```text
Close after 5 seconds.
```

