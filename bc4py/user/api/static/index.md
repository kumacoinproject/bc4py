Index page
====
[all REST methods](./rest.md)

<table class="table4" border="1">
    <tbody>
    <tr><th>URI</th> <th>Method</th> <th>Params</th> <th>Message</th></tr>
    <tr><td><a href="./api/getsysteminfo">http://127.0.0.1:3000/api/getsysteminfo</a></td><td>GET</td><td></td><td>System info</td></tr>
    <tr><td><a href="./api/getchaininfo">http://127.0.0.1:3000/api/getchaininfo</a></td><td>GET</td><td></td><td>Chain info</td></tr>
    <tr><td><a href="./api/getnetworkinfo">http://127.0.0.1:3000/api/getnetworkinfo</a></td><td>GET</td><td></td><td>Network info</td></tr>
    <tr><td><a href="./api/validatorinfo">http://127.0.0.1:3000/api/validatorinfo</a></td><td>GET</td><td></td><td>Validator info.</td></tr>
    <tr><td><a href="./api/stop">http://127.0.0.1:3000/api/stop</a></td><td>GET</td><td></td><td>stop client.</td></tr>
    <tr><td><a href="./api/resync">http://127.0.0.1:3000/api/resync</a></td><td>GET</td><td></td><td>set True resync flag.</td></tr>
    <tr><td><a href="./api/listbalance">http://127.0.0.1:3000/api/listbalance</a></td><td>GET</td><td>[confirm=6]</td><td>All account balance.</td></tr>
    <tr><td><a href="./api/listtransactions">http://127.0.0.1:3000/api/listtransactions</a></td><td>GET</td><td>[page=0 limit=25]</td><td>Get account transactions.</td></tr>
    <tr><td><a href="./api/listunspents">http://127.0.0.1:3000/api/listunspents</a></td><td>GET</td><td></td><td>Get all unspent and orphan txhash:txindex pairs.</td></tr>
    <tr><td><a href="./api/listaccountaddress">http://127.0.0.1:3000/api/listaccountaddress</a></td><td>GET</td><td>[account=Unknown]</td><td>Get account related addresses.</td></tr>
    <tr><td><a href="./api/lock">http://127.0.0.1:3000/api/lock</a></td><td>GET</td><td></td><td>Lock by random bytes key.</td></tr>
    <tr><td><a href="./api/unlock">http://127.0.0.1:3000/api/unlock</a></td><td>POST</td><td>[password=None]</td><td>Unlock database by key.</td></tr>
    <tr><td><a href="./api/changepassword">http://127.0.0.1:3000/api/changepassword</a></td><td>POST</td><td>[old=None] [new=None]</td><td>Change password.</td></tr>
    <tr><td><a href="./api/move">http://127.0.0.1:3000/api/move</a></td><td>POST</td><td>[from=Unknown] [to] [coin_id=0] [amount]</td><td>Move account balance of single coin.</td></tr>
    <tr><td><a href="./api/movemany">http://127.0.0.1:3000/api/movemany</a></td><td>POST</td><td>[from=Unknown] [to] [coins]</td><td>Move account balance of many coins.</td></tr>
    <tr><td><a href="./api/sendfrom">http://127.0.0.1:3000/api/sendfrom</a></td><td>POST</td><td>[from=Unknown] [address] [coin_id=0] [amount] [message=None]</td><td>Send from account to address.</td></tr>
    <tr><td><a href="./api/sendmany">http://127.0.0.1:3000/api/sendmany</a></td><td>POST</td><td>[from=Unknown] [pairs:list(address,coin_id,amount)] [message=None]</td><td>Send to many account</td></tr>
    <tr><td><a href="./api/issueminttx">http://127.0.0.1:3000/api/issueminttx</a></td><td>POST</td><td>[name] [unit] [amount] [digit=0] <br>
        [message=None] [image=None] [additional_issue=True] [account=Unknown]</td><td>Issue mintcoin.</td></tr>
    <tr><td><a href="./api/changeminttx">http://127.0.0.1:3000/api/changeminttx</a></td><td>POST</td><td>[mint_id] [amount=0] [message=None] [image=None]<br>
        [additional_issue=None] [group=Unknown]</td><td>Chainge mintcoin.</td></tr>
    <tr><td><a href="./api/newaddress">http://127.0.0.1:3000/api/newaddress</a></td><td>GET</td><td>[account=Unknown]</td><td>Get new bind account address.</td></tr>
    <tr><td><a href="./api/getkeypair">http://127.0.0.1:3000/api/getkeypair</a></td><td>GET</td><td>[address]</td><td>Get priKey:pubKey by address.</td></tr>
    <tr><td><a href="./api/createrawtx">http://127.0.0.1:3000/api/createrawtx</a></td><td>POST</td><td>[version=1] [type=TRANSFER] [time=now] [deadline=now+10800] <br>
        [inputs:list((txhash, txindex),..)] <br>[outputs:list((address, coin_id, amount),..)] <br>
        [gas_price=MINIMUM_PRICE] [gas_amount=MINIMUM_AMOUNT] <br>[message_type=None] [message=None]</td><td>Create raw tx without signing.</td></tr>
    <tr><td><a href="./api/signrawtx">http://127.0.0.1:3000/api/signrawtx</a></td><td>POST</td><td>[hex] [pk=list(sk,..)]</td><td>Sign raw tx by manually</td></tr>
    <tr><td><a href="./api/broadcasttx">http://127.0.0.1:3000/api/broadcasttx</a></td><td>POST</td><td>[hex] [signature:list([pk, sign],..)]</td><td>Send raw tx by manually.</td></tr>
    <tr><td><a href="./api/contracthistory">http://127.0.0.1:3000/api/contracthistory</a></td><td>GET</td><td>[address]</td><td>Get contract related txhash(start:finish) pairs.</td></tr>
    <tr><td><a href="./api/contractdetail">http://127.0.0.1:3000/api/contractdetail</a></td><td>GET</td><td>[address]</td><td>Get contract detail by address.</td></tr>
    <tr><td><a href="./api/contractstorage">http://127.0.0.1:3000/api/contractstorage</a></td><td>GET</td><td>[address]</td><td>Get contract storage.</td></tr>
    <tr><td><a href="./api/sourcecompile">http://127.0.0.1:3000/api/sourcecompile</a></td><td>POST</td><td>[source OR path] [name=None]</td><td>Python code to hexstr.</td></tr>
    <tr><td><a href="./api/contractcreate">http://127.0.0.1:3000/api/contractcreate</a></td><td>POST</td><td>[hex] [account=Unknown]</td><td>register contract to blockchain.</td></tr>
    <tr><td><a href="./api/contractstart">http://127.0.0.1:3000/api/contractstart</a></td><td>POST</td><td>[address] [method] [args=None] [gas_limit=100000000] [outputs=list()] <br>
        [account=Unknown]</td><td>create and send start contract.</td></tr>
    <tr><td><a href="./api/getblockbyheight">http://127.0.0.1:3000/api/getblockbyheight</a></td><td>GET</td><td>[height]</td><td>Get blockinfo by height.</td></tr>
    <tr><td><a href="./api/getblockbyhash">http://127.0.0.1:3000/api/getblockbyhash</a></td><td>GET</td><td>[hash]</td><td>Get blockinfo by blockhash.</td></tr>
    <tr><td><a href="./api/gettxbyhash">http://127.0.0.1:3000/api/gettxbyhash</a></td><td>GET</td><td>[hash]</td><td>Get tx by txhash.</td></tr>
    <tr><td><a href="./api/getmintinfo">http://127.0.0.1:3000/api/getmintinfo</a></td><td>GET</td><td>[mint_id]</td><td>Get mintcoin info.</td></tr>
    </tbody>
</table>
<style>
.table4 {
border-collapse: collapse;  width: 100%;}.table4 th, .table4 td {  border: 1px solid gray;}
</style>
If raised error, return string error message. If success, return object except string.<br>Please detect error by string or other objects.