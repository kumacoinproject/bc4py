

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
      selectSection(selectName);
  }

  function selectSection(selectName){
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
        console.log(response.response.data);
        commonMessage(response.response.data, true);
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

  function loginCheck () {
    let axios_option = {
        method: 'get',
        url: this.endpoint+'/private/getsysteminfo',
        auth: {
            username: this.username,
            password: this.password}
    };
    axios(axios_option).then(response => {
        commonMessage('login success! ' + response.data.system_ver);
        this.status = 'login';
    }).catch(response => {
        console.log(response.response.data);
        commonMessage(response.response.data, true);
    });
  }

  function tryLogout (){
    this.username = this.password = '';
    this.status = 'guest';
    commonMessage('logout now.');
  }
