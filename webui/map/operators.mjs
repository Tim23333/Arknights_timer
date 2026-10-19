import data from './operatorData.mjs';

const byKey=new Map(data.characters.map(item=>[item.key,item]));
const byName=new Map();
for(const definition of data.characters){
  const matches=byName.get(definition.name)||[];matches.push(definition);byName.set(definition.name,matches);
}
const icons=new Set(data.assets);

/** A visual lookup, never a synthesized game ID. Ambiguous names stay unknown. */
export function operatorVisual(item){
  if(item.kind!=='ally'||(item.entityKind&&item.entityKind!=='operator'))return null;
  const id=item.characterId;
  // A supplied but unrecognized ID must not be overridden with a name guess.
  const matches=byName.get(item.name)||[];
  const definition=id?byKey.get(id):matches.length===1?matches[0]:null;
  if(!definition)return null;
  return {definition,matchedBy:id?'角色 ID':'唯一中文名称',
    icon:icons.has(definition.key)?new URL(`./assets/portraits/${definition.key}.png`,import.meta.url).href:null};
}

/** PRTS range grids face right. Output uses Timeline bottom-left row/col. */
export function rotateRange(grids,x,y,direction){
  if(!Number.isInteger(x)||!Number.isInteger(y)||![0,1,2,3].includes(direction)||!Array.isArray(grids))return [];
  if(grids.some(p=>!Number.isInteger(p.row)||!Number.isInteger(p.col)))return [];
  return grids.map(({row:r,col:c})=>{
    const [dy,dx]=[[c,-r],[r,c],[-c,r],[-r,-c]][direction];
    return {row:y+dy,col:x+dx};
  });
}

export function operatorRange(item,{phase=0,mode='normal',skill=0,level=1}={}){
  const visual=operatorVisual(item);
  const unknown=reason=>({cells:[],reason,rangeId:null});
  if(!visual)return unknown('没有可靠对应的干员配置');
  if(mode==='off')return unknown('范围展示已关闭');
  if(!Number.isInteger(phase)||!Object.hasOwn(visual.definition.phases,phase))return unknown('该配置阶段不存在');
  let rangeId=visual.definition.phases[phase];
  if(mode==='skill'){
    const ranges=Number.isInteger(skill)?visual.definition.skills[skill]?.ranges:null;
    if(!ranges||!Number.isInteger(level)||level<1||level>ranges.length)return unknown('技能或技能等级配置不存在');
    // Null/empty range overrides inherit the selected phase's normal range.
    rangeId=ranges[level-1]||rangeId;
  }else if(mode!=='normal')return unknown('未知预览模式');
  const shape=data.ranges[rangeId];
  if(!shape||shape.direction!==1)return unknown('范围定义缺失或方向基准未知');
  const cells=rotateRange(shape.grids,item.x,item.y,item.direction);
  if(!cells.length)return unknown('部署坐标或朝向不可用');
  return {cells,rangeId,reason:'配置预览，非当前实际生效范围'};
}
