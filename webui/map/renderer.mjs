import {classes, tiles as definitions} from './definitions.mjs';
import {tileBlackboard} from './blackboard.mjs';
import {operatorVisual,operatorRange} from './operators.mjs';

const cls=(...names)=>names.filter(Boolean).map(name=>classes[name]||'').filter(Boolean).join(' ');
const renamed={tile_start_cooperate:'tile_start',tile_end_cooperate:'tile_end',tile_fence_bound:'tile_fence',tile_rcm_operator:'tile_road',tile_rcm_crate:'tile_road'};

/** Pick an existing DOM parent, retaining the exact entity position as offsets.
 * Only the anchor is bounded; unknown/outside game coordinates are never fixed.
 */
export function markerAnchor(x,y,rows,cols){
  if(!Number.isFinite(x)||!Number.isFinite(y)||x<0||y<0||x>=cols||y>=rows)return null;
  const col=Math.min(cols-1,Math.round(x)),row=Math.min(rows-1,Math.round(y));
  return {col,row,dx:x-col,dy:y-row};
}

/** Pure presentation: no network data channel, clocks, extrapolation or level files.
 * The caller owns freshness, session boundaries and policy. DOM identities survive
 * ordinary updates; only an unavailable board or a new session clears the scene.
 */
export function createMapRenderer(host) {
  const doc=host.ownerDocument, root=host.attachShadow({mode:'open'});
  const node=(tag,className,parent,text)=>{
    const element=doc.createElement(tag);element.className=className;
    if(text!==undefined)element.textContent=text;
    parent?.append(element);return element;
  };
  for(const file of ['reference.css','map.css']){
    const link=node('link','',root);link.rel='stylesheet';link.href=new URL(file,import.meta.url).href;
  }
  const controls=node('div','controls',root);
  const depth=node('button','',controls,'立体 / 平面');depth.type='button';depth.setAttribute('aria-pressed','true');
  const coords=node('button','',controls,'坐标');coords.type='button';coords.setAttribute('aria-pressed','true');
  const select=(label,options)=>{const wrap=node('label','',controls,label),input=node('select','',wrap);for(const [value,text] of options){const option=node('option','',input,text);option.value=value;}return input;};
  const rangeMode=select('范围 ',[['normal','普通配置'],['skill','技能配置'],['off','关闭']]);
  const rangePhase=select('手动阶段 ',[['0','E0'],['1','E1'],['2','E2']]);
  const rangeSkill=select('手动技能 ',[['0','技能 1'],['1','技能 2'],['2','技能 3']]);
  const rangeLevel=select('手动技能等级 ',Array.from({length:10},(_,i)=>[String(i+1),String(i+1)]));
  const operatorStatus=node('p','operator-status',root,'点击干员头像查看配置范围；阶段、技能和等级为手动预览值，不自动判断当前技能状态。头像使用程序内置的默认图标，无需联网。');
  const viewport=node('div','viewport',root), sizer=node('div','sizer',viewport);
  const scene=node('div','scene map_render_hover',sizer);
  const detail=node('pre','detail',root,'点击地块查看原始字段。');
  const cells=new Map(), markers=new Map();
  let shape='',session=null,selected=null,width=664,height=440,renderedTiles=null;
  let layoutDirty=true,fitWidth=0,extent=null,disposed=false;
  let selectedOperator=null,lastView=null;
  const rangeNodes=new Map();
  for(const control of [rangeMode,rangePhase,rangeSkill,rangeLevel])control.onchange=()=>drawRange();
  // Perspective can project tall maps beyond the nominal scene rectangle.
  // Measure static tile geometry only after actual geometry/style changes,
  // never on ordinary entity updates. Resize reuses these unscaled bounds.
  const fit=()=>{
    const available=viewport.clientWidth-4;
    if(disposed || available<=0 || (!layoutDirty && fitWidth===available))return;
    if(layoutDirty){
      scene.style.transform='scale(1)';scene.style.left='0px';scene.style.top='0px';
      const origin=scene.getBoundingClientRect();
      let left=0,top=0,right=width,bottom=height;
      for(const cell of cells.values())for(const element of [cell.node,...cell.node.children]){
        if(element.classList.contains('live-unit') || element.classList.contains('preview-range'))continue;
        const box=element.getBoundingClientRect();
        left=Math.min(left,box.left-origin.left-2);top=Math.min(top,box.top-origin.top-2);
        right=Math.max(right,box.right-origin.left+2);bottom=Math.max(bottom,box.bottom-origin.top+2);
      }
      extent={left,top,width:right-left,height:bottom-top};layoutDirty=false;
    }
    const scale=Math.min(1,available/extent.width);
    scene.style.transform=`scale(${scale})`;scene.style.left=-extent.left*scale+'px';scene.style.top=-extent.top*scale+'px';
    sizer.style.width=extent.width*scale+'px';sizer.style.height=extent.height*scale+'px';fitWidth=available;
  };
  const observer=new ResizeObserver(fit);observer.observe(viewport);
  const refit=()=>{layoutDirty=true;fit();};
  for(const link of root.querySelectorAll('link'))link.onload=refit;
  scene.addEventListener('transitionend',event=>{if(event.target===scene.firstElementChild && event.propertyName==='transform')refit();});
  depth.onclick=()=>{depth.setAttribute('aria-pressed',String(scene.classList.toggle('map_render_hover')));refit();};
  coords.onclick=()=>coords.setAttribute('aria-pressed',String(!scene.classList.toggle('hide-coords')));
  function clear(){scene.replaceChildren();cells.clear();markers.clear();rangeNodes.clear();shape='';selected=null;selectedOperator=null;lastView=null;renderedTiles=null;layoutDirty=true;detail.textContent='等待有效地图。';operatorStatus.textContent='点击干员头像查看配置范围（非实时生效范围）。';}
  function drawRange(){
    const item=lastView?.markers.find(item=>`${item.kind}:${item.id}`===selectedOperator);
    const result=item?operatorRange(item,{phase:Number(rangePhase.value),mode:rangeMode.value,skill:Number(rangeSkill.value),level:Number(rangeLevel.value)}):null;
    const wanted=new Set();
    for(const point of result?.cells||[]){
      const key=`${point.row}:${point.col}`,cell=cells.get(key);if(!cell)continue;
      wanted.add(key);let overlay=rangeNodes.get(key);
      if(!overlay){overlay=node('span','preview-range',cell.node);rangeNodes.set(key,overlay);}
      overlay.dataset.mode=rangeMode.value;
    }
    for(const [key,overlay] of rangeNodes)if(!wanted.has(key)){overlay.remove();rangeNodes.delete(key);}
    if(item){
      const visual=operatorVisual(item),source=lastView.sources.allyLayout;
      operatorStatus.textContent=`${item.name||visual?.definition.name||item.id} · ${visual?.matchedBy||'身份未知'} · 手动 E${rangePhase.value}${rangeMode.value==='skill'?` / 技能 ${Number(rangeSkill.value)+1} / 等级 ${rangeLevel.value}`:''} · ${result.reason}${result.rangeId?' · '+result.rangeId:''} · 布局来源 F${source?.sourceFrame??'未知'}${source?.state==='last_known'?'（旧）':''}`;
    }else{
      selectedOperator=null;operatorStatus.textContent='点击干员头像查看配置范围；阶段、技能和等级均为手动预览值，不代表当前战斗状态。';
    }
  }
  function show(cell){
    cells.get(selected)?.node.classList.remove('selected');selected=cell.key;cell.node.classList.add('selected');
    const t=cell.tile,bb=tileBlackboard(t,'timeline');
    detail.textContent=`(${t.col}, ${t.row}) · ${t.tileKey}\n高度 ${t.heightType??'未知'} · 建造类型 ${t.buildableType??'未知'} · 通行掩码 ${t.passableMask??'未知'}\n${bb.provenance}\nblackboard: ${JSON.stringify(bb.board.entries)}${bb.board.issues.length?'\n'+bb.board.issues.join('；'):''}\n地块许可不等于此刻可部署；参数不等于当前地块模式。`;
  }
  function decorate(cell,t){
    const key=t.tileKey,definition=definitions[key]||{},kind=definition.render_as||renamed[key]||key;
    const high=t.heightType===1||t.heightType==='HIGHLAND';
    const block=(high&&key!=='tile_flystart')||['tile_passable_wall','tile_passable_wall_forbidden'].includes(key);
    const box=['tile_start','tile_end','tile_flystart','tile_crate','tile_start_cooperate','tile_end_cooperate'].includes(key);
    const hole=['tile_hole','tile_deepwater'].includes(key),fence=['tile_fence','tile_fence_bound'].includes(key);
    const allowed=['MELEE','RANGED','ALL'].includes(t.buildableType)||(typeof t.buildableType==='number'&&t.buildableType>0);
    const tile=cell.node;
    tile.className=cls('tile',kind,block&&'tile_block',box&&'tile_box',hole&&'tile_hole',fence&&'tile_fence',allowed&&key!=='tile_crate'&&'tile_deployable')+(selected===cell.key?' selected':'');
    tile.style.zIndex=5900-10*t.row;tile.dataset.key=key;tile.setAttribute('aria-label',`${t.col},${t.row} ${key}`);
    // Only decorative children change. Preserve attached entity nodes and focus.
    for(const child of [...tile.children])if(!child.classList.contains('live-unit')&&!child.classList.contains('preview-range'))child.remove();
    if(block||box||hole||fence)for(const face of ['tile_box_left','tile_box_top','tile_box_right'])node('span',cls(face),tile);
    let index=0;
    const overlay=(type,text,options=[])=>{const e=node('span',cls('tile_overlay',type,...options,options.includes('content_on_top')&&'tile_block_overlay','enable_animation'),tile,text);e.style.zIndex=5900-10*t.row+(++index);return e;};
    const bb=tileBlackboard(t,'timeline');
    if(definition.effect){
      if(!key.startsWith('tile_yinyang')||bb.yinYang||key==='tile_yinyang_switch')overlay(definition.effect,undefined,[block&&'content_on_top',box&&'content_on_box',bb.yinYang]);
      else node('span','unknown',tile,'?');
    }
    if(!['tile_hole','tile_empty','tile_deepwater','tile_smog'].includes(key)&&(block||!definition.content)){
      const e=overlay('coord',String.fromCharCode(65+t.row)+(t.col+1),[block&&'content_fade_out_perspective']);e.dataset.coordinate='';
    }
    if(definition.content)overlay('content',definition.content,[block&&definition.content_on_top&&'content_on_top',box&&definition.content_on_top&&'content_on_box',key==='tile_hole'&&'content_fade_out_perspective']);
    if(key==='tile_grvtybtn')overlay('button_tile_grvtybtn',bb.gravity);
    if(allowed&&key!=='tile_crate')overlay('deployable',undefined,[block&&'content_on_top']);
    tile.title=`${key} · (${t.col}, ${t.row})${!definitions[key]?' · 专属样式未知':''}`;
  }
  function update(view,nextSession){
    if(session!==nextSession){clear();session=nextSession;}
    host.hidden=!view.available;
    if(!view.available){clear();return;}
    const nextShape=`${view.rows}:${view.cols}`;
    if(shape!==nextShape){
      clear();shape=nextShape;width=Math.max(664,view.cols*50+100);height=view.rows*50+94;
      detail.textContent='点击地块查看原始字段。';
      scene.style.width=width+'px';scene.style.height=height+'px';
      const rows=node('div',cls('tile_rows'),scene);
      for(let row=0;row<view.rows;row++){
        const line=node('div',cls('tile_row'),rows);
        for(let col=0;col<view.cols;col++){
          const wrap=node('div',cls('tile_wrapper'),line), tile=node('div','',wrap),key=`${row}:${col}`;
          const cell={key,node:tile,tile:null,signature:null};cells.set(key,cell);
          tile.tabIndex=0;tile.setAttribute('role','button');tile.dataset.cell=key;
          tile.onclick=()=>show(cell);tile.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();show(cell);}};
        }
      }
    }
    if(renderedTiles!==view.tiles){
      for(const t of view.tiles){
        const cell=cells.get(`${t.row}:${t.col}`);if(!cell)continue;
        const geometryChanged=!cell.tile || cell.tile.tileKey!==t.tileKey || cell.tile.heightType!==t.heightType;
        const signature=JSON.stringify(t);cell.tile=t;
        if(cell.signature!==signature){
          if(geometryChanged)layoutDirty=true;
          decorate(cell,t);cell.signature=signature;if(selected===cell.key)show(cell);
        }
      }
      renderedTiles=view.tiles;
    }
    fit();
    const wanted=new Set();
    for(const item of view.markers){
      const anchor=markerAnchor(item.x,item.y,view.rows,view.cols);
      if(!anchor)continue;
      const {col,row,dx,dy}=anchor,cell=cells.get(`${row}:${col}`);
      if(!cell)continue;
      const key=`${item.kind}:${item.id}`;wanted.add(key);let marker=markers.get(key);
      if(!marker){marker=node('span','live-unit '+item.kind);markers.set(key,marker);}
      if(marker.parentNode!==cell.node)cell.node.append(marker);
      const source=view.sources[item.kind==='enemy'?'enemyLayout':'allyLayout'];
      const old=source.state==='last_known'||item.displayOld===true;
      const label=(item.kind==='enemy'?'敌':'友')+(item.directionName||'')+(old?'·旧':'');
      const visual=operatorVisual(item),icon=visual?.icon||'';
      // Rebuild only when identity/portrait changes, not every sampling frame.
      if(marker.dataset.icon!==icon){
        marker.replaceChildren();marker.dataset.icon=icon;
        marker.classList.toggle('portrait',Boolean(icon));
        if(icon){const img=node('img','operator-icon',marker);img.alt=item.name||visual.definition.name;img.referrerPolicy='no-referrer';img.onerror=()=>{img.hidden=true;marker.classList.add('portrait-failed');};img.src=icon;}
        marker.classList.remove('portrait-failed');
        node('span','unit-label',marker);
      }
      const caption=marker.querySelector('.unit-label');if(caption.textContent!==label)caption.textContent=label;
      if(visual){
        marker.tabIndex=0;marker.setAttribute('role','button');marker.setAttribute('aria-label',`${item.name||visual.definition.name}：查看配置范围`);
        marker.onclick=event=>{event.stopPropagation();selectedOperator=key;drawRange();};
        marker.onkeydown=event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();event.stopPropagation();selectedOperator=key;drawRange();}};
      }else{marker.removeAttribute('tabindex');marker.removeAttribute('role');marker.removeAttribute('aria-label');marker.onclick=null;marker.onkeydown=null;}
      marker.style.opacity=old?'0.6':'1';
      marker.style.transform=`translate(${dx*52}px,${-dy*52}px) translateZ(28px)`;
      marker.title=`${item.name||item.enemyId||item.characterId||item.id} · (${item.x}, ${item.y})\n${old?'旧 · ':''}来源 F${item.displayFrame??source.sourceFrame??'未知'}`;
    }
    for(const [key,marker] of markers)if(!wanted.has(key)){marker.remove();markers.delete(key);}
    lastView=view;drawRange();
  }
  return {update,destroy(){disposed=true;observer.disconnect();root.replaceChildren();}};
}
