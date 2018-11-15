Index page
====
* [all REST methods](./rest.md)
* [sample.md](./sample.md)
* [test response for debug](./testresponse.html)


System
----
|URL    |Method    |Type    |About   |
|----   |----   |----   |----   |
|[/public/getsysteminfo](./public/getsysteminfo)    |GET    |public   | System public info.                    |
|[/private/getsysteminfo](./private/getsysteminfo)  |GET    |private  | System private info.                   |
|[/public/getchaininfo](./public/getchaininfo)      |GET    |public   | Blockchain info.                       |
|[/public/getnetworkinfo](./public/getnetworkinfo)  |GET    |public   | System network info.                   |
|[/private/resync](./private/resync)                |GET    |private  | Make system resync status.              |
|[/private/stop](./private/stop)                    |GET    |private  | Stop system.                            |

Account
----
|URL    |Method    |Type    |About   |
|----   |----   |----   |----   |
|[/private/listbalance](./private/listbalance)               |GET    |private  | List all user balance.                 |
|[/private/listtransactions](./private/listtransactions)     |GET    |private  | List user related transaction info.    |
|[/private/listunspents](./private/listunspents)              |GET    |private  | List system's unused outputs.         |
|[/private/listaccountaddress](./private/listaccountaddress) |GET    |private  | List user related addresses.          |
|[/private/lock](./private/lock)                               |POST   |private  | Encrypt keypair storage.              |
|[/private/unlock](./private/unlock)                           |POST   |private  | Decrypt keypair storage.             |
|[/private/changepassword](./private/changepassword)          |POST   |private  | Change keypair storage password.      |
|[/private/move](./private/move)                               |POST   |private  | Move inner account balance.           |
|[/private/movemany](./private/movemany)                       |POST   |private  | Move inner account balances.          |
|[/private/newaddress](./private/newaddress)                   |GET    |private  | Get new incoming address by account.  |
|[/private/getkeypair](./private/getkeypair)                   |GET    |private  | Get keypair by address.               |

Sending
----
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
|URL    |Method    |Type    |About   |
|----   |----   |----   |----   |
|[/public/getcontractinfo](./public/getcontractinfo)           |GET    |public   | Get contract info.                           |
|[/public/getvalidatorinfo](./public/getvalidatorinfo)         |GET    |public   | Get validator info.                          |
|[/public/contractstorage](./public/contractstorage)           |GET    |public   | Get contract storage key-value.              |
|[/private/sourcecompile](./private/sourcecompile)             |POST   |private  | Compile source.                              |
|[/private/contractinit](./private/contractinit)               |POST   |private  | Init contract first of all.                  |
|[/private/contractupdate](./private/contractupdate)           |POST   |private  | Update contract params after.                |
|[/private/contracttransfer](./private/contracttransfer)       |POST   |private  | Start contract transaction.                  |
|[/private/concludecontract](./private/concludecontract)       |POST   |private  | Conclude contract transaction.               |
|[/private/validatoredit](./private/validatoredit)              |POST   |private  | Edit validator status.                      |
|[/private/validateunconfirmed](./private/validateunconfirmed) |POST   |private  | Validate unconfirmed contract transactions.  |

Blockchain
----
|URL    |Method    |Type    |About   |
|----   |----   |----   |----   |
|[/public/getblockbyheight](./public/getblockbyheight)  |GET    |public   | Get block by height.         |
|[/public/getblockbyhash](./public/getblockbyhash)      |GET    |public   | Get block by hash.           |
|[/public/gettxbyhash](./public/gettxbyhash)            |GET    |public   | Get transaction by hash.     |
|[/public/getmintinfo](./public/getmintinfo)            |GET    |public   | Get mintcoin info.           |

Others
----
|URL    |Method    |Type    |About   |
|----   |----   |----   |----   |
|[/json-rpc](./json-rpc)            |POST   |JSON-RPC   | Mining interface, `getwork` and `getblocktemplete` |


API version 0.0.1 2018/11/15
