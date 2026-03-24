<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
import TimelineRow from "./components/TimelineRow.vue";

const FPS = 60;
/** 游戏内时间：1 秒 = 60 帧，1 小时 = 3600×60 帧 */
const FRAMES_PER_HOUR = 3600 * FPS;
/** 整页最多展示 10 小时；再缩小不再变（避免布局崩坏） */
const MAX_VISIBLE_HOURS = 10;
const MAX_VISIBLE_FRAMES = FRAMES_PER_HOUR * MAX_VISIBLE_HOURS;
/** 最大放大：每帧仍可单独成格（与此前一致） */
const MAX_PX_PER_FRAME = 80;

const TIMELINE_HEIGHT_PER_ROW = 66;
const TIMELINE_HEADER_HEIGHT = 26;
const TRACK_TOP_OFFSET = 15;
const TRACK_HEIGHT = 28;
const DRAG_THRESHOLD = 4;
const SNAP_PIXELS = 12;
const ROW_META_WIDTH = 250;
const ROW_META_GAP = 10;
const ROW_PADDING_X = 8;
const TRACK_X_OFFSET = ROW_PADDING_X + ROW_META_WIDTH + ROW_META_GAP;

const userId = ref("default");
const rows = ref([
  { id: crypto.randomUUID(), name: "干员1", segments: [] },
  { id: crypto.randomUUID(), name: "干员2", segments: [] },
]);
const selectedColor = ref("#ff4d4f");
const selectedKeys = ref([]);

const pxPerFrame = ref(1.8);
const panFrame = ref(0);
const viewportWidth = ref(1200);
const statusText = ref("就绪");
const selectedFrame = ref(0);
const timelineStartValue = ref(0);
const timelineStartUnit = ref("seconds");

/** 播放头：逻辑帧（与区间同一坐标系），默认从 0 起 */
const playheadFrame = ref(0);
/** 播放倍速：1 = 实时 60 帧/秒 */
const playbackSpeed = ref(1);
const isPlaying = ref(false);

const timelineViewport = ref(null);
const hScrollTrackEl = ref(null);
const fileInput = ref(null);
const trackLeftOffset = ref(TRACK_X_OFFSET);

let createRange = null;
let marquee = null;
let panning = null;
let segmentDrag = null;
let ignoreNextSegmentClick = false;
let saveTimer = null;
let resizeObserver = null;
let clipboardData = null;
/** 底部横向滚动条：拖动滑块平移 panFrame */
let draggingHScrollThumb = null;
/** 选中区间左右缘：拉长 / 缩短 */
let segmentResize = null;
let isPasting = false;
/** 播放头（PR 式时间标记）拖拽 */
let playheadDrag = null;
let playbackRafId = null;
let playbackLastTs = 0;
let playbackAccum = 0;
const MAX_UNDO_STEPS = 120;
const undoHistory = [];
const redoHistory = [];

function onBeforeUnload(event) {
  // Most browsers ignore custom text, but setting returnValue still triggers the prompt.
  event.preventDefault();
  event.returnValue = "关闭前请注意导出json进行保存";
  return event.returnValue;
}

function deepClone(value) {
  if (typeof structuredClone === "function") {
    try {
      return structuredClone(value);
    } catch {
      // Vue reactive proxies can fail structuredClone in some runtimes.
    }
  }
  return JSON.parse(JSON.stringify(value));
}

function buildHistorySnapshot() {
  return {
    rows: deepClone(rows.value),
    selectedKeys: [...selectedKeys.value],
    selectedFrame: selectedFrame.value,
    pxPerFrame: pxPerFrame.value,
    panFrame: panFrame.value,
    timelineStartValue: timelineStartValue.value,
    timelineStartUnit: timelineStartUnit.value,
  };
}

function historySignature(snapshot) {
  return JSON.stringify(snapshot);
}

function pushRedoSnapshot(snapshot) {
  const snap = snapshot || buildHistorySnapshot();
  const snapSig = historySignature(snap);
  const last = redoHistory[redoHistory.length - 1];
  if (last?.sig === snapSig) return;
  redoHistory.push({ sig: snapSig, snapshot: snap });
  if (redoHistory.length > MAX_UNDO_STEPS) redoHistory.shift();
}

function pushUndoSnapshot(snapshot, options = {}) {
  const { clearRedo = true } = options;
  const snap = snapshot || buildHistorySnapshot();
  const currentSig = historySignature(buildHistorySnapshot());
  const snapSig = historySignature(snap);
  if (snapSig === currentSig) return;
  const last = undoHistory[undoHistory.length - 1];
  if (last?.sig === snapSig) return;
  undoHistory.push({ sig: snapSig, snapshot: snap });
  if (undoHistory.length > MAX_UNDO_STEPS) undoHistory.shift();
  if (clearRedo) {
    redoHistory.length = 0;
  }
}

function applyHistorySnapshot(snapshot) {
  rows.value = deepClone(snapshot.rows || []);
  selectedKeys.value = Array.isArray(snapshot.selectedKeys) ? [...snapshot.selectedKeys] : [];
  selectedFrame.value = Number.isFinite(snapshot.selectedFrame) ? snapshot.selectedFrame : 0;
  pxPerFrame.value = clampPxPerFrame(Number(snapshot.pxPerFrame) || pxPerFrame.value);
  panFrame.value = Number(snapshot.panFrame) || 0;
  timelineStartUnit.value = snapshot.timelineStartUnit === "frames" ? "frames" : "seconds";
  timelineStartValue.value = Number.isFinite(Number(snapshot.timelineStartValue))
    ? Number(snapshot.timelineStartValue)
    : 0;
  clampPanFrame();
  scheduleSave();
}

function undoLastAction() {
  if (!undoHistory.length) {
    statusText.value = "没有可撤回的操作";
    return;
  }
  const currentSig = historySignature(buildHistorySnapshot());
  let entry = undoHistory.pop();
  while (entry && entry.sig === currentSig && undoHistory.length) {
    entry = undoHistory.pop();
  }
  if (!entry || entry.sig === currentSig) {
    statusText.value = "没有可撤回的操作";
    return;
  }
  pushRedoSnapshot(buildHistorySnapshot());
  applyHistorySnapshot(entry.snapshot);
  statusText.value = `已撤回，剩余 ${undoHistory.length} 步（可重做 ${redoHistory.length} 步）`;
}

function redoLastAction() {
  if (!redoHistory.length) {
    statusText.value = "没有可重做的操作";
    return;
  }
  const currentSig = historySignature(buildHistorySnapshot());
  let entry = redoHistory.pop();
  while (entry && entry.sig === currentSig && redoHistory.length) {
    entry = redoHistory.pop();
  }
  if (!entry || entry.sig === currentSig) {
    statusText.value = "没有可重做的操作";
    return;
  }
  pushUndoSnapshot(buildHistorySnapshot(), { clearRedo: false });
  applyHistorySnapshot(entry.snapshot);
  statusText.value = `已重做，剩余可重做 ${redoHistory.length} 步`;
}

const timelineStartFrames = computed(() => {
  const raw = Number(timelineStartValue.value);
  const safe = Number.isFinite(raw) ? Math.abs(raw) : 0;
  return timelineStartUnit.value === "frames" ? Math.round(safe) : Math.round(safe * FPS);
});
const cursorDisplayFrame = computed(() => selectedFrame.value - timelineStartFrames.value);
const timeAtCursor = computed(() => (cursorDisplayFrame.value / FPS).toFixed(3));
const totalHeight = computed(() =>
  Math.max(240, TIMELINE_HEADER_HEIGHT + rows.value.length * TIMELINE_HEIGHT_PER_ROW),
);
const visibleStart = computed(() => Math.max(0, Math.floor(panFrame.value)));
const visibleEnd = computed(() =>
  Math.max(visibleStart.value, Math.ceil(panFrame.value + viewportWidth.value / pxPerFrame.value)),
);
const selectedCount = computed(() => selectedKeys.value.length);
const singleSelectedSegment = computed(() => {
  if (selectedKeys.value.length !== 1) return null;
  const key = selectedKeys.value[0];
  const colon = key.indexOf(":");
  if (colon < 0) return null;
  const rowId = key.slice(0, colon);
  const segId = key.slice(colon + 1);
  const row = rows.value.find((r) => r.id === rowId);
  if (!row) return null;
  const seg = row.segments.find((s) => s.id === segId);
  if (!seg) return null;
  return { row, seg };
});

/** 最小 px/帧：一屏宽度对应恰好 10 小时（再缩小只会被钳住） */
const minPxPerFrame = computed(() =>
  Math.max(1e-9, viewportWidth.value / MAX_VISIBLE_FRAMES),
);

/** 当前视窗水平方向覆盖的游戏时长（小时），用于提示缩放是否触顶 */
const visibleSpanHours = computed(() => {
  const frames = viewportWidth.value / Math.max(1e-9, pxPerFrame.value);
  return frames / FRAMES_PER_HOUR;
});

/** 放大时显示底部拖动条（比最小缩放更「近」时） */
const showPanScrollbar = computed(() => pxPerFrame.value > minPxPerFrame.value * 1.02);

const visibleFrameSpan = computed(() => viewportWidth.value / Math.max(1e-9, pxPerFrame.value));

const maxSegmentEndFrame = computed(() => {
  let m = 0;
  rows.value.forEach((row) => {
    row.segments.forEach((s) => {
      m = Math.max(m, s.endFrame);
    });
  });
  return m;
});

/** 时间轴逻辑总长度（帧）：数据末尾 + 留白，且不少于当前视窗可滚动需求 */
const scrollContentExtent = computed(() => {
  const vs = visibleFrameSpan.value;
  const pad = Math.max(FRAMES_PER_HOUR / 6, vs * 0.35);
  const fromData = maxSegmentEndFrame.value + pad;
  const fromPan = panFrame.value + vs + pad;
  return Math.max(fromData, fromPan, vs * 2, FRAMES_PER_HOUR);
});

const scrollMaxPan = computed(() =>
  Math.max(0, scrollContentExtent.value - visibleFrameSpan.value),
);

/** 滑块宽度占轨道比例（%），最小 8% 便于抓取 */
const hScrollThumbWidthPct = computed(() => {
  const ce = scrollContentExtent.value;
  const vs = visibleFrameSpan.value;
  if (ce <= 1e-9) return 100;
  const raw = (vs / ce) * 100;
  return Math.min(100, Math.max(8, raw));
});

/** 滑块左偏移（%） */
const hScrollThumbLeftPct = computed(() => {
  const smp = scrollMaxPan.value;
  if (smp <= 1e-9) return 0;
  const w = hScrollThumbWidthPct.value;
  const avail = Math.max(0, 100 - w);
  return (panFrame.value / smp) * avail;
});

const hScrollThumbStyle = computed(() => ({
  width: `${hScrollThumbWidthPct.value}%`,
  left: `${hScrollThumbLeftPct.value}%`,
}));

const marqueeStyle = computed(() => {
  if (!marquee || !marquee.moved) return null;
  const left = Math.min(marquee.startX, marquee.currentX);
  const top = Math.min(marquee.startY, marquee.currentY);
  const width = Math.max(1, Math.abs(marquee.currentX - marquee.startX));
  const height = Math.max(1, Math.abs(marquee.currentY - marquee.startY));
  return { left: `${left}px`, top: `${top}px`, width: `${width}px`, height: `${height}px` };
});

/** 每帧一条竖线；缩放过小则合并步长并限制 DOM 数量，避免卡顿 */
const MAX_GRID_LINES = 1600;
const minorGridStep = computed(() => {
  const span = Math.max(1, visibleEnd.value - visibleStart.value + 2);
  const ppf = pxPerFrame.value;
  const minPpf = minPxPerFrame.value;
  /** 缩到最小附近：一格 = 1 小时（与「整页 10 小时」一致） */
  if (ppf <= minPpf * 1.02) {
    return FRAMES_PER_HOUR;
  }
  let step = 1;
  while (span / step > MAX_GRID_LINES) {
    step *= 2;
    if (step > 1024) break;
  }
  return step;
});

const majorTickStep = computed(() => {
  const ppf = pxPerFrame.value;
  const minPpf = minPxPerFrame.value;
  if (ppf <= minPpf * 1.02) return FRAMES_PER_HOUR;
  if (ppf >= 8) return 10;
  if (ppf >= 3) return 30;
  if (ppf >= 1) return 60;
  if (ppf >= 0.35) return 300;
  if (ppf >= 0.08) return 60 * FPS;
  if (ppf >= 0.02) return 600 * FPS;
  return FRAMES_PER_HOUR;
});

const frameGridLines = computed(() => {
  const step = minorGridStep.value;
  const list = [];
  const start = Math.floor(visibleStart.value / step) * step;
  for (let frame = Math.max(0, start); frame <= visibleEnd.value + step; frame += step) {
    list.push({
      frame,
      leftPx: Math.round(frameToX(frame)),
      major: frame % majorTickStep.value === 0,
    });
  }
  return list;
});

function formatTickLabel(frame) {
  const displayFrame = frame - timelineStartFrames.value;
  return `F${displayFrame} | ${(displayFrame / FPS).toFixed(2)}s`;
}

const ticks = computed(() => {
  const step = majorTickStep.value;
  const list = [];
  const start = Math.floor(visibleStart.value / step) * step;
  for (let frame = Math.max(0, start); frame <= visibleEnd.value + step; frame += step) {
    list.push({
      frame,
      leftPx: Math.round(frameToX(frame)),
      label: formatTickLabel(frame),
    });
  }
  return list;
});

function keyOf(rowId, segId) {
  return `${rowId}:${segId}`;
}

function frameToX(frame) {
  return trackLeftOffset.value + (frame - panFrame.value) * pxPerFrame.value;
}

function xToFrame(x) {
  return Math.max(0, Math.round(panFrame.value + (x - trackLeftOffset.value) / pxPerFrame.value));
}

function clientXToPlayheadFrame(clientX) {
  const rect = timelineViewport.value?.getBoundingClientRect();
  if (!rect) return playheadFrame.value;
  const raw = clientX - rect.left;
  const x = Math.max(trackLeftOffset.value, Math.min(rect.width - 1, raw));
  return xToFrame(x);
}

function displayFrameValue(frame) {
  return frame - timelineStartFrames.value;
}

function stopPlayback() {
  isPlaying.value = false;
  if (playbackRafId != null) {
    cancelAnimationFrame(playbackRafId);
    playbackRafId = null;
  }
  playbackAccum = 0;
}

function startPlayback() {
  if (isPlaying.value) return;
  isPlaying.value = true;
  playbackLastTs = performance.now();
  playbackAccum = 0;
  const step = (now) => {
    if (!isPlaying.value) return;
    const dt = Math.min(0.25, (now - playbackLastTs) / 1000);
    playbackLastTs = now;
    const spd = Number(playbackSpeed.value);
    const safeSpd = Number.isFinite(spd) && spd > 0 ? spd : 1;
    playbackAccum += dt * FPS * safeSpd;
    const adv = Math.floor(playbackAccum);
    playbackAccum -= adv;
    if (adv > 0) {
      playheadFrame.value = Math.max(0, playheadFrame.value + adv);
      selectedFrame.value = playheadFrame.value;
    }
    playbackRafId = requestAnimationFrame(step);
  };
  playbackRafId = requestAnimationFrame(step);
}

function togglePlayback() {
  if (isPlaying.value) {
    stopPlayback();
    statusText.value = "已暂停";
    scheduleSave();
  } else {
    startPlayback();
    statusText.value = "播放中";
  }
}

function nudgePlayhead(delta) {
  stopPlayback();
  playheadFrame.value = Math.max(0, playheadFrame.value + delta);
  selectedFrame.value = playheadFrame.value;
  scheduleSave();
}

function onPlayheadPointerDown(event) {
  if (event.button !== 0) return;
  event.stopPropagation();
  event.preventDefault();
  stopPlayback();
  if (!timelineViewport.value) return;
  playheadDrag = { pointerId: event.pointerId };
  try {
    timelineViewport.value.setPointerCapture?.(event.pointerId);
  } catch {
    /* ignore */
  }
  playheadFrame.value = clientXToPlayheadFrame(event.clientX);
  selectedFrame.value = playheadFrame.value;
}

function normalizeTimelineStart() {
  const n = Number(timelineStartValue.value);
  timelineStartValue.value = Number.isFinite(n) ? Math.max(0, Math.abs(n)) : 0;
  scheduleSave();
}

function clampPxPerFrame(v) {
  return Math.min(MAX_PX_PER_FRAME, Math.max(minPxPerFrame.value, v));
}

function clampPanFrame() {
  const smp = scrollMaxPan.value;
  if (panFrame.value > smp) panFrame.value = smp;
  if (panFrame.value < 0) panFrame.value = 0;
}

function onHScrollThumbPointerDown(event) {
  if (event.button !== 0) return;
  event.preventDefault();
  event.stopPropagation();
  draggingHScrollThumb = {
    startClientX: event.clientX,
    startPan: panFrame.value,
    pointerId: event.pointerId,
  };
  try {
    hScrollTrackEl.value?.setPointerCapture?.(event.pointerId);
  } catch {
    /* ignore */
  }
}

function onHScrollTrackPointerDown(event) {
  if (event.button !== 0) return;
  if (event.target.closest?.(".hscroll-thumb")) return;
  const el = hScrollTrackEl.value;
  if (!el) return;
  const smp = scrollMaxPan.value;
  if (smp <= 1e-9) return;
  const rect = el.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const trackW = rect.width;
  const tw = trackW * (hScrollThumbWidthPct.value / 100);
  const range = Math.max(1e-6, trackW - tw);
  let newPan = ((x - tw / 2) / range) * smp;
  panFrame.value = Math.max(0, Math.min(smp, newPan));
  scheduleSave();
}

/** 像素对齐：区间左缘与第 N 帧刻度线重合，右缘与第 end+1 帧刻度线重合 */
function segmentPixelStyle(startFrame, endFrame) {
  const left = Math.round(frameToX(startFrame) - trackLeftOffset.value);
  const right = Math.round(frameToX(endFrame + 1) - trackLeftOffset.value);
  return {
    left: `${left}px`,
    width: `${Math.max(1, right - left)}px`,
  };
}

function rowIndexFromClientY(clientY, rect) {
  const y = clientY - rect.top - TIMELINE_HEADER_HEIGHT;
  const idx = Math.floor(y / TIMELINE_HEIGHT_PER_ROW);
  return Math.max(0, Math.min(rows.value.length - 1, idx));
}

function pointInTimeline(clientX, clientY) {
  const rect = timelineViewport.value?.getBoundingClientRect();
  if (!rect) return null;
  return {
    rect,
    x: clientX - rect.left,
    y: clientY - rect.top,
    rowIndex: rowIndexFromClientY(clientY, rect),
  };
}

function findSegmentRow(segId) {
  for (let i = 0; i < rows.value.length; i++) {
    const row = rows.value[i];
    const seg = row.segments.find((s) => s.id === segId);
    if (seg) return { row, rowIndex: i, seg };
  }
  return null;
}

function normalizeRows(inputRows) {
  if (!Array.isArray(inputRows)) return [];
  return inputRows.map((row, idx) => {
    const rowId = row?.id || crypto.randomUUID();
    const rowName = row?.name || `干员${idx + 1}`;
    const segments = [];
    if (Array.isArray(row?.segments)) {
      row.segments.forEach((seg, segIdx) => {
        const start = Number(seg.startFrame);
        const end = Number(seg.endFrame);
        if (!Number.isFinite(start) || !Number.isFinite(end)) return;
        segments.push({
          id: seg.id || crypto.randomUUID(),
          startFrame: Math.max(0, Math.round(Math.min(start, end))),
          endFrame: Math.max(0, Math.round(Math.max(start, end))),
          color: seg.color || selectedColor.value,
          label: seg.label || `区间${segIdx + 1}`,
          note: typeof seg.note === "string" ? seg.note : "",
        });
      });
    } else if (Array.isArray(row?.items)) {
      row.items.forEach((item, itemIdx) => {
        const frame = Number(item.frame);
        if (!Number.isFinite(frame)) return;
        segments.push({
          id: item.id || crypto.randomUUID(),
          startFrame: Math.max(0, Math.round(frame)),
          endFrame: Math.max(0, Math.round(frame)),
          color: selectedColor.value,
          label: item.label || `区间${itemIdx + 1}`,
          note: "",
        });
      });
    }
    return { id: rowId, name: rowName, segments };
  });
}

function scheduleSave() {
  if (saveTimer) clearTimeout(saveTimer);
  saveTimer = setTimeout(async () => {
    const payload = buildPayload();
    localStorage.setItem(localCacheKey(), JSON.stringify(payload));
    try {
      const response = await fetch(`/api/timeline/cache/${encodeURIComponent(userId.value)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      statusText.value = response.ok ? "缓存已保存" : "已保存到本地，后端缓存失败";
    } catch {
      statusText.value = "已保存到本地，后端缓存失败";
    }
  }, 300);
}

function localCacheKey() {
  return `ak_timeline_cache_${userId.value || "default"}`;
}

function buildPayload() {
  return {
    meta: {
      version: 4,
      fps: FPS,
      pxPerFrame: pxPerFrame.value,
      panFrame: panFrame.value,
      timelineStartFrames: timelineStartFrames.value,
      playheadFrame: playheadFrame.value,
      playbackSpeed: playbackSpeed.value,
      updatedAt: new Date().toISOString(),
      userId: userId.value,
    },
    rows: rows.value,
  };
}

function applyPayload(payload) {
  if (!payload || !Array.isArray(payload.rows) || !payload.meta) return false;
  const normalized = normalizeRows(payload.rows);
  if (normalized.length === 0) return false;
  rows.value = normalized;
  pxPerFrame.value = clampPxPerFrame(Number(payload.meta.pxPerFrame) || pxPerFrame.value);
  panFrame.value = Number(payload.meta.panFrame) || 0;
  timelineStartUnit.value = "frames";
  timelineStartValue.value = Math.max(0, Math.round(Number(payload.meta.timelineStartFrames) || 0));
  const ph = Number(payload.meta.playheadFrame);
  playheadFrame.value = Number.isFinite(ph) ? Math.max(0, Math.round(ph)) : 0;
  const spd = Number(payload.meta.playbackSpeed);
  playbackSpeed.value = Number.isFinite(spd) && spd > 0 ? spd : 1;
  selectedKeys.value = [];
  return true;
}

async function loadCache() {
  statusText.value = "正在加载缓存...";
  try {
    const response = await fetch(`/api/timeline/cache/${encodeURIComponent(userId.value)}`);
    if (response.ok) {
      const result = await response.json();
      if (result.ok && result.has_cache && result.data && applyPayload(result.data)) {
        statusText.value = "已从后端缓存恢复";
        return;
      }
    }
  } catch {
    // fallback
  }

  const localRaw = localStorage.getItem(localCacheKey());
  if (localRaw) {
    try {
      if (applyPayload(JSON.parse(localRaw))) {
        statusText.value = "已从本地缓存恢复";
        return;
      }
    } catch {
      statusText.value = "本地缓存损坏，已忽略";
    }
  }
  statusText.value = "未找到缓存，使用默认模板";
}

function addRow() {
  const before = buildHistorySnapshot();
  rows.value.push({
    id: crypto.randomUUID(),
    name: `干员${rows.value.length + 1}`,
    segments: [],
  });
  pushUndoSnapshot(before);
  scheduleSave();
}

function removeRow(rowId) {
  if (rows.value.length <= 1) return;
  const before = buildHistorySnapshot();
  rows.value = rows.value.filter((row) => row.id !== rowId);
  selectedKeys.value = selectedKeys.value.filter((k) => !k.startsWith(`${rowId}:`));
  pushUndoSnapshot(before);
  scheduleSave();
}

function selectSegment(rowId, segId, frame, additive = false) {
  const key = keyOf(rowId, segId);
  if (additive) {
    if (selectedKeys.value.includes(key)) {
      selectedKeys.value = selectedKeys.value.filter((k) => k !== key);
    } else {
      selectedKeys.value = [...selectedKeys.value, key];
    }
  } else {
    if (selectedKeys.value.length === 1 && selectedKeys.value[0] === key) {
      selectedKeys.value = [];
    } else {
      selectedKeys.value = [key];
    }
  }
  selectedFrame.value = frame;
}

function isSelectedSegment(rowId, segId) {
  return selectedKeys.value.includes(keyOf(rowId, segId));
}

function isRowSelected(rowId) {
  const row = rows.value.find((r) => r.id === rowId);
  if (!row || !row.segments.length) return false;
  return row.segments.every((seg) => selectedKeys.value.includes(keyOf(rowId, seg.id)));
}

function toggleRowSelection(rowId, checked) {
  const row = rows.value.find((r) => r.id === rowId);
  if (!row) return;
  const rowKeys = row.segments.map((seg) => keyOf(rowId, seg.id));
  if (checked) {
    selectedKeys.value = [...new Set([...selectedKeys.value, ...rowKeys])];
    statusText.value = rowKeys.length ? `已选中整行 ${row.name}` : "该行没有可选区间";
    return;
  }
  selectedKeys.value = selectedKeys.value.filter((k) => !rowKeys.includes(k));
  statusText.value = `已取消整行 ${row.name}`;
}

function normalizeHex(color) {
  if (typeof color !== "string") return null;
  const m = color.trim().match(/^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/);
  if (!m) return null;
  const hex = m[1];
  if (hex.length === 3) {
    return `#${hex[0]}${hex[0]}${hex[1]}${hex[1]}${hex[2]}${hex[2]}`.toLowerCase();
  }
  return `#${hex.toLowerCase()}`;
}

function dividerColorFrom(baseColor) {
  const hex = normalizeHex(baseColor);
  if (!hex) return "rgba(255,255,255,0.65)";
  const r = Number.parseInt(hex.slice(1, 3), 16);
  const g = Number.parseInt(hex.slice(3, 5), 16);
  const b = Number.parseInt(hex.slice(5, 7), 16);
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  const factor = luminance > 0.55 ? 0.45 : 1.55;
  const nr = Math.max(0, Math.min(255, Math.round(r * factor)));
  const ng = Math.max(0, Math.min(255, Math.round(g * factor)));
  const nb = Math.max(0, Math.min(255, Math.round(b * factor)));
  return `rgb(${nr} ${ng} ${nb})`;
}

function applyColorToSelectedSegments() {
  if (!selectedKeys.value.length) return;
  const before = buildHistorySnapshot();
  rows.value.forEach((row) => {
    row.segments.forEach((seg) => {
      if (selectedKeys.value.includes(keyOf(row.id, seg.id))) {
        seg.color = selectedColor.value;
      }
    });
  });
  pushUndoSnapshot(before);
  scheduleSave();
}

function updateSingleSelectedNote(value) {
  if (!singleSelectedSegment.value) return;
  if (singleSelectedSegment.value.seg.note === value) return;
  const before = buildHistorySnapshot();
  singleSelectedSegment.value.seg.note = value;
  pushUndoSnapshot(before);
  scheduleSave();
}

function deleteSelectedSegments() {
  if (!selectedKeys.value.length) return;
  const before = buildHistorySnapshot();
  rows.value.forEach((row) => {
    row.segments = row.segments.filter((seg) => !selectedKeys.value.includes(keyOf(row.id, seg.id)));
  });
  selectedKeys.value = [];
  pushUndoSnapshot(before);
  scheduleSave();
}

function startCreateRangeByPointer(clientX, clientY) {
  if (!timelineViewport.value) return;
  const p = pointInTimeline(clientX, clientY);
  if (!p) return;
  if (p.y < TIMELINE_HEADER_HEIGHT) return;
  if (p.x < trackLeftOffset.value) return;
  const rowId = rows.value[p.rowIndex]?.id;
  if (!rowId) return;
  const frame = xToFrame(p.x);
  createRange = {
    rowId,
    startX: clientX,
    startFrame: frame,
    currentFrame: frame,
    moved: false,
  };
  selectedFrame.value = frame;
}

function startMarqueeByPointer(clientX, clientY) {
  const p = pointInTimeline(clientX, clientY);
  if (!p) return;
  if (p.x < trackLeftOffset.value) return;
  marquee = {
    startX: p.x,
    startY: p.y,
    currentX: p.x,
    currentY: p.y,
    moved: false,
  };
}

function startTimelinePointerDown(event) {
  if (event.altKey) {
    panning = { startX: event.clientX, startPanFrame: panFrame.value };
    return;
  }
  if (event.button !== 0) return;
  if (event.target?.closest?.(".segment, .segment-handle, .hscroll-wrap, .row-meta, .playhead")) return;
  if (event.shiftKey) {
    startCreateRangeByPointer(event.clientX, event.clientY);
    return;
  }
  startMarqueeByPointer(event.clientX, event.clientY);
}

function handlePointerMove(event) {
  if (playheadDrag && timelineViewport.value) {
    playheadFrame.value = clientXToPlayheadFrame(event.clientX);
    selectedFrame.value = playheadFrame.value;
    return;
  }

  if (segmentResize && timelineViewport.value) {
    const rect = timelineViewport.value.getBoundingClientRect();
    const frame = xToFrame(event.clientX - rect.left);
    const found = findSegmentRow(segmentResize.segId);
    if (!found) return;
    const seg = found.seg;
    if (segmentResize.edge === "left") {
      const maxStart = segmentResize.origEnd;
      const next = Math.max(0, Math.min(frame, maxStart));
      if (hasOverlapInRow(found.row, next, seg.endFrame, new Set([seg.id]))) return;
      seg.startFrame = next;
      if (seg.endFrame < seg.startFrame) seg.endFrame = seg.startFrame;
    } else {
      const minEnd = segmentResize.origStart;
      const next = Math.max(minEnd, frame);
      if (hasOverlapInRow(found.row, seg.startFrame, next, new Set([seg.id]))) return;
      seg.endFrame = next;
      if (seg.startFrame > seg.endFrame) seg.startFrame = seg.endFrame;
    }
    segmentResize.moved =
      seg.startFrame !== segmentResize.origStart || seg.endFrame !== segmentResize.origEnd;
    selectedFrame.value = segmentResize.edge === "left" ? seg.startFrame : seg.endFrame;
    found.row.segments.sort((a, b) => a.startFrame - b.startFrame);
    return;
  }

  if (draggingHScrollThumb && hScrollTrackEl.value) {
    const el = hScrollTrackEl.value;
    const rect = el.getBoundingClientRect();
    const trackW = rect.width;
    const twFrac = hScrollThumbWidthPct.value / 100;
    const thumbW = trackW * twFrac;
    const range = Math.max(1e-6, trackW - thumbW);
    const smp = scrollMaxPan.value;
    const delta = event.clientX - draggingHScrollThumb.startClientX;
    const newPan = draggingHScrollThumb.startPan + (delta / range) * smp;
    panFrame.value = Math.max(0, Math.min(smp, newPan));
    return;
  }

  if (segmentDrag && timelineViewport.value) {
    const rect = timelineViewport.value.getBoundingClientRect();
    const curFrame = xToFrame(event.clientX - rect.left);
    const curRow = rowIndexFromClientY(event.clientY, rect);
    const dFrame = curFrame - segmentDrag.startPointerFrame;
    const dRow = curRow - segmentDrag.startPointerRowIndex;
    if (
      Math.abs(event.clientX - segmentDrag.startClientX) >= DRAG_THRESHOLD ||
      Math.abs(event.clientY - segmentDrag.startClientY) >= DRAG_THRESHOLD
    ) {
      segmentDrag.moved = true;
    }

    const movingIds = new Set(segmentDrag.entries.map((e) => e.segId));
    segmentDrag.entries.forEach((entry) => {
      const found = findSegmentRow(entry.segId);
      if (!found) return;
      const { seg } = found;
      let targetRowIndex = Math.max(
        0,
        Math.min(rows.value.length - 1, entry.origRowIndex + dRow),
      );
      const targetRow = rows.value[targetRowIndex];
      const spanFrames = entry.origEnd - entry.origStart;
      const rawStart = entry.origStart + dFrame;
      let newStart = Math.max(0, rawStart);
      let newEnd = newStart + spanFrames;
      const snappedStart = snapStartToNeighborTail(targetRow, newStart, spanFrames, movingIds);
      if (snappedStart !== newStart) {
        newStart = snappedStart;
        newEnd = newStart + spanFrames;
      }
      if (hasOverlapInRow(targetRow, newStart, newEnd, movingIds)) return;

      if (found.rowIndex !== targetRowIndex) {
        const idx = found.row.segments.indexOf(seg);
        if (idx >= 0) found.row.segments.splice(idx, 1);
        targetRow.segments.push(seg);
      }
      seg.startFrame = newStart;
      seg.endFrame = newEnd;
    });

    rows.value.forEach((row) => {
      row.segments.sort((a, b) => a.startFrame - b.startFrame);
    });
    return;
  }

  if (createRange && timelineViewport.value) {
    const rect = timelineViewport.value.getBoundingClientRect();
    createRange.currentFrame = xToFrame(event.clientX - rect.left);
    if (Math.abs(event.clientX - createRange.startX) >= DRAG_THRESHOLD) {
      createRange.moved = true;
    }
    selectedFrame.value = createRange.currentFrame;
    return;
  }

  if (marquee && timelineViewport.value) {
    const rect = timelineViewport.value.getBoundingClientRect();
    marquee.currentX = event.clientX - rect.left;
    marquee.currentY = event.clientY - rect.top;
    if (
      Math.abs(marquee.currentX - marquee.startX) >= DRAG_THRESHOLD ||
      Math.abs(marquee.currentY - marquee.startY) >= DRAG_THRESHOLD
    ) {
      marquee.moved = true;
    }
    return;
  }

  if (panning) {
    const deltaX = event.clientX - panning.startX;
    panFrame.value = Math.max(0, panning.startPanFrame - deltaX / pxPerFrame.value);
  }
}

function finishCreateRange() {
  if (!createRange) return;
  const row = rows.value.find((r) => r.id === createRange.rowId);
  if (row && createRange.moved) {
    const before = buildHistorySnapshot();
    const startFrame = Math.min(createRange.startFrame, createRange.currentFrame);
    const endFrame = Math.max(createRange.startFrame, createRange.currentFrame);
    if (hasOverlapInRow(row, startFrame, endFrame)) {
      statusText.value = "同一行不允许区间重叠";
      createRange = null;
      return;
    }
    const segment = {
      id: crypto.randomUUID(),
      startFrame,
      endFrame,
      color: selectedColor.value,
      label: `区间 ${startFrame}-${endFrame}`,
      note: "",
    };
    row.segments.push(segment);
    row.segments.sort((a, b) => a.startFrame - b.startFrame);
    selectedKeys.value = [keyOf(row.id, segment.id)];
    pushUndoSnapshot(before);
    statusText.value = `已添加区间 F${startFrame}-${endFrame}`;
    scheduleSave();
  }
  createRange = null;
}

function rangesOverlap(minA, maxA, minB, maxB) {
  return Math.max(minA, minB) <= Math.min(maxA, maxB);
}

function segmentOverlaps(startA, endA, startB, endB) {
  return Math.max(startA, startB) <= Math.min(endA, endB);
}

function hasOverlapInRow(row, startFrame, endFrame, ignoreIds = new Set()) {
  return row.segments.some((s) => {
    if (ignoreIds.has(s.id)) return false;
    return segmentOverlaps(startFrame, endFrame, s.startFrame, s.endFrame);
  });
}

function snapStartToNeighborTail(row, proposedStart, spanFrames, ignoreIds = new Set()) {
  const thresholdFrames = Math.max(1, Math.round(SNAP_PIXELS / Math.max(1e-9, pxPerFrame.value)));
  let bestStart = proposedStart;
  let bestDistance = Infinity;

  row.segments.forEach((seg) => {
    if (ignoreIds.has(seg.id)) return;
    const candidateStart = seg.endFrame + 1;
    const distance = Math.abs(proposedStart - candidateStart);
    if (distance > thresholdFrames) return;

    const candidateEnd = candidateStart + spanFrames;
    if (hasOverlapInRow(row, candidateStart, candidateEnd, ignoreIds)) return;
    if (distance < bestDistance) {
      bestDistance = distance;
      bestStart = candidateStart;
    }
  });

  return bestStart;
}

function finishMarqueeSelection() {
  if (!marquee) return;
  if (!marquee.moved) {
    const x = marquee.startX;
    if (x >= trackLeftOffset.value) {
      playheadFrame.value = xToFrame(x);
      selectedFrame.value = playheadFrame.value;
      statusText.value = `播放头 F${displayFrameValue(playheadFrame.value)}`;
      scheduleSave();
    }
    marquee = null;
    return;
  }

  const x1 = Math.min(marquee.startX, marquee.currentX);
  const x2 = Math.max(marquee.startX, marquee.currentX);
  const y1 = Math.min(marquee.startY, marquee.currentY);
  const y2 = Math.max(marquee.startY, marquee.currentY);
  const next = [];

  rows.value.forEach((row, rowIndex) => {
    const trackTop = TIMELINE_HEADER_HEIGHT + rowIndex * TIMELINE_HEIGHT_PER_ROW + TRACK_TOP_OFFSET;
    const trackBottom = trackTop + TRACK_HEIGHT;
    if (!rangesOverlap(y1, y2, trackTop, trackBottom)) return;

    row.segments.forEach((seg) => {
      const left = Math.round(frameToX(seg.startFrame));
      const right = Math.round(frameToX(seg.endFrame + 1));
      if (rangesOverlap(x1, x2, left, right)) {
        next.push(keyOf(row.id, seg.id));
      }
    });
  });

  selectedKeys.value = next;
  statusText.value = next.length ? `已框选 ${next.length} 个区间` : "框选区域没有命中区间";
  marquee = null;
}

function handlePointerUp() {
  if (playheadDrag) {
    try {
      timelineViewport.value?.releasePointerCapture?.(playheadDrag.pointerId);
    } catch {
      /* ignore */
    }
    playheadDrag = null;
    scheduleSave();
  }
  if (segmentResize) {
    const before = segmentResize.historySnapshot;
    const moved = segmentResize.moved;
    try {
      timelineViewport.value?.releasePointerCapture?.(segmentResize.pointerId);
    } catch {
      /* ignore */
    }
    segmentResize = null;
    if (moved) {
      ignoreNextSegmentClick = true;
      pushUndoSnapshot(before);
      scheduleSave();
    }
  }
  if (draggingHScrollThumb) {
    try {
      hScrollTrackEl.value?.releasePointerCapture?.(draggingHScrollThumb.pointerId);
    } catch {
      /* ignore */
    }
    draggingHScrollThumb = null;
    scheduleSave();
  }
  if (segmentDrag) {
    const before = segmentDrag.historySnapshot;
    if (segmentDrag.moved) {
      ignoreNextSegmentClick = true;
      pushUndoSnapshot(before);
      scheduleSave();
    }
    segmentDrag = null;
  }
  if (createRange) finishCreateRange();
  if (marquee) finishMarqueeSelection();
  if (panning) {
    panning = null;
    scheduleSave();
  }
}

function previewStyle(rowId) {
  if (!createRange || createRange.rowId !== rowId || !createRange.moved) return null;
  const start = Math.min(createRange.startFrame, createRange.currentFrame);
  const end = Math.max(createRange.startFrame, createRange.currentFrame);
  return {
    ...segmentPixelStyle(start, end),
    background: `${selectedColor.value}66`,
  };
}

function segmentStyle(row, seg) {
  const style = {
    ...segmentPixelStyle(seg.startFrame, seg.endFrame),
    background: seg.color,
  };
  if (row?.segments?.length) {
    const prev = row.segments.find(
      (s) =>
        s.id !== seg.id &&
        s.endFrame + 1 === seg.startFrame &&
        normalizeHex(s.color) === normalizeHex(seg.color),
    );
    if (prev) {
      style.boxShadow = `inset 1px 0 0 ${dividerColorFrom(seg.color)}`;
    }
  }
  return style;
}

function startSegmentResize(rowId, segId, edge, event) {
  if (event.button !== 0 || event.shiftKey || event.altKey) return;
  event.stopPropagation();
  event.preventDefault();
  if (!timelineViewport.value) return;
  const found = findSegmentRow(segId);
  if (!found || found.row.id !== rowId) return;
  const seg = found.seg;
  segmentResize = {
    edge,
    segId,
    origStart: seg.startFrame,
    origEnd: seg.endFrame,
    moved: false,
    historySnapshot: buildHistorySnapshot(),
    pointerId: event.pointerId,
  };
  try {
    timelineViewport.value.setPointerCapture?.(event.pointerId);
  } catch {
    /* ignore */
  }
  selectedFrame.value = edge === "left" ? seg.startFrame : seg.endFrame;
  statusText.value = edge === "left" ? "拖动左缘缩短/拉长" : "拖动右缘缩短/拉长";
}

function startSegmentDrag(rowId, segId, event) {
  if (event.button !== 0 || event.shiftKey || event.altKey) return;
  if (event.target?.closest?.(".segment-handle")) return;
  event.stopPropagation();
  if (!timelineViewport.value) return;

  const key = keyOf(rowId, segId);
  const keysToMove = selectedKeys.value.includes(key)
    ? [...selectedKeys.value]
    : [key];

  const rect = timelineViewport.value.getBoundingClientRect();
  const startPointerFrame = xToFrame(event.clientX - rect.left);
  const startPointerRowIndex = rowIndexFromClientY(event.clientY, rect);

  const entries = [];
  keysToMove.forEach((k) => {
    const colon = k.indexOf(":");
    if (colon < 0) return;
    const rId = k.slice(0, colon);
    const sId = k.slice(colon + 1);
    const found = findSegmentRow(sId);
    if (!found || found.row.id !== rId) return;
    entries.push({
      segId: sId,
      origRowIndex: found.rowIndex,
      origStart: found.seg.startFrame,
      origEnd: found.seg.endFrame,
    });
  });
  if (!entries.length) return;

  segmentDrag = {
    entries,
    startPointerFrame,
    startPointerRowIndex,
    startClientX: event.clientX,
    startClientY: event.clientY,
    moved: false,
    historySnapshot: buildHistorySnapshot(),
  };
}

function onSegmentClick(rowId, segId, frame, additive) {
  if (ignoreNextSegmentClick) {
    ignoreNextSegmentClick = false;
    return;
  }
  if (isPasting) return;
  selectSegment(rowId, segId, frame, additive);
}

/** 将滚轮增量转为水平方向的等效像素位移（用于平移时间轴） */
function wheelToHorizontalPixels(event) {
  const useX = Math.abs(event.deltaX) > Math.abs(event.deltaY);
  const raw = useX ? event.deltaX : event.deltaY;
  if (event.deltaMode === 1) {
    return raw * 40;
  }
  if (event.deltaMode === 2) {
    return raw * (timelineViewport.value?.clientWidth || viewportWidth.value || 800);
  }
  return raw;
}

function handleWheel(event) {
  if (!timelineViewport.value) return;

  if (event.ctrlKey || event.metaKey) {
    event.preventDefault();
    const rect = timelineViewport.value.getBoundingClientRect();
    const offsetX = Math.max(trackLeftOffset.value, event.clientX - rect.left);
    const trackX = offsetX - trackLeftOffset.value;
    const anchorFrame = panFrame.value + trackX / pxPerFrame.value;
    const next = clampPxPerFrame(pxPerFrame.value * (event.deltaY < 0 ? 1.12 : 0.88));
    pxPerFrame.value = next;
    panFrame.value = Math.max(0, anchorFrame - trackX / next);
    clampPanFrame();
    scheduleSave();
    return;
  }

  event.preventDefault();
  const pxDelta = wheelToHorizontalPixels(event);
  const dFrames = pxDelta / pxPerFrame.value;
  panFrame.value = Math.max(0, Math.min(scrollMaxPan.value, panFrame.value + dFrames));
  scheduleSave();
}

function getSelectedSegments() {
  const result = [];
  rows.value.forEach((row, rowIndex) => {
    row.segments.forEach((seg) => {
      if (selectedKeys.value.includes(keyOf(row.id, seg.id))) {
        result.push({ rowId: row.id, rowIndex, segment: seg });
      }
    });
  });
  return result;
}

function copySelectedSegments() {
  const selected = getSelectedSegments();
  if (!selected.length) return;
  const minFrame = Math.min(...selected.map((item) => item.segment.startFrame));
  const maxFrame = Math.max(...selected.map((item) => item.segment.endFrame));
  clipboardData = {
    baseFrame: minFrame,
    spanFrames: Math.max(1, maxFrame - minFrame + 1),
    // Immediately paste to the nearest available position on the right.
    nextAnchor: maxFrame + 1,
    items: selected.map((item) => ({
      rowId: item.rowId,
      rowIndex: item.rowIndex,
      startOffset: item.segment.startFrame - minFrame,
      endOffset: item.segment.endFrame - minFrame,
      color: item.segment.color,
      label: item.segment.label,
      note: item.segment.note || "",
    })),
  };
  statusText.value = `已复制 ${selected.length} 个区间`;
}

function cutSelectedSegments() {
  const count = selectedKeys.value.length;
  if (!count) return;
  copySelectedSegments();
  deleteSelectedSegments();
  statusText.value = `已剪切 ${count} 个区间`;
}

function selectAllSegments() {
  const keys = [];
  rows.value.forEach((row) => {
    row.segments.forEach((seg) => keys.push(keyOf(row.id, seg.id)));
  });
  selectedKeys.value = keys;
  statusText.value = keys.length ? `已全选 ${keys.length} 个区间` : "没有可选区间";
}

function findPasteAnchor(baseAnchor, items, stepFrames) {
  let anchor = baseAnchor;
  for (let attempt = 0; attempt < 2000; attempt++) {
    let collided = false;
    for (const item of items) {
      const row =
        rows.value.find((r) => r.id === item.rowId) ||
        rows.value[Math.min(rows.value.length - 1, Math.max(0, item.rowIndex))];
      if (!row) continue;
      const s = Math.max(0, anchor + item.startOffset);
      const e = Math.max(s, anchor + item.endOffset);
      if (hasOverlapInRow(row, s, e)) {
        collided = true;
        break;
      }
    }
    if (!collided) return anchor;
    anchor += stepFrames;
  }
  return anchor;
}

function pasteSegments() {
  if (!clipboardData?.items?.length) return;
  const before = buildHistorySnapshot();
  isPasting = true;
  const initialAnchor = Number.isFinite(selectedFrame.value) ? selectedFrame.value : clipboardData.baseFrame;
  const stepFrames = Math.max(1, clipboardData.spanFrames || 1);
  const rawAnchor = Number.isFinite(clipboardData.nextAnchor)
    ? clipboardData.nextAnchor
    : initialAnchor;
  const anchor = findPasteAnchor(rawAnchor, clipboardData.items, stepFrames);
  const pasted = [];

  clipboardData.items.forEach((item) => {
    const row =
      rows.value.find((r) => r.id === item.rowId) ||
      rows.value[Math.min(rows.value.length - 1, Math.max(0, item.rowIndex))];
    if (!row) return;
    const seg = {
      id: crypto.randomUUID(),
      startFrame: Math.max(0, anchor + item.startOffset),
      endFrame: Math.max(0, anchor + item.endOffset),
      color: item.color,
      label: item.label,
      note: item.note || "",
    };
    if (hasOverlapInRow(row, seg.startFrame, seg.endFrame)) return;
    row.segments.push(seg);
    row.segments.sort((a, b) => a.startFrame - b.startFrame);
    pasted.push(keyOf(row.id, seg.id));
  });

  if (pasted.length) {
    selectedKeys.value = pasted;
    clipboardData.nextAnchor = anchor + stepFrames;
    pushUndoSnapshot(before);
    statusText.value = `已粘贴 ${pasted.length} 个区间`;
    scheduleSave();
  } else {
    statusText.value = "粘贴失败：目标区域与现有区间重叠";
  }
  setTimeout(() => {
    isPasting = false;
  }, 0);
}

function handleKeydown(event) {
  const target = event.target;
  const isTextInput =
    target instanceof HTMLInputElement ||
    target instanceof HTMLTextAreaElement ||
    target?.isContentEditable;
  if (isTextInput) return;

  if (event.code === "Space" || event.key === " " || event.key === "Spacebar") {
    if (!event.ctrlKey && !event.metaKey && !event.altKey) {
      event.preventDefault();
      togglePlayback();
      return;
    }
  }

  if (event.key === "ArrowLeft" && !event.ctrlKey && !event.metaKey) {
    event.preventDefault();
    nudgePlayhead(-1);
    return;
  }
  if (event.key === "ArrowRight" && !event.ctrlKey && !event.metaKey) {
    event.preventDefault();
    nudgePlayhead(1);
    return;
  }

  const keyLower = event.key.toLowerCase();
  if (keyLower === "backspace" || keyLower === "delete") {
    if (selectedKeys.value.length) {
      event.preventDefault();
      deleteSelectedSegments();
    }
    return;
  }

  const isCtrl = event.ctrlKey || event.metaKey;
  if (!isCtrl) return;

  if (keyLower === "c") {
    event.preventDefault();
    copySelectedSegments();
  } else if (keyLower === "x") {
    event.preventDefault();
    cutSelectedSegments();
  } else if (keyLower === "v") {
    event.preventDefault();
    pasteSegments();
  } else if (keyLower === "a") {
    event.preventDefault();
    selectAllSegments();
  } else if (keyLower === "y") {
    event.preventDefault();
    redoLastAction();
  } else if (keyLower === "z" && event.shiftKey) {
    event.preventDefault();
    redoLastAction();
  } else if (keyLower === "z" && !event.shiftKey) {
    event.preventDefault();
    undoLastAction();
  }
}

function exportJson() {
  const blob = new Blob([JSON.stringify(buildPayload(), null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `ak_timeline_${userId.value || "default"}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

function triggerImport() {
  fileInput.value?.click();
}

async function importJson(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  try {
    const before = buildHistorySnapshot();
    const parsed = JSON.parse(await file.text());
    if (!applyPayload(parsed)) {
      statusText.value = "导入失败：JSON 格式不正确";
      return;
    }
    pushUndoSnapshot(before);
    statusText.value = "导入成功";
    scheduleSave();
  } catch {
    statusText.value = "导入失败：无法解析 JSON";
  } finally {
    event.target.value = "";
  }
}

function updateViewportWidth() {
  if (!timelineViewport.value) return;
  const viewportRect = timelineViewport.value.getBoundingClientRect();
  const firstTrack = timelineViewport.value.querySelector(".row-track");
  if (firstTrack) {
    const trackRect = firstTrack.getBoundingClientRect();
    trackLeftOffset.value = Math.max(0, trackRect.left - viewportRect.left);
    viewportWidth.value = firstTrack.clientWidth || 1200;
  } else {
    trackLeftOffset.value = TRACK_X_OFFSET;
    viewportWidth.value = Math.max(320, (timelineViewport.value.clientWidth || 1200) - trackLeftOffset.value);
  }
  pxPerFrame.value = clampPxPerFrame(pxPerFrame.value);
  clampPanFrame();
}

function changeUserAndReload() {
  loadCache();
}

onMounted(() => {
  loadCache();
  window.addEventListener("pointermove", handlePointerMove);
  window.addEventListener("pointerup", handlePointerUp);
  window.addEventListener("keydown", handleKeydown);
  window.addEventListener("beforeunload", onBeforeUnload);
  window.addEventListener("resize", updateViewportWidth);
  resizeObserver = new ResizeObserver(updateViewportWidth);
  if (timelineViewport.value) resizeObserver.observe(timelineViewport.value);
  updateViewportWidth();
});

onUnmounted(() => {
  stopPlayback();
  window.removeEventListener("pointermove", handlePointerMove);
  window.removeEventListener("pointerup", handlePointerUp);
  window.removeEventListener("keydown", handleKeydown);
  window.removeEventListener("beforeunload", onBeforeUnload);
  window.removeEventListener("resize", updateViewportWidth);
  if (resizeObserver) resizeObserver.disconnect();
});
</script>

<template>
  <main class="page">
    <header class="page-title-bar">
      <h1 class="page-title">明日方舟排轴工具 Powered by Tim(QQ321346659)</h1>
    </header>

    <header class="toolbar">
      <div class="left-tools">
        <label>
          用户ID
          <input v-model.trim="userId" @change="changeUserAndReload" />
        </label>
        <label class="start-offset-editor">
          起点偏移（显示为负）
          <input v-model.number="timelineStartValue" type="number" min="0" step="1" @change="normalizeTimelineStart" />
          <select v-model="timelineStartUnit" @change="normalizeTimelineStart">
            <option value="seconds">秒</option>
            <option value="frames">帧</option>
          </select>
        </label>
        <button @click="addRow">添加行</button>
        <button @click="exportJson">导出JSON</button>
        <button @click="triggerImport">导入JSON</button>
        <input ref="fileInput" type="file" accept="application/json" class="hidden" @change="importJson" />
      </div>
      <div class="right-tools">
        <span>FPS: 60</span>
        <span>光标: F{{ cursorDisplayFrame }} ({{ timeAtCursor }}s)</span>
        <span>播放头: F{{ displayFrameValue(playheadFrame) }}</span>
        <label class="playback-speed">
          倍速
          <input
            v-model.number="playbackSpeed"
            type="number"
            min="0.1"
            step="0.1"
            @change="scheduleSave"
          />
        </label>
        <button type="button" @click="togglePlayback">{{ isPlaying ? "暂停" : "播放" }}</button>
        <span>时间轴起点: -{{ timelineStartFrames }} 帧</span>
        <span>已选区间: {{ selectedCount }}</span>
      </div>
    </header>

    <div class="palette">
      <span>区间颜色：</span>
      <input v-model="selectedColor" type="color" class="color-picker" />
      <span class="color-value">{{ selectedColor }}</span>
      <button @click="applyColorToSelectedSegments">给选中区间改色</button>
      <button class="danger" @click="deleteSelectedSegments">删除选中区间</button>
      <label class="note-editor">
        <span>备注：</span>
        <input
          :value="singleSelectedSegment?.seg.note || ''"
          :disabled="!singleSelectedSegment"
          placeholder="选中 1 个区间后可编辑备注"
          @input="updateSingleSelectedNote($event.target.value)"
        />
      </label>
    </div>

    <div class="status-line">
      <span>状态：{{ statusText }}</span>
      <span>
        操作：Shift+左键拖拽创建区间；左键拖框批量选择；拖拽区间可改时间/拖到其他行；Ctrl+A 全选；Ctrl+C/V/X
        复制粘贴剪切；Backspace/Delete 删除；空格 播放/暂停；左右方向键 ±1 帧；Ctrl+Z 撤回；Ctrl+Y / Ctrl+Shift+Z 重做；滚轮左右平移时间轴，Ctrl+滚轮缩放（最外≈{{ MAX_VISIBLE_HOURS }}h/屏；最大放大仍为 1
        帧一格）；Alt+拖动平移；放大时可用底部横条平移；选中区间后拖左右白边可拉长/缩短；格线步长={{
          minorGridStep
        }}
        帧
      </span>
      <span>视窗约 {{ visibleSpanHours.toFixed(2) }}h（上限 {{ MAX_VISIBLE_HOURS }}h）</span>
    </div>

    <section
      ref="timelineViewport"
      class="timeline"
      :style="{ height: `${totalHeight}px` }"
      @wheel="handleWheel"
      @pointerdown="startTimelinePointerDown"
    >
      <div class="marquee-layer">
        <div v-if="marqueeStyle" class="marquee" :style="marqueeStyle"></div>
      </div>

      <div
        v-for="line in frameGridLines"
        :key="`g-${line.frame}`"
        class="grid-line"
        :class="{ major: line.major, minor: !line.major }"
        :style="{ left: `${line.leftPx}px` }"
      ></div>

      <div
        v-for="tick in ticks"
        :key="tick.frame"
        class="tick"
        :style="{ left: `${tick.leftPx}px` }"
      >
        <span class="tick-label">{{ tick.label }}</span>
      </div>

      <TimelineRow
        v-for="(row, rowIndex) in rows"
        :key="row.id"
        :row="row"
        :row-index="rowIndex"
        :timeline-header-height="TIMELINE_HEADER_HEIGHT"
        :timeline-height-per-row="TIMELINE_HEIGHT_PER_ROW"
        :is-row-selected="isRowSelected"
        :toggle-row-selection="toggleRowSelection"
        :is-selected-segment="isSelectedSegment"
        :segment-style="segmentStyle"
        :preview-style="previewStyle"
        :display-frame-value="displayFrameValue"
        :schedule-save="scheduleSave"
        :remove-row="removeRow"
        :start-segment-drag="startSegmentDrag"
        :on-segment-click="onSegmentClick"
        :start-segment-resize="startSegmentResize"
      />

      <div
        class="playhead"
        :style="{ left: `${Math.round(frameToX(playheadFrame))}px` }"
        @pointerdown="onPlayheadPointerDown"
      >
        <div class="playhead-handle" title="拖动播放头"></div>
        <div class="playhead-line" title="拖动播放头"></div>
      </div>
    </section>

    <div v-show="showPanScrollbar" class="hscroll-wrap">
      <span class="hscroll-label">平移</span>
      <div
        ref="hScrollTrackEl"
        class="hscroll-track"
        @pointerdown="onHScrollTrackPointerDown"
      >
        <div
          class="hscroll-thumb"
          :style="hScrollThumbStyle"
          @pointerdown="onHScrollThumbPointerDown"
        ></div>
      </div>
    </div>
  </main>
</template>

<style scoped>
.page {
  margin: 0;
  min-height: 100vh;
  background: #111418;
  color: #f5f8ff;
  font-family: "Segoe UI", Arial, sans-serif;
  padding: 12px;
  box-sizing: border-box;
}

.page-title-bar {
  margin: 0 0 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #2f3745;
}

.page-title {
  margin: 0;
  font-size: 1.35rem;
  font-weight: 700;
  line-height: 1.35;
  letter-spacing: 0.02em;
  color: #f5f8ff;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 4px;
}

.left-tools,
.right-tools {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.start-offset-editor {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.start-offset-editor input {
  width: 90px;
}

.playback-speed {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.playback-speed input {
  width: 64px;
}

.palette {
  margin-top: 10px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.note-editor {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.note-editor input {
  width: 260px;
}

.status-line {
  margin: 10px 0;
  display: flex;
  gap: 20px;
  flex-wrap: wrap;
  color: #adb5c3;
}

.timeline {
  position: relative;
  overflow: hidden;
  border: 1px solid #2f3745;
  background: repeating-linear-gradient(
    to bottom,
    #1a1e26 0,
    #1a1e26 58px,
    #171b22 58px,
    #171b22 66px
  );
  user-select: none;
}

.marquee-layer {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.grid-line {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 1px;
}

.grid-line.minor {
  background: #2c3340;
}

.grid-line.major {
  background: #4b5668;
}

.tick {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 0;
  pointer-events: none;
}

.tick-label {
  position: absolute;
  top: 2px;
  left: 4px;
  font-size: 11px;
  color: #b3bfce;
  white-space: nowrap;
}

button {
  background: #2d66ff;
  color: #fff;
  border: 0;
  border-radius: 6px;
  padding: 6px 10px;
  cursor: pointer;
}

.danger {
  background: #a73642;
}

input {
  border-radius: 6px;
  padding: 5px 8px;
}

.color-picker {
  width: 44px;
  height: 28px;
  padding: 0;
  border: 1px solid #ffffff44;
  background: transparent;
}

.color-value {
  color: #cdd6e3;
  font-family: Consolas, monospace;
}

.marquee {
  position: absolute;
  border: 1px solid #7fb3ff;
  background: rgba(80, 140, 255, 0.18);
  pointer-events: none;
  z-index: 20;
}

.playhead {
  position: absolute;
  top: 0;
  bottom: 0;
  z-index: 30;
  width: 14px;
  margin-left: -7px;
  display: flex;
  flex-direction: column;
  align-items: center;
  pointer-events: auto;
  touch-action: none;
}

.playhead-handle {
  flex: 0 0 14px;
  width: 12px;
  background: #ffc107;
  border-radius: 2px 2px 0 0;
  box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.45);
  cursor: ew-resize;
}

.playhead-line {
  flex: 1;
  width: 2px;
  min-height: 0;
  background: #ffc107;
  box-shadow: 0 0 6px rgba(0, 0, 0, 0.85);
  cursor: ew-resize;
}

.hidden {
  display: none;
}

.hscroll-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 10px;
  padding: 6px 0;
}

.hscroll-label {
  flex: 0 0 auto;
  font-size: 12px;
  color: #8b96a8;
  width: 36px;
}

.hscroll-track {
  position: relative;
  flex: 1;
  min-width: 120px;
  height: 16px;
  border-radius: 8px;
  background: #1e242e;
  border: 1px solid #3a4556;
  cursor: pointer;
  touch-action: none;
}

.hscroll-thumb {
  position: absolute;
  top: 2px;
  height: 10px;
  border-radius: 5px;
  background: linear-gradient(180deg, #6b9fff, #3d6fd8);
  box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.35);
  cursor: grab;
  touch-action: none;
}

.hscroll-thumb:active {
  cursor: grabbing;
}
</style>
