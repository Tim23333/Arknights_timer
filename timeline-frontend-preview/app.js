// Standalone Web UI prototype. Sample data is simulated; only the optional WS
// self-check connects to the existing local game endpoint for a read-only probe.
const byId = id => document.getElementById(id);
const state = {
  page: "overview",
  tick: 0,
  rngTick: 0,
  frame: 1920,
  timerFrame: 1920,
  seconds: 64,
  running: true,
  ws: true,
  precise: true,
  hideDeparted: true,
  showTokens: true,
  unattributed: false,
  rngRunning: true,
  deployRunning: true,
  rngCount: 18,
  activeDrawer: null,
  toastEnabled: true,
};

const attributeLabels = [
  "最大生命", "攻击", "防御", "法术抗性", "部署费用", "阻挡数", "移动速度",
  "攻击速度", "基础攻击间隔", "每秒生命恢复", "每秒技力恢复", "技能范围前向延伸",
  "最大部署数", "物理穿透比例", "法抗穿透比例", "按最大生命每秒恢复", "嘲讽等级",
  "再部署时间", "最大卡组堆叠数", "重量等级", "基础力度等级", "固定物理穿透",
  "状态抗性", "固定法抗穿透", "损伤条上限", "每秒损伤恢复", "技力恢复倍率",
  "元素损伤减免", "元素抗性", "物理伤害命中倍率", "法术伤害命中倍率",
  "元素爆发恢复速度", "减速倍率", "阻挡半径倍率",
];
const attributeIds = [0,1,2,3,4,5,6,7,8,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37];
const enemyBase = [
  ["row","#",true], ["name","名称",true], ["code","编号",true], ["eid","敌人ID",true],
  ["hp","血量",true], ["pos","坐标",true], ["precise_pos","精确坐标",true],
  ["intent_end","意图终点",true], ["current_route","当前路线",true],
  ["next_waypoint","下一路点",true], ["next_checkpoint","下一检查点",true],
  ["checkpoint_countdown","检查点倒计时",true], ["action_state","行为状态",true],
  ["action_phase","动作阶段",true], ["remaining_time","剩余帧/时间",true],
  ["next_action","下一动作预测",true], ["abnormal_status","异常状态",true],
  ["immune_status","状态免疫",false],
];
const enemyExtra = [
  ["es","元素护盾",false], ["shield","伤害护盾",true],
  ["ep_sanity","神经损伤剩余",false], ["ep_water","侵蚀损伤剩余",false],
  ["ep_fire","灼燃损伤剩余",false], ["ep_dark","凋亡损伤剩余",false],
  ["ep_anger","狂躁损伤剩余",false], ["ep_break","元素爆发恢复",false],
  ["skill","技能 CD",true], ["life_status","生存状态",true],
  ["spawn_wait","距离出场",true], ["detail","详情",true],
];
const characterBase = [
  ["row","#",true], ["name","名称",true], ["kind","类别",true], ["cid","干员 ID",false],
  ["profession","职业",true], ["level","等级",true], ["hp","生命",true],
  ["sp","技力",true], ["pos","位置",true], ["action_state","行为状态",true],
  ["action_phase","动作阶段",true], ["remaining_time","剩余帧/时间",true],
  ["next_action","下一动作",true], ["abnormal_status","异常状态",true],
];
const characterExtra = [
  ["shield","伤害护盾",false], ["es","元素护盾",false],
  ["blocked","阻挡敌人",true], ["buff_count","Buff 数",true],
  ["damage_total","累计伤害",true], ["global_total_damage","全局总伤",true],
  ["damage_physical","物理伤害",false], ["damage_magical","法术伤害",false],
  ["damage_pure","真实伤害",false], ["damage_element","元素伤害",false],
  ["element_output_total","元素损伤累计",false], ["healing_total","累计治疗",false],
  ["skill","主技能",true], ["detail","详情",true],
];
const asColumns = items => items.map(([key,label,visible]) => ({ key, label, visible }));
const enemyColumns = [
  ...asColumns(enemyBase),
  ...attributeLabels.map((label,index) => ({ key: "attr_" + attributeIds[index], label, visible: [1,2,3,6,7].includes(attributeIds[index]) })),
  ...asColumns(enemyExtra),
];
const characterColumns = [
  ...asColumns(characterBase),
  ...attributeLabels.map((label,index) => ({ key: "attr_" + attributeIds[index], label, visible: [1,2,3,7,5].includes(attributeIds[index]) })),
  ...asColumns(characterExtra),
];

const enemies = [
  { id: "e1", name: "梅菲斯特", code: "enemy_1507_mephisto", eid: "enemy_1507", hp: 28000, maxHp: 28000, x: 8.02, y: 2.98, state: "移动", phase: "移动", route: "主 #2（C12 → D1）", waypoint: "C8", checkpoint: "按路径移动 C7", countdown: "该检查点无倒计时", next: "移动 → 路点", life: "场上", spawn: "—", skill: "特殊规则 就绪", abnormal: "正常", atk: 985, def: 300, res: 20, spd: 0.7 },
  { id: "e2", name: "粉碎攻坚手", code: "enemy_1045_h", eid: "enemy_1045", hp: 10000, maxHp: 10000, x: 8.02, y: 1.98, state: "移动", phase: "移动", route: "主 #4（C12 → D1）", waypoint: "B8", checkpoint: "等待波次计时 42.0s", countdown: "12.4s", next: "移动 → 等待", life: "场上", spawn: "—", skill: "—", abnormal: "正常", atk: 970, def: 650, res: 0, spd: 0.6 },
  { id: "e3", name: "粉碎攻坚手", code: "enemy_1045_h", eid: "enemy_1045", hp: 8230, maxHp: 10000, x: 8.03, y: 4.00, state: "攻击", phase: "攻击前摇", route: "主 #4（C12 → D1）", waypoint: "E7", checkpoint: "按路径移动 D7", countdown: "该检查点无倒计时", next: "普攻 · 候选", life: "场上", spawn: "—", skill: "—", abnormal: "正常", atk: 970, def: 650, res: 0, spd: 0.6 },
  { id: "e4", name: "粉碎攻坚手", code: "enemy_1045_h", eid: "enemy_1045", hp: 7610, maxHp: 10000, x: 9.00, y: 2.98, state: "移动", phase: "移动", route: "主 #4（C12 → D1）", waypoint: "D8", checkpoint: "等待当前片段计时 58.0s", countdown: "28.4s", next: "移动 → 等待", life: "场上", spawn: "—", skill: "—", abnormal: "正常", atk: 970, def: 650, res: 0, spd: 0.6 },
  { id: "e5", name: "源石虫", code: "enemy_1007_slime", eid: "enemy_1007", hp: null, maxHp: 550, x: null, y: null, state: "—", phase: "未出场", route: "—", waypoint: "—", checkpoint: "—", countdown: "—", next: "—", life: "未出场", spawn: "W2 · 18.6s", skill: "—", abnormal: "—", atk: 130, def: 0, res: 0, spd: 1.0 },
  { id: "e6", name: "源石虫", code: "enemy_1007_slime", eid: "enemy_1007", hp: 0, maxHp: 550, x: 4.3, y: 1.9, state: "—", phase: "离场", route: "—", waypoint: "—", checkpoint: "—", countdown: "—", next: "—", life: "已离场", spawn: "—", skill: "—", abnormal: "—", atk: 130, def: 0, res: 0, spd: 1.0 },
];
const characters = [
  { id: "c1", name: "芬", kind: "干员", cid: "char_123_fang", profession: "先锋", level: "E1 Lv.55", hp: 1631, maxHp: 1631, sp: 15, maxSp: 15, x: 8, y: 3, state: "待机", phase: "待机 / 技能已就绪", remaining: "等待游戏判定", next: "[未预选] 等待游戏判定", abnormal: "正常", blocked: 1, buffs: 0, damage: 2874, healing: 0, skill: "冲锋号令 · 就绪", atk: 393, def: 270, res: 0, direction: "右" },
  { id: "c2", name: "阿米娅", kind: "干员", cid: "char_002_amiya", profession: "术师", level: "E2 Lv.60", hp: 1340, maxHp: 1480, sp: 28, maxSp: 42, x: 7, y: 4, state: "攻击", phase: "攻击 / 动画进行", remaining: "14 帧 / 0.47s", next: "下一次普攻", abnormal: "正常", blocked: 0, buffs: 1, damage: 6491, healing: 230, skill: "精神爆发 · 28/42", atk: 692, def: 122, res: 20, direction: "上" },
];
const deployEvents = [
  { time: "00:16.2", frame: 486, op: "部署", char: "芬", direction: "右", position: "(8, 3)", extra: "费用 10" },
  { time: "00:29.4", frame: 882, op: "部署", char: "阿米娅", direction: "上", position: "(7, 4)", extra: "费用 18" },
  { time: "00:47.0", frame: 1410, op: "技能", char: "芬", direction: "—", position: "(8, 3)", extra: "手动触发" },
  { time: "00:55.8", frame: 1674, op: "撤退", char: "先前干员", direction: "—", position: "(5, 2)", extra: "主动撤退" },
];
const topics = [
  ["battle","20","1–60"], ["stage","2","0.2–20"], ["enemies","10","1–20"],
  ["enemy_pathing","30","1–60"], ["characters","10","1–20"],
  ["enemy_detail","2","0.2–60"], ["character_detail","2","0.2–60"],
  ["deploy","4","1–20"], ["rng","2","1–10"], ["quality","2","0.5–5"],
  ["ops.heartbeat","0.5","0.2–2"],
];

const fields = [
  { id: "frame", group: "基础与时钟", name: "敌我完整帧锚点", source: "BattleController.fixedFrame", grain: "共享必需 · 同帧", collect: true, display: true, ws: true, required: true, deps: [] },
  { id: "timer", group: "基础与时钟", name: "计时器时间", source: "timer_provider / 独立链", grain: "独立采样", collect: true, display: true, ws: true, deps: [] },
  { id: "enemy.hp", group: "敌人", name: "敌人生命", source: "Enemy 共享基础块 + 最大生命属性", grain: "共享块 · 同帧", collect: true, display: true, ws: true, deps: [] },
  { id: "enemy.attributes", group: "敌人", name: "敌人属性数组", source: "Attributes.cachedData", grain: "整组数组 · 同帧", collect: true, display: false, ws: false, deps: [] },
  { id: "enemy.precise", group: "敌人", name: "精确坐标", source: "Unity Transform 额外链", grain: "专属链 · 同帧", collect: true, display: true, ws: true, deps: [] },
  { id: "enemy.route", group: "敌人", name: "意图路线五字段", source: "DirectionCursor → RouteData", grain: "路线事务 · 同帧", collect: true, display: true, ws: true, deps: [] },
  { id: "enemy.checkpoint", group: "敌人", name: "下一检查点", source: "路线检查点集合", grain: "路线事务 · 同帧", collect: true, display: true, ws: true, deps: ["enemy.route"] },
  { id: "enemy.countdown", group: "敌人", name: "检查点倒计时", source: "检查点类型 + BattleController 战斗时钟", grain: "派生 · 同帧", collect: true, display: true, ws: true, deps: ["enemy.checkpoint"] },
  { id: "enemy.skill", group: "敌人", name: "敌人技能判据", source: "技能 / CD / 触发条件", grain: "技能链 · 同帧", collect: true, display: false, ws: false, deps: [] },
  { id: "enemy.abnormal", group: "敌人", name: "异常与免疫", source: "状态数组 / Buff 计时", grain: "运行状态 · 同帧", collect: true, display: true, ws: true, deps: [] },
  { id: "enemy.next", group: "敌人", name: "下一动作预测", source: "状态 + 技能 + 异常 + 战斗时钟", grain: "高扇入派生 · 同帧", collect: true, display: true, ws: true, deps: ["enemy.skill", "enemy.abnormal"] },
  { id: "enemy.roster", group: "敌人", name: "出怪名册与预告", source: "Scheduler / 关卡配置", grain: "关卡版本 / 事件", collect: true, display: true, ws: true, deps: [] },
  { id: "character.hp", group: "干员", name: "干员生命与技力", source: "Character 共享基础块", grain: "共享块 · 同帧", collect: true, display: true, ws: true, deps: [] },
  { id: "character.attributes", group: "干员", name: "干员属性数组", source: "Attributes.cachedData", grain: "整组数组 · 同帧", collect: true, display: false, ws: false, deps: [] },
  { id: "character.skill", group: "干员", name: "主技能与动作", source: "Ability / Timer / SP", grain: "技能链 · 同帧", collect: true, display: true, ws: true, deps: ["character.hp"] },
  { id: "character.stats", group: "干员", name: "伤害与治疗统计", source: "BattleStats / BattleLogger", grain: "本局累计", collect: true, display: true, ws: true, deps: [] },
  { id: "character.unattributed", group: "干员", name: "无来源总伤", source: "敌人 HP 差分 + 统计", grain: "额外跟踪 · 本局累计", collect: false, display: true, ws: false, deps: ["enemy.hp", "character.stats"] },
  { id: "deploy", group: "独立链", name: "部署 / 技能 / 撤退记录", source: "BattleLogger.m_logs", grain: "独立事件历史", collect: true, display: true, ws: true, deps: [] },
  { id: "rng", group: "独立链", name: "双路随机数", source: "randomImp / randomTrivial", grain: "独立采样", collect: true, display: true, ws: true, deps: [] },
  { id: "detail", group: "独立链", name: "敌我完整详情", source: "选中实体额外读取", grain: "异步详情", collect: false, display: false, ws: false, deps: [] },
  { id: "quality", group: "服务", name: "采样质量与心跳", source: "工作器 / WS 服务", grain: "软件状态", collect: true, display: true, ws: true, deps: [] },
];
const fieldById = Object.fromEntries(fields.map(field => [field.id, field]));

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}
function set(id, value) { byId(id).textContent = String(value); }
function fixed(value, places = 2) { return Number(value).toFixed(places); }
function clock(seconds) { return String(Math.floor(seconds / 60)).padStart(2,"0") + ":" + fixed(seconds % 60,1).padStart(4,"0"); }
function tableCell(value, className) { return node("td", className || "", String(value)); }
const activeToasts = [];
function toast(message, options = {}) {
  if (!state.toastEnabled && !options.force) return;
  const level = ["info","warn","error","success"].includes(options.level) ? options.level : "info";
  const durations = [...document.querySelectorAll(".duration-row input")].map(input => Number(input.value));
  const levelIndex = level === "error" ? 2 : level === "warn" ? 1 : 0;
  const duration = Math.max(10,Math.min(120000,durations[levelIndex] || 3200));
  const item = node("article","toast " + level);
  item.setAttribute("role",level === "error" ? "alert" : "status");
  const copy = node("div");
  copy.append(node("strong","",options.title || ({info:"提示",warn:"需要注意",error:"检测失败",success:"操作完成"})[level]),node("p","",message));
  const close = node("button","", "×");
  close.type = "button";
  close.setAttribute("aria-label","关闭提示");
  item.append(copy,close);
  byId("toast-stack").append(item);
  const entry = { item, timer:null };
  const dismiss = () => {
    clearTimeout(entry.timer);
    const index = activeToasts.indexOf(entry);
    if (index !== -1) activeToasts.splice(index,1);
    item.classList.add("leaving");
    setTimeout(() => item.remove(),180);
  };
  close.addEventListener("click",dismiss);
  activeToasts.push(entry);
  if (activeToasts.length > 5) activeToasts[0].item.querySelector("button").click();
  entry.timer = setTimeout(dismiss,duration);
  requestAnimationFrame(() => item.classList.add("show"));
}

function setNavOpen(open) {
  const drawer = byId("nav-drawer");
  drawer.classList.toggle("is-open",open);
  drawer.setAttribute("aria-hidden",String(!open));
  drawer.inert = !open;
  byId("nav-backdrop").hidden = !open;
  byId("open-nav").classList.toggle("is-hidden",open);
  byId("open-nav").setAttribute("aria-expanded",String(open));
  if (open) byId("close-nav").focus();
  else byId("open-nav").focus();
}
function visibleColumns(kind) { return (kind === "enemy" ? enemyColumns : characterColumns).filter(col => col.visible); }
function hpMarkup(cell, value, max) {
  cell.textContent = value === null ? "—" : fixed(value) + "/" + fixed(max);
  if (value === null) return;
  const track = node("span","hp-bar");
  const bar = node("i");
  bar.style.width = Math.max(0,Math.min(100,value/max*100)) + "%";
  track.append(bar);
  cell.append(track);
}

function enemyValue(enemy, key, index) {
  if (key === "row") return index + 1;
  if (key === "name") return enemy.name;
  if (key === "code") return enemy.code.split("_")[1] || enemy.code;
  if (key === "eid") return enemy.eid;
  if (key === "hp") return enemy.hp;
  if (key === "pos") return enemy.x === null ? "—" : "(" + fixed(enemy.x) + ", " + fixed(enemy.y) + ")";
  if (key === "precise_pos") return !state.precise || enemy.x === null ? "—" : "(" + fixed(enemy.x + .05) + ", " + fixed(enemy.y + .01) + ")";
  if (key === "intent_end") return enemy.life === "场上" ? "(3, 0)" : "—";
  if (key === "current_route") return enemy.route;
  if (key === "next_waypoint") return enemy.waypoint;
  if (key === "next_checkpoint") return enemy.checkpoint;
  if (key === "checkpoint_countdown") return enemy.countdown;
  if (key === "action_state") return enemy.state;
  if (key === "action_phase") return enemy.phase;
  if (key === "remaining_time") return enemy.life === "场上" ? "21 帧 / 0.70s" : "—";
  if (key === "next_action") return enemy.next;
  if (key === "abnormal_status") return enemy.abnormal;
  if (key === "immune_status") return "—";
  if (key === "shield" || key === "es") return "0.00";
  if (key === "skill") return enemy.skill;
  if (key === "life_status") return enemy.life;
  if (key === "spawn_wait") return enemy.spawn;
  if (key.startsWith("attr_")) {
    const n = Number(key.slice(5));
    if (n === 1) return fixed(enemy.atk);
    if (n === 2) return fixed(enemy.def);
    if (n === 3) return fixed(enemy.res);
    if (n === 6) return fixed(enemy.spd);
    if (n === 7) return "100.00";
    return "—";
  }
  return "—";
}
function characterValue(character, key, index) {
  const values = {
    row: index + 1, name: character.name, kind: character.kind, cid: character.cid,
    profession: character.profession, level: character.level,
    sp: fixed(character.sp) + "/" + fixed(character.maxSp),
    pos: "(" + character.x + "," + character.y + ")", action_state: character.state,
    action_phase: character.phase, remaining_time: character.remaining,
    next_action: character.next, abnormal_status: character.abnormal,
    shield: "0.00", es: "0.00", blocked: character.blocked,
    buff_count: character.buffs, damage_total: fixed(character.damage),
    global_total_damage: state.unattributed ? fixed(9365 + state.tick * 2) : "—",
    healing_total: fixed(character.healing), skill: character.skill,
  };
  if (key.startsWith("attr_")) {
    const n = Number(key.slice(5));
    if (n === 1) return fixed(character.atk);
    if (n === 2) return fixed(character.def);
    if (n === 3) return fixed(character.res);
    if (n === 7) return "100.00";
    if (n === 5) return character.blocked;
  }
  return values[key] === undefined ? "—" : values[key];
}

function renderDataTable(kind) {
  const cols = visibleColumns(kind);
  const head = byId(kind === "enemy" ? "enemy-head" : "character-head");
  const body = byId(kind === "enemy" ? "enemy-body" : "character-body");
  const scroll = head.closest(".table-scroll");
  const left = scroll.scrollLeft;
  const top = scroll.scrollTop;
  head.replaceChildren();
  body.replaceChildren();
  const headerRow = node("tr");
  for (const col of cols) headerRow.append(node("th","",col.label));
  head.append(headerRow);
  const rows = kind === "enemy"
    ? enemies.filter(enemy => !state.hideDeparted || enemy.life !== "已离场")
    : characters.filter(character => state.showTokens || character.kind === "干员");
  rows.forEach((item,index) => {
    const row = node("tr");
    for (const col of cols) {
      if (col.key === "detail") {
        const cell = node("td");
        const button = node("button","detail-button","详情");
        button.type = "button";
        button.dataset.detail = kind;
        button.dataset.entity = item.id;
        cell.append(button);
        row.append(cell);
        continue;
      }
      const value = kind === "enemy" ? enemyValue(item,col.key,index) : characterValue(item,col.key,index);
      const className = ["name","code","eid","cid"].includes(col.key) ? (col.key === "name" ? "name" : "code") : "";
      const cell = tableCell(value === null ? "—" : value,className);
      if (col.key === "hp") hpMarkup(cell,item.hp,item.maxHp);
      if (col.key === "life_status") cell.className = item.life === "未出场" ? "life-pending" : item.life === "已离场" ? "life-departed" : "value-good";
      if (col.key === "checkpoint_countdown" && value !== "该检查点无倒计时" && value !== "—") cell.className = "value-warn";
      row.append(cell);
    }
    body.append(row);
  });
  scroll.scrollLeft = left;
  scroll.scrollTop = top;
}

function renderDeploy() {
  const body = byId("deploy-body");
  body.replaceChildren();
  for (const event of deployEvents) {
    const row = node("tr");
    for (const value of [event.time, event.frame, event.op, event.char, event.direction, event.position, event.extra]) {
      row.append(tableCell(value));
    }
    body.append(row);
  }
}
function rngFraction(seed,index) {
  const raw = Math.sin(seed * 13.97 + index * 78.233) * 43758.5453;
  return fixed(raw - Math.floor(raw),4);
}
function renderRngRole(role) {
  const seed = role === "imp" ? 1183 + state.rngTick : 2968 + state.rngTick * 2;
  set("rng-" + role + "-meta", "状态：" + (state.rngRunning ? "监控中" : "已停止 · 最后已知") + "  ·  游标 " + (seed % 56) + " / " + ((seed + 31) % 56) + "  ·  已消耗 " + seed + " 发  ·  预测 " + state.rngCount + " 发");
  const pred = byId("rng-" + role + "-pred");
  const hist = byId("rng-" + role + "-hist");
  pred.replaceChildren();
  hist.replaceChildren();
  for (let i = 0; i < state.rngCount; i++) {
    const row = node("tr");
    row.append(tableCell(i + 1),tableCell(rngFraction(seed,i)));
    pred.append(row);
  }
  for (let i = 0; i < 18; i++) {
    const row = node("tr");
    row.append(tableCell(seed - 17 + i),tableCell(rngFraction(seed - 17,i)));
    hist.append(row);
  }
}
function renderTopics() {
  const grid = byId("topic-grid");
  grid.replaceChildren();
  for (const [name,defaults,limit] of topics) {
    const card = node("div","topic");
    card.append(node("code","",name),node("small","","默认 " + defaults + " Hz · 范围 " + limit + " Hz"));
    grid.append(card);
  }
}

function renderFields() {
  const query = byId("field-search").value.trim().toLowerCase();
  const body = byId("field-body");
  body.replaceChildren();
  let group = "";
  let shown = 0;
  for (const field of fields) {
    if (query && !(field.name + field.source + field.group + field.id).toLowerCase().includes(query)) continue;
    shown++;
    if (field.group !== group) {
      group = field.group;
      const separator = node("tr","group");
      const cell = node("td","",group);
      cell.colSpan = 5;
      separator.append(cell);
      body.append(separator);
    }
    const row = node("tr");
    const name = node("td","field-name");
    name.append(node("strong","",field.name),node("small","",field.source));
    row.append(name);
    for (const layer of ["collect","display","ws"]) {
      const cell = node("td");
      const toggle = node("button","toggle" + (field[layer] ? " on" : ""));
      toggle.type = "button";
      toggle.role = "switch";
      toggle.setAttribute("aria-checked",String(field[layer]));
      toggle.setAttribute("aria-label",field.name + " · " + ({collect:"采集",display:"本地展示",ws:"WS 发布"})[layer]);
      toggle.dataset.field = field.id;
      toggle.dataset.layer = layer;
      cell.append(toggle);
      row.append(cell);
    }
    row.append(node("td","granularity",field.grain + (field.required ? " · 必需" : "") + (!field.collect ? " · 未采集" : "")));
    body.append(row);
  }
  set("field-count",shown + " / " + fields.length + " 个字段");
}
function toggleField(id,layer) {
  const field = fieldById[id];
  if (layer === "collect" && field.required) {
    toast("完整帧锚点属于采集基础，不能单独关闭。",{level:"warn"});
    return;
  }
  if (layer === "collect" && !field.collect) {
    const missing = field.deps.find(dep => !fieldById[dep].collect);
    if (missing) {
      toast("请先开启「" + fieldById[missing].name + "」采集；不会暗中修改配置。",{level:"warn"});
      return;
    }
  }
  if (layer === "collect" && field.collect) {
    const dependent = fields.find(candidate => candidate.collect && candidate.deps.includes(id));
    if (dependent) {
      toast("「" + dependent.name + "」仍依赖本字段，请先关闭它。",{level:"warn"});
      return;
    }
  }
  field[layer] = !field[layer];
  renderFields();
  toast("规划交互：" + field.name + " · " + ({collect:"采集",display:"本地展示",ws:"WS 发布"})[layer] + "已" + (field[layer] ? "开启" : "关闭"));
}

let returnFocus = null;
function closeDrawer() {
  byId("overlay").hidden = true;
  state.activeDrawer = null;
  if (returnFocus && returnFocus.isConnected) returnFocus.focus();
}
function openDrawer(kicker,title,tabs) {
  returnFocus = document.activeElement;
  byId("overlay").hidden = false;
  set("drawer-kicker",kicker);
  set("drawer-title",title);
  const tabBar = byId("drawer-tabs");
  tabBar.replaceChildren();
  state.activeDrawer = { tabs, selected: 0 };
  tabs.forEach((tab,index) => {
    const button = node("button",index === 0 ? "active" : "",tab.label);
    button.type = "button";
    button.role = "tab";
    button.setAttribute("aria-selected",String(index === 0));
    button.dataset.drawerTab = String(index);
    tabBar.append(button);
  });
  showDrawerTab(0);
  byId("overlay").querySelector(".close-button").focus();
}
function showDrawerTab(index) {
  if (!state.activeDrawer) return;
  state.activeDrawer.selected = index;
  const tab = state.activeDrawer.tabs[index];
  const bar = byId("drawer-tabs");
  [...bar.children].forEach((button,i) => {
    button.classList.toggle("active",i === index);
    button.setAttribute("aria-selected",String(i === index));
  });
  tab.render(byId("drawer-body"));
}
function detailRows(rows) {
  const table = node("table","detail-table");
  for (const [name,value] of rows) {
    const row = node("tr");
    row.append(tableCell(name),tableCell(value));
    table.append(row);
  }
  return table;
}
function summaryCards(rows) {
  const grid = node("div","detail-grid");
  for (const [name,value] of rows) {
    const card = node("div");
    card.append(node("small","",name),node("strong","",value));
    grid.append(card);
  }
  return grid;
}
function tab(label,rows,intro) {
  return { label, render(body) {
    body.replaceChildren();
    if (intro) body.append(node("p","drawer-intro",intro));
    body.append(detailRows(rows));
  } };
}
function openEnemyDetail(enemy) {
  const base = [
    ["实例ID",enemy.eid], ["生存状态",enemy.life], ["行为状态",enemy.state],
    ["动作阶段",enemy.phase], ["剩余帧/时间",enemy.life === "场上" ? "21 帧 / 0.70s" : "—"],
    ["下一动作（含 CD）",enemy.next], ["预测可信度","按当前快照推断，动作结束时会重算"],
    ["当前路线",enemy.route], ["意图终点",enemy.life === "场上" ? "(3, 0)" : "—"],
    ["下一路点",enemy.waypoint], ["下一检查点",enemy.checkpoint],
    ["检查点倒计时",enemy.countdown], ["精确坐标",state.precise && enemy.x !== null ? "(" + fixed(enemy.x+.05) + ", " + fixed(enemy.y+.01) + ")" : "未采集"],
  ];
  const tabs = [
    { label:"概览", render(body) { body.replaceChildren(); body.append(node("p","drawer-intro","当前表行来自敌我完整帧；重型详情由额外通道异步读取，不自动宣称同帧。")); body.append(summaryCards([["当前生命",enemy.hp === null ? "—" : fixed(enemy.hp)],["当前路线",enemy.route],["来源帧","#" + state.frame]])); body.append(detailRows(base)); } },
    tab("属性",[["攻击",fixed(enemy.atk)],["防御",fixed(enemy.def)],["法术抗性",fixed(enemy.res)],["移动速度",fixed(enemy.spd)],["攻击速度","100.00"]],"真实详情页同时显示内部名、原始值、最终值和变化；这里是示例值。"),
    tab("损伤条",[["神经损伤","已累积 0 / 上限 1000"],["侵蚀损伤","已累积 0 / 上限 1000"],["灼燃损伤","已累积 0 / 上限 1000"],["凋亡损伤","已累积 0 / 上限 1000"],["狂躁损伤","已累积 0 / 上限 1000"]]),
    tab("状态与免疫",[["异常状态",enemy.abnormal],["眩晕","0"],["恐惧","0"],["状态免疫","—"]]),
    tab("当前 Buff",[["运行 Buff","示例中无活动 Buff"],["原始 Blackboard","详情实际可展开查看"]]),
    tab("关卡效果",[["全局 Buff","示例中未读取到作用于本敌人的效果"]]),
    tab("技能",[["当前技能",enemy.skill],["剩余 CD","就绪 / 不适用"],["触发条件","以游戏判据为准"]]),
    tab("生效帧",[["普攻动作","动画事件 OnAttack"],["投射物","效果帧与弹道时间由静态数据补充"]]),
  ];
  openDrawer("ENEMY DETAIL / 异步详情",enemy.name + " · " + enemy.code,tabs);
}
function openCharacterDetail(character) {
  const overview = [
    ["干员 ID",character.cid],["类别",character.kind],["职业",character.profession],["等级",character.level],
    ["当前生命",fixed(character.hp) + "/" + fixed(character.maxHp)],["当前技力",fixed(character.sp) + "/" + fixed(character.maxSp)],
    ["位置","(" + character.x + "," + character.y + ")"],["朝向",character.direction],
    ["动作阶段",character.phase],["剩余帧/时间",character.remaining],["下一动作",character.next],
    ["异常状态",character.abnormal],["阻挡数",character.blocked],["Buff 数",character.buffs],
  ];
  const tabs = [
    { label:"概览", render(body) { body.replaceChildren(); body.append(node("p","drawer-intro","主表实时值与异步读取的 Buff、天赋等详情应分别记录来源帧。")); body.append(summaryCards([["生命",fixed(character.hp)],["技力",fixed(character.sp) + "/" + fixed(character.maxSp)],["累计伤害",fixed(character.damage)]])); body.append(detailRows(overview)); } },
    tab("属性",[["攻击",fixed(character.atk)],["防御",fixed(character.def)],["法术抗性",fixed(character.res)],["攻击速度","100.00"]]),
    tab("伤害统计",[["累计伤害",fixed(character.damage)],["累计治疗",fixed(character.healing)],["物理 / 法术 / 真实","实际详情按类型细分"],["全局总伤","与个人累计量区分"]]),
    tab("主技能",[["技能",character.skill],["当前技力",fixed(character.sp)],["最大技力",fixed(character.maxSp)]]),
    tab("状态与免疫",[["异常状态",character.abnormal],["状态免疫","—"]]),
    tab("当前 Buff",[["Buff 数",character.buffs],["Buff 来源 / 层数 / 参数","实际详情可展开"]]),
    tab("天赋",[["天赋","异步详情读取"],["模式 / 参数","实际详情可展开"]]),
    tab("元素损伤",[["五类损伤","实际详情逐类展示已累积与剩余"]]),
    tab("其他效果",[["动态能力","异步详情读取"],["模组设置","异步详情读取"]]),
    tab("生效帧",[["普攻与技能","Spine 动画事件生效帧"]]),
  ];
  openDrawer("CHARACTER DETAIL / 异步详情",character.name + " · " + character.profession,tabs);
}

function openColumnSettings(kind) {
  const cols = kind === "enemy" ? enemyColumns : characterColumns;
  const label = kind === "enemy" ? "敌人" : "干员";
  openDrawer("DISPLAY COLUMNS / 现有功能",label + "显示列",[{
    label:"选择列",
    render(body) {
      body.replaceChildren();
      body.append(node("p","drawer-intro","现有主程序允许勾选可见列、拖动顺序和手调列宽。此处模拟勾选；不会更改采集和 WS 发布。"));
      const list = node("div","column-list");
      for (const col of cols) {
        const item = node("label");
        const input = node("input");
        input.type = "checkbox";
        input.checked = col.visible;
        input.dataset.column = col.key;
        input.dataset.kind = kind;
        item.append(input,node("span","",col.label));
        list.append(item);
      }
      body.append(list);
    },
  }]);
}
function openPrecision(kind) {
  const cols = kind === "enemy" ? enemyColumns : characterColumns;
  openDrawer("DECIMAL PRECISION / 现有功能",(kind === "enemy" ? "敌人" : "干员") + "小数位设置",[{
    label:"按列设置",
    render(body) {
      body.replaceChildren();
      body.append(node("p","drawer-intro","真实窗口按当前可见数值列设置 0–6 位小数。此处仅演示控件排布。"));
      const list = node("div","precision-list");
      for (const col of cols.filter(item => item.visible && (["hp","sp","checkpoint_countdown","damage_total","healing_total"].includes(item.key) || item.key.startsWith("attr_")))) {
        const item = node("label");
        const input = node("input");
        input.type = "number"; input.min = "0"; input.max = "6"; input.value = "2";
        item.append(node("span","",col.label),input);
        list.append(item);
      }
      body.append(list);
    },
  }]);
}
function openOverview() {
  const makeOverviewTab = (label,key,total,tone) => ({
    label, render(body) {
      body.replaceChildren();
      body.append(node("p","drawer-intro","按干员 ID 汇总本局累计数据；已撤退干员保留历史，召唤物/装置不单独计入。"));
      const donut = node("div","overview-donut " + tone);
      donut.style.setProperty("--first-share",(total > 0 ? characters[0][key] / total * 100 : 0) + "%");
      donut.dataset.total = "合计 " + fixed(total);
      body.append(donut);
      const list = node("div","overview-list");
      for (const character of characters) {
        const value = character[key];
        const row = node("div","overview-row " + tone);
        const track = node("span","overview-track");
        const bar = node("i");
        bar.style.width = (total > 0 ? value/total*100 : 0) + "%";
        track.append(bar);
        row.append(node("strong","",character.name),track,node("span","",fixed(value) + " · " + fixed(value/total*100,1) + "%"));
        list.append(row);
      }
      body.append(list);
    },
  });
  const damage = characters.reduce((sum,item) => sum + item.damage,0);
  const healing = characters.reduce((sum,item) => sum + item.healing,0);
  openDrawer("CHARACTER OVERVIEW / 现有功能","干员数据总览",[
    makeOverviewTab("总输出占比","damage",damage,"damage"),
    makeOverviewTab("治疗量占比","healing",healing,"healing"),
  ]);
}

function openInfo(kind) {
  const definitions = {
    api:["接口说明","现有 WebSocket 服务是独立网络线程，只消费主程序提交的快照，不直接读取游戏内存。",[
      ["服务地址","ws://127.0.0.1:8765"],["游戏接口","battle / stage / enemies / enemy_pathing / characters / enemy_detail / character_detail / deploy / rng / quality"],
      ["运维接口","ops.heartbeat"],["订阅速率","每 topic 独立 rateHz，上限见“运行设置与接口”"],
      ["重要边界","订阅/限频不控制上游采集；全量敌我详情由异步读取，不能默认同帧。"],
    ]],
    adb:["选择 ADB","现有窗口可刷新设备地址、浏览 adb.exe 并自动探测运行中的模拟器。",[
      ["当前可执行文件","adb.exe · 演示值"],["设备地址","127.0.0.1:7555 · 演示值"],["状态","本原型未探测真实设备"],
    ]],
    timer:["内存寻址","寻址工具负责游戏时间与逻辑帧地址。启动后可向主程序推送地址；部分流程需要管理员权限。",[
      ["计时器链","独立于敌我完整帧"],["本原型","仅模拟状态，不启动寻址进程"],
    ]],
    timeline:["排轴工具","这是另一个独立 Vue 页面，用于导入关卡/出怪 JSON，展示地图、敌人时间轴与我方操作，并编辑/导出排轴。它不是当前主程序实时监控页。",[
      ["打开方式","主程序“排轴工具”按钮启动内嵌静态 HTTP 服务"],["本原型","展示入口，不复制排轴工具本体"],
    ]],
    guide:["新手教程","现有主程序在顶部提供新手教程入口，解释 ADB、寻址与扫描步骤。",[
      ["第一步","选择 ADB 和模拟器"],["第二步","完成计时器寻址"],["第三步","进入关卡后扫描敌人、操作记录和随机数"],
    ]],
    diagnostics:["诊断日志","测试版提供实时日志窗口与一键打包诊断资料。",[
      ["内容","扫描阶段、ADB/游戏包版本、端口、内存通道、异常"],["本原型","不读取真实日志"],
    ]],
    cache:["导出本局缓存","现有按钮可导出本局最后一份完整快照；关卡结束或地址失效后仍可使用。",[
      ["包含","关卡/出怪、操作记录、敌我数据与 RNG"],["本原型","仅展示说明，未执行真实导出"],
    ]],
  };
  const [title,intro,rows] = definitions[kind];
  openDrawer("TIMELINE / 现有入口",title,[tab("说明",rows,intro)]);
}

const wsProbeTopics = {
  frame:"battle", timer:"battle", "enemy.hp":"enemies",
  "enemy.attributes":"enemy_detail", "enemy.route":"enemy_pathing",
  "enemy.checkpoint":"enemy_pathing", "enemy.countdown":"enemy_pathing",
  "enemy.abnormal":"enemies", "enemy.next":"enemies",
  "character.hp":"characters", "character.attributes":"character_detail",
  "character.skill":"characters", "character.stats":"characters",
  deploy:"deploy", rng:"rng", detail:"enemy_detail + character_detail", quality:"quality",
};
const wsUnexposed = {
  "enemy.precise":"当前 enemies 协议没有精确坐标字段",
  "enemy.skill":"当前公开协议没有完整技能判据字段",
  "enemy.roster":"当前公开协议没有完整预定出怪名册字段",
  "character.unattributed":"当前公开协议没有独立的无来源总伤字段",
};
function firstEnemy(data) {
  const items = Array.isArray(data?.items) ? data.items : [];
  return items.find(item => item?.lifecycle === "active") || items[0];
}
function firstCharacter(data) {
  const items = Array.isArray(data?.items) ? data.items : [];
  return items.find(item => item?.kind === "operator") || items[0];
}
function firstPath(data) {
  const items = Array.isArray(data?.items) ? data.items : [];
  return items.find(item => item?.pathing?.available)?.pathing || items[0]?.pathing;
}
function probeValue(id,data) {
  if (id === "frame") return data?.fixedFrame;
  if (id === "timer") return data?.gameTime;
  if (id === "enemy.hp") return firstEnemy(data)?.hp;
  if (id === "enemy.attributes") return firstEnemy(data)?.attributes;
  if (id === "enemy.route") {
    const route = firstPath(data)?.route;
    return route?.label ?? route?.globalIndex ?? route?.index;
  }
  if (id === "enemy.checkpoint") {
    const checkpoint = firstPath(data)?.nextCheckpoint;
    return checkpoint?.typeName ?? checkpoint?.type;
  }
  if (id === "enemy.countdown") {
    const countdown = firstPath(data)?.checkpointCountdown;
    return countdown?.seconds ?? countdown?.frames;
  }
  if (id === "enemy.abnormal") return firstEnemy(data)?.abnormalStatus;
  if (id === "enemy.next") return firstEnemy(data)?.action?.next_action ?? firstEnemy(data)?.action?.nextAction;
  if (id === "character.hp") return firstCharacter(data)?.hp;
  if (id === "character.attributes") return firstCharacter(data)?.attributes;
  if (id === "character.skill") return firstCharacter(data)?.skill;
  if (id === "character.stats") return firstCharacter(data)?.damageTotal;
  if (id === "deploy") return data?.events;
  if (id === "rng") return data?.by_role;
  if (id === "detail") return firstEnemy(data)?.attributes;
  if (id === "quality") return data?.sampleHz;
  return undefined;
}
function valueIsPresent(value) {
  if (value === null || value === undefined || value === "") return false;
  // An empty status/event list is still a current, valid value for that field.
  if (Array.isArray(value)) return true;
  if (typeof value === "object") return Object.keys(value).length > 0;
  return true;
}
function renderWsCheckResults(chosen,successes,received,topicErrors,connectionError) {
  const host = byId("ws-check-results");
  host.replaceChildren();
  const passed = chosen.filter(field => successes.has(field.id)).length;
  host.append(node("strong","",connectionError
    ? "连接失败 · " + connectionError
    : "检测完成 · " + passed + " / " + chosen.length + " 个已同意发布字段收到有效值"));
  const list = node("ul");
  for (const field of chosen) {
    let result;
    let tone = "check-warn";
    const topic = wsProbeTopics[field.id];
    if (!field.collect) result = "未采集：当前配置不会生成值";
    else if (wsUnexposed[field.id]) result = "协议未暴露：" + wsUnexposed[field.id];
    else if (successes.has(field.id)) { result = "收到有效值 · " + topic; tone = "check-ok"; }
    else if (connectionError) { result = "连接失败，未验证"; tone = "check-error"; }
    else if (topicErrors[topic]) { result = "订阅被拒绝：" + topicErrors[topic]; tone = "check-error"; }
    else if (field.id === "detail" && (topicErrors.enemy_detail || topicErrors.character_detail)) {
      result = "详情订阅被拒绝：" + (topicErrors.enemy_detail || topicErrors.character_detail);
      tone = "check-error";
    }
    else if (field.id === "detail") result = "敌我详情尚未同时收到有效值（需要场上敌人和干员）";
    else if (!received.has(topic)) result = "主题未收到 · " + topic;
    else result = "主题已收到，但该字段缺失或当前为空";
    list.append(node("li",tone,field.name + " — " + result));
  }
  host.append(list);
}
function runWsCheck() {
  const chosen = fields.filter(field => field.ws);
  if (!chosen.length) {
    byId("ws-check-results").textContent = "没有已同意 WS 发布的字段；先在下方打开至少一个发布开关。";
    toast("没有可检测的 WS 发布字段。",{level:"warn"});
    return;
  }
  const button = byId("ws-check-button");
  button.disabled = true;
  button.textContent = "检测中…";
  byId("ws-check-results").textContent = "正在连接本机游戏端点并订阅字段对应的主题；最多等待 7 秒。";
  const successes = new Set();
  const received = new Set();
  const topicErrors = {};
  const detailValues = new Set();
  let socket;
  let finished = false;
  let opened = false;
  let timeout;
  const finish = error => {
    if (finished) return;
    finished = true;
    clearTimeout(timeout);
    if (socket && socket.readyState < WebSocket.CLOSING) socket.close();
    button.disabled = false;
    button.textContent = "重新检测";
    renderWsCheckResults(chosen,successes,received,topicErrors,error);
    toast(error ? "本机 WS 自检未完成：" + error : "本机 WS 自检完成；请查看每个字段的结果。",{level:error ? "error" : successes.size ? "success" : "warn"});
  };
  if (typeof WebSocket === "undefined") {
    finish("当前浏览器不支持 WebSocket");
    return;
  }
  try {
    socket = new WebSocket("ws://127.0.0.1:8765/v1/game");
  } catch (error) {
    finish("浏览器拒绝建立本机连接");
    return;
  }
  timeout = setTimeout(() => finish(opened ? "" : "7 秒内未建立连接"),7000);
  socket.addEventListener("open",() => {
    opened = true;
    const names = new Set(chosen.filter(field => field.collect && field.id !== "detail" && !wsUnexposed[field.id])
      .map(field => wsProbeTopics[field.id]).filter(Boolean));
    names.delete("enemy_detail");
    names.delete("character_detail");
    if (chosen.some(field => field.ws && field.collect && ["enemy.attributes","detail"].includes(field.id))) names.add("enemies");
    if (chosen.some(field => field.ws && field.collect && ["character.attributes","detail"].includes(field.id))) names.add("characters");
    const topicsToSubscribe = Object.fromEntries([...names].map(name => [name,{rateHz:1}]));
    socket.send(JSON.stringify({type:"subscribe",topics:topicsToSubscribe,requestId:"webui-field-self-check"}));
  });
  const detailSubscribed = new Set();
  socket.addEventListener("message",event => {
    let message;
    try { message = JSON.parse(event.data); } catch { return; }
    if (message?.type === "subscription.updated") {
      for (const [topic,result] of Object.entries(message.data?.topics || {})) {
        if (result?.error) topicErrors[topic] = result.error;
      }
      return;
    }
    if (typeof message?.type !== "string" || !message.type.endsWith(".updated")) return;
    const topic = message.type.slice(0,-8);
    received.add(topic);
    const data = message.data;
    for (const field of chosen) {
      if (!field.collect || wsProbeTopics[field.id] !== topic) continue;
      if (valueIsPresent(probeValue(field.id,data))) successes.add(field.id);
    }
    if (chosen.some(field => field.id === "detail" && field.collect)
        && ["enemy_detail","character_detail"].includes(topic)
        && valueIsPresent(data?.items?.[0]?.attributes)) {
      detailValues.add(topic);
      if (detailValues.size === 2) successes.add("detail");
    }
    if (topic === "enemies" && !detailSubscribed.has("enemy_detail")
        && chosen.some(field => field.collect && ["enemy.attributes","detail"].includes(field.id))) {
      const id = firstEnemy(data)?.id;
      if (id) {
        detailSubscribed.add("enemy_detail");
        socket.send(JSON.stringify({type:"subscribe",topics:{enemy_detail:{scope:"selected",ids:[id],rateHz:1}}}));
      }
    }
    if (topic === "characters" && !detailSubscribed.has("character_detail")
        && chosen.some(field => field.collect && ["character.attributes","detail"].includes(field.id))) {
      const id = firstCharacter(data)?.id;
      if (id) {
        detailSubscribed.add("character_detail");
        socket.send(JSON.stringify({type:"subscribe",topics:{character_detail:{scope:"selected",ids:[id],rateHz:1}}}));
      }
    }
  });
  socket.addEventListener("close",() => {
    if (!finished) finish(opened ? "连接在检测期间关闭" : "本机服务不可达或浏览器阻止连接");
  });
}

function action(name) {
  if (name === "ws-check") return runWsCheck();
  if (["api","adb","timer","timeline","guide","diagnostics","cache"].includes(name)) return openInfo(name);
  if (name === "enemy-columns" || name === "character-columns") return openColumnSettings(name.startsWith("enemy") ? "enemy" : "character");
  if (name === "enemy-precision" || name === "character-precision") return openPrecision(name.startsWith("enemy") ? "enemy" : "character");
  if (name === "overview") return openOverview();
  if (name === "enemy-fit" || name === "character-fit") return toast("模拟：已按当前可见列自适应；仍可在真实程序拖动表头。");
  if (name === "mini") return toast("真实程序的迷你模式可置顶、调透明度并锁定左键穿透；本网页原型未调用系统窗口能力。");
  if (name === "pin") {
    const button = document.querySelector('[data-action="pin"]');
    button.setAttribute("aria-pressed",String(button.getAttribute("aria-pressed") !== "true"));
    return toast("模拟窗口置顶状态；浏览器页面不能直接控制系统置顶。");
  }
  if (name === "enemy-scan" || name === "character-scan") {
    state.running = true;
    set("source-battle","监控中");
    set("enemy-stop","停止监控");
    return toast(name === "enemy-scan" ? "模拟：重新定位 BattleController 并读取预定出怪序列。" : "模拟：干员复用敌人已定位的 BattleController/UnitManager。");
  }
  if (name === "enemy-stop" || name === "character-stop") {
    state.running = false;
    set("source-battle","已停止");
    return toast("模拟：敌人和干员共用工作器，停止监控会同时停止两侧刷新。");
  }
  if (name === "deploy-scan") { state.deployRunning = true; set("deploy-status","已定位 BattleLogger · 正在增量监控"); return toast("模拟：先解析关卡，再定位 BattleLogger；可在零操作时启动。"); }
  if (name === "deploy-stop") { state.deployRunning = false; set("deploy-status","已停止，历史记录保留"); return toast("模拟：操作记录轮询已停止，已观测历史保留。"); }
  if (name === "rng-scan") { state.rngRunning = true; set("rng-status","战斗随机与表现随机监控中 · 预测数两路共用"); return toast("模拟：同时定位 randomImp 与 randomTrivial。"); }
  if (name === "rng-stop") { state.rngRunning = false; set("rng-status","已停止，预测与历史留在界面"); return toast("模拟：随机数追踪已停止。"); }
  if (["stage-export","deploy-export","rng-export-imp","rng-export-trivial"].includes(name)) return exportDemo(name);
}

function exportDemo(name) {
  let payload;
  if (name === "stage-export") payload = { demo:true, stage:{stageId:"main_01-07",name:"1-7 暴君"}, plannedEnemies:23, instantiatedEnemies:6, note:"示例结构，非真实扫描导出" };
  else if (name === "deploy-export") payload = { demo:true, source:"live", stageId:"main_01-07", events:deployEvents };
  else payload = { demo:true, role:name.endsWith("imp") ? "imp" : "trivial", predictedCount:state.rngCount, history:"示例未连接实际随机数引擎" };
  const blob = new Blob([JSON.stringify(payload,null,2)],{type:"application/json"});
  const url = URL.createObjectURL(blob);
  const link = node("a");
  link.href = url;
  link.download = "timeline_" + name + "_demo.json";
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url),1000);
  toast("已导出带 demo:true 标记的模拟 JSON，不是游戏数据。");
}

function updateMetrics() {
  const gameTime = clock(state.seconds);
  set("clock-time",gameTime);
  set("workspace-clock-time",gameTime);
  set("clock-frame","逻辑帧 " + state.timerFrame);
  set("workspace-clock-frame","逻辑帧 " + state.timerFrame);
  set("source-frame","源帧 #" + state.frame);
  set("source-quality",state.running ? "一致 · 50.7 Hz" : "最后已知帧");
  set("source-deploy",state.deployRunning ? deployEvents.length + " 条事件" : "已停止");
  set("source-rng",state.rngRunning ? "双引擎" : "已停止");
  set("source-ws",state.ws ? "服务开启" : "服务关闭");
  set("diagnostic-worker",state.running ? "完整帧通过 · 模拟" : "已停止 · 最后已知帧");
  set("enemy-status",state.running
    ? "读取：设备快照（memsrv v4） · 精确坐标" + (state.precise ? "同步 6/6" : "关闭") + " · 完整帧 3 批/426 读 · IO 13.4 ms"
    : "已停止监控；表格保留最后已知值，不标为当前帧");
  set("character-status",state.running ? "与敌人共用监控 · 干员 2 · 0.6 ms/帧" : "与敌人共用的监控已停止 · 最后已知值");
}
function advance() {
  state.timerFrame += 30;
  state.seconds += 1;
  if (state.rngRunning) state.rngTick++;
  if (state.running) {
    state.tick++;
    state.frame += 30;
    enemies[2].hp = Math.max(0,enemies[2].hp - 4);
    enemies[3].hp = Math.max(0,enemies[3].hp - 7);
    enemies[0].x = Math.max(4,enemies[0].x - .02);
    characters[1].damage += 13;
    renderDataTable("enemy");
    renderDataTable("character");
  }
  if (state.rngRunning && state.page === "overview" && byId("overview-rng").open) {
    renderRngRole("imp");
    renderRngRole("trivial");
  }
  updateMetrics();
}
function setPage(page) {
  const module = ["enemies","characters","deploy","rng"].includes(page);
  const rootPage = module ? "overview" : page;
  if (!byId("page-" + rootPage)) return;
  state.page = rootPage;
  document.querySelectorAll(".content > .page").forEach(section => section.classList.toggle("active",section.id === "page-" + rootPage));
  document.querySelectorAll(".nav-button").forEach(button => button.classList.toggle("active",button.dataset.page === page));
  if (byId("nav-drawer").classList.contains("is-open")) setNavOpen(false);
  if (module) {
    const expanded = byId("overview-" + page);
    expanded.open = true;
    expanded.scrollIntoView({block:"start"});
  } else window.scrollTo(0,0);
  if (page === "rng") { renderRngRole("imp"); renderRngRole("trivial"); }
}
function init() {
  byId("clock-drawer-toggle").addEventListener("click",() => {
    const drawer = byId("clock-drawer");
    const open = drawer.classList.toggle("is-open");
    const panel = byId("clock-drawer-panel");
    panel.inert = !open;
    panel.setAttribute("aria-hidden",String(!open));
    byId("clock-drawer-toggle").setAttribute("aria-expanded",String(open));
    set("clock-toggle-label",open ? "收起游戏时钟" : "展开游戏时钟");
  });
  byId("clock-pin").addEventListener("click",() => {
    const pinned = byId("clock-drawer").classList.toggle("is-pinned");
    byId("clock-pin").setAttribute("aria-pressed",String(pinned));
    set("clock-pin",pinned ? "已置顶" : "置顶时钟");
  });
  byId("nav-drawer").inert = true;
  byId("open-nav").addEventListener("click",() => setNavOpen(true));
  byId("close-nav").addEventListener("click",() => setNavOpen(false));
  byId("nav-backdrop").addEventListener("click",() => setNavOpen(false));
  // Reuse each full module view in the overview accordion: controls, columns,
  // details and live updates stay on the same DOM nodes instead of diverging.
  for (const name of ["enemies","characters","deploy","rng"]) {
    byId("overview-panel-" + name).append(byId("page-" + name));
    const slot = byId("overview-" + name);
    slot.addEventListener("toggle",() => {
      slot.querySelector("summary em").textContent = slot.open ? "收起完整数据" : "展开完整数据";
      if (name === "rng" && slot.open) {
        renderRngRole("imp");
        renderRngRole("trivial");
      }
    });
  }
  renderDataTable("enemy");
  renderDataTable("character");
  renderDeploy();
  renderRngRole("imp");
  renderRngRole("trivial");
  renderTopics();
  renderFields();
  updateMetrics();
  document.addEventListener("click",event => {
    const page = event.target.closest("[data-page]");
    if (page) return setPage(page.dataset.page);
    const detail = event.target.closest("[data-detail]");
    if (detail) {
      if (detail.dataset.detail === "enemy") return openEnemyDetail(enemies.find(item => item.id === detail.dataset.entity));
      return openCharacterDetail(characters.find(item => item.id === detail.dataset.entity));
    }
    const field = event.target.closest("[data-field]");
    if (field) return toggleField(field.dataset.field,field.dataset.layer);
    const drawerTab = event.target.closest("[data-drawer-tab]");
    if (drawerTab) return showDrawerTab(Number(drawerTab.dataset.drawerTab));
    const command = event.target.closest("[data-action]");
    if (command) {
      if (command.dataset.action === "close-overlay") return closeDrawer();
      return action(command.dataset.action);
    }
  });
  document.addEventListener("change",event => {
    if (event.target.id === "hide-departed") { state.hideDeparted = event.target.checked; return renderDataTable("enemy"); }
    if (event.target.id === "precise-position") { state.precise = event.target.checked; renderDataTable("enemy"); return updateMetrics(); }
    if (event.target.id === "show-tokens") { state.showTokens = event.target.checked; return renderDataTable("character"); }
    if (event.target.id === "unattributed") { state.unattributed = event.target.checked; return renderDataTable("character"); }
    if (event.target.id === "ws-toggle") { state.ws = event.target.checked; updateMetrics(); return toast("模拟：WS 服务已" + (state.ws ? "开启" : "关闭") + "；采集状态不变。"); }
    if (event.target.id === "rng-count") {
      const numeric = Number(event.target.value);
      state.rngCount = Math.max(1,Math.min(500,Number.isFinite(numeric) ? numeric : 18));
      event.target.value = state.rngCount;
      renderRngRole("imp"); renderRngRole("trivial");
      return;
    }
    if (event.target.dataset.column) {
      const cols = event.target.dataset.kind === "enemy" ? enemyColumns : characterColumns;
      const col = cols.find(item => item.key === event.target.dataset.column);
      col.visible = event.target.checked;
      renderDataTable(event.target.dataset.kind);
      return;
    }
    if (event.target.dataset.setting === "toast") {
      state.toastEnabled = event.target.checked;
      return toast("气泡通知已" + (state.toastEnabled ? "开启" : "关闭") + "；本网页原型不修改 Timeline 配置文件。",{force:true,level:"success"});
    }
    if (event.target.dataset.setting) return toast("模拟：设置已切换。本网页原型不修改 Timeline 配置文件。");
  });
  byId("field-search").addEventListener("input",renderFields);
  document.addEventListener("keydown",event => {
    if (event.key !== "Escape") return;
    if (!byId("overlay").hidden) closeDrawer();
    else if (byId("nav-drawer").classList.contains("is-open")) setNavOpen(false);
  });
  setInterval(advance,1000);
}
init();
