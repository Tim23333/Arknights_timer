<script setup>
import { computed } from "vue";

const props = defineProps({
  groups: { type: Object, required: true },
  fps: { type: Number, default: 60 },
  pxPerSecond: { type: Number, default: 12 },
  durationFrames: { type: Number, default: 7200 },
  selectedActionId: { type: String, default: "" },
});
const emit = defineEmits(["add-row", "remove-row", "rename-row", "add-action", "select-action"]);

const categories = [
  { key: "deploy", label: "部署", hint: "双击时间轴添加部署点", color: "#53b7ff" },
  { key: "skill", label: "技能", hint: "同一干员可添加多个技能点", color: "#ffcc5c" },
  { key: "withdraw", label: "撤退", hint: "记录撤退/离场时机", color: "#ff7a87" },
];
const metaWidth = 214;
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

function actionLeft(action) {
  return Math.max(0, Number(action.frame) || 0) / props.fps * props.pxPerSecond;
}

function isTimedAction(action) {
  return action.frame !== null && action.frame !== "" && Number.isFinite(Number(action.frame));
}

function onTrackDoubleClick(category, row, event) {
  const rect = event.currentTarget.getBoundingClientRect();
  const frame = Math.max(0, Math.round((event.clientX - rect.left) / props.pxPerSecond * props.fps));
  emit("add-action", category.key, row.id, frame);
}
</script>

<template>
  <section class="operator-panel">
    <div class="panel-heading">
      <div>
        <h2>我方操作时间轴</h2>
        <span>部署 / 技能 / 撤退三类独立分组，每类可添加任意干员行</span>
      </div>
    </div>

    <div class="timeline-scroll">
      <div class="ruler-row" :style="{ width: `${metaWidth + contentWidth}px` }">
        <strong :style="{ width: `${metaWidth}px` }">操作分类 / 干员</strong>
        <div class="ruler" :style="{ width: `${contentWidth}px` }">
          <div v-for="tick in ticks" :key="tick.seconds" class="tick" :style="{ left: `${tick.left}px` }">
            <span>{{ tick.seconds }}s</span>
          </div>
        </div>
      </div>

      <div v-for="category in categories" :key="category.key" class="category">
        <div class="category-header" :style="{ width: `${metaWidth + contentWidth}px`, borderLeftColor: category.color }">
          <strong>{{ category.label }}</strong>
          <span>{{ category.hint }}</span>
          <button type="button" @click="emit('add-row', category.key)">+ 添加{{ category.label }}行</button>
        </div>

        <div
          v-for="row in groups[category.key] || []"
          :key="row.id"
          class="operator-row"
          :style="{ width: `${metaWidth + contentWidth}px` }"
        >
          <div class="row-meta" :style="{ width: `${metaWidth}px` }">
            <span class="category-dot" :style="{ background: category.color }"></span>
            <input
              :value="row.oper"
              :placeholder="`${category.label}干员`"
              @change="emit('rename-row', category.key, row.id, $event.target.value)"
            />
            <button type="button" title="删除本行" @click="emit('remove-row', category.key, row.id)">×</button>
          </div>
          <div
            class="action-track"
            :style="{ width: `${contentWidth}px` }"
            :title="`双击添加${category.label}动作`"
            @dblclick="onTrackDoubleClick(category, row, $event)"
          >
            <div v-for="tick in ticks" :key="tick.seconds" class="grid-line" :style="{ left: `${tick.left}px` }"></div>
            <button
              v-for="action in row.actions.filter(isTimedAction)"
              :key="action.id"
              type="button"
              class="action-marker"
              :class="[{ selected: action.id === selectedActionId }, `action-${category.key}`]"
              :style="{ left: `${actionLeft(action)}px`, background: category.color }"
              :title="`${category.label} · ${row.oper} · F${action.frame}${action.pos ? ` · ${action.pos}` : ''}`"
              @click.stop="emit('select-action', category.key, row.id, action.id)"
            >
              <span>{{ category.label }}</span>
              <small>F{{ action.frame }}</small>
            </button>
            <button
              v-for="(action, pendingIndex) in row.actions.filter((item) => !isTimedAction(item))"
              :key="action.id"
              type="button"
              class="action-marker undated"
              :class="{ selected: action.id === selectedActionId }"
              :style="{ left: `${8 + pendingIndex * 45}px` }"
              title="原始记录缺少帧；点击后可补填，也可保持为空导出"
              @click.stop="emit('select-action', category.key, row.id, action.id)"
            >
              <span>{{ category.label }}</span>
              <small>帧空</small>
            </button>
          </div>
        </div>

        <div v-if="!(groups[category.key] || []).length" class="category-empty">
          尚无{{ category.label }}行，点击右侧按钮添加。
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
.timeline-scroll { overflow-x: auto; border: 1px solid #2b3442; border-radius: 8px; background: #0d1015; }
.ruler-row { position: sticky; top: 0; z-index: 6; display: flex; height: 30px; background: #161c24; border-bottom: 1px solid #374253; }
.ruler-row > strong { box-sizing: border-box; padding: 7px 10px; font-size: 11px; color: #aab5c5; flex: 0 0 auto; }
.ruler { position: relative; height: 100%; flex: 0 0 auto; }
.tick { position: absolute; top: 0; bottom: 0; border-left: 1px solid #3a4658; }
.tick span { position: absolute; left: 4px; top: 7px; color: #8f9bad; font: 10px Consolas, monospace; }
.category { border-bottom: 1px solid #303947; }
.category:last-child { border-bottom: 0; }
.category-header { position: relative; display: flex; align-items: center; gap: 10px; min-height: 36px; box-sizing: border-box; padding: 5px 9px; border-left: 4px solid; background: #1b212b; }
.category-header strong { font-size: 14px; }
.category-header span { color: #8f9bad; font-size: 11px; }
.category-header button { margin-left: auto; position: sticky; right: 8px; background: #303b4c; color: #eef4ff; border: 1px solid #46566d; border-radius: 5px; padding: 4px 8px; cursor: pointer; }
.operator-row { display: flex; height: 47px; border-top: 1px solid #242c37; }
.row-meta { flex: 0 0 auto; box-sizing: border-box; padding: 7px 8px; display: flex; align-items: center; gap: 6px; background: #141920; border-right: 1px solid #323c4a; position: sticky; left: 0; z-index: 5; }
.category-dot { width: 8px; height: 28px; border-radius: 4px; flex: 0 0 auto; }
.row-meta input { min-width: 0; flex: 1; width: 130px; background: #0b0e13; color: #f3f7fc; border: 1px solid #354153; border-radius: 5px; padding: 5px 7px; }
.row-meta button { width: 25px; height: 25px; border: 0; border-radius: 5px; background: #7c303a; color: white; cursor: pointer; }
.action-track { position: relative; flex: 0 0 auto; background: #11161d; cursor: crosshair; }
.grid-line { position: absolute; top: 0; bottom: 0; border-left: 1px solid #293341; pointer-events: none; }
.action-marker { position: absolute; top: 6px; height: 34px; min-width: 38px; transform: translateX(-7px); border: 0; border-radius: 5px; color: #10151c; padding: 2px 5px; cursor: pointer; display: flex; flex-direction: column; align-items: center; justify-content: center; box-shadow: 0 2px 5px #0009; }
.action-marker span { font-size: 10px; font-weight: 800; }
.action-marker small { font: 9px Consolas, monospace; }
.action-marker.selected { outline: 2px solid #fff; outline-offset: 1px; z-index: 4; }
.action-marker.undated { background: #697488; color: #fff; border: 1px dashed #dce5f2; }
.category-empty { color: #738096; padding: 10px 14px; font-size: 12px; background: #11161d; }
</style>
