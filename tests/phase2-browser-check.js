'use strict';
// Exercise the real local browser with native keyboard events. Collected JS is never run.
const fs = require('node:fs');
const path = require('node:path');
const {spawn} = require('node:child_process');
const {createHash} = require('node:crypto');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const output = path.join(root, '.cache', 'phase2-ui-qa');
fs.mkdirSync(output, {recursive:true});
const chrome = process.env.MOTIONLAB_QA_CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const origin = 'http://127.0.0.1:8791';
const report = {checks:[], complete:false};
const runId=process.pid+'-'+Date.now();
const initialUrl='about:blank#motionlab-ui-qa-'+runId;
let browserStderr='';
const browser = spawn(chrome, ['--headless=new','--no-first-run','--disable-background-networking',
  '--disable-extensions','--disable-default-apps',
  '--remote-debugging-address=127.0.0.1','--remote-debugging-port=8792',
  '--user-data-dir='+path.join(output,'profile-'+runId),'--window-size=1440,1080',initialUrl],
  {windowsHide:true, stdio:['ignore','ignore','pipe']});
browser.stderr.on('data',chunk=>{browserStderr=(browserStderr+String(chunk)).slice(-8192);});
browser.on('error',error=>{report.launchError=String(error);});
let socket;
const delay = ms => new Promise(resolve=>setTimeout(resolve,ms));
const pending = new Map();
let sequence = 0;
async function until(fn, label, timeout=30000) {
  const started=Date.now();
  while(Date.now()-started<timeout){const value=await fn();if(value)return value;await delay(100);}
  throw new Error('Timed out: '+label);
}
function call(method, params={}) {
  const id=++sequence;
  return new Promise((resolve,reject)=>{
    const timer=setTimeout(()=>{pending.delete(id);reject(new Error('CDP timeout: '+method));},30000);
    pending.set(id,{resolve,reject,timer});socket.send(JSON.stringify({id,method,params}));
  });
}
async function evaluate(expression) {
  const value=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});
  if(value.exceptionDetails)throw new Error(value.exceptionDetails.exception?.description || value.exceptionDetails.text);
  return value.result.value;
}
async function key(key,code,number) {
  await call('Input.dispatchKeyEvent',{type:'keyDown',key,code,windowsVirtualKeyCode:number,nativeVirtualKeyCode:number,...(key==='Enter'?{text:'\r',unmodifiedText:'\r'}:{})});
  await call('Input.dispatchKeyEvent',{type:'keyUp',key,code,windowsVirtualKeyCode:number,nativeVirtualKeyCode:number});
}
async function click(id){await evaluate('document.getElementById('+JSON.stringify(id)+').click()');}
function check(name, value) {assert.ok(value,name);report.checks.push(name);}
(async()=>{
  try{
    const tab=await until(async()=>{try{
      const ownEndpoint=browserStderr.match(/DevTools listening on (ws:\/\/127\.0\.0\.1:8792\/devtools\/browser\/[a-f0-9-]+)/)?.[1];
      if(!ownEndpoint)return false;
      const version=await (await fetch('http://127.0.0.1:8792/json/version')).json();
      if(version.webSocketDebuggerUrl!==ownEndpoint)return false;
      const tabs=await (await fetch('http://127.0.0.1:8792/json/list')).json();
      report.initialPageUrls=tabs.filter(tab=>tab.type==='page').map(tab=>tab.url);
      // Only this launched instance can match its stderr endpoint. Chrome may strip an about:blank fragment.
      return tabs.find(tab=>tab.type==='page'&&tab.url===initialUrl)||tabs.find(tab=>tab.type==='page');
    }catch(error){report.debuggerConnectionError=String(error);return false;}},'owned Chrome debugger tab');
    socket=new WebSocket(tab.webSocketDebuggerUrl);
    await new Promise((resolve,reject)=>{socket.addEventListener('open',resolve,{once:true});socket.addEventListener('error',reject,{once:true});});
    socket.addEventListener('message',event=>{const value=JSON.parse(event.data);const request=pending.get(value.id);if(!request)return;clearTimeout(request.timer);pending.delete(value.id);value.error?request.reject(new Error(value.error.message)):request.resolve(value.result);});
    await call('Page.enable');await call('Runtime.enable');
    await call('Page.navigate',{url:origin+'/library.html'});
    await until(()=>evaluate('document.querySelectorAll(".asset-card").length===20'),'initial stored assets');
    const catalogBytes=fs.readFileSync(path.join(root,'data/catalog.json'));
    const data=JSON.parse(catalogBytes);
    report.catalogSha256=createHash('sha256').update(catalogBytes).digest('hex');
    report.rendererSha256=createHash('sha256').update(fs.readFileSync(path.join(root,'dist/preview.js'))).digest('hex');
    report.interfaceSha256=createHash('sha256').update(fs.readFileSync(path.join(root,'dist/app.js'))).digest('hex');
    const version=await call('Browser.getVersion');report.browser=version.product;
    const counts=await evaluate('({motion:document.querySelector("#assets-tab span").textContent,design:document.querySelector("#design-tab span").textContent,references:document.querySelector("#references-tab span").textContent})');
    for(const [key,count] of Object.entries({...data.stats.domains,references:data.stats.kinds.reference}))
      check(key+' count excludes other domains',Number(counts[key].replace(/\D/g,''))===count);
    check('default Motion selection',await evaluate('document.getElementById("assets-tab").getAttribute("aria-selected")==="true"'));
    await evaluate('document.querySelector(".asset-card-button").focus()');
    await key('ArrowRight','ArrowRight',39);
    check('native right arrow moves gallery focus',await evaluate('document.activeElement.dataset.gridIndex==="1"'));
    await key('Enter','Enter',13);
    check('native Enter opens original detail',await evaluate('document.getElementById("detail-dialog").open'));
    await key('Escape','Escape',27);
    check('native Escape closes detail',await evaluate('!document.getElementById("detail-dialog").open'));
    await evaluate('document.getElementById("assets-tab").focus()');
    await key('ArrowRight','ArrowRight',39);
    check('native right arrow reaches Design tab',await evaluate('document.activeElement.id==="design-tab"'));
    await key('Enter','Enter',13);
    const cssDocument=await evaluate('document.querySelector("#gallery iframe")?.srcdoc');
    if(cssDocument)fs.writeFileSync(path.join(output,'pattern-preview.html'),cssDocument);
    if(data.items.some(item=>item.id==='ml-css-pattern-g1'))check('authored pattern background survives CSS isolation',Boolean(cssDocument?.includes('conic-gradient(')&&cssDocument.includes('background-size:')));
    check('static design has no playback control',await evaluate('document.getElementById("motion-toggle").hidden&&getComputedStyle(document.getElementById("motion-toggle")).display==="none"'));
    check('Design has its own active tab',await evaluate('document.getElementById("design-tab").getAttribute("aria-selected")==="true"'));
    await evaluate('document.getElementById("page-size-select").focus()');
    await key('ArrowDown','ArrowDown',40);await key('Enter','Enter',13);
    check('native select supports 50 entries',await evaluate('document.getElementById("page-size-select").value==="50"&&document.querySelectorAll(".asset-card").length===50'));
    await evaluate('document.getElementById("page-size-select").value="100";document.getElementById("page-size-select").dispatchEvent(new Event("change",{bubbles:true}))');
    check('100 entry layout',await evaluate('document.querySelectorAll(".asset-card").length===100'));
    await click('language-button');check('English translation',await evaluate('document.documentElement.lang==="en"&&document.getElementById("design-tab").textContent.includes("Design")'));
    await click('language-button');check('Korean translation',await evaluate('document.documentElement.lang==="ko"&&document.getElementById("design-tab").textContent.includes("디자인")'));
    const image=data.items.find(item=>item.kind==='image');assert.ok(image);
    await evaluate('document.getElementById("search-input").value='+JSON.stringify(image.id)+';document.getElementById("search-input").focus()');
    await key('Enter','Enter',13);
    await until(()=>evaluate('document.querySelector(".motion-preview-image")?.complete&&document.querySelector(".motion-preview-image").naturalWidth>0'),'actual material image');
    check('material search returns one stored image',await evaluate('document.querySelectorAll(".asset-card").length===1'));
    await key('Enter','Enter',13);
    await until(()=>evaluate('document.getElementById("detail-dialog").open&&document.querySelector("#detail-dialog img")?.naturalWidth>0'),'material detail');
    check('image detail keeps actual dimensions and download',await evaluate('!!document.querySelector("#detail-dialog a[download]")&&document.querySelector("#detail-dialog img").naturalWidth===1024&&!document.getElementById("detail-motion-toggle")'));
    await click('detail-close');await click('reset-filters');
    await call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:false});
    check('mobile width has no horizontal overflow',await evaluate('document.documentElement.scrollWidth<=390'));
    await call('Emulation.clearDeviceMetricsOverride');
    await delay(1000); // Let newly mounted isolated CSS documents paint before capture.
    const screenshot=await call('Page.captureScreenshot',{format:'png'});
    fs.writeFileSync(path.join(output,'design-library.png'),Buffer.from(screenshot.data,'base64'));
    await call('Page.navigate',{url:origin+'/library.html?domain=design'});
    await until(()=>evaluate('document.querySelectorAll(".asset-card").length===20'),'design deep link');
    check('design deep link selects domain',await evaluate('document.getElementById("design-tab").getAttribute("aria-selected")==="true"'));
    report.complete=true;report.catalogStoredAssets=data.stats.storedAssets;
  }catch(error){report.error=String(error.stack||error);try{report.url=await evaluate('location.href');fs.writeFileSync(path.join(output,'failure.html'),await evaluate('document.documentElement.outerHTML'));}catch{}process.exitCode=1;}
  finally{
    if(!report.complete)report.browserLaunchStderr=browserStderr;
    fs.writeFileSync(path.join(output,'report.json'),JSON.stringify(report,null,2)+'\n');
    if(socket?.readyState===WebSocket.OPEN){try{await call('Browser.close');}catch{}socket.close();}
    browser.kill();browser.stderr.destroy();console.log(JSON.stringify(report,null,2));
  }
})();
