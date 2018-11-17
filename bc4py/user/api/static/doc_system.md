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

get chain info
----
* Request example
    * `curl -H "accept: application/json" 127.0.0.1:3000/public/getchaininfo`
* Response
```json
{
    "best": {
        "hash": "504c71e55ca19a283bc535ea38d15195e640c700bdc8563781530578818d8450",
        "work_hash": "301de7ae678664202f4a0438d609822b93daaa13b51aa2931f48a0f9663f0d00",
        "previous_hash": "e57712d323f4e74d8996e2c6254c8375e66b9d7b390a04a029e4ee188b78d088",
        "next_hash": null,
        "f_orphan": null,
        "f_on_memory": null,
        "height": 5021,
        "difficulty": 0.001965,
        "fixed_difficulty": 0.00064416,
        "flag": "POW_X11",
        "merkleroot": "d04e18946dc92b6f0e80801990af92744d2e056566beafeaa4951429b38a7854",
        "time": 1542367541,
        "bits": 522279172,
        "bias": 3.05050734,
        "nonce": "ce32041e",
        "txs": [
            "d04e18946dc92b6f0e80801990af92744d2e056566beafeaa4951429b38a7854"
        ]
    },
    "mining": {
        "POW_YES": {
            "number": 1,
            "diff": 0.0,
            "bias": 1.0,
            "fixed_diff": 2e-07,
            "hashrate(kh/s)": 0.0,
            "is_base": true
        },
        "POS": {
            "number": 2,
            "diff": 1e-08,
            "bias": 124223.93047213,
            "fixed_diff": 6.82e-06,
            "hashrate(kh/s)": 423.425,
            "is_base": false
        },
        "POW_X11": {
            "number": 4,
            "diff": 0.0,
            "bias": 3.05050734,
            "fixed_diff": 6.6e-06,
            "hashrate(kh/s)": 0.03,
            "is_base": false
        },
        "POW_HMQ": {
            "number": 5,
            "diff": 0.0,
            "bias": 1601.40854757,
            "fixed_diff": 1.67e-06,
            "hashrate(kh/s)": 4.001,
            "is_base": false
        }
    },
    "size": 171,
    "checkpoint": {
        "height": 5020,
        "blockhash": "e57712d323f4e74d8996e2c6254c8375e66b9d7b390a04a029e4ee188b78d088"
    },
    "money_supply": 278020758368594,
    "total_supply": 1000000000000000000
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

