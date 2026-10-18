/** Presentation-only accepted evidence, scoped to an entity, battle and policy.
 * No clocks are sampled here. Frames always come from the corresponding field,
 * never the containing message or the independent game-clock cache.
 */
const valid=new Set(['current','static','historical']);
const at=(value,path)=>path.split('.').reduce((item,key)=>item!=null && Object.hasOwn(item,key)?item[key]:undefined,value);
const stateOf=record=>record?.collectionState || record?.state;
const reasons={unsupported_in_source:'当前来源未支持',frame_inconsistent:'本次读取跨逻辑帧',
  detail_read_failed:'详情读取失败',source_stopped:'采集已停止'};
const framed=value=>Number.isInteger(value) && value>=0;

export function createDetailEvidence(kind,id) {
  const cache=new Map(), diagnostics=new Map(), diagnosticFrames=new Map();let scope;
  return {project(input) {
    const {basic,detail,basicMeta={},detailMeta={},policy={generation:0,fields:[]},historical=false,connected=true}=input;
    const nextScope=JSON.stringify([id,basicMeta.sessionId,policy.generation]);
    const stopped=['source_stopped','session_changed','adb_changed'].includes(basicMeta.reason);
    const owns=(data,meta)=>data && String(data.id)===String(id)
      && (meta.sessionId==null || basicMeta.sessionId==null || meta.sessionId===basicMeta.sessionId)
      && (meta.policyGeneration==null || meta.policyGeneration===policy.generation);
    if(scope!==nextScope || stopped || historical || (basic && !owns(basic,basicMeta)) || (detail && !owns(detail,detailMeta))) {
      cache.clear();diagnostics.clear();diagnosticFrames.clear();
    }
    scope=nextScope;
    const basicData=owns(basic,basicMeta)?basic:null, detailData=owns(detail,detailMeta)?detail:null;
    const fields=new Map((policy.fields || []).map(field=>[field.id,field]));
    const disabled=(fieldId,source)=>fields.get(fieldId)?.collect===false
      || (source==='detail' && fields.get(fieldId)?.display===false);
    function read(source,path,key,{optional=false,staticValue=false}={}) {
      const fieldId=`${kind}${source==='detail'?'_detail':''}.${key}`, token=`${fieldId}:${path}`;
      const candidates=(source==='detail'?[[detailData,detailMeta]]:[[basicData,basicMeta],[detailData,detailMeta]])
        .filter(([data])=>data).map(([data,meta])=>{
          const record=data.fieldStates?.[fieldId] || {}, state=stateOf(record), value=at(data,path);
          const accepted=valid.has(state) && (source==='detail' || meta.collectionState!=='unavailable');
          return {record,state,value,accepted,sourceFrame:staticValue?null:record.sourceFrame ?? null,
            usable:!stopped && (staticValue || accepted || (!state && meta.collectionState!=='unavailable'))
              && (value!=null || (optional && accepted && at(data,path.split('.').slice(0,-1).join('.'))!=null))};
        });
      // A disabled record is a tombstone, not an invitation to resurrect cache.
      if(disabled(fieldId,source) || candidates.some(item=>item.state==='not_collected')) {
        cache.delete(token);
        return {text:fields.get(fieldId)?.collect===false || candidates.some(item=>item.state==='not_collected')?'未采集':'未展示',
          freshness:'not_collected',title:'字段策略已关闭'};
      }
      const usable=candidates.filter(item=>item.usable).sort((a,b)=>
        Number(b.accepted)-Number(a.accepted) || (framed(b.sourceFrame)?b.sourceFrame:-1)-(framed(a.sourceFrame)?a.sourceFrame:-1));
      const selected=usable[0], held=cache.get(token);
      let cell;
      if(selected && !(held && framed(held.sourceFrame) && (!framed(selected.sourceFrame) || held.sourceFrame>selected.sourceFrame))) {
        const freshness=historical?'historical':!connected?'last_known':staticValue?'static':selected.state || 'unverified';
        cell={value:selected.value,sourceFrame:selected.sourceFrame,domain:source,freshness,
          accepted:selected.accepted,absent:selected.value==null};
        // Accepted optional absence is also evidence: keep a tombstone so a
        // delayed packet cannot resurrect a previous countdown/animation value.
        if((selected.accepted || staticValue) && connected && !historical) cache.set(token,structuredClone(cell));
      } else if(held && !stopped && !historical) cell={...structuredClone(held),freshness:'last_known'};
      else {
        const reason=candidates[0]?.record.reason || (source==='detail'?detailMeta:basicMeta).reason;
        return {text:reasons[reason] || '不可用',freshness:'unavailable',
          title:reason?`${reasons[reason] || reason}；当前范围内没有可用读数`:'当前接口未返回此值，未补默认值'};
      }
      return {...cell,title:`${cell.freshness==='last_known'?'最后有效值（非当前帧）':cell.freshness==='historical'?'历史记录':'来源读数'} · 来源帧 ${cell.sourceFrame ?? '—'}`};
    }
    function localDiagnostics() {
      const entries=detailData?.localDiagnostics;
      // An accepted empty list removes previous diagnostics for that group. A
      // failed group retains its own last-known rows; no pointer is dereferenced.
      const acceptedGroups=new Set(), groups=new Set([...diagnosticFrames.keys(),...(entries || []).map(entry=>entry.fieldId)]);
      for(const fieldId of groups) {
        const domain=fieldId.includes('_detail.')?'detail':'basic', record=detailData?.fieldStates?.[fieldId];
        const state=stateOf(record), frame=record?.sourceFrame ?? null, previous=diagnosticFrames.get(fieldId);
        const off=disabled(fieldId,domain) || state==='not_collected';
        const accepted=!stopped && !historical && Array.isArray(entries) && valid.has(state)
          && !(framed(previous) && (!framed(frame) || previous>frame));
        if(accepted) {acceptedGroups.add(fieldId);diagnosticFrames.set(fieldId,frame);}
        if(off || accepted) for(const [key,entry] of diagnostics) if(entry.fieldId===fieldId) diagnostics.delete(key);
        if(off) diagnosticFrames.delete(fieldId);
      }
      const current=new Set();
      if(!stopped && !historical) for(const entry of entries || []) {
        const domain=entry.fieldId.includes('_detail.')?'detail':'basic';
        const record=detailData.fieldStates?.[entry.fieldId] || {}, state=stateOf(record);
        if(disabled(entry.fieldId,domain) || (state && !acceptedGroups.has(entry.fieldId))) continue;
        const previous=diagnostics.get(entry.key), frame=record.sourceFrame ?? null;
        if(previous && framed(previous.sourceFrame) && (!framed(frame) || previous.sourceFrame>frame)) continue;
        diagnostics.set(entry.key,{...structuredClone(entry),sourceFrame:frame,domain,state});current.add(entry.key);
      }
      return [...diagnostics.values()].map(entry=>({...entry,
        freshness:connected && current.has(entry.key)?entry.state || 'unverified':'last_known',
        title:`${connected && current.has(entry.key)?'本地诊断':'最后有效本地诊断（旧）'}（不访问对象） · 来源帧 ${entry.sourceFrame ?? '—'}`}));
    }
    return {basicData,detailData,read,localDiagnostics};
  }};
}

/** Composite display values cannot claim one frame when their inputs differ. */
export function combineEvidence(cell,inputs) {
  const sources=inputs.flatMap(item=>item.sources || [item]);
  const frames=[...new Set(sources.map(item=>item.sourceFrame).filter(framed))];
  const mixed=frames.length>1, old=inputs.some(item=>item.freshness==='last_known');
  return {...cell,sources,sourceFrame:mixed?null:frames[0] ?? null,
    freshness:old || mixed?'last_known':inputs.some(item=>item.freshness==='historical')?'historical':cell.freshness,
    title:inputs.map((item,index)=>`输入 ${index+1}：${item.title}`).join('；')};
}

export function summarizeFrames(tabs,domain,attemptFrame) {
  const cells=tabs.flatMap(tab=>tab.rows.flatMap(row=>Object.values(row)))
    .filter(cell=>cell && typeof cell==='object' && cell.value!==undefined)
    .flatMap(cell=>cell.sources || [cell]).filter(cell=>cell.domain===domain);
  const frames=[...new Set(cells.map(cell=>cell.sourceFrame).filter(framed))].sort((a,b)=>a-b);
  const old=cells.some(cell=>cell.freshness==='last_known');
  const text=frames.length>1?`混合 F${frames[0]}–F${frames.at(-1)}`:frames.length?`F${frames[0]}`:cells.length?'静态 / 无帧':'—';
  return {text,sourceFrame:frames.length===1?frames[0]:null,freshness:old?'last_known':cells.some(cell=>cell.freshness==='historical')?'historical':'',
    title:`已显示值来源：${frames.length?frames.map(frame=>`F${frame}`).join('、'):'无逻辑帧证据'}${old?'；包含旧值':''}；本次消息尝试帧：${attemptFrame ?? '—'}（不作为已显示值来源）`};
}
