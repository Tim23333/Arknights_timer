import {getPresentationClient, standbyDestination} from './presentation.mjs';
const clientId=await getPresentationClient();
const status=document.querySelector('#status'), button=document.querySelector('#resume');
async function command(target) {
  const controller=new AbortController(), timer=setTimeout(()=>controller.abort(),15000);
  try {
    const response=await fetch('/api/command',{method:'POST',signal:controller.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'frontend',params:{target,clientId}})});
    const data=await response.json(); if(!response.ok) throw Error(data.error || '切换失败'); return data;
  } finally {clearTimeout(timer);}
}
button.onclick=async()=>{
  button.disabled=true;
  try { const {token}=await command('request-web'); location.replace('/?handoff='+encodeURIComponent(token)); }
  catch(error){status.textContent=error.message;button.disabled=false;}
};
// Only a tiny control-plane request; no clock/modules/EventSource/map work.
async function check(){
  try { const destination=standbyDestination(await command('page-status')); if(destination) {window.focus();location.replace(destination);} }
  catch { status.textContent='后端暂不可达，正在等待恢复'; }
  setTimeout(check,2000);
}
check();
window.addEventListener('pageshow',event=>{if(event.persisted) location.reload();});
