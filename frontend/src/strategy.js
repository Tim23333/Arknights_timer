export const FPS = 60;

export function uid() {
  return globalThis.crypto?.randomUUID?.() || `id-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export const ACTION_TYPES = {
  deploy: "部署",
  skill: "技能",
  withdraw: "撤退",
};

export function categoryFromActionType(value) {
  const text = String(value || "").toLowerCase();
  if (text === "部署" || text === "deploy" || text === "0") return "deploy";
  if (text === "技能" || text === "skill" || text === "1") return "skill";
  if (text === "撤退" || text === "withdraw" || text === "retreat" || text === "2") return "withdraw";
  return "deploy";
}

export function emptyGroups() {
  return { deploy: [], skill: [], withdraw: [] };
}

export function classifyTile(key, heightType, passableMask) {
  const tileKey = String(key || "").toLowerCase();
  if (["tile_start", "tile_flystart", "tile_enemygoal"].includes(tileKey)) return "enemy_spawn";
  if (["tile_end", "tile_allygoal"].includes(tileKey)) return "friendly_goal";
  if (tileKey === "tile_telin") return "teleport_in";
  if (tileKey === "tile_telout") return "teleport_out";
  if (tileKey === "tile_hole") return "hole";
  if (["tile_empty", "tile_forbidden"].includes(tileKey)) return "forbidden";
  if (tileKey === "tile_wall" || Number(heightType) === 1) return "highland";
  const common = new Set(["tile_floor", "tile_road", ""]);
  if (!common.has(tileKey)) return "device";
  if (Number(passableMask) === 0) return "obstacle";
  return "ground";
}

function normalizeBackendMap(source = {}) {
  const rows = Math.max(0, Number(source.rows) || 0);
  const cols = Math.max(0, Number(source.cols) || 0);
  const tiles = (source.tiles || []).map((tile, index) => ({
    ...tile,
    row: Number.isFinite(Number(tile.row)) ? Number(tile.row) : Math.floor(index / Math.max(1, cols)),
    col: Number.isFinite(Number(tile.col)) ? Number(tile.col) : index % Math.max(1, cols),
    tileKey: tile.tileKey || tile.key || "tile_empty",
    category: tile.category || classifyTile(tile.tileKey || tile.key, tile.heightType, tile.passableMask),
  }));
  return {
    mapId: source.mapId || "",
    rows,
    cols,
    tiles,
    blockEdges: Array.isArray(source.blockEdges) ? source.blockEdges : [],
    devices: Array.isArray(source.devices) ? source.devices : [],
    tags: Array.isArray(source.tags) ? source.tags : [],
  };
}

function normalizeRawLevelMap(payload) {
  const mapData = payload.mapData || {};
  const matrix = mapData.map || {};
  const rows = Math.max(0, Number(matrix.rows) || 0);
  const cols = Math.max(0, Number(matrix.cols) || 0);
  const definitions = Array.isArray(mapData.tiles) ? mapData.tiles : [];
  const cells = Array.isArray(matrix.cells) ? matrix.cells : [];
  const tiles = cells.map((tileIndex, index) => {
    const source = definitions[Number(tileIndex)] || {};
    return {
      ...source,
      tileIndex,
      // FlatBuffer 导出的 cells 按画面从上到下排列，而游戏坐标 row=0 在底部。
      row: Math.max(0, rows - 1 - Math.floor(index / Math.max(1, cols))),
      col: index % Math.max(1, cols),
      tileKey: source.tileKey || "tile_empty",
      category: classifyTile(source.tileKey, source.heightType, source.passableMask),
    };
  });
  return normalizeBackendMap({ mapId: payload.mapId, rows, cols, tiles });
}

function enumName(value, fallback = "") {
  if (value && typeof value === "object") return value.name || fallback;
  return typeof value === "string" ? value : fallback;
}

function normalizeRawRoutes(routes = []) {
  return routes.map((route, index) => ({
    index,
    isExtra: false,
    motionMode: Number(route.motionMode?.value ?? route.motionMode ?? 0),
    motionModeName: enumName(route.motionMode, "WALK"),
    start: route.startPosition || { row: 0, col: 0 },
    end: route.endPosition || { row: 0, col: 0 },
    spawnRandomRange: route.spawnRandomRange || { x: 0, y: 0 },
    spawnOffset: route.spawnOffset || { x: 0, y: 0 },
    allowDiagonalMove: Boolean(route.allowDiagonalMove),
    checkpoints: (route.checkpoints || []).map((checkpoint) => ({
      type: Number(checkpoint.type?.value ?? checkpoint.type ?? 0),
      typeName: enumName(checkpoint.type, "MOVE"),
      time: Number(checkpoint.time) || 0,
      position: checkpoint.position || { row: 0, col: 0 },
      reachOffset: checkpoint.reachOffset || { x: 0, y: 0 },
      randomizeReachOffset: Boolean(checkpoint.randomizeReachOffset),
      reachDistance: Number(checkpoint.reachDistance) || 0,
    })),
  }));
}

function normalizeEnemy(enemy, index) {
  const start = Number(enemy.startFrame);
  const end = Number(enemy.endFrame);
  return {
    ...enemy,
    id: String(enemy.id === undefined || enemy.id === null || enemy.id === ""
      ? `enemy-${index}-${uid()}` : enemy.id),
    order: Number(enemy.order) || index + 1,
    enemyId: enemy.enemyId || enemy.key || "",
    name: enemy.name || enemy.enemyId || enemy.key || "未知敌人",
    kind: enemy.kind || "scheduled",
    wave: Number.isFinite(Number(enemy.wave)) ? Number(enemy.wave) : -1,
    fragment: Number.isFinite(Number(enemy.fragment)) ? Number(enemy.fragment) : -1,
    routeIndex: Number.isFinite(Number(enemy.routeIndex)) ? Number(enemy.routeIndex) : -1,
    startFrame: Number.isFinite(start) && start >= 0 ? Math.round(start) : null,
    endFrame: Number.isFinite(end) && end >= 0 ? Math.round(end) : null,
    endReason: enemy.endReason || "",
    note: enemy.note || "",
  };
}

function expandRawWaves(payload) {
  const enemies = [];
  let waveTime = 0;
  let order = 0;
  for (const [waveIndex, wave] of (payload.waves || []).entries()) {
    const waveStart = waveTime + (Number(wave.preDelay) || 0);
    let waveEnd = waveStart;
    for (const [fragmentIndex, fragment] of (wave.fragments || []).entries()) {
      const fragmentStart = waveStart + (Number(fragment.preDelay) || 0);
      for (const [actionIndex, action] of (fragment.actions || []).entries()) {
        if (enumName(action.actionType, "SPAWN") !== "SPAWN") continue;
        const count = Math.max(1, Number(action.count) || 1);
        for (let spawnIndex = 0; spawnIndex < count; spawnIndex += 1) {
          const seconds = fragmentStart + (Number(action.preDelay) || 0) + spawnIndex * (Number(action.interval) || 0);
          waveEnd = Math.max(waveEnd, seconds);
          order += 1;
          enemies.push(normalizeEnemy({
            id: `raw-${waveIndex}-${fragmentIndex}-${actionIndex}-${spawnIndex}`,
            order,
            enemyId: action.key || "",
            name: action.key || "未知敌人",
            kind: action.hiddenGroup || action.randomSpawnGroupKey ? "conditional" : "scheduled",
            condition: action.randomSpawnGroupKey ? `随机组 ${action.randomSpawnGroupKey}` : "",
            wave: waveIndex,
            fragment: fragmentIndex,
            action: actionIndex,
            spawnIndex,
            routeIndex: Number(action.routeIndex) || 0,
            startTime: seconds,
            startFrame: Math.round(seconds * FPS),
            randomSpawnGroup: action.randomSpawnGroupKey || "",
            randomSpawnPack: action.randomSpawnGroupPackKey || "",
          }, enemies.length));
        }
      }
    }
    waveTime = waveEnd + (Number(wave.postDelay) || 0);
  }
  return enemies;
}

export function normalizeStagePackage(payload = {}) {
  const isRawLevel = Boolean(payload.mapData && payload.waves);
  const map = isRawLevel ? normalizeRawLevelMap(payload) : normalizeBackendMap(payload.map || {});
  const routes = isRawLevel ? normalizeRawRoutes(payload.routes || []) : (payload.routes || []);
  const enemies = isRawLevel ? expandRawWaves(payload) : (payload.enemySpawns || []).map(normalizeEnemy);
  const stageSource = payload.stage || {};
  return {
    schema: "arknights-stage-strategy",
    schemaVersion: 1,
    timeline: { fps: FPS, ...(payload.timeline || {}) },
    stage: {
      stageId: stageSource.stageId || "",
      levelId: stageSource.levelId || payload.levelId || payload._meta?.levelId || "",
      code: stageSource.code || "",
      name: stageSource.name || "",
      mapId: stageSource.mapId || payload.mapId || map.mapId || "",
    },
    map,
    routes,
    enemyKinds: payload.enemyKinds || {},
    enemySpawns: enemies,
    operatorActions: Array.isArray(payload.operatorActions) ? payload.operatorActions : [],
  };
}

export function groupsFromActions(actions = []) {
  const groups = emptyGroups();
  const index = new Map();
  for (const source of actions) {
    const category = categoryFromActionType(source.action_type ?? source.actionType ?? source.op);
    const oper = String(source.oper || source.operator || "未知干员");
    const key = `${category}:${oper}`;
    let row = index.get(key);
    if (!row) {
      row = { id: uid(), oper, actions: [] };
      index.set(key, row);
      groups[category].push(row);
    }
    const frame = source.frame === null || source.frame === "" || source.frame === undefined
      ? null : Number(source.frame);
    row.actions.push({
      id: uid(),
      frame: Number.isFinite(frame) && frame >= 0 ? Math.round(frame) : null,
      pos: source.pos || "",
      direction: source.direction || "",
      note: source.note || "",
    });
  }
  for (const rows of Object.values(groups)) {
    for (const row of rows) row.actions.sort((a, b) => {
      if (a.frame === null) return b.frame === null ? 0 : 1;
      if (b.frame === null) return -1;
      return a.frame - b.frame;
    });
  }
  return groups;
}

export function groupsFromLegacyRows(rows = []) {
  const actions = [];
  for (const row of rows) {
    for (const segment of row.segments || row.items || []) {
      const note = String(segment.note || "");
      const parts = note.split("_");
      const category = categoryFromActionType(row.category || segment.actionType || parts[0]);
      const frame = Number(segment.startFrame ?? segment.frame);
      actions.push({
        action_type: ACTION_TYPES[category],
        oper: row.name || row.oper || "未知干员",
        frame: Number.isFinite(frame) ? frame : 0,
        pos: segment.pos || parts[1] || "",
        direction: segment.direction || parts[2] || "",
        note: segment.note || "",
      });
    }
  }
  return groupsFromActions(actions);
}

export function actionsFromGroups(groups) {
  const actions = [];
  for (const [category, rows] of Object.entries(groups)) {
    for (const row of rows || []) {
      for (const item of row.actions || []) {
        const rawFrame = item.frame === null || item.frame === "" || item.frame === undefined
          ? null : Number(item.frame);
        const action = {
          action_type: ACTION_TYPES[category],
          frame: Number.isFinite(rawFrame) ? Math.max(0, Math.round(rawFrame)) : null,
          oper: row.oper || "",
          pos: item.pos || "",
        };
        if (category === "deploy" && item.direction) action.direction = item.direction;
        actions.push(action);
      }
    }
  }
  return actions.sort((a, b) => {
    if (a.frame === null && b.frame !== null) return 1;
    if (a.frame !== null && b.frame === null) return -1;
    return (a.frame ?? 0) - (b.frame ?? 0) || a.action_type.localeCompare(b.action_type);
  });
}
