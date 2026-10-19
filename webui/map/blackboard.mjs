// Presentation-only adapter. Presence is not proof of a successful/current memory read.
export function inspectBlackboard(raw){
 if(raw==null)return {state:'missing',entries:[],issues:[]};
 if(!Array.isArray(raw))return {state:'invalid',entries:[],issues:['blackboard 必须是数组']};
 const entries=[],issues=[],seen=new Set();
 for(const pair of raw){
  if(!pair||typeof pair.key!=='string'||!pair.key){issues.push('无效键');continue;}
  if(seen.has(pair.key)){issues.push('重复键 '+pair.key);continue;}seen.add(pair.key);
  const text=pair.valueStr??pair.value_str??null;
  const number=typeof pair.value==='number'&&Number.isFinite(pair.value)?pair.value:null;
  if(number===null&&(typeof text!=='string'||!text)){issues.push('无效值 '+pair.key);continue;}
  entries.push({key:pair.key,value:number,valueStr:typeof text==='string'?text:null});
 }
 return {state:issues.length?'invalid':'available',entries,issues};
}
export function tileBlackboard(tile,sourceFormat){
 const board=inspectBlackboard(tile.blackboard);
 const number=key=>board.state==='available'?board.entries.find(e=>e.key===key&&!(e.valueStr?.length))?.value:null;
 const dynamic=number('dynamic'),direction=number('source_direction');
 const originalConfig=!sourceFormat; // Full PRTS configuration: use website's documented default.
 return {board,provenance:sourceFormat==='timeline'?`Timeline ${tile.blackboardMeta?.source==='runtime_parameters'?'运行时对象参数（不等于当前地块模式）':'初始配置参数'} · ${tile.blackboardMeta?.state??'未知'}${tile.blackboardMeta?.reason?' · '+tile.blackboardMeta.reason:''}`:sourceFormat==='maa'?'MAA 静态配置':'PRTS 初始配置',
  yinYang:dynamic!=null?(dynamic!==0?'effect_yinyang_yang':'effect_yinyang_yin'):originalConfig&&board.state!=='invalid'?'effect_yinyang_yin':null,
  gravity:direction===0?'G↑':direction===2?'G↓':'G↕'};
}
