from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bc4py.database.builder import *

"""
database object
====
warning: do not import bc4py.* on this file
"""


tables: 'Tables' = None
chain_builder: 'ChainBuilder' = None
tx_builder: 'TransactionBuilder' = None
account_builder: 'AccountBuilder' = None


__all__ = [
    "tables",
    "chain_builder",
    "tx_builder",
    "account_builder",
]
