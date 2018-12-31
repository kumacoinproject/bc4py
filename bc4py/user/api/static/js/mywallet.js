  //httpGet = axios.create({
    // set by 'params'
    //method: 'get',
    //baseURL: app.endpoint,
    //responseType: 'json',
  //});

  //httpPost = axios.create({
    // set by 'data'
    //method: 'post',
    //baseURL: app.endpoint,
    //headers: {'Content-Type': 'application/json'},
    //responseType: 'json',
  //});

  function topSelect(selectName){
      const b = document.getElementById("select-button");
      const pointClass = 'is-primary';
      for (let key in b.children) {
        let obj = b.children[key];
        if (typeof obj !== 'object'){continue;}
        if (obj.innerHTML === selectName) {
            obj.classList.add(pointClass);
        }else if (obj.classList.contains(pointClass)) {
            obj.classList.remove(pointClass);
        }
      }
      displaySection(selectName);
  }

  function displaySection(selectName){
      const b = document.getElementById("info");
      for (let key in b.children) {
        let obj = b.children[key];
        if (typeof obj !== 'object' && obj.tagName !== 'SECTION'){continue;}
        if (obj.firstChild.innerHTML === selectName) {
            obj.style['display'] = 'block';
        }else {
            obj.style['display'] = 'none';
        }
      }
  }

  function commonMessage(setMessage, setError=false){
      const c = document.getElementsByClassName('common-message');
      for (let key in c){
        let obj = c[key];
        if (typeof obj !== 'object' || obj.tagName!=='SPAN'){continue;}
        if (setError){
            obj.textContent = 'Error! ' + setMessage;
            obj.style.color = 'red';
        }else {
            obj.textContent = 'Notice: ' + setMessage;
            obj.style.color = 'black';
        }
      }
  }

  function updateBlockInfo () {
    let axios_option = {
        method: 'get',
        url: app.endpoint+'/public/getchaininfo',
    };
    axios(axios_option).then(response => {
        console.log(response);
        const bestblock = document.getElementById('bestblock-info');
        const mining = document.getElementById('mining-info');
        bestblock.innerHTML = dict2PreText(response.data.best);
        mining.innerHTML = dict2PreText(response.data.mining, 15);
        commonMessage('update block info ' + response.data.best.height);
    }).catch(response => {
        console.log(response);
        commonMessage(response, true);
    });
  }

  function updateAccountInfo (confirm=6, page=0){
    if (app.status!=='login'){commonMessage('You are not login!', true)}
    let axios_option = {
      method: 'get',
      url: app.endpoint+'/private/listbalance',
      params: {
        confirm :confirm,
        limit: 3,
        page: page
      },
      auth: {
        username: app.username,
        password: app.password
      }
    };
    axios(axios_option).then(response => {
        console.log(response);
        const b = document.getElementById('account-balance');
          b.innerHTML = '';
          for (let key in response.data){
            let data = response.data[key];
            b.innerHTML +=
              '<section class="nes-container with-title">' +
                `<h3 class="title">${key}</h3>` +
                '<pre>' + dict2PreText(data) + '</pre>' +
                '</section>';
          }
          commonMessage('/update account balance and history.');
          axios_option.url = app.endpoint+'/private/listtransactions';
          return axios(axios_option);
      }).then(response => {
        const b = document.getElementById('account-history');
        b.innerHTML = '';
        for (let key in response.data.txs){
          let data = response.data.txs[key];
          b.innerHTML +=
              '<section class="nes-container with-title">' +
              `<h3 class="title">${data.index}</h3>` +
              '<pre>' + dict2PreText(data) + '</pre>' +
              '</section>';
        }
        b.innerHTML += `<button onclick="updateAccountInfo(6, ${page+1})">Next</button>`;
        console.log(response.data);
      }).catch(response => {
        commonMessage(response, true);
      });
  }

  function updateAccounts() {
    if (app.status!=='login'){commonMessage('You are not login!', true)}
    let axios_option = {
      method: 'get',
      url: app.endpoint+'/private/listbalance',
      auth: {
        username: app.username,
        password: app.password}
    };
    axios(axios_option).then(response => {
        console.log(response);
        for (let accountName in response.data){
            Vue.set(app.accounts, accountName, response.data[accountName]);
        }
    }).catch(response => {
        commonMessage(response, true);
    });
  }

  function updateSender(selectObject){
      function getSelected(s){
          for (let k in s.children){
          if (typeof s.children[k]!=='object'){continue;}
          if (s.children[k].selected){
            return s.children[k];
          }
        }
      }
      const select = getSelected(selectObject);
  }

  function addRecipients(formObject) {
      const addressObj = formObject.nextElementSibling,
          coinIdObj = addressObj.nextElementSibling,
          amountObj = coinIdObj.nextElementSibling;
      try {
          const el = [addressObj.value.trim(), Number(coinIdObj.value), Number(amountObj.value)];
          Vue.set(app.sendInfo.recipients, app.sendInfo.recipients.length, el);

        console.log(address, coinId, amount);
      }catch (e) {
          commonMessage(String(e), true);
      }
  }

  function removeRecipients(Obj){
      function getIndex() {
          const p = Obj.parentNode.parentNode.children;
          for (let k in p){
            if (Obj.parentNode.textContent===p[k].textContent){
                return k;
            }
          }
      }
      Vue.delete(app.sendInfo.recipients, getIndex());
  }

  function trySendto(btnObj){
      const msgInfo = app.sendMessageInfo;
      var message = null, hexMessage = null;
      if (msgInfo==='Plain message'){
          message = app.sendInfo.message;
      } else if (msgInfo==='Hex string') {
          hexMessage = app.sendInfo.message.toLocaleLowerCase();
      }
      let axios_option = {
        method: 'post',
        url: app.endpoint+'/private/sendmany',
        headers: {'Content-Type': 'application/json'},
        responseType: 'json',
        auth: {
          username: app.username,
          password: app.password
        },
        data: {
          from: app.sendInfo.sender,
          pairs: app.sendInfo.recipients,
          hex: hexMessage,
          message: message
        }
      };
      axios(axios_option).then(response => {
          commonMessage('sending success!');
          const el = document.getElementById('send-result');
          el.innerHTML = '<section class="nes-container with-title">' +
              '<h4 class="title">result</h4>' + dict2PreText(response.data, 12) + '</section>';
      }).catch(response => {
          commonMessage(response, true);
      });
  }

  function resetSendto (){
      const tmp = {
          sender: null,
          recipients: [],
          hexMessage: null,
          message: null
      };
      Vue.set(app, 'sendInfo', tmp);
  }

  function tryContract(btnObj) {
    const p = document.getElementById('contract-params'),
        params = app.contracts[app.contractInfo.address][1][app.contractInfo.method];
    var args = [];
    for (let k in params){
        const inputObj = p.children[k].lastElementChild.lastElementChild,
            typeName = params[k][1];
        if (inputObj.style['color']!=='black'){
            commonMessage(`Please check JSON format of argument ${k}.`, true);
            return;
        }
        const inputValue = JSON.parse(inputObj.value);
        if (typeof inputValue!==typeName){
            console.log(`failed: arg=${k} type=${typeName} input=${inputValue}`);
            commonMessage(`Please check type format of argument ${k}.`, true);
            return;
        }
        args.push(inputValue);
    }
    if (app.status!=='login'){
        commonMessage('you are not login!', true);
        return;
    }
    const axios_option = {
        method: 'post',
        url: app.endpoint+'/private/contracttransfer',
        headers: {'Content-Type': 'application/json'},
        responseType: 'json',
        auth: {
            username: app.username,
            password: app.password
        },
        data: {
            c_address: app.contractInfo.address,
            c_method: app.contractInfo.method,
            c_args: args,
            // send_pairs:
            // from:
        }
    };
    axios(axios_option).then(response => {
        btnObj.nextElementSibling.innerHTML = dict2PreText(response.data, 13);
        commonMessage('success contract request!');
    }).catch(response => {
        commonMessage(response, true);
    });
  }

  function dict2PreText(dict, len=18, preSpace='') {
    let data = '';
    for (let key in dict){
        if (Array.isArray(dict)){
            data += preSpace + key + ': ';
        } else {
            data += preSpace + key + ' '.repeat(len - key.length);
        }
        if (typeof dict[key] === 'object') {
            let d = dict2PreText(dict[key], len, preSpace + ' '.repeat(len));
            data += '\n' + d + '\n';
        }else {
            data += dict[key] + '\n';
        }
    }
    return data;
  }

  function inputJsonCheck(Obj){
      // Set the input color red when failed json parse.
      // <input type="text" oninput="inputJsonCheck(this);" style="color: black;">
      try {
          JSON.parse(Obj.value);
          Obj.style['color'] = 'black';
      }catch (e) {
          Obj.style['color'] = 'red';
      }
  }

  function loginCheck () {
    let axios_option = {
        method: 'get',
        url: app.endpoint+'/private/getsysteminfo',
        auth: {
            username: app.username,
            password: app.password}
    };
    axios(axios_option).then(response => {
        commonMessage('login success! ' + response.data.system_ver);
        app.status = 'login';
        actionCookie('update');
    }).catch(response => {
        commonMessage(response, true);
    });
  }

  function tryLogout (){
    app.username = app.password = '';
    app.status = 'guest';
    commonMessage('logout now.');
    actionCookie('remove');
  }

  function actionCookie(action){
    if (action==='update'){
        window.$cookies.set('mywallet-username', app.username);
        window.$cookies.set('mywallet-password', app.password);
    } else if (action==='remove'){
        window.$cookies.remove('mywallet-username');
        window.$cookies.remove('mywallet-password');
    } else if (action==='init'){
        if(!window.$cookies.isKey('mywallet-username')){ return; }
        app.username = window.$cookies.get('mywallet-username');
        app.password = window.$cookies.get('mywallet-password');
        loginCheck();
    }
  }
