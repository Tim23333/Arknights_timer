<script setup>
import { computed, ref, watch } from "vue";
import { buildOperatorLifecycles } from "../strategy";

const props = defineProps({
  groups: { type: Object, required: true },
  fps: { type: Number, default: 30 },
  pxPerSecond: { type: Number, default: 12 },
  durationFrames: { type: Number, default: 7200 },
  selectedActionId: { type: String, default: "" },
  playFrame: { type: Number, default: 0 },
  playing: { type: Boolean, default: false },
});
const emit = defineEmits(["add-oper", "remove-oper", "rename-oper", "add-action", "select-action", "seek"]);

const CATEGORY_META = {
  deploy: { label: "部署", color: "#53b7ff" },
  skill: { label: "技能", color: "#ffcc5c" },
  withdraw: { label: "撤退", color: "#ff7a87" },
};
const CATEGORY_ORDER = ["deploy", "skill", "withdraw"];

const metaWidth = 250;
const scrollRef = ref(null);
const contentWidth = computed(() => Math.max(900, Math.ceil(props.durationFrames / props.fps * props.pxPerSecond) + 80));
const tickStepSeconds = computed(() => {
  const candidates = [1, 2, 5, 10, 15, 30, 60, 120, 300];
  return candidates.find((value) => value * props.pxPerSecond >= 72) || 600;
});
const ticks = computed(() => {
  const result = [];
  const maxSeconds = props.durationFrames / props.fps;
  for (let seconds = 0; seconds <= maxSeconds + tickStepSeconds.value; seconds += tickStepSeconds.value) {
    result.push({ seconds, left: seconds * props.pxPerSecond });
  }
  return result;
});

const playheadX = computed(() => props.playFrame / props.fps * props.pxPerSecond);

watch(() => props.playFrame, () => {
  if (!props.playing) return;
  const el = scrollRef.value;
  if (!el) return;
  const x = metaWidth + playheadX.value;
  if (x < el.scrollLeft + metaWidth + 40 || x > el.scrollLeft + el.clientWidth - 120) {
    el.scrollLeft = Math.max(0, x - el.clientWidth * 0.25);
  }
});

// 干员生命周期：部署→撤退 配对成在场区间
const lifecycles = computed(() => {
  const map = new Map();
  for (const lifecycle of buildOperatorLifecycles(props.groups)) map.set(lifecycle.oper, lifecycle);
  return map;
});

// 合并视图：一个干员一行，汇聚其 部署/技能/撤退 全部动作（底层数据仍按三类分组存储）
const mergedRows = computed(() => {
  const order = [];
  const byOper = new Map();
  for (const category of CATEGORY_ORDER) {
    for (const row of props.groups[category] || []) {
      let entry = byOper.get(row.oper);
      if (!entry) {
        entry = { oper: row.oper, actions: [] };
        byOper.set(row.oper, entry);
        order.push(entry);
      }
      for (const action of row.actions || []) {
        entry.actions.push({ category, rowId: row.id, action });
      }
    }
  }
  const frameOf = (item) => {
    const frame = Number(item.action.frame);
    return Number.isFinite(frame) ? frame : Infinity;
  };
  for (const entry of order) entry.actions.sort((a, b) => frameOf(a) - frameOf(b));
  return order;
});

function intervalsOf(oper) {
  return lifecycles.value.get(oper)?.intervals || [];
}

function intervalStyle(interval) {
  const start = interval.start / props.fps * props.pxPerSecond;
  const endFrame = interval.end ?? props.durationFrames;
  return {
    left: `${start}px`,
    width: `${Math.max(6, (endFrame - interval.start) / props.fps * props.pxPerSecond)}px`,
  };
}

function actionLeft(action) {
  return Math.max(0, Number(action.frame) || 0) / props.fps * props.pxPerSecond;
}

function isTimedAction(action) {
  return action.frame !== null && action.frame !== "" && Number.isFinite(Number(action.frame));
}

// 双击轨道：在该时刻添加技能（部署/撤退用行首按钮按播放头位置添加）
function onTrackDoubleClick(row, event) {
  const rect = event.currentTarget.getBoundingClientRect();
  const frame = Math.max(0, Math.round((event.clientX - rect.left) / props.pxPerSecond * props.fps));
  emit("add-action", "skill", row.oper, frame);
}

function addAtPlayhead(category, oper) {
  emit("add-action", category, oper, Math.max(0, Math.round(props.playFrame)));
}

// PR 式播放头：点击/拖动标尺或轨道空白区跳转当前时刻
function onSeekPointerDown(event) {
  if (event.target.closest(".action-marker")) return;
  const rect = event.currentTarget.getBoundingClientRect();
  const frameFromX = (clientX) => Math.max(
    0, Math.round(Math.max(0, clientX - rect.left) / props.pxPerSecond * props.fps));
  emit("seek", frameFromX(event.clientX));
  const move = (moveEvent) => emit("seek", frameFromX(moveEvent.clientX));
  const up = () => {
    window.removeEventListener("pointermove", move);
    window.removeEventListener("pointerup", up);
  };
  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", up);
}
</script>

<template>
  <section class="operator-panel">
    <div class="panel-heading">
      <div>
        <h2>我方操作时间轴</h2>
        <span>一行 = 一个干员：蓝方块 部署 → 黄菱形 技能 → 红方块 撤退；区间条 = 在场时间；双击轨道在该时刻添加技能</span>
      </div>
      <button type="button" class="add-oper" @click="emit('add-oper')">+ 添加干员行</button>
    </div>

    <div class="timeline-scroll" ref="scrollRef">
      <div class="scroll-inner" :style="{ width: `${metaWidth + contentWidth}px` }">
        <div class="playhead" :style="{ left: `${metaWidth + playheadX}px` }"></div>
        <div class="ruler-row">
          <strong :style="{ width: `${metaWidth}px` }">干员</strong>
          <div class="ruler" :style="{ width: `${contentWidth}px` }" @pointerdown="onSeekPointerDown">
            <div v-for="tick in ticks" :key="tick.seconds" class="tick" :style="{ left: `${tick.left}px` }">
              <span>{{ tick.seconds }}s</span>
            </div>
          </div>
        </div>

        <div v-for="row in mergedRows" :key="row.oper" class="operator-row">
          <div class="row-meta" :style="{ width: `${metaWidth}px` }">
            <input
              :value="row.oper"
              placeholder="干员名"
              @change="emit('rename-oper', row.oper, $event.target.value)"
            />
            <span class="row-tools">
              <button
                v-for="category in CATEGORY_ORDER"
                :key="category"
                type="button"
                :style="{ color: CATEGORY_META[category].color }"
                :title="`在当前播放头 F${Math.round(playFrame)} 添加${CATEGORY_META[category].label}`"
                @click="addAtPlayhead(category, row.oper)"
              >{{ CATEGORY_META[category].label[0] }}</button>
            </span>
            <button type="button" class="row-del" title="删除该干员全部操作" @click="emit('remove-oper', row.oper)">×</button>
          </div>
          <div
            class="action-track"
            :style="{ width: `${contentWidth}px` }"
            title="双击在该时刻添加技能；行首按钮按播放头位置添加部署/技能/撤退；单击/拖动空白跳转播放时刻"
            @dblclick="onTrackDoubleClick(row, $event)"
            @pointerdown="onSeekPointerDown"
          >
            <div v-for="tick in ticks" :key="tick.seconds" class="grid-line" :style="{ left: `${tick.left}px` }"></div>
            <i
              v-for="(interval, intervalIndex) in intervalsOf(row.oper)"
              :key="`interval-${intervalIndex}`"
              class="interval-bar"
              :class="{ open: interval.end === null }"
              :style="intervalStyle(interval)"
              :title="`在场 F${interval.start} → ${interval.end === null ? '未撤退' : `F${interval.end}`}`"
            ></i>
            <button
              v-for="item in row.actions.filter((entry) => isTimedAction(entry.action))"
              :key="item.action.id"
              type="button"
              class="action-marker"
              :class="[{ selected: item.action.id === selectedActionId }, `action-${item.category}`]"
              :style="{ left: `${actionLeft(item.action)}px`, background: CATEGORY_META[item.category].color }"
              :title="`${CATEGORY_META[item.category].label} · ${row.oper} · F${item.action.frame}${item.action.pos ? ` · ${item.action.pos}` : ''}`"
              @click.stop="emit('select-action', item.category, item.rowId, item.action.id)"
            >
              <span>{{ CATEGORY_META[item.category].label }}</span>
              <small>F{{ item.action.frame }}</small>
            </button>
            <button
              v-for="(item, pendingIndex) in row.actions.filter((entry) => !isTimedAction(entry.action))"
              :key="item.action.id"
              type="button"
              class="action-marker undated"
              :class="{ selected: item.action.id === selectedActionId }"
              :style="{ left: `${8 + pendingIndex * 45}px` }"
              :title="`${CATEGORY_META[item.category].label} · 原始记录缺少帧；点击后可补填，也可保持为空导出`"
              @click.stop="emit('select-action', item.category, item.rowId, item.action.id)"
            >
              <span>{{ CATEGORY_META[item.category].label }}</span>
              <small>帧空</small>
            </button>
          </div>
        </div>

        <div v-if="!mergedRows.length" class="category-empty">
          尚无干员行，点击右上角「+ 添加干员行」，或双击轨道快速开始。
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.operator-panel { border: 1px solid #313a49; border-radius: 12px; background: #171b22; padding: 14px; }
.panel-heading { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 12px; }
.panel-heading h2 { margin: 0 0 4px; font-size: 18px; }
.panel-heading span { color: #aab5c5; font-size: 13px; }
.add-oper { background: #303b4c; color: #eef4ff; border: 1px solid #46566d; border-radius: 5px; padding: 5px 12px; cursor: pointer; white-space: nowrap; }
.timeline-scroll { overflow-x: auto; border: 1px solid #2b3442; border-radius: 8px; background: #0d1015; }
.scroll-inner { position: relative; }
.playhead { position: absolute; top: 0; bottom: 0; width: 2px; background: #ff5252; box-shadow: 0 0 6px #ff5252aa; z-index: 7; pointer-events: none; }
.ruler-row { position: sticky; top: 0; z-index: 6; display: flex; height: 30px; background: #161c24; border-bottom: 1px solid #374253; }
.ruler-row > strong { box-sizing: border-box; padding: 7px 10px; font-size: 11px; color: #aab5c5; flex: 0 0 auto; }
.ruler { position: relative; height: 100%; flex: 0 0 auto; }
.tick { position: absolute; top: 0; bottom: 0; border-left: 1px solid #3a4658; }
.tick span { position: absolute; left: 4px; top: 7px; color: #8f9bad; font: 10px Consolas, monospace; }
.operator-row { display: flex; height: 47px; border-top: 1px solid #242c37; }
.row-meta { flex: 0 0 auto; box-sizing: border-box; padding: 7px 8px; display: flex; align-items: center; gap: 6px; background: #141920; border-right: 1px solid #323c4a; position: sticky; left: 0; z-index: 5; }
.row-meta input { min-width: 0; flex: 1; width: 96px; background: #0b0e13; color: #f3f7fc; border: 1px solid #354153; border-radius: 5px; padding: 5px 7px; }
.row-tools { display: flex; gap: 3px; flex: 0 0 auto; }
.row-tools button { width: 22px; height: 22px; border: 1px solid #354153; border-radius: 4px; background: #0b0e13; font-size: 11px; font-weight: 700; cursor: pointer; padding: 0; }
.row-tools button:hover { background: #1a2230; }
.row-del { width: 25px; height: 25px; border: 0; border-radius: 5px; background: #7c303a; color: white; cursor: pointer; flex: 0 0 auto; }
.action-track { position: relative; flex: 0 0 auto; background: #11161d; cursor: crosshair; }
.grid-line { position: absolute; top: 0; bottom: 0; border-left: 1px solid #293341; pointer-events: none; }
.interval-bar { position: absolute; top: 38px; height: 5px; border-radius: 3px; background: linear-gradient(90deg, #53b7ffcc, #53b7ff55); pointer-events: none; }
.interval-bar.open { background: repeating-linear-gradient(90deg, #53b7ff88 0 8px, #53b7ff33 8px 16px); }
.action-marker { position: absolute; top: 6px; height: 34px; min-width: 38px; transform: translateX(-7px); border: 0; border-radius: 5px; color: #10151c; padding: 2px 5px; cursor: pointer; display: flex; flex-direction: column; align-items: center; justify-content: center; box-shadow: 0 2px 5px #0009; z-index: 2; }
.action-marker.action-skill { border-radius: 5px 14px; }
.action-marker.action-withdraw { border-radius: 14px 5px; }
.action-marker span { font-size: 10px; font-weight: 800; }
.action-marker small { font: 9px Consolas, monospace; }
.action-marker.selected { outline: 2px solid #fff; outline-offset: 1px; z-index: 4; }
.action-marker.undated { background: #697488; color: #fff; border: 1px dashed #dce5f2; }
.category-empty { color: #738096; padding: 10px 14px; font-size: 12px; background: #11161d; }
</style>
