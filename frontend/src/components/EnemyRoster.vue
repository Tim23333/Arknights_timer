<script setup>
import { computed } from "vue";
import { enemyStateAt, finiteFrame, routeColor } from "../strategy";

const props = defineProps({
  enemies: { type: Array, default: () => [] },
  journeys: { type: Map, default: () => new Map() },
  playFrame: { type: Number, default: 0 },
  fps: { type: Number, default: 30 },
  selectedIds: { type: Set, default: () => new Set() },
});
const emit = defineEmits(["toggle", "select-all", "clear-selection"]);

const rows = computed(() => props.enemies
  .map((enemy) => {
    const journey = props.journeys.get(String(enemy.id));
    const state = enemyStateAt(journey, enemy, props.playFrame, props.fps);
    let status = "待定";
    let statusClass = "pending";
    if (journey) {
      if (state.phase === "pending") { status = `F${journey.startFrame} 出场`; statusClass = "pending"; }
      else if (state.phase === "on") {
        status = state.state === "waiting" ? "检查点等待" : state.state === "hidden" ? "未现形" : "在场移动";
        statusClass = state.state === "waiting" ? "waiting" : state.state === "hidden" ? "hidden" : "on";
      } else {
        status = state.reason || "已离场";
        statusClass = "gone";
      }
    }
    let coord = "";
    if (state.phase === "on" && Number.isFinite(state.row) && Number.isFinite(state.col)) {
      // 在场：跟随播放帧的实时位置（1 位小数）
      coord = `(${state.col.toFixed(2)},${state.row.toFixed(2)})`;
    } else if (state.phase === "pending") {
      const from = journey?.legs?.[0]?.from;
      if (from) coord = `(${from.col},${from.row})`; // 未出场：出生点
    }
    return {
      id: String(enemy.id),
      name: enemy.name || enemy.enemyId || "未知敌人",
      kind: enemy.kind || "dynamic",
      routeIndex: enemy.routeIndex,
      startFrame: journey ? journey.startFrame : finiteFrame(enemy.startFrame),
      status,
      statusClass,
      coord,
      onField: state.phase === "on",
      checked: props.selectedIds.has(String(enemy.id)),
    };
  })
  .sort((a, b) => (a.startFrame ?? 1e15) - (b.startFrame ?? 1e15)));

const onFieldCount = computed(() => rows.value.filter((row) => row.onField).length);
</script>

<template>
  <aside class="roster-panel">
    <div class="roster-heading">
      <h2>敌方列表</h2>
      <span>{{ onFieldCount }} 在场 / {{ rows.length }} 总计</span>
    </div>
    <div class="roster-toolbar">
      <span>{{ selectedIds.size ? `已选 ${selectedIds.size} 个（显示选中路线）` : "未选择（不显示路线）" }}</span>
      <button type="button" @click="emit('select-all')">全选</button>
      <button type="button" :disabled="!selectedIds.size" @click="emit('clear-selection')">清空</button>
    </div>
    <div v-if="rows.length" class="roster-scroll">
      <button
        v-for="row in rows"
        :key="row.id"
        type="button"
        class="roster-row"
        :class="[row.statusClass, { checked: row.checked }]"
        @click="emit('toggle', row.id)"
      >
        <i class="route-dot" :style="{ background: routeColor(row.routeIndex) }"></i>
        <span class="roster-name">{{ row.name }}</span>
        <small v-if="row.coord" class="roster-coord">{{ row.coord }}</small>
        <small class="roster-status">{{ row.status }}</small>
      </button>
    </div>
    <div v-else class="empty-state">导入关卡 JSON 后显示敌方列表。</div>
  </aside>
</template>

<style scoped>
.roster-panel { border: 1px solid #313a49; border-radius: 12px; background: #171b22; padding: 14px; width: 290px; flex: 0 0 290px; display: flex; flex-direction: column; min-height: 0; }
.roster-heading { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px; }
.roster-heading h2 { margin: 0; font-size: 18px; }
.roster-heading span { color: #aab5c5; font-size: 12px; }
.roster-toolbar { display: flex; align-items: center; gap: 6px; margin-bottom: 8px; }
.roster-toolbar span { flex: 1 1 auto; color: #8f9bad; font-size: 11px; }
.roster-toolbar button { border: 1px solid #46566d; border-radius: 5px; background: #303b4c; color: #eef4ff; padding: 3px 8px; font-size: 11px; cursor: pointer; }
.roster-toolbar button:disabled { opacity: .4; cursor: default; }
.roster-scroll { overflow-y: auto; min-height: 0; max-height: 520px; display: flex; flex-direction: column; gap: 3px; padding-right: 4px; }
.roster-row { display: flex; align-items: center; gap: 7px; border: 0; border-radius: 6px; padding: 5px 8px; background: #11161d; color: #e8eef7; cursor: pointer; text-align: left; }
.roster-row:hover { background: #1a2230; }
.roster-row.checked { outline: 2px solid #66c2ff; background: #16222f; }
.roster-row.on { background: #14263a; }
.roster-row.on.checked { background: #173049; }
.roster-row.gone { opacity: .42; }
.route-dot { width: 9px; height: 9px; border-radius: 50%; flex: 0 0 auto; }
.roster-name { flex: 1 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; }
.roster-status { flex: 0 0 auto; font-size: 10px; color: #93a2b8; font-family: Consolas, monospace; }
.roster-coord { flex: 0 0 auto; font-size: 10px; color: #7fc98f; font-family: Consolas, monospace; }
.roster-row.gone .roster-coord { color: #5d6b7d; }
.roster-row.on .roster-status { color: #7fd6ff; }
.roster-row.waiting .roster-status { color: #ffd166; }
.roster-row.hidden .roster-status { color: #b9a7ff; }
.empty-state { color: #8f9aac; text-align: center; padding: 30px 10px; background: #0d1015; border-radius: 8px; font-size: 12px; }
</style>
