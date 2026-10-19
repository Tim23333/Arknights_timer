import {formatValue, formatClock, pathValues, fieldTopic, assessField, metaLabel, policyFields, deployView, pieData, departedView, monitorStatus} from "./model.mjs";
import {policyChanges} from './policyChanges.mjs';
import {createPager} from './pagination.mjs';
import {createLogs} from './logs.mjs';
import {createTableRenderer} from './tableRenderer.mjs';
import {createStaticTableColumnOrder} from './tableColumnOrder.mjs';
import {createLatestUpdates} from './liveUpdates.mjs';
import {createFieldDisplay} from './fieldDisplay.mjs';
import {createSourceMeta} from './sourceMeta.mjs';
import {clockChannelName, createClockPublisher} from './clockRelay.mjs';
import {createDetailSelection} from './detailSelection.mjs';
import {createStageGlobalRenderer} from './stageGlobal.mjs';
import {createEntityDetails} from './entityDetails.mjs';
import {initializeColumnPreferences} from './columnPreferences.mjs';
import {createPresentationWatch, waitForPresentation, getPresentationClient} from './presentation.mjs';

// Read once before constructing tables; never gate capture or ordinary frames on disk I/O.
await initializeColumnPreferences();
const presentationClient=await getPresentationClient();

const byId = id => document.getElementById(id);
const ui = {data: {}, policy: {generation: 0, fields: []}, columns: {}, precision: {}, page: "overview", detail: null, busyPolicy: false, connected: false};
const tables = new Map();
const pagers = new Map();
const policyOrder=createStaticTableColumnOrder(document.querySelector('.policy-table'),[
  {key:'field',label:'字段 / 来源'},{key:'collect',label:'采集'},{key:'display',label:'本地展示'},
  {key:'publish',label:'WS 发布'},{key:'dependencies',label:'依赖与粒度'},
],'field-policy');
const fieldDisplays = {enemy:createFieldDisplay(), character:createFieldDisplay()};
const heldFieldCounts = {enemy:0, character:0};
const displayExpiry = {enemy:null, character:null};
const sourceMetadata = {enemy:createSourceMeta(byId('enemy-meta')), character:createSourceMeta(byId('character-meta'))};
let notificationSession = null, notificationCursor = 0;
let policyRequest = null;
const toasts = [];
let drawerReturn = null;
let drawerCleanup = null;
let entityDetails = null;
const detailSelection = createDetailSelection(
  target => command('detail', target), error => toast(error.message, 'error'));
const stageGlobal = createStageGlobalRenderer(byId('module-global'), {table:updateTable, policy:() => ui.policy});

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = String(text);
  return element;
}
function set(id, text) {
  const element = byId(id);
  if (element && element.textContent !== String(text)) element.textContent = String(text);
}

async function api(path, body) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(path, {method: body === undefined ? "GET" : "POST", cache: "no-store", signal: controller.signal,
      ...(body === undefined ? {} : {headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)})});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || `请求失败 ${response.status}`);
    return result;
  } finally { clearTimeout(timeout); }
}

function toast(message, level = "info", duration = null, title = null) {
  if (!byId("toast-enabled").checked && level !== "error") return;
  const item = node("article", "toast " + level);
  item.setAttribute("role", level === "error" ? "alert" : "status");
  const copy = node("div");
  copy.append(node("strong", "", title || {info: "提示", error: "操作失败", warn: "需要注意", success: "操作完成"}[level] || "提示"), node("p", "", message));
  const close = node("button", "", "×");
  close.setAttribute("aria-label", "关闭提示");
  item.append(copy, close);
  byId("toast-stack").append(item);
  let timer;
  const dismiss = () => { clearTimeout(timer); item.remove(); const index = toasts.indexOf(dismiss); if (index >= 0) toasts.splice(index, 1); };
  close.addEventListener("click", dismiss);
  toasts.push(dismiss);
  if (toasts.length > 5) toasts[0]();
  const input = document.querySelector(`[data-duration="${level === "error" ? "error" : level === "warn" ? "warn" : "info"}"]`);
  timer = setTimeout(dismiss, Math.max(10, Math.min(120000, duration ?? (Number(input.value) || 2500))));
  requestAnimationFrame(() => item.classList.add("show"));
}

function setNav(open) {
  const drawer = byId("nav-drawer");
  drawer.classList.toggle("is-open", open);
  drawer.inert = !open;
  drawer.setAttribute("aria-hidden", String(!open));
  byId("nav-backdrop").hidden = !open;
  byId("open-nav").setAttribute("aria-expanded", String(open));
  byId("open-nav").classList.toggle("is-hidden", open);
  (open ? byId("close-nav") : byId("open-nav")).focus();
}

function showPage(page) {
  ui.page = ['system', 'logs'].includes(page) ? page : "overview";
  for (const element of document.querySelectorAll(".content > .page")) element.classList.toggle("active", element.id === "page-" + ui.page);
  for (const button of document.querySelectorAll(".nav-button")) button.classList.toggle("active", button.dataset.page === page);
  if (byId("nav-drawer").classList.contains("is-open")) setNav(false);
  if (!["system", "overview", "logs"].includes(page)) {
    const slot = byId("overview-" + page);
    slot.open = true;
    slot.scrollIntoView({block: "start"});
  } else window.scrollTo(0, 0);
  render();
}

function openDrawer(title, content, detail = null) {
  drawerCleanup?.();
  drawerCleanup = null;
  drawerReturn = document.activeElement;
  byId("overlay").hidden = false;
  set("drawer-title", title);
  byId("drawer-tabs").replaceChildren();
  byId("drawer-body").replaceChildren(content);
  ui.detail = detail;
  detailSelection.replace(detail);
  byId("overlay").querySelector(".close-button").focus();
}
function closeDrawer() {
  drawerCleanup?.();
  drawerCleanup = null;
  byId("overlay").hidden = true;
  ui.detail = null;
  detailSelection.replace(null);
  if (drawerReturn?.isConnected) drawerReturn.focus();
}

function openEntityDetails(kind, item, historical = false) {
  if (!item) return toast('对象已更新，请重新选择', 'warn');
  const basicMeta = ui.data[kind === 'enemy' ? 'enemies' : 'characters']?.meta || {};
  const target = {kind, id:String(item.id), historical, sessionId:basicMeta.sessionId,
    generation:ui.policy.generation, ...(historical ? {snapshot:structuredClone(item), basicMeta:structuredClone(basicMeta)} : {})};
  // History is a frozen projected snapshot: never request a retired address.
  openDrawer(item.name || (kind === 'enemy' ? '敌人详情' : '干员详情'), node('div'), historical ? null : target);
  ui.detail = target;
  const drawer = byId('overlay').querySelector('.drawer');
  drawer.classList.add('entity-drawer');
  const viewer = createEntityDetails(kind,target.id,byId('drawer-tabs'));
  entityDetails = viewer;
  byId('drawer-body').replaceChildren(viewer.element);
  drawerCleanup = () => {viewer.destroy();entityDetails=null;drawer.classList.remove('entity-drawer');};
  renderEntityDetails();
}

function renderEntityDetails() {
  if (!ui.detail || !entityDetails) return;
  const target = ui.detail;
  const basicTopic = ui.data[target.kind === 'enemy' ? 'enemies' : 'characters'] || {};
  const detailTopic = ui.data[target.kind + '_detail'] || {};
  if (target.sessionId !== basicTopic.meta?.sessionId || target.generation !== ui.policy.generation) {
    closeDrawer();
    toast('战局或字段策略已更新，请重新打开详情', 'info');
    return;
  }
  if (['source_stopped','session_changed','adb_changed'].includes(basicTopic.meta?.reason)) {
    closeDrawer();return;
  }
  const current=basicTopic.items?.find(item=>String(item.id)===target.id);
  if (!target.historical && basicTopic.meta?.collectionState==='current') {
    if (current?.lifecycle==='departed' || (!current && target.lastBasic)) {
      // A confirmed departure is not a transient failed sample. Freeze only
      // the last accepted basic snapshot and release the live target once.
      detailSelection.replace(null);target.historical=true;
      target.snapshot=structuredClone(current || target.lastBasic);
      target.basicMeta=structuredClone(current?basicTopic.meta:target.lastBasicMeta);
    } else if(current) {
      target.lastBasic=current;target.lastBasicMeta=basicTopic.meta;
    }
  }
  const view = entityDetails.update({
    basic:target.historical ? target.snapshot : current,
    detail:target.historical ? null : detailTopic.items?.find(item => String(item.id) === target.id),
    basicMeta:target.historical ? target.basicMeta : basicTopic.meta,
    detailMeta:target.historical ? {} : detailTopic.meta,
    policy:ui.policy,historical:target.historical,connected:ui.connected,
  });
  set('drawer-title',view.title + (target.historical ? ' · 历史快照' : ' · 详情'));
  entityDetails.updateClock(ui.data.clock);
}

function rawBlock(title, data) {
  const block = node("details", "raw-block");
  block.open = true;
  const pre = node('pre', 'raw-data');
  block.append(node('summary', '', title));
  // Overview drawers can contain top-level entity/event lists too. Keep their
  // original complete JSON as the default; optional paging only projects a copy.
  const lists = Object.entries(data || {}).filter(([, value]) => Array.isArray(value));
  const controls = new Map();
  const draw = () => {
    const projection = {...data};
    for (const [key, values] of lists) projection[key] = controls.get(key).slice(values).items;
    pre.textContent = JSON.stringify(projection, null, 2);
  };
  for (const [key] of lists) { const pager = createPager(title + ' · ' + key, draw, 0); controls.set(key, pager); block.append(pager.element); }
  block.append(pre); draw();
  return block;
}

/** Use text nodes for Markdown, so local docs cannot execute HTML or scripts. */
function markdown(source) {
  const body = node("div", "doc-content");
  let code = null;
  for (const line of String(source).split(/\r?\n/)) {
    if (line.startsWith("```")) { if (code) { body.append(code); code = null; } else code = node("pre"); continue; }
    if (code) { code.textContent += line + "\n"; continue; }
    const heading = /^(#{1,6})\s+(.+)$/.exec(line);
    if (heading) body.append(node("h" + heading[1].length, "", heading[2]));
    else if (/^\s*[-*]\s/.test(line)) body.append(node("p", "", "• " + line.replace(/^\s*[-*]\s/, "")));
    else if (line.trim()) body.append(node("p", "", line));
  }
  if (code) body.append(code);
  return body;
}

function updateTable(id, columns, items, values) {
  const table = byId(id);
  const page = displayPage(id, table.parentElement, items);
  let cached = tables.get(id);
  if (!cached) { cached = createTableRenderer(table); tables.set(id, cached); }
  cached.update(columns, page.items, values, page.offset);
}

function displayPage(id, container, items, changed = render) {
  let pager = pagers.get(id);
  if (!pager || !pager.element.isConnected) {
    pager = createPager(id, changed); pagers.set(id, pager);
    container.before(pager.element);
  }
  return pager.slice(items);
}

function entityColumns(kind, items) {
  const supplied = ui.data.columns?.[kind] || [];
  const all = supplied.length ? supplied : Object.keys(items[0] || {}).filter(key => !["columns", "fieldStates"].includes(key)).map(key => ({key, label: key, default: true, path: key}));
  const chosen = all.filter(column => {
    const field = ui.policy.fields.find(field => field.id === `${kind}.${column.key}`);
    if (field && !field.display) return false;
    return ui.columns[kind]?.[column.key] ?? column.default !== false;
  });
  return [...chosen.filter(column => column.key !== "detail"), {key: "detail", label: "详情"}];
}

function renderEntities(kind) {
  const domain = kind === "enemy" ? "enemies" : "characters";
  const payload = ui.data[domain] || {};
  const columns = entityColumns(kind, payload.items || []);
  const valueOf = (item, column, index) => {
    if (column.key === "row") return index + 1;
    if (item.columns && column.key in item.columns) return item.columns[column.key];
    const path = (column.path || column.key).replace(/^(enemies|characters)\.items\[\]\./, "");
    return formatValue(pathValues(item, path)[0], ui.precision[kind] ?? 2);
  };
  const view = fieldDisplays[kind].project(payload,
    {kind, policy:ui.policy, precision:ui.precision[kind] ?? 2}, columns, valueOf);
  if (kind === 'enemy') renderDeparted({...payload, items:view.rows});
  let items = view.rows;
  if (kind === "enemy" && byId("hide-departed").checked) items = items.filter(item => !["departed", "dead", "removed"].includes(item.lifecycle));
  if (kind === "character" && !byId("show-tokens").checked) items = items.filter(item => ["operator", "干员"].includes(item.kind));
  updateTable(kind + "-table", columns, items, view.cell);
  heldFieldCounts[kind]=view.heldCount;
  sourceMetadata[kind].update(payload.meta);
  clearTimeout(displayExpiry[kind]);
  if (view.expiresAt !== null) {
    // Expire even when the failed producer stops sending packets. This is a
    // one-shot deadline for existing values, not a new polling/update rate.
    displayExpiry[kind] = setTimeout(() => renderEntities(kind), Math.max(1, view.expiresAt - performance.now() + 1));
  }
  set(kind + "-status", monitorStatus(payload,kind==='enemy'?ui.data.service?.enemy:undefined,view.heldCount));
  if (byId("raw-" + domain).parentElement.open) set("raw-" + domain, JSON.stringify(payload, null, 2));
}

function renderDeploy() {
  const deploy = ui.data.deploy || {};
  const stage = ui.data.stage || {};
  const view = deployView(stage, deploy);
  updateTable("deploy-table", view.columns, view.rows, (item, column) => item.values[column.key]);
  const facts = byId("stage-facts");
  const value = JSON.stringify(view.facts);
  if (facts.dataset.value !== value) {
    facts.dataset.value = value;
    facts.replaceChildren();
    for (const fact of view.facts) {
      const card = node("div");
      card.append(node("small", "", fact.label), node("strong", "", fact.value));
      facts.append(card);
    }
  }
  // Debug JSON retains the source fields and values without localization;
  // localization only affects the cards and table, not backend/WS/export data.
  if (byId("raw-deploy").parentElement.open) set("raw-deploy", JSON.stringify({stage, deploy}, null, 2));
}

function renderDeparted(payload) {
  const items = payload.items || [];
  set('departed-count', `${items.filter(item => item.lifecycle === 'departed').length} 条`);
  if (!byId('departed-enemies').open) return;
  const view = departedView(items, byId('departed-filter').value);
  set('departed-status', ui.connected ? '本局历史记录 · 不额外读取离场对象' : '后端连接中断 · 最后已知历史记录');
  updateTable('enemy-departed-table', [
    {key: 'name', label: '名称', width: 120}, {key: 'code', label: '编号', width: 70},
    {key: 'enemyId', label: '敌人 ID', width: 200}, {key: 'reason', label: '离场原因', width: 180},
    {key: 'finishReason', label: '原始原因编号', width: 110},
    {key: 'endFrame', label: '观测离场帧', width: 110}, {key: 'hp', label: '最后观测血量', width: 170},
    {key: 'hpFrame', label: '血量来源帧', width: 110}, {key: 'position', label: '最后观测位置', width: 140},
    {key: 'positionFrame', label: '位置来源帧', width: 110}, {key: 'history', label: '历史快照', width: 100},
  ].filter(column => {
    const fieldId = {name: 'name', code: 'code', enemyId: 'eid', finishReason: 'finish_reason', endFrame: 'end_frame',
      hp: 'hp', hpFrame: 'hp', position: 'pos', positionFrame: 'pos'}[column.key];
    if (column.key === 'reason') return ['enemy.end_reason', 'enemy.finish_reason'].some(
      id => ui.policy.fields.find(field => field.id === id)?.display !== false);
    return !fieldId || ui.policy.fields.find(field => field.id === `enemy.${fieldId}`)?.display !== false;
  }), view.rows, (row, column) => row.values[column.key]);
}

function renderCaptureControls() {
  for (const input of document.querySelectorAll('[data-capture-field]')) {
    const field = ui.policy.fields.find(field => field.id === input.dataset.captureField);
    input.checked = !!field?.collect;
    input.disabled = ui.busyPolicy || !field;
  }
}

function openCharacterOverview() {
  const panel = node('div');
  panel.id = 'character-overview-charts';
  panel.append(node('p', 'overview-note', '本局累计，含已撤退干员的最后已知累计值；同一干员取最大累计值，召唤物/装置不单独计入。'));
  const status = node('p', 'overview-note'); status.id = 'character-overview-status'; panel.append(status);
  const charts = node('div', 'character-charts');
  for (const [metric, title] of [['damage', '干员总输出占比'], ['healing', '干员治疗量占比']]) {
    const figure = node('section', 'character-chart');
    figure.append(node('h3', '', title));
    const pie = node('div', 'character-pie'); pie.id = `overview-${metric}-pie`; pie.setAttribute('role', 'img');
    figure.append(pie);
    const note = node('p', 'overview-note'); note.id = `overview-${metric}-note`; figure.append(note);
    const shell = node('div', 'table-scroll');
    const table = node('table', 'data-table'); table.id = `overview-${metric}-table`;
    table.append(node('thead'), node('tbody')); shell.append(table); figure.append(shell);
    tables.delete(table.id); // Each newly opened drawer owns a fresh table DOM.
    charts.append(figure);
  }
  panel.append(charts);
  openDrawer('全局总伤饼图', panel);
  renderCharacterOverview();
}

function renderCharacterOverview() {
  if (byId('overlay').hidden || !byId('character-overview-charts')) return;
  const overview = ui.data.characterOverview || {};
  const freshness = ui.connected ? metaLabel(overview.meta) : '后端连接中断 · 以下为最后已知累计';
  set('character-overview-status', `${freshness} · 全局总伤 ${formatValue(overview.globalTotal)}`);
  for (const metric of ['damage', 'healing']) {
    const enabled = overview.available && overview[`${metric}Available`];
    const chart = pieData(enabled ? overview.rows || [] : [], metric);
    const pie = byId(`overview-${metric}-pie`);
    const label = `${metric === 'damage' ? '总输出' : '总治疗'} ${formatValue(chart.total)}，${chart.rows.length} 名干员`;
    pie.style.background = chart.total > 0 ? `conic-gradient(${chart.rows.filter(row => row.value > 0).map(row => `${row.color} ${row.start}% ${row.end}%`).join(',')})` : '#e4ebed';
    pie.setAttribute('aria-label', enabled ? label : '未采集、未展示或当前数据不可用');
    pie.textContent = enabled ? (chart.rows.length ? `合计\n${formatValue(chart.total)}` : '暂无数据') : '暂无可用数据';
    set(`overview-${metric}-note`, enabled ? `干员 ${chart.rows.length}${chart.missing ? ` · ${chart.missing} 名干员该值不可用，未计入` : ''}` : '请检查对应统计的采集/展示开关，以及干员监控状态。');
    updateTable(`overview-${metric}-table`, [{key: 'name', label: '干员'}, {key: 'value', label: '累计值'}, {key: 'ratio', label: '占比'}], chart.rows,
      (item, column) => column.key === 'ratio' ? `${item.ratio.toFixed(1)}%` : formatValue(item[column.key]));
    for (const row of byId(`overview-${metric}-table`).tBodies[0].rows) {
      const item = chart.rows.find(item => tables.get(`overview-${metric}-table`)?.rowFor(item.id) === row);
      if (item) row.cells[0].style.borderLeft = `5px solid ${item.color}`;
    }
  }
}

function renderRng() {
  const rng = ui.data.rng || {};
  const roles = rng.by_role || {};
  const container = byId("rng-panels");
  for (const role of ["imp", "trivial"]) {
    let panel = byId("rng-" + role);
    if (!panel) {
      panel = node("section", "rng-panel"); panel.id = "rng-" + role;
      const heading = node("div", "rng-panel-head"); heading.append(node("h2", "", role === "imp" ? "战斗随机" : "表现随机"));
      const button = node("button", "button quiet", "导出 JSON"); button.dataset.action = "rng-export-" + role; heading.append(button);
      const meta = node("div", "rng-meta"); meta.id = "rng-" + role + "-meta";
      const layout = node("div", "rng-tables");
      for (const [key, label] of [["predictions", "未来预测"], ["history", "最近消耗"]]) {
        const block = node("div"); const table = node("table"); table.id = `rng-${role}-${key}`; table.append(node("thead"), node("tbody")); block.append(node("h3", "", label), table); layout.append(block);
      }
      panel.append(heading, meta, layout); container.append(panel);
    }
    // Keep every engine field and all predicted/history values; never synthesize.
    const engine = roles[role] || {};
    set("rng-" + role + "-meta", `状态 ${engine.status || "等待扫描"} · 游标 ${formatValue(engine.cursor)} / ${formatValue(engine.cursor2)} · 已消耗 ${formatValue(engine.total)} · 速率 ${formatValue(engine.rate)}`);
    for (const key of ["predictions", "history"]) {
      const entries = engine[key] || [];
      const keys = [...new Set(entries.flatMap(entry => Object.keys(entry)))];
      const tableId = `rng-${role}-${key}`;
      // Empty samples remove rows, not the previously known column schema.
      const columns = keys.length ? keys.map(key => ({key, label: ({n: "第几发", seq: "序号", frac: "值", raw: "原始整数"})[key] || key})) : tables.get(tableId)?.defaultColumns || [];
      updateTable(tableId, columns, entries, (entry, column) => formatValue(entry[column.key], 6));
    }
  }
  if (byId("raw-rng").parentElement.open) set("raw-rng", JSON.stringify(rng, null, 2));
}

function renderClock() {
  const clock = ui.data.clock || {};
  stageGlobal.updateSources(ui.data);
  set("clock-time", formatClock(clock.gameTime)); set("overview-time", formatClock(clock.gameTime));
  set("clock-frame", "逻辑帧 " + formatValue(clock.fixedFrame)); set("overview-frame", "逻辑帧 " + formatValue(clock.fixedFrame));
  for (const [key,id,label,formatter] of [['gameTime','global-time','',formatClock],['fixedFrame','global-frame','逻辑帧 ',formatValue]]) {
    const field=ui.policy.fields.find(field => field.id === 'stage_global.'+key);
    set(id,label+(field?.display === false ? '未展示' : field?.collect === false ? '未采集' : formatter(clock[key])));
  }
  set("clock-source", [clock.connected ? "已连接" : "未连接", clock.clockSource || "—", clock.message || ""].join(" · "));
  byId("clock-time").classList.toggle("source-unavailable", !ui.connected || !clock.connected);
  entityDetails?.updateClock(clock);
  if (ui.page === 'system') set('timer-status', clock.message || (clock.connected ? '已连接' : '未连接'));
}

function render(changed = null) {
  const has = key => !changed || changed.has(key);
  if (has('policyGeneration')) renderCaptureControls();
  if (has('characterOverview')) renderCharacterOverview();
  const data = ui.data;
  if (data.options?.toast && document.activeElement !== byId('toast-enabled') && !byId('toast-enabled').disabled) byId('toast-enabled').checked = data.options.toast.enabled !== false;
  logs.metadata(data.service?.logs);
  const clock = data.clock || {};
  const ws = data.service?.ws || {};
  if (has('clock') || has('policyGeneration')) renderClock();
  set("version", "ARKNIGHTS TIMELINE / " + (data.version || "—"));
  set("connection", ui.connected ? (data.service?.adb?.serial || "本机后端已连接") : "后端连接断开");
  set("nav-status", ui.connected ? "后端已连接" : "连接断开");
  set("source-battle", data.enemies?.meta?.frameConsistent === false ? "帧不一致" : data.enemies?.meta?.collectionState === "current" ? "本次采样有效" : "等待有效采样");
  set("source-quality", metaLabel(data.enemies?.meta));
  set("stage-name", data.stage?.stage?.name || data.stage?.name || data.stage?.stageId || "—");
  set("source-deploy", (data.deploy?.events?.length ?? 0) + " 条事件");
  set("source-rng", data.rng?.by_role ? "双路状态已收到" : "等待扫描");
  set("source-ws", ws.state === "ready" || ws.running ? "服务运行中" : ws.enabled ? "正在启动 / 不可用" : "服务关闭");
  set("ws-url", ws.gameUrl || "—");
  set("count-enemies", (data.enemies?.items?.length ?? 0) + " 个实体 / 名册");
  set("count-characters", (data.characters?.items?.length ?? 0) + " 个单位");
  set("count-deploy", (data.deploy?.events?.length ?? 0) + " 条操作"); set("count-rng", data.rng?.by_role ? "双引擎" : "待扫描");
  set('count-global', data.stage_global ? '已收到全局主题' : '等待采样');
  if (ui.page === "overview") {
    if ((has('stage_global') || has('stage_map') || has('stage_units') || has('policyGeneration')) && byId('overview-global').open) stageGlobal.draw(data, has('policyGeneration'));
    if ((has('enemies') || has('columns') || has('policyGeneration')) && byId("overview-enemies").open) renderEntities("enemy");
    if ((has('characters') || has('columns') || has('policyGeneration')) && byId("overview-characters").open) renderEntities("character");
    if ((has('deploy') || has('stage')) && byId("overview-deploy").open) renderDeploy();
    if (has('rng') && byId("overview-rng").open) renderRng();
  }
  if (ui.page === "system") {
    if (document.activeElement !== byId("ws-toggle")) byId("ws-toggle").checked = !!ws.enabled;
    set("adb-status", data.service?.adb?.serial || data.service?.adb?.path || "未配置");
    set("timer-status", clock.message || (clock.connected ? "已连接" : "未连接"));
    set("worker-status", data.service?.enemy || data.service?.worker?.message || metaLabel(data.enemies?.meta));
    if (byId("raw-service").parentElement.open) set("raw-service", JSON.stringify(data.service || {}, null, 2));
    for (const input of document.querySelectorAll("[data-setting]")) if (document.activeElement !== input && !input.disabled) input.checked = !!data.options?.[input.dataset.setting]?.[input.dataset.key];
    if (data.options?.toast && document.activeElement !== byId("toast-enabled")) byId("toast-enabled").checked = data.options.toast.enabled !== false;
    for (const input of document.querySelectorAll("[data-duration]")) if (document.activeElement !== input && data.options?.toast?.duration_ms?.[input.dataset.duration] !== undefined) input.value = data.options.toast.duration_ms[input.dataset.duration];
  }
  // Service messages may change without a new accepted enemy frame (scanning,
  // failed reads, stop). Update this text independently, never redraw tables
  // or create a new timer/transport just to display the existing Qt metrics.
  if (has('service')) set('enemy-status',monitorStatus(data.enemies,data.service?.enemy,heldFieldCounts.enemy));
  if (ui.detail && (has('enemies') || has('characters') || has('enemy_detail') || has('character_detail') || has('policyGeneration'))) renderEntityDetails();
}

function renderPolicy() {
  const body = byId("field-body");
  const query = byId("field-search").value.toLowerCase();
  body.replaceChildren();
  const filtered = ui.policy.fields.filter(field => (field.label + field.id + field.domain + field.group).toLowerCase().includes(query));
  const page = displayPage('fields', body.closest('.policy-scroll'), filtered, renderPolicy);
  for (const field of page.items) {
    const row = node("tr"); const name = node("td", "field-name");
    name.append(node("strong", "", field.label || field.id), node("small", "", field.id + " · " + (field.paths || []).join(", ")));
    row.append(name);
    for (const layer of ["collect", "display", "publish"]) {
      const cell = node("td"); const toggle = node("button", "toggle" + (field[layer] ? " on" : ""));
      toggle.setAttribute("role", "switch"); toggle.setAttribute("aria-checked", String(!!field[layer]));
      toggle.setAttribute("aria-label", (field.label || field.id) + " · " + ({collect: "采集", display: "本地展示", publish: "WS 发布"})[layer]);
      toggle.disabled = ui.busyPolicy || (layer === "collect" && !!(field.captureRequired || field.capture_required || field.required));
      toggle.dataset.field = field.id; toggle.dataset.layer = layer; cell.append(toggle); row.append(cell);
    }
    const domainLabel = field.domain === 'stage_global' ? '关卡全局状态' : field.domain;
    const groupLabel = field.domain === 'stage_global' ? ({clock_reference:'主时钟引用',identity:'关卡身份',map_identity:'地图标识',runtime:'战斗运行状态',mode:'游戏模式',waves:'波次与门控',wave_enemies:'下一波敌人配置',map:'地图配置',map_runtime:'当前地块',layout:'当前布局',enemy_layout:'当前敌方布局',ally_layout:'当前我方布局'})[field.group] || field.group : field.group;
    row.append(node("td", "granularity", domainLabel + " / " + groupLabel + ((field.dependencies || field.deps || []).length ? " · 依赖 " + (field.dependencies || field.deps).join(", ") : "") + (!field.collect ? " · 未采集" : "")));
    body.append(row);
  }
  set("field-count", `${filtered.length} / ${ui.policy.fields.length} 个字段`);
  policyOrder.apply();
}

function confirmShutdown() {
  const content = node('div');
  content.append(node('p', '', '确认关闭 Timeline 后端？采集、WebSocket 和网页服务将停止，其他已连接窗口也会断开。不会关闭电脑或模拟器。'));
  const actions = node('div', 'adb-actions');
  const cancel = node('button', 'button', '取消');
  const confirm = node('button', 'button', '确认关机');
  actions.append(cancel, confirm); content.append(actions);
  cancel.onclick = closeDrawer;
  confirm.onclick = async () => {
    confirm.disabled = true;
    try {
      const result = await command('shutdown', {confirmed: true});
      content.replaceChildren(node('p', '', result.message + '。再次使用时请重新启动程序。'));
      toast(result.message, 'info');
    } catch (error) { confirm.disabled = false; toast(error.message, 'error'); }
  };
  openDrawer('关机确认', content);
}

function confirmDependencyChanges(fields) {
  return new Promise(resolve => {
    const content = node('div');
    content.append(node('p', '', '以下字段依赖此采集来源，继续将一并关闭它们的采集（不会改变展示及 WS 发布开关）：'));
    const list = node('ul');
    for (const field of fields) list.append(node('li', '', `${field.label || field.id}（${field.id}）`));
    const actions = node('div', 'adb-actions');
    const cancel = node('button', 'button', '取消');
    const apply = node('button', 'button primary', '确认一并关闭');
    actions.append(cancel, apply); content.append(list, actions);
    openDrawer('确认关闭依赖字段', content);
    drawerCleanup = () => resolve(false);
    cancel.onclick = closeDrawer;
    apply.onclick = () => { drawerCleanup = null; closeDrawer(); resolve(true); };
  });
}

async function updatePolicy(id, layer, enabled = null) {
  const field = ui.policy.fields.find(field => field.id === id);
  if (!field || ui.busyPolicy) return;
  ui.busyPolicy = true; renderPolicy(); renderCaptureControls();
  try {
    const registry = ui.policy.fields;
    const generation = ui.policy.generation;
    const changes = policyChanges(registry, id, layer, enabled === null ? !field[layer] : enabled);
    const dependents = registry.filter(item => item.id !== id && changes[item.id]);
    if (dependents.length && !await confirmDependencyChanges(dependents)) return;
    // A concurrent policy change is rejected by the backend generation check.
    const result = await api("/api/policy", {generation, fields: changes});
    ui.policy = policyFields({...result, registry: result.registry || registry});
    const enabledCollection = layer === 'collect' && changes[id].collect;
    toast((field.label || id) + (enabledCollection
      ? " · 已开启采集；若字段尚未定位，请点击顶部全量刷新（或对应模块重新扫描）"
      : " · 策略已保存"), "success");
  } catch (error) { toast(error.message, "error"); ui.policy = policyFields(await api("/api/policy").catch(() => ui.policy)); }
  finally { ui.busyPolicy = false; renderPolicy(); render(); }
}

async function command(action, params = {}) {
  const result = await api("/api/command", {action, params});
  if (result?.error || result?.ok === false) throw new Error(result.error || result.message || "操作未完成");
  return result;
}

function download(name, payload) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], {type: "application/json"}));
  const link = node("a"); link.href = url; link.download = name + ".json"; document.body.append(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Keep ADB form state independent of the 100 ms telemetry refresh.
 * Discovery uses pollable backend jobs; only explicit apply switches readers.
 * The local picker belongs to this computer, not the browser upload sandbox.
 */
function openAdbDrawer() {
  const form = node("form", "adb-form");
  const path = node("input"); path.type = "text"; path.id = "adb-path"; path.value = ui.data.service?.adb?.path || "";
  const serial = node("input"); serial.type = "text"; serial.id = "adb-serial"; serial.value = ui.data.service?.adb?.serial || ""; serial.maxLength = 256;
  const paths = node("select"); paths.id = "adb-paths"; paths.setAttribute("aria-label", "探测到的 ADB 程序"); paths.hidden = true;
  const devices = node("select"); devices.id = "adb-devices"; devices.setAttribute("aria-label", "设备列表"); devices.hidden = true;
  const pathLabel = node("label", "", "ADB 可执行文件"); pathLabel.htmlFor = path.id;
  const serialLabel = node("label", "", "设备地址 / 序列号"); serialLabel.htmlFor = serial.id;
  serial.placeholder = "例如 127.0.0.1:16384；只有一个在线设备时可留空";
  const actions = node("div", "adb-actions");
  const browse = node("button", "button", "浏览 adb.exe…");
  const detect = node("button", "button", "自动探测运行中模拟器");
  const refresh = node("button", "button", "刷新设备地址");
  const current = node("button", "button", "读取当前配置");
  for (const button of [browse, detect, refresh, current]) button.type = "button";
  actions.append(browse, detect, refresh, current);
  const status = node("p", "adb-status", "请选择模拟器自带的 ADB 和与 MAA 相同的连接地址。探测与浏览只更新本表单，不会切换设备。");
  status.setAttribute("role", "status"); status.setAttribute("aria-live", "polite");
  const footer = node("div", "adb-actions");
  const apply = node("button", "button primary", "使用此 ADB"); apply.type = "submit";
  const cancel = node("button", "button", "取消操作"); cancel.type = "button"; cancel.disabled = true;
  footer.append(apply, cancel);
  form.append(pathLabel, path, paths, actions, serialLabel, serial, devices, status, footer,
    node("p", "", "使用前会验证 ADB 能否运行及目标设备是否在线；切换时自动停止旧监控，完成后需要重新扫描。浏览会打开本机文件选择窗口。"));
  const controls = [path, serial, paths, devices, browse, detect, refresh, current, apply];
  let alive = true; let busy = false; let jobId = null; let cancelRequested = false;
  const setBusy = value => { busy = value; for (const control of controls) control.disabled = value; cancel.disabled = !value; form.setAttribute("aria-busy", String(value)); };
  const cancelJob = async () => {
    cancelRequested = true;
    if (!jobId) return;
    const job = await command("adb-cancel", {id: jobId});
    if (alive) status.textContent = job.message;
  };
  paths.onchange = () => { path.value = paths.value; devices.hidden = true; status.textContent = "已选择另一个 ADB，请刷新设备地址。"; };
  devices.onchange = () => { if (devices.value) serial.value = devices.value; };
  path.oninput = () => { devices.hidden = true; };
  const showResult = result => {
    if (!result) return;
    if (result.path !== undefined) path.value = result.path;
    if (result.serial !== undefined) serial.value = result.serial;
    if (result.candidates?.length) {
      paths.replaceChildren();
      for (const item of result.candidates) {
        const option = node("option", "", `${item.process_name} → ${item.adb_path}`); option.value = item.adb_path; paths.append(option);
      }
      paths.value = result.path; paths.hidden = false;
    }
    if (result.devices) {
      const placeholder = node("option", "", "请选择设备（也可手动填写地址）"); placeholder.value = "";
      devices.replaceChildren(placeholder);
      for (const item of result.devices) {
        const state = {device: "在线", offline: "离线", unauthorized: "未授权"}[item.state] || item.state;
        const option = node("option", "", `${item.serial} · ${state}${item.description ? " · " + item.description : ""}`);
        option.value = item.serial; option.disabled = item.state !== "device"; devices.append(option);
      }
      devices.value = result.devices.some(item => item.serial === serial.value && item.state === "device") ? serial.value : "";
      devices.hidden = false;
    }
  };
  const run = async name => {
    if (busy) return;
    cancelRequested = false; setBusy(true); status.textContent = name === "adb-browse" ? "请在本机文件窗口中选择 adb.exe…" : "正在验证与探测，耗时取决于模拟器及 ADB 响应…";
    try {
      let job = await command(name, {path: path.value.trim(), serial: serial.value.trim()});
      jobId = job.id;
      if (!alive || cancelRequested) await cancelJob();
      const deadline = Date.now() + 180000;
      while (alive && ["running", "stopping"].includes(job.status)) {
        if (Date.now() >= deadline) { await cancelJob(); throw new Error("ADB 操作等待超时，已请求取消，请稍后重试"); }
        status.textContent = job.message;
        await new Promise(resolve => setTimeout(resolve, 250));
        if (alive) job = await command("adb-job", {id: jobId});
      }
      if (!alive) return;
      status.textContent = job.message;
      if (job.status === "error") throw new Error(job.message);
      if (job.status === "done") {
        showResult(job.result);
        if (name === "adb") {
          toast(job.message, job.result?.persisted === false ? "warn" : "success");
          jobId = null; closeDrawer();
        } else if (name !== "adb-browse") toast(job.message, job.result?.devices?.some(item => item.state === "device") ? "success" : "warn");
      }
    } catch (error) {
      if (jobId) await command("adb-cancel", {id: jobId}).catch(() => {});
      if (alive) { status.textContent = error.message; toast(error.message, "error"); }
    } finally { jobId = null; if (alive) setBusy(false); }
  };
  browse.onclick = () => run("adb-browse"); detect.onclick = () => run("adb-detect"); refresh.onclick = () => run("adb-devices");
  cancel.onclick = () => cancelJob().catch(error => { if (alive) toast(error.message, "error"); });
  current.onclick = async () => { setBusy(true); try { showResult(await command("adb")); status.textContent = "已读取主程序当前配置；点击刷新设备地址以验证在线状态。"; } catch (error) { toast(error.message, "error"); } finally { if (alive) setBusy(false); } };
  form.onsubmit = event => { event.preventDefault(); run("adb"); };
  openDrawer("选择 ADB", form);
  drawerCleanup = () => { alive = false; if (busy) cancelJob().catch(() => {}); };
}

async function action(name) {
  try {
    if (name === 'frontend-desktop') {
      await command('frontend', {target:'desktop'});
      location.replace('/standby.html');
      return;
    }
    if (name === 'logs' || name === 'diagnostics') return showPage('logs');
    if (name === "close-overlay") return closeDrawer();
    if (name === 'shutdown') return confirmShutdown();
    if (name === "ws-check") return runWsCheck();
    if (["guide", "api"].includes(name)) { const data = await api("/api/docs/" + name); return openDrawer(name === "guide" ? "使用教程" : "接口说明", markdown(data.markdown)); }
    if (name === "adb") return openAdbDrawer();
    if (name.endsWith("-columns")) {
      const kind = name.startsWith("enemy") ? "enemy" : "character"; const list = node("div", "column-list");
      ui.columns[kind] ||= {};
      for (const column of ui.data.columns?.[kind] || []) { const label = node("label"); const checkbox = node("input"); checkbox.type = "checkbox"; checkbox.checked = ui.columns[kind][column.key] ?? column.default !== false; checkbox.onchange = () => { ui.columns[kind][column.key] = checkbox.checked; renderEntities(kind); }; label.append(checkbox, node("span", "", column.label)); list.append(label); }
      const labels = [...list.children];
      const draw = () => { list.replaceChildren(...pager.slice(labels).items); };
      const pager = createPager('显示列', draw, 0), content = node('div');
      content.append(pager.element, list); draw();
      return openDrawer("显示列", content);
    }
    if (name.endsWith("-precision")) {
      const kind = name.startsWith("enemy") ? "enemy" : "character"; const label = node("label", "number-setting", "小数位 "); const input = node("input"); input.type = "number"; input.min = "0"; input.max = "6"; input.value = ui.precision[kind] ?? 2;
      input.onchange = async () => { ui.precision[kind] = Math.max(0, Math.min(6, Number(input.value) || 0)); try { await command("precision", {kind, places: ui.precision[kind]}); } catch (error) { toast(error.message, "error"); } renderEntities(kind); }; label.append(input); return openDrawer("小数位设置", label);
    }
    if (name.endsWith("-fit")) {
      const tableId = name.startsWith("enemy") ? "enemy-table" : "character-table";
      const fitted = tables.get(tableId)?.layout.fit();
      return toast(fitted ? "已按当前页自适应并固定列宽；超长值悬停查看全文" : "表格尚未就绪", fitted ? "success" : "warn");
    }
    if (name === "character-overview") return openCharacterOverview();
    if (name === "diagnostics") return openDrawer("运行诊断", rawBlock("完整运行状态", ui.data.service || {}));
    if (name.startsWith("rng-export-")) return download(name, ui.data.rng?.by_role?.[name.slice(11)] || {});
    const result = await command(name);
    if (result.url) window.open(result.url, "_blank", "noopener");
    if (result.payload) download("timeline-" + name, result.payload);
    toast(result.message || "命令已由主程序执行", "success");
  } catch (error) { toast(error.message, "error"); }
}

async function runWsCheck() {
  const fields = ui.policy.fields.filter(field => field.publish);
  const url = ui.data.service?.ws?.gameUrl;
  if (!fields.length) return toast("没有同意 WS 发布的字段", "warn");
  if (!url) return toast("后端未提供游戏 WebSocket 地址", "error");
  const button = byId("ws-check"); button.disabled = true;
  set("ws-check-results", "直接连接游戏端点，等待实际字段值（最多 8 秒）…");
  const results = new Map(); const received = new Set(); const errors = new Map(); let socket; let done = false; let timer;
  const finish = reason => {
    if (done) return; done = true; clearTimeout(timer); socket?.close(); button.disabled = false;
    const host = byId("ws-check-results"); host.replaceChildren(); const list = node("ul"); let passed = 0;
    const entries = fields.map(field => {
      const topic = fieldTopic(field);
      const result = !field.collect ? {status: "not_collected", text: "未采集"} : results.get(field.id) || {status: "unavailable", text: errors.get(topic) || reason || (received.has(topic) ? "主题已收到，字段未验证" : "未收到主题")};
      if (result.status === 'received') passed++;
      return {label: field.label || field.id, ...result};
    });
    const draw = () => { list.replaceChildren(); for (const entry of pager.slice(entries).items) list.append(node('li', entry.status === 'received' ? 'check-ok' : 'check-warn', `${entry.label} — ${entry.text}`)); };
    const pager = createPager('WS 自检结果', draw);
    host.append(node("strong", "", `检测结束 · ${passed} / ${fields.length} 个字段收到有效值`), pager.element, list); draw();
    toast(reason || "字段自检完成，请查看逐项结果", reason ? "error" : "info");
  };
  try {
    socket = new WebSocket(url); timer = setTimeout(() => finish(""), 8000);
    socket.onopen = () => {
      const topics = Object.fromEntries([...new Set(fields.filter(field => field.collect).map(fieldTopic))].filter(topic => !["ops", "service"].includes(topic)).map(topic => [topic, {rateHz: 1, ...(["enemy_detail", "character_detail"].includes(topic) ? {scope: "all"} : {})}]));
      socket.send(JSON.stringify({type: "subscribe", requestId: "webui-field-self-check", topics}));
    };
    socket.onmessage = event => {
      let message; try { message = JSON.parse(event.data); } catch { return; }
      if (message.type === "subscription.updated") for (const [topic, value] of Object.entries(message.data?.topics || {})) if (value.error) errors.set(topic, value.error);
      if (!message.type?.endsWith(".updated") || message.type === "subscription.updated") return;
      const topic = message.type.slice(0, -8); received.add(topic);
      for (const field of fields.filter(field => fieldTopic(field) === topic)) { const result = assessField(field, message.data); if (results.get(field.id)?.status !== "received") results.set(field.id, result); }
    };
    socket.onerror = () => finish("连接失败或浏览器拒绝本机 WebSocket");
    socket.onclose = () => { if (!done) finish("检测期间连接关闭"); };
  } catch (error) { finish(error.message); }
}

async function updatePoliciesAndNotifications() {
    const journal = ui.data.notifications;
    if (journal) {
      if (notificationSession === journal.sessionId) {
        for (const item of journal.items || []) if (item.seq > notificationCursor) toast(item.text, ['success','error','warn'].includes(item.semantic) ? item.semantic : item.level, item.duration, item.title);
      }
      notificationSession = journal.sessionId; notificationCursor = journal.lastSeq;
    }
    if (!ui.busyPolicy && !policyRequest && (!ui.policy.fields.length || (ui.data.policyGeneration !== undefined && ui.data.policyGeneration !== ui.policy.generation))) {
      policyRequest = api('/api/policy');
      try {
        ui.policy = policyFields(await policyRequest); renderPolicy(); renderCaptureControls();
        // A paused producer may send only one policy-change snapshot. Reapply
        // it after registry loading instead of waiting for another game frame.
        render(new Set(['policyGeneration']));
      }
      finally { policyRequest = null; }
    }
}

async function startLive() {
  let handoff = new URLSearchParams(location.search).get('handoff');
  const presentation = await waitForPresentation(
    () => command('frontend', {target:'page-status',clientId:presentationClient}),
    () => set('transport-status', '等待后端展示状态，正在重试…'));
  handoff ||= presentation.handoff;
  if (!handoff && !presentation.active) {
    location.replace('/standby.html');
    return;
  }
  if (handoff) {
    try { await command('frontend',{target:'claim-web',token:handoff,clientId:presentationClient}); }
    catch { location.replace('/standby.html'); return; }
  }
  // Bootstrap once, then independent SSE connections. No repeated full-state
  // HTTP polling, interpolation or client-generated game frames.
  // A handoff page only proves transport readiness. Never paint cached modules
  // before ownership is confirmed; the clean entry reloads current state.
  if (!handoff) {
    try { ui.data = await api('/api/state'); } catch (error) { toast(error.message, 'error'); }
  } else set('transport-status', '正在切换界面，等待实时通道就绪…');
  render();
  let clockPublisher = null, relayClock = ui.data.clock ?? null;
  try {
    clockPublisher = createClockPublisher({channel:new BroadcastChannel(clockChannelName), id:crypto.randomUUID()});
    clockPublisher.update(relayClock, false);
  } catch { /* Optional browser relay must not prevent the main worktable from connecting. */ }
  const connected = new Set();
  let confirming = false, confirmed = false;
  // Accept/relay outside requestAnimationFrame: a background worktable may not
  // draw, but its visible log window must still receive the actual new sample.
  const relayUpdates = createLatestUpdates(flush => flush(), values => {
    if (!Object.hasOwn(values, 'clock')) return;
    relayClock = values.clock;
    clockPublisher?.update(relayClock, connected.has('clock'));
  });
  const updates = createLatestUpdates(requestAnimationFrame, values => {
    for (const [key, value] of Object.entries(values)) {
      if (value === null) delete ui.data[key]; else ui.data[key] = value;
    }
    const keys = new Set(Object.keys(values));
    if (keys.has('clock')) renderClock();
    keys.delete('clock');
    if (keys.size) {
      render(keys);
      updatePoliciesAndNotifications().catch(error => toast(error.message, 'error'));
    }
  }, {sessionTopics:['clock','stage_global','stage_map','stage_units'],
    initialSession:ui.data.stage_global?.meta?.sessionId || ui.data.clock?.meta?.sessionId || null,
    initialOrder:ui.data.stage_global?.meta || ui.data.clock?.meta || null});
  const sources = ['clock', 'modules'].map(channel => {
    let source, retry, closed=false;
    const status = active => {
      if (active) connected.add(channel); else connected.delete(channel);
      ui.connected = connected.size === 2;
      set('transport-status', ui.connected ? '' : '本地实时通道连接中断或正在重连；当前画面为最后已知值。');
      set('connection', ui.connected ? (ui.data.service?.adb?.serial || '本机后端已连接') : '后端连接断开');
      set('nav-status', ui.connected ? '后端已连接' : '连接断开');
      renderClock();
      renderEntityDetails();
      if (channel === 'clock') clockPublisher?.update(relayClock, active);
      if (handoff && connected.size === 2 && !confirming) {
        confirming = true;
        command('frontend', {target:'confirm-web', token:handoff,clientId:presentationClient}).then(() => {
          confirmed = true;
          location.replace(location.pathname);
        }).catch(error => {
          toast(error.message, 'error');
          location.replace('/standby.html');
        });
      }
    };
    const receive = event => {
      if (handoff) return; // Pre-confirmation replay is not live evidence.
      try {
        const message = JSON.parse(event.data);
        if (channel === 'clock') relayUpdates.receive(channel, message);
        updates.receive(channel, message);
      }
      catch { status(false); }
    };
    function connect() {
      if (closed) return;
      source = new EventSource('/api/stream/' + channel+'?client='+encodeURIComponent(presentationClient));
      source.onopen = () => status(true);
      source.onmessage = receive;
      source.onerror = () => {
        status(false);
        // HTTP 409/503 makes EventSource terminal, unlike a dropped socket.
        // Retry one connection at a time while the owner watcher can retire us.
        if (source.readyState === 2 && !closed) {
          source.close(); clearTimeout(retry); retry=setTimeout(connect,2000);
        }
      };
    }
    connect();
    return {close(){closed=true;clearTimeout(retry);source.close();}};
  });
  const watch = createPresentationWatch(() => command('frontend', {target:'page-status',clientId:presentationClient}), () => location.replace('/standby.html'));
  let handoffPollPending=false;
  const watchTimer = setInterval(() => {
    if (!handoff || confirmed) watch.check();
    else if (!handoffPollPending) {
      handoffPollPending=true;
      command('frontend',{target:'page-status',clientId:presentationClient}).then(state=>{
        if (state.handoff !== handoff && !state.active) location.replace('/standby.html');
      }).catch(()=>{}).finally(()=>{handoffPollPending=false;});
    } // A failed poll does not cancel a healthy pending transport.
  }, 2000);
  window.addEventListener('pagehide', () => { clearInterval(watchTimer); sources.forEach(source => source.close()); clockPublisher?.close(); stageGlobal.destroy(); }, {once: true});
  window.addEventListener('pageshow', event => { if (event.persisted) location.reload(); });
}

for (const input of document.querySelectorAll('[data-capture-field]')) input.onchange = () => updatePolicy(input.dataset.captureField, 'collect', input.checked);

document.addEventListener("click", async event => {
  const page = event.target.closest("[data-page]"); if (page) return showPage(page.dataset.page);
  const field = event.target.closest("[data-field]"); if (field) return updatePolicy(field.dataset.field, field.dataset.layer);
  const detail = event.target.closest("[data-detail-kind]");
  const history = event.target.closest('[data-history-entity]');
  if (history) {
    const item = ui.data.enemies?.items?.find(item => String(item.id) === history.dataset.historyEntity);
    if (!item || item.lifecycle !== 'departed') return toast('本局记录已更新，请重新选择', 'warn');
    // A frozen projected snapshot is inspectable without subscribing to detail
    // or dereferencing a recycled address. Keep its original session/frame tags.
    openEntityDetails('enemy',item,true);
    return;
  }
  if (detail) { const kind = detail.dataset.detailKind; const item = ui.data[kind === "enemy" ? "enemies" : "characters"]?.items?.find(item => String(item.id) === detail.dataset.entity); openEntityDetails(kind,item); return; }
  const button = event.target.closest("[data-action]"); if (button) action(button.dataset.action);
});
byId("open-nav").onclick = () => setNav(true); byId("close-nav").onclick = () => setNav(false); byId("nav-backdrop").onclick = () => setNav(false);
byId("clock-toggle").onclick = () => { const open = byId("clock-drawer").classList.toggle("is-open"); byId("clock-drawer-panel").inert = !open; byId("clock-drawer-panel").setAttribute("aria-hidden", String(!open)); byId("clock-toggle").setAttribute("aria-expanded", String(open)); set("clock-toggle", open ? "收起游戏时钟" : "展开游戏时钟"); };
byId("clock-pin").onclick = () => { const pinned = byId("clock-drawer").classList.toggle("is-pinned"); byId("clock-pin").setAttribute("aria-pressed", String(pinned)); set("clock-pin", pinned ? "已置顶" : "置顶时钟"); };
byId("field-search").oninput = renderPolicy;
byId("hide-departed").onchange = () => renderEntities("enemy"); byId("show-tokens").onchange = () => renderEntities("character");
byId('departed-filter').onchange = () => renderDeparted(ui.data.enemies || {});
byId('departed-enemies').addEventListener('toggle', () => renderDeparted(ui.data.enemies || {}));
byId("ws-toggle").onchange = async event => { event.target.disabled = true; try { const result = await command("ws-toggle", {enabled: event.target.checked}); toast(result.message || "WS 服务配置已更新", "success"); } catch (error) { toast(error.message, "error"); event.target.checked = !event.target.checked; } finally { event.target.disabled = false; } };
byId("rng-count").onchange = async event => { const count = Math.max(1, Math.min(500, Math.round(Number(event.target.value)) || 18)); event.target.value = count; try { await command("rng-count", {count}); } catch (error) { toast(error.message, "error"); } };
byId("toast-enabled").onchange = async event => { try { await command("setting", {section: "toast", key: "enabled", value: event.target.checked}); } catch (error) { event.target.checked = !event.target.checked; toast(error.message, "error"); } };
for (const input of document.querySelectorAll("[data-duration]")) input.onchange = async () => { const value = Math.max(10, Math.min(120000, Math.round(Number(input.value)) || 2500)); input.value = value; try { await command("setting", {section: "toast", key: "duration_ms", value: {[input.dataset.duration]: value}}); } catch (error) { toast(error.message, "error"); } };
for (const input of document.querySelectorAll("[data-setting]")) input.onchange = async () => { input.disabled = true; try { await command("setting", {section: input.dataset.setting, key: input.dataset.key, value: input.checked}); } catch (error) { input.checked = !input.checked; toast(error.message, "error"); } finally { input.disabled = false; } };
for (const slot of document.querySelectorAll(".overview-module-slot")) slot.addEventListener("toggle", () => { slot.querySelector("summary em").textContent = slot.open ? "收起完整数据" : "展开完整数据"; render(); });
for (const block of document.querySelectorAll(".raw-block")) block.addEventListener("toggle", render);
document.addEventListener("keydown", event => {
  if (event.key === "Escape") { if (!byId("overlay").hidden) closeDrawer(); else if (!byId("nav-drawer").inert) setNav(false); }
  if (event.key === "Tab" && !byId("overlay").hidden) { const focusable = [...byId("overlay").querySelectorAll("button,input,select,a,[tabindex]")].filter(element => !element.disabled && element.tabIndex >= 0 && element.getClientRects().length && !element.closest('[hidden],[inert]')); const first = focusable[0], last = focusable.at(-1); if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); } else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); } }
});
const logs = createLogs({command, toast, visible: () => ui.page === 'logs', openPopup: () => {
  const content = byId('page-logs'), home = content.parentNode, next = content.nextSibling;
  openDrawer('实时日志', content);
  byId('logs-popup').disabled = true;
  byId('overlay').querySelector('.drawer').classList.add('log-drawer');
  drawerCleanup = () => { home.insertBefore(content, next); byId('logs-popup').disabled = false; byId('overlay').querySelector('.drawer').classList.remove('log-drawer'); };
}});
if (new URLSearchParams(location.search).get('view') === 'logs') {
  // Keep old bookmarked log links, but do not start the full worktable streams.
  location.replace(new URL('/logs.html', location.href).href);
} else {
  ui.policy = policyFields(await api("/api/policy").catch(error => { toast(error.message, "error"); return ui.policy; })); renderPolicy(); startLive();
}
