import io
import os

"""Web UI for the Ark_emulator live server.

Provides an interactive battle viewer:
  - level selection (search)
  - squad / custom enemy config
  - live grid map with units / projectiles / terrain
  - click-to-deploy on the map, withdraw / skill on deployed units
  - pause / resume control
"""

import json

PAGE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>Ark_emulator battlefield</title>
<style>
body{font-family:'Segoe UI',system-ui;background:#1a1d26;color:#e8eaf0;margin:0}
#top{display:flex;gap:10px;padding:8px 14px;background:#22263a;align-items:center;flex-wrap:wrap}
input,select,button{background:#2b3050;color:#e8eaf0;border:1px solid #3a4070;border-radius:6px;padding:5px 9px}
button{cursor:pointer}button:hover{background:#3a4070}
#main{display:flex;height:calc(100vh - 52px)}
#mapwrap{flex:1;overflow:auto;padding:10px}
table{border-collapse:collapse;cursor:pointer}
td{width:46px;height:46px;border:1px solid #33395e;text-align:center;font-size:10px;position:relative}
td.road{background:#2a2f47}td.wall{background:#464b63}td.forbidden{background:#23242f}
td.hole{background:#0e1626}td.end{background:#4a3a2a}td.start{background:#2a4a2a}
td.volcano{background:#7a3a1a}td.toxic{background:#5a5a1a}td.heal{background:#1a5a3a}
td.sel{outline:2px solid #ffd040}
td.route{outline:1px dashed #9fc080;background-image:radial-gradient(circle,#9fc080 2px,transparent 3px)}
.unit{position:absolute;inset:2px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:bold;color:#fff;cursor:pointer}
.unit.enemy{background:#b04040}.unit.op{background:#4080c0}.unit.token{background:#60a060}
#side{width:350px;background:#20243a;padding:10px;overflow-y:auto;font-size:12px}
#side h3{margin:8px 0 5px;color:#9fb0e0}
#events{height:200px;overflow-y:auto;background:#161827;padding:5px;border-radius:6px;font-family:monospace;font-size:11px}
.bar{display:flex;justify-content:space-between;margin:3px 0}
.hint{color:#8fa;font-size:11px;margin-top:6px}
</style>
</head>
<body>
<div id="top">
  <b>Ark_emulator</b>
  <input id="search" placeholder="search level (1-1, 4-3)">
  <button onclick="searchLevel()">search</button>
  <select id="level"></select>
  <button onclick="loadLevel()">load</button>
  <span style="flex:1"></span>
  <label>operator:</label>
  <select id="charSel"><option value="char_149_scave">scave</option>
    <option value="char_002_amiya">amiya</option>
    <option value="char_102_texas">texas</option></select>
  <label>dir:</label>
  <select id="dirSel"><option value="1">R</option><option value="0">U</option>
    <option value="2">D</option><option value="3">L</option></select>
  <button onclick="ctl('pause')">pause</button>
  <button onclick="ctl('resume')">resume</button>
  <button onclick="ctl('step',{n:30})">step 1s</button>
  <button onclick="ctl('withdraw')">withdraw</button>
  <button onclick="ctl('skill')">skill</button>  <button onclick="summonAt()">summon</button>  <button onclick="toggleConfig()">config</button>
</div>
<div id="cfg" style="display:none;background:#22263a;padding:8px 14px">
  <b>squad JSON</b>
  <textarea id="squadJson" rows="3" style="width:100%;background:#161827;color:#e8eaf0;font-family:monospace"></textarea>
  <b>custom enemies JSON</b>
  <textarea id="customJson" rows="3" style="width:100%;background:#161827;color:#e8eaf0;font-family:monospace"></textarea>
  <button onclick="saveConfig()">apply & reload</button>
</div>
<div id="main">
  <div id="mapwrap"><div id="map"></div>
    <div class="hint">click ground to deploy selected operator; click an operator to withdraw/skill</div>
  </div>
  <div id="side">
    <div class="bar"><span>time</span><b id="t">0.0s</b></div>
    <div class="bar"><span>life</span><b id="life">-</b></div>
    <div class="bar"><span>cost</span><b id="cost">-</b></div>
    <div class="bar"><span>enemies</span><b id="ecnt">-</b></div>
    <div class="bar"><span>projectiles</span><b id="pcnt">-</b></div>
    <h3>stats</h3><div id="stats"></div>
    <h3>operators</h3><div id="ops"></div>
    <h3>summons</h3><div id="summons"></div>
    <h3>enemies</h3><div id="enemies"></div>
    <h3>events</h3><div id="events"></div>
  </div>
</div>
<script>
let lastSeq=0, selectedCell=null;
async function j(url,opt){const r=await fetch(url,opt);return r.json();}
function selectCell(r,c){selectedCell=[r,c];}
async function summonAt(){if(!selectedCell){alert('click a map cell first');return;}
  const d=await ctl('summon',{row:selectedCell[0],col:selectedCell[1]});
  if(!d.ok)alert('summon failed: '+JSON.stringify(d));}
async function searchLevel(){const q=document.getElementById('search').value;
  const d=await j('/levels?q='+encodeURIComponent(q));
  const sel=document.getElementById('level');sel.innerHTML='';
  for(const h of d.hits){const o=document.createElement('option');o.value=h.levelId;
    o.text=h.stageId+' '+h.name;sel.appendChild(o);}}
async function loadLevel(){const sel=document.getElementById('level');
  if(!sel.value)return;await j('/new?level='+encodeURIComponent(sel.value));lastSeq=0;}
async function loadConfig(){const d=await j('/config');
  document.getElementById('squadJson').value=JSON.stringify(d.squad||[],null,1);
  document.getElementById('customJson').value=JSON.stringify(d.custom_enemies||[],null,1);}
function toggleConfig(){const e=document.getElementById('cfg');
  e.style.display=e.style.display==='none'?'block':'none';if(e.style.display==='block')loadConfig();}
async function saveConfig(){let sq,cu;
  try{sq=JSON.parse(document.getElementById('squadJson').value||'[]');}catch(e){alert('squad JSON error');return;}
  try{cu=JSON.parse(document.getElementById('customJson').value||'[]');}catch(e){alert('custom JSON error');return;}
  await j('/config',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({squad:sq,custom_enemies:cu})});lastSeq=0;}
async function ctl(act, extra){const body=Object.assign({action:act,
  charId:document.getElementById('charSel').value,
  direction:parseInt(document.getElementById('dirSel').value)||1,
  row:3,col:4,instId:1,skillIndex:0}, extra||{});
  return j('/action',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify(body)});}
async function deployAt(r,c){const d=await ctl('deploy',{row:r,col:c});
  if(!d.ok)alert('deploy failed: '+JSON.stringify(d));}
async function opClick(inst){const d=await ctl('withdraw',{instId:inst});
  if(!d.ok)alert('withdraw failed: '+JSON.stringify(d));}
async function tick(){const s=await j('/snapshot');
  document.getElementById('t').textContent=s.t.toFixed(1)+'s';
  document.getElementById('life').textContent=s.lifePoint;
  document.getElementById('cost').textContent=s.cost.toFixed(1);
  document.getElementById('ecnt').textContent=s.enemies.length;
  document.getElementById('pcnt').textContent=s.projectiles.length;
  drawStats(s);drawMap(s);drawSide(s);pushEvents(s);}
function drawStats(s){const st=s.stats||{},el=document.getElementById('stats');
  el.innerHTML=
  '<div class="bar"><span>kills</span><b>'+st.kills+'</b></div>'+
  '<div class="bar"><span>leaks</span><b>'+st.leaks+'</b></div>'+
  '<div class="bar"><span>dmg dealt</span><b>'+Math.round(st.playerDamageDealt||0)+'</b></div>'+
  '<div class="bar"><span>dmg taken</span><b>'+Math.round(st.playerDamageTaken||0)+'</b></div>'+
  '<div class="bar"><span>deploys</span><b>'+st.deployments+'</b></div>'+
  '<div class="bar"><span>skills</span><b>'+st.skillCasts+'</b></div>';}
function routeCells(s){const cells=new Set();
  for(const rt of (s.routes||[])){
    const add=p=>{if(p)cells.add(p.row+','+p.col)};
    add(rt.startPosition);add(rt.endPosition);
    for(const cp of (rt.checkpoints||[]))add(cp.position);}
  return cells;}
function drawMap(s){const m=s.map,wrap=document.getElementById('map');
  const rc=routeCells(s);
  let html='<table>';for(let r=0;r<m.rows;r++){html+='<tr>';
    for(let c=0;c<m.cols;c++){const t=m.tiles[r*m.cols+c];let cls='road';
      const k=t.tileKey;
      if(k.includes('forbidden')||k.includes('wall'))cls='wall';
      if(k.includes('hole'))cls='hole';if(k.includes('end'))cls='end';
      if(k.includes('start'))cls='start';if(k.includes('volcano'))cls='volcano';
      if(k.includes('toxic'))cls='toxic';if(k.includes('heal'))cls='heal';
      if(rc.has(r+','+c))cls+=' route';
      if(selectedCell&&selectedCell[0]===r&&selectedCell[1]===c)cls+=' sel';
      html+='<td class="'+cls+'" onclick="selectCell('+r+','+c+');deployAt('+r+','+c+')">';
      for(const e of s.enemies)if(e.row===r&&e.col===c)
        html+='<div class="unit enemy" title="'+e.key+' hp='+Math.round(e.hp)+'">'+(e.hp/e.maxHp*100|0)+'</div>';
      for(const o of s.deployed)if(o.row===r&&o.col===c)
        html+='<div class="unit op" onclick="event.stopPropagation();opClick('+o.instId+')">'+o.charId.slice(-4)+'</div>';
      for(const t of s.tokens)if(t.row===r&&t.col===c)
        html+='<div class="unit token" title="'+t.tokenId+' hp='+Math.round(t.hp)+'" onclick="event.stopPropagation();opClick('+t.instId+')">'+t.tokenId.slice(-6)+'</div>';
      html+='</td>';}html+='</tr>';}html+='</table>';
  wrap.innerHTML=html;}
function drawSide(s){let h='';for(const o of s.deployed){h+='<div>'+o.charId+
  ' hp='+Math.round(o.hp)+' sp='+o.sp.toFixed(1)+'/'+o.spMax+
  ' <button onclick="ctl(\'skill\',{instId:'+o.instId+'})">skill</button></div>';}
  document.getElementById('ops').innerHTML=h;
  h='';for(const sm of (s.summons||[])){h+='<div>'+sm.charId.slice(-8)+' -> '+sm.tokenKey+
    (sm.deployed.length?' deployed':'')+
    (sm.deployable?' <button onclick="summonAt()">summon</button>':'')+
    ' redeploy '+sm.redeployIn+'s</div>';}
  document.getElementById('summons').innerHTML=h;
  h='';for(const e of s.enemies.slice(0,25)){h+='<div>'+e.key+
    ' hp='+Math.round(e.hp)+' '+e.state+' @('+e.row+','+e.col+')';
    if(e.skills&&e.skills.length)h+=' <span style="color:#9f8">'+
      e.skills.map(x=>x.prefabKey.slice(0,8)+':'+(x.cooldownRemaining||0).toFixed(1)).join(' ')+'</span>';
    if(e.casting)h+=' <b style="color:#fa8">cast:'+e.casting.skill.slice(0,8)+'</b>';
    h+='</div>';}
  document.getElementById('enemies').innerHTML=h;}
function pushEvents(s){for(const ev of s.events){if(ev.seq<=lastSeq)continue;lastSeq=ev.seq;
  const box=document.getElementById('events');const d=document.createElement('div');
  d.textContent=ev.t.toFixed(2)+' '+ev.type+' '+JSON.stringify(ev.data).slice(0,70);
  box.prepend(d);while(box.children.length>200)box.lastChild.remove();}}
setInterval(tick,300);tick();
</script>
</body>
</html>"""


def page_html():
    return PAGE


EDITOR_PAGE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>Ark_emulator - custom level editor</title>
<style>
body{font-family:'Segoe UI',system-ui;background:#1a1d26;color:#e8eaf0;margin:0}
#top{display:flex;gap:8px;padding:8px 14px;background:#22263a;align-items:center;flex-wrap:wrap}
input,select,textarea,button{background:#2b3050;color:#e8eaf0;border:1px solid #3a4070;border-radius:6px;padding:5px 9px}
button{cursor:pointer}button:hover{background:#3a4070}
#main{display:flex;height:calc(100vh - 52px)}
#mapwrap{flex:1;overflow:auto;padding:10px}
table{border-collapse:collapse}
td{width:38px;height:38px;border:1px solid #33395e;text-align:center;font-size:9px;cursor:pointer}
td.floor{background:#2a2f47}td.wall{background:#464b63}td.hole{background:#0e1626}
td.end{background:#4a3a2a}td.start{background:#2a4a2a}td.deploy{background:#1a3a5a}
.pal{display:inline-block;width:52px;height:26px;margin:2px;border-radius:4px;cursor:pointer;text-align:center;font-size:10px;line-height:26px}
#side{width:360px;background:#20243a;padding:10px;overflow-y:auto;font-size:12px}
textarea{width:100%;font-family:monospace;font-size:11px;background:#161827}
#log{height:120px;overflow-y:auto;background:#161827;padding:5px;border-radius:6px;font-family:monospace;font-size:11px;white-space:pre-wrap}
</style>
</head>
<body>
<div id="top">
  <b>Custom level editor</b>
  <label>rows <input id="rows" type="number" value="6" min="3" max="20"></label>
  <label>cols <input id="cols" type="number" value="10" min="4" max="30"></label>
  <button onclick="newGrid()">new grid</button>
  <span style="flex:1"></span>
  <button onclick="saveLevel(false)">save</button>
  <button onclick="saveLevel(true)">save &amp; run</button>
  <button onclick="location.href='/'">back to battle</button>
</div>
<div id="main">
  <div id="mapwrap">
    <div id="palette"></div>
    <div id="map" style="margin-top:8px"></div>
  </div>
  <div id="side">
    <b>enemies JSON</b>
    <textarea id="enemies" rows="6">[{"key":"enemy_1000_gopro","count":5,"interval":2.0,"start":2.0}]</textarea>
    <b>level name</b><br>
    <input id="name" value="custom" style="width:100%">
    <b>routes</b> (click route brush on map; Enter adds waypoint)<br>
    <textarea id="routesJson" rows="4">[]</textarea>
    <div>
      <button onclick="newRoute()">new route</button>
      <button onclick="undoWaypoint()">undo</button>
      <button onclick="syncRoutesJson()">update from JSON</button>
    </div>
    <b>options</b>
    <textarea id="options" rows="3">{"maxLifePoint":3,"initialCost":10,"costIncreaseTime":1.0,"maxCost":99}</textarea>
    <div id="log"></div>
  </div>
</div>
<script>
let grid=[], pal='floor', rows=6, cols=10;
let routes=[[{row:3,col:0},{row:3,col:9}]];   // list of waypoint arrays
let curRoute=0;
const PALETTE=[['floor','#2a2f47'],['wall','#464b63'],['hole','#0e1626'],
               ['start','#2a4a2a'],['end','#4a3a2a'],['deploy','#1a3a5a'],
               ['route','#9fc080']];
function paintPalette(){const p=document.getElementById('palette');p.innerHTML='';
  for(const [k,c] of PALETTE){const d=document.createElement('div');d.className='pal';
    d.style.background=c;d.textContent=k;d.onclick=()=>{pal=k};p.appendChild(d);}}
function newGrid(){rows=+document.getElementById('rows').value||6;
  cols=+document.getElementById('cols').value||10;
  grid=[];for(let r=0;r<rows;r++){grid.push([]);for(let c=0;c<cols;c++)
    grid[r].push(c===cols-1?'end':'floor');}
  grid[Math.floor(rows/2)][0]='start';
  draw();}
function draw(){const t=document.createElement('table');
  for(let r=0;r<rows;r++){const tr=document.createElement('tr');
    for(let c=0;c<cols;c++){const td=document.createElement('td');
      td.className=grid[r][c];
      let label=grid[r][c]==='route'?'R':grid[r][c][0].toUpperCase();
      for(let ri=0;ri<routes.length;ri++){const wp=routes[ri];
        for(let wi=0;wi<wp.length;wi++){
          if(wp[wi].row===r&&wp[wi].col===c){label='R'+(ri+1)+'#'+wi;}}
      }
      td.textContent=label;
      td.onclick=()=>{
        if(pal==='route'){
          routes[curRoute].push({row:r,col:c});draw();return;}
        grid[r][c]=pal;draw();};tr.appendChild(td);}
    t.appendChild(tr);}
  document.getElementById('map').innerHTML='';document.getElementById('map').appendChild(t);}
function newRoute(){routes.push([]);curRoute=routes.length-1;syncRoutesJson();draw();}
function undoWaypoint(){const wp=routes[curRoute];if(wp&&wp.length)wp.pop();syncRoutesJson();draw();}
function syncRoutesJson(){document.getElementById('routesJson').value=JSON.stringify(routes);}
function parseRoutes(){
  try{routes=JSON.parse(document.getElementById('routesJson').value||'[]');}
  catch(e){log('routes JSON error: '+e);return false;}
  if(!routes.length)routes=[[]];curRoute=routes.length-1;return true;}
function buildLevel(){
  const name=document.getElementById('name').value||'custom';
  const rr=+document.getElementById('routeRow').value||Math.floor(rows/2);
  const opts=JSON.parse(document.getElementById('options').value||'{}');
  const enemies=JSON.parse(document.getElementById('enemies').value||'[]');
  parseRoutes();
  const tiles=[];for(let r=0;r<rows;r++)for(let c=0;c<cols;c++){
    const k=grid[r][c];let tileKey='tile_floor',buildable=1,pass=1,height=1;
    if(k==='wall'){tileKey='tile_forbidden';buildable=0;pass=0;height=2;}
    if(k==='hole'){tileKey='tile_hole';buildable=0;pass=1;height=1;}
    if(k==='end'){tileKey='tile_end';buildable=0;pass=1;height=1;}
    if(k==='start'){tileKey='tile_road';buildable=0;pass=1;height=1;}
    tiles.push({tileKey,buildableType:buildable,passableMask:pass,heightType:height});}
  const wave=[];let seq=0;
  for(const e of enemies){let t=+e.start||2.0;
    for(let j=0;j<(+e.count||1);j++){wave.push({t:t+j*(+e.interval||2.0),
      key:e.key,routeIndex:0,actionType:'SPAWN',seq:seq++});}}
  const rtList=routes.map(wp=>{
    if(!wp.length)wp=[{row:rr,col:0},{row:rr,col:cols-1}];
    const start=wp[0], end=wp[wp.length-1];
    const cps=wp.slice(1).map(pos=>({type:{name:'MOVE'},position:pos}));
    return {startPosition:{row:start.row,col:start.col},
            endPosition:{row:end.row,col:end.col},
            checkpoints:cps};});
  return {name,map:{rows,cols,tiles},
    routes:rtList,
    waveTimeline:wave.sort((a,b)=>a.t-b.t),options:opts,enemyDbRefs:[]};
}
async function saveLevel(run){
  let lv;try{lv=buildLevel();}catch(e){log('build error: '+e);return;}
  const r=await fetch('/custom-level',{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify({level:lv,run:!!run})});
  const d=await r.json();log('saved '+d.name+(run?' -> running':''));
  if(run)location.href='/';
}
function log(m){const b=document.getElementById('log');
  b.textContent+=m+'\n';b.scrollTop=b.scrollHeight;}
paintPalette();newGrid();log('ready - paint tiles, set enemies, save & run');
</script>
</body>
</html>"""


_EDITOR_HTML = None


def editor_html():
    """Serve the editor page; prefer the standalone HTML file (editable,
    Chinese-safe) and fall back to the inline string."""
    global _EDITOR_HTML
    if _EDITOR_HTML is None:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "web_editor_page.html")
        try:
            with io.open(p, encoding="utf-8-sig") as f:
                _EDITOR_HTML = f.read()
        except Exception:
            _EDITOR_HTML = EDITOR_PAGE
    return _EDITOR_HTML


def ui_state(sim):
    return sim.snapshot()
