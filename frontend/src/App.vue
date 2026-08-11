<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { version as FRONTEND_VERSION } from "../package.json";
import StageMap from "./components/StageMap.vue";
import EnemyTimeline from "./components/EnemyTimeline.vue";
import OperatorTimeline from "./components/OperatorTimeline.vue";
import EnemyRoster from "./components/EnemyRoster.vue";
import {
  ACTION_TYPES,
  FPS,
  actionsFromGroups,
  buildOperatorLifecycles,
  emptyGroups,
  enemyJourney,
  flipGroupsPos,
  groupsFromActions,
  groupsFromLegacyRows,
  normalizeStagePackage,
  uid,
} from "./strategy";

const CACHE_KEY = "ak_strategy_workspace_v1";
const stageFileInput = ref(null);
const statusText = ref("请导入后端导出的关卡/出怪 JSON");
const pxPerSecond = ref(12);
const stagePackage = ref(normalizeStagePackage({}));
const operatorGroups = ref(emptyGroups());
const selectedEnemyId = ref("");
const selectedActionRef = ref(null);
let saveTimer = null;

const selectedEnemy = computed(() => stagePackage.value.enemySpawns.find(
  (enemy) => String(enemy.id) === String(selectedEnemyId.value),
) || null);

const selectedAction = computed(() => {
  const refValue = selectedActionRef.value;
  if (!refValue) return null;
  const row = (operatorGroups.value[refValue.category] || []).find((item) => item.id === refValue.rowId);
  const action = row?.actions.find((item) => item.id === refValue.actionId);
  return action ? { category: refValue.category, row, action } : null;
});

// ===== 播放引擎 =====
const playFrame = ref(0);
const playing = ref(false);
const playRate = ref(1);
let rafId = null;
let lastTickTime = 0;

const routeByIndex = computed(() => {
  const map = new Map();
  for (const route of stagePackage.value.routes || []) {
    const key = Number(route.index);
    // 旧版导出文件 extra 路线与主路线 index 重复（0/1/2 两轮）：
    // 重复时优先保留主路线，避免敌人走错路。
    const prev = map.get(key);
    if (!prev || (prev.isExtra && !route.isExtra)) map.set(key, route);
  }
  return map;
});

const journeys = computed(() => {
  const map = new Map();
  for (const enemy of stagePackage.value.enemySpawns || []) {
    const journey = enemyJourney(enemy, routeByIndex.value.get(Number(enemy.routeIndex)), FPS, stagePackage.value.map);
    if (journey) map.set(String(enemy.id), journey);
  }
  return map;
});

const lifecycles = computed(() => buildOperatorLifecycles(operatorGroups.value));

// ===== 敌方列表多选过滤（空选择 = 显示全部）=====
const selectedEnemyIds = ref(new Set());

const filteredEnemies = computed(() => {
  if (!selectedEnemyIds.value.size) return stagePackage.value.enemySpawns || [];
  return (stagePackage.value.enemySpawns || []).filter(
    (enemy) => selectedEnemyIds.value.has(String(enemy.id)));
});

const visibleRouteIndexes = computed(() => {
  // 默认不画任何路线；只显示在敌方列表中选中敌人的路线。
  if (!selectedEnemyIds.value.size) return new Set();
  return new Set(filteredEnemies.value.map((enemy) => Number(enemy.routeIndex)));
});

function toggleEnemySelection(id) {
  const key = String(id);
  const next = new Set(selectedEnemyIds.value);
  if (next.has(key)) {
    next.delete(key);
    if (selectedEnemyId.value === key) selectedEnemyId.value = "";
  } else {
    next.add(key);
    selectedEnemyId.value = key;
  }
  selectedEnemyIds.value = next;
}

function selectAllEnemies() {
  selectedEnemyIds.value = new Set(
    (stagePackage.value.enemySpawns || []).map((enemy) => String(enemy.id)));
}

function clearEnemySelection() {
  selectedEnemyIds.value = new Set();
}

function onSeek(frame) {
  playFrame.value = Math.max(0, Math.min(durationFrames.value, Math.round(frame) || 0));
}

function stopPlaybackLoop() {
  if (rafId !== null) cancelAnimationFrame(rafId);
  rafId = null;
}

function playbackTick(timestamp) {
  if (!playing.value) { rafId = null; return; }
  if (lastTickTime) {
    const dt = Math.min(0.25, (timestamp - lastTickTime) / 1000);
    playFrame.value = Math.min(durationFrames.value, playFrame.value + dt * FPS * playRate.value);
    if (playFrame.value >= durationFrames.value) {
      playing.value = false;
      rafId = null;
      return;
    }
  }
  lastTickTime = timestamp;
  rafId = requestAnimationFrame(playbackTick);
}

function togglePlay() {
  playing.value = !playing.value;
  if (playing.value) {
    if (playFrame.value >= durationFrames.value) playFrame.value = 0;
    lastTickTime = 0;
    rafId = requestAnimationFrame(playbackTick);
  } else {
    stopPlaybackLoop();
  }
}

function resetPlay() {
  playing.value = false;
  stopPlaybackLoop();
  playFrame.value = 0;
}

function onScrub(event) {
  playFrame.value = Math.max(0, Number(event.target.value) || 0);
  if (playing.value) togglePlay();
}

onBeforeUnmount(stopPlaybackLoop);

const durationFrames = computed(() => {
  let maximum = FPS * 120;
  for (const enemy of stagePackage.value.enemySpawns || []) {
    // endFrame 缺失（未击杀/未观测到进蓝门）时用 journey 估算的到达蓝门帧兜底，
    // 否则像 5-10 浮士德这种晚出场 + 长行程的敌人会在播放入口前就被截断
    const journey = journeys.value.get(String(enemy.id));
    for (const value of [enemy.startFrame, enemy.endFrame, journey?.effectiveEnd]) {
      const number = Number(value);
      if (Number.isFinite(number) && number >= 0) maximum = Math.max(maximum, number + FPS * 10);
    }
  }
  for (const rows of Object.values(operatorGroups.value)) {
    for (const row of rows || []) {
      for (const action of row.actions || []) {
        const frame = Number(action.frame);
        if (action.frame !== null && action.frame !== "" && Number.isFinite(frame)) {
          maximum = Math.max(maximum, frame + FPS * 10);
        }
      }
    }
  }
  return Math.min(Math.ceil(maximum / (FPS * 30)) * FPS * 30, FPS * 3600 * 10);
});

const enemyKindCounts = computed(() => {
  const counts = { scheduled: 0, conditional: 0, summoned: 0, dynamic: 0 };
  for (const enemy of stagePackage.value.enemySpawns || []) {
    const key = enemy.kind in counts ? enemy.kind : "dynamic";
    counts[key] += 1;
  }
  return counts;
});

function downloadJson(payload, filename) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function safeFilePart(value, fallback) {
  return String(value || fallback).replace(/[\\/:*?"<>|\s]+/g, "_").slice(0, 80);
}

function normalizeOperatorPlan(plan) {
  const result = emptyGroups();
  for (const category of Object.keys(result)) {
    result[category] = (Array.isArray(plan?.[category]) ? plan[category] : []).map((row) => ({
      id: row.id || uid(),
      oper: String(row.oper || row.name || "未知干员"),
      actions: (Array.isArray(row.actions) ? row.actions : []).map((action) => ({
        id: action.id || uid(),
        frame: action.frame === null || action.frame === "" || action.frame === undefined
          ? null : Math.max(0, Math.round(Number(action.frame) || 0)),
        pos: action.pos || "",
        direction: action.direction || "",
        note: action.note || "",
      })),
    }));
  }
  return result;
}

// 旧导出/旧工作区的我方坐标是底部基准 (gridRow 0=底部)，导入时用
// strategy.js 的 flipGroupsPos 翻转到顶部基准显示；rows<=0 时不翻。

function buildOperatorPayload() {
  return {
    positionsTopBased: true,
    settings: {
      map_code: stagePackage.value.stage.code || stagePackage.value.stage.levelId || "",
      map_name: stagePackage.value.stage.name || "",
    },
    actions: actionsFromGroups(operatorGroups.value),
  };
}

function buildWorkspacePayload() {
  return {
    ...stagePackage.value,
    schema: "arknights-stage-strategy",
    schemaVersion: 1,
    exportedAt: new Date().toISOString(),
    timeline: { fps: FPS, pxPerSecond: pxPerSecond.value },
    operatorActions: actionsFromGroups(operatorGroups.value),
    operatorPlan: JSON.parse(JSON.stringify(operatorGroups.value)),
  };
}

function exportWorkspace() {
  const code = safeFilePart(stagePackage.value.stage.code || stagePackage.value.stage.levelId, "stage");
  downloadJson(buildWorkspacePayload(), `ark_strategy_${code}.json`);
  statusText.value = "已导出完整排轴（地图、出怪与我方操作）";
}

function exportOperatorActions() {
  const code = safeFilePart(stagePackage.value.stage.code || stagePackage.value.stage.levelId, "stage");
  downloadJson(buildOperatorPayload(), `deploy_log_${code}.json`);
  statusText.value = "已按现有关卡局内操作追踪格式导出我方操作";
}

function triggerImport() {
  stageFileInput.value?.click();
}

function applyImportedPayload(payload) {
  if (Array.isArray(payload?.actions)) {
    // 后端部署追踪导出 (settings/actions) 坐标为底部基准；前端再导出的带
    // positionsTopBased 标记，不翻。无地图时无行数可翻，跳过。
    const flipRows = payload.positionsTopBased ? 0 : (Number(stagePackage.value.map?.rows) || 0);
    operatorGroups.value = flipGroupsPos(groupsFromActions(payload.actions), flipRows);
    const settings = payload.settings || payload;
    stagePackage.value.stage.code = settings.map_code || stagePackage.value.stage.code;
    stagePackage.value.stage.name = settings.map_name || stagePackage.value.stage.name;
    statusText.value = `已导入我方操作：${payload.actions.length} 条`;
    return;
  }
  if (payload?.meta && Array.isArray(payload.rows)) {
    const flipRows = payload.positionsTopBased ? 0 : (Number(stagePackage.value.map?.rows) || 0);
    operatorGroups.value = flipGroupsPos(groupsFromLegacyRows(payload.rows), flipRows);
    statusText.value = "已迁移旧版排轴 JSON 到部署/技能/撤退三类时间轴";
    return;
  }
  if (payload?.map || payload?.mapData || payload?.enemySpawns || payload?.waves) {
    const normalized = normalizeStagePackage(payload);
    stagePackage.value = normalized;
    resetPlay();
    selectedEnemyIds.value = new Set();
    if (payload.operatorPlan && typeof payload.operatorPlan === "object") {
      // 旧工作区无 positionsTopBased 标记: 路线/地图已被 normalize 翻转,
      // operatorPlan 里的坐标也要同步翻转, 否则干员部署上下颠倒
      const flipRows = payload.positionsTopBased ? 0 : (Number(normalized.map?.rows) || 0);
      operatorGroups.value = flipGroupsPos(normalizeOperatorPlan(payload.operatorPlan), flipRows);
    } else if (Array.isArray(payload.operatorActions)) {
      // 用 normalized 的 operatorActions：其中的 (列,行) 坐标已随包翻转到顶部基准。
      operatorGroups.value = groupsFromActions(normalized.operatorActions);
    }
    const zoom = Number(payload.timeline?.pxPerSecond);
    if (Number.isFinite(zoom)) pxPerSecond.value = Math.min(36, Math.max(4, zoom));
    selectedEnemyId.value = "";
    selectedActionRef.value = null;
    statusText.value = `已导入 ${normalized.map.rows}×${normalized.map.cols} 地图、${normalized.enemySpawns.length} 个出怪项`;
    return;
  }
  throw new Error("无法识别的 JSON：需要 map/enemySpawns、mapData/waves、settings/actions 或旧版 meta/rows");
}

async function importJson(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  try {
    applyImportedPayload(JSON.parse(await file.text()));
    persistWorkspace();
  } catch (error) {
    statusText.value = `导入失败：${error instanceof Error ? error.message : "JSON 无法解析"}`;
  } finally {
    event.target.value = "";
  }
}

const OPERATOR_CATEGORIES = ["deploy", "skill", "withdraw"];

function addOperator() {
  const names = new Set();
  for (const category of OPERATOR_CATEGORIES) {
    for (const row of operatorGroups.value[category]) names.add(row.oper);
  }
  let index = names.size + 1;
  while (names.has(`干员${index}`)) index += 1;
  operatorGroups.value.deploy.push({ id: uid(), oper: `干员${index}`, actions: [] });
}

function removeOperator(oper) {
  for (const category of OPERATOR_CATEGORIES) {
    operatorGroups.value[category] = operatorGroups.value[category].filter((row) => row.oper !== oper);
  }
  const selected = selectedActionRef.value;
  if (selected && !OPERATOR_CATEGORIES.some(
    (category) => operatorGroups.value[category].some((row) => row.id === selected.rowId))) {
    selectedActionRef.value = null;
  }
}

function renameOperator(oldOper, newName) {
  const name = String(newName || "").trim() || "未知干员";
  for (const category of OPERATOR_CATEGORIES) {
    for (const row of operatorGroups.value[category]) {
      if (row.oper === oldOper) row.oper = name;
    }
  }
}

function addOperatorAction(category, oper, frame) {
  let row = operatorGroups.value[category].find((item) => item.oper === oper);
  if (!row) {
    row = { id: uid(), oper, actions: [] };
    operatorGroups.value[category].push(row);
  }
  const action = { id: uid(), frame, pos: "", direction: "", note: "" };
  row.actions.push(action);
  row.actions.sort((a, b) => {
    if (a.frame === null) return b.frame === null ? 0 : 1;
    if (b.frame === null) return -1;
    return a.frame - b.frame;
  });
  selectedActionRef.value = { category, rowId: row.id, actionId: action.id };
  statusText.value = `已添加${ACTION_TYPES[category]}：${row.oper} F${frame}`;
}

function selectOperatorAction(category, rowId, actionId) {
  selectedActionRef.value = { category, rowId, actionId };
}

function deleteSelectedAction() {
  const selected = selectedAction.value;
  if (!selected) return;
  selected.row.actions = selected.row.actions.filter((item) => item.id !== selected.action.id);
  selectedActionRef.value = null;
  statusText.value = "已删除选中的我方操作";
}

function updateOptionalEnemyFrame(field, value) {
  if (!selectedEnemy.value) return;
  const number = Number(value);
  selectedEnemy.value[field] = value === "" || !Number.isFinite(number) ? null : Math.max(0, Math.round(number));
}

function persistWorkspace() {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify(buildWorkspacePayload()));
  } catch {
    // 浏览器禁用存储时不影响导入、编辑和下载。
  }
}

function schedulePersist() {
  if (saveTimer) clearTimeout(saveTimer);
  saveTimer = setTimeout(persistWorkspace, 250);
}

function restoreWorkspace() {
  const raw = localStorage.getItem(CACHE_KEY);
  if (!raw) return;
  try {
    const payload = JSON.parse(raw);
    const normalized = normalizeStagePackage(payload);
    stagePackage.value = normalized;
    // 与 applyImportedPayload 一致：旧工作区(无 positionsTopBased 标记)的
    // operatorPlan 坐标需随包翻转；operatorActions 直接用 normalized 的(已翻转)
    const flipRows = payload.positionsTopBased ? 0 : (Number(normalized.map?.rows) || 0);
    operatorGroups.value = payload.operatorPlan && typeof payload.operatorPlan === "object"
      ? flipGroupsPos(normalizeOperatorPlan(payload.operatorPlan), flipRows)
      : groupsFromActions(normalized.operatorActions || []);
    const zoom = Number(payload.timeline?.pxPerSecond);
    if (Number.isFinite(zoom)) pxPerSecond.value = Math.min(36, Math.max(4, zoom));
    statusText.value = "已恢复上次未导出的本地排轴";
  } catch {
    localStorage.removeItem(CACHE_KEY);
  }
}

watch([stagePackage, operatorGroups, pxPerSecond], schedulePersist, { deep: true });
onMounted(() => {
  document.title = `明日方舟地图与排轴工具 v${FRONTEND_VERSION}`;
  restoreWorkspace();
});
</script>

<template>
  <main class="page-shell">
    <header class="app-header">
      <div>
        <p class="eyebrow">ARKNIGHTS STRATEGY WORKSPACE</p>
        <h1>明日方舟地图与排轴工具 <span class="app-ver">v{{ FRONTEND_VERSION }}</span></h1>
        <p>地图、敌人生命周期与我方操作使用同一帧坐标，方便攻略作者安排部署和技能时机。</p>
      </div>
      <div class="header-actions">
        <button class="primary" type="button" @click="triggerImport">导入关卡/排轴 JSON</button>
        <button type="button" @click="exportWorkspace">导出完整排轴</button>
        <button type="button" @click="exportOperatorActions">仅导出我方操作</button>
        <input ref="stageFileInput" class="hidden" type="file" accept="application/json" @change="importJson" />
      </div>
    </header>

    <section class="stage-summary">
      <label>关卡编号<input v-model.trim="stagePackage.stage.code" placeholder="例如 1-7" /></label>
      <label>关卡名称<input v-model.trim="stagePackage.stage.name" placeholder="关卡名称" /></label>
      <label>Level ID<input v-model.trim="stagePackage.stage.levelId" placeholder="level_main_01-07" /></label>
      <label class="zoom-control">
        时间轴缩放
        <input v-model.number="pxPerSecond" type="range" min="4" max="36" step="1" />
        <strong>{{ pxPerSecond }}px/s</strong>
      </label>
      <div class="metric"><span>固定波次</span><strong>{{ enemyKindCounts.scheduled }}</strong></div>
      <div class="metric"><span>条件/随机</span><strong>{{ enemyKindCounts.conditional }}</strong></div>
      <div class="metric"><span>召唤/转阶段</span><strong>{{ enemyKindCounts.summoned }}</strong></div>
      <div class="metric"><span>运行时动态</span><strong>{{ enemyKindCounts.dynamic }}</strong></div>
    </section>

    <div class="status-bar">{{ statusText }}</div>

    <div class="playback-bar">
      <button class="primary" type="button" @click="togglePlay">{{ playing ? "⏸ 暂停" : "▶ 播放" }}</button>
      <button type="button" @click="resetPlay">复位</button>
      <select v-model.number="playRate" title="播放速度">
        <option :value="0.5">0.5×</option>
        <option :value="1">1×</option>
        <option :value="2">2×</option>
        <option :value="4">4×</option>
      </select>
      <input
        class="play-slider"
        type="range"
        min="0"
        :max="durationFrames"
        :value="Math.round(playFrame)"
        @input="onScrub"
      />
      <strong class="play-readout">F{{ Math.round(playFrame) }} · {{ (playFrame / FPS).toFixed(1) }}s</strong>
    </div>

    <div class="map-row">
      <StageMap
        :map="stagePackage.map"
        :routes="stagePackage.routes"
        :enemies="filteredEnemies"
        :journeys="journeys"
        :lifecycles="lifecycles"
        :visible-route-indexes="visibleRouteIndexes"
        :selected-ids="selectedEnemyIds"
        :play-frame="playFrame"
        :fps="FPS"
      />
      <EnemyRoster
        :enemies="stagePackage.enemySpawns"
        :journeys="journeys"
        :play-frame="playFrame"
        :fps="FPS"
        :selected-ids="selectedEnemyIds"
        @toggle="toggleEnemySelection"
        @select-all="selectAllEnemies"
        @clear-selection="clearEnemySelection"
      />
    </div>

    <EnemyTimeline
      :enemies="filteredEnemies"
      :journeys="journeys"
      :fps="FPS"
      :px-per-second="pxPerSecond"
      :duration-frames="durationFrames"
      :selected-id="selectedEnemyId"
      :play-frame="playFrame"
      :playing="playing"
      @select="selectedEnemyId = String($event)"
      @seek="onSeek"
    />

    <section v-if="selectedEnemy" class="editor-card enemy-editor">
      <div class="editor-title">
        <div><small>敌人块编辑</small><strong>{{ selectedEnemy.name || selectedEnemy.enemyId }}</strong></div>
        <button type="button" @click="selectedEnemyId = ''">关闭</button>
      </div>
      <label>出生帧<input :value="selectedEnemy.startFrame ?? ''" type="number" min="0" @change="updateOptionalEnemyFrame('startFrame', $event.target.value)" /></label>
      <label>死亡/转阶段帧<input :value="selectedEnemy.endFrame ?? ''" type="number" min="0" placeholder="留空表示未知" @change="updateOptionalEnemyFrame('endFrame', $event.target.value)" /></label>
      <label>结束原因<input v-model.trim="selectedEnemy.endReason" placeholder="死亡 / 转阶段 / 漏怪" /></label>
      <label class="wide">攻略备注<input v-model.trim="selectedEnemy.note" placeholder="例如：优先处理、进入二阶段" /></label>
      <span class="readonly-info">{{ selectedEnemy.kind }} · W{{ selectedEnemy.wave + 1 }} · 路线 {{ selectedEnemy.routeIndex }}</span>
    </section>

    <OperatorTimeline
      :groups="operatorGroups"
      :fps="FPS"
      :px-per-second="pxPerSecond"
      :duration-frames="durationFrames"
      :selected-action-id="selectedAction?.action.id || ''"
      :play-frame="playFrame"
      :playing="playing"
      @add-oper="addOperator"
      @remove-oper="removeOperator"
      @rename-oper="renameOperator"
      @add-action="addOperatorAction"
      @select-action="selectOperatorAction"
      @seek="onSeek"
    />

    <section v-if="selectedAction" class="editor-card action-editor">
      <div class="editor-title">
        <div><small>我方操作编辑</small><strong>{{ ACTION_TYPES[selectedAction.category] }} · {{ selectedAction.row.oper }}</strong></div>
        <button type="button" @click="selectedActionRef = null">关闭</button>
      </div>
      <label>帧<input v-model.number="selectedAction.action.frame" type="number" min="0" step="1" /></label>
      <label>格子<input v-model.trim="selectedAction.action.pos" placeholder="例如 F9" /></label>
      <label v-if="selectedAction.category === 'deploy'">
        朝向
        <select v-model="selectedAction.action.direction">
          <option value="">未设置</option><option>上</option><option>下</option><option>左</option><option>右</option>
        </select>
      </label>
      <label class="wide">备注<input v-model.trim="selectedAction.action.note" placeholder="备注仅保存在完整排轴中" /></label>
      <button class="danger" type="button" @click="deleteSelectedAction">删除此操作</button>
    </section>

    <footer>
      <span>双击我方时间轴在该时刻添加技能，行首「部/技/撤」按钮按播放头位置添加；点击敌人块或动作块编辑精确帧。</span>
      <span>“仅导出我方操作”严格输出现有 <code>settings/actions</code> 格式。</span>
    </footer>
  </main>
</template>

<style scoped>
:global(*) { box-sizing: border-box; }
:global(body) { margin: 0; background: #0c0f14; color: #f4f7fc; font-family: "Segoe UI", "Microsoft YaHei", sans-serif; }
:global(button), :global(input), :global(select) { font: inherit; }
.page-shell { min-height: 100vh; padding: 20px; display: flex; flex-direction: column; gap: 14px; background: radial-gradient(circle at 78% 0%, #1c2a3b 0, transparent 34%), #0c0f14; }
.app-header { display: flex; justify-content: space-between; align-items: flex-end; gap: 24px; padding: 6px 2px 16px; border-bottom: 1px solid #313a49; }
.eyebrow { margin: 0 0 4px; color: #66c2ff; font: 700 10px Consolas, monospace; letter-spacing: .18em; }
.app-header h1 { margin: 0; font-size: 27px; letter-spacing: .02em; }
.app-header .app-ver { font-size: 13px; font-weight: 500; color: #7fc7ff; vertical-align: middle; margin-left: 6px; letter-spacing: 0; }
.app-header p:last-child { margin: 7px 0 0; color: #9ca8ba; font-size: 13px; }
.header-actions { display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
button { border: 1px solid #445166; border-radius: 7px; padding: 7px 11px; background: #293344; color: #f2f6fd; cursor: pointer; }
button:hover { filter: brightness(1.13); }
button.primary { background: #2676d9; border-color: #3991f4; }
button.danger { background: #8d3340; border-color: #bc4e5e; }
.hidden { display: none; }
.stage-summary { display: grid; grid-template-columns: minmax(150px, 1fr) minmax(170px, 1.2fr) minmax(190px, 1.3fr) minmax(220px, 1.4fr) repeat(4, minmax(82px, .45fr)); gap: 8px; align-items: stretch; }
.stage-summary label, .metric { border: 1px solid #303a49; border-radius: 8px; background: #151a21; padding: 7px 9px; }
.stage-summary label { display: flex; flex-direction: column; gap: 4px; color: #8f9bad; font-size: 10px; }
.stage-summary input:not([type="range"]), .editor-card input, .editor-card select { width: 100%; background: #0b0e13; color: #f5f8fd; border: 1px solid #39465a; border-radius: 5px; padding: 5px 7px; }
.zoom-control { min-width: 210px; }
.zoom-control input { width: 100%; }
.zoom-control strong { color: #cfe7ff; font: 11px Consolas, monospace; }
.metric { display: flex; flex-direction: column; justify-content: center; align-items: center; gap: 2px; }
.metric span { color: #8f9bad; font-size: 9px; white-space: nowrap; }
.metric strong { font-size: 18px; }
.status-bar { padding: 7px 10px; border-left: 3px solid #66c2ff; background: #15202c; color: #b9c7d9; font-size: 12px; border-radius: 0 6px 6px 0; }
.playback-bar { display: flex; align-items: center; gap: 10px; border: 1px solid #313a49; border-radius: 10px; background: #171b22; padding: 9px 12px; }
.playback-bar select { background: #0b0e13; color: #f5f8fd; border: 1px solid #39465a; border-radius: 5px; padding: 5px 6px; }
.play-slider { flex: 1 1 auto; accent-color: #ff5252; }
.play-readout { color: #cfe7ff; font: 13px Consolas, monospace; flex: 0 0 auto; min-width: 130px; text-align: right; }
.map-row { display: flex; gap: 14px; align-items: stretch; }
.map-row > .map-panel { flex: 1 1 auto; min-width: 0; }
@media (max-width: 1100px) { .map-row { flex-direction: column; } .map-row > aside { width: 100%; flex-basis: auto; } }
.editor-card { position: sticky; bottom: 10px; z-index: 20; align-self: stretch; display: grid; grid-template-columns: minmax(210px, 1.2fr) repeat(3, minmax(140px, .7fr)) minmax(240px, 1.4fr) auto; gap: 9px; align-items: end; padding: 11px; background: #222a36f2; border: 1px solid #52627a; border-radius: 10px; box-shadow: 0 10px 28px #000b; backdrop-filter: blur(8px); }
.editor-card label { display: flex; flex-direction: column; gap: 4px; color: #a9b5c5; font-size: 10px; }
.editor-title { display: flex; justify-content: space-between; align-items: center; gap: 9px; }
.editor-title div { display: flex; flex-direction: column; gap: 2px; }
.editor-title small { color: #7fc7ff; }
.editor-title strong { font-size: 14px; }
.editor-title button { padding: 4px 7px; }
.readonly-info { color: #9daabc; font: 11px Consolas, monospace; align-self: center; }
footer { display: flex; justify-content: space-between; gap: 16px; color: #7f8b9e; font-size: 11px; padding: 4px 2px 12px; }
footer code { color: #ffd166; }
@media (max-width: 1250px) {
  .stage-summary { grid-template-columns: repeat(4, 1fr); }
  .editor-card { grid-template-columns: repeat(3, 1fr); }
  .editor-title, .editor-card .wide { grid-column: span 2; }
}
@media (max-width: 780px) {
  .page-shell { padding: 10px; }
  .app-header { align-items: flex-start; flex-direction: column; }
  .stage-summary { grid-template-columns: repeat(2, 1fr); }
  .editor-card { position: static; grid-template-columns: 1fr; }
  .editor-title, .editor-card .wide { grid-column: auto; }
  footer { flex-direction: column; }
}
</style>
