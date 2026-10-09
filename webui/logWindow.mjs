import {createLogs} from './logs.mjs';
import {clockChannelName, createClockReceiver} from './clockRelay.mjs';
import {formatClock, formatValue} from './model.mjs';

// This entry owns only log controls and the mandatory game clock. Opening a
// log window must not duplicate any SSE subscriptions: several full
// worktables can exhaust a browser's per-origin HTTP/1.1 connection pool and
// leave ordinary log requests waiting behind long-lived streams.
const get = id => document.getElementById(id);
function set(id, text) {
  const element = get(id);
  if (element.textContent !== text) element.textContent = text;
}
async function request(path, body) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(path, {method:body ? 'POST' : 'GET', cache:'no-store', signal:controller.signal,
      ...(body ? {headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)} : {})});
    const result = await response.json();
    if (!response.ok || result?.error || result?.ok === false) throw new Error(result.error || result.message || `请求失败 ${response.status}`);
    return result;
  } finally { clearTimeout(timeout); }
}
function toast(message, level = 'info') {
  const item = document.createElement('article'); item.className = 'toast show ' + level;
  item.setAttribute('role', level === 'error' ? 'alert' : 'status');
  const text = document.createElement('p'); text.textContent = message;
  const close = document.createElement('button'); close.textContent = '×'; close.setAttribute('aria-label','关闭提示');
  const dismiss = () => { clearTimeout(timer); item.remove(); };
  close.onclick = dismiss; item.append(text, close); get('toast-stack').append(item);
  const timer = setTimeout(dismiss, level === 'error' ? 7000 : 2500);
  while (get('toast-stack').children.length > 5) get('toast-stack').firstElementChild.remove();
}
const logs = createLogs({command:(action, params) => request('/api/command', {action, params}), toast, visible:() => true});
function renderSharedClock({clock:value, connected, status}) {
  const clock = value || {};
  set('clock-time', formatClock(clock.gameTime));
  set('clock-frame', '逻辑帧 ' + formatValue(clock.fixedFrame));
  const active = status === 'shared' && connected;
  set('clock-source', status === 'waiting' ? '等待同源主工作台共享时钟'
    : ['主工作台共享', active && clock.connected ? '已连接' : '最后已知值', clock.clockSource || '—', clock.message || ''].join(' · '));
  get('clock-time').classList.toggle('source-unavailable', !active || !clock.connected);
  set('transport-status', status === 'waiting'
    ? '尚未收到主工作台时钟；请保持同一浏览器、同一地址的主工作台打开。日志可独立使用。'
    : status === 'lost' ? '未收到主工作台共享更新；时钟为最后已知值，日志可独立使用。'
    : !connected ? '主工作台的时钟通道未连接；显示最后已知值，日志可独立使用。' : '');
}
let receiver = null;
try {
  receiver = createClockReceiver({channel:new BroadcastChannel(clockChannelName), id:crypto.randomUUID(), onChange:renderSharedClock});
} catch {
  get('clock-source').textContent = '窗口时钟共享不可用';
  get('transport-status').textContent = '当前浏览器不支持窗口时钟共享；日志可独立使用，不另建时钟连接。';
}
window.addEventListener('pagehide', () => receiver?.close(), {once:true});
window.addEventListener('pageshow', event => { if (event.persisted) location.reload(); });
// Log reads start immediately, not behind this optional full-state bootstrap.
// It is fetched once solely for shared test-mode/session metadata, not polled.
request('/api/state').then(state => logs.metadata(state.service?.logs)).catch(error => {
  get('log-mode').textContent = '实时诊断日志（运行信息暂不可用）'; toast(error.message, 'warn');
});
