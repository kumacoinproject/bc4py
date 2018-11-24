function Format(format /*,obj1,obj2...*/)
{
    let args = arguments;
    return format.replace(/\{(\d)\}/g, function(m, c) { return args[parseInt(c) + 1] });
}

function timeConverter(UNIX_timestamp){
    let a = new Date(UNIX_timestamp * 1000);
    let months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    let year = a.getFullYear();
    let month = months[a.getMonth()];
    let date = a.getDate();
    let hour = a.getHours();
    let min = a.getMinutes();
    let sec = a.getSeconds();
    return year+'-'+month+'-'+date+' '+hour+':'+min+':'+sec;
}

function getRandomColor() {
    let color = (Math.random() * 0xFFFFFF | 0).toString(16);
    return "#" + ("000000" + color).slice(-6);
}

function urlSerialize( obj ) {
  return '?'+Object.keys(obj).reduce(function(a,k){a.push(k+'='+encodeURIComponent(obj[k]));return a},[]).join('&')
}
