import {createPager} from './pagination.mjs';

/** Session-scoped incremental diagnostics with independent popup and complete disk exports. */
export function createLogs({command, toast, visible, openPopup}) {
  const get = id => document.getElementById(id);
  const table = get('log-table');
  let rows = [], cursor = 0, session = null, pausedRows = null, busy = false, loaded = false, stopped = false;
  let timer;
  const pager = createPager('实时日志', () => { get('logs-follow').checked = false; render(); }, 15);
  table.parentElement.before(pager.element);
  function render() {
    if (!visible()) return;
    const query = get('logs-search').value.toLowerCase();
    const source = (pausedRows ?? rows).filter(row => row.text.toLowerCase().includes(query));
    let page = pager.slice(source);
    if (get('logs-follow').checked && !pausedRows) { pager.last(); page = pager.slice(source); }
    const body = table.tBodies[0];
    const emptyText = !loaded ? '正在读取日志…' : query ? '没有匹配的日志' : pausedRows ? '暂停时没有可显示的日志' : '暂无日志（或已清空显示），等待新日志';
    const signature = JSON.stringify([page.items, page.items.length ? null : emptyText]);
    if (body.dataset.signature === signature) return;
    body.dataset.signature = signature;
    const fragment = document.createDocumentFragment();
    for (const row of page.items) {
      const tr = document.createElement('tr'); const seq = document.createElement('td'); const text = document.createElement('td');
      seq.textContent = row.seq; text.textContent = row.text; tr.append(seq, text); fragment.append(tr);
    }
    if (!page.items.length) {
      const tr = document.createElement('tr'), cell = document.createElement('td');
      cell.colSpan = 2; cell.textContent = emptyText; tr.append(cell); fragment.append(tr);
    }
    body.replaceChildren(fragment);
    if (get('logs-follow').checked && !pausedRows) table.parentElement.scrollTop = table.parentElement.scrollHeight;
  }
  get('logs-paused').onchange = event => { pausedRows = event.target.checked ? [...rows] : null; render(); };
  get('logs-follow').onchange = render; get('logs-search').oninput = render;
  get('logs-clear').onclick = () => { rows = []; if (pausedRows) pausedRows = []; render(); toast('仅清空网页显示，落盘日志和导出内容保留'); };
  if (get('logs-popup')) get('logs-popup').onclick = openPopup;
  if (get('logs-window')) {
    // A native link gives embedded browsers a complete navigation target rather
    // than a named window.open popup which can remain at about:blank.
    get('logs-window').href = new URL('/logs.html', location.href).href;
  }
  for (const button of document.querySelectorAll('[data-log-command]')) button.onclick = async () => {
    if (busy) return;
    busy = true;
    const controls = [...document.querySelectorAll('[data-log-command]')]; controls.forEach(control => control.disabled = true);
    try {
      let job = await command(button.dataset.logCommand, {format: button.dataset.format || 'zip'});
      if (!job.id) { toast(job.message, 'success'); return; }
      get('log-task-status').textContent = job.message;
      const deadline = Date.now() + 180000;
      while (job.status === 'running' && Date.now() < deadline) {
        await new Promise(resolve => setTimeout(resolve, 500));
        job = await command('logs-job', {id: job.id});
      }
      if (job.status !== 'done') throw new Error(job.message || '任务仍在后台运行，请稍后查看日志目录');
      if (job.result?.url) {
        // Keep the canonical export in the program-relative log directory.
        // A browser download is an explicit optional second copy.
        const anchor = get('logs-download'); anchor.href = job.result.url; anchor.download = job.result.filename;
        get('logs-export').hidden = false;
      }
      const message = job.message + (job.result?.url ? `：${job.result.filename}（已保存到日志目录；可选择下载副本）` : '');
      get('log-task-status').textContent = message; toast(message, 'success');
    } catch (error) { get('log-task-status').textContent = error.message; toast(error.message, 'error'); }
    finally { busy = false; controls.forEach(control => control.disabled = false); }
  };
  async function poll() {
    try {
      // Populate a newly opened background window once as well. Thereafter
      // hidden windows do not continuously poll or consume extra resources.
      if (visible() && (!loaded || !document.hidden)) {
        const requestedCursor = cursor;
        let snapshot = await command('logs-read', {after: requestedCursor, limit: 10000});
        if (snapshot.sessionId !== session && requestedCursor > 0) {
          // A restarted backend may return an empty page for the old cursor.
          // Do not adopt its last sequence and permanently skip its early rows.
          snapshot = await command('logs-read', {after: 0, limit: 10000});
        }
        if (stopped) return;
        if (session !== snapshot.sessionId) { session = snapshot.sessionId; rows = []; pausedRows = null; get('logs-paused').checked = false; get('logs-export').hidden = true; }
        if (get('log-task-status').textContent.startsWith('日志读取失败：')) get('log-task-status').textContent = '日志连接已恢复；网页缓存最近 10000 行。';
        if (snapshot.gap) get('log-task-status').textContent = '部分早期行已离开网页缓存，可通过完整日志导出查看。';
        rows.push(...snapshot.items); rows = rows.slice(-10000); cursor = snapshot.nextCursor; loaded = true;
        get('log-path').textContent = snapshot.logPath;
        render();
      }
    } catch (error) { get('log-task-status').textContent = '日志读取失败：' + error.message; }
    finally { if (!stopped) timer = setTimeout(poll, 750); }
  }
  window.addEventListener('pagehide', () => { stopped = true; clearTimeout(timer); }, {once:true});
  render();
  poll();
  return {metadata(meta) {
    if (!meta) return;
    if (session && session !== meta.sessionId) { session = null; rows = []; cursor = 0; loaded = false; pausedRows = null; get('logs-paused').checked = false; get('logs-export').hidden = true; }
    get('log-mode').textContent = meta.testMode ? '测试模式 · 共享诊断日志' : '源程序实时诊断日志';
    get('log-path').textContent = meta.logPath; render();
  }};
}
