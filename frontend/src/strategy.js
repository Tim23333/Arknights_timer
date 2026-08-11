export const FPS = 30;

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
  // 游戏原生关卡 JSON 的 map 二维数组首行 = 画面顶部（与内存 short[,] 一致）；
  // 部分 FlatBuffer 导出则给 {rows, cols, cells} 扁平结构，两种都兼容。
  let rows = 0;
  let cols = 0;
  let cells = [];
  if (Array.isArray(matrix)) {
    rows = matrix.length;
    cols = matrix.reduce((max, row) => Math.max(max, Array.isArray(row) ? row.length : 0), 0);
    cells = matrix.flatMap((row) => (Array.isArray(row) ? row : []));
  } else {
    rows = Math.max(0, Number(matrix.rows) || 0);
    cols = Math.max(0, Number(matrix.cols) || 0);
    cells = Array.isArray(matrix.cells) ? matrix.cells : [];
  }
  const definitions = Array.isArray(mapData.tiles) ? mapData.tiles : [];
  const tiles = cells.map((tileIndex, index) => {
    const source = definitions[Number(tileIndex)] || {};
    return {
      ...source,
      tileIndex,
      // cells 首行 = 画面顶部，与瓦片/地图显示一致。
      // 注意：路线等 GridPosition 坐标相反（row 0 = 底部），在 normalizeStagePackage 统一翻转。
      row: Math.floor(index / Math.max(1, cols)),
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
  const pkg = {
    schema: "arknights-stage-strategy",
    schemaVersion: 1,
    // 位置坐标已翻转为 row 0 = 画面顶部的标记；工作区再导出会带上它，
    // 再导入时跳过翻转，不会重复。
    positionsTopBased: true,
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
  if (!payload.positionsTopBased) flipPositionRows(pkg);
  return pkg;
}

/**
 * 游戏 GridPosition（路线起终点/检查点、装置、出生格、部署坐标等）row 0 = 画面
 * 底部，而地图瓦片数组 row 0 = 画面顶部（5-10 红门与路线起点实测：翻转后 6/6
 * 起点落在 tile_start）。导入时统一把位置坐标翻转到顶部基准，与瓦片对齐。
 * F9 记谱（行字母从顶部数）本身是顶部基准，不翻。
 */
function flipPositionRows(pkg) {
  const rows = Number(pkg.map?.rows) || 0;
  if (rows <= 0) return;
  const flip = (value) => {
    const n = Number(value);
    return Number.isFinite(n) ? rows - 1 - n : value;
  };
  const flipPoint = (point) => (point ? { ...point, row: flip(point.row) } : point);
  pkg.routes = (pkg.routes || []).map((route) => ({
    ...route,
    start: flipPoint(route.start),
    end: flipPoint(route.end),
    checkpoints: (route.checkpoints || []).map((checkpoint) => ({
      ...checkpoint,
      position: flipPoint(checkpoint.position),
    })),
  }));
  pkg.map = {
    ...pkg.map,
    devices: (pkg.map.devices || []).map((device) => ({ ...device, row: flip(device.row) })),
    blockEdges: (pkg.map.blockEdges || []).map((edge) => ({ ...edge, row: flip(edge.row) })),
  };
  const flipPosString = (pos) => {
    const text = String(pos || "").trim();
    const match = text.match(/^\(?\s*(\d+)\s*[,，]\s*(\d+)\s*\)?$/);
    if (!match) return pos;
    return `(${match[1]},${rows - 1 - Number(match[2])})`;
  };
  pkg.enemySpawns = (pkg.enemySpawns || []).map((enemy) => (
    enemy.bornPos ? { ...enemy, bornPos: flipPosString(enemy.bornPos) } : enemy));
  pkg.operatorActions = (pkg.operatorActions || []).map((action) => (
    action.pos ? { ...action, pos: flipPosString(action.pos) } : action));
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


// ===== 路线行走模拟 / 坐标解析 / 播放状态推导 =====

export function finiteFrame(value) {
  const number = Number(value);
  return Number.isFinite(number) && number >= 0 ? Math.round(number) : null;
}

/** 解析格子文本：新格式 "(列,行)" 如 (8,5)；兼容旧记谱 F9（行字母+列数字）。 */
export function parseGridPos(pos) {
  const text = String(pos || "").trim();
  let match = text.match(/^\(?\s*(\d+)\s*[,，]\s*(\d+)\s*\)?$/);
  if (match) return { col: Number(match[1]), row: Number(match[2]) };
  match = text.match(/^([A-Za-z])\s*(\d+)$/);
  if (match) return { row: match[1].toUpperCase().charCodeAt(0) - 65, col: Number(match[2]) - 1 };
  return null;
}

const MOVE_TYPES = new Set(["MOVE", "PATROL_MOVE"]);
const TELEPORT_TYPES = new Set(["APPEAR_AT_POS", "MAP_OFFSET_MOVE"]);

// ===== 寻路（复刻游戏 SPFA 流场 + Bresenham 视线平滑，见 dump.cs SPFA 类）=====

const MOTION_FLY = 1;
const PASSABLE_BITS = { NONE: 0, WALK_ONLY: 1, FLY_ONLY: 2, ALL: 3 };
const WALKABLE_KEYS = new Set([
  "tile_road", "tile_floor", "tile_start", "tile_end",
  "tile_telin", "tile_telout", "tile_fence", "tile_fence_bound",
]);

/** 瓦片对该移动方式是否可通行（MotionMask：bit0=地面 bit1=飞行）。 */
export function tilePassable(tile, motionMode = 0) {
  if (!tile) return false;
  let mask = tile.passableMask;
  if (typeof mask === "string") mask = PASSABLE_BITS[mask];
  mask = Number(mask);
  if (Number.isFinite(mask)) return (mask & (motionMode === MOTION_FLY ? 2 : 1)) !== 0;
  const key = tile.tileKey || tile.key || "";
  if (WALKABLE_KEYS.has(key)) return true;
  if (key === "tile_hole") return motionMode === MOTION_FLY;
  return false;
}

function mapGrid(map) {
  const rows = Math.max(0, Number(map?.rows) || 0);
  const cols = Math.max(0, Number(map?.cols) || 0);
  const tiles = new Map();
  for (const tile of map?.tiles || []) tiles.set(`${tile.row}:${tile.col}`, tile);
  return { rows, cols, at: (row, col) => tiles.get(`${row}:${col}`) };
}

const ORTHO_DIRS = [[-1, 0], [1, 0], [0, -1], [0, 1]];
const DIAG_DIRS = [[-1, -1], [-1, 1], [1, -1], [1, 1]];

/**
 * 等权网格最短路（BFS，与游戏 SPFA 在等权地图上的结果一致）。
 * allowDiagonalMove 时对角步要求两侧正交格均可通行（禁穿墙角）。
 * 起终点强制视为可通行（红蓝门/传送门格）。不可达时返回 null。
 */
export function findTilePath(map, from, to, { motionMode = 0, allowDiagonalMove = false } = {}) {
  const grid = mapGrid(map);
  const start = { row: Math.round(Number(from?.row)), col: Math.round(Number(from?.col)) };
  const goal = { row: Math.round(Number(to?.row)), col: Math.round(Number(to?.col)) };
  if (!grid.rows || !grid.cols) return null;
  if (start.row === goal.row && start.col === goal.col) return [start];
  const inBounds = (row, col) => row >= 0 && row < grid.rows && col >= 0 && col < grid.cols;
  const isEnd = (row, col) => (row === start.row && col === start.col) || (row === goal.row && col === goal.col);
  const canPass = (row, col) => inBounds(row, col)
    && (isEnd(row, col) || tilePassable(grid.at(row, col), motionMode));
  if (!canPass(goal.row, goal.col)) return null;
  const key = (row, col) => row * grid.cols + col;
  const prev = new Map([[key(start.row, start.col), null]]);
  const queue = [start];
  for (let head = 0; head < queue.length; head += 1) {
    const cur = queue[head];
    if (cur.row === goal.row && cur.col === goal.col) break;
    const dirs = [...ORTHO_DIRS];
    if (allowDiagonalMove) {
      for (const [dr, dc] of DIAG_DIRS) {
        // 对角步要求两侧正交格均可通行，防止穿墙角
        if (canPass(cur.row + dr, cur.col) && canPass(cur.row, cur.col + dc)) dirs.push([dr, dc]);
      }
    }
    for (const [dr, dc] of dirs) {
      const nr = cur.row + dr;
      const nc = cur.col + dc;
      const nk = key(nr, nc);
      if (!canPass(nr, nc) || prev.has(nk)) continue;
      prev.set(nk, cur);
      queue.push({ row: nr, col: nc });
    }
  }
  if (!prev.has(key(goal.row, goal.col))) return null;
  const path = [];
  for (let cur = goal; cur; cur = prev.get(key(cur.row, cur.col))) path.unshift(cur);
  return path;
}

/**
 * 游戏 _PostprocessAndMakeNextMapSmoothly 对应的视线平滑：
 * 贪心跳向最远可视点；视线用超覆盖采样，途经格（含对角两侧）均可通行才算通畅。
 */
export function smoothPath(map, path, { motionMode = 0, endpoints = [] } = {}) {
  if (!Array.isArray(path) || path.length <= 2) return path ? [...(path || [])] : [];
  const grid = mapGrid(map);
  const forced = new Set(endpoints.map((p) => `${p.row}:${p.col}`));
  const canPass = (row, col) => row >= 0 && row < grid.rows && col >= 0 && col < grid.cols
    && (forced.has(`${row}:${col}`) || tilePassable(grid.at(row, col), motionMode));
  const losClear = (a, b) => {
    const span = Math.max(Math.abs(b.row - a.row), Math.abs(b.col - a.col));
    const steps = Math.max(1, Math.ceil(span * 8));
    let prev = { row: Math.floor(a.row + 0.5), col: Math.floor(a.col + 0.5) };
    if (!canPass(prev.row, prev.col)) return false;
    for (let i = 1; i <= steps; i += 1) {
      const row = a.row + 0.5 + ((b.row - a.row) * i) / steps;
      const col = a.col + 0.5 + ((b.col - a.col) * i) / steps;
      const cell = { row: Math.floor(row), col: Math.floor(col) };
      if (cell.row !== prev.row || cell.col !== prev.col) {
        if (cell.row !== prev.row && cell.col !== prev.col) {
          // 对角过渡：两侧正交格也要通畅（不许擦墙角）
          if (!canPass(cell.row, prev.col) || !canPass(prev.row, cell.col)) return false;
        }
        if (!canPass(cell.row, cell.col)) return false;
        prev = cell;
      }
    }
    return true;
  };
  const result = [path[0]];
  for (let i = 0; i < path.length - 1;) {
    let j = path.length - 1;
    while (j > i + 1 && !losClear(path[i], path[j])) j -= 1;
    result.push(path[j]);
    i = j;
  }
  return result;
}

function pathDistance(path) {
  let dist = 0;
  for (let i = 1; i < (path?.length || 0); i += 1) {
    dist += Math.hypot(path[i].row - path[i - 1].row, path[i].col - path[i - 1].col);
  }
  return dist;
}

/** 折线上行走 dist 格后的位置（线性插值）。 */
export function pointAlongPath(path, dist) {
  if (!path?.length) return null;
  let remaining = Math.max(0, Number(dist) || 0);
  for (let i = 1; i < path.length; i += 1) {
    const seg = Math.hypot(path[i].row - path[i - 1].row, path[i].col - path[i - 1].col);
    if (remaining <= seg && seg > 0) {
      const t = remaining / seg;
      return {
        row: path[i - 1].row + (path[i].row - path[i - 1].row) * t,
        col: path[i - 1].col + (path[i].col - path[i - 1].col) * t,
      };
    }
    remaining -= seg;
  }
  return { ...path[path.length - 1] };
}

/**
 * 生成一条路线的完整折线分段：start → 各检查点 → end，
 * 地面段逐段寻路+视线平滑；飞行/闪现段为直线（闪现建议虚线绘制）。
 * 返回 [{ type: "walk"|"fly"|"teleport", points: [{row,col}...] }]。
 */
export function computeRoutePath(route, map) {
  if (!route?.start) return [];
  const motionMode = Number(route.motionMode) === MOTION_FLY ? MOTION_FLY : 0;
  const norm = (p) => ({ row: Number(p?.row) || 0, col: Number(p?.col) || 0 });
  const keyPoints = [{ pos: norm(route.start), kind: "move" }];
  for (const checkpoint of route.checkpoints || []) {
    const typeName = String(checkpoint.typeName || "");
    const position = checkpoint.position;
    const hasPos = position && Number.isFinite(Number(position.row)) && Number.isFinite(Number(position.col));
    if (!hasPos) continue;
    if (MOVE_TYPES.has(typeName)) keyPoints.push({ pos: norm(position), kind: "move" });
    else if (TELEPORT_TYPES.has(typeName)) keyPoints.push({ pos: norm(position), kind: "teleport" });
  }
  if (route.end && Number.isFinite(Number(route.end.row))) {
    keyPoints.push({ pos: norm(route.end), kind: "move" });
  }
  const segments = [];
  for (let i = 1; i < keyPoints.length; i += 1) {
    const from = keyPoints[i - 1].pos;
    const to = keyPoints[i].pos;
    if (keyPoints[i].kind === "teleport") {
      segments.push({ type: "teleport", points: [from, to] });
      continue;
    }
    if (motionMode === MOTION_FLY) {
      segments.push({ type: "fly", points: [from, to] });
      continue;
    }
    const endpoints = [from, to];
    const raw = findTilePath(map, from, to, {
      motionMode,
      allowDiagonalMove: Boolean(route.allowDiagonalMove),
    });
    segments.push({
      type: "walk",
      points: raw ? smoothPath(map, raw, { motionMode, endpoints }) : [from, to],
    });
  }
  return segments;
}

/**
 * 把一条路线展开成有序 leg 序列：
 * move（按移速走）/ wait（检查点停留 time 秒）/ teleport（闪现，不占时间）。
 * 传入 map 时地面 move 段走寻路折线（距离/插值沿折线），否则退化为直线段。
 */
export function buildRouteLegs(route, map = null) {
  const legs = [];
  if (!route || !route.start) return legs;
  const motionMode = Number(route.motionMode) === MOTION_FLY ? MOTION_FLY : 0;
  const diagonal = Boolean(route.allowDiagonalMove);
  const dist = (a, b) => (diagonal
    ? Math.hypot(b.row - a.row, b.col - a.col)
    : Math.abs(b.row - a.row) + Math.abs(b.col - a.col));
  const moveLeg = (from, to) => {
    if (motionMode === MOTION_FLY) {
      // 飞行无视地形，直线
      return { type: "move", from, to, dist: Math.hypot(to.row - from.row, to.col - from.col) };
    }
    if (map) {
      const endpoints = [from, to];
      const raw = findTilePath(map, from, to, { motionMode, allowDiagonalMove: diagonal });
      if (raw && raw.length > 1) {
        const path = smoothPath(map, raw, { motionMode, endpoints });
        return { type: "move", from, to, path, dist: pathDistance(path) };
      }
    }
    return { type: "move", from, to, dist: dist(from, to) };
  };
  let current = { row: Number(route.start.row) || 0, col: Number(route.start.col) || 0 };
  for (const checkpoint of route.checkpoints || []) {
    const typeName = String(checkpoint.typeName || "");
    const position = checkpoint.position;
    const hasPos = position && Number.isFinite(Number(position.row)) && Number.isFinite(Number(position.col));
    if (MOVE_TYPES.has(typeName) && hasPos) {
      const to = { row: Number(position.row), col: Number(position.col) };
      legs.push(moveLeg(current, to));
      current = to;
    } else if (TELEPORT_TYPES.has(typeName) && hasPos) {
      const to = { row: Number(position.row), col: Number(position.col) };
      legs.push({ type: "teleport", from: current, to });
      current = to;
    } else if (typeName.startsWith("WAIT")) {
      legs.push({ type: "wait", at: current, seconds: Math.max(0, Number(checkpoint.time) || 0) });
    }
  }
  if (route.end && Number.isFinite(Number(route.end.row))) {
    const to = { row: Number(route.end.row), col: Number(route.end.col) || 0 };
    legs.push(moveLeg(current, to));
  }
  return legs;
}

/** 出生 seconds 秒后在路线上的位置；state: walking / waiting / arrived。 */
export function positionOnLegs(legs, seconds, speed) {
  let remaining = Math.max(0, Number(seconds) || 0);
  const v = Number(speed) > 0.01 ? Number(speed) : 1.0;
  let lastTo = null;
  for (const leg of legs) {
    if (leg.to) lastTo = leg.to;
    if (leg.type === "teleport") continue;
    if (leg.type === "wait") {
      if (remaining < leg.seconds) return { row: leg.at.row, col: leg.at.col, state: "waiting" };
      remaining -= leg.seconds;
      continue;
    }
    const duration = leg.dist / v;
    if (remaining < duration) {
      if (leg.path?.length > 1) {
        return { ...pointAlongPath(leg.path, remaining * v), state: "walking" };
      }
      const t = duration > 0 ? remaining / duration : 1;
      return {
        row: leg.from.row + (leg.to.row - leg.from.row) * t,
        col: leg.from.col + (leg.to.col - leg.from.col) * t,
        state: "walking",
      };
    }
    remaining -= duration;
  }
  return lastTo ? { row: lastTo.row, col: lastTo.col, state: "arrived" } : null;
}

/** 单个敌人的完整行程：出生帧 →(未现形延迟 → 走/等/闪现)→ 到达蓝门帧（估算）。
 *  传入 map 时地面移动段按寻路折线计算距离与位置。 */
export function enemyJourney(enemy, route, fps, map = null) {
  const startFrame = finiteFrame(enemy?.startFrame);
  if (startFrame === null) return null;
  const legs = buildRouteLegs(route, map);
  const speed = Number(enemy?.moveSpeed) > 0.01 ? Number(enemy.moveSpeed) : 1.0;
  // 出生到现形的延迟（潜伏/泄漏源这类会在场上先隐藏一段时间）
  const bornDelay = Number(enemy?.bornDelay) > 0 ? Number(enemy.bornDelay) : 0;
  const moveDist = legs.filter((leg) => leg.type === "move").reduce((sum, leg) => sum + leg.dist, 0);
  const waitSeconds = legs.filter((leg) => leg.type === "wait").reduce((sum, leg) => sum + leg.seconds, 0);
  const totalSeconds = bornDelay + moveDist / speed + waitSeconds;
  const arriveFrame = legs.length ? Math.round(startFrame + totalSeconds * fps) : null;
  // endFrame 为 0 或不晚于出生帧时视为“未观测到结束”，回退到到达蓝门估算
  const rawEnd = finiteFrame(enemy?.endFrame);
  const endFrame = rawEnd !== null && rawEnd > startFrame ? rawEnd : null;
  return {
    legs, speed, bornDelay, startFrame, arriveFrame, endFrame, totalSeconds,
    effectiveEnd: endFrame ?? arriveFrame,
  };
}

/** 播放帧 F 时敌人的场上状态：pending / on(含位置, hidden=未现形) / gone。 */
export function enemyStateAt(journey, enemy, frame, fps) {
  if (!journey) return { phase: "pending" };
  if (frame < journey.startFrame) return { phase: "pending" };
  const effectiveEnd = journey.effectiveEnd;
  if (effectiveEnd !== null && frame > effectiveEnd) {
    return { phase: "gone", reason: enemy?.endReason || (journey.endFrame === null ? "到达蓝门(估)" : "") };
  }
  const elapsed = (frame - journey.startFrame) / fps;
  const start = journey.legs[0]?.from || { row: 0, col: 0 };
  if (elapsed < (journey.bornDelay || 0)) {
    return { phase: "on", row: start.row, col: start.col, state: "hidden" };
  }
  const position = positionOnLegs(journey.legs, elapsed - (journey.bornDelay || 0), journey.speed);
  if (!position) return { phase: "on", row: start.row, col: start.col, state: "walking" };
  return { phase: "on", ...position };
}

/** 把我方三类操作按干员合并成生命周期：部署区间 + 技能时刻。 */
export function buildOperatorLifecycles(groups) {
  const byOper = new Map();
  const ensure = (oper) => {
    if (!byOper.has(oper)) byOper.set(oper, { oper, deploys: [], skills: [], withdraws: [] });
    return byOper.get(oper);
  };
  for (const row of groups?.deploy || []) {
    const entry = ensure(row.oper || "未知干员");
    for (const action of row.actions || []) {
      const frame = finiteFrame(action.frame);
      if (frame === null) continue;
      entry.deploys.push({ frame, pos: action.pos || "", direction: action.direction || "" });
    }
  }
  for (const row of groups?.skill || []) {
    const entry = ensure(row.oper || "未知干员");
    for (const action of row.actions || []) {
      const frame = finiteFrame(action.frame);
      if (frame === null) continue;
      entry.skills.push({ frame });
    }
  }
  for (const row of groups?.withdraw || []) {
    const entry = ensure(row.oper || "未知干员");
    for (const action of row.actions || []) {
      const frame = finiteFrame(action.frame);
      if (frame === null) continue;
      entry.withdraws.push({ frame });
    }
  }
  const lifecycles = [];
  for (const entry of byOper.values()) {
    entry.deploys.sort((a, b) => a.frame - b.frame);
    entry.skills.sort((a, b) => a.frame - b.frame);
    entry.withdraws.sort((a, b) => a.frame - b.frame);
    const usedWithdraws = new Set();
    const intervals = entry.deploys.map((deploy) => {
      const withdrawIndex = entry.withdraws.findIndex(
        (item, index) => !usedWithdraws.has(index) && item.frame > deploy.frame);
      let end = null;
      if (withdrawIndex >= 0) {
        usedWithdraws.add(withdrawIndex);
        end = entry.withdraws[withdrawIndex].frame;
      }
      return { start: deploy.frame, end, pos: deploy.pos, direction: deploy.direction };
    });
    lifecycles.push({ oper: entry.oper, intervals, skills: entry.skills });
  }
  return lifecycles.sort((a, b) => (a.intervals[0]?.start ?? 0) - (b.intervals[0]?.start ?? 0));
}

/** 播放帧 F 时干员在场状态：在场区间 + 是否正在开技能（±0.25s 窗口）。 */
export function operatorStateAt(lifecycle, frame, fps) {
  const active = lifecycle.intervals.find(
    (interval) => frame >= interval.start && (interval.end === null || frame < interval.end));
  if (!active) return null;
  const windowFrames = Math.max(1, Math.round(fps * 0.25));
  const skillActive = lifecycle.skills.some(
    (skill) => Math.abs(skill.frame - frame) <= windowFrames
      && frame >= active.start && (active.end === null || frame < active.end));
  return { ...active, skillActive };
}

export const ROUTE_COLORS = ["#ff7a7a", "#66c2ff", "#ffd166", "#a78bfa", "#70e1a1", "#ff9f43"];

export function routeColor(routeIndex) {
  const index = Number(routeIndex);
  if (!Number.isFinite(index) || index < 0) return "#9aa7ba";
  return ROUTE_COLORS[index % ROUTE_COLORS.length];
}
