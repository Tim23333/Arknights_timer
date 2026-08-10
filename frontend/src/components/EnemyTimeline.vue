<script setup>
import { computed } from "vue";

const props = defineProps({
  enemies: { type: Array, default: () => [] },
  fps: { type: Number, default: 60 },
  pxPerSecond: { type: Number, default: 12 },
  durationFrames: { type: Number, default: 7200 },
  selectedId: { type: String, default: "" },
});
const emit = defineEmits(["select"]);

const laneHeight = 31;
const defaultVisualFrames = computed(() => Math.max(props.fps * 5, Math.round(52 / props.pxPerSecond * props.fps)));
const kindLabels = {
  scheduled: "固定",
  conditional: "条件/随机",
  summoned: "召唤/转阶段",
  dynamic: "动态",
};

function finiteFrame(value) {
  const number = Number(value);
  return Number.isFinite(number) && number >= 0 ? Math.round(number) : null;
}

const scheduled = computed(() => props.enemies
  .map((enemy, index) => ({ ...enemy, _index: index, _start: finiteFrame(enemy.startFrame) }))
  .filter((enemy) => enemy._start !== null)
  .sort((a, b) => a._start - b._start || Number(a.order || 0) - Number(b.order || 0)));

const unresolved = computed(() => props.enemies.filter((enemy) => finiteFrame(enemy.startFrame) === null));

const packed = computed(() => {
  const laneEnds = [];
  const items = [];
  for (const enemy of scheduled.value) {
    const actualEnd = finiteFrame(enemy.endFrame);
    const visualEnd = Math.max(enemy._start + 1, actualEnd ?? enemy._start + defaultVisualFrames.value);
    let lane = laneEnds.findIndex((end) => enemy._start >= end + 2);
    if (lane < 0) {
      lane = laneEnds.length;
      laneEnds.push(visualEnd);
    } else {
      laneEnds[lane] = visualEnd;
    }
    items.push({ ...enemy, _lane: lane, _visualEnd: visualEnd, _actualEnd: actualEnd });
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

function itemStyle(enemy) {
  return {
    left: `${enemy._start / props.fps * props.pxPerSecond}px`,
    top: `${enemy._lane * laneHeight + 5}px`,
    width: `${Math.max(28, (enemy._visualEnd - enemy._start) / props.fps * props.pxPerSecond)}px`,
  };
}

function blockTitle(enemy) {
  const end = enemy._actualEnd === null ? "未观测到死亡/转阶段" : `F${enemy._actualEnd}`;
  return `${enemy.name || enemy.enemyId}\n出生 F${enemy._start} · 结束 ${end}\n${kindLabels[enemy.kind] || enemy.kind}\n${enemy.condition || ""}`;
}
</script>

<template>
  <section class="enemy-panel">
    <div class="panel-heading">
      <div>
        <h2>敌方出怪时间轴</h2>
        <span>{{ enemies.length }} 个出怪项 · {{ packed.laneCount }} 条复用泳道（不是一怪一行）</span>
      </div>
      <div class="kind-legend">
        <span v-for="(label, key) in kindLabels" :key="key"><i :class="`kind-${key}`"></i>{{ label }}</span>
      </div>
    </div>

    <div v-if="scheduled.length" class="timeline-scroll">
      <div class="timeline-content" :style="{ width: `${contentWidth}px`, height: `${packed.laneCount * laneHeight + 30}px` }">
        <div v-for="tick in ticks" :key="tick.seconds" class="tick" :style="{ left: `${tick.left}px` }">
          <span>{{ tick.seconds }}s</span>
        </div>
        <button
          v-for="enemy in packed.items"
          :key="enemy.id"
          type="button"
          class="enemy-block"
          :class="[
            `kind-${enemy.kind || 'dynamic'}`,
            { selected: String(enemy.id) === selectedId, open: enemy._actualEnd === null },
          ]"
          :style="itemStyle(enemy)"
          :title="blockTitle(enemy)"
          @click="emit('select', enemy.id)"
        >
          <span class="enemy-name">{{ enemy.name || enemy.enemyId || "未知敌人" }}</span>
          <span v-if="enemy.randomSpawnGroup" class="enemy-tag">随机</span>
          <span v-else-if="enemy.kind !== 'scheduled'" class="enemy-tag">{{ kindLabels[enemy.kind] || enemy.kind }}</span>
          <b v-if="enemy._actualEnd === null" title="右侧虚线表示结束时间未知">…</b>
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
.kind-legend { display: flex; gap: 12px; flex-wrap: wrap; font-size: 12px; color: #b8c3d3; }
.kind-legend span { display: inline-flex; align-items: center; gap: 5px; }
.kind-legend i { width: 12px; height: 12px; border-radius: 3px; display: inline-block; }
.timeline-scroll { overflow-x: auto; overflow-y: hidden; background: #0d1015; border-radius: 8px; border: 1px solid #28303d; }
.timeline-content { position: relative; min-height: 60px; background: repeating-linear-gradient(to bottom, #151a21 0, #151a21 30px, #11161c 30px, #11161c 31px); }
.tick { position: absolute; top: 0; bottom: 0; border-left: 1px solid #344052; pointer-events: none; }
.tick span { position: absolute; top: 2px; left: 4px; color: #8794a7; font: 10px Consolas, monospace; }
.enemy-block { position: absolute; height: 24px; border: 0; border-radius: 5px; color: #081018; padding: 2px 6px; display: flex; align-items: center; gap: 4px; overflow: hidden; cursor: pointer; box-shadow: 0 2px 5px #0008; }
.enemy-block.open { border-right: 2px dashed #fff; }
.enemy-block.selected, .pending-zone button.selected { outline: 2px solid #fff; outline-offset: 1px; z-index: 3; }
.enemy-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 11px; font-weight: 700; }
.enemy-tag { flex: 0 0 auto; padding: 1px 3px; border-radius: 3px; background: #0004; font-size: 9px; }
.enemy-block b { margin-left: auto; }
.kind-scheduled { background: #66c2ff; }
.kind-conditional { background: #ffd166; }
.kind-summoned { background: #c89bff; }
.kind-dynamic { background: #70e1a1; }
.pending-zone { margin-top: 10px; display: flex; gap: 7px; align-items: center; flex-wrap: wrap; }
.pending-zone > strong { color: #d1d9e5; font-size: 12px; margin-right: 4px; }
.pending-zone button { border: 0; border-radius: 6px; color: #10151c; padding: 5px 8px; cursor: pointer; display: flex; gap: 8px; align-items: center; }
.pending-zone small { opacity: .75; max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.empty-state { color: #8f9aac; text-align: center; padding: 35px; background: #0d1015; border-radius: 8px; }
</style>
