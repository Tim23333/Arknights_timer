/** Shared rendering/probe rules, independent of DOM and network lifecycles. */
export function formatValue(value, precision = 2) {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") return Number.isFinite(value) ? (Number.isInteger(value) ? String(value) : value.toFixed(precision)) : "—";
  if (typeof value === "boolean") return value ? "是" : "否";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export function formatClock(seconds) {
  if (typeof seconds !== "number" || !Number.isFinite(seconds)) return "—";
  // Display sampled centiseconds, not interpolated time. Truncate to avoid
  // rounding 59.999s into an impossible 00:60.00 before the next actual sample.
  const ticks = Math.floor(Math.max(0, seconds) * 100);
  return `${Math.floor(ticks / 6000).toString().padStart(2, "0")}:${((ticks % 6000) / 100).toFixed(2).padStart(5, "0")}`;
}

// Same palette as backend/app/character_ui.py's lightweight desktop pie chart.
const overviewColors = ['#4f8cff', '#55c271', '#ffad42', '#ed5f5f', '#9b72e8', '#35b7bd',
  '#e979b7', '#8caa3f', '#d17a45', '#6e8fd5', '#48a07a', '#b574d1', '#d3a52f', '#5ba3c9', '#c26d70', '#7f95a8'];

/**
 * Derives pie sectors and an accessible legend from backend-merged statistics.
 * Use when: showing cumulative damage or healing, not summing entity instances.
 * Expects: numeric cumulative values or null for unknown/disabled values.
 * Returns: sorted known rows, percentage boundaries, total and missing count.
 */
export function pieData(rows, metric) {
  const known = rows.filter(row => Number.isFinite(row[metric]) && row[metric] >= 0)
    .map(row => ({id: row.id, name: row.name, value: row[metric]}))
    .sort((a, b) => b.value - a.value || a.name.localeCompare(b.name, 'zh-CN'));
  const total = known.reduce((sum, row) => sum + row.value, 0);
  let end = 0;
  return {total, missing: rows.length - known.length, rows: known.map((row, index) => {
    const start = end, ratio = total > 0 ? row.value / total * 100 : 0;
    end += ratio;
    return {...row, ratio, start, end, color: overviewColors[index % overviewColors.length]};
  })};
}

/** Labels for BattleLogger events plus the timer provider's optional frame match. */
const deployLabels = {
  timestamp: '时间（秒）', frame: '逻辑帧', op: '操作', charName: '干员',
  direction: '朝向', gridCol: '位置列', gridRow: '位置行', extraInfo: '附加信息',
  uniqueId: '干员唯一标识', charInstId: '干员实例标识', charId: '干员标识',
  opName: '操作名称', directionName: '朝向名称', frameSource: '逻辑帧匹配来源',
  frameSampleTime: '匹配采样时间（秒）', frameTimeDelta: '匹配时间差（秒）',
};
const operationNames = new Map([[0, '部署'], [1, '撤退'], [2, '技能'], [3, '作弊'],
  ['SPAWN', '部署'], ['WITHDRAW', '撤退'], ['SKILL', '技能'], ['CHEAT', '作弊']]);
const directionNames = new Map([[0, '上'], [1, '右'], [2, '下'], [3, '左'], [4, '无'],
  ['UP', '上'], ['RIGHT', '右'], ['DOWN', '下'], ['LEFT', '左'], ['NONE', '无']]);
const frameSources = new Map([['timerCacheExact', '计时器缓存精确匹配'], ['timerCacheInterpolated', '计时器缓存插值匹配']]);

/**
 * Projects stage-topic wrappers and operation events into Chinese UI data.
 *
 * Use when: rendering the local stage/operation view, never for protocol export.
 * Expects: the stage topic contains stage/squad/meta; deploy contains events.
 * Returns: scalar stage facts and a non-mutating, full event display projection.
 * Missing values stay unknown; future keys are retained with an explicit label.
 */
export function deployView(stagePayload = {}, deployPayload = {}) {
  const stage = stagePayload.stage || {};
  const facts = [['code', '关卡编号'], ['name', '关卡名称'], ['stageId', '关卡标识'], ['levelId', '关卡资源标识']]
    .map(([key, label]) => ({key, label, value: formatValue(stage[key])}));
  const events = deployPayload.events || [];
  const keys = [...new Set(['timestamp', 'frame', 'op', 'charName', 'direction', 'gridCol', 'gridRow', 'extraInfo',
    ...events.flatMap(event => Object.keys(event))])];
  const columns = keys.map(key => ({key, label: Object.hasOwn(deployLabels, key) ? deployLabels[key] : `未识别字段（${key}）`}));
  const squad = stagePayload.squad || [];
  const instanceNames = new Map(squad.filter(item => item.charInstId != null && item.charName).map(item => [item.charInstId, item.charName]));
  const characterNames = new Map(squad.filter(item => item.charId && item.charName).map(item => [item.charId, item.charName]));
  const rows = events.map((event, index) => {
    const values = Object.fromEntries(keys.map(key => {
      const value = event[key];
      if (key === 'charName') return [key, event.charName || instanceNames.get(event.charInstId ?? event.uniqueId) || characterNames.get(event.charId) || event.charId || '—'];
      if (key === 'frame' && value == null) return [key, '不可用（无对应时钟采样）'];
      if (value == null) return [key, '—'];
      if (key === 'op' || key === 'opName') return [key, operationNames.get(value) ?? `未知操作（${formatValue(value)}）`];
      if (key === 'direction' || key === 'directionName') return [key, directionNames.get(value) ?? `未知朝向（${formatValue(value)}）`];
      if (key === 'frame') return [key, `F${formatValue(value)}`];
      if (key === 'timestamp' && Number.isFinite(value)) return [key, value.toFixed(3)];
      if (['frameSampleTime', 'frameTimeDelta'].includes(key) && Number.isFinite(value)) return [key, value.toFixed(6)];
      if (key === 'frameSource') return [key, frameSources.get(value) ?? formatValue(value)];
      return [key, formatValue(value)];
    }));
    // uniqueId identifies an operator, not an event: deployments and skills can
    // share it. A position in the ordered event list keeps each record distinct.
    return {id: `event:${index}`, values};
  });
  return {facts, columns, rows};
}

// Entity.FinishReason enum; it is not the unrelated Ability.FinishReason enum.
const finishReasons = ['未结束', '到达出口', '生命归零', '坠落', '撤退／撤出', '死亡式撤出', '静默撤出',
  '其他原因', '无伤害来源的生命归零', '被替换', '自身重生', '自身移动式重生', '外部移动式重生'];

/**
 * Projects departed roster entries without reading recycled game objects.
 * Use when: rendering historical enemies separately from the live table.
 * Expects: policy-projected entities and per-field sampling states.
 * Returns: filtered rows and last observed values; unknown departure is not death.
 */
export function departedView(items = [], filter = 'all') {
  const departed = items.filter(item => item.lifecycle === 'departed');
  // Never reconstruct raw codes from the lossy endReason summary. Ignore stale
  // values explicitly invalidated by field policy or a failed memory read.
  const rawReason = item => Number.isInteger(item.finishReason) &&
    !['not_collected', 'unavailable'].includes(item.fieldStates?.['enemy.finish_reason']?.collectionState)
    ? item.finishReason : null;
  const isDeath = item => item.endReason === 'death' || [2, 8].includes(rawReason(item));
  const rows = departed.filter(item => filter === 'all' ||
    (filter === 'death' ? isDeath(item) : filter === 'other' ? !isDeath(item) :
      filter === 'unknown' ? rawReason(item) === null : filter === `finish:${rawReason(item)}`))
    .map(item => {
      const sampled = key => ['current', 'historical'].includes(item.fieldStates?.[`enemy.${key}`]?.collectionState);
      const raw = rawReason(item);
      // A terminal state can be observed before the finish flag changes from
      // NONE. Keep that confirmed classification; the raw column still shows 0.
      const reason = raw === 0 && item.endReason === 'death' ? '已确认阵亡' :
        raw === 0 && item.endReason === 'reach_exit' ? '进入目标点' :
        raw !== null ? finishReasons[raw] ?? `未知离场类型（${raw}）` :
        item.endReason === 'death' ? '已确认阵亡' :
        item.endReason === 'reach_exit' ? '进入目标点' :
        !item.endReason || item.endReason === 'departed' ? '离场原因未知' : `其他离场（${item.endReason}）`;
      return {id: item.id, item, values: {
        name: formatValue(item.name), code: formatValue(item.code), enemyId: formatValue(item.enemyId), reason,
        finishReason: raw === null ? '未观测' : String(raw),
        endFrame: item.endFrame == null ? '未观测' : `F${item.endFrame}`,
        hp: sampled('hp') ? item.columns?.hp ?? (Number.isFinite(item.hp) && Number.isFinite(item.maxHp) ? `${item.hp}/${item.maxHp}` : '不可用') : '不可用',
        position: sampled('pos') ? item.columns?.pos ?? formatValue(item.position) : '不可用',
        hpFrame: sampled('hp') && item.fieldStates['enemy.hp'].sourceFrame != null ? `F${item.fieldStates['enemy.hp'].sourceFrame}` : '未观测',
        positionFrame: sampled('pos') && item.fieldStates['enemy.pos'].sourceFrame != null ? `F${item.fieldStates['enemy.pos'].sourceFrame}` : '未观测',
      }};
    }).sort((a, b) => (b.item.endFrame ?? -1) - (a.item.endFrame ?? -1));
  return {total: departed.length, rows};
}

/** Resolve registered dotted paths; [] fans out but an empty field array is valid. */
export function pathValues(data, path) {
  const parts = path.replace(/^\$\./, "").split(".").filter(Boolean);
  let values = [data];
  for (let index = 0; index < parts.length; index++) {
    const expand = parts[index].endsWith("[]");
    const key = expand ? parts[index].slice(0, -2) : parts[index];
    const next = [];
    for (const value of values) {
      if (value === null || typeof value !== "object") continue;
      if (key === "*") { next.push(...Object.values(value)); continue; }
      if (!(key in value)) continue;
      const child = value[key];
      if (expand && Array.isArray(child)) next.push(...child);
      else if (!expand) next.push(child);
    }
    values = next;
  }
  return values;
}

export function fieldTopic(field) {
  return field.topic || ({enemy: "enemies", character: "characters", timer: "battle", battle: "battle", detail_enemy: "enemy_detail", detail_character: "character_detail"})[field.domain] || field.domain;
}

export function assessField(field, data) {
  if (!field.collect) return {status: "not_collected", text: "未采集"};
  const metadata = data?.fieldStates?.[field.id] || data?.meta?.fields?.[field.id];
  const collection = metadata?.collectionState || metadata?.state;
  if (["not_collected", "unavailable"].includes(collection)) return {status: collection, text: metadata.reason || (collection === "not_collected" ? "未采集" : "读取不可用")};
  const topic = fieldTopic(field);
  const paths = field.paths || [];
  const entityDomain = ["enemy", "character", "enemy_detail", "character_detail"].includes(field.domain);
  const entities = (data?.items || []).filter(item => {
    const record = item.fieldStates?.[field.id];
    return !["unavailable", "not_collected"].includes(record?.collectionState || record?.state);
  });
  if (entityDomain && data?.items?.length && !entities.length) return {status: "unavailable", text: "所有对象的该字段均不可用或未采集"};
  const values = paths.flatMap(path => {
    const relative = path.startsWith(topic + ".") ? path.slice(topic.length + 1) : path;
    if (entityDomain && !relative.startsWith("items[]")) return entities.flatMap(item => pathValues(item, relative));
    return pathValues(entityDomain ? {...data, items: entities} : data, relative);
  });
  // Null and absent keys are not proof of reachability. Zero/false/empty lists are.
  if (values.some(value => value !== null && value !== undefined)) return {status: "received", text: "已收到有效值"};
  if (Array.isArray(data?.items) && !data.items.length) return {status: "no_entities", text: "当前无对象，未验证"};
  return {status: "unavailable", text: "主题已收到，字段未获得有效值"};
}

/** Merge server-owned registry metadata with the current persisted switches. */
export function policyFields(policy) {
  if (Array.isArray(policy.fields)) return policy;
  return {...policy, fields: (policy.registry || []).map(spec => ({...spec, ...(policy.fields?.[spec.id] || spec.defaults)}))};
}

/** Projects sampling status and frame values for independent stable UI slots. */
export function metaParts(meta) {
  const state = meta?.collectionState || meta?.state;
  const status = ({current: "本次读取成功", static: "已验证静态数据", historical: "最后已知历史值", unavailable: "读取不可用", not_collected: "未采集", last_known: "最后已知值"})[state] || "来源状态待确认";
  return {status, source:String(meta?.sourceFrame ?? '—'), latest:String(meta?.latestKnownFrame ?? '—')};
}

export function metaLabel(meta = {}) {
  const {status, source, latest} = metaParts(meta);
  return `${status} · 来源帧 ${source} · 最近已知帧 ${latest}`;
}
