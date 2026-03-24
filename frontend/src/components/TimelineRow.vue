<script setup>
defineProps({
  row: { type: Object, required: true },
  rowIndex: { type: Number, required: true },
  timelineHeaderHeight: { type: Number, required: true },
  timelineHeightPerRow: { type: Number, required: true },
  isRowSelected: { type: Function, required: true },
  toggleRowSelection: { type: Function, required: true },
  isSelectedSegment: { type: Function, required: true },
  segmentStyle: { type: Function, required: true },
  previewStyle: { type: Function, required: true },
  displayFrameValue: { type: Function, required: true },
  scheduleSave: { type: Function, required: true },
  removeRow: { type: Function, required: true },
  startSegmentDrag: { type: Function, required: true },
  onSegmentClick: { type: Function, required: true },
  startSegmentResize: { type: Function, required: true },
});
</script>

<template>
  <div
    class="row"
    :style="{
      top: `${timelineHeaderHeight + rowIndex * timelineHeightPerRow}px`,
      height: `${timelineHeightPerRow - 8}px`,
    }"
  >
    <div class="row-meta">
      <input
        class="row-select"
        type="checkbox"
        :checked="isRowSelected(row.id)"
        :disabled="!row.segments.length"
        @click.stop
        @change="toggleRowSelection(row.id, $event.target.checked)"
      />
      <input v-model="row.name" class="row-name" @change="scheduleSave" />
      <button class="danger" @click.stop="removeRow(row.id)">删除行</button>
    </div>

    <div class="row-track">
      <div
        v-for="seg in row.segments"
        :key="seg.id"
        class="segment"
        :class="{ selected: isSelectedSegment(row.id, seg.id) }"
        :style="segmentStyle(row, seg)"
        :title="seg.note ? `备注：${seg.note}` : '无备注'"
        @pointerdown.stop="startSegmentDrag(row.id, seg.id, $event)"
        @click.stop="onSegmentClick(row.id, seg.id, seg.startFrame, $event.ctrlKey || $event.metaKey)"
      >
        <span v-if="seg.note" class="segment-note">{{ seg.note }}</span>
        <div
          v-if="isSelectedSegment(row.id, seg.id)"
          class="segment-handle left"
          title="拖动左缘"
          @pointerdown.stop="startSegmentResize(row.id, seg.id, 'left', $event)"
        ></div>
        <span class="segment-text"
          >F{{ displayFrameValue(seg.startFrame) }}-{{ displayFrameValue(seg.endFrame) }}</span
        >
        <div
          v-if="isSelectedSegment(row.id, seg.id)"
          class="segment-handle right"
          title="拖动右缘"
          @pointerdown.stop="startSegmentResize(row.id, seg.id, 'right', $event)"
        ></div>
      </div>
      <div v-if="previewStyle(row.id)" class="segment preview" :style="previewStyle(row.id)"></div>
    </div>
  </div>
</template>

<style scoped>
.row {
  position: absolute;
  left: 0;
  right: 0;
  padding: 4px 8px;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  gap: 10px;
}

.row-meta {
  display: flex;
  gap: 8px;
  align-items: center;
  width: 250px;
  flex: 0 0 250px;
}

.row-select {
  width: 16px;
  height: 16px;
  margin: 0;
  accent-color: #4f9bff;
}

.row-track {
  position: relative;
  flex: 1;
  height: 28px;
  border-radius: 0;
  background: rgba(255, 255, 255, 0.06);
  cursor: crosshair;
  overflow: hidden;
}

.row-name {
  width: 170px;
  background: #0d0f14;
  border: 1px solid #2f3745;
  color: #f5f8ff;
  border-radius: 6px;
  padding: 5px 8px;
}

.segment {
  position: absolute;
  top: 0;
  bottom: 0;
  color: #111;
  border-radius: 0;
  padding: 0 2px;
  display: flex;
  align-items: center;
  box-sizing: border-box;
  cursor: grab;
  overflow: hidden;
}

.segment:active {
  cursor: grabbing;
}

.segment-text {
  position: relative;
  z-index: 1;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
  text-align: center;
  padding-top: 10px;
  pointer-events: none;
}

.segment-note {
  position: absolute;
  top: 1px;
  left: 10px;
  z-index: 3;
  max-width: calc(100% - 12px);
  font-size: 11px;
  line-height: 1;
  color: #111;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  text-shadow: 0 1px 0 rgba(255, 255, 255, 0.45);
  pointer-events: none;
}

.segment.selected {
  outline: 2px solid #fff;
  outline-offset: -2px;
}

.segment-handle {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 8px;
  z-index: 2;
  flex-shrink: 0;
  background: rgba(255, 255, 255, 0.35);
  cursor: ew-resize;
  touch-action: none;
}

.segment-handle:hover {
  background: rgba(255, 255, 255, 0.55);
}

.segment-handle.left {
  left: 0;
}

.segment-handle.right {
  right: 0;
}

.segment.preview {
  pointer-events: none;
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
</style>
