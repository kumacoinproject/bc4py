Index page
====
* [sample.md](./sample.md)
* [REST response test](./test-response-rest.html)
* [WebSocket response test](./test-response-ws.html)
* [bootstrap3 components](https://getbootstrap.com/docs/3.3/components/)


System
----
[document link](./doc_system.md)

|URL    |Method    |Type    |About   |
|----   |----   |----   |----   |
|[/public/getsysteminfo](./public/getsysteminfo)    |GET    |public   | System public info.                    |
|[/private/getsysteminfo](./private/getsysteminfo)  |GET    |private  | System private info.                   |
|[/public/getchaininfo](./public/getchaininfo)      |GET    |public   | Blockchain info.                       |
|[/private/getchaininfo](./private/getchaininfo)    |GET    |public   | inner chain info of database.          |
|[/public/getnetworkinfo](./public/getnetworkinfo)  |GET    |public   | System network info.                   |
|[/private/resync](./private/resync)                |GET    |private  | Make system resync status.              |
|[/private/stop](./private/stop)                    |GET    |private  | Stop system.                            |

Account
----
[document link](./doc_account.md)

|URL    |Method    |Type    |About   |
|----   |----   |----   |----   |
|[/private/listbalance](./private/listbalance)               |GET    |private  | List all user balance.                 |
|[/private/listtransactions](./private/listtransactions)     |GET    |private  | List user related transaction info.    |
|[/public/listunspents](./public/listunspents)                |GET    |public  | List unused outputs by addresses.      |
|[/private/listunspents](./private/listunspents)              |GET    |private  | List system's unused outputs.         |
|[/private/listaccountaddress](./private/listaccountaddress) |GET    |private  | List user related addresses.          |
|[/private/lockwallet](./private/lockwallet)                  |POST   |private  | delete private key from system        |
|[/private/unlockwallet](./private/unlockwallet)              |POST   |private  | decrypt and recode private key to memory |
|[/private/createwallet](./private/createwallet)              |POST   |private  | generate new wallet private/public pair |
|[/private/importprivatekey](./private/importprivatekey)      |POST   |private  | import private key manually           |
|[/private/move](./private/move)                               |POST   |private  | Move inner account balance.           |
|[/private/movemany](./private/movemany)                       |POST   |private  | Move inner account balances.          |
|[/private/newaddress](./private/newaddress)                   |GET    |private  | Get new incoming address by account.  |
|[/private/getkeypair](./private/getkeypair)                   |GET    |private  | Get keypair by address.               |

Sending
----
[document link](./doc_sending.md)

|URL    |Method    |Type    |About   |
|----   |----   |----   |----   |
|[/public/createrawtx](./public/createrawtx)        |POST   |public   | Create raw transaction by params.   |
|[/private/signrawtx](./private/signrawtx)          |POST   |private  | Sign raw tx by inner keypairs info. |
|[/public/broadcasttx](./public/broadcasttx)        |POST   |public   | Broadcast raw tx.                   |
|[/private/sendfrom](./private/sendfrom)            |POST   |private  | Send to one address.                |
|[/private/sendmany](./private/sendmany)            |POST   |private  | Send to many addresses.             |
|[/private/issueminttx](./private/issueminttx)      |POST   |private  | Issue new mintcoin.                 |
|[/private/changeminttx](./private/changeminttx)    |POST   |private  | Cahge mintcoin's status.            |

Contract
----
[document link](./doc_contract.md)

|URL    |Method    |Type    |About   |
|----   |----   |----   |----   |
|[/public/getcontractinfo](./public/getcontractinfo)           |GET    |public   | Get contract info.                           |
|[/public/getvalidatorinfo](./public/getvalidatorinfo)         |GET    |public   | Get validator info.                          |
|[/public/getcontracthistory](./public/getcontracthistory)           |GET    |public   | Get contract history.                           |
|[/public/getvalidatorhistory](./public/getvalidatorhistory)         |GET    |public   | Get validator history.                          |
|[/public/contractstorage](./public/contractstorage)           |GET    |public   | Get contract storage key-value.              |
|[/private/watchinginfo](./private/watchinginfo)               |GET   |private  | Get account related contrac/validator tx.      |
|[/private/sourcecompile](./private/sourcecompile)             |POST   |private  | Compile source.                              |
|[/private/contractinit](./private/contractinit)               |POST   |private  | Init contract first of all.                  |
|[/private/contractupdate](./private/contractupdate)           |POST   |private  | Update contract params after.                |
|[/private/contracttransfer](./private/contracttransfer)       |POST   |private  | Start contract transaction.                  |
|[/private/concludecontract](./private/concludecontract)       |POST   |private  | Conclude contract transaction.               |
|[/private/validatoredit](./private/validatoredit)              |POST   |private  | Edit validator status.                      |
|[/private/validateunconfirmed](./private/validateunconfirmed) |POST   |private  | Validate unconfirmed contract transactions.  |

Blockchain
----
[document link](./doc_blockchain.md)

|URL    |Method    |Type    |About   |
|----   |----   |----   |----   |
|[/public/getblockbyheight](./public/getblockbyheight)  |GET    |public   | Get block by height.         |
|[/public/getblockbyhash](./public/getblockbyhash)      |GET    |public   | Get block by hash.           |
|[/public/gettxbyhash](./public/gettxbyhash)            |GET    |public   | Get transaction by hash.     |
|[/public/getmintinfo](./public/getmintinfo)            |GET    |public   | Get mintcoin info.           |
|[/public/getminthistory](./public/getminthistory)      |GET    |public   | Get mintcoin history.        |

Others
----
[document link](./doc_others.md)

|URL    |Method    |Type    |About   |
|----   |----   |----   |----   |
|[/public/ws](./public/ws)          |GET   |public      | Realtime information stream.                       |
|[/private/ws](./private/ws)        |GET   |private     | Realtime private information stream.               |
|[/json-rpc](./json-rpc)            |POST   |JSON-RPC   | Mining interface, `getwork` and `getblocktemplete` |


API version 0.0.2 2018/11/23
