http/ws proxy introduction
====
We are often requested "always-on SSL" (HTTPS) compliant.
A browser display a warning when we access HTTP sites.
However, we need root privilege to user SSL port(443), is not recommended.
That's why I wrote a method to setup local proxy. [JP](https://gist.github.com/namuyan/a94d2363cc363a5d8393c8716d8f5143)


Init env
----
1. `sudo apt-get install nodejs`
2. ```sudo ln -s `which nodejs` /usr/bin/node```
3. check `nodejs -v`
4. `sudo apt-get install npm`
5. `mkdir proxy && cd proxy && mkdir ssl`
6. `npm init`

edit package.json
----
Add `fs` and `http-proxy` to dependencies.
```json
{
   "name": "proxy",
   "version": "1.0.0",
   "description": "Proxy server.",
   "main": "index.js",
   "scripts": {
      "start": "node index.js &",
      "stop": "./stop.sh"
   },
   "author": "Robert Lie",
   "license": "ISC",
   "dependencies": {
      "fs": "0.0.1-security",
      "http-proxy": "^1.16.2"
   }
} 
```

start/stop proxy
----
1. start by `sudo npm start`
2. stop by `sudo npm stop`

index.js
----
start by index.js, very simple proxy server.
```javascript
var httpProxy = require('http-proxy'),
    fs = require('fs');
 
var ssl = {
  key: fs.readFileSync('./ssl/priv.pem', 'utf8'),
  cert: fs.readFileSync('./ssl/cert.pem', 'utf8')
};
 
var server = httpProxy.createProxyServer({
  target: {host: 'localhost', port: 3000},
  ssl: ssl,
  ws: true,
  xfwd: true
});
 
server.on('error', function(err, req, res) {
  res.end();
});
 
server.listen(443);
```
