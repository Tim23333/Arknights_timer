<script setup>
import { computed, ref } from "vue";
import { enemyStateAt, operatorStateAt, parseGridPos, routeColor, computeRoutePath } from "../strategy";

const props = defineProps({
  map: { type: Object, default: () => ({}) },
  routes: { type: Array, default: () => [] },
  enemies: { type: Array, default: () => [] },
  journeys: { type: Map, default: () => new Map() },
  lifecycles: { type: Array, default: () => [] },
  visibleRouteIndexes: { type: Set, default: null },
  selectedIds: { type: Set, default: () => new Set() },
  playFrame: { type: Number, default: 0 },
  fps: { type: Number, default: 30 },
});

const cellSize = ref(58);
const selectedTile = ref(null);
const rows = computed(() => Math.max(0, Number(props.map?.rows) || 0));
const cols = computed(() => Math.max(0, Number(props.map?.cols) || 0));

const routeColors = ["#ff7a7a", "#66c2ff", "#ffd166", "#a78bfa", "#70e1a1", "#ff9f43"];
const categoryLabels = {
  enemy_spawn: "敌方出生点",
  friendly_goal: "我方蓝门",
  teleport_in: "传送入口",
  teleport_out: "传送出口",
  hole: "地穴",
  forbidden: "不可用",
  highland: "高台/墙",
  obstacle: "障碍",
  device: "装置/机制",
  ground: "地面",
};
const categorySymbols = {
  enemy_spawn: "红",
  friendly_goal: "蓝",
  teleport_in: "入",
  teleport_out: "出",
  hole: "坑",
  forbidden: "×",
  highland: "高",
  obstacle: "障",
  device: "装",
  ground: "",
};

const tileMap = computed(() => {
  const out = new Map();
  for (const tile of props.map?.tiles || []) {
    out.set(`${tile.row}:${tile.col}`, tile);
  }
  return out;
});

const deviceMap = computed(() => {
  const out = new Map();
  for (const device of props.map?.devices || []) {
    const key = `${device.row}:${device.col}`;
    if (!out.has(key)) out.set(key, []);
    out.get(key).push(device);
  }
  return out;
});

const edgeMap = computed(() => {
  const out = new Map();
  for (const edge of props.map?.blockEdges || []) {
    const key = `${edge.row}:${edge.col}`;
    if (!out.has(key)) out.set(key, []);
    out.get(key).push(edge);
  }
  return out;
});

const GAP_ROW_HEIGHT = 0.32;

// 整行都是禁行格（且无装置/阻断边）的行视为区域间隔带，压缩成细条显示，
// 避免双层/双区关卡（如 17-17）被画成等高的“两份地图”。
const gapRowSet = computed(() => {
  const set = new Set();
  if (!tileMap.value.size) return set;
  for (let row = 0; row < rows.value; row += 1) {
    let hasContent = false;
    for (let col = 0; col < cols.value; col += 1) {
      const tile = tileMap.value.get(`${row}:${col}`);
      if (tile && tile.category && tile.category !== "forbidden") { hasContent = true; break; }
      if (deviceMap.value.has(`${row}:${col}`) || edgeMap.value.has(`${row}:${col}`)) { hasContent = true; break; }
    }
    if (!hasContent) set.add(row);
  }
  return set;
});

// 显示布局：游戏坐标 row 0 = 画面顶部，从上到下按 row 升序排列
const rowLayout = computed(() => {
  const layout = new Map();
  let y = 0;
  for (let row = 0; row < rows.value; row += 1) {
    const h = gapRowSet.value.has(row) ? GAP_ROW_HEIGHT : 1;
    layout.set(row, { y, h });
    y += h;
  }
  return { layout, total: y };
});

const gridTemplateRows = computed(() => {
  const parts = [];
  for (let row = 0; row < rows.value; row += 1) {
    parts.push(`${rowLayout.value.layout.get(row).h * cellSize.value}px`);
  }
  return parts.join(" ");
});

function yCenter(row) {
  const info = rowLayout.value.layout.get(row);
  return info ? info.y + info.h / 2 : null;
}

/** 小数行号 → 显示 y（格单位），在行带中心间线性插值。 */
function yOf(rowFloat) {
  if (!Number.isFinite(rowFloat)) return null;
  const base = Math.floor(rowFloat);
  const frac = rowFloat - base;
  const info = rowLayout.value.layout.get(base);
  if (!info) return null;
  const next = rowLayout.value.layout.get(base + 1);
  const center = info.y + info.h / 2;
  const nextCenter = next ? next.y + next.h / 2 : info.y + info.h;
  return center + frac * (nextCenter - center);
}

// ===== 播放时的敌我实时位置标记 =====
const enemyMarkers = computed(() => {
  const result = [];
  for (const enemy of props.enemies) {
    const journey = props.journeys.get(String(enemy.id));
    if (!journey) continue;
    const state = enemyStateAt(journey, enemy, props.playFrame, props.fps);
    if (state.phase !== "on") continue;
    if (yOf(state.row) === null) continue;
    result.push({
      id: String(enemy.id),
      name: enemy.name || enemy.enemyId || "敌人",
      row: state.row,
      col: state.col,
      state: state.state,
      color: routeColor(enemy.routeIndex),
      pinned: props.selectedIds.has(String(enemy.id)),
    });
  }
  return result;
});

const DIR_GLYPHS = { 上: "▲", 下: "▼", 左: "◀", 右: "▶" };

const operatorMarkers = computed(() => {
  const result = [];
  for (const lifecycle of props.lifecycles) {
    const state = operatorStateAt(lifecycle, props.playFrame, props.fps);
    if (!state) continue;
    const pos = parseGridPos(state.pos);
    if (!pos || yOf(pos.row) === null) continue;
    result.push({
      oper: lifecycle.oper,
      row: pos.row,
      col: pos.col,
      skillActive: state.skillActive,
      direction: DIR_GLYPHS[state.direction] || "",
    });
  }
  return result;
});

const denseMarkers = computed(() => enemyMarkers.value.length > 14);

function markerStyle(marker) {
  const y = yOf(marker.row);
  return {
    left: `${((marker.col + 0.5) / Math.max(1, cols.value)) * 100}%`,
    top: `${(y / Math.max(0.001, rowLayout.value.total)) * 100}%`,
  };
}

const cells = computed(() => {
  const result = [];
  for (let displayRow = 0; displayRow < rows.value; displayRow += 1) {
    if (gapRowSet.value.has(displayRow)) {
      result.push({ gap: true, row: displayRow, col: -1 });
      continue;
    }
    for (let col = 0; col < cols.value; col += 1) {
      const tile = tileMap.value.get(`${displayRow}:${col}`) || {
        row: displayRow,
        col,
        tileKey: "tile_empty",
        category: "forbidden",
      };
      result.push({
        ...tile,
        devices: deviceMap.value.get(`${displayRow}:${col}`) || [],
        blockEdges: edgeMap.value.get(`${displayRow}:${col}`) || [],
      });
    }
  }
  return result;
});

// 每条路线的寻路折线分段（BFS+视线平滑，复刻游戏 SPFA 路径），随地图/路线缓存。
const routeSegmentsMap = computed(() => {
  const cache = new Map();
  for (const route of props.routes || []) {
    cache.set(Number(route.index), computeRoutePath(route, props.map));
  }
  return cache;
});

function routeSegments(route) {
  return (routeSegmentsMap.value.get(Number(route.index)) || [])
    .map((segment) => ({
      ...segment,
      pointsText: segment.points
        .filter((point) => yCenter(point.row) !== null)
        .map((point) => `${point.col + 0.5},${yCenter(point.row)}`)
        .join(" "),
    }))
    .filter((segment) => segment.pointsText);
}

function tileTitle(tile) {
  const deviceText = tile.devices?.length
    ? `\n预置：${tile.devices.map((item) => item.alias || item.key || item.kind).join("、")}`
    : "";
  return `(${tile.col}, ${tile.row}) ${tile.tileKey || "未知格"}\n${categoryLabels[tile.category] || tile.category}${deviceText}`;
}

const visibleRoutes = computed(() => props.routes.filter(
  (route) => props.visibleRouteIndexes
    ? props.visibleRouteIndexes.has(Number(route.index))
    : !route.isExtra));
</script>

<template>
  <section class="map-panel">
    <div class="panel-heading">
      <div>
        <h2>关卡地图</h2>
        <span>{{ map?.mapId || (rows && cols ? "当前地图" : "未导入地图") }} · {{ rows }}×{{ cols }}</span>
      </div>
      <label>
        格子大小
        <input v-model.number="cellSize" type="range" min="36" max="82" step="2" />
        {{ cellSize }}px
      </label>
    </div>

    <div v-if="rows && cols" class="map-scroll">
      <div
        class="map-grid"
        :style="{
          width: `${cols * cellSize}px`,
          height: `${rowLayout.total * cellSize}px`,
          gridTemplateColumns: `repeat(${cols}, ${cellSize}px)`,
          gridTemplateRows,
        }"
      >
        <template v-for="tile in cells" :key="tile.gap ? `gap-${tile.row}` : `${tile.row}:${tile.col}`">
          <div
            v-if="tile.gap"
            class="map-gap"
            :style="{ gridColumn: '1 / -1' }"
            title="区域间隔带（整行不可通行）"
          ></div>
          <button
            v-else
            type="button"
            class="map-cell"
            :class="[`tile-${tile.category || 'ground'}`, { selected: selectedTile === tile }]"
            :title="tileTitle(tile)"
            @click="selectedTile = tile"
          >
            <span class="cell-coordinate">({{ tile.col }},{{ tile.row }})</span>
            <strong>{{ categorySymbols[tile.category] || "" }}</strong>
            <small v-if="tile.devices?.length">{{ tile.devices.length }}装置</small>
            <i
              v-for="(edge, edgeIndex) in tile.blockEdges"
              :key="`edge-${edgeIndex}`"
              class="blocked-edge"
              :class="`edge-${edge.direction}`"
              title="路线阻断边"
            ></i>
          </button>
        </template>

        <svg
          class="route-layer"
          :viewBox="`0 0 ${cols} ${rowLayout.total}`"
          preserveAspectRatio="none"
          aria-label="敌人路线"
        >
          <g v-for="route in visibleRoutes" :key="`route-${route.index}`">
            <polyline
              v-for="(seg, si) in routeSegments(route)"
              :key="`route-${route.index}-seg-${si}`"
              :points="seg.pointsText"
              fill="none"
              :stroke="routeColor(route.index)"
              stroke-width="0.08"
              stroke-linecap="round"
              stroke-linejoin="round"
              :stroke-dasharray="seg.type === 'teleport' ? '0.2 0.12' : 'none'"
            />
            <circle
              v-if="route.start && yCenter(route.start.row) !== null"
              :cx="route.start.col + 0.5"
              :cy="yCenter(route.start.row)"
              r="0.12"
              :fill="routeColor(route.index)"
            />
          </g>
        </svg>

        <div class="entity-layer" :class="{ dense: denseMarkers }" aria-label="播放位置">
          <div
            v-for="marker in enemyMarkers"
            :key="`enemy-${marker.id}`"
            class="enemy-marker"
            :class="[marker.state, { pinned: marker.pinned }]"
            :style="markerStyle(marker)"
            :title="`${marker.name} · ${marker.state === 'waiting' ? '检查点等待' : marker.state === 'hidden' ? '未现形' : '移动中'}`"
          >
            <i :style="{ background: marker.color }"></i>
            <span>{{ marker.name }}</span>
          </div>
          <div
            v-for="marker in operatorMarkers"
            :key="`oper-${marker.oper}`"
            class="operator-marker"
            :class="{ skill: marker.skillActive }"
            :style="markerStyle(marker)"
            :title="`${marker.oper}${marker.skillActive ? ' · 技能开启' : ''}`"
          >
            <span>{{ marker.oper }}</span>
            <b v-if="marker.direction">{{ marker.direction }}</b>
          </div>
        </div>
      </div>
    </div>
    <div v-else class="empty-state">请导入后端导出的“关卡/出怪 JSON”。</div>

    <div class="map-footer">
      <div class="legend">
        <span v-for="(label, key) in categoryLabels" :key="key">
          <i :class="`tile-${key}`"></i>{{ label }}
        </span>
      </div>
      <div v-if="selectedTile" class="tile-detail">
        <strong>({{ selectedTile.col }},{{ selectedTile.row }})</strong>
        <code>{{ selectedTile.tileKey }}</code>
        <span>{{ categoryLabels[selectedTile.category] || selectedTile.category }}</span>
        <span v-if="selectedTile.devices?.length">
          {{ selectedTile.devices.map((item) => item.alias || item.key || item.kind).join("、") }}
        </span>
      </div>
    </div>
  </section>
</template>

<style scoped>
.map-panel {
  border: 1px solid #313a49;
  border-radius: 12px;
  background: #171b22;
  padding: 14px;
}
.panel-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}
.panel-heading h2 { margin: 0 0 4px; font-size: 18px; }
.panel-heading span, .panel-heading label { color: #aab5c5; font-size: 13px; }
.panel-heading label { display: flex; align-items: center; gap: 8px; }
.map-scroll { overflow: auto; padding: 8px; background: #0d1015; border-radius: 9px; }
.map-grid { position: relative; display: grid; isolation: isolate; }
.map-cell {
  position: relative;
  z-index: 1;
  border: 1px solid #111722;
  border-radius: 0;
  color: #f6f8fc;
  padding: 2px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-width: 0;
  cursor: pointer;
}
.map-cell.selected { outline: 3px solid #fff; outline-offset: -3px; z-index: 3; }
.map-gap {
  background: repeating-linear-gradient(135deg, #10141b 0 6px, #171e28 6px 12px);
  border-top: 1px dashed #2b3547;
  border-bottom: 1px dashed #2b3547;
}
.cell-coordinate { position: absolute; left: 3px; top: 2px; font: 9px Consolas, monospace; opacity: .68; }
.map-cell strong { font-size: 16px; text-shadow: 0 1px 2px #000; }
.map-cell small { font-size: 9px; }
.blocked-edge { position: absolute; z-index: 4; background: #ffdd75; box-shadow: 0 0 3px #000; }
.blocked-edge.edge-0 { left: 2px; right: 2px; top: 1px; height: 3px; }
.blocked-edge.edge-1 { top: 2px; bottom: 2px; right: 1px; width: 3px; }
.blocked-edge.edge-2 { left: 2px; right: 2px; bottom: 1px; height: 3px; }
.blocked-edge.edge-3 { top: 2px; bottom: 2px; left: 1px; width: 3px; }
.tile-ground { background: #4c5664; }
.tile-highland { background: #7b6a57; }
.tile-forbidden { background: #242a33; color: #8792a3; }
.tile-obstacle { background: #5e4650; }
.tile-enemy_spawn { background: #a83d49; }
.tile-friendly_goal { background: #2767ba; }
.tile-teleport_in { background: #7d4fb8; }
.tile-teleport_out { background: #a56ac9; }
.tile-hole { background: #080a0e; }
.tile-device { background: #b27822; }
.route-layer { position: absolute; inset: 0; width: 100%; height: 100%; z-index: 2; pointer-events: none; }
.entity-layer { position: absolute; inset: 0; z-index: 5; pointer-events: none; }
.enemy-marker { position: absolute; transform: translate(-50%, -50%); display: flex; align-items: center; gap: 3px; }
.enemy-marker i { width: 10px; height: 10px; border-radius: 50%; border: 2px solid #fff; box-shadow: 0 0 5px #000; flex: 0 0 auto; }
.enemy-marker.waiting i { animation: pulse 1s infinite; }
.enemy-marker.hidden { opacity: .45; }
.enemy-marker.hidden i { border-style: dashed; }
.enemy-marker span { font-size: 9px; color: #fff; text-shadow: 0 1px 2px #000, 0 0 3px #000; white-space: nowrap; }
.entity-layer.dense .enemy-marker span { display: none; }
/* 敌方列表中选中的敌人即使密集模式也保留名称，并置顶显示 */
.entity-layer.dense .enemy-marker.pinned span { display: block; }
.enemy-marker.pinned { z-index: 6; }
.enemy-marker.pinned i { border-color: #ffe58a; }
.operator-marker { position: absolute; transform: translate(-50%, -50%); display: flex; align-items: center; gap: 2px; background: #1f6fdd; border: 2px solid #bcd9ff; border-radius: 6px; padding: 1px 5px; box-shadow: 0 0 6px #000; }
.operator-marker span { font-size: 10px; font-weight: 700; color: #fff; white-space: nowrap; }
.operator-marker b { font-size: 9px; color: #cfe6ff; }
.operator-marker.skill { background: #d97a1f; border-color: #ffe1b0; animation: pulse .6s infinite; }
@keyframes pulse { 50% { opacity: .45; } }
.empty-state { padding: 56px 20px; text-align: center; color: #8f9aac; background: #0d1015; border-radius: 9px; }
.map-footer { display: flex; gap: 16px; justify-content: space-between; align-items: flex-start; margin-top: 12px; flex-wrap: wrap; }
.legend { display: flex; flex-wrap: wrap; gap: 8px 14px; color: #aab5c5; font-size: 12px; }
.legend span { display: inline-flex; align-items: center; gap: 5px; }
.legend i { width: 13px; height: 13px; border-radius: 2px; display: inline-block; }
.tile-detail { display: flex; gap: 9px; align-items: center; flex-wrap: wrap; font-size: 12px; color: #c9d3e2; }
.tile-detail code { color: #ffd166; }
</style>
