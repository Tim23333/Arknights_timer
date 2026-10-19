import {formatValue} from './model.mjs';
import {createFieldDisplay} from './fieldDisplay.mjs';
import {createSourceMeta} from './sourceMeta.mjs';
import {createMapRenderer} from './map/renderer.mjs';

const gateLabels = {spawning:'正在出怪',fragment_block:'片段条件阻塞',clearance_wait:'等待清敌',timeout_wait:'有限清敌等待',pre_delay:'波前等待',post_delay:'波后等待',mode_wait:'模式条件等待',finished:'调度结束',unknown:'门控未知'};
const unavailable = state => ['unavailable','not_collected'].includes(state?.collectionState || state?.state);
const fieldRecord = (payload, id) => payload?.fieldStates?.['stage_global.' + id] || {};
const switchState = (policy,id) => policy?.fields?.find(field => field.id === 'stage_global.' + id);
const visible = (policy, id) => switchState(policy,id)?.display !== false && switchState(policy,id)?.collect !== false;
const number = value => typeof value === 'number' && Number.isFinite(value);
const listState = (payload,id,value,policy) => {
  const field=switchState(policy,id), record=fieldRecord(payload,id);
  if(field?.display === false) return 'not_displayed';
  if(field?.collect === false || record.collectionState === 'not_collected') return 'not_collected';
  if(unavailable(record)) return 'unavailable';
  if(id === 'nextWaveEnemies' && value === null && record.collectionState === 'current'
      && record.reason === 'selection_pending') return 'selection_pending';
  if(record.collectionState === 'last_known') return 'last_known';
  return Array.isArray(value) ? 'current' : 'unavailable';
};
const sourceFrame = (payload,id) => {
  const record=fieldRecord(payload,id);
  // Explicit null is not permission to borrow a different aggregate frame.
  const frame=Object.hasOwn(record,'sourceFrame') ? record.sourceFrame : payload.meta?.sourceFrame;
  return Number.isSafeInteger(frame) ? frame : null;
};
const listLabels = {not_displayed:'未展示',not_collected:'未采集',unavailable:'不可用',last_known:'旧',selection_pending:'等待模式选择，名单尚未确定'};
const sessionId = data => data.stage_global?.meta?.sessionId || data.clock?.meta?.sessionId;
const sharedStopped = data => ['source_stopped','session_changed','adb_changed'].includes(data.stage_global?.meta?.reason);
const topicData = (data,topic,policy) => {
  if(topic !== 'stage_global' && sharedStopped(data)) return {};
  const payload=data[topic] || {};
  const currentSession=sessionId(data);
  if(currentSession && payload.meta?.sessionId && payload.meta.sessionId !== currentSession) return {};
  return Number.isInteger(payload.meta?.policyGeneration) && Number.isInteger(policy.generation) && payload.meta.policyGeneration !== policy.generation ? {} : payload;
};

/** Presentation-only retention. Raw topics, field records and WS are
 * untouched; failed reads retain the original frame without a timeout.
 * Empty current lists replace old rows immediately. Policy/session/stop clears
 * every retained value, including folded tables and markers, without waiting for IO. */
export function createStageTopicDisplay() {
  const cache=new Map(), definitions=[['stage_map','map','map'],['stage_map','mapRuntime','mapRuntime'],
    ['stage_units','enemyLayout','enemyLayout'],['stage_units','allyLayout','allyLayout'],
    ['stage_global','nextWaveEnemies','waves.nextEnemies']];
  let scope=null, previousPolicy=null;
  return {project(data,policy,now=performance.now()) {
    const nextScope=JSON.stringify([sessionId(data),policy.generation]);
    if(scope!==nextScope || (policy.generation==null && previousPolicy!==policy) || !sessionId(data) || sharedStopped(data)) cache.clear();
    scope=nextScope; previousPolicy=policy;
    const projected={...data}; let expiresAt=null;
    for(const [topic,id,path] of definitions) {
      const payload=topicData(data,topic,policy), record=fieldRecord(payload,id), value=path.split('.').reduce((value,key)=>value?.[key],payload);
      const stopped=['source_stopped','session_changed','adb_changed'].includes(payload.meta?.reason);
      if(!visible(policy,id) || stopped || sharedStopped(data) || record.collectionState==='not_collected' || !payload.meta?.sessionId) {cache.delete(id);continue;}
      if(['current','static'].includes(record.collectionState)) {
        // A documented current null (e.g. pending mode) is not a failed read.
        if(value==null) {cache.delete(id);continue;}
        const old=cache.get(id);
        if(old?.payload!==payload) cache.set(id,{payload,value,record});
      } else if(unavailable(record)) {
        const old=cache.get(id);
        if(!old) continue;
        const held={...(projected[topic] || payload),fieldStates:{...projected[topic]?.fieldStates,
          ['stage_global.'+id]:{...old.record,collectionState:'last_known',reason:record.reason}}};
        if(path.includes('.')) held.waves={...held.waves,nextEnemies:old.value};else held[path]=old.value;
        projected[topic]=held;
      } else cache.delete(id);
    }
    return {data:projected,expiresAt};
  }};
}

/** Null is not zero: only an explicitly successful empty game value has meaning. */
export function stageFieldText(id, value, record = {}) {
  if (record.collectionState === 'not_collected') return '未采集';
  if (unavailable(record)) return '不可用';
  if (value == null) {
    if (id === 'mapId' && ['current','static'].includes(record.collectionState) && record.reason === 'not_provided') return '游戏未提供';
    if (id === 'waveWait' && record.collectionState === 'current' && record.reason === 'not_applicable') return '当前阶段无等待';
    return '不可用';
  }
  if (id === 'isPaused') return value === true ? '暂停' : value === false ? '进行中' : '不可用';
  if (id === 'timeScale') return number(value) ? `${value} ×` : '不可用';
  if (id === 'speedLevel') return `档位 ${value}`;
  if (id === 'state') return ({PLAYING:'进行中',playing:'进行中',INIT:'初始化',READY:'准备中',END:'已结束',FINISHED:'已结束'})[value] || formatValue(value);
  if (id === 'currentWave' || id === 'nextWave') return `第 ${value.ordinal ?? value.index + 1} / ${value.totalConfigured ?? '—'} 波`;
  if (id === 'waveGate') return [gateLabels[value.kind] || value.kind || '门控未知',
    Number.isInteger(value.fragmentIndex) ? `片段索引 ${value.fragmentIndex}` : '',
    Number.isInteger(value.actionIndex) ? `行动索引 ${value.actionIndex}` : '',
    Number.isInteger(value.blockingEnemyCount) ? `阻塞敌人 ${value.blockingEnemyCount}` : '',
    Number.isInteger(value.blockCounter) ? `阻塞计数 ${value.blockCounter}` : ''].filter(Boolean).join(' · ');
  if (id === 'waveWait') return waveWaitText(value);
  if (id === 'mode') return value.name || value.type || value.kind || formatValue(value);
  return formatValue(value);
}

/** Coroutine resume counts are deliberately never renamed frames or divided by 30. */
export function waveWaitText(wait) {
  if (!wait || wait.kind === 'unavailable') return '不可用';
  if (wait.kind === 'not_applicable') return '无等待';
  if (wait.kind === 'undetermined') return '条件等待，时间不确定';
  const budget = wait.kind === 'timeout_budget';
  const prefix = budget ? '最多剩余 ' : '剩余 ';
  const earlier = budget || wait.mayFinishEarlier ? '（可提前结束）' : '';
  if (number(wait.remainingSeconds) && ['logical_time_estimate','mode_logical_timer'].includes(wait.secondsBasis)) {
    const basis = wait.secondsBasis === 'mode_logical_timer' ? '模式计时器' : '已核验时基估计';
    return `${prefix}${wait.remainingSeconds} 逻辑秒（${basis}）${earlier}`;
  }
  if (Number.isInteger(wait.remainingResumeCount)) return `${prefix}${wait.remainingResumeCount} 次恢复（秒数未确认）${earlier}`;
  return '等待量尚未取得';
}

/** Read-only projection of the three topics; the existing main clock stays authoritative. */
export function stageGlobalView(data = {}, policy = {}) {
  const global = topicData(data,'stage_global',policy), waves = global.waves || {}, runtime = global.runtime || {}, identity = global.identity || {};
  const values = {stageName:identity.stageName, levelId:identity.levelId, state:runtime.state, isPaused:runtime.isPaused,
    speedLevel:runtime.speedLevel,timeScale:runtime.timeScale,mode:global.mode,currentWave:waves.current,nextWave:waves.next,waveGate:waves.gate,waveWait:waves.wait};
  const labels = {stageName:'关卡名字',levelId:'地图 ID',state:'战斗状态',isPaused:'暂停状态',speedLevel:'配置速度',timeScale:'实际引擎倍率',mode:'模式',currentWave:'当前配置波次',nextWave:'下一配置波次',waveGate:'当前换波条件',waveWait:'活动等待'};
  const facts = Object.entries(values).map(([id,value]) => {
    // levelId belongs to the existing identity collection group, not raw mapId.
    const sourceId = id === 'levelId' ? 'stageName' : id;
    const record = fieldRecord(global,sourceId);
    let text = visible(policy,sourceId) ? stageFieldText(id,value,record) : switchState(policy,sourceId)?.display === false ? '未展示' : '未采集';
    if (id === 'nextWave' && value == null && visible(policy,id) && !unavailable(record)) text = ({none:'无后续配置波次',pending:'等待模式选择',unknown:'下一波未知'})[waves.nextSelection] || text;
    return {id,fieldId:'stage_global.'+sourceId,label:labels[id],text,record};
  });
  const units = topicData(data,'stage_units',policy);
  const listStates={nextEnemies:listState(global,'nextWaveEnemies',waves.nextEnemies,policy),
    enemyLayout:listState(units,'enemyLayout',units.enemyLayout,policy),
    allyLayout:listState(units,'allyLayout',units.allyLayout,policy)};
  return {clock:data.clock || {}, global, facts,
    listStates,
    stageId:visible(policy,'stageName') ? identity.stageId || identity.levelId || '—' : '未展示',
    nextEnemies:visible(policy,'nextWaveEnemies') && !unavailable(fieldRecord(global,'nextWaveEnemies')) && Array.isArray(waves.nextEnemies) ? waves.nextEnemies : [],
    enemyLayout:visible(policy,'enemyLayout') && !unavailable(fieldRecord(units,'enemyLayout')) && Array.isArray(units.enemyLayout) ? units.enemyLayout : [],
    allyLayout:visible(policy,'allyLayout') && !unavailable(fieldRecord(units,'allyLayout')) && Array.isArray(units.allyLayout) ? units.allyLayout : [],
  };
}

const tileProperties=['tileKey','heightType','buildableType','passableMask','playerSideMask','advancedBuildableMask'];
function flattenTiles(selected,rows,cols) {
  const tiles=[];
  for(let row=rows-1;row>=0;row--) for(let col=0;col<cols;col++) tiles.push({row,col,...selected.tiles[row][col]});
  return tiles;
}

/** One bounded presentation cache. Compare current payload contents, not just
 * revision: runtime terrain can change without changing the base revision. */
export function createTileProjection() {
  let previous=null, previousRows=0, previousCols=0, tiles=[];
  return (selected,rows,cols)=>{
    if(previous===selected && previousRows===rows && previousCols===cols) return tiles;
    const same=previous && previousRows===rows && previousCols===cols
      && selected.tiles.every((line,r)=>line.every((tile,c)=>tileProperties.every(key=>tile?.[key]===previous.tiles[r][c]?.[key])
        && JSON.stringify([tile?.blackboard,tile?.blackboardMeta])===JSON.stringify([previous.tiles[r][c]?.blackboard,previous.tiles[r][c]?.blackboardMeta])));
    if(!same) tiles=flattenTiles(selected,rows,cols);
    previous=selected;previousRows=rows;previousCols=cols;
    return tiles;
  };
}

/** Canonical coordinates are bottom-left; only display order is reversed here. */
export function boardView(data = {}, policy = {}, projectTiles = flattenTiles) {
  const payload = topicData(data,'stage_map',policy), base = payload.map;
  if (!visible(policy,'map') || unavailable(fieldRecord(payload,'map')) || !base || !Number.isInteger(base.rows) || !Number.isInteger(base.cols)
      || base.rows < 1 || base.cols < 1 || base.rows * base.cols > 65536 || !Array.isArray(base.tiles)
      || base.tiles.length !== base.rows || base.tiles.some(row => !Array.isArray(row) || row.length !== base.cols)) return {available:false,tiles:[],markers:[],unplaced:[]};
  const runtime = payload.mapRuntime;
  const useRuntime = visible(policy,'mapRuntime') && !unavailable(fieldRecord(payload,'mapRuntime')) && runtime?.revision === base.revision
    && Array.isArray(runtime.tiles) && runtime.tiles.length === base.rows && runtime.tiles.every(row => Array.isArray(row) && row.length === base.cols);
  const selected = useRuntime ? runtime : base, tiles = projectTiles(selected,base.rows,base.cols);
  const unitSession=data.stage_units?.meta?.sessionId, mapSession=payload.meta?.sessionId;
  const scopedData=unitSession && mapSession && unitSession !== mapSession ? {...data,stage_units:{}} : data;
  const view = stageGlobalView(scopedData,policy), units=topicData(scopedData,'stage_units',policy), markers = [], unplaced = [];
  for (const [kind,items] of [['enemy',view.enemyLayout],['ally',view.allyLayout]]) {
    for (const item of items) {
      const x = kind === 'enemy' ? item.position?.x : item.grid?.col;
      const y = kind === 'enemy' ? item.position?.y : item.grid?.row;
      const entry = {...item,kind,entityKind:item.kind,x,y};
      // Do not clamp, infer, or borrow historical coordinates for missing entities.
      if (number(x) && number(y) && x >= 0 && y >= 0 && x < base.cols && y < base.rows) markers.push(entry);
      else unplaced.push({...entry,placementReason:number(x) && number(y) ? '坐标超出棋盘' : '没有可用坐标'});
    }
  }
  const mapField=useRuntime?'mapRuntime':'map';
  const sources={map:{sourceFrame:sourceFrame(payload,mapField),state:fieldRecord(payload,mapField).collectionState || (useRuntime?'current':'static'),active:true},
    enemyLayout:{sourceFrame:sourceFrame(units,'enemyLayout'),state:view.listStates.enemyLayout,active:view.listStates.enemyLayout === 'current'},
    allyLayout:{sourceFrame:sourceFrame(units,'allyLayout'),state:view.listStates.allyLayout,active:view.listStates.allyLayout === 'current'}};
  for(const key of ['enemyLayout','allyLayout']) if(sources[key].state==='last_known') sources[key].active=true;
  const active=Object.values(sources).filter(item=>item.active), frames=active.map(item=>item.sourceFrame);
  const frameRelation=active.length === 1 ? 'no_layout' : frames.some(frame=>frame === null) ? 'unknown_frame' : new Set(frames).size === 1 ? 'same_frame' : 'mixed_frames';
  return {available:true,rows:base.rows,cols:base.cols,layer:useRuntime?'runtime':'base',revision:base.revision,tiles,markers,unplaced,sources,frameRelation};
}

/** Stable DOM owner: only changed text/tiles/markers mutate; raw JSON is lazy. */
export function createStageGlobalRenderer(root, {table, policy = () => ({})}) {
  const doc = root.ownerDocument, find = id => doc.getElementById(id);
  const mapHost=find('global-perspective-map');
  const perspective=mapHost?createMapRenderer(mapHost):null;
  const set = (id,value) => { const element=find(id), text=String(value); if (element && element.textContent !== text) element.textContent=text; };
  const facts = new Map(), tileNodes = new Map(), markerNodes = new Map();
  const display = createFieldDisplay(), topicDisplay=createStageTopicDisplay();
  const source = createSourceMeta(find('global-meta'), {sourceLabel:'运行采样帧',additionalFrames:[{key:'clockSourceFrame',label:'时钟来源帧'}]});
  let shape = '', expiry = null, lastData = {}, previousMap = null, previousUnits = null, previousSession = null;
  const displayPayloads = new WeakMap();
  const append = (tag,host,className,text) => {const element=doc.createElement(tag); if(className) element.className=className; if(text!==undefined) element.textContent=text; host.append(element); return element;};
  const factHost = find('global-facts');
  let projectTiles=createTileProjection(), renderedTiles=null;
  function updateSources(data) {
    const payload=topicData(data,'stage_global',policy()), clock=data.clock || {};
    const sameSession=!sessionId(data) || !clock.meta?.sessionId || clock.meta.sessionId===sessionId(data);
    source.update({...payload.meta,sourceFrame:payload.meta?.runtimeFrame,
      clockSourceFrame:sameSession?clock.meta?.sourceFrame:null},'多来源采样');
  }
  function drawMap(data) {
    const currentSession=sessionId(data);
    if (previousMap === data.stage_map && previousUnits === data.stage_units && previousSession === currentSession) return;
    if(previousSession!==currentSession) {projectTiles=createTileProjection();renderedTiles=null;}
    previousMap=data.stage_map; previousUnits=data.stage_units; previousSession=currentSession;
    const view = boardView(data,policy(),projectTiles), board=find('global-board'), markers=find('global-markers');
    perspective?.update(view,currentSession);
    board.hidden=!view.available;
    if (!view.available) {set('global-map-status','地图不可用或未展示'); board.replaceChildren(); markers.replaceChildren(); tileNodes.clear(); markerNodes.clear(); shape=''; renderedTiles=null; projectTiles=createTileProjection(); return;}
    const frameLabel=source=>source.sourceFrame === null?'来源帧未取得':`F${source.sourceFrame}`;
    const heldMap=fieldRecord(data.stage_map || {},view.layer==='runtime'?'mapRuntime':'map').collectionState==='last_known';
    const provenance=[`地图 ${frameLabel(view.sources.map)}${heldMap?'（旧）':''}`,
      ...[['enemyLayout','敌方布局'],['allyLayout','我方布局']].map(([key,label])=>`${label} ${view.sources[key].active?frameLabel(view.sources[key]):listLabels[view.sources[key].state] || '不可用'}${view.sources[key].state==='last_known'?'（旧）':''}`),
      ({same_frame:'同一来源帧（不代表原子快照）',mixed_frames:'混合来源帧（非共同采样帧）',unknown_frame:'来源帧不完整，不判断同帧',no_layout:'布局尚未取得有效样本'})[view.frameRelation]].join(' · ');
    set('global-map-status',`${view.cols} 列 × ${view.rows} 行 · ${view.layer === 'runtime' ? '运行时地块采样' : '配置底图（不是当帧可部署判断）'} · ${provenance}`);
    if(perspective){
      set('global-map-legend',[...new Set(view.tiles.map(tile=>tile.tileKey))].sort().join(' · '));
      set('global-unplaced',view.unplaced.length?`未叠加 ${view.unplaced.length} 个实体（坐标未知或超出棋盘）`:'当前有坐标的敌我实体已叠加；移动状态不等于实际位移。');
      return;
    }
    if(shape !== `${view.rows}:${view.cols}`) {
      board.replaceChildren(); tileNodes.clear(); shape=`${view.rows}:${view.cols}`;
      board.style.setProperty('--map-cols',view.cols); board.style.setProperty('--map-rows',view.rows);
      markers.style.setProperty('--map-cols',view.cols); markers.style.setProperty('--map-rows',view.rows);
    }
    if(renderedTiles!==view.tiles) {
      const keys = new Set();
      for(const tile of view.tiles) {
        const key=`${tile.row}:${tile.col}`;
        let cell=tileNodes.get(key);
        if(!cell) {cell=append('div',board,'global-tile'); tileNodes.set(key,cell);}
        const text=tile.tileKey ?? '不可用', hint=`(${tile.col}, ${tile.row}) · ${text}\n高度 ${tile.heightType ?? '—'} · 建造类型 ${tile.buildableType ?? '—'} · 通行掩码 ${tile.passableMask ?? '—'} · 阵营掩码 ${tile.playerSideMask ?? '—'} · 高级建造掩码 ${tile.advancedBuildableMask ?? '—'}`;
        if(cell.title!==hint) cell.title=hint;
        if(cell.textContent!==`${tile.col},${tile.row}`) cell.textContent=`${tile.col},${tile.row}`;
        const styleKey=({tile_start:'start',tile_end:'end',tile_floor:'floor',tile_road:'road',tile_forbidden:'forbidden',tile_hole:'hole'})[text] || 'unknown';
        if(cell.dataset.type!==styleKey) cell.dataset.type=styleKey;
        keys.add(text);
      }
      set('global-map-legend',[...keys].sort().join(' · '));
      renderedTiles=view.tiles;
    }
    const wanted=new Set();
    for(const item of view.markers) {
      const key=`${item.kind}:${item.id}`; wanted.add(key);
      let marker=markerNodes.get(key);
      if(!marker) {marker=append('span',markers,'global-marker '+item.kind); markerNodes.set(key,marker);}
      const text=item.kind === 'enemy' ? '敌' : ({0:'↑',1:'→',2:'↓',3:'←'})[item.direction] || '我';
      if(marker.textContent!==text) marker.textContent=text;
      const left=`${(item.x+.5)*100/view.cols}%`, bottom=`${(item.y+.5)*100/view.rows}%`;
      if(marker.style.left!==left) marker.style.left=left;
      if(marker.style.bottom!==bottom) marker.style.bottom=bottom;
      const hint=`${item.name || item.enemyId || item.characterId || item.id} · (${item.x}, ${item.y}) · ${item.stateName || item.directionName || '—'}`;
      if(marker.title!==hint) marker.title=hint;
    }
    for(const [key,marker] of markerNodes) if(!wanted.has(key)) {marker.remove(); markerNodes.delete(key);}
    set('global-unplaced',view.unplaced.length ? `未叠加 ${view.unplaced.length} 个实体：${view.unplaced.map(item => `${item.id}（${item.placementReason}）`).join('、')}` : '当前有坐标的敌我实体已叠加；移动状态不等于实际位移。');
  }
  function draw(data = lastData, forceMap = false) {
    lastData=data;
    const view=stageGlobalView(data,policy()), payload=view.global;
    const presentation=topicDisplay.project(data,policy()), presentedView=stageGlobalView(presentation.data,policy());
    const columns=view.facts.map(item => ({key:item.id,fieldId:item.fieldId}));
    let displayPayload=displayPayloads.get(payload);
    if(!displayPayload || displayPayload.policy !== policy()
        || displayPayload.meta.reason !== payload.meta?.reason
        || displayPayload.meta.sessionId !== payload.meta?.sessionId) {
      const row={id:'global',fieldStates:payload.fieldStates || {},columns:Object.fromEntries(view.facts.map(item => [item.id,item.text]))};
      // Aggregates deliberately have multiple producers. Field records already
      // describe dynamic guard failures; applying the entity-wide failedBatch
      // rule would falsely invalidate independent clock/static successes. This
      // presentation-only scope omits batch verdicts, never rewrites canonical
      // metadata (raw JSON and source.update below keep the actual verdict).
      const {frameConsistent,collectionState,...presentationMeta}=payload.meta || {};
      displayPayload={meta:presentationMeta,items:[row],policy:policy()};
      displayPayloads.set(payload,displayPayload);
    }
    const row=displayPayload.items[0];
    const presented=display.project(displayPayload, {kind:'stage_global',policy:policy(),precision:2},columns,(item,column)=>item.columns[column.key]);
    // The failure hold is presentation only: originals below remain canonical.
    clearTimeout(expiry);
    const deadlines=[presented.expiresAt,presentation.expiresAt].filter(value=>value!==null);
    if(deadlines.length) expiry=setTimeout(()=>draw(),Math.max(0,Math.min(...deadlines)-performance.now()+1));
    for(const item of view.facts) {
      let value=facts.get(item.id);
      if(!value) {const box=append('div',factHost,'global-fact'); append('span',box,'',item.label); value=append('strong',box); facts.set(item.id,value);}
      const cell=presented.cell(row,{key:item.id});
      if(value.textContent!==cell.text) value.textContent=cell.text;
      if(value.title!==cell.title) value.title=cell.title;
      if(value.dataset.freshness!==cell.freshness) value.dataset.freshness=cell.freshness;
    }
    set('global-stage-id',view.stageId);
    if(find('global-wave-detail').parentElement.open) set('global-wave-detail', JSON.stringify(payload.waves || {},null,2));
    updateSources(data);
    table('global-wave-table',[['enemyId','敌人 ID'],['count','数量'],['fragmentIndex','片段索引'],['actionIndex','行动索引'],['routeIndex','路线索引'],['preDelay','前置等待（秒）'],['interval','生成间隔（秒）'],['selection','确定状态'],['hiddenGroup','隐藏组'],['randomGroup','随机组'],['randomPack','随机包']].map(([key,label])=>({key,label})),presentedView.nextEnemies,(item,column)=>{
      const text=column.key==='selection' ? ({confirmed:'已确定',conditional:'条件候选'})[item.selection] || formatValue(item.selection) : formatValue(item[column.key]);
      return presentedView.listStates.nextEnemies==='last_known'?{text,title:'最后有效名单，非当前样本',freshness:'last_known'}:text;
    });
    const units=[...presentedView.enemyLayout.map(item=>({...item,id:'enemy:'+item.id,side:'敌方',_old:presentedView.listStates.enemyLayout==='last_known'})),...presentedView.allyLayout.map(item=>({...item,id:'ally:'+item.id,side:'我方',_old:presentedView.listStates.allyLayout==='last_known'}))];
    table('global-layout-table',[['side','阵营'],['id','实例 ID'],['name','名称'],['kind','类别'],['position','当前坐标'],['stateName','移动状态'],['directionName','朝向']].map(([key,label])=>({key,label})),units,(item,column)=>{
      const text=column.key==='position' ? item.side==='我方' ? formatValue(item.grid) : formatValue(item.position) : formatValue(item[column.key]);
      return item._old?{text,title:'最后有效布局，非当前样本',freshness:'last_known'}:text;
    });
    set('global-wave-status',['current','last_known'].includes(presentedView.listStates.nextEnemies) ? `${presentedView.nextEnemies.length} 项配置${presentedView.listStates.nextEnemies==='last_known'?'（旧）':''}（不是已实例化敌人）` : listLabels[presentedView.listStates.nextEnemies] || '不可用');
    set('global-layout-status',`当前敌方 ${['current','last_known'].includes(presentedView.listStates.enemyLayout)?presentedView.enemyLayout.length+(presentedView.listStates.enemyLayout==='last_known'?'（旧）':''):listLabels[presentedView.listStates.enemyLayout] || '不可用'} · 当前我方 ${['current','last_known'].includes(presentedView.listStates.allyLayout)?presentedView.allyLayout.length+(presentedView.listStates.allyLayout==='last_known'?'（旧）':''):listLabels[presentedView.listStates.allyLayout] || '不可用'}`);
    if(forceMap) {previousMap=null;previousUnits=null;}
    drawMap(presentation.data);
    for(const topic of ['stage_global','stage_map','stage_units']) {const pre=find('raw-'+topic); if(pre.parentElement.open) {const text=JSON.stringify(topicData(data,topic,policy()),null,2); if(pre.textContent!==text) pre.textContent=text;}}
  }
  return {draw, updateSources, destroy(){clearTimeout(expiry);perspective?.destroy();}};
}
