<script setup>
import { computed, ref } from "vue";

const props = defineProps({
  map: { type: Object, default: () => ({}) },
  routes: { type: Array, default: () => [] },
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

const cells = computed(() => {
  const result = [];
  for (let displayRow = rows.value - 1; displayRow >= 0; displayRow -= 1) {
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

function routePoints(route) {
  const points = [route.start];
  for (const checkpoint of route.checkpoints || []) {
    if (["MOVE", "PATROL_MOVE", "APPEAR_AT_POS", "MAP_OFFSET_MOVE"].includes(checkpoint.typeName)) {
      points.push(checkpoint.position);
    }
  }
  points.push(route.end);
  return points
    .filter((point) => Number.isFinite(point?.row) && Number.isFinite(point?.col))
    .map((point) => `${point.col + 0.5},${rows.value - point.row - 0.5}`)
    .join(" ");
}

function tileTitle(tile) {
  const deviceText = tile.devices?.length
    ? `\n预置：${tile.devices.map((item) => item.alias || item.key || item.kind).join("、")}`
    : "";
  return `(${tile.row}, ${tile.col}) ${tile.tileKey || "未知格"}\n${categoryLabels[tile.category] || tile.category}${deviceText}`;
}
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
          height: `${rows * cellSize}px`,
          gridTemplateColumns: `repeat(${cols}, ${cellSize}px)`,
          gridTemplateRows: `repeat(${rows}, ${cellSize}px)`,
        }"
      >
        <button
          v-for="tile in cells"
          :key="`${tile.row}:${tile.col}`"
          type="button"
          class="map-cell"
          :class="[`tile-${tile.category || 'ground'}`, { selected: selectedTile === tile }]"
          :title="tileTitle(tile)"
          @click="selectedTile = tile"
        >
          <span class="cell-coordinate">{{ String.fromCharCode(65 + tile.row) }}{{ tile.col + 1 }}</span>
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

        <svg
          class="route-layer"
          :viewBox="`0 0 ${cols} ${rows}`"
          preserveAspectRatio="none"
          aria-label="敌人路线"
        >
          <g v-for="(route, index) in routes.filter((item) => !item.isExtra)" :key="`route-${route.index}`">
            <polyline
              :points="routePoints(route)"
              fill="none"
              :stroke="routeColors[index % routeColors.length]"
              stroke-width="0.08"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
            <circle
              v-if="route.start"
              :cx="route.start.col + 0.5"
              :cy="rows - route.start.row - 0.5"
              r="0.12"
              :fill="routeColors[index % routeColors.length]"
            />
          </g>
        </svg>
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
        <strong>{{ String.fromCharCode(65 + selectedTile.row) }}{{ selectedTile.col + 1 }}</strong>
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
.empty-state { padding: 56px 20px; text-align: center; color: #8f9aac; background: #0d1015; border-radius: 9px; }
.map-footer { display: flex; gap: 16px; justify-content: space-between; align-items: flex-start; margin-top: 12px; flex-wrap: wrap; }
.legend { display: flex; flex-wrap: wrap; gap: 8px 14px; color: #aab5c5; font-size: 12px; }
.legend span { display: inline-flex; align-items: center; gap: 5px; }
.legend i { width: 13px; height: 13px; border-radius: 2px; display: inline-block; }
.tile-detail { display: flex; gap: 9px; align-items: center; flex-wrap: wrap; font-size: 12px; color: #c9d3e2; }
.tile-detail code { color: #ffd166; }
</style>
