<script setup>
import { computed, ref, watch } from "vue";
import { finiteFrame, routeColor } from "../strategy";

const props = defineProps({
  enemies: { type: Array, default: () => [] },
  journeys: { type: Map, default: () => new Map() },
  fps: { type: Number, default: 30 },
  pxPerSecond: { type: Number, default: 12 },
  durationFrames: { type: Number, default: 7200 },
  selectedId: { type: String, default: "" },
  playFrame: { type: Number, default: 0 },
  playing: { type: Boolean, default: false },
});
const emit = defineEmits(["select", "seek"]);

const laneHeight = 34;
const defaultVisualFrames = computed(() => Math.max(props.fps * 5, Math.round(52 / props.pxPerSecond * props.fps)));
const kindLabels = {
  scheduled: "固定",
  conditional: "条件/随机",
  summoned: "召唤/转阶段",
  dynamic: "动态",
};
const scrollRef = ref(null);

const scheduled = computed(() => props.enemies
  .map((enemy, index) => {
    const journey = props.journeys.get(String(enemy.id)) || null;
    const start = journey ? journey.startFrame : finiteFrame(enemy.startFrame);
    const rawEnd = finiteFrame(enemy.endFrame);
    // endFrame 为 0 或不晚于出生帧时视为未观测到结束
    const actualEnd = start !== null && rawEnd !== null && rawEnd > start ? rawEnd : null;
    const effectiveEnd = actualEnd ?? journey?.arriveFrame ?? null;
    return { ...enemy, _index: index, _start: start, _journey: journey, _actualEnd: actualEnd, _effectiveEnd: effectiveEnd };
  })
  .filter((enemy) => enemy._start !== null)
  .sort((a, b) => a._start - b._start || Number(a.order || 0) - Number(b.order || 0)));

const unresolved = computed(() => props.enemies.filter(
  (enemy) => !props.journeys.get(String(enemy.id)) && finiteFrame(enemy.startFrame) === null));

const packed = computed(() => {
  const laneEnds = [];
  const items = [];
  for (const enemy of scheduled.value) {
    const visualEnd = Math.max(enemy._start + 1,
      enemy._effectiveEnd ?? enemy._start + defaultVisualFrames.value);
    let lane = laneEnds.findIndex((end) => enemy._start >= end + 2);
    if (lane < 0) {
      lane = laneEnds.length;
      laneEnds.push(visualEnd);
    } else {
      laneEnds[lane] = visualEnd;
    }
    items.push({ ...enemy, _lane: lane, _visualEnd: visualEnd });
  }
  return { items, laneCount: Math.max(1, laneEnds.length) };
});

const contentWidth = computed(() => Math.max(900, Math.ceil(props.durationFrames / props.fps * props.pxPerSecond) + 80));
const tickStepSeconds = computed(() => {
  const candidates = [1, 2, 5, 10, 15, 30, 60, 120, 300];
  return candidates.find((value) => value * props.pxPerSecond >= 72) || 600;
});
const ticks = computed(() => {
  const maxSeconds = props.durationFrames / props.fps;
  const result = [];
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
  const x = playheadX.value;
  if (x < el.scrollLeft + 40 || x > el.scrollLeft + el.clientWidth - 120) {
    el.scrollLeft = Math.max(0, x - el.clientWidth * 0.25);
  }
});

function itemStyle(enemy) {
  return {
    left: `${enemy._start / props.fps * props.pxPerSecond}px`,
    top: `${enemy._lane * laneHeight + 6}px`,
    width: `${Math.max(30, (enemy._visualEnd - enemy._start) / props.fps * props.pxPerSecond)}px`,
    borderColor: routeColor(enemy.routeIndex),
  };
}

/** 行程分段：未现形灰段 + 按 走/等/闪现 的真实耗时占比填色，闪现画成白色竖线。 */
function segmentsOf(enemy) {
  const journey = enemy._journey;
  if (!journey || !journey.legs.length) return [];
  const spanSeconds = (enemy._visualEnd - journey.startFrame) / props.fps;
  if (spanSeconds <= 0) return [];
  const segments = [];
  let elapsed = 0;
  if (journey.bornDelay > 0) {
    segments.push({ type: "hidden", left: 0, width: (journey.bornDelay / spanSeconds) * 100 });
    elapsed += journey.bornDelay;
  }
  for (const leg of journey.legs) {
    if (leg.type === "teleport") {
      segments.push({ type: "teleport", left: (elapsed / spanSeconds) * 100, width: 0 });
      continue;
    }
    const duration = leg.type === "wait" ? leg.seconds : leg.dist / journey.speed;
    segments.push({ type: leg.type, left: (elapsed / spanSeconds) * 100, width: (duration / spanSeconds) * 100 });
    elapsed += duration;
  }
  return segments;
}

// PR 式播放头：点击/拖动时间轴空白区跳转当前时刻
function onSeekPointerDown(event) {
  if (event.target.closest(".enemy-block")) return;
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

function blockTitle(enemy) {
  const lines = [enemy.name || enemy.enemyId, `出生 F${enemy._start}`];
  if (enemy._journey?.arriveFrame != null) lines.push(`到达蓝门 F${enemy._journey.arriveFrame}（按移速 ${enemy._journey.speed} 估）`);
  if (enemy._actualEnd !== null) lines.push(`实测结束 F${enemy._actualEnd}${enemy.endReason ? ` · ${enemy.endReason}` : ""}`);
  lines.push(kindLabels[enemy.kind] || enemy.kind || "");
  if (enemy.condition) lines.push(enemy.condition);
  return lines.filter(Boolean).join("\n");
}
</script>

<template>
  <section class="enemy-panel">
    <div class="panel-heading">
      <div>
        <h2>敌方出怪时间轴</h2>
        <span>块 = 出生 → 按移速行进/等待/闪现 → 蓝门；颜色与地图路线一致</span>
      </div>
      <div class="kind-legend">
        <span><i class="leg-hidden"></i>未现形</span>
        <span><i class="leg-move"></i>移动</span>
        <span><i class="leg-wait"></i>检查点等待</span>
        <span><i class="leg-teleport"></i>闪现/传送</span>
        <span v-for="(label, key) in kindLabels" :key="key"><em :class="`kind-${key}`">{{ label }}</em></span>
      </div>
    </div>

    <div v-if="scheduled.length" class="timeline-scroll" ref="scrollRef">
      <div class="timeline-content" :style="{ width: `${contentWidth}px`, height: `${packed.laneCount * laneHeight + 34}px` }" @pointerdown="onSeekPointerDown">
        <div v-for="tick in ticks" :key="tick.seconds" class="tick" :style="{ left: `${tick.left}px` }">
          <span>{{ tick.seconds }}s</span>
        </div>
        <div class="playhead" :style="{ left: `${playheadX}px` }"></div>
        <button
          v-for="enemy in packed.items"
          :key="enemy.id"
          type="button"
          class="enemy-block"
          :class="[
            `kind-${enemy.kind || 'dynamic'}`,
            { selected: String(enemy.id) === selectedId, estimated: enemy._actualEnd === null },
          ]"
          :style="itemStyle(enemy)"
          :title="blockTitle(enemy)"
          @click="emit('select', enemy.id)"
        >
          <span class="journey-layer">
            <i
              v-for="(segment, segmentIndex) in segmentsOf(enemy)"
              :key="segmentIndex"
              class="journey-segment"
              :class="`leg-${segment.type}`"
              :style="{ left: `${segment.left}%`, width: segment.type === 'teleport' ? '2px' : `${segment.width}%` }"
            ></i>
          </span>
          <span class="enemy-name">{{ enemy.name || enemy.enemyId || "未知敌人" }}</span>
          <span v-if="enemy.randomSpawnGroup" class="enemy-tag">随机</span>
          <span v-else-if="enemy.kind !== 'scheduled'" class="enemy-tag">{{ kindLabels[enemy.kind] || enemy.kind }}</span>
        </button>
      </div>
    </div>
    <div v-else class="empty-state">当前文件没有可定位到时间点的敌人。</div>

    <div v-if="unresolved.length" class="pending-zone">
      <strong>待触发区（无可靠绝对时间，不伪造帧）</strong>
      <button
        v-for="enemy in unresolved"
        :key="enemy.id"
        type="button"
        :class="[`kind-${enemy.kind || 'conditional'}`, { selected: String(enemy.id) === selectedId }]"
        :title="enemy.condition"
        @click="emit('select', enemy.id)"
      >
        {{ enemy.name || enemy.enemyId }}
        <small>{{ enemy.condition || kindLabels[enemy.kind] }}</small>
      </button>
    </div>
  </section>
</template>

<style scoped>
.enemy-panel { border: 1px solid #313a49; border-radius: 12px; background: #171b22; padding: 14px; }
.panel-heading { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 12px; flex-wrap: wrap; }
.panel-heading h2 { margin: 0 0 4px; font-size: 18px; }
.panel-heading > div > span { color: #aab5c5; font-size: 13px; }
.kind-legend { display: flex; gap: 12px; flex-wrap: wrap; font-size: 12px; color: #b8c3d3; align-items: center; }
.kind-legend span { display: inline-flex; align-items: center; gap: 5px; }
.kind-legend i { width: 14px; height: 10px; border-radius: 2px; display: inline-block; }
.kind-legend .leg-move { background: #66c2ff; }
.kind-legend .leg-hidden { background: #8b93a5; }
.kind-legend .leg-wait { background: repeating-linear-gradient(135deg, #4a5468 0 3px, #2c3442 3px 6px); }
.kind-legend .leg-teleport { width: 3px; background: #fff; }
.kind-legend em { font-style: normal; padding: 1px 5px; border-radius: 3px; color: #081018; font-size: 10px; }
.kind-legend .kind-scheduled { background: #66c2ff; }
.kind-legend .kind-conditional { background: #ffd166; }
.kind-legend .kind-summoned { background: #c89bff; }
.kind-legend .kind-dynamic { background: #70e1a1; }
.timeline-scroll { overflow-x: auto; overflow-y: hidden; background: #0d1015; border-radius: 8px; border: 1px solid #28303d; }
.timeline-content { position: relative; min-height: 60px; background: repeating-linear-gradient(to bottom, #151a21 0, #151a21 33px, #11161c 33px, #11161c 34px); }
.tick { position: absolute; top: 0; bottom: 0; border-left: 1px solid #344052; pointer-events: none; }
.tick span { position: absolute; top: 2px; left: 4px; color: #8794a7; font: 10px Consolas, monospace; }
.playhead { position: absolute; top: 0; bottom: 0; width: 2px; background: #ff5252; box-shadow: 0 0 6px #ff5252aa; z-index: 4; pointer-events: none; }
.enemy-block { position: absolute; height: 26px; border: 1px solid; border-radius: 5px; background: #202a38; color: #f2f7ff; padding: 0 6px; display: flex; align-items: center; gap: 4px; overflow: hidden; cursor: pointer; box-shadow: 0 2px 5px #0008; }
.enemy-block.estimated { border-right-style: dashed; }
.enemy-block.selected, .pending-zone button.selected { outline: 2px solid #fff; outline-offset: 1px; z-index: 3; }
.journey-layer { position: absolute; inset: 0; pointer-events: none; }
.journey-segment { position: absolute; top: 0; bottom: 0; }
.journey-segment.leg-move { background: #66c2ff2e; }
.journey-segment.leg-hidden { background: #8b93a545; }
.journey-segment.leg-wait { background: repeating-linear-gradient(135deg, #ffd16638 0 4px, #0000 4px 8px); }
.journey-segment.leg-teleport { background: #fff; box-shadow: 0 0 4px #fff; }
.enemy-name { position: relative; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 11px; font-weight: 700; text-shadow: 0 1px 2px #000; }
.enemy-tag { position: relative; flex: 0 0 auto; padding: 1px 3px; border-radius: 3px; background: #0006; font-size: 9px; }
.pending-zone { margin-top: 10px; display: flex; gap: 7px; align-items: center; flex-wrap: wrap; }
.pending-zone > strong { color: #d1d9e5; font-size: 12px; margin-right: 4px; }
.pending-zone button { border: 0; border-radius: 6px; color: #10151c; padding: 5px 8px; cursor: pointer; display: flex; gap: 8px; align-items: center; }
.pending-zone .kind-scheduled { background: #66c2ff; }
.pending-zone .kind-conditional { background: #ffd166; }
.pending-zone .kind-summoned { background: #c89bff; }
.pending-zone .kind-dynamic { background: #70e1a1; }
.pending-zone small { opacity: .75; max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.empty-state { color: #8f9aac; text-align: center; padding: 35px; background: #0d1015; border-radius: 8px; }
</style>
