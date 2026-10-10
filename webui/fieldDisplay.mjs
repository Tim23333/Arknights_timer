/**
 * Owns short, explicitly last-known presentation of failed entity fields.
 * Only the WebUI table is smoothed: canonical payloads, details and WS stay raw.
 * Successful values update immediately. A failure may reuse its own last valid
 * value for 500ms, never renewing its deadline or assigning a newer source frame.
 * Session/policy/format changes, disabled fields and source stops clear the cache.
 */
export function createFieldDisplay() {
  const holdMs = 500;
  const cache = new Map();
  let scope = null, lastRows = [], lastRowsAt = -Infinity;
  let lastPayload = null, sampleAt = -Infinity;

  return {
    project(payload, context, columns, valueOf, now = performance.now()) {
      // Table toggles, pagination and expiry timers are not producer samples.
      // Only a newly received payload can advance the cache's arrival time.
      if (payload !== lastPayload) { sampleAt = now; lastPayload = payload; }
      const meta = payload?.meta || {};
      const generation = meta.policyGeneration ?? context.policy.generation;
      const nextScope = JSON.stringify([meta.sessionId, generation, context.precision]);
      const stopped = ['source_stopped', 'session_changed', 'adb_changed'].includes(meta.reason)
        || meta.collectionState === 'not_collected';
      const eligible = typeof meta.sessionId === 'string' && !stopped
        && generation === context.policy.generation;
      if (nextScope !== scope || !eligible) {
        cache.clear(); lastRows = []; lastRowsAt = -Infinity; scope = nextScope;
      }
      const failedBatch = meta.collectionState === 'unavailable' || meta.frameConsistent === false;
      const rows = failedBatch && eligible && now - lastRowsAt < holdMs
        ? lastRows : payload?.items || [];
      if (!failedBatch) {
        const ids = new Set(rows.map(row => String(row.id)));
        for (const id of cache.keys()) if (!ids.has(id)) cache.delete(id);
        if (eligible) { lastRows = rows; lastRowsAt = sampleAt; }
      }
      const policies = new Map(context.policy.fields.map(field => [field.id, field]));
      const cells = new Map();
      let heldCount = 0, expiresAt = null;
      for (const [index, row] of rows.entries()) {
        const id = String(row.id);
        const previous = cache.get(id) || new Map();
        const rowCells = new Map();
        if (eligible) cache.set(id, previous);
        for (const column of columns) {
          if (['row', 'detail', 'history'].includes(column.key)) continue;
          const fieldId = `${context.kind}.${column.key}`;
          const field = policies.get(fieldId);
          const record = row.fieldStates?.[fieldId] || {};
          const state = record.collectionState || record.state;
          const text = String(valueOf(row, column, index));
          const disabled = field?.collect === false || field?.display === false || state === 'not_collected';
          const unavailable = failedBatch || state === 'unavailable' || text === '—'
            || text.startsWith('不可用');
          // Explicit null means this field has no observed source frame (e.g.
          // verified static identity). Do not relabel it as the batch frame.
          const sourceFrame = 'sourceFrame' in record ? record.sourceFrame : meta.sourceFrame ?? null;
          let cell = {text, title:text, freshness:state || 'current'};
          if (disabled) {
            previous.delete(column.key);
            cell = {text:field?.display === false ? '未展示' : '未采集', title:'字段已关闭，不保留旧值', freshness:'not_collected'};
          } else if (unavailable) {
            const known = previous.get(column.key);
            if (eligible && known && now - known.at < holdMs) {
              cell = {text:known.text, freshness:'last_known',
                title:`${known.text} · 最后有效值（非当前值） · 来源帧 ${known.frame ?? '—'} · 当前读取失败：${record.reason || meta.reason || '本次采样不可用'}`};
              heldCount++;
              expiresAt = Math.min(expiresAt ?? Infinity, known.at + holdMs);
            } else {
              previous.delete(column.key);
              cell = {text:'不可用', title:'本次读取不可用，且没有500ms内的有效读数', freshness:'unavailable'};
            }
          } else {
            if (eligible) previous.set(column.key, {text, frame:sourceFrame, at:sampleAt});
            cell.title = `${text} · ${state === 'historical' ? '历史读数' : state === 'static' ? '已验证静态数据' : '当前有效读数'} · 来源帧 ${sourceFrame ?? '—'}`;
          }
          rowCells.set(column.key, cell);
        }
        cells.set(id, rowCells);
      }
      return {rows, heldCount, expiresAt,
        cell:(row, column, index) => cells.get(String(row.id))?.get(column.key) ?? valueOf(row, column, index)};
    },
  };
}
