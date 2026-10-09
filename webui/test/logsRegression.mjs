import {createLogs} from '../logs.mjs';
// External modules work under the actual WebUI script-src 'self' policy.
window.addEventListener('error', event => { document.getElementById('result').textContent = '测试页面错误：' + event.message; });
window.addEventListener('unhandledrejection', event => { document.getElementById('result').textContent = '测试页面错误：' + event.reason; });
const source = await fetch('../index.html', {cache:'no-store'}).then(response => response.text());
const markup = new DOMParser().parseFromString(source, 'text/html');
const page = markup.getElementById('page-logs');
page.classList.add('active');
document.getElementById('fixture').append(page);
let session = 'a', requests = [];
const datasets = {a:[{seq:1,text:'旧会话第一行'}, {seq:2,text:'旧会话第二行'}], b:[{seq:1,text:'新会话仅有的一行'}]};
const logs = createLogs({visible:() => true, toast:() => {}, openPopup:() => {},
  command:async (action, {after}) => {
    if (action === 'logs-export') return {id:'test-export', status:'done', message:'合成日志导出完成',
      result:{url:'/test/fixture-export.log', filename:'fixture-export.log'}};
    if (action !== 'logs-read') throw new Error('测试禁止执行其他命令');
    requests.push({session, after});
    const items = datasets[session].filter(row => row.seq > after);
    return {sessionId:session, items, nextCursor:items.at(-1)?.seq ?? Math.min(after,datasets[session].length), logPath:'合成日志'};
  }});
const waitFor = async predicate => {
  const deadline = performance.now() + 3000;
  while (!predicate() && performance.now() < deadline) await new Promise(resolve => setTimeout(resolve, 25));
  return predicate();
};
document.getElementById('run').disabled = false;
document.getElementById('result').textContent = '等待测试';
document.getElementById('run').onclick = async () => {
  const result = document.getElementById('result');
  result.textContent = '测试中…';
  session = 'a';
  logs.metadata({sessionId:'a', logPath:'合成日志', testMode:false});
  await waitFor(() => document.getElementById('log-table').textContent.includes('旧会话第二行'));
  requests = [];
  // ROOT CAUSE: sending an old high cursor to a restarted logger returns an
  // empty page and the new last sequence. Without refetching from zero, that
  // new session's initial lines are never displayed until another line arrives.
  session = 'b';
  const recovered = await waitFor(() => document.getElementById('log-table').textContent.includes('新会话仅有的一行'));
  const noOldRows = !document.getElementById('log-table').textContent.includes('旧会话');
  const resetCursor = requests.some(request => request.session === 'b' && request.after === 0);
  const link = document.getElementById('logs-window');
  const independentLink = link.tagName === 'A' && new URL(link.href).pathname === '/logs.html'
    && link.target === '_blank' && link.rel.split(' ').includes('noopener');
  const search = document.getElementById('logs-search');
  search.value = '没有匹配'; search.dispatchEvent(new Event('input'));
  const emptyHint = document.getElementById('log-table').textContent.includes('没有匹配的日志');
  search.value = ''; search.dispatchEvent(new Event('input'));
  const searchRestored = document.getElementById('log-table').textContent.includes('新会话仅有的一行');
  // Metadata received after logs must not erase the same session's rows.
  logs.metadata({sessionId:'b', logPath:'合成日志', testMode:true});
  const testMode = document.getElementById('log-mode').textContent.includes('测试模式');
  // Export remains an explicit download, with its hint outside the action label.
  // A new session must hide the entire result, not leave a stale download hint.
  const exportGroup = document.getElementById('logs-export');
  const initiallyHidden = exportGroup?.hidden === true;
  document.querySelector('[data-log-command="logs-export"]').click();
  const download = document.getElementById('logs-download');
  const exportShown = await waitFor(() => exportGroup?.hidden === false);
  const downloadReady = download.download === 'fixture-export.log' && new URL(download.href).pathname === '/test/fixture-export.log';
  const hint = document.getElementById(download.getAttribute('aria-describedby'));
  const exportPresentation = download.classList.contains('button') && download.classList.contains('primary')
    && hint?.textContent.includes('浏览器设置') && exportGroup && getComputedStyle(exportGroup).display === 'flex';
  logs.metadata({sessionId:'new-session', logPath:'新会话', testMode:false});
  const hiddenAfterSession = exportGroup?.hidden === true;
  const passed = recovered && noOldRows && resetCursor && independentLink && emptyHint && searchRestored && testMode
    && initiallyHidden && exportShown && downloadReady && exportPresentation && hiddenAfterSession;
  result.textContent = JSON.stringify({passed, recovered, noOldRows, resetCursor, independentLink, emptyHint, searchRestored, testMode,
    initiallyHidden, exportShown, downloadReady, exportPresentation, hiddenAfterSession, requests}, null, 2);
};
